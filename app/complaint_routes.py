import json
import logging

from datetime import datetime, timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.emergency_screening import screen_emergency
from app.department_config import CATEGORY_TO_DEPARTMENT
from app.dependencies import get_db, get_current_user
from app.models import Complaint, Department, User, Notification
from app.schemas.complaint import ComplaintCreate, ComplaintResponse


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/complaints",
    tags=["Complaints"],
)


@router.post(
    "/",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
)
def create_complaint(
    data: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only citizens can submit complaints.
    if current_user.role != "citizen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only citizens can submit complaints.",
        )

    category_key = data.category

    # Validate category.
    if category_key not in CATEGORY_TO_DEPARTMENT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid complaint category: '{category_key}'. "
                f"Allowed categories: "
                f"{', '.join(sorted(CATEGORY_TO_DEPARTMENT))}."
            ),
        )

    # Find responsible department.
    department_name = CATEGORY_TO_DEPARTMENT[category_key]

    department = db.scalar(
        select(Department).where(
            Department.name == department_name,
            Department.is_active.is_(True),
        )
    )

    if department is None:
        logger.error(
            "Department configuration missing: %s",
            department_name,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The responsible department is currently unavailable. "
                "Please try again later."
            ),
        )

    # Emergency screening.
    complaint_text = f"{data.title}. {data.description}"

    try:
        emergency_result = screen_emergency(complaint_text)

    except Exception:
        logger.exception(
            "Emergency screening failed for citizen ID %s",
            current_user.id,
        )

        # Fail safely: do not classify an unchecked complaint as routine.
        emergency_result = {
            "emergency_review_required": True,
            "matched_indicators": ["screening_unavailable"],
            "priority": "urgent_review",
            "message": (
                "Automated screening was unavailable. "
                "This complaint requires urgent human review. "
                "This is not confirmation of an emergency."
            ),
        }

    emergency_review = emergency_result["emergency_review_required"]

    sla_hours = 4 if emergency_review else 72

    sla_deadline = datetime.now() + timedelta(hours=sla_hours)

    # Create complaint.
    complaint = Complaint(
        title=data.title,
        description=data.description,
        category=category_key,
        location=data.location,
        latitude=data.latitude,
        longitude=data.longitude,
        status="submitted",
        sla_deadline=sla_deadline,
        escalation_level=0,
        escalated_at=None,
        citizen_id=current_user.id,
        department_id=department.id,
        emergency_review_required=emergency_review,
        priority=emergency_result["priority"],
        matched_indicators_json=json.dumps(
            emergency_result["matched_indicators"]
        ),
    )

    try:
        db.add(complaint)
        db.flush()

        # Find active authorities in the responsible department.
        authorities = db.scalars(
            select(User).where(
                User.role == "authority",
                User.department_id == department.id,
                User.is_active.is_(True),
            )
        ).all()

        # Create authority notifications.
        for authority in authorities:
            db.add(
                Notification(
                    user_id=authority.id,
                    complaint_id=complaint.id,
                    title="New complaint assigned",
                    message=(
                        f"A new {category_key} complaint "
                        f"has been submitted: {complaint.title}."
                    ),
                    notification_type="new_complaint",
                    is_read=False,
                )
            )

        # Save complaint and notifications atomically.
        db.commit()
        db.refresh(complaint)

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Complaint creation failed for citizen ID %s",
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The complaint could not be saved. Please try again.",
        ) from exc

    # Build response.
    try:
        response = ComplaintResponse.model_validate(complaint)

        response.emergency_message = emergency_result["message"]

        return response

    except Exception:
        logger.exception(
            "Complaint response creation failed for complaint ID %s",
            complaint.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The complaint was saved, but its response could not be generated.",
        )


@router.get(
    "/my",
    response_model=list[ComplaintResponse],
)
def get_my_complaints(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size

    complaints = db.scalars(
        select(Complaint)
        .options(joinedload(Complaint.department))
        .where(
            Complaint.citizen_id == current_user.id
        )
        .order_by(
            Complaint.created_at.desc()
        )
        .offset(offset)
        .limit(page_size)
    ).all()

    return complaints
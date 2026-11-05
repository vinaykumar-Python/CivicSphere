import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import (
    Complaint,
    ComplaintStatusHistory,
    Department,
    User,
    Notification,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/authority",
    tags=["Department Authority"],
)


class ComplaintStatusUpdate(BaseModel):
    status: str = Field(
        pattern=r"^(in_progress|resolved|rejected)$"
    )


def require_authority(current_user: User) -> None:
    if current_user.role != "authority":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only department authorities can access this resource.",
        )

    if current_user.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not assigned to a department.",
        )


def get_active_department(
    db: Session,
    current_user: User,
) -> Department:
    department = db.get(
        Department,
        current_user.department_id,
    )

    if department is None or not department.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your department is inactive or unavailable.",
        )

    return department


@router.get("/me")
def get_authority_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_authority(current_user)

    department = get_active_department(db, current_user)

    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "role": current_user.role,
        "department_id": department.id,
        "department_name": department.name,
    }


@router.get("/complaints")
def get_department_complaints(
    status_filter: str | None = Query(default=None, max_length=30),
    category: str | None = Query(default=None, max_length=80),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_authority(current_user)

    department = get_active_department(db, current_user)

    query = select(Complaint).where(
        Complaint.department_id == department.id
    )

    if status_filter and status_filter.strip():
        allowed_statuses = {
            "submitted",
            "in_progress",
            "resolved",
            "rejected",
        }

        normalized_status = status_filter.strip().lower()

        if normalized_status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid status filter.",
            )

        query = query.where(
            Complaint.status == normalized_status
        )

    if category and category.strip():
        query = query.where(
            func.lower(Complaint.category)
            == category.strip().lower()
        )

    if search and search.strip():
        search_term = f"%{search.strip()}%"

        query = query.where(
            Complaint.title.ilike(search_term)
            | Complaint.description.ilike(search_term)
            | Complaint.location.ilike(search_term)
        )

    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    total_pages = (total + page_size - 1) // page_size

    paginated_query = (
        query
        .order_by(
            Complaint.emergency_review_required.desc(),
            Complaint.created_at.desc(),
            Complaint.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    complaints = db.scalars(paginated_query).all()

    items = [
        {
            "id": complaint.id,
            "title": complaint.title,
            "description": complaint.description,
            "category": complaint.category,
            "location": complaint.location,
            "latitude": complaint.latitude,
            "longitude": complaint.longitude,
            "status": complaint.status,
            "emergency_review_required": (
                complaint.emergency_review_required
            ),
            "priority": complaint.priority,
            "matched_indicators": complaint.matched_indicators,
            "citizen_id": complaint.citizen_id,
            "authority_id": complaint.authority_id,
            "department_id": complaint.department_id,
            "created_at": complaint.created_at,
            "updated_at": complaint.updated_at,
            "sla_deadline": complaint.sla_deadline,
            "escalation_level": complaint.escalation_level,
            "escalated_at": complaint.escalated_at,
        }
        for complaint in complaints
    ]

    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1 and total > 0,
        },
    }


@router.patch("/complaints/{complaint_id}/status")
def update_complaint_status(
    complaint_id: int,
    data: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_authority(current_user)

    department = get_active_department(db, current_user)

    # Lock the complaint row during the status update.
    # Databases supporting SELECT FOR UPDATE can then prevent
    # simultaneous updates from creating conflicting history.
    complaint = db.scalar(
        select(Complaint)
        .where(
            Complaint.id == complaint_id,
            Complaint.department_id == department.id,
        )
        .with_for_update()
    )

    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found in your department.",
        )

    old_status = complaint.status

    closed_statuses = {"resolved", "rejected"}

    if old_status in closed_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This complaint is already closed. "
                "A separate reopen process is required."
            ),
        )

    if old_status == data.status:
        return {
            "message": "Complaint already has this status.",
            "complaint_id": complaint.id,
            "status": complaint.status,
            "department_name": department.name,
        }

    status_messages = {
        "in_progress": (
            "Your complaint is now being reviewed and addressed."
        ),
        "resolved": (
            "Your complaint has been marked as resolved."
        ),
        "rejected": (
            "Your complaint has been rejected. Please review its history."
        ),
    }

    try:
        complaint.status = data.status

        history_entry = ComplaintStatusHistory(
            complaint_id=complaint.id,
            old_status=old_status,
            new_status=data.status,
            changed_by_user_id=current_user.id,
            note=f"Status updated by {department.name}.",
        )

        notification = Notification(
            user_id=complaint.citizen_id,
            complaint_id=complaint.id,
            title=(
                "Complaint status: "
                f"{data.status.replace('_', ' ').title()}"
            ),
            message=(
                f"Your complaint '{complaint.title}' has been updated. "
                f"{status_messages[data.status]}"
            ),
            notification_type="status_update",
            is_read=False,
        )

        db.add(history_entry)
        db.add(notification)

        # Save status, history and notification together.
        db.commit()
        db.refresh(complaint)

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Complaint status update failed. Complaint ID: %s, "
            "Authority ID: %s",
            complaint_id,
            current_user.id,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Could not update complaint status, history "
                "and notification."
            ),
        ) from exc

    return {
        "message": (
            "Complaint status updated and history recorded successfully."
        ),
        "complaint_id": complaint.id,
        "old_status": old_status,
        "status": complaint.status,
        "department_name": department.name,
    }
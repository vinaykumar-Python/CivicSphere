from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import Complaint, User

router = APIRouter(
    prefix="/api/analytics",
    tags=["Citizen Analytics"]
)


@router.get("/citizen")
def get_citizen_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    citizen_filter = Complaint.citizen_id == current_user.id

    # Count the citizen's complaints by status.
    status_rows = db.execute(
        select(
            Complaint.status,
            func.count(Complaint.id).label("total"),
        )
        .where(citizen_filter)
        .group_by(Complaint.status)
    ).all()

    status_counts = {
        complaint_status: total
        for complaint_status, total in status_rows
    }

    # Count the citizen's complaints by category.
    category_rows = db.execute(
        select(
            Complaint.category,
            func.count(Complaint.id).label("total"),
        )
        .where(citizen_filter)
        .group_by(Complaint.category)
        .order_by(func.count(Complaint.id).desc())
    ).all()

    total_complaints = db.scalar(
        select(func.count(Complaint.id)).where(citizen_filter)
    ) or 0

    return {
        "citizen": {
            "id": current_user.id,
            "full_name": current_user.full_name,
        },
        "summary": {
            "total_complaints": total_complaints,
            "submitted": status_counts.get("submitted", 0),
            "in_progress": status_counts.get("in_progress", 0),
            "resolved": status_counts.get("resolved", 0),
            "rejected": status_counts.get("rejected", 0),
        },
        "by_category": [
            {"category": category, "total": total}
            for category, total in category_rows
        ],
    }

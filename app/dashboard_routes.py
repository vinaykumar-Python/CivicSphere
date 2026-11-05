from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, get_current_user
from app.models import Complaint, User

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


@router.get("/citizen")
def get_citizen_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    citizen_filter = Complaint.citizen_id == current_user.id

    # Calculate complaint counts directly in the database.
    status_counts = db.execute(
        select(
            Complaint.status,
            func.count(Complaint.id),
        )
        .where(citizen_filter)
        .group_by(Complaint.status)
    ).all()

    counts = {
        status: count
        for status, count in status_counts
    }

    total_complaints = sum(counts.values())

    # Fetch only the five most recent complaints.
    recent_complaints = db.scalars(
        select(Complaint)
        .options(joinedload(Complaint.department))
        .where(citizen_filter)
        .order_by(
            Complaint.created_at.desc(),
            Complaint.id.desc(),
        )
        .limit(5)
    ).all()

    return {
        "citizen": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
        },
        "summary": {
            "total_complaints": total_complaints,
            "submitted": counts.get("submitted", 0),
            "in_progress": counts.get("in_progress", 0),
            "resolved": counts.get("resolved", 0),
            "rejected": counts.get("rejected", 0),
        },
        "recent_complaints": [
            {
                "id": complaint.id,
                "title": complaint.title,
                "category": complaint.category,
                "location": complaint.location,
                "status": complaint.status,
                "department_name": (
                    complaint.department.name
                    if complaint.department is not None
                    else None
                ),
                "created_at": complaint.created_at,
            }
            for complaint in recent_complaints
        ],
    }
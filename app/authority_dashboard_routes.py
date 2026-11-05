from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import Complaint, Department, User

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Authority Dashboard"]
)


@router.get("/authority")
def get_authority_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only department authorities can access this dashboard.
    if current_user.role != "authority":
        raise HTTPException(
            status_code=403,
            detail="Only department authorities can access this dashboard."
        )

    if current_user.department_id is None:
        raise HTTPException(
            status_code=403,
            detail="Your account is not assigned to a department."
        )

    department = db.get(Department, current_user.department_id)

    if department is None or not department.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your department is unavailable or inactive."
        )

    # Count complaints assigned to this authority's department.
    status_counts = db.execute(
        select(
            Complaint.status,
            func.count(Complaint.id)
        )
        .where(Complaint.department_id == department.id)
        .group_by(Complaint.status)
    ).all()

    counts = {
        complaint_status: count
        for complaint_status, count in status_counts
    }

    total_complaints = sum(counts.values())

    overdue_complaints = db.scalar(
        select(func.count(Complaint.id)).where(
            Complaint.department_id == department.id,
            Complaint.status.notin_(("resolved", "rejected")),
            Complaint.sla_deadline.is_not(None),
            Complaint.sla_deadline <= datetime.now(),
        )
    ) or 0

    # Fetch the five most recent complaints for this department.
    recent_complaints = db.scalars(
        select(Complaint)
        .where(Complaint.department_id == department.id)
        .order_by(Complaint.created_at.desc())
        .limit(5)
    ).all()

    return {
        "authority": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email
        },
        "department": {
            "id": department.id,
            "name": department.name
        },
        "summary": {
            "total_complaints": total_complaints,
            "submitted": counts.get("submitted", 0),
            "in_progress": counts.get("in_progress", 0),
            "resolved": counts.get("resolved", 0),
            "rejected": counts.get("rejected", 0),
            "overdue": overdue_complaints,
        },
        "recent_complaints": [
            {
                "id": complaint.id,
                "title": complaint.title,
                "category": complaint.category,
                "location": complaint.location,
                "status": complaint.status,
                "created_at": complaint.created_at
            }
            for complaint in recent_complaints
        ]
    }

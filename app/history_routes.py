from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import (
    Complaint,
    ComplaintStatusHistory,
    Department,
    User,
)

router = APIRouter(
    prefix="/api/complaints",
    tags=["Complaint History"],
)


@router.get("/{complaint_id}/history")
def get_complaint_history(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    complaint = db.get(Complaint, complaint_id)

    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found.",
        )

    # Citizens can view only their own complaints.
    if current_user.role == "citizen":
        if complaint.citizen_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found.",
            )

    # Authorities can view only their department's complaints.
    elif current_user.role == "authority":
        if current_user.department_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account is not assigned to a department.",
            )

        department = db.get(
            Department,
            current_user.department_id,
        )

        if department is None or not department.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your department is inactive or unavailable.",
            )

        if complaint.department_id != department.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Complaint not found.",
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view complaint history.",
        )

    # Fetch the original citizen.
    citizen = db.get(User, complaint.citizen_id)

    # Original complaint submission is the first timeline event.
    timeline = [
        {
            "event_type": "submission",
            "old_status": None,
            "new_status": "submitted",
            "changed_by_user_id": complaint.citizen_id,
            "changed_by_name": (
                citizen.full_name if citizen else "Citizen"
            ),
            "changed_by_role": "citizen",
            "changed_at": complaint.created_at,
            "note": "Complaint submitted successfully.",
        }
    ]

    # Fetch all history entries and updater department information
    # in one query instead of querying separately for every entry.
    history_records = db.execute(
        select(
            ComplaintStatusHistory,
            User.full_name,
            User.role,
            Department.name,
        )
        .outerjoin(
            User,
            ComplaintStatusHistory.changed_by_user_id == User.id,
        )
        .outerjoin(
            Department,
            User.department_id == Department.id,
        )
        .where(
            ComplaintStatusHistory.complaint_id == complaint.id
        )
        .order_by(
            ComplaintStatusHistory.changed_at.asc(),
            ComplaintStatusHistory.id.asc(),
        )
    ).all()

    for item, updater_name, updater_role, department_name in history_records:
        timeline.append(
            {
                "event_type": "status_update",
                "old_status": item.old_status,
                "new_status": item.new_status,
                "changed_by_user_id": item.changed_by_user_id,
                "changed_by_name": updater_name or "Unknown user",
                "changed_by_role": updater_role or "unknown",
                "department_name": department_name,
                "changed_at": item.changed_at,
                "note": item.note,
            }
        )

    return {
        "complaint_id": complaint.id,
        "complaint_title": complaint.title,
        "current_status": complaint.status,
        "department_name": complaint.department_name,
        "history": timeline,
    }
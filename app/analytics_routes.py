from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, cast, String
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import Complaint, Department, User

router = APIRouter(
    prefix="/api/analytics",
    tags=["Department Analytics"],
)


@router.get("/authority")
def get_authority_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "authority":
        raise HTTPException(
            status_code=403,
            detail="Only department authorities can access these analytics.",
        )

    if current_user.department_id is None:
        raise HTTPException(
            status_code=403,
            detail="Your account is not assigned to a department.",
        )

    department = db.get(Department, current_user.department_id)

    if department is None or not department.is_active:
        raise HTTPException(
            status_code=403,
            detail="Your department is unavailable or inactive.",
        )

    department_filter = Complaint.department_id == department.id

    category_rows = db.execute(
        select(
            Complaint.category,
            func.count(Complaint.id).label("total"),
        )
        .where(department_filter)
        .group_by(Complaint.category)
        .order_by(func.count(Complaint.id).desc())
    ).all()

    status_rows = db.execute(
        select(
            Complaint.status,
            func.count(Complaint.id).label("total"),
        )
        .where(department_filter)
        .group_by(Complaint.status)
    ).all()

    # Portable month grouping for SQLite and MySQL.
    month_expression = cast(
        func.strftime("%Y-%m", Complaint.created_at),
        String,
    )

    if db.bind.dialect.name == "mysql":
        month_expression = func.date_format(
            Complaint.created_at,
            "%Y-%m",
        )

    monthly_rows = db.execute(
        select(
            month_expression.label("month"),
            func.count(Complaint.id).label("total"),
        )
        .where(
            department_filter,
            Complaint.created_at.is_not(None),
        )
        .group_by(month_expression)
        .order_by(month_expression)
    ).all()

    return {
        "department": {
            "id": department.id,
            "name": department.name,
        },
        "by_category": [
            {"category": category, "total": total}
            for category, total in category_rows
        ],
        "by_status": [
            {"status": status, "total": total}
            for status, total in status_rows
        ],
        "monthly_trend": [
            {"month": month, "total": total}
            for month, total in monthly_rows
            if month is not None
        ],
    }
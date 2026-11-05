from sqlalchemy import select
from app.database import SessionLocal
from app.models import User, Department, Complaint

db = SessionLocal()

try:
    authorities = db.scalars(
        select(User).where(
            User.role == "authority",
            User.is_active == True
        )
    ).all()

    print("\n========== AUTHORITY DEPARTMENT AUDIT ==========\n")

    for authority in authorities:
        department = db.get(Department, authority.department_id)

        if not department:
            print(f"FAIL: {authority.email} has no valid department")
            continue

        complaint_count = db.scalar(
            select(Complaint.id).where(
                Complaint.department_id == department.id
            ).count()
        ) if False else None

        complaint_count = len(
            db.scalars(
                select(Complaint).where(
                    Complaint.department_id == department.id
                )
            ).all()
        )

        print(f"Authority: {authority.full_name}")
        print(f"Email: {authority.email}")
        print(f"Department: {department.name}")
        print(f"Assigned complaints: {complaint_count}")
        print("Status:", "PASS" if authority.department_id == department.id else "FAIL")
        print("-" * 45)

    print("\n========== DEPARTMENT ROUTING AUDIT ==========\n")

    for complaint in db.scalars(select(Complaint)).all():
        department = db.get(Department, complaint.department_id)

        print(
            f"Complaint #{complaint.id} | "
            f"{complaint.category} | "
            f"{department.name if department else 'UNASSIGNED'}"
        )

finally:
    db.close()

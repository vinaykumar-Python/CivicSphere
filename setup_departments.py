from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Department

DEPARTMENTS = [
    {
        "name": "Sanitation Department",
        "description": "Handles garbage collection and sanitation complaints.",
    },
    {
        "name": "Public Works Department",
        "description": "Handles damaged roads and public infrastructure.",
    },
    {
        "name": "Electrical Department",
        "description": "Handles streetlight and public electrical complaints.",
    },
    {
        "name": "Water Supply Department",
        "description": "Handles water supply problems.",
    },
    {
        "name": "Drainage Department",
        "description": "Handles drainage and sewage complaints.",
    },
    {
        "name": "Public Safety Department",
        "description": "Handles public safety concerns.",
    },
    {
        "name": "General Administration",
        "description": "Handles complaints that need general review.",
    },
]


def setup_departments():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        for item in DEPARTMENTS:
            existing = db.scalar(
                select(Department).where(
                    Department.name == item["name"]
                )
            )

            if existing is None:
                db.add(Department(**item))

        db.commit()

        departments = db.scalars(
            select(Department).order_by(Department.name)
        ).all()

        print("Departments configured successfully:")
        for department in departments:
            print(f"{department.id}: {department.name}")


if __name__ == "__main__":
    setup_departments()

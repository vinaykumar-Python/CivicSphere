from getpass import getpass

from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Department, User


def main():
    db = SessionLocal()

    try:
        print("\n=== CivicCare AI: Create Department Authority ===\n")

        full_name = input("Authority full name: ").strip()
        email = input("Authority email: ").strip().lower()
        password = getpass("Authority password (minimum 8 characters): ")

        if len(full_name) < 2:
            print("Error: Name must contain at least 2 characters.")
            return

        if "@" not in email or "." not in email.split("@")[-1]:
            print("Error: Enter a valid email address.")
            return

        if len(password) < 8:
            print("Error: Password must contain at least 8 characters.")
            return

        existing_user = db.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            print("Error: An account with this email already exists.")
            return

        departments = db.scalars(
            select(Department)
            .where(Department.is_active.is_(True))
            .order_by(Department.name)
        ).all()

        if not departments:
            print("Error: No active departments found.")
            return

        print("\nAvailable departments:")

        for department in departments:
            print(f"{department.id}: {department.name}")

        try:
            department_id = int(input("\nEnter department ID: ").strip())
        except ValueError:
            print("Error: Department ID must be a number.")
            return

        department = db.scalar(
            select(Department).where(
                Department.id == department_id,
                Department.is_active.is_(True),
            )
        )

        if department is None:
            print("Error: Invalid or inactive department ID.")
            return

        authority = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role="authority",
            is_active=True,
            department_id=department.id,
        )

        db.add(authority)
        db.commit()
        db.refresh(authority)

        print("\nAuthority created successfully!")
        print(f"User ID: {authority.id}")
        print(f"Name: {authority.full_name}")
        print(f"Email: {authority.email}")
        print(f"Department: {department.name}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
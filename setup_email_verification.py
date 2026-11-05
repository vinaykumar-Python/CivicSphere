from app import models
from app.database import Base, engine


def main():
    Base.metadata.create_all(
        bind=engine,
        tables=[models.EmailVerification.__table__],
    )
    print("Email verification table created successfully.")


if __name__ == "__main__":
    main()

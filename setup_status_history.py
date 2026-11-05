from app.database import Base, engine
from app import models


def main():
    Base.metadata.create_all(bind=engine, tables=[
        models.ComplaintStatusHistory.__table__
    ])
    print("Complaint status history table created successfully.")


if __name__ == "__main__":
    main()
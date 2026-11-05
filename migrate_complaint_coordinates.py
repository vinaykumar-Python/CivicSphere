from sqlalchemy import text

from app.database import engine


def migrate():
    statements = [
        """
        ALTER TABLE complaints
        ADD COLUMN latitude FLOAT NULL
        """,
        """
        ALTER TABLE complaints
        ADD COLUMN longitude FLOAT NULL
        """,
    ]

    with engine.begin() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
                print("Migration step completed.")
            except Exception as error:
                if "Duplicate column name" in str(error):
                    print("Column already exists; skipping.")
                else:
                    raise

    print("Complaint coordinate migration finished.")


if __name__ == "__main__":
    migrate()

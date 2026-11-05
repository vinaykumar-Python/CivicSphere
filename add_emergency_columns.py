from sqlalchemy import inspect, text

from app.database import engine


def main():
    inspector = inspect(engine)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns("complaints")
    }

    migrations = [
        (
            "emergency_review_required",
            """
            ALTER TABLE complaints
            ADD COLUMN emergency_review_required
            BOOLEAN NOT NULL DEFAULT FALSE
            """,
        ),
        (
            "priority",
            """
            ALTER TABLE complaints
            ADD COLUMN priority
            VARCHAR(30) NOT NULL DEFAULT 'normal'
            """,
        ),
        (
            "matched_indicators",
            """
            ALTER TABLE complaints
            ADD COLUMN matched_indicators
            TEXT NOT NULL
            """,
        ),
    ]

    with engine.begin() as connection:
        for column_name, sql in migrations:
            if column_name in existing_columns:
                print(f"Already exists: {column_name}")
                continue

            connection.execute(text(sql))
            print(f"Added column: {column_name}")

        connection.execute(
            text(
                """
                UPDATE complaints
                SET matched_indicators = '[]'
                WHERE matched_indicators IS NULL
                """
            )
        )

    print("\nMigration completed.")

    inspector = inspect(engine)
    columns = inspector.get_columns("complaints")

    print("\nVerified emergency columns:")
    for column in columns:
        if column["name"] in {
            "emergency_review_required",
            "priority",
            "matched_indicators",
        }:
            print(f"- {column['name']}: {column['type']}")

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM complaints")
        ).scalar_one()

    print(f"\nExisting complaint count: {count}")


if __name__ == "__main__":
    main()
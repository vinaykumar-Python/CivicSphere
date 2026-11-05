from sqlalchemy import inspect, text

from app.database import engine


def main():
    expected_columns = {
        "sla_deadline": (
            "ALTER TABLE complaints "
            "ADD COLUMN sla_deadline DATETIME NULL"
        ),
        "escalation_level": (
            "ALTER TABLE complaints "
            "ADD COLUMN escalation_level INT NOT NULL DEFAULT 0"
        ),
        "escalated_at": (
            "ALTER TABLE complaints "
            "ADD COLUMN escalated_at DATETIME NULL"
        ),
    }

    inspector = inspect(engine)

    if "complaints" not in inspector.get_table_names():
        raise RuntimeError("The complaints table was not found.")

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("complaints")
    }

    with engine.begin() as connection:
        for name, sql in expected_columns.items():
            if name in existing_columns:
                print(f"Already exists; skipping: {name}")
                continue

            connection.execute(text(sql))
            print(f"Added column: {name}")

    final_columns = {
        column["name"]
        for column in inspect(engine).get_columns("complaints")
    }

    missing = set(expected_columns) - final_columns

    if missing:
        raise RuntimeError(
            f"Migration incomplete. Missing columns: {sorted(missing)}"
        )

    print("\nSLA database migration completed successfully.")

    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM complaints")
        ).scalar_one()

    print(f"Existing complaints preserved: {count}")


if __name__ == "__main__":
    main()
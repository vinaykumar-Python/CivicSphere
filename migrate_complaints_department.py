from sqlalchemy import inspect, text

from app.database import engine


def migrate():
    inspector = inspect(engine)
    columns = {
        column["name"]
        for column in inspector.get_columns("complaints")
    }

    if "department_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE complaints "
                    "ADD COLUMN department_id INT NULL"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX ix_complaints_department_id "
                    "ON complaints (department_id)"
                )
            )
            connection.execute(
                text(
                    "ALTER TABLE complaints "
                    "ADD CONSTRAINT fk_complaints_department "
                    "FOREIGN KEY (department_id) "
                    "REFERENCES departments(id)"
                )
            )

        print("Department column and foreign key added successfully.")
    else:
        print("department_id already exists; no migration needed.")


if __name__ == "__main__":
    migrate()

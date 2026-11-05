from sqlalchemy import inspect, text

from app.database import engine


def migrate():
    inspector = inspect(engine)

    columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    if "department_id" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD COLUMN department_id INT NULL"
                )
            )

            connection.execute(
                text(
                    "CREATE INDEX ix_users_department_id "
                    "ON users (department_id)"
                )
            )

            connection.execute(
                text(
                    "ALTER TABLE users "
                    "ADD CONSTRAINT fk_users_department "
                    "FOREIGN KEY (department_id) "
                    "REFERENCES departments(id)"
                )
            )

        print("User department column added successfully.")
    else:
        print("department_id already exists; no migration needed.")


if __name__ == "__main__":
    migrate()
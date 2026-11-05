from sqlalchemy import inspect, text
from app.database import engine

columns = {
    column["name"]
    for column in inspect(engine).get_columns("users")
}

if "updated_at" in columns:
    print("users.updated_at already exists. No change needed.")
else:
    with engine.begin() as connection:
        connection.execute(text("""
            ALTER TABLE users
            ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        """))
    print("Successfully added users.updated_at.")

with engine.connect() as connection:
    result = connection.execute(text("""
        SELECT id, email, created_at, updated_at
        FROM users
        ORDER BY id
    """))
    for row in result.mappings():
        print(dict(row))

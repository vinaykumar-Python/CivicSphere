import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Add it to the project's .env file."
    )

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def check_database_connection() -> dict:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT DATABASE() AS database_name, "
                "CURRENT_USER() AS db_user"
            )
        ).mappings().one()

    return {
        "database": row["database_name"],
        "user": row["db_user"],
    }
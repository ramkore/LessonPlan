"""Database engine and session management."""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import settings

# check_same_thread is SQLite-only; Postgres doesn't need/want it
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=False,
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def run_migrations() -> None:
    """Add missing columns to existing tables."""
    insp = inspect(engine)
    if "timetableentry" not in insp.get_table_names():
        return
    columns = [col["name"] for col in insp.get_columns("timetableentry")]
    if "is_lab" not in columns:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE timetableentry ADD COLUMN is_lab BOOLEAN NOT NULL DEFAULT FALSE")
            )


def get_session() -> Session:
    return Session(engine)

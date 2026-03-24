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
    table_names = insp.get_table_names()

    # Migration: add is_lab to timetableentry
    if "timetableentry" in table_names:
        columns = [col["name"] for col in insp.get_columns("timetableentry")]
        if "is_lab" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE timetableentry ADD COLUMN is_lab BOOLEAN NOT NULL DEFAULT FALSE")
                )

    # Migration: add is_global to academiccalendarentry
    if "academiccalendarentry" in table_names:
        columns = [col["name"] for col in insp.get_columns("academiccalendarentry")]
        if "is_global" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE academiccalendarentry ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT FALSE")
                )

    # Migration: add is_global to holiday
    if "holiday" in table_names:
        columns = [col["name"] for col in insp.get_columns("holiday")]
        if "is_global" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE holiday ADD COLUMN is_global BOOLEAN NOT NULL DEFAULT FALSE")
                )

    # Migration: allow NULL user_id for admin-created global entries (PostgreSQL only)
    if not _is_sqlite and "academiccalendarentry" in table_names:
        cal_cols = {c["name"]: c for c in insp.get_columns("academiccalendarentry")}
        if "user_id" in cal_cols and not cal_cols["user_id"].get("nullable", True):
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE academiccalendarentry ALTER COLUMN user_id DROP NOT NULL"))

    if not _is_sqlite and "holiday" in table_names:
        hol_cols = {c["name"]: c for c in insp.get_columns("holiday")}
        if "user_id" in hol_cols and not hol_cols["user_id"].get("nullable", True):
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE holiday ALTER COLUMN user_id DROP NOT NULL"))


def get_session() -> Session:
    return Session(engine)

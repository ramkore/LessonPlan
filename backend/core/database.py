"""SQLite database engine and session management."""
from __future__ import annotations

import sqlite3

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
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(timetableentry)")
    columns = [row[1] for row in cursor.fetchall()]
    if "is_lab" not in columns:
        cursor.execute("ALTER TABLE timetableentry ADD COLUMN is_lab BOOLEAN NOT NULL DEFAULT 0")
        conn.commit()

    conn.close()


def get_session() -> Session:
    return Session(engine)

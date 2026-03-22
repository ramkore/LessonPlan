"""Timetable entry model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class TimetableEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    day: str
    period: str
    entry: str
    branch: str = ""
    time_slot: str = ""
    is_lab: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

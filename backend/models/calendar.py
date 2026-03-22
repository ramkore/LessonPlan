"""Academic calendar entry model."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class AcademicCalendarEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    description: str
    from_date: date
    to_date: date
    event_type: str = "teaching"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

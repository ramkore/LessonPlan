"""Holiday model."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class Holiday(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    occasion: str
    holiday_date: date
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

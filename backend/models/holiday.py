"""Holiday model."""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class Holiday(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)  # None = admin-provided global
    occasion: str
    holiday_date: date
    is_global: bool = False  # True if created by admin for all users
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

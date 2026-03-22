"""User database model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str = ""
    role: str = "faculty"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

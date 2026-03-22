"""Calendar request/response schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CalendarEntryCreate(BaseModel):
    description: str
    from_date: date
    to_date: date
    event_type: str = "teaching"


class CalendarEntryUpdate(BaseModel):
    description: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    event_type: str | None = None


class CalendarEntryRead(BaseModel):
    id: int
    description: str
    from_date: date
    to_date: date
    event_type: str

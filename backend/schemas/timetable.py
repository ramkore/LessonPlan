"""Timetable request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class TimetableEntryCreate(BaseModel):
    day: str
    period: str
    entry: str
    branch: str = ""
    time_slot: str = ""
    is_lab: bool = False


class TimetableEntryUpdate(BaseModel):
    day: str | None = None
    period: str | None = None
    entry: str | None = None
    branch: str | None = None
    time_slot: str | None = None
    is_lab: bool | None = None


class TimetableEntryRead(BaseModel):
    id: int
    day: str
    period: str
    entry: str
    branch: str
    time_slot: str
    is_lab: bool

"""Holiday request/response schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class HolidayCreate(BaseModel):
    occasion: str
    holiday_date: date


class HolidayUpdate(BaseModel):
    occasion: str | None = None
    holiday_date: date | None = None


class HolidayRead(BaseModel):
    id: int
    occasion: str
    holiday_date: date

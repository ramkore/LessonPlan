"""Academic calendar CRUD endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlmodel import Session, select

from backend.api.deps import get_current_user, get_db
from backend.models.calendar import AcademicCalendarEntry
from backend.models.user import User
from backend.schemas.calendar import CalendarEntryCreate, CalendarEntryRead, CalendarEntryUpdate

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("", response_model=list[CalendarEntryRead])
def list_entries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get both user-specific and global admin-provided calendar entries
    entries = db.exec(
        select(AcademicCalendarEntry)
        .where(
            (AcademicCalendarEntry.user_id == user.id) | (AcademicCalendarEntry.is_global == True)  # type: ignore[union-attr]
        )
        .order_by(AcademicCalendarEntry.from_date)  # type: ignore[union-attr]
    ).all()
    return entries


@router.post("", response_model=CalendarEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: CalendarEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = AcademicCalendarEntry(user_id=user.id, **body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/bulk", response_model=list[CalendarEntryRead], status_code=status.HTTP_201_CREATED)
def bulk_create(
    entries: list[CalendarEntryCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    created = []
    for body in entries:
        entry = AcademicCalendarEntry(user_id=user.id, **body.model_dump())
        db.add(entry)
        created.append(entry)
    db.commit()
    for entry in created:
        db.refresh(entry)
    return created


@router.put("/{entry_id}", response_model=CalendarEntryRead)
def update_entry(
    entry_id: int,
    body: CalendarEntryUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.get(AcademicCalendarEntry, entry_id)
    if not entry or entry.user_id != user.id or entry.is_global:
        raise HTTPException(status_code=404, detail="Entry not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.get(AcademicCalendarEntry, entry_id)
    if not entry or entry.user_id != user.id or entry.is_global:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = db.exec(
        select(AcademicCalendarEntry)
        .where((AcademicCalendarEntry.user_id == user.id) & (AcademicCalendarEntry.is_global == False))  # type: ignore[union-attr]
    ).all()
    for entry in entries:
        db.delete(entry)
    db.commit()


@router.post("/upload", response_model=list[CalendarEntryRead])
async def upload_calendar(
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    from backend.services.parser_service import _cleanup_temp, _save_upload_to_temp, parse_calendar_sync

    temp_path = await _save_upload_to_temp(file)
    try:
        records = await asyncio.to_thread(parse_calendar_sync, temp_path)
        return [
            {
                "id": 0,
                "description": r.get("description", ""),
                "from_date": r["from_date"],
                "to_date": r["to_date"],
                "event_type": "teaching",
            }
            for r in records
        ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse calendar: {exc}")
    finally:
        _cleanup_temp(temp_path)

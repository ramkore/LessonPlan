"""Timetable CRUD endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlmodel import Session, select

from backend.api.deps import get_current_user, get_db
from backend.models.timetable import TimetableEntry
from backend.models.user import User
from backend.schemas.timetable import TimetableEntryCreate, TimetableEntryRead, TimetableEntryUpdate

router = APIRouter(prefix="/api/timetable", tags=["timetable"])


@router.get("", response_model=list[TimetableEntryRead])
def list_entries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.exec(
        select(TimetableEntry).where(TimetableEntry.user_id == user.id)
    ).all()


@router.post("", response_model=TimetableEntryRead, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: TimetableEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = TimetableEntry(user_id=user.id, **body.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/bulk", response_model=list[TimetableEntryRead], status_code=status.HTTP_201_CREATED)
def bulk_create(
    items: list[TimetableEntryCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    created = []
    for body in items:
        entry = TimetableEntry(user_id=user.id, **body.model_dump())
        db.add(entry)
        created.append(entry)
    db.commit()
    for entry in created:
        db.refresh(entry)
    return created


@router.put("/{entry_id}", response_model=TimetableEntryRead)
def update_entry(
    entry_id: int,
    body: TimetableEntryUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entry = db.get(TimetableEntry, entry_id)
    if not entry or entry.user_id != user.id:
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
    entry = db.get(TimetableEntry, entry_id)
    if not entry or entry.user_id != user.id:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entries = db.exec(select(TimetableEntry).where(TimetableEntry.user_id == user.id)).all()
    for entry in entries:
        db.delete(entry)
    db.commit()


@router.post("/upload", response_model=list[TimetableEntryRead])
async def upload_timetable(
    file: UploadFile,
    subject_name: str = Query(..., description="Subject name to match in timetable"),
    faculty_name: str = Query("", description="Faculty name (optional)"),
    branch: str = Query("", description="Branch name (optional)"),
    user: User = Depends(get_current_user),
):
    from backend.services.parser_service import _cleanup_temp, _save_upload_to_temp, parse_timetable_sync

    temp_path = await _save_upload_to_temp(file)
    try:
        records = await asyncio.to_thread(parse_timetable_sync, temp_path, subject_name, faculty_name, branch)
        return [
            {
                "id": 0,
                "day": r.get("day", ""),
                "period": r.get("period", ""),
                "entry": r.get("entry", ""),
                "branch": r.get("branch", ""),
                "time_slot": r.get("time_slot", ""),
                "is_lab": r.get("is_lab", False),
            }
            for r in records
        ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse timetable: {exc}")
    finally:
        _cleanup_temp(temp_path)

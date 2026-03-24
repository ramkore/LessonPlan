"""Holiday CRUD endpoints."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlmodel import Session, select

from backend.api.deps import get_current_user, get_db
from backend.models.holiday import Holiday
from backend.models.user import User
from backend.schemas.holiday import HolidayCreate, HolidayRead, HolidayUpdate

router = APIRouter(prefix="/api/holidays", tags=["holidays"])


@router.get("", response_model=list[HolidayRead])
def list_holidays(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get both user-specific and global admin-provided holidays
    return db.exec(
        select(Holiday)
        .where(
            (Holiday.user_id == user.id) | (Holiday.is_global == True)  # type: ignore[union-attr]
        )
        .order_by(Holiday.holiday_date)  # type: ignore[union-attr]
    ).all()


@router.post("", response_model=HolidayRead, status_code=status.HTTP_201_CREATED)
def create_holiday(
    body: HolidayCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    holiday = Holiday(user_id=user.id, **body.model_dump())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.post("/bulk", response_model=list[HolidayRead], status_code=status.HTTP_201_CREATED)
def bulk_create(
    items: list[HolidayCreate],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    created = []
    for body in items:
        holiday = Holiday(user_id=user.id, **body.model_dump())
        db.add(holiday)
        created.append(holiday)
    db.commit()
    for holiday in created:
        db.refresh(holiday)
    return created


@router.put("/{holiday_id}", response_model=HolidayRead)
def update_holiday(
    holiday_id: int,
    body: HolidayUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    holiday = db.get(Holiday, holiday_id)
    if not holiday or holiday.user_id != user.id or holiday.is_global:
        raise HTTPException(status_code=404, detail="Holiday not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(holiday, key, value)
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(
    holiday_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    holiday = db.get(Holiday, holiday_id)
    if not holiday or holiday.user_id != user.id or holiday.is_global:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    holidays = db.exec(
        select(Holiday)
        .where((Holiday.user_id == user.id) & (Holiday.is_global == False))  # type: ignore[union-attr]
    ).all()
    for holiday in holidays:
        db.delete(holiday)
    db.commit()


@router.post("/upload", response_model=list[HolidayRead])
async def upload_holidays(
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    from backend.services.parser_service import _cleanup_temp, _save_upload_to_temp, parse_holidays_sync

    temp_path = await _save_upload_to_temp(file)
    try:
        records = await asyncio.to_thread(parse_holidays_sync, temp_path)
        return [
            {"id": 0, "occasion": r.get("occasion", "Holiday"), "holiday_date": r["holiday_date"]}
            for r in records
        ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse holidays: {exc}")
    finally:
        _cleanup_temp(temp_path)

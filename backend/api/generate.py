"""Generation and export endpoints."""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from backend.api.deps import get_current_user, get_db
from backend.models.calendar import AcademicCalendarEntry
from backend.models.holiday import Holiday
from backend.models.lesson_plan import LessonPlanRecord
from backend.models.subject import Subject
from backend.models.timetable import TimetableEntry
from backend.models.user import User
from backend.schemas.lesson_plan import (
    GenerateRequest,
    LessonPlanHistoryItem,
    LessonPlanPreview,
)
from backend.services.generator_service import (
    bundle_to_preview,
    export_bundle,
    generate_lesson_plan,
    reconstruct_syllabus_from_subject,
)

router = APIRouter(prefix="/api/generate", tags=["generate"])


@router.post("", response_model=LessonPlanPreview)
async def generate(
    body: GenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Load user's data from DB (include global admin-provided entries)
    calendar_entries = db.exec(
        select(AcademicCalendarEntry).where(
            (AcademicCalendarEntry.user_id == user.id) | (AcademicCalendarEntry.is_global == True)  # type: ignore[union-attr]
        )
    ).all()
    if not calendar_entries:
        raise HTTPException(status_code=400, detail="No academic calendar entries found. Please add calendar data first.")

    holidays = db.exec(
        select(Holiday).where(
            (Holiday.user_id == user.id) | (Holiday.is_global == True)  # type: ignore[union-attr]
        )
    ).all()

    timetable_entries = db.exec(
        select(TimetableEntry).where(TimetableEntry.user_id == user.id)
    ).all()
    if not timetable_entries:
        raise HTTPException(status_code=400, detail="No timetable entries found. Please add timetable data first.")

    # Load syllabus
    if body.syllabus_id:
        subject = db.get(Subject, body.syllabus_id)
        if not subject or subject.user_id != user.id:
            raise HTTPException(status_code=404, detail="Subject not found")
        syllabus = reconstruct_syllabus_from_subject({
            "course_title": subject.course_title,
            "course_code": subject.course_code,
            "regulation": subject.regulation,
            "units": json.loads(subject.units_json),
            "flat_topics": json.loads(subject.flat_topics_json),
            "experiments": json.loads(subject.experiments_json),
            "course_objectives": json.loads(subject.course_objectives_json),
            "course_outcomes": json.loads(subject.course_outcomes_json),
            "text_books": json.loads(subject.text_books_json),
            "reference_books": json.loads(subject.reference_books_json),
        })
    else:
        raise HTTPException(status_code=400, detail="Please select a syllabus/subject")

    faculty_info = body.faculty_info.model_dump()

    cal_dicts = [
        {"description": e.description, "from_date": e.from_date, "to_date": e.to_date}
        for e in calendar_entries
    ]
    hol_dicts = [
        {"occasion": h.occasion, "holiday_date": h.holiday_date}
        for h in holidays
    ]
    tt_dicts = [
        {"day": e.day, "period": e.period, "entry": e.entry, "branch": e.branch, "time_slot": e.time_slot, "is_lab": e.is_lab}
        for e in timetable_entries
    ]

    try:
        bundle = await asyncio.to_thread(
            generate_lesson_plan, cal_dicts, hol_dicts, tt_dicts, syllabus, faculty_info
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Save generation record
    preview = bundle_to_preview(bundle)
    record = LessonPlanRecord(
        user_id=user.id,
        faculty_name=faculty_info.get("faculty_name", ""),
        designation=faculty_info.get("designation", ""),
        subject_name=faculty_info.get("subject_name", ""),
        course_code=faculty_info.get("course_code", ""),
        branch=faculty_info.get("branch", ""),
        semester=faculty_info.get("semester", ""),
        section=faculty_info.get("section", ""),
        student_count=faculty_info.get("student_count", ""),
        is_lab=bundle.metadata.get("is_lab", False),
        planned_classes=bundle.metadata.get("planned_classes", 0),
        planned_lectures=bundle.metadata.get("planned_lectures", 0),
        lesson_plan_json=json.dumps(preview["lesson_plan"]),
        monthly_plan_json=json.dumps(preview["monthly_plan"]),
        coverage_report_json=json.dumps(preview["coverage_report"]),
    )
    db.add(record)
    db.commit()

    return preview


@router.post("/export/{fmt}")
async def generate_and_export(
    fmt: str,
    body: GenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if fmt not in ("pdf", "excel", "word"):
        raise HTTPException(status_code=400, detail="Format must be pdf, excel, or word")

    # Load data (same as generate, include global admin-provided entries)
    calendar_entries = db.exec(
        select(AcademicCalendarEntry).where(
            (AcademicCalendarEntry.user_id == user.id) | (AcademicCalendarEntry.is_global == True)  # type: ignore[union-attr]
        )
    ).all()
    if not calendar_entries:
        raise HTTPException(status_code=400, detail="No academic calendar entries found")

    holidays = db.exec(
        select(Holiday).where(
            (Holiday.user_id == user.id) | (Holiday.is_global == True)  # type: ignore[union-attr]
        )
    ).all()
    timetable_entries = db.exec(
        select(TimetableEntry).where(TimetableEntry.user_id == user.id)
    ).all()
    if not timetable_entries:
        raise HTTPException(status_code=400, detail="No timetable entries found")

    if body.syllabus_id:
        subject = db.get(Subject, body.syllabus_id)
        if not subject or subject.user_id != user.id:
            raise HTTPException(status_code=404, detail="Subject not found")
        syllabus = reconstruct_syllabus_from_subject({
            "course_title": subject.course_title,
            "course_code": subject.course_code,
            "regulation": subject.regulation,
            "units": json.loads(subject.units_json),
            "flat_topics": json.loads(subject.flat_topics_json),
            "experiments": json.loads(subject.experiments_json),
            "course_objectives": json.loads(subject.course_objectives_json),
            "course_outcomes": json.loads(subject.course_outcomes_json),
            "text_books": json.loads(subject.text_books_json),
            "reference_books": json.loads(subject.reference_books_json),
        })
    else:
        raise HTTPException(status_code=400, detail="Please select a syllabus/subject")

    faculty_info = body.faculty_info.model_dump()
    cal_dicts = [{"description": e.description, "from_date": e.from_date, "to_date": e.to_date} for e in calendar_entries]
    hol_dicts = [{"occasion": h.occasion, "holiday_date": h.holiday_date} for h in holidays]
    tt_dicts = [{"day": e.day, "period": e.period, "entry": e.entry, "branch": e.branch, "time_slot": e.time_slot, "is_lab": e.is_lab} for e in timetable_entries]

    try:
        bundle = await asyncio.to_thread(
            generate_lesson_plan, cal_dicts, hol_dicts, tt_dicts, syllabus, faculty_info
        )
        file_path = await asyncio.to_thread(export_bundle, bundle, fmt)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    media_types = {
        "pdf": "application/pdf",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    extensions = {"pdf": ".pdf", "excel": ".xlsx", "word": ".docx"}

    return FileResponse(
        path=str(file_path),
        media_type=media_types[fmt],
        filename=f"lesson_plan{extensions[fmt]}",
    )


@router.get("/history", response_model=list[LessonPlanHistoryItem])
def generation_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = db.exec(
        select(LessonPlanRecord)
        .where(LessonPlanRecord.user_id == user.id)
        .order_by(LessonPlanRecord.generated_at.desc())  # type: ignore[union-attr]
        .limit(20)
    ).all()
    return [
        LessonPlanHistoryItem(
            id=r.id,
            faculty_name=r.faculty_name,
            subject_name=r.subject_name,
            branch=r.branch,
            semester=r.semester,
            is_lab=r.is_lab,
            planned_lectures=r.planned_lectures,
            generated_at=r.generated_at.isoformat(),
        )
        for r in records
    ]

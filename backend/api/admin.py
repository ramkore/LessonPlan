"""Admin panel endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from backend.api.deps import get_current_admin, get_db
from backend.models.calendar import AcademicCalendarEntry
from backend.models.holiday import Holiday
from backend.models.lesson_plan import LessonPlanRecord
from backend.models.subject import Subject
from backend.models.timetable import TimetableEntry
from backend.models.user import User
from backend.schemas.admin import AdminPlanRead, AdminStats, AdminUserRead, AdminUserDetail, RoleUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStats)
def admin_stats(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total_users = db.exec(select(func.count(User.id))).one()
    total_admins = db.exec(select(func.count(User.id)).where(User.role == "admin")).one()
    total_faculty = total_users - total_admins
    total_plans = db.exec(select(func.count(LessonPlanRecord.id))).one()

    now = datetime.now(timezone.utc)
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    plans_this_month = db.exec(
        select(func.count(LessonPlanRecord.id)).where(
            LessonPlanRecord.generated_at >= first_of_month
        )
    ).one()

    return AdminStats(
        total_users=total_users,
        total_admins=total_admins,
        total_faculty=total_faculty,
        total_plans=total_plans,
        plans_this_month=plans_this_month,
    )


@router.get("/users", response_model=list[AdminUserRead])
def admin_list_users(
    search: str = "",
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(User)
    if search:
        stmt = stmt.where(
            User.email.contains(search) | User.full_name.contains(search)  # type: ignore[union-attr]
        )
    stmt = stmt.order_by(User.created_at.desc())  # type: ignore[union-attr]
    users = db.exec(stmt).all()

    result = []
    for u in users:
        plan_count = db.exec(
            select(func.count(LessonPlanRecord.id)).where(LessonPlanRecord.user_id == u.id)
        ).one()
        result.append(
            AdminUserRead(
                id=u.id,  # type: ignore[arg-type]
                email=u.email,
                full_name=u.full_name,
                role=u.role,
                created_at=u.created_at.isoformat(),
                plan_count=plan_count,
            )
        )
    return result


@router.put("/users/{user_id}/role", response_model=AdminUserRead)
def admin_update_role(
    user_id: int,
    body: RoleUpdate,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if body.role not in ("admin", "faculty"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'faculty'")
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = body.role
    db.add(user)
    db.commit()
    db.refresh(user)

    plan_count = db.exec(
        select(func.count(LessonPlanRecord.id)).where(LessonPlanRecord.user_id == user.id)
    ).one()

    return AdminUserRead(
        id=user.id,  # type: ignore[arg-type]
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at.isoformat(),
        plan_count=plan_count,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete user's lesson plans first
    plans = db.exec(select(LessonPlanRecord).where(LessonPlanRecord.user_id == user_id)).all()
    for plan in plans:
        db.delete(plan)

    db.delete(user)
    db.commit()


@router.get("/plans", response_model=list[AdminPlanRead])
def admin_list_plans(
    search: str = "",
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    stmt = select(LessonPlanRecord).order_by(LessonPlanRecord.generated_at.desc())  # type: ignore[union-attr]
    if search:
        stmt = stmt.where(
            LessonPlanRecord.subject_name.contains(search)  # type: ignore[union-attr]
            | LessonPlanRecord.faculty_name.contains(search)  # type: ignore[union-attr]
        )

    plans = db.exec(stmt).all()
    result = []
    for p in plans:
        user = db.get(User, p.user_id)
        result.append(
            AdminPlanRead(
                id=p.id,  # type: ignore[arg-type]
                user_id=p.user_id,
                user_email=user.email if user else "deleted",
                faculty_name=p.faculty_name,
                subject_name=p.subject_name,
                course_code=p.course_code,
                branch=p.branch,
                semester=p.semester,
                is_lab=p.is_lab,
                planned_lectures=p.planned_lectures,
                generated_at=p.generated_at.isoformat(),
            )
        )
    return result


# ── Admin: View any user's full data ──────────────────────────────────────


@router.get("/users/{user_id}/detail", response_model=AdminUserDetail)
def admin_user_detail(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    calendars = db.exec(
        select(AcademicCalendarEntry).where(AcademicCalendarEntry.user_id == user_id)
    ).all()
    holidays = db.exec(select(Holiday).where(Holiday.user_id == user_id)).all()
    timetables = db.exec(
        select(TimetableEntry).where(TimetableEntry.user_id == user_id)
    ).all()
    subjects = db.exec(select(Subject).where(Subject.user_id == user_id)).all()
    plans = db.exec(
        select(LessonPlanRecord)
        .where(LessonPlanRecord.user_id == user_id)
        .order_by(LessonPlanRecord.generated_at.desc())  # type: ignore[union-attr]
    ).all()

    return AdminUserDetail(
        id=user.id,  # type: ignore[arg-type]
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        created_at=user.created_at.isoformat(),
        calendar_count=len(calendars),
        holiday_count=len(holidays),
        timetable_count=len(timetables),
        subject_count=len(subjects),
        plan_count=len(plans),
        calendars=[
            {"id": c.id, "description": c.description, "from_date": str(c.from_date), "to_date": str(c.to_date), "event_type": c.event_type}
            for c in calendars
        ],
        holidays=[
            {"id": h.id, "occasion": h.occasion, "holiday_date": str(h.holiday_date)}
            for h in holidays
        ],
        timetables=[
            {"id": t.id, "day": t.day, "period": t.period, "entry": t.entry, "branch": t.branch, "is_lab": t.is_lab}
            for t in timetables
        ],
        subjects=[
            {"id": s.id, "course_code": s.course_code, "course_title": s.course_title}
            for s in subjects
        ],
        plans=[
            {
                "id": p.id, "faculty_name": p.faculty_name, "subject_name": p.subject_name,
                "branch": p.branch, "semester": p.semester, "is_lab": p.is_lab,
                "planned_lectures": p.planned_lectures, "generated_at": p.generated_at.isoformat(),
            }
            for p in plans
        ],
    )


@router.delete("/users/{user_id}/data", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user_data(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete ALL data for a user (calendar, holidays, timetable, subjects, plans) but keep the account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for model in [AcademicCalendarEntry, Holiday, TimetableEntry, Subject, LessonPlanRecord]:
        rows = db.exec(select(model).where(model.user_id == user_id)).all()  # type: ignore[attr-defined]
        for row in rows:
            db.delete(row)
    db.commit()


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_plan(
    plan_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    plan = db.get(LessonPlanRecord, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    db.commit()


# ── Admin: Global Calendar Management ────────────────────────────────────────


@router.get("/calendar", response_model=list[dict])
def admin_list_calendar(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entries = db.exec(
        select(AcademicCalendarEntry)
        .where(AcademicCalendarEntry.is_global == True)  # type: ignore[union-attr]
        .order_by(AcademicCalendarEntry.from_date)  # type: ignore[union-attr]
    ).all()
    return [
        {
            "id": e.id,
            "description": e.description,
            "from_date": str(e.from_date),
            "to_date": str(e.to_date),
            "event_type": e.event_type,
        }
        for e in entries
    ]


@router.post("/calendar", response_model=dict, status_code=status.HTTP_201_CREATED)
def admin_create_calendar(
    body: dict,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entry = AcademicCalendarEntry(
        description=body["description"],
        from_date=body["from_date"],
        to_date=body["to_date"],
        event_type=body.get("event_type", "teaching"),
        is_global=True,
        user_id=None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "description": entry.description,
        "from_date": str(entry.from_date),
        "to_date": str(entry.to_date),
        "event_type": entry.event_type,
    }


@router.put("/calendar/{entry_id}", response_model=dict)
def admin_update_calendar(
    entry_id: int,
    body: dict,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entry = db.get(AcademicCalendarEntry, entry_id)
    if not entry or not entry.is_global:
        raise HTTPException(status_code=404, detail="Calendar entry not found")

    if "description" in body:
        entry.description = body["description"]
    if "from_date" in body:
        entry.from_date = body["from_date"]
    if "to_date" in body:
        entry.to_date = body["to_date"]
    if "event_type" in body:
        entry.event_type = body["event_type"]

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "description": entry.description,
        "from_date": str(entry.from_date),
        "to_date": str(entry.to_date),
        "event_type": entry.event_type,
    }


@router.delete("/calendar/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_calendar(
    entry_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    entry = db.get(AcademicCalendarEntry, entry_id)
    if not entry or not entry.is_global:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    db.delete(entry)
    db.commit()


# ── Admin: Global Holiday Management ─────────────────────────────────────────


@router.get("/holidays", response_model=list[dict])
def admin_list_holidays(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    holidays = db.exec(
        select(Holiday)
        .where(Holiday.is_global == True)  # type: ignore[union-attr]
        .order_by(Holiday.holiday_date)  # type: ignore[union-attr]
    ).all()
    return [
        {
            "id": h.id,
            "occasion": h.occasion,
            "holiday_date": str(h.holiday_date),
        }
        for h in holidays
    ]


@router.post("/holidays", response_model=dict, status_code=status.HTTP_201_CREATED)
def admin_create_holiday(
    body: dict,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    holiday = Holiday(
        occasion=body["occasion"],
        holiday_date=body["holiday_date"],
        is_global=True,
        user_id=None,
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return {
        "id": holiday.id,
        "occasion": holiday.occasion,
        "holiday_date": str(holiday.holiday_date),
    }


@router.put("/holidays/{holiday_id}", response_model=dict)
def admin_update_holiday(
    holiday_id: int,
    body: dict,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    holiday = db.get(Holiday, holiday_id)
    if not holiday or not holiday.is_global:
        raise HTTPException(status_code=404, detail="Holiday not found")

    if "occasion" in body:
        holiday.occasion = body["occasion"]
    if "holiday_date" in body:
        holiday.holiday_date = body["holiday_date"]

    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return {
        "id": holiday.id,
        "occasion": holiday.occasion,
        "holiday_date": str(holiday.holiday_date),
    }


@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_holiday(
    holiday_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    holiday = db.get(Holiday, holiday_id)
    if not holiday or not holiday.is_global:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    db.commit()

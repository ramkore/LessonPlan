"""Admin panel endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from backend.api.deps import get_current_admin, get_db
from backend.models.lesson_plan import LessonPlanRecord
from backend.models.user import User
from backend.schemas.admin import AdminPlanRead, AdminStats, AdminUserRead, RoleUpdate

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

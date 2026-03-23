"""Admin panel request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class AdminStats(BaseModel):
    total_users: int
    total_admins: int
    total_faculty: int
    total_plans: int
    plans_this_month: int


class AdminUserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    created_at: str
    plan_count: int


class AdminPlanRead(BaseModel):
    id: int
    user_id: int
    user_email: str
    faculty_name: str
    subject_name: str
    course_code: str
    branch: str
    semester: str
    is_lab: bool
    planned_lectures: int
    generated_at: str


class RoleUpdate(BaseModel):
    role: str

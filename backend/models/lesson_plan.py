"""Lesson plan generation record model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class LessonPlanRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    faculty_name: str = ""
    designation: str = ""
    subject_name: str = ""
    course_code: str = ""
    branch: str = ""
    semester: str = ""
    section: str = ""
    student_count: str = ""
    is_lab: bool = False
    planned_classes: int = 0
    planned_lectures: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lesson_plan_json: str = ""
    monthly_plan_json: str = ""
    coverage_report_json: str = ""

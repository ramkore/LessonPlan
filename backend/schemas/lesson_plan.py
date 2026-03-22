"""Lesson plan / generation request/response schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FacultyInfo(BaseModel):
    faculty_name: str
    designation: str = ""
    subject_name: str
    course_code: str = ""
    branch: str = ""
    semester: str = ""
    section: str = ""
    student_count: str = ""
    selected_entry: str = ""


class GenerateRequest(BaseModel):
    faculty_info: FacultyInfo
    syllabus_id: int | None = None


class LessonPlanPreview(BaseModel):
    lesson_plan: list[dict[str, Any]]
    monthly_plan: list[dict[str, Any]]
    coverage_report: list[dict[str, Any]]
    metadata: dict[str, Any]


class LessonPlanHistoryItem(BaseModel):
    id: int
    faculty_name: str
    subject_name: str
    branch: str
    semester: str
    is_lab: bool
    planned_lectures: int
    generated_at: str


class SubjectCreate(BaseModel):
    course_code: str = ""
    course_title: str
    regulation: str = ""
    units: list[dict[str, Any]] = []
    flat_topics: list[dict[str, Any]] = []
    experiments: list[dict[str, Any]] = []
    course_objectives: list[str] = []
    course_outcomes: list[str] = []
    text_books: list[str] = []
    reference_books: list[str] = []


class SubjectRead(BaseModel):
    id: int
    course_code: str
    course_title: str
    regulation: str
    units: list[dict[str, Any]]
    flat_topics: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
    course_objectives: list[str]
    course_outcomes: list[str]
    text_books: list[str]
    reference_books: list[str]

"""Subject (syllabus) model."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Subject(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    course_code: str = ""
    course_title: str
    regulation: str = ""
    units_json: str = "[]"
    flat_topics_json: str = "[]"
    experiments_json: str = "[]"
    course_objectives_json: str = "[]"
    course_outcomes_json: str = "[]"
    text_books_json: str = "[]"
    reference_books_json: str = "[]"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

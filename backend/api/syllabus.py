"""Syllabus CRUD endpoints."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlmodel import Session, select

from backend.api.deps import get_current_user, get_db
from backend.models.subject import Subject
from backend.models.user import User
from backend.schemas.lesson_plan import SubjectCreate, SubjectRead

router = APIRouter(prefix="/api/syllabus", tags=["syllabus"])


def _subject_to_read(subject: Subject) -> SubjectRead:
    return SubjectRead(
        id=subject.id,
        course_code=subject.course_code,
        course_title=subject.course_title,
        regulation=subject.regulation,
        units=json.loads(subject.units_json),
        flat_topics=json.loads(subject.flat_topics_json),
        experiments=json.loads(subject.experiments_json),
        course_objectives=json.loads(subject.course_objectives_json),
        course_outcomes=json.loads(subject.course_outcomes_json),
        text_books=json.loads(subject.text_books_json),
        reference_books=json.loads(subject.reference_books_json),
    )


@router.get("", response_model=list[SubjectRead])
def list_subjects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subjects = db.exec(select(Subject).where(Subject.user_id == user.id)).all()
    return [_subject_to_read(s) for s in subjects]


@router.get("/{subject_id}", response_model=SubjectRead)
def get_subject(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = db.get(Subject, subject_id)
    if not subject or subject.user_id != user.id:
        raise HTTPException(status_code=404, detail="Subject not found")
    return _subject_to_read(subject)


@router.post("", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(
    body: SubjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = Subject(
        user_id=user.id,
        course_code=body.course_code,
        course_title=body.course_title,
        regulation=body.regulation,
        units_json=json.dumps(body.units, default=str),
        flat_topics_json=json.dumps(body.flat_topics, default=str),
        experiments_json=json.dumps(body.experiments, default=str),
        course_objectives_json=json.dumps(body.course_objectives),
        course_outcomes_json=json.dumps(body.course_outcomes),
        text_books_json=json.dumps(body.text_books),
        reference_books_json=json.dumps(body.reference_books),
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _subject_to_read(subject)


@router.put("/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: int,
    body: SubjectCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = db.get(Subject, subject_id)
    if not subject or subject.user_id != user.id:
        raise HTTPException(status_code=404, detail="Subject not found")
    subject.course_code = body.course_code
    subject.course_title = body.course_title
    subject.regulation = body.regulation
    subject.units_json = json.dumps(body.units, default=str)
    subject.flat_topics_json = json.dumps(body.flat_topics, default=str)
    subject.experiments_json = json.dumps(body.experiments, default=str)
    subject.course_objectives_json = json.dumps(body.course_objectives)
    subject.course_outcomes_json = json.dumps(body.course_outcomes)
    subject.text_books_json = json.dumps(body.text_books)
    subject.reference_books_json = json.dumps(body.reference_books)
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return _subject_to_read(subject)


@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subject = db.get(Subject, subject_id)
    if not subject or subject.user_id != user.id:
        raise HTTPException(status_code=404, detail="Subject not found")
    db.delete(subject)
    db.commit()


@router.post("/upload", response_model=SubjectCreate)
async def upload_syllabus(
    file: UploadFile,
    user: User = Depends(get_current_user),
):
    from backend.services.parser_service import _cleanup_temp, _save_upload_to_temp, parse_syllabus_sync

    temp_path = await _save_upload_to_temp(file)
    try:
        result = await asyncio.to_thread(parse_syllabus_sync, temp_path)
        return SubjectCreate(
            course_code=result.get("course_code", ""),
            course_title=result.get("course_title", ""),
            regulation=result.get("regulation", ""),
            units=result.get("units", []),
            flat_topics=result.get("flat_topics", []),
            experiments=result.get("experiments", []),
            course_objectives=result.get("course_objectives", []),
            course_outcomes=result.get("course_outcomes", []),
            text_books=result.get("text_books", []),
            reference_books=result.get("reference_books", []),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse syllabus: {exc}")
    finally:
        _cleanup_temp(temp_path)

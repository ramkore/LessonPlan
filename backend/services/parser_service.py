"""Service layer wrapping existing src/ parsers for web API use."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import UploadFile

from src.calendar_processor import CalendarProcessor
from src.syllabus_parser import SyllabusParser
from src.timetable_parser import TimeTableParser
from src.utils import load_parsed_document


async def _save_upload_to_temp(file: UploadFile) -> Path:
    """Save an uploaded file to a temporary directory and return the path."""
    suffix = Path(file.filename or "upload").suffix
    temp_dir = Path(tempfile.mkdtemp(prefix="lp_upload_"))
    safe_name = Path(file.filename or "upload").name
    temp_path = temp_dir / safe_name
    with temp_path.open("wb") as f:
        content = await file.read()
        f.write(content)
    return temp_path


def _cleanup_temp(temp_path: Path) -> None:
    """Remove the temporary directory containing the uploaded file."""
    try:
        shutil.rmtree(temp_path.parent, ignore_errors=True)
    except Exception:
        pass


def parse_calendar_sync(temp_path: Path) -> list[dict]:
    """Parse an academic calendar file and return structured entries."""
    doc = load_parsed_document(temp_path)
    processor = CalendarProcessor()
    events = processor.extract_calendar_events(doc)
    return events.to_dict("records")


def parse_holidays_sync(temp_path: Path) -> list[dict]:
    """Parse a holiday list file and return structured entries."""
    doc = load_parsed_document(temp_path)
    processor = CalendarProcessor()
    holidays = processor.extract_holidays(doc)
    result = []
    for _, row in holidays.iterrows():
        result.append({
            "occasion": row.get("occasion", "Holiday"),
            "holiday_date": row["date"].date() if hasattr(row["date"], "date") else row["date"],
        })
    return result


def parse_timetable_sync(
    temp_path: Path,
    subject_name: str,
    faculty_name: str = "",
    branch: str = "",
) -> list[dict]:
    """Parse a timetable file and return subject period entries."""
    doc = load_parsed_document(temp_path)
    parser = TimeTableParser()
    periods = parser.extract_subject_periods(doc, subject_name, faculty_name, branch)
    records = periods.to_dict("records")

    # Auto-detect lab entries based on entry text only (per-entry, not per-subject).
    # The is_lab flag must reflect whether the timetable slot itself is a lab slot,
    # not whether the subject being searched for is a lab subject.
    for r in records:
        entry_text = str(r.get("entry", "")).lower()
        r["is_lab"] = "lab" in entry_text or "laboratory" in entry_text

    return records


def parse_syllabus_sync(temp_path: Path) -> dict:
    """Parse a syllabus file and return structured syllabus data."""
    doc = load_parsed_document(temp_path)
    parser = SyllabusParser()
    return parser.parse(doc)

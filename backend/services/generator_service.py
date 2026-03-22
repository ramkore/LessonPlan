"""Service layer wrapping the lesson plan generator for web API use."""
from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.calendar_processor import CalendarProcessor
from src.export_excel import export_bundle_to_excel
from src.export_pdf import export_bundle_to_pdf
from src.export_word import export_bundle_to_word
from src.lesson_generator import LessonPlanGenerator
from src.utils import LessonPlanBundle


def generate_lesson_plan(
    calendar_entries: list[dict],
    holidays: list[dict],
    timetable_entries: list[dict],
    syllabus: dict[str, Any],
    faculty_info: dict[str, str],
) -> LessonPlanBundle:
    """Generate a lesson plan bundle from structured data."""
    # Build teaching days from calendar entries and holidays
    calendar_events_df = pd.DataFrame([
        {
            "description": e["description"],
            "from_date": _to_date(e["from_date"]),
            "to_date": _to_date(e["to_date"]),
        }
        for e in calendar_entries
    ])
    holidays_df = pd.DataFrame([
        {
            "occasion": h.get("occasion", "Holiday"),
            "date": pd.Timestamp(_to_date(h["holiday_date"])),
        }
        for h in holidays
    ]) if holidays else pd.DataFrame(columns=["occasion", "date"])

    if not holidays_df.empty:
        holidays_df["date"] = pd.to_datetime(holidays_df["date"])

    processor = CalendarProcessor()
    teaching_days = processor.build_teaching_days_from_frames(calendar_events_df, holidays_df)

    # Filter timetable entries by the user's selected entry so that only
    # the exact matching entries are included.  This separates both
    # theory/lab (e.g. "ECE" vs "ECE LAB") and different branches
    # (e.g. "ECE LAB" vs "CE/EEE LAB") at the source.
    selected_entry = faculty_info.get("selected_entry", "").strip()
    selected_branch = faculty_info.get("branch", "").strip().upper()

    if selected_entry:
        filtered = [
            e for e in timetable_entries
            if e.get("entry", "").strip().upper() == selected_entry.upper()
        ]
        if filtered:
            timetable_entries = filtered
    elif selected_branch:
        # Backward compatibility: fall back to branch-based filtering
        filtered = [
            e for e in timetable_entries
            if (
                not e.get("branch", "").strip()
                or e.get("branch", "").strip().upper() == selected_branch
            )
        ]
        if filtered:
            timetable_entries = filtered

    # Build subject periods from timetable entries
    subject_periods = pd.DataFrame([
        {
            "day": e["day"],
            "period": e["period"],
            "entry": e["entry"],
            "branch": e.get("branch", ""),
            "time_slot": e.get("time_slot", ""),
            "is_lab": e.get("is_lab", False),
        }
        for e in timetable_entries
    ])

    # For lab subjects, keep only lab-flagged entries so that theory periods
    # (e.g. single-period "ECE" on Saturday) don't pollute the lab schedule.
    # This mirrors the filtering in timetable_parser.extract_subject_periods().
    course_title = str(syllabus.get("course_title", faculty_info.get("subject_name", ""))).strip()
    _title_lower = course_title.lower()
    is_lab_subject = (
        bool(syllabus.get("experiments"))
        or any(tok in _title_lower for tok in (" lab", "laboratory", "practical"))
        or _title_lower.endswith("lab")
    )
    if is_lab_subject and not subject_periods.empty:
        lab_mask = subject_periods["is_lab"].astype(bool)
        if "entry" in subject_periods.columns:
            lab_mask = lab_mask | subject_periods["entry"].str.lower().str.contains("lab", na=False)
        lab_only = subject_periods[lab_mask]
        if not lab_only.empty:
            subject_periods = lab_only.reset_index(drop=True)

    # Update faculty_info with syllabus metadata
    course_title = str(syllabus.get("course_title", faculty_info.get("subject_name", ""))).strip()
    course_code = str(syllabus.get("course_code", "")).strip()
    faculty_info = dict(faculty_info)
    faculty_info["subject_name"] = course_title or faculty_info.get("subject_name", "")
    if course_code:
        faculty_info["course_code"] = course_code

    # Generate
    generator = LessonPlanGenerator()
    return generator.generate(teaching_days, subject_periods, syllabus, faculty_info)


def bundle_to_preview(bundle: LessonPlanBundle) -> dict[str, Any]:
    """Convert a LessonPlanBundle to JSON-serializable preview data."""
    metadata = dict(bundle.metadata)
    # Clean non-serializable items
    for key in list(metadata.keys()):
        if isinstance(metadata[key], pd.DataFrame):
            metadata[key] = metadata[key].to_dict("records")

    return {
        "lesson_plan": _df_to_records(bundle.lesson_plan),
        "monthly_plan": _df_to_records(bundle.monthly_plan),
        "coverage_report": _df_to_records(bundle.coverage_report),
        "metadata": metadata,
    }


def export_bundle(bundle: LessonPlanBundle, fmt: str) -> Path:
    """Export a bundle to a file and return the file path."""
    output_dir = Path(tempfile.mkdtemp(prefix="lp_export_"))

    if fmt == "pdf":
        return export_bundle_to_pdf(bundle, output_dir)
    elif fmt == "excel":
        paths = export_bundle_to_excel(bundle, output_dir)
        return paths["lesson_plan"]
    elif fmt == "word":
        return export_bundle_to_word(bundle, output_dir)
    else:
        raise ValueError(f"Unsupported export format: {fmt}")


def reconstruct_syllabus_from_subject(subject_data: dict) -> dict[str, Any]:
    """Reconstruct the syllabus dict from a Subject model's data."""
    return {
        "course_title": subject_data.get("course_title", ""),
        "course_code": subject_data.get("course_code", ""),
        "regulation": subject_data.get("regulation", ""),
        "units": subject_data.get("units", []),
        "flat_topics": subject_data.get("flat_topics", []),
        "experiments": subject_data.get("experiments", []),
        "course_objectives": subject_data.get("course_objectives", []),
        "course_outcomes": subject_data.get("course_outcomes", []),
        "text_books": subject_data.get("text_books", []),
        "reference_books": subject_data.get("reference_books", []),
    }


def _to_date(value: Any) -> date:
    """Coerce a value to a date object."""
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return pd.to_datetime(value).date()
    return value


def _df_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert DataFrame to list of dicts with clean string values."""
    if df.empty:
        return []
    records = df.astype(str).to_dict("records")
    return records

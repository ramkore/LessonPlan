"""Shared dataclasses, caching, file I/O utilities, and project configuration."""
from __future__ import annotations

import hashlib
import pickle
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from shutil import copy2
from typing import Any

import pandas as pd

from .logger import get_logger

logger = get_logger(__name__)


INPUT_FOLDERS = {
    "academic_calendar": "academic_calendar",
    "holiday_list": "holiday_list",
    "syllabus": "syllabus",
    "timetable": "timetable",
}

OUTPUT_FILES = {
    "lesson_plan_excel": "lesson_plan.xlsx",
    "lesson_plan_word": "lesson_plan.docx",
    "lesson_plan_pdf": "lesson_plan.pdf",
    "monthly_plan_excel": "monthly_teaching_plan.xlsx",
    "coverage_report_excel": "syllabus_coverage_report.xlsx",
}

OUTPUT_LABELS = {
    "lesson_plan_excel": "Lesson_Plan",
    "lesson_plan_word": "Lesson_Plan",
    "lesson_plan_pdf": "Lesson_Plan",
    "monthly_plan_excel": "Monthly_Teaching_Plan",
    "coverage_report_excel": "Syllabus_Coverage_Report",
}

OUTPUT_EXTENSIONS = {
    "lesson_plan_excel": ".xlsx",
    "lesson_plan_word": ".docx",
    "lesson_plan_pdf": ".pdf",
    "monthly_plan_excel": ".xlsx",
    "coverage_report_excel": ".xlsx",
}

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "text",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".xlsx": "spreadsheet",
    ".csv": "spreadsheet",
}

PARSED_DOCUMENT_CACHE_VERSION = "2026-03-19"

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_UPLOAD_SIZE_LABEL = "50 MB"


class ProcessingError(Exception):
    """Raised when the application cannot parse or generate the requested data."""


@dataclass
class ParsedDocument:
    file_path: Path
    file_type: str
    raw_text: str = ""
    tables: list[pd.DataFrame] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LessonPlanBundle:
    lesson_plan: pd.DataFrame
    monthly_plan: pd.DataFrame
    coverage_report: pd.DataFrame
    class_schedule: pd.DataFrame
    teaching_days: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def report_output_paths(bundle: LessonPlanBundle, output_dir: str | Path) -> dict[str, Path]:
    base_dir = Path(output_dir)
    branch_dir = branch_output_directory(bundle, base_dir)
    stem = lesson_plan_output_stem(bundle)
    return {
        key: branch_dir / f"{stem}_{OUTPUT_LABELS[key]}{OUTPUT_EXTENSIONS[key]}"
        for key in OUTPUT_LABELS
    }


def branch_output_directory(bundle: LessonPlanBundle, output_dir: Path) -> Path:
    branch_section = _branch_section_folder(bundle)
    subject_folder = _subject_output_folder(bundle)

    target = output_dir
    if branch_section:
        target = target / branch_section
    if subject_folder:
        target = target / subject_folder
    target.mkdir(parents=True, exist_ok=True)
    return target


def lesson_plan_output_stem(bundle: LessonPlanBundle) -> str:
    faculty_info = bundle.metadata.get("faculty_info", {})
    year_token, sem_token = _year_sem_tokens(str(faculty_info.get("semester", "")).strip())
    branch_token = _branch_token(bundle)
    section_token = _section_token(bundle)
    subject_token = _subject_token(bundle)
    lab_token = _lab_token(bundle)

    parts = [part for part in [year_token, "B.Tech", sem_token, "Sem", branch_token, section_token, subject_token, lab_token] if part]
    return "_".join(parts) if parts else "Lesson_Plan"


def _branch_token(bundle: LessonPlanBundle) -> str:
    faculty_info = bundle.metadata.get("faculty_info", {})
    branch = str(faculty_info.get("branch", "")).strip()
    if not branch:
        planned_branches = bundle.metadata.get("planned_branches", [])
        if isinstance(planned_branches, list) and planned_branches:
            branch = str(planned_branches[0]).strip()
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", branch.upper()).strip("_")
    return cleaned


def _subject_token(bundle: LessonPlanBundle) -> str:
    faculty_info = bundle.metadata.get("faculty_info", {})
    course_title = str(bundle.metadata.get("course_title", faculty_info.get("subject_name", ""))).strip()
    cleaned = re.sub(r"\([^)]*\)", " ", course_title)
    words = [
        word
        for word in re.findall(r"[A-Za-z0-9]+", cleaned)
        if word.lower() not in {"and", "of", "the", "for", "to", "in", "with", "lab", "laboratory", "practical"}
    ]
    abbreviation = "".join(word[0].upper() for word in words[:4])
    if abbreviation:
        return abbreviation

    course_code = str(bundle.metadata.get("course_code", "")).strip().upper()
    fallback = re.sub(r"[^A-Z0-9]+", "", course_code)
    return fallback[:6] or "SUBJECT"


def _section_token(bundle: LessonPlanBundle) -> str:
    faculty_info = bundle.metadata.get("faculty_info", {})
    section = str(faculty_info.get("section", "")).strip()
    if not section:
        return ""

    cleaned = re.sub(r"(?i)\bsection\b", " ", section)
    compact = re.sub(r"[^A-Za-z0-9]+", "_", cleaned.upper()).strip("_")
    return compact


def _lab_token(bundle: LessonPlanBundle) -> str:
    faculty_info = bundle.metadata.get("faculty_info", {})
    course_title = str(bundle.metadata.get("course_title", faculty_info.get("subject_name", ""))).strip()
    cleaned = normalize_whitespace(course_title).lower()
    if any(token in cleaned for token in (" lab", "laboratory", "practical")) or cleaned.endswith("lab"):
        return "Lab"
    return ""


def _branch_section_folder(bundle: LessonPlanBundle) -> str:
    branch = _branch_token(bundle)
    section = _section_token(bundle)
    return " ".join(part for part in [branch, section] if part)


def _subject_type_folder(bundle: LessonPlanBundle) -> str:
    return "Lab" if _lab_token(bundle) else "Sub"


def _subject_output_folder(bundle: LessonPlanBundle) -> str:
    subject_token = _subject_token(bundle)
    subject_type = _subject_type_folder(bundle)
    if subject_token and subject_type:
        return f"{subject_token}_{subject_type}"
    return subject_token or subject_type


def _year_sem_tokens(value: str) -> tuple[str, str]:
    cleaned = normalize_whitespace(value).replace(".", " ")
    year_match = re.search(r"\b([IVX]+|\d+)\s*year\b", cleaned, flags=re.IGNORECASE)
    sem_match = re.search(r"\b([IVX]+|\d+)\s*sem(?:ester)?\b", cleaned, flags=re.IGNORECASE)

    if year_match and sem_match:
        return (_roman_token(year_match.group(1)), _roman_token(sem_match.group(1)))

    compact_tokens = [token for token in re.split(r"[-/]", cleaned) if token.strip()]
    if len(compact_tokens) >= 2:
        return (_roman_token(compact_tokens[0]), _roman_token(compact_tokens[1]))

    roman_candidates = re.findall(r"\b([IVX]+|\d+)\b", cleaned, flags=re.IGNORECASE)
    if len(roman_candidates) >= 2:
        return (_roman_token(roman_candidates[0]), _roman_token(roman_candidates[1]))
    if len(roman_candidates) == 1:
        token = _roman_token(roman_candidates[0])
        return (token, token)
    return ("", "")


def _roman_token(value: str) -> str:
    cleaned = normalize_whitespace(value).upper()
    if cleaned.isdigit():
        return _roman(int(cleaned))
    return cleaned


def _roman(value: int) -> str:
    numerals = (
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    remaining = max(value, 0)
    result: list[str] = []
    for number, symbol in numerals:
        while remaining >= number:
            result.append(symbol)
            remaining -= number
    return "".join(result)


def header_image_path() -> Path | None:
    candidate = project_root() / 'assets' / 'header.png'
    return candidate if candidate.exists() else None


CACHE_MAX_AGE_DAYS = 90


def _evict_stale_cache_entries() -> None:
    """Remove parsed document cache files older than CACHE_MAX_AGE_DAYS."""
    import time
    cache_dir = parsed_cache_directory()
    if not cache_dir.exists():
        return
    cutoff = time.time() - (CACHE_MAX_AGE_DAYS * 86400)
    for pkl_file in cache_dir.glob("*.pkl"):
        try:
            if pkl_file.stat().st_mtime < cutoff:
                pkl_file.unlink(missing_ok=True)
                logger.debug("Evicted stale cache entry: %s", pkl_file.name)
        except OSError:
            pass


def ensure_directories() -> None:
    root = project_root()
    (root / "input").mkdir(exist_ok=True)
    for folder in INPUT_FOLDERS.values():
        (root / "input" / folder).mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(exist_ok=True)
    parsed_cache_directory().mkdir(parents=True, exist_ok=True)
    _evict_stale_cache_entries()


def normalize_whitespace(text: Any) -> str:
    if text is None:
        return ""
    text = str(text).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def safe_string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return normalize_whitespace(value)


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for column in frame.columns:
        value = safe_string(column).lower()
        value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
        renamed[column] = value or "column"
    return frame.rename(columns=renamed)


def clean_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    cleaned = frame.copy()
    for column in cleaned.columns:
        cleaned[column] = cleaned[column].map(safe_string)
    cleaned = cleaned.replace("", pd.NA).dropna(how="all").fillna("")
    return cleaned


def table_to_dataframe(table: list[list[Any]]) -> pd.DataFrame:
    rows = [[safe_string(cell) for cell in row] for row in table if row]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return pd.DataFrame()

    header = rows[0]
    non_empty_header = [cell for cell in header if cell]
    unique_header = len(set(cell.lower() for cell in non_empty_header)) == len(non_empty_header)
    use_header = bool(non_empty_header) and unique_header

    if use_header:
        data = rows[1:] or [[]]
        width = len(header)
        normalized_rows = [(row + [""] * width)[:width] for row in data]
        frame = pd.DataFrame(normalized_rows, columns=header)
    else:
        width = max(len(row) for row in rows)
        normalized_rows = [(row + [""] * width)[:width] for row in rows]
        frame = pd.DataFrame(normalized_rows, columns=[f"column_{index + 1}" for index in range(width)])
    return clean_dataframe(frame)


def strip_ordinal_suffixes(text: str) -> str:
    return re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)


def coerce_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 20000 <= float(value) <= 80000:
        base = pd.Timestamp("1899-12-30")
        return (base + pd.to_timedelta(int(float(value)), unit="D")).date()

    candidate = normalize_whitespace(strip_ordinal_suffixes(str(value)))
    parse_candidates = [candidate]

    without_parentheses = normalize_whitespace(re.sub(r"\([^)]*\)", " ", candidate))
    if without_parentheses and without_parentheses not in parse_candidates:
        parse_candidates.append(without_parentheses)

    stripped_trailing = normalize_whitespace(re.sub(r"[^0-9A-Za-z/,: -]+", " ", without_parentheses))
    if stripped_trailing and stripped_trailing not in parse_candidates:
        parse_candidates.append(stripped_trailing)

    for candidate_value in parse_candidates:
        parsed = pd.to_datetime(candidate_value, dayfirst=True, errors="coerce")
        if not pd.isna(parsed):
            return parsed.date()

    patterns = (
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
        r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}",
        r"[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}",
    )
    for pattern in patterns:
        match = re.search(pattern, candidate)
        if not match:
            continue
        parsed = pd.to_datetime(match.group(0), dayfirst=True, errors="coerce")
        if not pd.isna(parsed):
            return parsed.date()
    return None


def extract_dates_from_text(text: str) -> list[date]:
    patterns = [
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b",
        r"\b[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4}\b",
    ]
    matches: list[date] = []
    for pattern in patterns:
        for raw_match in re.findall(pattern, strip_ordinal_suffixes(text)):
            parsed = coerce_date(raw_match)
            if parsed and parsed not in matches:
                matches.append(parsed)
    return matches


def expand_date_range(start_date: date, end_date: date) -> list[date]:
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    total_days = (end_date - start_date).days
    return [start_date + timedelta(days=offset) for offset in range(total_days + 1)]


def month_label(value: date) -> str:
    return value.strftime("%B %Y")


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def escape_cell_value(value: object) -> object:
    if isinstance(value, str) and value and value[0] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value


def persist_uploaded_file(source_path: str | Path, input_kind: str) -> Path:
    ensure_directories()
    source = Path(source_path).resolve()
    target_dir = project_root() / "input" / INPUT_FOLDERS[input_kind]
    target_dir.mkdir(parents=True, exist_ok=True)
    sanitized_name = Path(source.name).name
    if ".." in sanitized_name or "/" in sanitized_name or "\\" in sanitized_name:
        raise ProcessingError(f"Invalid filename: {sanitized_name}")
    target = target_dir / sanitized_name
    if not str(target.resolve()).startswith(str(target_dir.resolve())):
        raise ProcessingError(f"File path escapes target directory: {sanitized_name}")
    if source == target:
        return target
    copy2(source, target)
    return target


def load_parsed_document(file_path: str | Path) -> ParsedDocument:
    from .doc_parser import parse_document_file
    from .excel_parser import parse_spreadsheet_file
    from .file_detector import detect_file_type
    from .image_ocr_parser import parse_image_file
    from .pdf_parser import parse_pdf_file

    path = Path(file_path).resolve()
    cached = _load_cached_parsed_document(path)
    if cached is not None:
        return cached

    detected = detect_file_type(path)
    category = detected["category"]

    if category == "document":
        parsed = parse_pdf_file(path) if detected["type"] == "pdf" else parse_document_file(path)
    elif category == "image":
        parsed = parse_image_file(path)
    elif category == "spreadsheet":
        parsed = parse_spreadsheet_file(path)
    else:
        raise ProcessingError(f"Unsupported file type for {file_path}")

    _store_cached_parsed_document(path, parsed)
    return parsed


def parsed_cache_directory() -> Path:
    return project_root() / ".cache" / "parsed_documents"


class _RestrictedUnpickler(pickle.Unpickler):
    _ALLOWED_MODULES = {
        "builtins": {"set", "frozenset", "dict", "list", "tuple", "bytes", "str", "int", "float", "bool", "complex", "type"},
        "collections": {"OrderedDict"},
        "datetime": {"date", "datetime", "timedelta"},
        "pathlib": {"PurePosixPath", "PureWindowsPath", "PosixPath", "WindowsPath"},
        "pandas.core.frame": {"DataFrame"},
        "pandas.core.series": {"Series"},
        "pandas.core.indexes.base": {"Index"},
        "pandas.core.indexes.range": {"RangeIndex"},
        "numpy": {"ndarray", "dtype"},
        "numpy.core.multiarray": {"_reconstruct", "scalar"},
    }

    def find_class(self, module: str, name: str) -> type:
        if module == "src.utils" and name == "ParsedDocument":
            return ParsedDocument
        allowed = self._ALLOWED_MODULES.get(module)
        if allowed is not None and name in allowed:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"Restricted: {module}.{name}")


def _load_cached_parsed_document(path: Path) -> ParsedDocument | None:
    cache_path = _parsed_document_cache_path(path)
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("rb") as handle:
            payload = _RestrictedUnpickler(handle).load()
    except (OSError, pickle.PickleError, EOFError) as exc:
        logger.debug("Cache load failed for %s: %s", cache_path.name, exc)
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("version") != PARSED_DOCUMENT_CACHE_VERSION:
        return None

    try:
        current_signature = _parsed_document_signature(path)
    except OSError:
        return None
    cached_signature = payload.get("signature", {})
    if not isinstance(cached_signature, dict) or current_signature != cached_signature:
        return None

    parsed = payload.get("parsed")
    if not isinstance(parsed, ParsedDocument):
        return None
    parsed.file_path = path
    return parsed


def _store_cached_parsed_document(path: Path, parsed_document: ParsedDocument) -> None:
    ensure_directories()
    cache_path = _parsed_document_cache_path(path)
    payload = {
        "version": PARSED_DOCUMENT_CACHE_VERSION,
        "signature": _parsed_document_signature(path),
        "parsed": parsed_document,
    }

    try:
        temp_path = cache_path.with_suffix(".tmp")
        with temp_path.open("wb") as handle:
            pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)
        temp_path.replace(cache_path)
    except OSError as exc:
        logger.warning("Could not write cache for %s: %s", path.name, exc)
        return


def _parsed_document_cache_path(path: Path) -> Path:
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return parsed_cache_directory() / f"{digest}.pkl"


def _parsed_document_signature(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }

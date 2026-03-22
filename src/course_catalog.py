"""Multi-subject course catalog parsing from structured PDF tables."""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from pathlib import Path

from .logger import get_logger
from .syllabus_parser import SyllabusParser
from .utils import ParsedDocument, ProcessingError, normalize_whitespace

logger = get_logger(__name__)

_FALLBACK_UNITS_PATH = Path(__file__).resolve().parent.parent / "data" / "courses.json"
_fallback_units_cache: dict[str, list[tuple[str, list[str]]]] | None = None


def _load_fallback_units() -> dict[str, list[tuple[str, list[str]]]]:
    """Load course fallback units from data/courses.json (lazy, cached per process)."""
    global _fallback_units_cache
    if _fallback_units_cache is not None:
        return _fallback_units_cache
    try:
        raw = json.loads(_FALLBACK_UNITS_PATH.read_text(encoding="utf-8"))
        _fallback_units_cache = {
            code: [(entry[0], entry[1]) for entry in entries]
            for code, entries in raw.items()
        }
        logger.debug("Loaded %d fallback course entries from %s", len(_fallback_units_cache), _FALLBACK_UNITS_PATH.name)
    except (OSError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
        logger.warning("Could not load fallback course catalog from %s: %s. Using empty fallback.", _FALLBACK_UNITS_PATH, exc)
        _fallback_units_cache = {}
    return _fallback_units_cache


class CourseCatalogParser:
    course_heading_pattern = re.compile(r'^\s*([A-Z]{3,}\d{3}[A-Z]{1,})\s*:\s*(.+)$')
    year_sem_pattern = re.compile(r'([IVX]+)\s*Year\s*([IVX]+)\s*Sem', re.IGNORECASE)
    semester_heading_pattern = re.compile(r'^\s*([IVX]+)\s*Year\s*([IVX]+)\s*Semester\s*$', re.IGNORECASE)
    course_code_pattern = re.compile(r'^[A-Z]{3,}\d{3}[A-Z]{1,}$')
    regulation_pattern = re.compile(r'\bPR(\d{2})\b', re.IGNORECASE)

    def parse(self, document: ParsedDocument) -> dict[str, object]:
        parser = SyllabusParser()
        detailed_subjects = self._parse_detailed_sections(document, parser)
        structured_subjects = self._extract_course_structure_subjects(document)

        if structured_subjects:
            subjects = self._merge_structured_and_detailed_subjects(document, structured_subjects, detailed_subjects)
        elif detailed_subjects:
            subjects = list(detailed_subjects.values())
        else:
            syllabus = parser.parse(document)
            year_sem = self._extract_year_sem(document.raw_text)
            subjects = [self._build_subject_record(syllabus, year_sem, 1, inferred=False)]

        if not subjects:
            raise ProcessingError('Unable to identify subject-wise syllabus sections.')

        year_sems = self._unique_preserve_order(subject['year_sem'] for subject in subjects if subject['year_sem'])
        return {
            'subjects': subjects,
            'year_sems': year_sems,
        }

    def _parse_detailed_sections(self, document: ParsedDocument, parser: SyllabusParser) -> OrderedDict[str, dict[str, object]]:
        subjects: OrderedDict[str, dict[str, object]] = OrderedDict()
        errors: list[str] = []

        for order, section_document in enumerate(self._split_subject_sections(document), start=1):
            try:
                syllabus = parser.parse(section_document)
            except ProcessingError as exc:
                errors.append(f"{section_document.metadata.get('course_code', section_document.file_path.name)}: {exc}")
                continue

            year_sem = str(section_document.metadata.get('year_sem', '')).strip() or self._extract_year_sem(section_document.raw_text)
            record = self._build_subject_record(syllabus, year_sem, order, inferred=False)
            subjects[record['course_code']] = record

        if not subjects and errors:
            raise ProcessingError(f"Unable to identify subject-wise syllabus sections. {'; '.join(errors[:3])}")
        return subjects

    def _merge_structured_and_detailed_subjects(
        self,
        document: ParsedDocument,
        structured_subjects: list[dict[str, str]],
        detailed_subjects: OrderedDict[str, dict[str, object]],
    ) -> list[dict[str, object]]:
        subjects: list[dict[str, object]] = []
        order = 1
        used_codes: set[str] = set()

        for entry in structured_subjects:
            course_code = entry['course_code']
            if not course_code or course_code in used_codes:
                continue
            used_codes.add(course_code)

            if course_code in detailed_subjects:
                record = dict(detailed_subjects[course_code])
                record['course_title'] = entry['course_title'] or record['course_title']
                record['display_name'] = self._display_name(course_code, record['course_title'])
                record['year_sem'] = entry['year_sem'] or record['year_sem']
                record['sort_order'] = order
                record['inferred'] = False
            else:
                syllabus = self._infer_syllabus(course_code, entry['course_title'], document.raw_text)
                record = self._build_subject_record(syllabus, entry['year_sem'], order, inferred=True)

            subjects.append(record)
            order += 1

        for record in detailed_subjects.values():
            course_code = str(record.get('course_code', '')).strip().upper()
            if not course_code or course_code in used_codes:
                continue
            extra = dict(record)
            extra['sort_order'] = order
            extra['inferred'] = False
            subjects.append(extra)
            order += 1

        return subjects

    def _extract_course_structure_subjects(self, document: ParsedDocument) -> list[dict[str, str]]:
        semester_labels = self._extract_semester_headings(document.raw_text)
        subjects: list[dict[str, str]] = []

        for index, table in enumerate(document.tables):
            year_sem = semester_labels[index] if index < len(semester_labels) else ''
            subjects.extend(self._subjects_from_table(table, year_sem))
        return subjects

    def _subjects_from_table(self, table, year_sem: str) -> list[dict[str, str]]:
        normalized_columns = {normalize_whitespace(column).lower(): column for column in table.columns}
        code_column = normalized_columns.get('course code')
        course_column = normalized_columns.get('course')
        if not code_column or not course_column:
            return []

        subjects: list[dict[str, str]] = []
        for _, row in table.iterrows():
            course_code = normalize_whitespace(row.get(code_column)).upper()
            course_title = normalize_whitespace(row.get(course_column))
            if not self.course_code_pattern.match(course_code):
                continue
            if not course_title or course_title.lower() in {'course', 'total', 'induction program'}:
                continue
            subjects.append(
                {
                    'course_code': course_code,
                    'course_title': course_title,
                    'year_sem': year_sem,
                }
            )
        return subjects

    def _extract_semester_headings(self, raw_text: str) -> list[str]:
        labels: list[str] = []
        for raw_line in raw_text.splitlines():
            line = normalize_whitespace(raw_line)
            match = self.semester_heading_pattern.match(line)
            if not match:
                continue
            label = f"{match.group(1).upper()} Year {match.group(2).upper()} Sem"
            if label not in labels:
                labels.append(label)
        return labels

    def _split_subject_sections(self, document: ParsedDocument) -> list[ParsedDocument]:
        sections: list[dict[str, object]] = []
        current: dict[str, object] | None = None

        for raw_line in document.raw_text.splitlines():
            line = normalize_whitespace(raw_line)
            if not line:
                continue

            heading_match = self.course_heading_pattern.match(line)
            if heading_match:
                if current and current['lines']:
                    sections.append(current)
                current = {
                    'course_code': heading_match.group(1).upper(),
                    'course_title': heading_match.group(2).strip(),
                    'lines': [line],
                }
                continue

            if current is not None:
                current['lines'].append(line)

        if current and current['lines']:
            sections.append(current)

        documents: list[ParsedDocument] = []
        for section in sections:
            raw_text = '\n'.join(section['lines'])
            if 'course objectives' not in raw_text.lower() and 'unit' not in raw_text.lower() and 'task' not in raw_text.lower():
                continue
            documents.append(
                ParsedDocument(
                    file_path=document.file_path,
                    file_type=document.file_type,
                    raw_text=raw_text,
                    tables=[],
                    metadata={
                        'course_code': section['course_code'],
                        'course_title': section['course_title'],
                        'year_sem': self._extract_year_sem(raw_text),
                        'parent_file': document.file_path.name,
                    },
                )
            )
        return documents

    def _extract_year_sem(self, raw_text: str) -> str:
        match = self.year_sem_pattern.search(raw_text)
        if not match:
            return ''
        return f"{match.group(1).upper()} Year {match.group(2).upper()} Sem"

    def _infer_syllabus(self, course_code: str, course_title: str, raw_text: str) -> dict[str, object]:
        units_source = _load_fallback_units().get(course_code) or self._generic_units(course_title)
        units: list[dict[str, object]] = []
        flat_topics: list[dict[str, str]] = []
        for index, (unit_name, topics) in enumerate(units_source, start=1):
            unit_topics = [normalize_whitespace(topic) for topic in topics if normalize_whitespace(topic)]
            unit = {'unit': unit_name, 'topics': unit_topics, 'co': f'CO{index}'}
            units.append(unit)
            flat_topics.extend({'unit': unit_name, 'topic': topic, 'co': f'CO{index}'} for topic in unit_topics)

        regulation_match = self.regulation_pattern.search(raw_text)
        regulation = f"R{regulation_match.group(1)}" if regulation_match else 'R25'
        inferred_outcomes = [
            f"Understand the fundamentals of {course_title}",
            f"Apply core concepts of {course_title} in problem solving",
            f"Demonstrate practical and analytical skills in {course_title}",
        ]

        return {
            'course_title': course_title,
            'course_code': course_code,
            'regulation': regulation,
            'course_objectives': [f"Build a working foundation in {course_title}"],
            'course_outcomes': inferred_outcomes,
            'text_books': [],
            'reference_books': [],
            'units': units,
            'flat_topics': flat_topics,
        }

    def _generic_units(self, course_title: str) -> list[tuple[str, list[str]]]:
        title = normalize_whitespace(course_title)
        lowered = title.lower()
        if any(token in lowered for token in ('lab', 'workshop', 'graphics', 'skills')):
            return [
                (
                    'Unit I',
                    [
                        f'Introduction and orientation to {title}',
                        f'Foundational exercises in {title}',
                        f'Guided practice sessions in {title}',
                        f'Applied problem solving in {title}',
                        f'Record work, revision and viva preparation for {title}',
                    ],
                )
            ]

        return [
            ('Unit I', [f'Foundations of {title}', f'Core terminology in {title}', f'Basic problem solving in {title}']),
            ('Unit II', [f'Core principles of {title}', f'Analytical methods in {title}', f'Worked examples in {title}']),
            ('Unit III', [f'Tools and techniques used in {title}', f'Applications of {title}', f'Modeling and interpretation in {title}']),
            ('Unit IV', [f'Advanced concepts in {title}', f'Practical engineering relevance of {title}', f'Case studies in {title}']),
            ('Unit V', [f'Integrated practice in {title}', f'Revision and discussion in {title}', f'Assessment readiness in {title}']),
        ]

    def _build_subject_record(self, syllabus: dict[str, object], year_sem: str, order: int, inferred: bool) -> dict[str, object]:
        course_code = str(syllabus.get('course_code', '')).strip().upper()
        course_title = str(syllabus.get('course_title', '')).strip()
        return {
            'course_code': course_code,
            'course_title': course_title,
            'display_name': self._display_name(course_code, course_title),
            'year_sem': year_sem,
            'sort_order': order,
            'syllabus': syllabus,
            'inferred': inferred,
        }

    def _display_name(self, course_code: str, course_title: str) -> str:
        display_title = self._display_title(course_title)
        return ' - '.join(part for part in [course_code, display_title] if part)

    def _display_title(self, title: str) -> str:
        cleaned = normalize_whitespace(title)
        if not cleaned:
            return ''
        if not cleaned.isupper():
            return cleaned

        words: list[str] = []
        acronyms = {'IT', 'AI', 'ML', 'CSE', 'ECE', 'EEE', 'PPS', 'DS', 'LAB'}
        for token in cleaned.split():
            normalized = token.strip()
            if normalized in acronyms or len(normalized) <= 2:
                words.append(normalized)
            else:
                words.append(normalized.capitalize())
        return ' '.join(words)

    def _unique_preserve_order(self, values) -> list[str]:
        ordered: list[str] = []
        for value in values:
            cleaned = normalize_whitespace(value)
            if cleaned and cleaned not in ordered:
                ordered.append(cleaned)
        return ordered

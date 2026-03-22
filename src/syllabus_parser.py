"""Syllabus content extraction — units, topics, experiments, and course outcomes."""
from __future__ import annotations

import re
from collections import OrderedDict

from .logger import get_logger
from .utils import ParsedDocument, ProcessingError, normalize_whitespace

logger = get_logger(__name__)


class SyllabusParser:
    unit_pattern = re.compile(r'^\s*unit\s*[-–—\s]*([ivx0-9]+)\s*(?:[:.\-–—]+)?\s*(.*)$', re.IGNORECASE)
    course_title_pattern = re.compile(r'course\s+title\s*[:\-]?\s*(.+)$', re.IGNORECASE)
    course_code_pattern = re.compile(r'\b([A-Z]{2,}\d{2,}[A-Z]*)\s*[:\-]\s*(.+)$')
    regulation_pattern = re.compile(r'\bP?R(\d{2})\b', re.IGNORECASE)
    objective_pattern = re.compile(r'course\s+objectives?\s*[:\-]?\s*(.*)$', re.IGNORECASE)
    outcome_pattern = re.compile(r'\b(CO\s*\d+)\b', re.IGNORECASE)
    task_pattern = re.compile(r'^task\s*[- ]*(\d+)\s*[:\-]?\s*(.*)$', re.IGNORECASE)

    def parse(self, document: ParsedDocument) -> dict[str, object]:
        units: OrderedDict[str, dict[str, object]] = OrderedDict()
        course_title = ''
        course_code = ''
        regulation = ''
        objectives: list[str] = []
        outcomes: list[str] = []
        text_books: list[str] = []
        reference_books: list[str] = []
        experiment_topics: list[str] = []
        outline_topics: list[str] = []

        for table in document.tables:
            self._parse_table(table, units)

        current_unit: str | None = None
        capture_objectives = False
        capture_outcomes = False
        capture_text_books = False
        capture_reference_books = False
        capture_experiments = False
        current_outline_heading = ''
        pending_experiment = ''

        for raw_line in document.raw_text.splitlines():
            line = normalize_whitespace(raw_line)
            if not line:
                continue

            code_match = self.course_code_pattern.search(line)
            if code_match and code_match.group(1).upper().startswith('CO') is False:
                if not course_code:
                    course_code = code_match.group(1).strip().upper()
                if not course_title:
                    course_title = code_match.group(2).strip()
                continue

            regulation_match = self.regulation_pattern.search(line)
            if regulation_match and not regulation:
                regulation = f"R{regulation_match.group(1)}"

            title_match = self.course_title_pattern.search(line)
            if title_match and not course_title:
                course_title = title_match.group(1).strip()
                continue

            lower_line = line.lower()
            if lower_line.startswith('text books') or lower_line.startswith('textbooks'):
                pending_experiment = self._flush_pending_experiment(pending_experiment, experiment_topics)
                capture_text_books = True
                capture_reference_books = False
                capture_objectives = False
                capture_outcomes = False
                capture_experiments = False
                inline = line.split(':', 1)[-1] if ':' in line else ''
                text_books.extend(self._split_book_entries(inline))
                continue

            if lower_line.startswith('reference books') or lower_line.startswith('reference book') or lower_line.startswith('reference:'):
                pending_experiment = self._flush_pending_experiment(pending_experiment, experiment_topics)
                capture_reference_books = True
                capture_text_books = False
                capture_objectives = False
                capture_outcomes = False
                capture_experiments = False
                inline = line.split(':', 1)[-1] if ':' in line else ''
                reference_books.extend(self._split_book_entries(inline))
                continue

            if capture_text_books:
                if self._is_books_section_break(line):
                    capture_text_books = False
                else:
                    entries = self._split_book_entries(line)
                    if len(entries) > 1 or not text_books or self._is_new_book_line(line):
                        text_books.extend(entries)
                    else:
                        text_books[-1] += ', ' + entries[0]
                    continue

            if capture_reference_books:
                if self._is_books_section_break(line):
                    capture_reference_books = False
                else:
                    entries = self._split_book_entries(line)
                    if len(entries) > 1 or not reference_books or self._is_new_book_line(line):
                        reference_books.extend(entries)
                    else:
                        reference_books[-1] += ', ' + entries[0]
                    continue

            if line.lower().startswith('course objectives'):
                capture_objectives = True
                capture_outcomes = False
                capture_experiments = False
                inline = self._split_topics(line.split(':', 1)[-1]) if ':' in line else []
                objectives.extend(inline)
                continue

            if line.lower().startswith('course outcomes'):
                capture_outcomes = True
                capture_objectives = False
                capture_experiments = False
                inline = self._split_topics(line.split(':', 1)[-1]) if ':' in line else []
                outcomes.extend(inline)
                continue

            unit_match = self.unit_pattern.match(line)
            if unit_match:
                pending_experiment = self._flush_pending_experiment(pending_experiment, experiment_topics)
                capture_objectives = False
                capture_outcomes = False
                capture_experiments = False
                current_unit = self._normalize_unit(unit_match.group(1))
                units.setdefault(current_unit, {'unit': current_unit, 'topics': [], 'co': ''})
                inline_topics = self._split_topics(unit_match.group(2))
                self._append_topics(units[current_unit]['topics'], inline_topics)
                continue

            if self._is_experiment_heading(line):
                pending_experiment = self._flush_pending_experiment(pending_experiment, experiment_topics)
                capture_experiments = True
                capture_objectives = False
                capture_outcomes = False
                inline = line.split(':', 1)[-1] if ':' in line else ''
                pending_experiment = self._consume_experiment_line(inline, experiment_topics, pending_experiment)
                continue

            if capture_experiments:
                if self._is_experiment_section_break(line):
                    pending_experiment = self._flush_pending_experiment(pending_experiment, experiment_topics)
                    capture_experiments = False
                else:
                    pending_experiment = self._consume_experiment_line(line, experiment_topics, pending_experiment)
                    continue

            if (capture_objectives or capture_outcomes) and self._starts_topic_block(line):
                capture_objectives = False
                capture_outcomes = False

            if capture_objectives and not self._looks_like_metadata(line):
                objectives.extend(self._split_topics(line))
                continue

            if capture_outcomes and not self._looks_like_metadata(line):
                outcomes.extend(self._split_topics(line))
                continue

            outcome_match = self.outcome_pattern.search(line)
            if outcome_match and line not in outcomes:
                outcomes.append(line)

            if current_unit and not self._looks_like_metadata(line):
                self._append_topics(units[current_unit]['topics'], self._split_topics(line))
                continue

            current_outline_heading = self._capture_outline_heading(line, current_outline_heading)
            task_topic = self._extract_outline_topic(line, current_outline_heading)
            if task_topic:
                outline_topics.append(task_topic)

        pending_experiment = self._flush_pending_experiment(pending_experiment, experiment_topics)
        experiment_entries = self._extract_experiment_entries(document.raw_text)
        if experiment_entries:
            experiment_topics = [entry['topic'] for entry in experiment_entries if entry.get('topic')]

        if not units and experiment_topics:
            units['Unit I'] = {'unit': 'Unit I', 'topics': self._unique_preserve_order(experiment_topics), 'co': 'CO1'}

        if not units and outline_topics:
            units['Unit I'] = {'unit': 'Unit I', 'topics': self._unique_preserve_order(outline_topics), 'co': 'CO1'}

        if not units:
            raise ProcessingError('Unable to identify syllabus units and topics.')

        ordered_units = list(units.values())
        for index, unit in enumerate(ordered_units, start=1):
            unit['topics'] = [topic for topic in unit['topics'] if topic]
            if not unit['topics']:
                unit['topics'] = [f"{unit['unit']} overview"]
            unit['co'] = unit['co'] or f'CO{index}'

        flat_topics = [
            {'unit': unit['unit'], 'topic': topic, 'co': unit['co']}
            for unit in ordered_units
            for topic in unit['topics']
        ]

        return {
            'course_title': course_title or self._infer_course_title(document.raw_text, document.file_path.stem),
            'course_code': course_code,
            'regulation': regulation,
            'course_objectives': self._unique_preserve_order(objectives),
            'course_outcomes': self._unique_preserve_order(outcomes),
            'text_books': self._clean_book_entries(text_books),
            'reference_books': self._clean_book_entries(reference_books),
            'units': ordered_units,
            'flat_topics': flat_topics,
            'experiments': experiment_entries,
        }

    def _parse_table(self, table, units: OrderedDict[str, dict[str, object]]) -> None:
        lowered_columns = [str(column).strip().lower().replace(' ', '_') for column in table.columns]
        unit_col = next((column for column in lowered_columns if 'unit' in column), None)
        topic_col = next((column for column in lowered_columns if 'topic' in column or 'contents' in column), None)
        co_col = next((column for column in lowered_columns if column.startswith('co')), None)

        if unit_col and topic_col:
            table = table.copy()
            table.columns = lowered_columns
            for _, row in table.iterrows():
                unit_name = self._normalize_unit(str(row.get(unit_col, '')).replace('Unit', '').strip())
                if not unit_name:
                    continue
                units.setdefault(unit_name, {'unit': unit_name, 'topics': [], 'co': ''})
                self._append_topics(units[unit_name]['topics'], self._split_topics(str(row.get(topic_col, ''))))
                if co_col and not units[unit_name]['co']:
                    units[unit_name]['co'] = normalize_whitespace(row.get(co_col))
            return

        current_unit: str | None = None
        outline_topics: list[str] = []
        current_heading = ''
        for _, row in table.iterrows():
            row_text = ' '.join(str(value) for value in row.tolist())
            normalized_row = normalize_whitespace(row_text)
            unit_match = self.unit_pattern.match(normalized_row)
            if unit_match:
                current_unit = self._normalize_unit(unit_match.group(1))
                units.setdefault(current_unit, {'unit': current_unit, 'topics': [], 'co': ''})
                inline_topics = self._split_topics(unit_match.group(2))
                self._append_topics(units[current_unit]['topics'], inline_topics)
                continue
            if current_unit and not self._looks_like_metadata(normalized_row):
                self._append_topics(units[current_unit]['topics'], self._split_topics(normalized_row))
                continue

            current_heading = self._capture_outline_heading(normalized_row, current_heading)
            topic = self._extract_outline_topic(normalized_row, current_heading)
            if topic:
                outline_topics.append(topic)

        if not units and outline_topics:
            units['Unit I'] = {'unit': 'Unit I', 'topics': self._unique_preserve_order(outline_topics), 'co': 'CO1'}

    def _split_topics(self, text: str) -> list[str]:
        cleaned = normalize_whitespace(text)
        if not cleaned:
            return []

        cleaned = re.sub(r'^[0-9]+[.)]\s*', '', cleaned)
        cleaned = cleaned.strip(':- ')
        if not cleaned:
            return []

        separators = [r';', r'\|', r'•', r'●']
        for separator in separators:
            if re.search(separator, cleaned):
                return [segment.strip(' -') for segment in re.split(separator, cleaned) if segment.strip(' -')]

        if cleaned.count(',') >= 2:
            return [segment.strip(' -') for segment in cleaned.split(',') if segment.strip(' -')]
        return [cleaned]

    def _split_book_entries(self, text: str) -> list[str]:
        cleaned = normalize_whitespace(text).strip(':- ')
        if not cleaned:
            return []

        cleaned = cleaned.replace('•', ' ')
        numbered = [segment.strip() for segment in re.split(r'(?=\b\d+\.\s*)', cleaned) if segment.strip()]
        if len(numbered) > 1:
            entries: list[str] = []
            for segment in numbered:
                entry = re.sub(r'^\d+\.\s*', '', segment).strip(' ;')
                if entry:
                    entries.append(entry)
            return entries

        if cleaned.lower().count(' by ') > 1 and ', ' in cleaned:
            split_entries = [segment.strip(' ;') for segment in re.split(r',\s*(?=[A-Z])', cleaned) if segment.strip(' ;')]
            if len(split_entries) > 1:
                return split_entries

        return [re.sub(r'^\d+\.\s*', '', cleaned).strip(' ;')]

    def _clean_book_entries(self, values: list[str]) -> list[str]:
        cleaned_values: list[str] = []
        for value in values:
            cleaned = normalize_whitespace(re.sub(r'^\d+\.\s*', '', value)).strip(' ;')
            if cleaned and cleaned not in cleaned_values:
                cleaned_values.append(cleaned)
        return cleaned_values

    def _append_topics(self, target: list[str], topics: list[str]) -> None:
        for topic in topics:
            if topic and topic not in target:
                target.append(topic)

    def _normalize_unit(self, value: str) -> str:
        cleaned = normalize_whitespace(value).upper().replace('UNIT', '').strip()
        if not cleaned:
            return ''
        return f'Unit {cleaned}'

    def _looks_like_metadata(self, text: str) -> bool:
        cleaned = normalize_whitespace(text).lower()
        return cleaned.startswith(
            (
                'text books',
                'textbooks',
                'reference books',
                'reference book',
                'reference:',
                'prerequisites',
                'l t p c',
                'sub code',
                'page ',
                'pr25 ',
                'common syllabus',
                'b.tech.',
                'b.tech ',
            )
        )

    def _is_new_book_line(self, text: str) -> bool:
        cleaned = normalize_whitespace(text).strip()
        if not cleaned:
            return False
        if re.match(r'^\d+[\.\)]\s', cleaned):
            return True
        if re.match(r'^[•\-]\s', cleaned):
            return True
        return bool(re.match(r'^[A-Z][a-z]+[\.,]?\s', cleaned))

    def _is_books_section_break(self, text: str) -> bool:
        cleaned = normalize_whitespace(text).lower()
        if not cleaned:
            return True
        if self.unit_pattern.match(cleaned):
            return True
        if cleaned.startswith(('course objectives', 'course outcomes', 'list of experiments', 'list of experiment', 'practice sessions', 'note:', 'note ', 'prerequisites', 'page ', 'sub code')):
            return True
        return bool(self.course_code_pattern.search(text))

    def _is_experiment_heading(self, text: str) -> bool:
        cleaned = normalize_whitespace(text).lower()
        return cleaned.startswith(('list of experiments', 'list of experiment', 'practice sessions'))

    def _is_experiment_section_break(self, text: str) -> bool:
        cleaned = normalize_whitespace(text)
        lowered = cleaned.lower()
        if not cleaned:
            return True
        if self.unit_pattern.match(cleaned):
            return True
        if self.course_code_pattern.match(cleaned):
            return True
        return lowered.startswith(('text books', 'textbooks', 'reference books', 'reference book', 'reference:', 'course objectives', 'course outcomes'))

    def _consume_experiment_line(self, text: str, topics: list[str], pending: str) -> str:
        cleaned = normalize_whitespace(text)
        if not cleaned or self._looks_like_metadata(cleaned) or cleaned.lower().startswith('note'):
            return pending

        new_item_match = re.match(r'^(\d+|[a-zA-Z])[.)]\s*(.+)$', cleaned)
        if new_item_match:
            pending = self._flush_pending_experiment(pending, topics)
            return normalize_whitespace(new_item_match.group(2))

        if pending:
            return normalize_whitespace(f'{pending} {cleaned}')
        return cleaned

    def _flush_pending_experiment(self, pending: str, topics: list[str]) -> str:
        cleaned = normalize_whitespace(pending)
        if cleaned and cleaned not in topics:
            topics.append(cleaned)
        return ''

    def _extract_experiment_entries(self, raw_text: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        in_section = False
        current_heading = ''
        heading_index = 0
        pending_no = ''
        pending_topic = ''

        def flush_pending() -> None:
            nonlocal pending_no, pending_topic
            topic = normalize_whitespace(pending_topic)
            if topic:
                entries.append({'exp_no': normalize_whitespace(pending_no), 'topic': topic})
            pending_no = ''
            pending_topic = ''

        for raw_line in raw_text.splitlines():
            line = normalize_whitespace(raw_line)
            if not line:
                continue

            lower_line = line.lower()
            if self._is_experiment_heading(line):
                flush_pending()
                in_section = True
                current_heading = ''
                heading_index = 0
                continue

            if not in_section:
                continue

            if self._is_experiment_section_break(line):
                flush_pending()
                break
            if self._looks_like_metadata(line) or lower_line.startswith('note'):
                continue

            if self._is_experiment_group_heading(line):
                flush_pending()
                current_heading = line.rstrip(':')
                heading_index += 1
                continue

            task_match = self.task_pattern.match(line)
            if task_match:
                flush_pending()
                pending_no = f"Task {task_match.group(1)}"
                pending_topic = normalize_whitespace(task_match.group(2))
                continue

            letter_match = re.match(r'^([a-z])[.)]\s*(.+)$', line, flags=re.IGNORECASE)
            if letter_match:
                letter_topic = self._prefix_heading(current_heading, letter_match.group(2))
                if pending_topic:
                    pending_topic = normalize_whitespace(f'{pending_topic} {letter_topic}')
                    continue
                flush_pending()
                prefix = f"{heading_index}.{letter_match.group(1).lower()}" if heading_index else letter_match.group(1).lower()
                pending_no = prefix
                pending_topic = letter_topic
                continue

            number_match = re.match(r'^(\d+)\.\s*(.+)$', line)
            if number_match:
                flush_pending()
                pending_no = number_match.group(1)
                pending_topic = normalize_whitespace(number_match.group(2))
                continue

            if pending_topic:
                pending_topic = normalize_whitespace(f'{pending_topic} {line}')

        flush_pending()
        return entries

    def _is_experiment_group_heading(self, text: str) -> bool:
        cleaned = normalize_whitespace(text)
        if not cleaned or self._looks_like_metadata(cleaned):
            return False
        if self.task_pattern.match(cleaned) or re.match(r'^(\d+|[a-z])[.)]', cleaned, flags=re.IGNORECASE):
            return False
        return cleaned.endswith(':') and len(cleaned.split()) <= 8

    def _prefix_heading(self, heading: str, text: str) -> str:
        heading_text = normalize_whitespace(heading).rstrip(':')
        body = normalize_whitespace(text)
        if not heading_text:
            return body
        if body.lower().startswith(heading_text.lower()):
            return body
        return f'{heading_text}: {body}'

    def _capture_outline_heading(self, line: str, current_heading: str) -> str:
        cleaned = normalize_whitespace(line)
        if self._is_outline_heading_candidate(cleaned):
            return cleaned
        return current_heading

    def _is_outline_heading_candidate(self, text: str) -> bool:
        cleaned = normalize_whitespace(text)
        lowered = cleaned.lower()
        if not cleaned or self._looks_like_metadata(cleaned):
            return False
        if self.task_pattern.match(cleaned):
            return False
        if lowered in {'excel', 'powerpoint', 'pc hardware', 'internet & world wide web', 'latex and word'}:
            return True
        if ':' in cleaned:
            return False
        if len(cleaned.split()) > 6:
            return False
        if not any(character.isalpha() for character in cleaned):
            return False
        return cleaned.isupper() or cleaned == cleaned.title()

    def _starts_topic_block(self, text: str) -> bool:
        cleaned = normalize_whitespace(text)
        return bool(
            self.unit_pattern.match(cleaned)
            or self._is_experiment_heading(cleaned)
            or self.task_pattern.match(cleaned)
            or self._is_outline_heading_candidate(cleaned)
        )

    def _extract_outline_topic(self, line: str, current_heading: str) -> str:
        cleaned = normalize_whitespace(line)
        if not cleaned or self._looks_like_metadata(cleaned):
            return ''

        task_match = self.task_pattern.match(cleaned)
        if task_match:
            task_body = normalize_whitespace(task_match.group(2))
            if current_heading:
                return f'{current_heading}: {task_body}'
            return task_body

        numbered_match = re.match(r'^\d+[.)]\s*(.+)$', cleaned)
        if numbered_match and len(cleaned) < 180:
            return numbered_match.group(1)
        return ''

    def _infer_course_title(self, raw_text: str, fallback_name: str) -> str:
        lines = [normalize_whitespace(line) for line in raw_text.splitlines() if normalize_whitespace(line)]

        for cleaned in lines:
            if ':' not in cleaned:
                continue
            key, value = cleaned.split(':', 1)
            key_lower = key.strip().lower()
            if key_lower in {'course objectives', 'course outcomes'}:
                continue
            if key_lower.endswith('es') or key_lower.endswith('code'):
                return value.strip() or fallback_name.replace('_', ' ').title()

        for cleaned in lines:
            if 'syllabus' in cleaned.lower() or 'engineering college' in cleaned.lower():
                continue
            if len(cleaned) <= 80:
                return cleaned
        return fallback_name.replace('_', ' ').title()

    def _unique_preserve_order(self, values: list[str]) -> list[str]:
        ordered: list[str] = []
        for value in values:
            cleaned = normalize_whitespace(value)
            if cleaned and cleaned not in ordered:
                ordered.append(cleaned)
        return ordered

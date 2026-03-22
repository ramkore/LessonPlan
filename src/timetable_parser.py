"""Timetable parsing and subject period extraction from class or faculty schedules."""
from __future__ import annotations

import re

import pandas as pd

from .logger import get_logger
from .utils import ParsedDocument, ProcessingError, normalize_whitespace

logger = get_logger(__name__)


class TimeTableParser:
    weekdays = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday')
    day_aliases = {
        'mon': 'Monday',
        'monday': 'Monday',
        'tue': 'Tuesday',
        'tues': 'Tuesday',
        'tuesday': 'Tuesday',
        'wed': 'Wednesday',
        'wednesday': 'Wednesday',
        'thu': 'Thursday',
        'thur': 'Thursday',
        'thurs': 'Thursday',
        'thursday': 'Thursday',
        'fri': 'Friday',
        'friday': 'Friday',
        'sat': 'Saturday',
        'saturday': 'Saturday',
        'sun': 'Sunday',
        'sunday': 'Sunday',
    }
    branch_aliases = {
        'CE': 'CE',
        'CIVIL': 'CE',
        'CIVILENGINEERING': 'CE',
        'EEE': 'EEE',
        'ELECTRICAL': 'EEE',
        'ELECTRICALANDELECTRONICSENGINEERING': 'EEE',
        'ECE': 'ECE',
        'ELECTRONICS': 'ECE',
        'ELECTRONICSANDCOMMUNICATIONENGINEERING': 'ECE',
        'EC': 'ECE',
        'CSE': 'CSE',
        'COMPUTERSCIENCEENGINEERING': 'CSE',
    }
    non_teaching_entries = {'', 'free', 'lunch', 'break', 'nil', 'na', 'n/a', '-', '--'}

    def extract_subject_periods(
        self,
        document: ParsedDocument,
        subject_name: str,
        faculty_name: str = '',
        branch_name: str = '',
    ) -> pd.DataFrame:
        if not subject_name.strip():
            raise ProcessingError('Subject name is required to process the timetable.')

        candidate_tables = self._select_relevant_tables(document.tables, subject_name, faculty_name)
        faculty_mode = self._is_faculty_subject_timetable(document, subject_name, faculty_name, candidate_tables)
        matches: list[dict[str, object]] = []

        for table in candidate_tables:
            matches.extend(self._extract_from_table(table, subject_name, faculty_mode))

        if not matches:
            matches.extend(self._extract_from_text(document.raw_text, subject_name, faculty_mode))

        if not matches and not faculty_mode:
            for table in candidate_tables:
                if self._looks_like_individual_faculty_grid(table):
                    matches.extend(self._extract_from_table(table, subject_name, faculty_mode=True))
            if not matches:
                matches.extend(self._extract_from_text(document.raw_text, subject_name, faculty_mode=True))
                faculty_mode = True

        periods = pd.DataFrame(matches)
        if periods.empty:
            raise ProcessingError(
                f"No teaching periods were found for '{subject_name}'. For individual faculty bundles, provide the faculty name so the parser can select the correct table."
            )

        periods = self._apply_branch_filter(periods, branch_name, faculty_mode)
        if periods.empty:
            raise ProcessingError(
                f"No teaching periods were found for the selected branch '{branch_name}'. Check the branch value against the individual timetable entries."
            )

        # For lab subjects, filter to only include entries marked as 'LAB'
        if 'lab' in subject_name.lower():
            lab_periods = periods[
                periods['entry'].str.lower().str.contains('lab', na=False)
            ].copy()
            if not lab_periods.empty:
                periods = lab_periods
            # If no explicit 'LAB' entries found, use all periods (fallback)

        dedupe_columns = ['day', 'period']
        if 'branch' in periods.columns:
            dedupe_columns.append('branch')
        sort_columns = ['day_order', 'period_order']
        if 'branch' in periods.columns:
            sort_columns.append('branch')
        periods = periods.drop_duplicates(subset=dedupe_columns).sort_values(sort_columns)

        result_columns = ['day', 'period', 'entry']
        if 'branch' in periods.columns:
            result_columns.append('branch')
        if 'time_slot' in periods.columns:
            result_columns.append('time_slot')
        return periods.reset_index(drop=True)[result_columns]

    def _select_relevant_tables(
        self,
        tables: list[pd.DataFrame],
        subject_name: str,
        faculty_name: str,
    ) -> list[pd.DataFrame]:
        if not tables:
            return []

        scored_tables: list[tuple[int, int, pd.DataFrame]] = []
        for index, table in enumerate(tables):
            score = self._table_context_score(table.attrs.get('context_text', ''), subject_name, faculty_name)
            scored_tables.append((score, index, table))

        if faculty_name.strip():
            faculty_hits = [item for item in scored_tables if item[0] >= 100]
            if faculty_hits:
                best_score = max(item[0] for item in faculty_hits)
                return [table for score, _index, table in faculty_hits if score == best_score]

        subject_hits = [item for item in scored_tables if item[0] > 0]
        if subject_hits:
            best_score = max(item[0] for item in subject_hits)
            best_tables = [table for score, _index, table in subject_hits if score == best_score]
            if best_tables:
                return best_tables

        return tables

    def _table_context_score(self, context_text: str, subject_name: str, faculty_name: str) -> int:
        context = normalize_whitespace(context_text)
        if not context:
            return 0

        score = 0
        if faculty_name.strip() and self._name_matches(context, faculty_name):
            score += 100
        if subject_name.strip() and self._subject_matches(context, subject_name):
            score += 20
        return score

    def _extract_from_table(self, table: pd.DataFrame, subject_name: str, faculty_mode: bool) -> list[dict[str, object]]:
        if table.empty:
            return []

        frame = table.copy()
        frame.columns = [normalize_whitespace(column) for column in frame.columns]
        day_column = self._find_day_column(frame.columns)
        if not day_column:
            return []

        teaching_columns = self._teaching_columns(frame, day_column)
        if not teaching_columns:
            return []

        matches: list[dict[str, object]] = []
        for _, row in frame.iterrows():
            day_value = self._normalize_day(row.get(day_column))
            if not day_value or day_value == 'Sunday':
                continue
            for teaching_index, period_column in enumerate(teaching_columns, start=1):
                entry = normalize_whitespace(row.get(period_column))
                if not self._should_include_entry(entry, subject_name, faculty_mode):
                    continue
                matches.append(
                    {
                        'day': day_value,
                        'period': self._normalize_period(period_column, teaching_index),
                        'entry': entry,
                        'time_slot': self._extract_time_slot(period_column),
                        'day_order': self._day_order(day_value),
                        'period_order': teaching_index,
                    }
                )
        return matches

    def _extract_from_text(self, text: str, subject_name: str, faculty_mode: bool) -> list[dict[str, object]]:
        matches: list[dict[str, object]] = []
        for raw_line in text.splitlines():
            line = normalize_whitespace(raw_line)
            if not line:
                continue

            day_token = line.split(' ', 1)[0].rstrip(':')
            day_value = self._normalize_day(day_token)
            if not day_value or day_value == 'Sunday':
                continue

            tokens = [segment.strip() for segment in re.split(r'\t|\s{2,}', line) if segment.strip()]
            if len(tokens) <= 1:
                continue

            teaching_index = 0
            for token in tokens[1:]:
                if self._is_lunch_label(token):
                    continue
                teaching_index += 1
                if not self._should_include_entry(token, subject_name, faculty_mode):
                    continue
                matches.append(
                    {
                        'day': day_value,
                        'period': f'P{teaching_index}',
                        'entry': token,
                        'time_slot': '',
                        'day_order': self._day_order(day_value),
                        'period_order': teaching_index,
                    }
                )
        return matches

    def _apply_branch_filter(self, periods: pd.DataFrame, branch_name: str, faculty_mode: bool) -> pd.DataFrame:
        requested_branches = self._parse_requested_branches(branch_name)
        rows: list[dict[str, object]] = []

        for row in periods.to_dict('records'):
            if faculty_mode:
                branches = self._match_entry_branches(row.get('entry', ''), requested_branches)
                if requested_branches and not branches:
                    continue
                if not branches:
                    branches = requested_branches or self._derive_entry_branches(row.get('entry', ''))
            else:
                if len(requested_branches) == 1:
                    branches = requested_branches
                elif len(requested_branches) > 1:
                    branches = [' / '.join(requested_branches)]
                else:
                    branches = []

            if branches:
                for branch in branches:
                    expanded = dict(row)
                    expanded['branch'] = branch
                    rows.append(expanded)
            else:
                rows.append(dict(row))

        return pd.DataFrame(rows)

    def _parse_requested_branches(self, branch_name: str) -> list[str]:
        cleaned = normalize_whitespace(branch_name)
        if not cleaned:
            return []

        normalized = cleaned.upper().replace('&', '/').replace(',', '/').replace('+', '/')
        normalized = re.sub(r'AND', '/', normalized, flags=re.IGNORECASE)
        parts = [part.strip() for part in normalized.split('/') if part.strip()]

        branches: list[str] = []
        for part in parts:
            canonical = self._canonical_branch(part)
            if canonical and canonical not in branches:
                branches.append(canonical)
        return branches

    def _match_entry_branches(self, entry: str, requested_branches: list[str]) -> list[str]:
        if not requested_branches:
            return []

        tokens = self._extract_entry_tokens(entry)
        matches: list[str] = []
        for branch in requested_branches:
            if any(self._canonical_branch(token) == branch for token in tokens):
                matches.append(branch)
        return matches

    def _derive_entry_branches(self, entry: str) -> list[str]:
        tokens = self._extract_entry_tokens(entry)
        branches: list[str] = []
        for token in tokens:
            canonical = self._canonical_branch(token)
            if not canonical or canonical in {'LAB', 'THEORY'}:
                continue
            if canonical not in branches:
                branches.append(canonical)
        return branches[:3]

    def _extract_entry_tokens(self, entry: str) -> list[str]:
        cleaned = normalize_whitespace(entry).upper().replace('L A B', 'LAB')
        if ' - ' in cleaned:
            cleaned = cleaned.split(' - ', 1)[0]
        cleaned = cleaned.replace('&', '/').replace(',', '/').replace('+', '/')
        cleaned = re.sub(r'\bAND\b', '/', cleaned)
        return re.findall(r'[A-Z0-9]+(?:-[A-Z0-9]+)?', cleaned)

    def _canonical_branch(self, value: str) -> str:
        cleaned = normalize_whitespace(value).upper().strip('/- ')
        if not cleaned:
            return ''
        compact = re.sub(r'[^A-Z0-9]+', '', cleaned)
        if compact in self.branch_aliases:
            return self.branch_aliases[compact]
        if cleaned.endswith(' LAB'):
            return self._canonical_branch(cleaned[:-4])
        if compact.endswith('LAB'):
            return self._canonical_branch(compact[:-3])
        if '-' in cleaned:
            prefix, suffix = cleaned.split('-', 1)
            prefix_branch = self._canonical_branch(prefix)
            suffix_compact = re.sub(r'[^A-Z0-9]+', '', suffix)
            if prefix_branch in self.branch_aliases.values() and 0 < len(suffix_compact) <= 3:
                return prefix_branch
        for branch_code in ('CSE', 'ECE', 'EEE', 'CE'):
            remainder = compact[len(branch_code) :]
            if compact.startswith(branch_code) and 0 < len(remainder) <= 3:
                return branch_code
        if compact.endswith('EC') and compact.count('C') >= 1 and compact not in {'EC', 'ECE'}:
            prefix = compact[:-2]
            if prefix:
                return self._canonical_branch(prefix)
        return cleaned

    def _find_day_column(self, columns) -> str | None:
        for column in columns:
            lowered = normalize_whitespace(column).lower()
            if lowered in {'day', 'days', 'day/period', 'day / period'} or 'day' in lowered:
                return column

        if len(columns) > 1:
            return columns[0]
        return None

    def _teaching_columns(self, frame: pd.DataFrame, day_column: str) -> list[str]:
        teaching_columns: list[str] = []
        for column in frame.columns:
            if column == day_column:
                continue
            if self._column_is_lunch(frame, column):
                continue
            teaching_columns.append(column)
        return teaching_columns

    def _column_is_lunch(self, frame: pd.DataFrame, column: str) -> bool:
        if self._is_lunch_label(column):
            return True

        values = [normalize_whitespace(value) for value in frame[column].tolist()]
        non_empty_values = [value for value in values if value]
        if not non_empty_values:
            return False

        lunch_values = [value for value in non_empty_values if self._is_lunch_label(value)]
        return len(lunch_values) >= max(2, len(non_empty_values) // 2)

    def _normalize_day(self, value) -> str | None:
        candidate = normalize_whitespace(value).lower().strip('.:/- ')
        if not candidate:
            return None
        return self.day_aliases.get(candidate)

    def _normalize_period(self, label: str, fallback_index: int) -> str:
        cleaned = normalize_whitespace(label)
        explicit = re.search(r'\bp\s*([0-9]+)\b', cleaned, flags=re.IGNORECASE)
        if explicit:
            return f"P{explicit.group(1)}"
        if self._extract_time_slot(cleaned):
            return f'P{fallback_index}'
        numeric = re.fullmatch(r'[0-9]+', cleaned)
        if numeric:
            return f"P{numeric.group(0)}"
        return f'P{fallback_index}'

    def _extract_time_slot(self, label: str) -> str:
        cleaned = normalize_whitespace(label)
        if re.search(r'\b(am|pm)\b', cleaned, flags=re.IGNORECASE) or re.search(r'\d{1,2}:\d{2}', cleaned):
            return cleaned
        return ''

    def _should_include_entry(self, entry: str, subject_name: str, faculty_mode: bool) -> bool:
        if self._is_non_teaching_entry(entry):
            return False
        if self._subject_matches(entry, subject_name):
            return True
        if not faculty_mode:
            return False
        return self._entry_matches_subject_type(entry, subject_name)

    def _entry_matches_subject_type(self, entry: str, subject_name: str) -> bool:
        entry_is_lab = self._is_lab_entry(entry)
        subject_is_lab = self._is_lab_subject(subject_name)
        if subject_is_lab:
            return entry_is_lab
        return not entry_is_lab

    def _is_lab_entry(self, entry: str) -> bool:
        cleaned = normalize_whitespace(entry).lower()
        return 'lab' in cleaned or 'laboratory' in cleaned

    def _is_lab_subject(self, subject_name: str) -> bool:
        cleaned = normalize_whitespace(subject_name).lower()
        return any(token in cleaned for token in (' lab', 'laboratory', 'practical')) or cleaned.endswith('lab')

    def _is_non_teaching_entry(self, value: str) -> bool:
        cleaned = normalize_whitespace(value).lower().strip()
        return cleaned in self.non_teaching_entries or self._is_lunch_label(cleaned)

    def _is_lunch_label(self, value: str) -> bool:
        cleaned = normalize_whitespace(value).lower().replace(' ', '')
        return 'lunch' in cleaned

    def _subject_matches(self, value: str, subject_name: str) -> bool:
        entry = normalize_whitespace(value).lower()
        subject = normalize_whitespace(subject_name).lower()
        if not entry or not subject:
            return False

        normalized_entry = re.sub(r'[^a-z0-9]+', '', entry)
        normalized_subject = re.sub(r'[^a-z0-9]+', '', subject)
        if normalized_subject and normalized_subject in normalized_entry:
            return True

        entry_tokens = {token for token in re.split(r'[^a-z0-9]+', entry) if token}
        subject_tokens = [token for token in re.split(r'[^a-z0-9]+', subject) if len(token) > 1]
        if subject_tokens and all(token in entry for token in subject_tokens):
            return True

        for alias in self._subject_aliases(subject_name):
            if len(alias) >= 3 and alias in normalized_entry:
                return True
            if alias in entry_tokens:
                return True
        return False

    def _subject_aliases(self, subject_name: str) -> set[str]:
        cleaned = normalize_whitespace(subject_name).lower()
        words = [re.sub(r'[^a-z0-9]+', '', token) for token in cleaned.split()]
        words = [token for token in words if token]
        if not words:
            return set()

        stop_words = {'and', 'of', 'the', 'for', 'to', 'in', 'with', 'on', 'a', 'an'}
        significant = [token for token in words if token not in stop_words]
        aliases: set[str] = set()

        if len(words) > 1:
            aliases.add(''.join(token[0] for token in words))
        if len(significant) > 1:
            aliases.add(''.join(token[0] for token in significant))

        joined = ''.join(significant)
        if joined:
            aliases.add(joined)

        custom_aliases = {
            'programmingproblemsolving': 'pps',
            'datastructures': 'ds',
            'pythonprogramming': 'python',
            'pythonprogramminglaboratory': 'pythonlab',
            'electronicdevicescircuits': 'edc',
            'basicelectricalengineering': 'bee',
        }
        for key, alias in custom_aliases.items():
            if key in joined:
                aliases.add(alias)

        return {alias for alias in aliases if alias}

    def _name_matches(self, context_text: str, faculty_name: str) -> bool:
        context = normalize_whitespace(context_text).lower()
        faculty = normalize_whitespace(faculty_name).lower()
        if not context or not faculty:
            return False

        normalized_context = re.sub(r'[^a-z0-9]+', '', context)
        normalized_faculty = re.sub(r'[^a-z0-9]+', '', faculty)
        if normalized_faculty and normalized_faculty in normalized_context:
            return True

        faculty_tokens = [token for token in re.split(r'[^a-z0-9]+', faculty) if len(token) > 1]
        return bool(faculty_tokens) and all(token in context for token in faculty_tokens)

    def _is_faculty_subject_timetable(
        self,
        document: ParsedDocument,
        subject_name: str,
        faculty_name: str,
        tables: list[pd.DataFrame],
    ) -> bool:
        if faculty_name.strip() and any(table.attrs.get('context_text') for table in tables):
            return True

        raw_text = normalize_whitespace(document.raw_text).lower()
        subject = normalize_whitespace(subject_name).lower()
        if subject and subject in raw_text and 'name of the faculty' in raw_text:
            return True
        return bool(faculty_name.strip()) and self._name_matches(raw_text, faculty_name)

    def _looks_like_individual_faculty_grid(self, table: pd.DataFrame) -> bool:
        if table.empty or len(table.columns) < 3:
            return False

        frame = table.copy()
        frame.columns = [normalize_whitespace(column) for column in frame.columns]
        day_column = self._find_day_column(frame.columns)
        if not day_column:
            return False

        day_hits = 0
        code_like_hits = 0
        teaching_columns = self._teaching_columns(frame, day_column)
        for _, row in frame.iterrows():
            if self._normalize_day(row.get(day_column)):
                day_hits += 1
            for column in teaching_columns:
                entry = normalize_whitespace(row.get(column))
                if self._is_non_teaching_entry(entry):
                    continue
                if re.fullmatch(r'[A-Za-z0-9/&\- ]{2,30}', entry):
                    code_like_hits += 1

        return day_hits >= 4 and code_like_hits >= 3

    def _day_order(self, day_value: str) -> int:
        try:
            return self.weekdays.index(day_value)
        except ValueError:
            return 999

"""Academic calendar and holiday processing for teaching day extraction."""
from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher

import pandas as pd

from .logger import get_logger
from .utils import (
    ParsedDocument,
    ProcessingError,
    coerce_date,
    expand_date_range,
    extract_dates_from_text,
    month_label,
    normalize_whitespace,
)

logger = get_logger(__name__)


class CalendarProcessor:
    description_aliases = ('description', 'event', 'activity', 'occasion', 'details', 'particulars', 'title')
    start_aliases = ('from_date', 'start_date', 'from', 'start', 'date')
    end_aliases = ('to_date', 'end_date', 'to', 'end')
    holiday_aliases = ('date', 'holiday_date')
    teaching_keywords = ('instruction', 'instructions', 'class work', 'classwork', 'teaching', 'spell')
    exclusion_keywords = ('exam', 'mid term', 'mid-term', 'vacation', 'holiday', 'break', 'internals', 'practical', 'summer', 'preparation')
    header_tokens = ('description', 'duration', 'from', 'to', 'date', 'occasion', 'day', 's.no', 'sno', 'serial')
    weekday_tokens = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')

    def extract_calendar_events(self, document: ParsedDocument) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for table in document.tables:
            rows.extend(self._records_from_table(table))
        if not rows:
            rows.extend(self._records_from_text(document.raw_text))

        frame = pd.DataFrame(rows)
        if frame.empty:
            raise ProcessingError('Unable to extract academic calendar data.')

        frame = frame.dropna(subset=['from_date', 'to_date']).copy()
        if frame.empty:
            raise ProcessingError('Academic calendar does not contain readable date ranges.')

        frame['description'] = frame['description'].fillna('').astype(str)
        frame = frame.sort_values(['from_date', 'to_date', 'description']).reset_index(drop=True)
        return frame

    def extract_holidays(self, document: ParsedDocument) -> pd.DataFrame:
        rows: list[dict[str, object]] = []

        for table in document.tables:
            rows.extend(self._holiday_rows_from_table(table))

        if not rows:
            for line in document.raw_text.splitlines():
                cleaned = line.strip()
                if not cleaned:
                    continue
                dates = extract_dates_from_text(cleaned)
                if not dates:
                    continue
                rows.append({'occasion': cleaned, 'date': dates[0]})

        holidays = pd.DataFrame(rows)
        if holidays.empty:
            return pd.DataFrame(columns=['occasion', 'date'])

        holidays = holidays.dropna(subset=['date']).copy()
        holidays['occasion'] = holidays['occasion'].fillna('').astype(str)
        holidays['date'] = pd.to_datetime(holidays['date'])
        holidays = holidays.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
        return holidays

    def build_teaching_days(self, calendar_document: ParsedDocument, holiday_document: ParsedDocument) -> pd.DataFrame:
        calendar_events = self.extract_calendar_events(calendar_document)
        holidays = self.extract_holidays(holiday_document)
        teaching_periods = self._derive_teaching_periods(calendar_events)
        blocked_dates = self._derive_blocked_dates(calendar_events, holidays)
        teaching_start = teaching_periods['from_date'].min()

        rows: list[dict[str, object]] = []
        seen_dates: set[date] = set()
        for spell_index, period in enumerate(teaching_periods.itertuples(index=False), start=1):
            for current_day in expand_date_range(period.from_date, period.to_date):
                if current_day in seen_dates:
                    continue
                if current_day.strftime('%A') == 'Sunday':
                    continue
                if current_day in blocked_dates:
                    continue
                rows.append(
                    {
                        'date': pd.Timestamp(current_day),
                        'day': current_day.strftime('%A'),
                        'week': 0,
                        'month': month_label(current_day),
                        'spell': spell_index,
                    }
                )
                seen_dates.add(current_day)

        rows.sort(key=lambda r: r['date'])
        week_num = 0
        current_bucket: int | None = None
        for row in rows:
            bucket = (row['date'].date() - teaching_start).days // 7
            if bucket != current_bucket:
                week_num += 1
                current_bucket = bucket
            row['week'] = week_num

        teaching_days = pd.DataFrame(rows)
        if teaching_days.empty:
            raise ProcessingError('No valid teaching days were generated after removing exams, vacations, holidays, and Sundays.')
        return teaching_days.sort_values('date').reset_index(drop=True)

    def build_teaching_days_from_frames(self, calendar_events: pd.DataFrame, holidays: pd.DataFrame) -> pd.DataFrame:
        """Build teaching days from pre-structured DataFrames (for web API use)."""
        teaching_periods = self._derive_teaching_periods(calendar_events)
        blocked_dates = self._derive_blocked_dates(calendar_events, holidays)
        teaching_start = teaching_periods['from_date'].min()

        rows: list[dict[str, object]] = []
        seen_dates: set[date] = set()
        for spell_index, period in enumerate(teaching_periods.itertuples(index=False), start=1):
            for current_day in expand_date_range(period.from_date, period.to_date):
                if current_day in seen_dates:
                    continue
                if current_day.strftime('%A') == 'Sunday':
                    continue
                if current_day in blocked_dates:
                    continue
                rows.append(
                    {
                        'date': pd.Timestamp(current_day),
                        'day': current_day.strftime('%A'),
                        'week': 0,
                        'month': month_label(current_day),
                        'spell': spell_index,
                    }
                )
                seen_dates.add(current_day)

        rows.sort(key=lambda r: r['date'])
        week_num = 0
        current_bucket: int | None = None
        for row in rows:
            bucket = (row['date'].date() - teaching_start).days // 7
            if bucket != current_bucket:
                week_num += 1
                current_bucket = bucket
            row['week'] = week_num

        teaching_days = pd.DataFrame(rows)
        if teaching_days.empty:
            raise ProcessingError('No valid teaching days were generated after removing exams, vacations, holidays, and Sundays.')
        return teaching_days.sort_values('date').reset_index(drop=True)

    def _records_from_table(self, table: pd.DataFrame) -> list[dict[str, object]]:
        cleaned = table.copy()
        cleaned.columns = [str(column).strip().lower().replace(' ', '_') for column in cleaned.columns]
        desc_col = self._find_column(cleaned.columns, self.description_aliases)
        start_col = self._find_column(cleaned.columns, self.start_aliases)
        end_col = self._find_column(cleaned.columns, self.end_aliases)

        if desc_col and start_col:
            rows = self._records_from_table_by_headers(cleaned, desc_col, start_col, end_col)
            if rows:
                return rows

        return self._records_from_table_by_rows(cleaned)

    def _records_from_table_by_headers(self, table: pd.DataFrame, desc_col: str, start_col: str, end_col: str | None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for _, row in table.iterrows():
            values = [normalize_whitespace(row.get(column, '')) for column in table.columns]
            if self._is_header_like_row(values):
                continue

            description = normalize_whitespace(row.get(desc_col, ''))
            from_date = coerce_date(row.get(start_col))
            to_date = coerce_date(row.get(end_col)) if end_col else from_date
            if description and from_date:
                rows.append(
                    {
                        'description': description,
                        'from_date': from_date,
                        'to_date': to_date or from_date,
                    }
                )
        return rows

    def _records_from_table_by_rows(self, table: pd.DataFrame) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for _, row in table.iterrows():
            values = [normalize_whitespace(row.get(column, '')) for column in table.columns]
            if self._is_header_like_row(values):
                continue

            row_dates = self._extract_row_dates(values)
            description = self._extract_calendar_description_from_cells(values)
            if description and row_dates:
                rows.append(
                    {
                        'description': description,
                        'from_date': row_dates[0],
                        'to_date': row_dates[1] if len(row_dates) > 1 else row_dates[0],
                    }
                )
        return rows

    def _records_from_text(self, text: str) -> list[dict[str, object]]:
        lines = [normalize_whitespace(line) for line in text.splitlines() if normalize_whitespace(line)]
        rows: list[dict[str, object]] = []
        pending_description = ''
        index = 0

        while index < len(lines):
            line = lines[index]
            combined = f'{pending_description} {line}'.strip() if pending_description else line
            dates = extract_dates_from_text(combined)

            if not dates:
                pending_description = combined
                index += 1
                continue

            if len(dates) == 1 and index + 1 < len(lines):
                next_line = lines[index + 1]
                next_dates = extract_dates_from_text(next_line)
                if next_dates and not self._looks_like_new_event(next_line):
                    combined = f'{combined} {next_line}'.strip()
                    dates = extract_dates_from_text(combined)
                    index += 1

            description = self._clean_calendar_description(combined)
            rows.append(
                {
                    'description': description or 'Academic Event',
                    'from_date': dates[0],
                    'to_date': dates[1] if len(dates) > 1 else dates[0],
                }
            )
            pending_description = ''
            index += 1

        return rows

    def _clean_calendar_description(self, value: str) -> str:
        description = normalize_whitespace(value)
        description = re.sub(r'\b\d+\b\s*', '', description, count=1)
        for marker in re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', description):
            description = description.replace(marker, '')
        description = re.sub(r'\([^)]*weeks?[^)]*\)', ' ', description, flags=re.IGNORECASE)
        description = re.sub(r'\bto\b', ' ', description, flags=re.IGNORECASE)
        description = re.sub(r'[-–]+', ' ', description)
        description = re.sub(r'\s+', ' ', description).strip(' :-')
        return description

    def _looks_like_new_event(self, line: str) -> bool:
        cleaned = normalize_whitespace(line)
        return bool(re.match(r'^\d+\s+', cleaned)) or bool(re.match(r'^(commencement|spell|mid term|summer|preparation|end semester)', cleaned, flags=re.IGNORECASE))

    def _holiday_rows_from_table(self, table: pd.DataFrame) -> list[dict[str, object]]:
        cleaned = table.copy()
        cleaned.columns = [str(column).strip().lower().replace(' ', '_') for column in cleaned.columns]
        date_col = self._find_column(cleaned.columns, self.holiday_aliases)
        occasion_col = self._find_column(cleaned.columns, self.description_aliases)

        if date_col:
            rows = self._holiday_rows_by_headers(cleaned, date_col, occasion_col)
            if rows:
                return rows

        return self._holiday_rows_by_rows(cleaned)

    def _holiday_rows_by_headers(self, table: pd.DataFrame, date_col: str, occasion_col: str | None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for _, row in table.iterrows():
            values = [normalize_whitespace(row.get(column, '')) for column in table.columns]
            if self._is_header_like_row(values):
                continue

            holiday_date = coerce_date(row.get(date_col))
            occasion = normalize_whitespace(row.get(occasion_col, 'Holiday')) if occasion_col else 'Holiday'
            if holiday_date:
                rows.append({'occasion': occasion or 'Holiday', 'date': holiday_date})
        return rows

    def _holiday_rows_by_rows(self, table: pd.DataFrame) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for _, row in table.iterrows():
            values = [normalize_whitespace(row.get(column, '')) for column in table.columns]
            if self._is_header_like_row(values):
                continue

            row_dates = self._extract_row_dates(values)
            occasion = self._extract_holiday_occasion_from_cells(values)
            if row_dates:
                rows.append({'occasion': occasion or 'Holiday', 'date': row_dates[0]})
        return rows

    def _extract_row_dates(self, values: list[str]) -> list[date]:
        dates: list[date] = []
        for cell in values:
            cleaned = normalize_whitespace(cell)
            if not cleaned:
                continue

            parsed = coerce_date(cleaned)
            if parsed and parsed not in dates:
                dates.append(parsed)
                continue

            for extracted in extract_dates_from_text(cleaned):
                if extracted not in dates:
                    dates.append(extracted)
        return dates

    def _extract_calendar_description_from_cells(self, values: list[str]) -> str:
        parts: list[str] = []
        for cell in values:
            cleaned = normalize_whitespace(cell)
            if not cleaned or cleaned.isdigit():
                continue
            lowered = cleaned.lower()
            if any(token in lowered for token in self.header_tokens):
                continue

            description = self._clean_calendar_description(cleaned)
            if not description or description.isdigit():
                continue
            if re.search(r'[A-Za-z]', description):
                parts.append(description)
        return self._dedupe_join(parts)

    def _extract_holiday_occasion_from_cells(self, values: list[str]) -> str:
        parts: list[str] = []
        for cell in values:
            cleaned = normalize_whitespace(cell)
            if not cleaned or cleaned.isdigit():
                continue
            lowered = cleaned.lower()
            if any(token in lowered for token in self.header_tokens):
                continue
            if lowered in self.weekday_tokens:
                continue

            description = self._clean_calendar_description(cleaned)
            if not description or description.isdigit():
                continue
            if re.search(r'[A-Za-z]', description):
                parts.append(description)
        return self._dedupe_join(parts)

    def _dedupe_join(self, parts: list[str]) -> str:
        ordered: list[str] = []
        for part in parts:
            normalized = normalize_whitespace(part)
            if normalized and normalized not in ordered:
                ordered.append(normalized)
        return ' '.join(ordered).strip()

    def _is_header_like_row(self, values: list[str]) -> bool:
        joined = normalize_whitespace(' '.join(values)).lower()
        if not joined:
            return True
        return any(token in joined for token in self.header_tokens) and not extract_dates_from_text(joined)

    def _find_column(self, columns: pd.Index, aliases: tuple[str, ...]) -> str | None:
        lowered = [str(column).lower() for column in columns]
        for alias in aliases:
            for column in lowered:
                if alias in column:
                    return column
        return None

    def _derive_teaching_window(self, events: pd.DataFrame) -> tuple[date, date]:
        teaching_periods = self._derive_teaching_periods(events)
        return teaching_periods['from_date'].min(), teaching_periods['to_date'].max()

    def _derive_teaching_periods(self, events: pd.DataFrame) -> pd.DataFrame:
        descriptions = events['description'].fillna('').astype(str).str.lower()
        teaching_mask = descriptions.apply(self._is_teaching_event)
        candidate_events = events[teaching_mask].copy()
        if candidate_events.empty:
            candidate_events = events[descriptions.apply(self._is_likely_teaching_period)].copy()
        if candidate_events.empty:
            raise ProcessingError('Unable to determine the teaching period from the academic calendar.')
        return candidate_events.sort_values(['from_date', 'to_date', 'description']).reset_index(drop=True)

    def _derive_blocked_dates(self, events: pd.DataFrame, holidays: pd.DataFrame) -> set[date]:
        blocked: set[date] = set()
        for _, row in events.iterrows():
            description = str(row['description']).lower()
            if self._is_exclusion_event(description):
                blocked.update(expand_date_range(row['from_date'], row['to_date']))

        if not holidays.empty:
            blocked.update(holidays['date'].dt.date.tolist())
        return blocked

    def _is_teaching_event(self, description: str) -> bool:
        lowered = description.lower()
        return self._matches_keywords(lowered, self.teaching_keywords) and not self._is_exclusion_event(lowered)

    def _is_likely_teaching_period(self, description: str) -> bool:
        lowered = description.lower()
        if self._is_exclusion_event(lowered):
            return False
        if self._matches_keywords(lowered, ('instruction', 'class work', 'classwork', 'spell', 'teaching')):
            return True
        return self._matches_keywords(lowered, ('commencement',)) and self._matches_keywords(lowered, ('class work', 'instruction', 'teaching'))

    def _is_exclusion_event(self, description: str) -> bool:
        lowered = description.lower()
        return self._matches_keywords(lowered, self.exclusion_keywords)

    def _matches_keywords(self, description: str, keywords: tuple[str, ...]) -> bool:
        normalized = normalize_whitespace(description.lower())
        compact_tokens = self._compact_tokens(normalized)

        for keyword in keywords:
            keyword_text = keyword.lower()
            if keyword_text in normalized:
                return True

            keyword_tokens = self._compact_tokens(keyword_text)
            if not keyword_tokens:
                continue

            if len(keyword_tokens) == 1:
                target = keyword_tokens[0]
                if any(self._similar(token, target) >= 0.78 for token in compact_tokens):
                    return True
                continue

            window_size = len(keyword_tokens)
            for index in range(len(compact_tokens) - window_size + 1):
                window = compact_tokens[index : index + window_size]
                if all(self._similar(token, target) >= 0.78 for token, target in zip(window, keyword_tokens)):
                    return True

        return False

    def _compact_tokens(self, value: str) -> list[str]:
        return [token for token in re.findall(r'[a-z]+', value.lower()) if token]

    def _similar(self, left: str, right: str) -> float:
        return SequenceMatcher(None, left, right).ratio()

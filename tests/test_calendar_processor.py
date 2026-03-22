import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from src.calendar_processor import CalendarProcessor
from src.utils import ParsedDocument, ProcessingError


def _calendar_document(rows: list[list[str]]) -> ParsedDocument:
    """Build a ParsedDocument with a single table from row data."""
    table = pd.DataFrame(rows[1:], columns=rows[0])
    return ParsedDocument(file_path=Path("calendar.pdf"), file_type="pdf", raw_text="", tables=[table], metadata={})


def _holiday_document(rows: list[list[str]]) -> ParsedDocument:
    """Build a ParsedDocument with a single holiday table."""
    table = pd.DataFrame(rows[1:], columns=rows[0])
    return ParsedDocument(file_path=Path("holidays.pdf"), file_type="pdf", raw_text="", tables=[table], metadata={})


class CalendarProcessorTests(unittest.TestCase):
    def _make_calendar_doc(self) -> ParsedDocument:
        rows = [
            ["S.No", "Description", "From", "To"],
            ["1", "Commencement of class work / Instructions", "02-06-2025", "15-07-2025"],
            ["2", "I Mid Term Examinations", "16-07-2025", "22-07-2025"],
            ["3", "Instructions", "23-07-2025", "30-08-2025"],
        ]
        return _calendar_document(rows)

    def _make_holiday_doc(self) -> ParsedDocument:
        rows = [
            ["S.No", "Date", "Occasion"],
            ["1", "15-06-2025", "Festival Holiday"],
            ["2", "15-08-2025", "Independence Day"],
        ]
        return _holiday_document(rows)

    def test_build_teaching_days_returns_sorted_dates(self) -> None:
        processor = CalendarProcessor()
        calendar_doc = self._make_calendar_doc()
        holiday_doc = self._make_holiday_doc()

        teaching_days = processor.build_teaching_days(calendar_doc, holiday_doc)

        self.assertFalse(teaching_days.empty)
        dates = teaching_days["date"].tolist()
        self.assertEqual(dates, sorted(dates))

    def test_holidays_are_excluded_from_teaching_days(self) -> None:
        processor = CalendarProcessor()
        calendar_doc = self._make_calendar_doc()
        holiday_doc = self._make_holiday_doc()

        teaching_days = processor.build_teaching_days(calendar_doc, holiday_doc)

        teaching_dates = {pd.Timestamp(d).date() for d in teaching_days["date"]}
        self.assertNotIn(date(2025, 6, 15), teaching_dates)
        self.assertNotIn(date(2025, 8, 15), teaching_dates)

    def test_sundays_are_excluded_from_teaching_days(self) -> None:
        processor = CalendarProcessor()
        calendar_doc = self._make_calendar_doc()
        holiday_doc = self._make_holiday_doc()

        teaching_days = processor.build_teaching_days(calendar_doc, holiday_doc)

        days_of_week = teaching_days["day"].unique().tolist()
        self.assertNotIn("Sunday", days_of_week)

    def test_empty_calendar_raises_processing_error(self) -> None:
        processor = CalendarProcessor()
        empty_table = pd.DataFrame(columns=["Description", "From", "To"])
        calendar_doc = ParsedDocument(
            file_path=Path("empty.pdf"), file_type="pdf", raw_text="", tables=[empty_table], metadata={}
        )

        with self.assertRaises(ProcessingError):
            processor.extract_calendar_events(calendar_doc)

    def test_calendar_with_single_teaching_period(self) -> None:
        processor = CalendarProcessor()
        rows = [
            ["S.No", "Description", "From", "To"],
            ["1", "Instructions", "02-06-2025", "07-06-2025"],
        ]
        calendar_doc = _calendar_document(rows)
        holiday_doc = _holiday_document([["S.No", "Date", "Occasion"]])

        teaching_days = processor.build_teaching_days(calendar_doc, holiday_doc)

        self.assertFalse(teaching_days.empty)
        teaching_dates = {pd.Timestamp(d).date() for d in teaching_days["date"]}
        # June 2 (Mon) through June 7 (Sat) minus Sunday June 1 is not in range
        self.assertIn(date(2025, 6, 2), teaching_dates)
        self.assertIn(date(2025, 6, 7), teaching_dates)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

import pandas as pd

from src.timetable_parser import TimeTableParser
from src.utils import ParsedDocument, ProcessingError


def _timetable_document(rows: list[list[str]], raw_text: str = "") -> ParsedDocument:
    """Build a ParsedDocument with a single timetable table."""
    table = pd.DataFrame(rows[1:], columns=rows[0])
    return ParsedDocument(file_path=Path("timetable.pdf"), file_type="pdf", raw_text=raw_text, tables=[table], metadata={})


class TimetableParserTests(unittest.TestCase):
    def _make_class_timetable(self) -> ParsedDocument:
        rows = [
            ["Day", "P1", "P2", "P3", "P4", "Lunch", "P5", "P6"],
            ["Monday", "PPS", "Maths", "Physics", "English", "Lunch", "PPS Lab", "PPS Lab"],
            ["Tuesday", "Maths", "PPS", "English", "Physics", "Lunch", "Chemistry", "Free"],
            ["Wednesday", "English", "PPS", "Maths", "Free", "Lunch", "Physics", "Maths"],
            ["Thursday", "Physics", "Maths", "PPS", "English", "Lunch", "Free", "Free"],
            ["Friday", "Maths", "English", "Physics", "PPS", "Lunch", "Maths", "English"],
            ["Saturday", "Free", "Free", "Free", "Free", "Lunch", "Free", "Free"],
        ]
        return _timetable_document(rows)

    def test_extract_from_class_timetable(self) -> None:
        parser = TimeTableParser()
        document = self._make_class_timetable()

        periods = parser.extract_subject_periods(document, subject_name="PPS")

        self.assertFalse(periods.empty)
        self.assertIn("day", periods.columns)
        self.assertIn("period", periods.columns)
        self.assertIn("entry", periods.columns)
        # PPS appears multiple times across days
        days_with_pps = periods["day"].unique().tolist()
        self.assertIn("Monday", days_with_pps)
        self.assertIn("Tuesday", days_with_pps)

    def test_empty_table_raises_error(self) -> None:
        parser = TimeTableParser()
        rows = [["Day", "P1"], ["Monday", "Free"], ["Tuesday", "Free"]]
        document = _timetable_document(rows)

        with self.assertRaises(ProcessingError):
            parser.extract_subject_periods(document, subject_name="Nonexistent Subject XYZ")

    def test_branch_filter_narrows_results(self) -> None:
        parser = TimeTableParser()
        rows = [
            ["Day", "P1", "P2", "P3"],
            ["Monday", "PPS - CSE", "Maths", "PPS - ECE"],
            ["Tuesday", "Maths", "PPS - CSE", "Free"],
            ["Wednesday", "PPS - ECE", "Free", "PPS - CSE"],
        ]
        document = _timetable_document(rows)

        periods = parser.extract_subject_periods(document, subject_name="PPS", branch_name="CSE")

        self.assertFalse(periods.empty)
        if "branch" in periods.columns:
            branches = periods["branch"].unique().tolist()
            for branch in branches:
                self.assertIn("CSE", branch.upper())


if __name__ == "__main__":
    unittest.main()

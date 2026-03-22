import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.export_excel import export_bundle_to_excel
from src.utils import LessonPlanBundle, escape_cell_value


def _minimal_bundle() -> LessonPlanBundle:
    """Build a minimal LessonPlanBundle for export tests."""
    lesson_plan = pd.DataFrame(
        [
            {
                "Week": 1,
                "Date": "02-06-2025",
                "Day": "Monday",
                "Period": "P1",
                "Unit": "Unit 1",
                "Topic": "Variables and Data Types",
                "Teaching Method": "Lecture",
                "CO": "CO1",
            },
            {
                "Week": 1,
                "Date": "04-06-2025",
                "Day": "Wednesday",
                "Period": "P2",
                "Unit": "Unit 1",
                "Topic": "Operators",
                "Teaching Method": "Lecture",
                "CO": "CO1",
            },
        ]
    )
    monthly_plan = pd.DataFrame(
        [{"Month": "June 2025", "Units Covered": "Unit 1", "Classes Planned": 2}]
    )
    coverage_report = pd.DataFrame(
        [{"Unit": "Unit 1", "Total Topics": 3, "Completed": 2, "Remaining": 1}]
    )
    teaching_days = pd.DataFrame(
        [
            {"date": pd.Timestamp("2025-06-02"), "day": "Monday", "week": 1, "month": "June 2025"},
            {"date": pd.Timestamp("2025-06-04"), "day": "Wednesday", "week": 1, "month": "June 2025"},
        ]
    )
    return LessonPlanBundle(
        lesson_plan=lesson_plan,
        monthly_plan=monthly_plan,
        coverage_report=coverage_report,
        class_schedule=lesson_plan.copy(),
        teaching_days=teaching_days,
        metadata={
            "faculty_info": {
                "faculty_name": "Dr. Test",
                "subject_name": "Programming for Problem Solving",
                "branch": "CSE",
                "section": "A",
                "semester": "I Year I Sem",
                "designation": "Professor",
                "student_count": "60",
            },
            "course_title": "Programming for Problem Solving",
            "course_code": "PCS105ES",
            "regulation": "R25",
            "text_books": ["Book A"],
            "reference_books": [],
            "course_outcomes": [],
            "teaching_days": 2,
            "planned_classes": 2,
            "planned_branches": [],
            "is_lab": False,
            "experiment_count": 0,
        },
    )


class ExportExcelTests(unittest.TestCase):
    def test_export_creates_xlsx_files(self) -> None:
        bundle = _minimal_bundle()
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = export_bundle_to_excel(bundle, tmp_dir)

            self.assertIn("lesson_plan", result)
            self.assertIn("monthly_plan", result)
            self.assertIn("coverage_report", result)
            self.assertTrue(result["lesson_plan"].exists())
            self.assertTrue(result["monthly_plan"].exists())
            self.assertTrue(result["coverage_report"].exists())
            self.assertTrue(str(result["lesson_plan"]).endswith(".xlsx"))

    def test_export_creates_output_directory(self) -> None:
        bundle = _minimal_bundle()
        with tempfile.TemporaryDirectory() as tmp_dir:
            nested_dir = Path(tmp_dir) / "subdir" / "output"
            result = export_bundle_to_excel(bundle, nested_dir)

            self.assertTrue(nested_dir.exists())
            self.assertTrue(result["lesson_plan"].exists())

    def test_formula_escaping_applied_to_cells(self) -> None:
        self.assertEqual(escape_cell_value("=SUM(A1)"), "'=SUM(A1)")
        self.assertEqual(escape_cell_value("+cmd"), "'+cmd")
        self.assertEqual(escape_cell_value("-1+1"), "'-1+1")
        self.assertEqual(escape_cell_value("@import"), "'@import")
        self.assertEqual(escape_cell_value("Normal text"), "Normal text")
        self.assertEqual(escape_cell_value(42), 42)
        self.assertEqual(escape_cell_value(""), "")


if __name__ == "__main__":
    unittest.main()

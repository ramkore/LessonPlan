import tempfile
import unittest

import pandas as pd

from src.export_pdf import export_bundle_to_pdf
from src.utils import LessonPlanBundle


def _minimal_bundle(lab: bool = False) -> LessonPlanBundle:
    """Build a minimal LessonPlanBundle for PDF export tests."""
    if lab:
        lesson_plan = pd.DataFrame(
            [
                {
                    "Week": 1,
                    "Date": "02-06-2025",
                    "Day": "Monday",
                    "Period": "P1 / P2",
                    "Unit": "Lab",
                    "Exp No": "1",
                    "Topic": "Write a C program for arithmetic",
                    "Teaching Method": "Practical",
                    "CO": "CO1",
                },
                {
                    "Week": 1,
                    "Date": "04-06-2025",
                    "Day": "Wednesday",
                    "Period": "P1 / P2",
                    "Unit": "Lab",
                    "Exp No": "2",
                    "Topic": "Write a C program for loops",
                    "Teaching Method": "Practical",
                    "CO": "CO1",
                },
            ]
        )
        metadata = {
            "faculty_info": {
                "faculty_name": "Dr. Test",
                "subject_name": "Programming Lab",
                "branch": "CSE",
                "section": "A",
                "semester": "I Year I Sem",
                "designation": "Professor",
                "student_count": "60",
            },
            "course_title": "Programming Lab",
            "course_code": "PCS106ES",
            "regulation": "R25",
            "text_books": [],
            "reference_books": [],
            "course_outcomes": [],
            "teaching_days": 2,
            "planned_classes": 2,
            "planned_branches": [],
            "is_lab": True,
            "experiment_count": 2,
        }
    else:
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
            ]
        )
        metadata = {
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
            "teaching_days": 1,
            "planned_classes": 1,
            "planned_branches": [],
            "is_lab": False,
            "experiment_count": 0,
        }

    teaching_days = pd.DataFrame(
        [{"date": pd.Timestamp("2025-06-02"), "day": "Monday", "week": 1, "month": "June 2025"}]
    )
    monthly_plan = pd.DataFrame(
        [{"Month": "June 2025", "Units Covered": "Unit 1", "Classes Planned": 1}]
    )
    coverage_report = pd.DataFrame(
        [{"Unit": "Unit 1", "Total Topics": 1, "Completed": 1, "Remaining": 0}]
    )
    return LessonPlanBundle(
        lesson_plan=lesson_plan,
        monthly_plan=monthly_plan,
        coverage_report=coverage_report,
        class_schedule=lesson_plan.copy(),
        teaching_days=teaching_days,
        metadata=metadata,
    )


class ExportPdfTests(unittest.TestCase):
    def test_export_creates_pdf_file(self) -> None:
        bundle = _minimal_bundle(lab=False)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result_path = export_bundle_to_pdf(bundle, tmp_dir)

            self.assertTrue(result_path.exists())
            self.assertTrue(str(result_path).endswith(".pdf"))
            self.assertGreater(result_path.stat().st_size, 0)

    def test_export_pdf_with_lab_bundle(self) -> None:
        bundle = _minimal_bundle(lab=True)
        with tempfile.TemporaryDirectory() as tmp_dir:
            result_path = export_bundle_to_pdf(bundle, tmp_dir)

            self.assertTrue(result_path.exists())
            self.assertTrue(str(result_path).endswith(".pdf"))
            self.assertGreater(result_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

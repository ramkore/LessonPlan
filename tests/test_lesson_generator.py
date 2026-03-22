import unittest
from datetime import date

import pandas as pd

from src.lesson_generator import LessonPlanGenerator
from src.utils import ProcessingError


def _minimal_teaching_days(count: int = 10) -> pd.DataFrame:
    """Build a minimal teaching_days DataFrame starting from a Monday."""
    start = date(2025, 6, 2)  # Monday
    rows = []
    current = start
    week = 1
    while len(rows) < count:
        if current.strftime("%A") != "Sunday":
            rows.append(
                {
                    "date": pd.Timestamp(current),
                    "day": current.strftime("%A"),
                    "week": week,
                    "month": current.strftime("%B %Y"),
                }
            )
        current += pd.Timedelta(days=1)
        if current.strftime("%A") == "Monday":
            week += 1
    return pd.DataFrame(rows)


def _minimal_subject_periods() -> pd.DataFrame:
    """Build a subject_periods DataFrame with Monday and Wednesday periods."""
    return pd.DataFrame(
        [
            {"day": "Monday", "period": "P1", "entry": "PPS", "branch": "", "time_slot": ""},
            {"day": "Wednesday", "period": "P2", "entry": "PPS", "branch": "", "time_slot": ""},
        ]
    )


def _minimal_syllabus() -> dict:
    return {
        "course_title": "Programming for Problem Solving",
        "course_code": "PCS105ES",
        "regulation": "R25",
        "units": [
            {"unit": "Unit 1", "topics": ["Variables", "Data Types", "Operators"], "co": "CO1"},
            {"unit": "Unit 2", "topics": ["Functions", "Recursion"], "co": "CO2"},
        ],
        "text_books": ["Example Book"],
        "reference_books": [],
        "course_outcomes": ["CO1: Solve problems"],
    }


def _minimal_faculty_info() -> dict:
    return {
        "faculty_name": "Dr. Test",
        "subject_name": "Programming for Problem Solving",
        "branch": "CSE",
        "section": "A",
        "semester": "I Year I Sem",
        "designation": "Associate Professor",
        "student_count": "60",
    }


def _lab_syllabus() -> dict:
    return {
        "course_title": "Programming Lab",
        "course_code": "PCS106ES",
        "regulation": "R25",
        "units": [],
        "experiments": [
            {"exp_no": "1", "topic": "Write a C program for arithmetic"},
            {"exp_no": "2", "topic": "Write a C program for loops"},
            {"exp_no": "3", "topic": "Write a C program for arrays"},
        ],
        "text_books": [],
        "reference_books": [],
        "course_outcomes": [],
    }


class LessonGeneratorTests(unittest.TestCase):
    def test_generate_produces_lesson_plan_dataframe(self) -> None:
        generator = LessonPlanGenerator()
        teaching_days = _minimal_teaching_days(20)
        subject_periods = _minimal_subject_periods()
        syllabus = _minimal_syllabus()
        faculty_info = _minimal_faculty_info()

        bundle = generator.generate(teaching_days, subject_periods, syllabus, faculty_info)

        self.assertFalse(bundle.lesson_plan.empty)
        self.assertIsInstance(bundle.lesson_plan, pd.DataFrame)

    def test_generate_produces_monthly_plan(self) -> None:
        generator = LessonPlanGenerator()
        teaching_days = _minimal_teaching_days(20)
        subject_periods = _minimal_subject_periods()
        syllabus = _minimal_syllabus()
        faculty_info = _minimal_faculty_info()

        bundle = generator.generate(teaching_days, subject_periods, syllabus, faculty_info)

        self.assertFalse(bundle.monthly_plan.empty)
        self.assertIn("Month", bundle.monthly_plan.columns)
        self.assertIn("Classes Planned", bundle.monthly_plan.columns)

    def test_generate_produces_coverage_report(self) -> None:
        generator = LessonPlanGenerator()
        teaching_days = _minimal_teaching_days(20)
        subject_periods = _minimal_subject_periods()
        syllabus = _minimal_syllabus()
        faculty_info = _minimal_faculty_info()

        bundle = generator.generate(teaching_days, subject_periods, syllabus, faculty_info)

        self.assertFalse(bundle.coverage_report.empty)
        self.assertIn("Unit", bundle.coverage_report.columns)
        self.assertIn("Total Topics", bundle.coverage_report.columns)

    def test_lesson_plan_has_expected_columns(self) -> None:
        generator = LessonPlanGenerator()
        teaching_days = _minimal_teaching_days(20)
        subject_periods = _minimal_subject_periods()
        syllabus = _minimal_syllabus()
        faculty_info = _minimal_faculty_info()

        bundle = generator.generate(teaching_days, subject_periods, syllabus, faculty_info)

        columns = bundle.lesson_plan.columns.tolist()
        for expected in ["Week", "Date", "Day", "Period", "Unit", "Topic", "Teaching Method", "CO"]:
            self.assertIn(expected, columns)

    def test_empty_periods_raises_processing_error(self) -> None:
        generator = LessonPlanGenerator()
        teaching_days = _minimal_teaching_days(10)
        empty_periods = pd.DataFrame(columns=["day", "period", "entry", "branch", "time_slot"])
        syllabus = _minimal_syllabus()
        faculty_info = _minimal_faculty_info()

        with self.assertRaises(ProcessingError):
            generator.generate(teaching_days, empty_periods, syllabus, faculty_info)

    def test_lab_mode_uses_experiment_numbers(self) -> None:
        generator = LessonPlanGenerator()
        teaching_days = _minimal_teaching_days(20)
        subject_periods = _minimal_subject_periods()
        syllabus = _lab_syllabus()
        faculty_info = {**_minimal_faculty_info(), "subject_name": "Programming Lab"}

        bundle = generator.generate(teaching_days, subject_periods, syllabus, faculty_info)

        self.assertTrue(bundle.metadata["is_lab"])
        self.assertIn("Exp No", bundle.lesson_plan.columns)
        exp_numbers = bundle.lesson_plan["Exp No"].tolist()
        self.assertTrue(any(str(v).strip() for v in exp_numbers))


if __name__ == "__main__":
    unittest.main()

import unittest

import pandas as pd

from src.export_excel import _signature_ranges
from src.lesson_plan_format import (
    SIGN_LABELS,
    formatted_lab_lesson_plan_frame,
    formatted_theory_lesson_plan_frame,
    summary_values,
)
from src.utils import LessonPlanBundle


class SignatureLayoutTests(unittest.TestCase):
    def _bundle(self, course_title: str, section: str = "") -> LessonPlanBundle:
        return LessonPlanBundle(
            lesson_plan=pd.DataFrame([{"Topic": "Introduction", "Teaching Method": "Lecture"}]),
            monthly_plan=pd.DataFrame(),
            coverage_report=pd.DataFrame(),
            class_schedule=pd.DataFrame([{"branch": "CSE"}]),
            teaching_days=pd.DataFrame({"date": pd.to_datetime(["2026-01-12"])}),
            metadata={
                "course_title": course_title,
                "course_code": "PCS205ES",
                "faculty_info": {
                    "branch": "CSE",
                    "semester": "I Year II Sem",
                    "section": section,
                    "faculty_name": "Mr. B. Naresh",
                    "subject_name": course_title,
                },
            },
        )

    def test_summary_values_use_three_signature_labels_for_theory_and_lab(self) -> None:
        theory_summary = summary_values(self._bundle("Data Structures"))
        lab_summary = summary_values(self._bundle("Data Structures Lab"))

        self.assertEqual(theory_summary["sign_labels"], SIGN_LABELS)
        self.assertEqual(lab_summary["sign_labels"], SIGN_LABELS)

    def test_summary_values_include_section_in_class_sem(self) -> None:
        summary = summary_values(self._bundle("Data Structures", section="C"))

        self.assertEqual(summary["class_sem"], "CSE-C - I Year II Sem")

    def test_summary_values_prepare_wrapped_display_text_for_long_summary_cells(self) -> None:
        summary = summary_values(self._bundle("Python Programming Laboratory"))

        self.assertIn("\n", summary["course_title_display"])
        self.assertIn("\n", summary["total_label_display"])

    def test_excel_signature_ranges_keep_visible_gaps(self) -> None:
        self.assertEqual(_signature_ranges(9, SIGN_LABELS), [(1, 2, "FACULTY"), (5, 5, "HOD"), (8, 9, "PRINCIPAL")])
        self.assertEqual(_signature_ranges(7, SIGN_LABELS), [(1, 2, "FACULTY"), (4, 4, "HOD"), (6, 7, "PRINCIPAL")])

    def test_text_book_column_always_uses_t1_for_theory_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"Week": 1, "Unit": "Unit I", "Topic": "Introduction", "Date": "12-02-2026", "Teaching Method": "Lecture"},
                {"Week": 2, "Unit": "Unit I", "Topic": "UNIT TEST - I", "Date": "19-02-2026", "Teaching Method": "Unit Test"},
            ]
        )

        formatted = formatted_theory_lesson_plan_frame(frame)

        self.assertEqual(formatted["Text Book"].tolist(), ["T1", "T1"])

    def test_text_book_column_always_uses_t1_for_lab_rows(self) -> None:
        frame = pd.DataFrame(
            [
                {"Exp No": "1", "Topic": "Experiment 1", "Date": "12-02-2026"},
                {"Exp No": "2", "Topic": "Experiment 2", "Date": "19-02-2026"},
            ]
        )

        formatted = formatted_lab_lesson_plan_frame(frame)

        self.assertEqual(
            formatted.columns.tolist(),
            ['SN No.', 'Exp No:', 'Topics to be Covered', 'Text book', 'Planned date', 'Actual Date', 'Remarks'],
        )
        self.assertEqual(formatted["Text book"].tolist(), ["T1", "T1"])


if __name__ == "__main__":
    unittest.main()

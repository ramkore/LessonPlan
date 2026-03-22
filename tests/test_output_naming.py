import unittest
from pathlib import Path

import pandas as pd

from src.utils import LessonPlanBundle, lesson_plan_output_stem, report_output_paths


class OutputNamingTests(unittest.TestCase):
    def _bundle(
        self,
        course_title: str = "Python Programming",
        branch: str = "ECE",
        section: str = "",
    ) -> LessonPlanBundle:
        return LessonPlanBundle(
            lesson_plan=pd.DataFrame([{"Topic": "Introduction"}]),
            monthly_plan=pd.DataFrame([{"Month": "January 2026"}]),
            coverage_report=pd.DataFrame([{"Unit": "Unit I"}]),
            class_schedule=pd.DataFrame([{"branch": branch}]),
            teaching_days=pd.DataFrame({"date": pd.to_datetime(["2026-01-12"])}),
            metadata={
                "course_title": course_title,
                "course_code": "PCS208ES",
                "planned_branches": [branch],
                "faculty_info": {
                    "branch": branch,
                    "semester": "I Year II Sem",
                    "subject_name": course_title,
                    "section": section,
                },
            },
        )

    def test_report_output_paths_use_branch_folder_and_requested_stem(self) -> None:
        bundle = self._bundle()
        base = Path("output") / "naming_test"
        paths = report_output_paths(bundle, base)

        self.assertEqual(paths["lesson_plan_excel"], base / "ECE" / "PP_Sub" / "I_B.Tech_II_Sem_ECE_PP_Lesson_Plan.xlsx")
        self.assertEqual(paths["lesson_plan_word"], base / "ECE" / "PP_Sub" / "I_B.Tech_II_Sem_ECE_PP_Lesson_Plan.docx")
        self.assertEqual(paths["lesson_plan_pdf"], base / "ECE" / "PP_Sub" / "I_B.Tech_II_Sem_ECE_PP_Lesson_Plan.pdf")
        self.assertEqual(paths["monthly_plan_excel"], base / "ECE" / "PP_Sub" / "I_B.Tech_II_Sem_ECE_PP_Monthly_Teaching_Plan.xlsx")
        self.assertEqual(paths["coverage_report_excel"], base / "ECE" / "PP_Sub" / "I_B.Tech_II_Sem_ECE_PP_Syllabus_Coverage_Report.xlsx")

    def test_lab_subjects_add_lab_suffix_without_changing_subject_abbreviation(self) -> None:
        bundle = self._bundle("Python Programming Laboratory")

        self.assertEqual(lesson_plan_output_stem(bundle), "I_B.Tech_II_Sem_ECE_PP_Lab")

    def test_section_is_included_in_output_stem_when_present(self) -> None:
        bundle = self._bundle("Data Structures", branch="CSE", section="C")
        paths = report_output_paths(bundle, Path("output") / "naming_test")

        self.assertEqual(lesson_plan_output_stem(bundle), "I_B.Tech_II_Sem_CSE_C_DS")
        self.assertEqual(paths["lesson_plan_excel"], Path("output") / "naming_test" / "CSE C" / "DS_Sub" / "I_B.Tech_II_Sem_CSE_C_DS_Lesson_Plan.xlsx")

    def test_section_and_lab_are_both_included_in_output_stem(self) -> None:
        bundle = self._bundle("Data Structures Lab", branch="CSE", section="C")
        paths = report_output_paths(bundle, Path("output") / "naming_test")

        self.assertEqual(lesson_plan_output_stem(bundle), "I_B.Tech_II_Sem_CSE_C_DS_Lab")
        self.assertEqual(paths["lesson_plan_excel"], Path("output") / "naming_test" / "CSE C" / "DS_Lab" / "I_B.Tech_II_Sem_CSE_C_DS_Lab_Lesson_Plan.xlsx")


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

import pandas as pd

from src.lesson_generator import LessonPlanGenerator
from src.lesson_plan_format import formatted_lab_lesson_plan_frame, lab_date_row_spans
from src.syllabus_parser import SyllabusParser
from src.timetable_parser import TimeTableParser
from src.utils import ParsedDocument


class LabLessonPlanTests(unittest.TestCase):
    def test_individual_timetable_filters_theory_and_lab_slots_separately(self) -> None:
        table = pd.DataFrame(
            [
                ['MON', '', '', '', 'ECE', '', ''],
                ['TUE', 'ECE LAB', '', '', '', 'ECE', ''],
                ['THU', '', 'ECE', '', '', '', 'ECE'],
            ],
            columns=['DAY / Period', '09:20', '10:20', '11:30', '01:10', '02:10', '03:10'],
        )
        table.attrs['context_text'] = 'Name of the Faculty: K Ramesh Subject: Python & Python Lab'
        document = ParsedDocument(file_path=Path('sample.docx'), file_type='docx', raw_text='Name of the Faculty: K Ramesh', tables=[table], metadata={})
        parser = TimeTableParser()

        theory = parser.extract_subject_periods(document, 'Python', 'K Ramesh', 'ECE')
        lab = parser.extract_subject_periods(document, 'Python Programming Laboratory', 'K Ramesh', 'ECE')

        self.assertEqual(theory['entry'].tolist(), ['ECE', 'ECE', 'ECE', 'ECE'])
        self.assertEqual(lab['entry'].tolist(), ['ECE LAB'])

    def test_branch_filter_accepts_section_suffixed_entries(self) -> None:
        table = pd.DataFrame(
            [
                ['MON', 'ECE', 'CSE-C', '', ''],
                ['TUE', '', 'CSE-C LAB', '', ''],
                ['WED', '', '', 'CSE-C', ''],
            ],
            columns=['DAY / Period', '09:20', '10:20', '11:30', '02:10'],
        )
        table.attrs['context_text'] = 'Name of the Faculty: Mr. B. Naresh Subject: DS & DS LAB'
        document = ParsedDocument(file_path=Path('faculty_timetable.docx'), file_type='docx', raw_text='Name of the Faculty: Mr. B. Naresh', tables=[table], metadata={})
        parser = TimeTableParser()

        theory = parser.extract_subject_periods(document, 'Data Structures', 'Mr. B. Naresh', 'CSE')
        lab = parser.extract_subject_periods(document, 'Data Structures Lab', 'Mr. B. Naresh', 'CSE')

        self.assertEqual(theory['entry'].tolist(), ['CSE-C', 'CSE-C'])
        self.assertTrue((theory['branch'] == 'CSE').all())
        self.assertEqual(lab['entry'].tolist(), ['CSE-C LAB'])
        self.assertTrue((lab['branch'] == 'CSE').all())

    def test_lab_generation_uses_experiment_numbers_without_unit_tests(self) -> None:
        teaching_days = pd.DataFrame(
            {
                'date': pd.to_datetime(['2026-02-10', '2026-02-17']),
                'day': ['Tuesday', 'Tuesday'],
                'week': [1, 2],
                'month': [2, 2],
            }
        )
        subject_periods = pd.DataFrame(
            [{'day': 'Tuesday', 'period': 'P1', 'entry': 'ECE LAB', 'branch': 'ECE', 'time_slot': '09:20 AM to 10:20 AM'}]
        )
        syllabus = {
            'course_title': 'Python Programming Laboratory',
            'course_code': 'PCS208ES',
            'experiments': [
                {'exp_no': '1', 'topic': 'Install Python'},
                {'exp_no': '2', 'topic': 'Calculator using Python'},
                {'exp_no': '3', 'topic': 'Compound interest program'},
            ],
            'units': [{'unit': 'Unit I', 'topics': ['Install Python', 'Calculator using Python', 'Compound interest program'], 'co': 'CO1'}],
        }
        faculty_info = {'subject_name': 'Python Programming Laboratory', 'branch': 'ECE'}

        bundle = LessonPlanGenerator().generate(teaching_days, subject_periods, syllabus, faculty_info)

        self.assertIn('Exp No', bundle.lesson_plan.columns)
        self.assertEqual(bundle.lesson_plan['Exp No'].tolist(), ['1 + 2', '3'])
        self.assertFalse(bundle.lesson_plan['Topic'].str.contains('UNIT TEST', case=False).any())

    def test_lab_generation_uses_only_actual_experiments_when_more_dates_are_available(self) -> None:
        teaching_days = pd.DataFrame(
            {
                'date': pd.to_datetime(['2026-02-12', '2026-02-19', '2026-02-26', '2026-03-05', '2026-03-12', '2026-03-19']),
                'day': ['Thursday'] * 6,
                'week': [1, 2, 3, 4, 5, 6],
                'month': [2, 2, 2, 3, 3, 3],
            }
        )
        subject_periods = pd.DataFrame(
            [
                {'day': 'Thursday', 'period': 'P1', 'entry': 'CSE-C LAB', 'branch': 'CSE', 'time_slot': '09:20 AM to 10:20 AM'},
                {'day': 'Thursday', 'period': 'P2', 'entry': 'CSE-C LAB', 'branch': 'CSE', 'time_slot': '10:20 AM to 11:20 AM'},
            ]
        )
        syllabus = {
            'course_title': 'Data Structures Lab',
            'course_code': 'PCS205ES',
            'experiments': [
                {'exp_no': '1', 'topic': 'Single linked list'},
                {'exp_no': '2', 'topic': 'Doubly linked list'},
                {'exp_no': '3', 'topic': 'Circular linked list'},
                {'exp_no': '4', 'topic': 'Stack and queue'},
            ],
            'units': [{'unit': 'Unit I', 'topics': ['Single linked list', 'Doubly linked list', 'Circular linked list', 'Stack and queue'], 'co': 'CO1'}],
        }
        faculty_info = {'subject_name': 'Data Structures Lab', 'branch': 'CSE'}

        bundle = LessonPlanGenerator().generate(teaching_days, subject_periods, syllabus, faculty_info)
        formatted = formatted_lab_lesson_plan_frame(bundle.lesson_plan)

        self.assertEqual(bundle.metadata['experiment_count'], 4)
        self.assertEqual(bundle.lesson_plan['Exp No'].tolist(), ['1', '1', '2', '2', '3', '4'])
        self.assertFalse(bundle.lesson_plan['Topic'].str.contains('Record Work|Debugging|Lab Viva', case=False).any())
        self.assertEqual(formatted['Exp No:'].tolist(), ['1', '2', '3', '4'])
        self.assertEqual(
            formatted['Planned date'].tolist(),
            ['12-02-2026\n19-02-2026', '26-02-2026\n05-03-2026', '12-03-2026', '19-03-2026'],
        )

    def test_lab_formatter_keeps_blank_extension_numbers_and_tracks_repeated_dates(self) -> None:
        frame = pd.DataFrame(
            [
                {'Exp No': '1', 'Topic': 'Experiment 1', 'Date': '12-02-2026'},
                {'Exp No': '', 'Topic': 'Record Work and Observation Review', 'Date': '12-02-2026'},
                {'Exp No': '2', 'Topic': 'Experiment 2', 'Date': '19-02-2026'},
            ]
        )

        formatted = formatted_lab_lesson_plan_frame(frame)

        self.assertEqual(formatted['Exp No:'].tolist(), ['1', '', '2'])
        self.assertEqual(lab_date_row_spans(formatted), [(0, 1, '12-02-2026'), (2, 2, '19-02-2026')])

    def test_lab_formatter_splits_merged_experiments_but_keeps_shared_date_block(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    'Exp No': '1 + 2 + 3',
                    'Topic': 'Experiment 1 AND Experiment 2 AND Experiment 3',
                    'Date': '10-02-2026',
                }
            ]
        )

        formatted = formatted_lab_lesson_plan_frame(frame)

        self.assertEqual(formatted['Exp No:'].tolist(), ['1', '2', '3'])
        self.assertEqual(
            formatted['Topics to be Covered'].tolist(),
            ['Experiment 1', 'Experiment 2', 'Experiment 3'],
        )
        self.assertEqual(formatted['Planned date'].tolist(), ['10-02-2026', '10-02-2026', '10-02-2026'])
        self.assertEqual(lab_date_row_spans(formatted), [(0, 2, '10-02-2026')])

    def test_lab_coverage_report_uses_experiment_progress_and_branch_section_label(self) -> None:
        today = pd.Timestamp.today().normalize()
        lesson_plan = pd.DataFrame(
            [
                {'Branch': 'CSE', 'Exp No': '1', 'Topic': 'Single linked list', 'Date': (today - pd.Timedelta(days=14)).strftime('%d-%m-%Y')},
                {'Branch': 'CSE', 'Exp No': '1', 'Topic': 'Single linked list', 'Date': (today - pd.Timedelta(days=7)).strftime('%d-%m-%Y')},
                {'Branch': 'CSE', 'Exp No': '2', 'Topic': 'Doubly linked list', 'Date': today.strftime('%d-%m-%Y')},
                {'Branch': 'CSE', 'Exp No': '3', 'Topic': 'Circular linked list', 'Date': (today + pd.Timedelta(days=7)).strftime('%d-%m-%Y')},
                {'Branch': 'CSE', 'Exp No': '4', 'Topic': 'Stack and queue', 'Date': (today + pd.Timedelta(days=14)).strftime('%d-%m-%Y')},
            ]
        )
        syllabus = {
            'course_title': 'Data Structures Lab',
            'experiments': [
                {'exp_no': '1', 'topic': 'Single linked list'},
                {'exp_no': '2', 'topic': 'Doubly linked list'},
                {'exp_no': '3', 'topic': 'Circular linked list'},
                {'exp_no': '4', 'topic': 'Stack and queue'},
            ],
            'units': [{'unit': 'Unit I', 'topics': ['Single linked list', 'Doubly linked list', 'Circular linked list', 'Stack and queue']}],
        }
        faculty_info = {'subject_name': 'Data Structures Lab', 'branch': 'CSE', 'section': 'C'}

        report = LessonPlanGenerator()._build_coverage_report(syllabus, lesson_plan, ['CSE'], faculty_info)

        self.assertEqual(report.to_dict('records'), [{'Branch': 'CSE-C', 'Unit': 'Lab Experiments', 'Total Topics': 4, 'Completed': 2, 'Remaining': 2}])

    def test_syllabus_parser_keeps_lettered_experiment_lines_under_the_same_number(self) -> None:
        raw_text = """
Course Title: Data Structures Lab
List of Experiments:
1. Write a program that uses functions to perform singly linked list operations.
i) Creation ii) Insertion iii) Deletion iv) Traversal
2. Write a program that uses functions to perform doubly linked list operations.
i) Creation ii) Insertion iii) Deletion iv) Traversal
TEXT BOOKS:
1. Example Text
"""
        document = ParsedDocument(file_path=Path('sample.pdf'), file_type='pdf', raw_text=raw_text, tables=[], metadata={})

        syllabus = SyllabusParser().parse(document)

        self.assertEqual([item['exp_no'] for item in syllabus['experiments']], ['1', '2'])
        self.assertIn('Creation', syllabus['experiments'][0]['topic'])
        self.assertIn('Creation', syllabus['experiments'][1]['topic'])


    def test_is_lab_flag_filters_schedule_to_flagged_entries_only(self) -> None:
        """When is_lab flag is set on some entries, only those are used for lab schedule."""
        teaching_days = pd.DataFrame(
            {
                'date': pd.to_datetime([
                    '2026-02-09', '2026-02-10', '2026-02-11', '2026-02-12', '2026-02-13',
                    '2026-02-16', '2026-02-17', '2026-02-18', '2026-02-19', '2026-02-20',
                ]),
                'day': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'] * 2,
                'week': [1, 1, 1, 1, 1, 2, 2, 2, 2, 2],
                'month': [2] * 10,
            }
        )
        # Faculty timetable: lab on Tuesday (P5+P6), theory on other days
        subject_periods = pd.DataFrame([
            {'day': 'Monday', 'period': 'P4', 'entry': 'ECE', 'branch': 'ECE', 'time_slot': '', 'is_lab': False},
            {'day': 'Tuesday', 'period': 'P5', 'entry': 'ECE', 'branch': 'ECE', 'time_slot': '', 'is_lab': True},
            {'day': 'Tuesday', 'period': 'P6', 'entry': 'CE/EEE', 'branch': 'ECE', 'time_slot': '', 'is_lab': True},
            {'day': 'Thursday', 'period': 'P1', 'entry': 'CE/EEE', 'branch': 'ECE', 'time_slot': '', 'is_lab': False},
            {'day': 'Thursday', 'period': 'P2', 'entry': 'ECE', 'branch': 'ECE', 'time_slot': '', 'is_lab': False},
        ])
        syllabus = {
            'course_title': 'Python Programming Laboratory',
            'course_code': 'PCS208ES',
            'experiments': [
                {'exp_no': '1', 'topic': 'Install Python'},
                {'exp_no': '2', 'topic': 'Calculator using Python'},
                {'exp_no': '3', 'topic': 'Compound interest program'},
            ],
            'units': [],
        }
        faculty_info = {'subject_name': 'Python Programming Laboratory', 'branch': 'ECE'}

        bundle = LessonPlanGenerator().generate(teaching_days, subject_periods, syllabus, faculty_info)

        # Should only have Tuesday dates (lab-flagged entries)
        unique_days = bundle.lesson_plan['Day'].unique().tolist()
        self.assertEqual(unique_days, ['Tuesday'])
        unique_dates = bundle.lesson_plan['Date'].unique().tolist()
        self.assertEqual(unique_dates, ['10-02-2026', '17-02-2026'])


if __name__ == '__main__':
    unittest.main()

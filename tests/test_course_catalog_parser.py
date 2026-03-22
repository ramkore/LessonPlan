import unittest
from pathlib import Path

import pandas as pd

from src.course_catalog import CourseCatalogParser
from src.syllabus_parser import SyllabusParser
from src.utils import ParsedDocument


class CourseCatalogParserTests(unittest.TestCase):
    def test_catalog_splits_multi_subject_document(self) -> None:
        raw_text = '''
PCS105ES: PROGRAMMING FOR PROBLEM SOLVING
B.Tech. I Year I Sem. L T P C
Course Objectives:
 To learn programming basics.
Course Outcomes:
 Solve problems using C.
UNIT - I: Overview of C: Variables, Data Types
UNIT - II: Functions: Definition, Calls
TEXT BOOKS:
1. Example Book

PCS110ES: IT WORKSHOP
B.Tech. I Year I Sem. L T P C
Course Objectives: Hardware and office productivity.
Course Outcomes:
 Perform hardware troubleshooting
PC Hardware
Task 1: Identify peripherals of a computer.
Task 2: Install Windows on a system.
Excel
Task 1: Create a scheduler using spreadsheet features.
REFERENCE BOOKS:
1. Example Reference
'''
        document = ParsedDocument(file_path=Path('sample.pdf'), file_type='pdf', raw_text=raw_text, tables=[], metadata={})

        catalog = CourseCatalogParser().parse(document)

        self.assertEqual(catalog['year_sems'], ['I Year I Sem'])
        self.assertEqual(len(catalog['subjects']), 2)

        subjects = {subject['course_code']: subject for subject in catalog['subjects']}
        self.assertIn('PCS105ES', subjects)
        self.assertIn('PCS110ES', subjects)
        self.assertEqual(len(subjects['PCS105ES']['syllabus']['units']), 2)
        self.assertEqual(subjects['PCS110ES']['syllabus']['units'][0]['unit'], 'Unit I')
        self.assertTrue(any('PC Hardware' in topic for topic in subjects['PCS110ES']['syllabus']['units'][0]['topics']))

    def test_course_structure_rows_become_catalog_subjects_with_fallback(self) -> None:
        table_one = pd.DataFrame(
            [
                ['1.', 'PMA101BS', 'Matrices and Calculus', '3', '1', '0', '4'],
                ['2.', 'PCS105ES', 'Programming for Problem Solving', '3', '0', '0', '3'],
            ],
            columns=['S. No.', 'Course Code', 'Course', 'L', 'T', 'P', 'Credits'],
        )
        table_two = pd.DataFrame(
            [
                ['1.', 'PMA201BS', 'Ordinary Differential Equations and Vector Calculus', '3', '0', '0', '3'],
            ],
            columns=['S. No.', 'Course Code', 'Course', 'L', 'T', 'P', 'Credits'],
        )
        raw_text = '''
I Year I Semester
I Year II Semester
PCS105ES: PROGRAMMING FOR PROBLEM SOLVING
B.Tech. I Year I Sem. L T P C
Course Objectives:
 Learn programming basics.
Course Outcomes:
 Solve problems using C.
UNIT - I: Overview of C
UNIT - II: Functions
'''
        document = ParsedDocument(file_path=Path('sample.pdf'), file_type='pdf', raw_text=raw_text, tables=[table_one, table_two], metadata={})

        catalog = CourseCatalogParser().parse(document)
        subjects = {subject['course_code']: subject for subject in catalog['subjects']}

        self.assertIn('PMA101BS', subjects)
        self.assertIn('PCS105ES', subjects)
        self.assertIn('PMA201BS', subjects)
        self.assertTrue(subjects['PMA101BS']['inferred'])
        self.assertFalse(subjects['PCS105ES']['inferred'])
        self.assertEqual(subjects['PMA101BS']['year_sem'], 'I Year I Sem')
        self.assertEqual(subjects['PMA201BS']['year_sem'], 'I Year II Sem')
        self.assertEqual(len(subjects['PMA101BS']['syllabus']['units']), 5)

    def test_unit_parser_accepts_pdf_dash_variants(self) -> None:
        raw_text = '''
PCS205ES: DATA STRUCTURES
B.Tech. I Year II Sem. L T P C
Course Objectives:
 Learn data structures.
Course Outcomes:
 Apply suitable structures.
UNIT – I
Introduction to Data Structures, Arrays, Linked Lists
UNIT - II
Trees, Binary Search Trees
UNIT – III
Graphs, Traversals
TEXT BOOKS:
1. Example Book
'''
        document = ParsedDocument(file_path=Path('sample.pdf'), file_type='pdf', raw_text=raw_text, tables=[], metadata={})

        syllabus = SyllabusParser().parse(document)

        self.assertEqual([unit['unit'] for unit in syllabus['units']], ['Unit I', 'Unit II', 'Unit III'])


if __name__ == '__main__':
    unittest.main()

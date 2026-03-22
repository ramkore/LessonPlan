"""Output formatting templates, column definitions, and display helpers."""
from __future__ import annotations

import re
import textwrap

import pandas as pd

from .utils import LessonPlanBundle

DEPARTMENT_NAMES = {
    'ECE': 'DEPARTMENT OF ELECTRONICS AND COMMUNICATION ENGINEERING',
    'EEE': 'DEPARTMENT OF ELECTRICAL AND ELECTRONICS ENGINEERING',
    'CE': 'DEPARTMENT OF CIVIL ENGINEERING',
    'CSE': 'DEPARTMENT OF COMPUTER SCIENCE AND ENGINEERING',
    'CIVIL': 'DEPARTMENT OF CIVIL ENGINEERING',
    'MECH': 'DEPARTMENT OF MECHANICAL ENGINEERING',
    'AIML': 'DEPARTMENT OF ARTIFICIAL INTELLIGENCE AND MACHINE LEARNING',
    'CSM': 'DEPARTMENT OF COMPUTER SCIENCE AND MACHINE LEARNING',
    'CSD': 'DEPARTMENT OF COMPUTER SCIENCE AND DATA SCIENCE',
}

THEORY_MAIN_COLUMNS = ['Unit No', 'Week', 'Lecture No:', 'Topics to be Covered', 'Planned date', 'Actual Date', 'Text Book', 'Teaching Aids', 'Remarks']
THEORY_MAIN_COLUMN_WIDTHS = [0.45, 0.42, 0.62, 2.52, 0.82, 0.82, 0.48, 0.92, 0.75]
LAB_MAIN_COLUMNS = ['SN No.', 'Exp No:', 'Topics to be Covered', 'Text book', 'Planned date', 'Actual Date', 'Remarks']
LAB_MAIN_COLUMN_WIDTHS = [0.42, 1.10, 3.00, 0.42, 0.78, 0.78, 0.72]
SUMMARY_TABLE_COLUMN_WIDTHS = [0.82, 1.45, 1.00, 1.45, 0.78, 0.85, 0.85]
MAIN_COLUMNS = THEORY_MAIN_COLUMNS
MAIN_COLUMN_WIDTHS = THEORY_MAIN_COLUMN_WIDTHS
SIGN_LABELS = ('FACULTY', 'HOD', 'PRINCIPAL')


def department_name(branch: str) -> str:
    cleaned = branch.strip().upper()
    return DEPARTMENT_NAMES.get(cleaned, f'DEPARTMENT OF {cleaned}' if cleaned else 'DEPARTMENT')


def academic_year(teaching_days: pd.DataFrame) -> str:
    if teaching_days.empty:
        return ''
    start_date = pd.to_datetime(teaching_days['date']).min()
    if pd.isna(start_date):
        return ''
    year = int(start_date.year)
    if int(start_date.month) <= 5:
        return f'{year - 1}-{str(year)[-2:]}'
    return f'{year}-{str(year + 1)[-2:]}'


def is_lab_subject_name(value: str) -> bool:
    cleaned = str(value).strip().lower()
    return any(token in cleaned for token in (' lab', 'laboratory', 'practical')) or cleaned.endswith('lab')


def is_lab_bundle(bundle: LessonPlanBundle) -> bool:
    if bool(bundle.metadata.get('is_lab')):
        return True
    faculty_info = bundle.metadata.get('faculty_info', {})
    return is_lab_subject_name(bundle.metadata.get('course_title', '')) or is_lab_subject_name(faculty_info.get('subject_name', ''))


def summary_values(bundle: LessonPlanBundle) -> dict[str, str]:
    faculty_info = bundle.metadata.get('faculty_info', {})
    branch = str(faculty_info.get('branch', '')).strip()
    section = str(faculty_info.get('section', '')).strip()
    semester = str(faculty_info.get('semester', '')).strip()
    class_sem = ' - '.join(part for part in [_branch_section_label(branch, section), semester] if part)
    faculty_name = str(faculty_info.get('faculty_name', '')).strip()
    designation = str(faculty_info.get('designation', '')).strip()
    faculty_display = '\n'.join(part for part in [faculty_name, designation] if part).strip()
    student_count = str(faculty_info.get('student_count', '')).strip()
    lab_mode = is_lab_bundle(bundle)
    experiment_count = int(bundle.metadata.get('experiment_count', 0) or 0)
    # Use planned_lectures (unique dates) for theory, experiment_count for labs
    planned_lectures = int(bundle.metadata.get('planned_lectures', 0) or 0)
    fallback_count = len(bundle.lesson_plan)
    lecture_count_value = (
        experiment_count
        if lab_mode and experiment_count > 0
        else planned_lectures or fallback_count
    )
    total_classes = str(lecture_count_value) if not bundle.lesson_plan.empty else ''
    tutorial_count = str(int((bundle.lesson_plan.get('Teaching Method', pd.Series(dtype=str)) == 'Problem Solving').sum())) if not bundle.lesson_plan.empty else '0'
    course_title = str(bundle.metadata.get('course_title', faculty_info.get('subject_name', ''))).strip()
    total_label = 'Total Proposed Experiments per semester/year' if lab_mode else 'Total Proposed Periods per semester/year'
    return {
        'course_code': str(bundle.metadata.get('course_code', '')).strip(),
        'course_title': course_title,
        'course_title_display': _wrap_summary_text(course_title, 20),
        'class_sem': class_sem,
        'class_sem_display': _wrap_summary_text(class_sem, 16),
        'faculty_display': faculty_display,
        'faculty_display_summary': _wrap_summary_text(faculty_display, 18),
        'student_count': student_count,
        'lecture_label': 'Lectures',
        'tutorial_label': 'Tutorial',
        'lecture_count': total_classes,
        'tutorial_count': '-' if lab_mode else tutorial_count,
        'total_label': total_label,
        'total_label_display': _wrap_summary_text(total_label, 24),
        'regulation': str(bundle.metadata.get('regulation', '')).strip() or 'R25',
        'academic_year': academic_year(bundle.teaching_days),
        'department_name': department_name(branch),
        'plan_title': 'LESSON PLAN - LAB' if lab_mode else 'LESSON PLAN',
        'sign_line': '     '.join(SIGN_LABELS),
        'sign_labels': SIGN_LABELS,
        'is_lab': lab_mode,
    }


def _branch_section_label(branch: str, section: str) -> str:
    branch_clean = branch.strip().upper()
    section_clean = re.sub(r'(?i)\bsection\b', ' ', section).strip().upper()
    section_token = re.sub(r'[^A-Z0-9]+', '', section_clean)

    if not branch_clean:
        return section_clean
    if not section_token:
        return branch_clean

    combined_compact = re.sub(r'[^A-Z0-9]+', '', f'{branch_clean}-{section_clean}')
    if section_token == re.sub(r'[^A-Z0-9]+', '', branch_clean):
        return branch_clean
    if combined_compact == re.sub(r'[^A-Z0-9]+', '', section_clean):
        return section_clean
    return f'{branch_clean}-{section_token}'


def formatted_lesson_plan_frame(frame: pd.DataFrame, lab_mode: bool = False) -> pd.DataFrame:
    return formatted_lab_lesson_plan_frame(frame) if lab_mode else formatted_theory_lesson_plan_frame(frame)


def formatted_theory_lesson_plan_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Format theory lesson plan: one lecture number per date.

    Key logic:
    - All periods on the same date = ONE lecture row (topics merged in one cell)
    - Unit tests appear as separate rows only when they occur
    - Tutorial/revision/doubt clearance items combined by date
    """
    rows: list[dict[str, str]] = []
    lecture_no = 0

    # Group by date to handle multiple periods per day
    grouped = frame.groupby('Date', sort=False)

    for current_date, date_group in grouped:
        current_date = str(current_date).strip()
        lecture_no += 1

        # Separate unit tests from regular topics within this date
        regular_rows = []
        unit_tests = []

        for _, row in date_group.iterrows():
            topic = str(row.get('Topic', '')).strip()
            teaching_method = str(row.get('Teaching Method', '')).strip()
            is_unit_test = 'unit test' in topic.lower() or teaching_method.lower() == 'unit test'

            if is_unit_test:
                unit_tests.append(row)
            else:
                regular_rows.append(row)

        # Add ONE row for all regular topics on this date (merged)
        if regular_rows:
            first_row = regular_rows[0]
            unit = str(first_row.get('Unit', '')).strip()
            week_value = str(first_row.get('Week', '')).strip()

            # Combine all topics from this date
            topics_list = [str(r.get('Topic', '')).strip() for r in regular_rows]
            combined_topic = ', '.join(t for t in topics_list if t)

            rows.append(
                {
                    'Unit No': unit_suffix(unit),
                    'Week': f'Week {week_value}' if week_value else '',
                    'Lecture No:': str(lecture_no),
                    'Topics to be Covered': combined_topic,
                    'Planned date': current_date,
                    'Actual Date': '',
                    'Text Book': 'T1',
                    'Teaching Aids': 'Block Board and\nPPT',
                    'Remarks': '',
                }
            )

        # Add unit tests as separate rows (keep in same lecture number)
        for ut_row in unit_tests:
            unit = str(ut_row.get('Unit', '')).strip()
            week_value = str(ut_row.get('Week', '')).strip()

            rows.append(
                {
                    'Unit No': unit_suffix(unit),
                    'Week': f'Week {week_value}' if week_value else '',
                    'Lecture No:': str(lecture_no),
                    'Topics to be Covered': f'UNIT TEST - {unit_suffix(unit)}',
                    'Planned date': current_date,
                    'Actual Date': '',
                    'Text Book': 'T1',
                    'Teaching Aids': 'Question Paper and Answer Sheets',
                    'Remarks': 'Assessment',
                }
            )

    return pd.DataFrame(rows, columns=THEORY_MAIN_COLUMNS)


def formatted_lab_lesson_plan_frame(frame: pd.DataFrame) -> pd.DataFrame:
    collapsed = _collapse_lab_rows(_expand_merged_lab_rows(frame))
    rows: list[dict[str, str]] = []
    has_exp_numbers = any(str(item.get('Exp No', '')).strip() for item in collapsed)
    for serial_no, item in enumerate(collapsed, start=1):
        exp_no = str(item.get('Exp No', '')).strip()
        rows.append(
            {
                'SN No.': str(serial_no),
                'Exp No:': exp_no if exp_no or has_exp_numbers else str(serial_no),
                'Topics to be Covered': str(item.get('Topic', '')).strip(),
                'Text book': 'T1',
                'Planned date': str(item.get('Date', '')).strip(),
                'Actual Date': '',
                'Remarks': '',
            }
        )
    return pd.DataFrame(rows, columns=LAB_MAIN_COLUMNS)


def week_row_spans(frame: pd.DataFrame) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    if frame.empty or 'Week' not in frame.columns:
        return spans

    start_index = 0
    current_value = str(frame.iloc[0]['Week']).strip()
    for index in range(1, len(frame)):
        value = str(frame.iloc[index]['Week']).strip()
        if value == current_value:
            continue
        if current_value:
            spans.append((start_index, index - 1, current_value))
        start_index = index
        current_value = value

    if current_value:
        spans.append((start_index, len(frame) - 1, current_value))
    return spans


def lab_date_row_spans(frame: pd.DataFrame) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    if frame.empty or 'Planned date' not in frame.columns:
        return spans

    start_index = 0
    current_value = str(frame.iloc[0]['Planned date']).strip()
    for index in range(1, len(frame)):
        value = str(frame.iloc[index]['Planned date']).strip()
        if value == current_value:
            continue
        if current_value:
            spans.append((start_index, index - 1, current_value))
        start_index = index
        current_value = value

    if current_value:
        spans.append((start_index, len(frame) - 1, current_value))
    return spans


def _collapse_lab_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
    rows = frame.to_dict('records')
    if not rows:
        return []

    collapsed: list[dict[str, str]] = []
    current_group: list[dict[str, str]] = []
    current_key: tuple[str, str] | None = None

    for row in rows:
        exp_no = str(row.get('Exp No', '')).strip()
        topic = str(row.get('Topic', '')).strip()
        key = (exp_no, topic)
        if current_key is None or key == current_key:
            current_group.append(row)
            current_key = key
            continue

        collapsed.append(_merge_lab_group(current_group))
        current_group = [row]
        current_key = key

    if current_group:
        collapsed.append(_merge_lab_group(current_group))
    return collapsed


def _expand_merged_lab_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows = frame.to_dict('records')
    if not rows:
        return frame

    expanded_rows: list[dict[str, str]] = []
    for row in rows:
        exp_values = [item.strip() for item in str(row.get('Exp No', '')).split('+') if item.strip()]
        topic_values = [item.strip() for item in str(row.get('Topic', '')).split(' AND ') if item.strip()]

        if len(exp_values) <= 1 or len(exp_values) != len(topic_values):
            expanded_rows.append(dict(row))
            continue

        for exp_no, topic in zip(exp_values, topic_values):
            expanded_row = dict(row)
            expanded_row['Exp No'] = exp_no
            expanded_row['Topic'] = topic
            expanded_rows.append(expanded_row)

    return pd.DataFrame(expanded_rows, columns=frame.columns)


def _merge_lab_group(rows: list[dict[str, str]]) -> dict[str, str]:
    first = rows[0]
    dates = _unique_values(str(row.get('Date', '')).strip() for row in rows)
    merged = dict(first)
    merged['Date'] = '\n'.join(dates)
    return merged


def _unique_values(values) -> list[str]:
    unique: list[str] = []
    for value in values:
        if value and value not in unique:
            unique.append(value)
    return unique


def unit_suffix(unit: str) -> str:
    cleaned = unit.strip()
    match = re.search(r'([IVX]+|\d+)$', cleaned, flags=re.IGNORECASE)
    if not match:
        return cleaned
    token = match.group(1).upper()
    if token.isdigit():
        return roman(int(token))
    return token


def roman(value: int) -> str:
    numerals = [
        (10, 'X'),
        (9, 'IX'),
        (5, 'V'),
        (4, 'IV'),
        (1, 'I'),
    ]
    remaining = max(value, 0)
    result: list[str] = []
    for number, symbol in numerals:
        while remaining >= number:
            result.append(symbol)
            remaining -= number
    return ''.join(result) or str(value)


def _wrap_summary_text(value: str, width: int) -> str:
    lines: list[str] = []
    for raw_line in str(value).splitlines() or ['']:
        cleaned = re.sub(r'\s+', ' ', raw_line).strip()
        if not cleaned:
            lines.append('')
            continue
        wrapped = textwrap.wrap(cleaned, width=width, break_long_words=False, break_on_hyphens=True)
        lines.extend(wrapped or [cleaned])
    return '\n'.join(lines)

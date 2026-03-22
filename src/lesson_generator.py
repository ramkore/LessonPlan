"""Core lesson plan generation algorithm — scheduling, distribution, and reporting."""
from __future__ import annotations

import re
from collections.abc import Iterable
from itertools import cycle

import pandas as pd

from .logger import get_logger
from .utils import LessonPlanBundle, ProcessingError

logger = get_logger(__name__)


class LessonPlanGenerator:
    extra_session_templates = (
        'Revision and recap for {unit}',
        'Tutorial and problem solving for {unit}',
        'Discussion and doubt clarification for {unit}',
    )

    def generate(
        self,
        teaching_days: pd.DataFrame,
        subject_periods: pd.DataFrame,
        syllabus: dict[str, object],
        faculty_info: dict[str, str],
    ) -> LessonPlanBundle:
        logger.debug(
            "Generating lesson plan: subject=%s, teaching_days=%d",
            faculty_info.get('subject_name', '?'),
            len(teaching_days),
        )
        lab_mode = self._is_lab_syllabus(syllabus, faculty_info)
        experiment_items = self._experiment_items(syllabus) if lab_mode else []
        class_schedule = self.build_class_schedule(teaching_days, subject_periods, faculty_info)

        # For theory syllabi, exclude any entries that are lab periods.
        # This prevents lab periods (e.g. "ECE LAB") from appearing in
        # theory plans even if upstream filtering didn't separate them.
        if not lab_mode and not class_schedule.empty:
            theory_mask = ~(
                class_schedule['is_lab'].astype(bool)
                if 'is_lab' in class_schedule.columns
                else pd.Series(False, index=class_schedule.index)
            )
            if 'entry' in class_schedule.columns:
                entry_has_lab = class_schedule['entry'].str.lower().str.contains(
                    r'\blab\b', na=False, regex=True
                )
                theory_mask = theory_mask & ~entry_has_lab
            theory_schedule = class_schedule[theory_mask]
            if not theory_schedule.empty:
                class_schedule = theory_schedule.reset_index(drop=True)

        if lab_mode:
            class_schedule = self._normalize_lab_schedule(class_schedule, syllabus)
        lesson_plan = self._build_lesson_plan(class_schedule, syllabus)
        active_branches = self._schedule_branches(class_schedule, faculty_info.get('branch', ''))
        monthly_plan = self._build_monthly_plan(lesson_plan)
        coverage_report = self._build_coverage_report(syllabus, lesson_plan, active_branches, faculty_info)

        # Count unique lecture numbers (one per unique date in formatted lesson plan)
        planned_lectures = lesson_plan['Date'].nunique() if not lesson_plan.empty else 0

        metadata = {
            'faculty_info': faculty_info,
            'course_title': syllabus.get('course_title', faculty_info.get('subject_name', '')),
            'course_code': syllabus.get('course_code', ''),
            'regulation': syllabus.get('regulation', ''),
            'text_books': list(syllabus.get('text_books', [])),
            'reference_books': list(syllabus.get('reference_books', [])),
            'course_outcomes': list(syllabus.get('course_outcomes', [])),
            'teaching_days': len(teaching_days),
            'planned_classes': len(class_schedule),
            'planned_lectures': planned_lectures,
            'planned_branches': active_branches,
            'is_lab': lab_mode,
            'experiment_count': len(experiment_items),
        }

        return LessonPlanBundle(
            lesson_plan=lesson_plan,
            monthly_plan=monthly_plan,
            coverage_report=coverage_report,
            class_schedule=class_schedule,
            teaching_days=teaching_days,
            metadata=metadata,
        )

    def build_class_schedule(
        self,
        teaching_days: pd.DataFrame,
        subject_periods: pd.DataFrame,
        faculty_info: dict[str, str],
    ) -> pd.DataFrame:
        if subject_periods.empty:
            raise ProcessingError('No subject periods are available to build the class schedule.')

        rows: list[dict[str, object]] = []
        for day_row in teaching_days.itertuples(index=False):
            matches = subject_periods[subject_periods['day'] == day_row.day].copy()
            if matches.empty:
                continue
            sort_columns = ['period']
            if 'branch' in matches.columns:
                sort_columns.append('branch')
            matches = matches.sort_values(sort_columns, key=lambda series: series.map(self._sort_value))

            for _, subject_row in matches.iterrows():
                rows.append(
                    {
                        'date': day_row.date,
                        'day': day_row.day,
                        'period': subject_row['period'],
                        'week': day_row.week,
                        'month': day_row.month,
                        'spell': getattr(day_row, 'spell', 1),
                        'branch': subject_row.get('branch', faculty_info.get('branch', '')),
                        'entry': subject_row.get('entry', ''),
                        'time_slot': subject_row.get('time_slot', ''),
                        'is_lab': subject_row.get('is_lab', False),
                    }
                )

        schedule = pd.DataFrame(rows)
        if schedule.empty:
            raise ProcessingError('No class schedule could be generated from the teaching days and timetable.')
        return schedule

    def distribute_topics(self, syllabus: dict[str, object], class_count: int) -> list[dict[str, str]]:
        if class_count <= 0:
            raise ProcessingError('Class count must be greater than zero.')

        experiment_items = self._experiment_items(syllabus)
        if experiment_items:
            return self._distribute_experiments(experiment_items, class_count)

        units: list[dict[str, object]] = [unit for unit in syllabus.get('units', []) if unit.get('topics')]
        if not units:
            raise ProcessingError('The syllabus does not contain any topics to schedule.')

        test_count = len(units)
        teaching_slot_count = class_count - test_count
        if teaching_slot_count < len(units):
            raise ProcessingError('Not enough classes are available to schedule one UNIT TEST after each unit.')

        slot_counts = self._allocate_unit_slots(units, teaching_slot_count)
        assignments: list[dict[str, str]] = []

        for unit, slot_count in zip(units, slot_counts):
            assignments.extend(self._shape_unit_sessions(unit, slot_count))
            assignments.append(
                {
                    'unit': str(unit['unit']),
                    'topic': f"UNIT TEST - {unit['unit']}",
                    'co': str(unit.get('co') or 'CO1'),
                    'session_type': 'unit_test',
                }
            )

        if len(assignments) < class_count:
            assignments.extend(self._append_general_extension(units, class_count - len(assignments)))

        return assignments[:class_count]

    def _build_lesson_plan(self, class_schedule: pd.DataFrame, syllabus: dict[str, object]) -> pd.DataFrame:
        assignments = self._topic_assignments(class_schedule, syllabus)
        include_branch = class_schedule['branch'].astype(str).str.strip().any() if 'branch' in class_schedule.columns else False
        include_exp_no = any(str(topic.get('exp_no', '')).strip() for topic in assignments.values())

        lesson_rows: list[dict[str, object]] = []
        for index, schedule_row in class_schedule.iterrows():
            topic_info = assignments[index]
            row = {
                'Week': schedule_row['week'],
                'Date': pd.Timestamp(schedule_row['date']).strftime('%d-%m-%Y'),
                'Day': schedule_row['day'],
                'Period': schedule_row['period'],
                'Unit': topic_info.get('unit', ''),
                'Topic': topic_info['topic'],
                'Teaching Method': self._choose_teaching_method(topic_info),
                'CO': topic_info['co'],
            }
            if include_exp_no:
                row['Exp No'] = topic_info.get('exp_no', '')
            if include_branch:
                row['Branch'] = schedule_row['branch']
            lesson_rows.append(row)

        ordered_columns = ['Week', 'Date', 'Day', 'Period']
        if include_branch:
            ordered_columns.append('Branch')
        ordered_columns.extend(['Unit'])
        if include_exp_no:
            ordered_columns.append('Exp No')
        ordered_columns.extend(['Topic', 'Teaching Method', 'CO'])
        return pd.DataFrame(lesson_rows)[ordered_columns]

    def _topic_assignments(self, class_schedule: pd.DataFrame, syllabus: dict[str, object]) -> dict[int, dict[str, str]]:
        assignments: dict[int, dict[str, str]] = {}
        branches = self._schedule_branches(class_schedule)

        if branches:
            for _branch, frame in class_schedule.groupby('branch', sort=False):
                assignments.update(self._distribute_by_spell(frame, syllabus))
            return assignments

        assignments.update(self._distribute_by_spell(class_schedule, syllabus))
        return assignments

    def _distribute_by_spell(self, schedule: pd.DataFrame, syllabus: dict[str, object]) -> dict[int, dict[str, str]]:
        """Distribute topics across teaching spells so that ~2.5 units complete before Mid 1."""
        assignments: dict[int, dict[str, str]] = {}

        # Fall back to flat distribution when spell info is missing or only one spell
        has_spells = 'spell' in schedule.columns
        spells = sorted(schedule['spell'].unique()) if has_spells else [1]
        is_lab = bool(self._experiment_items(syllabus))

        if len(spells) <= 1 or is_lab:
            topics = self.distribute_topics(syllabus, len(schedule))
            for index, topic in zip(schedule.index.tolist(), topics):
                assignments[index] = topic
            return assignments

        # Split syllabus units across spells: ceil(N/2) units before mid-1, rest after
        units: list[dict[str, object]] = [u for u in syllabus.get('units', []) if u.get('topics')]
        spell_unit_groups = self._split_units_across_spells(units, len(spells))

        # Safety check: each spell needs at least 2*units slots (topics + tests).
        # If any spell is too small, fall back to flat distribution.
        feasible = True
        for spell, unit_group in zip(spells, spell_unit_groups):
            spell_slots = int((schedule['spell'] == spell).sum())
            min_needed = 2 * len(unit_group)  # at least 1 topic + 1 test per unit
            if unit_group and spell_slots < min_needed:
                logger.warning(
                    "Spell %s has %d slots but needs at least %d for %d units — falling back to flat distribution",
                    spell, spell_slots, min_needed, len(unit_group),
                )
                feasible = False
                break

        if not feasible:
            topics = self.distribute_topics(syllabus, len(schedule))
            for index, topic in zip(schedule.index.tolist(), topics):
                assignments[index] = topic
            return assignments

        for spell, unit_group in zip(spells, spell_unit_groups):
            spell_frame = schedule[schedule['spell'] == spell]
            if spell_frame.empty or not unit_group:
                continue

            spell_syllabus = dict(syllabus)
            spell_syllabus['units'] = unit_group
            topics = self.distribute_topics(spell_syllabus, len(spell_frame))
            for index, topic in zip(spell_frame.index.tolist(), topics):
                assignments[index] = topic

        return assignments

    @staticmethod
    def _split_units_across_spells(
        units: list[dict[str, object]], spell_count: int
    ) -> list[list[dict[str, object]]]:
        """Split units into groups per spell.

        For 2 spells (standard mid-term format):
          ceil(N/2) units go to spell 1, remainder to spell 2.
          e.g. 5 units → 3 + 2  (satisfies 2.5-unit rule before Mid-1).
        For 3+ spells: distribute as evenly as possible, extra to earlier spells.
        """
        if spell_count <= 1 or not units:
            return [units]

        unit_count = len(units)
        if spell_count == 2:
            first_half = (unit_count + 1) // 2
            return [units[:first_half], units[first_half:]]

        per_spell = unit_count // spell_count
        remainder = unit_count % spell_count
        groups: list[list[dict[str, object]]] = []
        start = 0
        for i in range(spell_count):
            count = per_spell + (1 if i < remainder else 0)
            groups.append(units[start : start + count])
            start += count
        return groups

    def _allocate_unit_slots(self, units: list[dict[str, object]], teaching_slot_count: int) -> list[int]:
        topic_counts = [max(len(unit.get('topics', [])), 1) for unit in units]
        total_topics = sum(topic_counts)
        unit_count = len(units)

        if teaching_slot_count >= total_topics:
            counts = topic_counts[:]
            extra = teaching_slot_count - total_topics
            index = 0
            while extra > 0:
                counts[index % unit_count] += 1
                index += 1
                extra -= 1
            return counts

        counts = [1] * unit_count
        remaining = teaching_slot_count - unit_count
        backlogs = [count - 1 for count in topic_counts]

        while remaining > 0:
            target_index = max(range(unit_count), key=lambda idx: (backlogs[idx], topic_counts[idx], -idx))
            counts[target_index] += 1
            if backlogs[target_index] > 0:
                backlogs[target_index] -= 1
            remaining -= 1
        return counts

    def _shape_unit_sessions(self, unit: dict[str, object], slot_count: int) -> list[dict[str, str]]:
        topic_items = [
            {'unit': str(unit['unit']), 'topic': str(topic), 'co': str(unit.get('co') or 'CO1'), 'session_type': 'topic'}
            for topic in unit.get('topics', [])
        ]
        topic_items = self._merge_unclosed_parens(topic_items)

        if len(topic_items) > slot_count:
            return self._merge_topic_items(topic_items, slot_count, str(unit['unit']), str(unit.get('co') or 'CO1'))
        if len(topic_items) < slot_count:
            return self._extend_unit_with_revision(topic_items, unit, slot_count)
        return topic_items

    def _merge_unclosed_parens(self, items: list[dict[str, str]]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        buffer: dict[str, str] | None = None
        for item in items:
            if buffer is None:
                buffer = dict(item)
            else:
                buffer['topic'] += ', ' + item['topic']
            if buffer['topic'].count('(') == buffer['topic'].count(')'):
                result.append(buffer)
                buffer = None
        if buffer is not None:
            result.append(buffer)
        return result

    def _merge_topic_items(self, topics: list[dict[str, str]], slot_count: int, unit_name: str, co: str) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        base_size = len(topics) // slot_count
        remainder = len(topics) % slot_count
        start = 0
        for index in range(slot_count):
            size = base_size + (1 if index < remainder else 0)
            chunk = topics[start : start + size]
            start += size
            merged.append(
                {
                    'unit': unit_name,
                    'topic': ' + '.join(item['topic'] for item in chunk),
                    'co': co,
                    'session_type': 'topic',
                }
            )
        return merged

    def _extend_unit_with_revision(
        self,
        topics: list[dict[str, str]],
        unit: dict[str, object],
        slot_count: int,
    ) -> list[dict[str, str]]:
        extended = list(topics)
        template_cycle = cycle(self.extra_session_templates)
        while len(extended) < slot_count:
            template = next(template_cycle)
            extended.append(
                {
                    'unit': str(unit['unit']),
                    'topic': template.format(unit=unit['unit']),
                    'co': str(unit.get('co') or 'CO1'),
                    'session_type': 'revision',
                }
            )
        return extended

    def _append_general_extension(self, units: list[dict[str, object]], extra_count: int) -> list[dict[str, str]]:
        extras: list[dict[str, str]] = []
        unit_cycle = cycle(units)
        template_cycle = cycle(self.extra_session_templates)
        while len(extras) < extra_count:
            unit = next(unit_cycle)
            template = next(template_cycle)
            extras.append(
                {
                    'unit': str(unit['unit']),
                    'topic': template.format(unit=unit['unit']),
                    'co': str(unit.get('co') or 'CO1'),
                    'session_type': 'revision',
                }
            )
        return extras

    def _experiment_items(self, syllabus: dict[str, object]) -> list[dict[str, str]]:
        experiments = [item for item in syllabus.get('experiments', []) if str(item.get('topic', '')).strip()]
        if experiments:
            return [
                {
                    'unit': 'Lab',
                    'exp_no': str(item.get('exp_no', '')).strip(),
                    'topic': str(item.get('topic', '')).strip(),
                    'co': 'CO1',
                    'session_type': 'lab',
                }
                for item in experiments
            ]

        course_title = str(syllabus.get('course_title', '')).lower()
        if 'lab' not in course_title and 'laboratory' not in course_title and 'practical' not in course_title:
            return []

        flat_topics = [item for item in syllabus.get('flat_topics', []) if str(item.get('topic', '')).strip()]
        return [
            {
                'unit': 'Lab',
                'exp_no': str(index),
                'topic': str(item.get('topic', '')).strip(),
                'co': str(item.get('co') or 'CO1'),
                'session_type': 'lab',
            }
            for index, item in enumerate(flat_topics, start=1)
        ]

    def _distribute_experiments(self, experiments: list[dict[str, str]], class_count: int) -> list[dict[str, str]]:
        if not experiments:
            raise ProcessingError('The lab syllabus does not contain experiments to schedule.')
        if class_count > len(experiments):
            return self._expand_experiments_across_sessions(experiments, class_count)
        if class_count == len(experiments):
            return [dict(item) for item in experiments]
        return self._merge_experiment_items(experiments, class_count)

    def _merge_experiment_items(self, experiments: list[dict[str, str]], class_count: int) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        base_size = len(experiments) // class_count
        remainder = len(experiments) % class_count
        start = 0
        for index in range(class_count):
            size = base_size + (1 if index < remainder else 0)
            chunk = experiments[start : start + size]
            start += size
            exp_no = ' + '.join(item['exp_no'] for item in chunk if str(item.get('exp_no', '')).strip())
            topic = ' AND '.join(item['topic'] for item in chunk if str(item.get('topic', '')).strip())
            merged.append(
                {
                    'unit': 'Lab',
                    'exp_no': exp_no,
                    'topic': topic,
                    'co': chunk[0].get('co', 'CO1'),
                    'session_type': 'lab',
                }
            )
        return merged

    def _append_lab_extension(self, extra_count: int, co: str) -> list[dict[str, str]]:
        templates = cycle(
            (
                'Record Work and Observation Review',
                'Debugging, Corrections and Completion',
                'Lab Viva and Final Demonstration',
            )
        )
        extras: list[dict[str, str]] = []
        while len(extras) < extra_count:
            extras.append(
                {
                    'unit': 'Lab',
                    'exp_no': '',
                    'topic': next(templates),
                    'co': co,
                    'session_type': 'lab',
                }
            )
        return extras

    def _expand_experiments_across_sessions(self, experiments: list[dict[str, str]], class_count: int) -> list[dict[str, str]]:
        base_count = class_count // len(experiments)
        remainder = class_count % len(experiments)

        assignments: list[dict[str, str]] = []
        for index, experiment in enumerate(experiments):
            repeat_count = base_count + (1 if index < remainder else 0)
            assignments.extend(dict(experiment) for _ in range(repeat_count))
        return assignments[:class_count]

    def _normalize_lab_schedule(self, class_schedule: pd.DataFrame, syllabus: dict[str, object]) -> pd.DataFrame:
        if class_schedule.empty:
            return class_schedule

        # Priority 0: If any entries have the explicit is_lab flag, use ONLY those.
        if 'is_lab' in class_schedule.columns:
            lab_flagged = class_schedule[class_schedule['is_lab'] == True]  # noqa: E712
            if not lab_flagged.empty:
                session_schedule = self._collapse_lab_schedule(lab_flagged.reset_index(drop=True))
                return session_schedule.reset_index(drop=True)

        # Priority 1: If any entries have "lab" in the entry text, use only those.
        # This handles faculty timetables where lab slots are explicitly marked
        # (e.g. "ECE LAB") alongside theory slots (e.g. "ECE").
        if 'entry' in class_schedule.columns:
            lab_mask = class_schedule['entry'].str.lower().str.contains('lab', na=False)
            if lab_mask.any():
                filtered = class_schedule[lab_mask].reset_index(drop=True)
                session_schedule = self._collapse_lab_schedule(filtered)
                return session_schedule.reset_index(drop=True)

        # Priority 2: Filter to only keep days with consecutive period blocks
        # (actual lab sessions). Single-period entries are likely theory classes.
        filtered = self._filter_lab_session_days(class_schedule)
        session_schedule = self._collapse_lab_schedule(filtered)
        return session_schedule.reset_index(drop=True)

    def _filter_lab_session_days(self, class_schedule: pd.DataFrame) -> pd.DataFrame:
        """Keep only entries on days that have consecutive period blocks (lab sessions).

        In a faculty timetable, single isolated periods are likely theory classes
        while consecutive period blocks (P1+P2, P5+P6+P7, etc.) indicate lab sessions.
        If no consecutive blocks are found, all entries are returned as-is.
        """
        group_cols = ['date']
        if 'branch' in class_schedule.columns:
            group_cols = ['date', 'branch']

        keep_indices: list = []
        non_consecutive_indices: list = []

        for _, group in class_schedule.groupby(group_cols, sort=False):
            if len(group) < 2:
                non_consecutive_indices.extend(group.index.tolist())
                continue

            # Extract period numbers and sort
            period_nums = []
            for idx, row in group.iterrows():
                num = self._extract_period_number(str(row['period']))
                period_nums.append((num, idx))
            period_nums.sort(key=lambda x: x[0])

            # Find indices belonging to consecutive period blocks
            consecutive = set()
            for i in range(len(period_nums) - 1):
                if period_nums[i + 1][0] - period_nums[i][0] == 1:
                    consecutive.add(period_nums[i][1])
                    consecutive.add(period_nums[i + 1][1])

            if consecutive:
                keep_indices.extend(sorted(consecutive))
            else:
                non_consecutive_indices.extend(group.index.tolist())

        if not keep_indices:
            # No consecutive blocks found anywhere; use all entries as fallback
            return class_schedule

        return class_schedule.loc[keep_indices].reset_index(drop=True)

    @staticmethod
    def _extract_period_number(period_str: str) -> int:
        digits = ''.join(c for c in period_str if c.isdigit())
        return int(digits) if digits else 999

    def _collapse_lab_schedule(self, class_schedule: pd.DataFrame) -> pd.DataFrame:
        rows = class_schedule.to_dict('records')
        if not rows:
            return class_schedule

        collapsed_rows: list[dict[str, object]] = []
        current_group: list[dict[str, object]] = []
        current_key: tuple[object, str] | None = None

        for row in rows:
            key = (row.get('date'), str(row.get('branch', '')).strip())
            if current_key is None or key == current_key:
                current_group.append(row)
                current_key = key
                continue

            collapsed_rows.append(self._merge_lab_schedule_rows(current_group))
            current_group = [row]
            current_key = key

        if current_group:
            collapsed_rows.append(self._merge_lab_schedule_rows(current_group))

        return pd.DataFrame(collapsed_rows)

    def _merge_lab_schedule_rows(self, rows: list[dict[str, object]]) -> dict[str, object]:
        merged = dict(rows[0])
        if len(rows) == 1:
            return merged

        merged['period'] = ' / '.join(self._collect_unique_schedule_values(rows, 'period'))
        merged['entry'] = ' / '.join(self._collect_unique_schedule_values(rows, 'entry'))
        merged['time_slot'] = ' / '.join(self._collect_unique_schedule_values(rows, 'time_slot'))
        return merged

    def _collect_unique_schedule_values(self, rows: list[dict[str, object]], key: str) -> list[str]:
        values: list[str] = []
        for row in rows:
            value = str(row.get(key, '')).strip()
            if value and value not in values:
                values.append(value)
        return values


    def _build_monthly_plan(self, lesson_plan: pd.DataFrame) -> pd.DataFrame:
        if lesson_plan.empty:
            return pd.DataFrame(columns=['Month', 'Units Covered', 'Classes Planned'])

        dated = lesson_plan.copy()
        dated['DateObject'] = pd.to_datetime(dated['Date'], dayfirst=True)
        dated['Month'] = dated['DateObject'].dt.strftime('%B %Y')

        rows: list[dict[str, object]] = []
        group_columns = ['Month']
        if 'Branch' in dated.columns:
            group_columns = ['Branch', 'Month']

        for group_keys, frame in dated.groupby(group_columns, sort=False):
            units = self._unique_units(frame['Unit'])
            if isinstance(group_keys, tuple) and len(group_keys) == 2:
                branch, month = group_keys
            elif isinstance(group_keys, tuple):
                branch, month = '', group_keys[0]
            else:
                branch, month = '', group_keys

            row = {
                'Month': month,
                'Units Covered': ', '.join(units),
                'Classes Planned': len(frame),
            }
            if branch:
                row['Branch'] = branch
            rows.append(row)

        if rows and 'Branch' in rows[0]:
            return pd.DataFrame(rows)[['Branch', 'Month', 'Units Covered', 'Classes Planned']]
        return pd.DataFrame(rows)

    def _build_coverage_report(
        self,
        syllabus: dict[str, object],
        lesson_plan: pd.DataFrame,
        branches: list[str],
        faculty_info: dict[str, str],
    ) -> pd.DataFrame:
        if self._is_lab_syllabus(syllabus, faculty_info):
            return self._build_lab_coverage_report(syllabus, lesson_plan, branches, faculty_info)

        units: list[dict[str, object]] = list(syllabus.get('units', []))
        rows = []

        if branches:
            for branch in branches:
                for unit in units:
                    total_topics = len(unit.get('topics', []))
                    rows.append(
                        {
                            'Branch': self._coverage_branch_label(branch, faculty_info),
                            'Unit': unit['unit'],
                            'Total Topics': total_topics,
                            'Completed': total_topics,
                            'Remaining': 0,
                        }
                    )
            return pd.DataFrame(rows)

        for unit in units:
            total_topics = len(unit.get('topics', []))
            rows.append(
                {
                    'Unit': unit['unit'],
                    'Total Topics': total_topics,
                    'Completed': total_topics,
                    'Remaining': 0,
                }
            )
        return pd.DataFrame(rows)

    def _build_lab_coverage_report(
        self,
        syllabus: dict[str, object],
        lesson_plan: pd.DataFrame,
        branches: list[str],
        faculty_info: dict[str, str],
    ) -> pd.DataFrame:
        experiments = self._experiment_items(syllabus)
        columns = ['Branch', 'Unit', 'Total Topics', 'Completed', 'Remaining'] if branches else ['Unit', 'Total Topics', 'Completed', 'Remaining']
        if not experiments:
            return pd.DataFrame(columns=columns)

        as_of_date = pd.Timestamp.today().normalize()
        report_rows: list[dict[str, object]] = []

        if 'Branch' in lesson_plan.columns and lesson_plan['Branch'].astype(str).str.strip().any():
            grouped_frames = list(lesson_plan.groupby('Branch', sort=False))
        elif branches:
            grouped_frames = [(branch, lesson_plan.copy()) for branch in branches]
        else:
            grouped_frames = [('', lesson_plan)]

        total_experiments = len(experiments)
        for raw_branch, frame in grouped_frames:
            completed = self._completed_lab_experiment_count(frame, experiments, as_of_date)
            row = {
                'Unit': 'Lab Experiments',
                'Total Topics': total_experiments,
                'Completed': completed,
                'Remaining': max(total_experiments - completed, 0),
            }
            branch_label = self._coverage_branch_label(str(raw_branch), faculty_info)
            if branch_label:
                row['Branch'] = branch_label
            report_rows.append(row)

        if report_rows and 'Branch' in report_rows[0]:
            return pd.DataFrame(report_rows)[['Branch', 'Unit', 'Total Topics', 'Completed', 'Remaining']]
        return pd.DataFrame(report_rows)[['Unit', 'Total Topics', 'Completed', 'Remaining']]

    def _completed_lab_experiment_count(
        self,
        lesson_plan: pd.DataFrame,
        experiments: list[dict[str, str]],
        as_of_date: pd.Timestamp,
    ) -> int:
        expected_ids = [self._experiment_identifier(item, index) for index, item in enumerate(experiments, start=1)]
        expected_set = set(expected_ids)
        latest_dates = {identifier: pd.NaT for identifier in expected_ids}

        for row in lesson_plan.to_dict('records'):
            row_date = pd.to_datetime(str(row.get('Date', '')).strip(), dayfirst=True, errors='coerce')
            if pd.isna(row_date):
                continue

            identifiers = self._lesson_row_experiment_identifiers(row, expected_set)
            for identifier in identifiers:
                current = latest_dates.get(identifier)
                if pd.isna(current) or row_date > current:
                    latest_dates[identifier] = row_date

        return sum(1 for value in latest_dates.values() if pd.notna(value) and value.normalize() <= as_of_date)

    def _lesson_row_experiment_identifiers(self, row: dict[str, object], expected_ids: set[str]) -> list[str]:
        raw_exp_no = str(row.get('Exp No', '')).strip()
        if raw_exp_no:
            identifiers = [
                token
                for token in (part.strip() for part in raw_exp_no.split('+'))
                if token and token in expected_ids
            ]
            if identifiers:
                return identifiers

        topic_key = self._experiment_topic_key(str(row.get('Topic', '')).strip())
        if not topic_key:
            return []
        return [identifier for identifier in expected_ids if identifier.startswith('__topic__:') and identifier == topic_key]

    def _experiment_identifier(self, experiment: dict[str, str], index: int) -> str:
        exp_no = str(experiment.get('exp_no', '')).strip()
        if exp_no:
            return exp_no
        topic_key = self._experiment_topic_key(str(experiment.get('topic', '')).strip())
        return topic_key or f'__experiment__:{index}'

    def _experiment_topic_key(self, topic: str) -> str:
        cleaned = re.sub(r'\s+', ' ', str(topic).strip()).lower()
        return f'__topic__:{cleaned}' if cleaned else ''

    def _coverage_branch_label(self, branch: str, faculty_info: dict[str, str]) -> str:
        branch_clean = branch.strip().upper() or str(faculty_info.get('branch', '')).strip().upper()
        section_clean = re.sub(r'(?i)\bsection\b', ' ', str(faculty_info.get('section', '')).strip()).strip().upper()
        section_token = re.sub(r'[^A-Z0-9]+', '', section_clean)

        if not branch_clean:
            return section_clean
        if not section_token:
            return branch_clean

        branch_token = re.sub(r'[^A-Z0-9]+', '', branch_clean)
        combined_compact = re.sub(r'[^A-Z0-9]+', '', f'{branch_clean}-{section_clean}')
        if section_token == branch_token:
            return branch_clean
        if combined_compact == re.sub(r'[^A-Z0-9]+', '', section_clean):
            return section_clean
        return f'{branch_clean}-{section_token}'

    def _choose_teaching_method(self, topic_info: dict[str, str] | str) -> str:
        if isinstance(topic_info, dict):
            lowered = str(topic_info.get('topic', '')).lower()
            session_type = str(topic_info.get('session_type', '')).lower()
        else:
            lowered = str(topic_info).lower()
            session_type = ''

        if session_type == 'lab':
            return 'Practical'
        if session_type == 'unit_test' or 'unit test' in lowered:
            return 'Unit Test'
        if any(keyword in lowered for keyword in ('lab', 'program', 'coding', 'demonstration', 'simulation')):
            return 'Demonstration'
        if any(keyword in lowered for keyword in ('problem', 'exercise', 'numerical', 'tutorial')):
            return 'Problem Solving'
        if any(keyword in lowered for keyword in ('discussion', 'revision', 'recap', 'doubt')):
            return 'Discussion'
        return 'Lecture'

    def _is_lab_syllabus(self, syllabus: dict[str, object], faculty_info: dict[str, str]) -> bool:
        if syllabus.get('experiments'):
            return True
        course_title = str(syllabus.get('course_title', faculty_info.get('subject_name', ''))).lower()
        return any(token in course_title for token in (' lab', 'laboratory', 'practical')) or course_title.endswith('lab')

    def _period_sort_key(self, value: str) -> tuple[int, str]:
        digits = ''.join(character for character in str(value) if character.isdigit())
        return (int(digits) if digits else 999, value)

    def _sort_value(self, value):
        if isinstance(value, str) and value.startswith('P'):
            return self._period_sort_key(value)
        return (999, str(value))

    def _unique_units(self, units: Iterable[str]) -> list[str]:
        ordered: list[str] = []
        for value in units:
            for unit in str(value).split('/'):
                cleaned = unit.strip()
                if cleaned and cleaned not in ordered:
                    ordered.append(cleaned)
        return ordered

    def _schedule_branches(self, class_schedule: pd.DataFrame, fallback_branch: str = '') -> list[str]:
        if 'branch' not in class_schedule.columns:
            return [fallback_branch] if fallback_branch.strip() else []

        branches = [str(value).strip() for value in class_schedule['branch'].tolist() if str(value).strip()]
        ordered: list[str] = []
        for branch in branches:
            if branch not in ordered:
                ordered.append(branch)
        return ordered or ([fallback_branch] if fallback_branch.strip() else [])

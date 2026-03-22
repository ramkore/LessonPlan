"""PyQt6 main window — orchestration, layout, and event handling."""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

import pandas as pd

from .calendar_processor import CalendarProcessor
from .course_catalog import CourseCatalogParser
from .export_excel import export_bundle_to_excel
from .export_pdf import export_bundle_to_pdf
from .export_word import export_bundle_to_word
from .file_detector import validate_file_type
from .lesson_generator import LessonPlanGenerator
from .logger import get_logger
from .syllabus_parser import SyllabusParser
from .theme import PALETTE, SPACING, load_stylesheet
from .timetable_parser import TimeTableParser
from .utils import (
    LessonPlanBundle,
    ParsedDocument,
    ProcessingError,
    ensure_directories,
    load_parsed_document,
    persist_uploaded_file,
    project_root,
)
from .widgets import ElevatedPanel, PandasTableModel, SummaryChip, UploadCard, refresh_widget_style

logger = get_logger(__name__)

from PyQt6.QtCore import QProcess, Qt, QThread, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QColor, QFont  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__

APP_META = {
    "name": "AI Lesson Plan Automation",
    "version": f"v{__version__}",
}

UPLOAD_HINTS = {
    "academic_calendar": "Semester calendar or academic schedule document.",
    "holiday_list": "Official holidays list, notice, or tabular extract.",
    "syllabus": "Course structure, subject syllabus, or catalog extract.",
    "timetable": "Class timetable or individual faculty timetable.",
}

SUPPORTED_FILE_TEXT = "PDF, DOCX, TXT, JPG, JPEG, PNG, XLSX, CSV"


class _GenerationWorker(QThread):
    """Runs lesson plan generation off the main thread."""

    finished = pyqtSignal(object)  # emits LessonPlanBundle
    failed = pyqtSignal(str)  # emits error message

    def __init__(
        self,
        input_files: dict[str, Path | None],
        parsed_documents: dict[str, ParsedDocument | None],
        upload_labels: dict[str, str],
        subject_name: str,
        faculty_info_snapshot: dict[str, str],
        syllabus_record: dict | None,
    ) -> None:
        super().__init__()
        self._input_files = input_files
        self._parsed_documents = dict(parsed_documents)
        self._upload_labels = upload_labels
        self._subject_name = subject_name
        self._faculty_info_snapshot = faculty_info_snapshot
        self._syllabus_record = syllabus_record

    def run(self) -> None:
        try:
            keys = ('academic_calendar', 'holiday_list', 'syllabus', 'timetable')
            resolved: dict[str, ParsedDocument] = {}
            missing_paths: dict[str, Path] = {}

            for key in keys:
                parsed = self._parsed_documents.get(key)
                if parsed is not None:
                    resolved[key] = parsed
                    continue
                path = self._input_files.get(key)
                if path is None:
                    self.failed.emit(f"{self._upload_labels[key]} is missing.")
                    return
                missing_paths[key] = path

            if len(missing_paths) == 1:
                key, path = next(iter(missing_paths.items()))
                resolved[key] = load_parsed_document(path)
            elif missing_paths:
                with ThreadPoolExecutor(max_workers=min(4, len(missing_paths))) as executor:
                    future_map = {
                        executor.submit(load_parsed_document, path): key
                        for key, path in missing_paths.items()
                    }
                    for future in as_completed(future_map):
                        key = future_map[future]
                        resolved[key] = future.result()

            for key in keys:
                if key not in resolved:
                    self.failed.emit(f"{self._upload_labels[key]} could not be parsed.")
                    return

            calendar_processor = CalendarProcessor()
            teaching_days = calendar_processor.build_teaching_days(
                resolved['academic_calendar'], resolved['holiday_list']
            )

            timetable_parser = TimeTableParser()
            subject_periods = timetable_parser.extract_subject_periods(
                resolved['timetable'],
                self._subject_name,
                self._faculty_info_snapshot.get('faculty_name', ''),
                self._faculty_info_snapshot.get('branch', ''),
            )

            if self._syllabus_record and isinstance(self._syllabus_record.get('syllabus'), dict):
                syllabus = dict(self._syllabus_record['syllabus'])
            else:
                syllabus = SyllabusParser().parse(resolved['syllabus'])

            course_title = str(syllabus.get('course_title', self._subject_name)).strip() or self._subject_name
            course_code = str(syllabus.get('course_code', '')).strip()
            faculty_info = dict(self._faculty_info_snapshot)
            faculty_info['subject_name'] = course_title
            faculty_info['course_code'] = course_code

            generator = LessonPlanGenerator()
            bundle = generator.generate(teaching_days, subject_periods, syllabus, faculty_info)
            self._resolved = resolved
            self.finished.emit(bundle)
        except ProcessingError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            logger.exception("Unexpected error during lesson plan generation: %s", exc)
            self.failed.emit(f"Unexpected error: {exc}")


class LessonPlanWindow(QMainWindow):
    upload_labels = {
        "academic_calendar": "Academic Calendar",
        "holiday_list": "Holiday List",
        "syllabus": "Subject Syllabus",
        "timetable": "Class / Individual Time Table",
    }

    def __init__(self) -> None:
        super().__init__()
        ensure_directories()
        self.bundle: LessonPlanBundle | None = None
        self.is_generating = False
        self.input_files: dict[str, Path | None] = {key: None for key in self.upload_labels}
        self.parsed_documents: dict[str, ParsedDocument | None] = {key: None for key in self.upload_labels}
        self.input_summaries: dict[str, str] = {key: "No file selected yet." for key in self.upload_labels}
        self.input_errors: dict[str, str] = {}
        self.upload_cards: dict[str, UploadCard] = {}
        self.preview_models: dict[str, PandasTableModel] = {}
        self.preview_tables: dict[str, QTableView] = {}
        self.summary_chips: dict[str, SummaryChip] = {}
        self.syllabus_catalog: list[dict[str, object]] = []
        self.install_process: QProcess | None = None
        self._generation_worker: _GenerationWorker | None = None
        self.last_export_directory = project_root() / "output"

        self.setWindowTitle("AI Lesson Plan Generator")
        self.resize(1520, 940)
        self.setMinimumSize(1280, 800)
        self.setFont(QFont("Segoe UI", 10))

        self._build_ui()
        self._apply_styles()
        self._populate_section_options()
        self._install_field_watchers()
        self._setup_accessibility()
        self._initialize_empty_previews()
        self._refresh_ui_state()

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("MainSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(12)
        splitter.addWidget(self._build_workflow_column())
        splitter.addWidget(self._build_workspace_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([418, 992])
        root_layout.addWidget(splitter, stretch=1)

        status_bar = QStatusBar()
        status_bar.setObjectName("AppStatusBar")
        status_bar.setSizeGripEnabled(False)
        self.status_version_label = QLabel(APP_META["version"])
        self.status_version_label.setObjectName("StatusBarVersion")
        status_bar.addPermanentWidget(self.status_version_label)
        status_bar.showMessage("Ready")
        self.setStatusBar(status_bar)

    def _build_top_bar(self) -> QWidget:
        top_bar = ElevatedPanel("TopBar", "topbar")
        top_bar.setMinimumHeight(56)

        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        # Hidden attributes — updated at runtime
        self.topbar_title_label = QLabel(APP_META["name"])
        self.topbar_subtitle_label = QLabel()
        self.topbar_formula_badge = QLabel()
        self.topbar_export_badge = QLabel()
        self.topbar_status_badge = QLabel()
        self.topbar_status_badge.setObjectName("TopBarStatus")
        self.topbar_status_badge.setProperty("tone", "info")

        # Hidden status strip attributes — updated at runtime by _set_status_strip
        self.status_strip = ElevatedPanel("StatusStrip", "status-strip")
        self.status_strip.setProperty("tone", "info")
        self.status_icon_label = QLabel()
        self.status_strip_title = QLabel()
        self.status_strip_detail = QLabel()

        self.open_templates_button = QPushButton("  Templates")
        self.open_templates_button.setObjectName("SecondaryButton")
        self.open_templates_button.setMinimumHeight(38)
        self.open_templates_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.open_templates_button.setToolTip("Open the templates folder with sample input files")
        self.open_templates_button.clicked.connect(self._open_templates_folder)

        self.install_requirements_button = QPushButton("Install Requirements")
        self.install_requirements_button.setObjectName("SecondaryButton")
        self.install_requirements_button.setMinimumHeight(38)
        self.install_requirements_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_BrowserReload))
        self.install_requirements_button.clicked.connect(self._install_requirements)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setObjectName("TopBarSeparator")

        self.export_pdf_button = QPushButton("Download Lesson Plan")
        self.export_pdf_button.setObjectName("AccentButton")
        self.export_pdf_button.setMinimumHeight(38)
        self.export_pdf_button.clicked.connect(self._export_pdf)

        self.export_excel_button = QPushButton("Excel")
        self.export_excel_button.setObjectName("SecondaryButton")
        self.export_excel_button.setMinimumHeight(38)
        self.export_excel_button.clicked.connect(self._export_excel)

        self.export_word_button = QPushButton("Word")
        self.export_word_button.setObjectName("SecondaryButton")
        self.export_word_button.setMinimumHeight(38)
        self.export_word_button.clicked.connect(self._export_word)

        layout.addWidget(self.export_pdf_button)
        layout.addStretch(1)
        layout.addWidget(separator)
        layout.addWidget(self.open_templates_button)
        layout.addWidget(self.install_requirements_button)
        return top_bar

    def _build_workflow_column(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("WorkflowScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(400)
        scroll.setMaximumWidth(448)

        content = QWidget()
        content.setAutoFillBackground(False)
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 2, 12, 2)
        layout.setSpacing(SPACING["section"])
        layout.addWidget(self._build_upload_panel())
        layout.addWidget(self._build_faculty_panel())
        layout.addStretch(1)

        scroll.setWidget(content)
        return scroll

    def _build_workspace_panel(self) -> QWidget:
        workspace = ElevatedPanel("WorkspacePanel", "workspace")
        self._apply_shadow(workspace, blur=34, y_offset=14, alpha=0.12)

        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Keep as hidden attributes — updated at runtime
        self.workspace_title_label = QLabel()
        self.workspace_subtitle_label = QLabel()
        self.workspace_badge = QLabel()

        self.summary_strip = QWidget()
        self.summary_strip.setObjectName("SummaryStrip")
        summary_layout = QHBoxLayout(self.summary_strip)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)

        for key, label in (
            ("planned_lectures", "Planned Lectures"),
            ("teaching_days", "Teaching Days"),
            ("branches", "Active Branches"),
            ("deliverables", "Deliverables"),
        ):
            chip = SummaryChip(label)
            self.summary_chips[key] = chip
            summary_layout.addWidget(chip)
            self._apply_shadow(chip, blur=16, y_offset=6, alpha=0.08)

        self.preview_stack = QStackedWidget()
        self.empty_state_page = self._build_empty_state_page()
        self.results_page = self._build_results_page()
        self.preview_stack.addWidget(self.empty_state_page)
        self.preview_stack.addWidget(self.results_page)

        layout.addWidget(self.summary_strip)
        layout.addWidget(self.preview_stack, stretch=1)
        return workspace

    def _build_upload_panel(self) -> QWidget:
        panel, layout = self._create_panel(
            "INPUT FILES",
            "Add the required academic source files.",
        )

        for key, label in self.upload_labels.items():
            card = UploadCard(
                label,
                UPLOAD_HINTS[key],
                "Choose File",
                self._standard_icon(QStyle.StandardPixmap.SP_DialogOpenButton),
            )
            card.button.clicked.connect(partial(self._select_file, key))
            self.upload_cards[key] = card
            layout.addWidget(card)
            self._apply_shadow(card, blur=18, y_offset=7, alpha=0.07)
        return panel

    def _build_faculty_panel(self) -> QWidget:
        panel, layout = self._create_panel("SETTINGS")

        self.faculty_name_input = QLineEdit()
        self.faculty_name_input.setPlaceholderText("Faculty name")

        self.designation_input = QComboBox()
        self.designation_input.addItems(["Assistant Professor", "Associate Professor", "Professor"])
        self.designation_input.setCurrentIndex(0)

        self.subject_name_input = QComboBox()
        self.subject_name_input.setEditable(True)
        self.subject_name_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.subject_name_input.lineEdit().setPlaceholderText("Subject name")

        self.branch_input = QLineEdit()
        self.branch_input.setPlaceholderText("CSE / ECE / branch")

        self.semester_input = QComboBox()
        self.semester_input.setEditable(True)
        self.semester_input.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.semester_input.lineEdit().setPlaceholderText("I-I / II-II / Year-Sem")
        self.semester_input.currentTextChanged.connect(self._refresh_subject_options)

        self.section_input = QComboBox()

        for widget in (
            self.faculty_name_input,
            self.designation_input,
            self.subject_name_input,
            self.branch_input,
            self.semester_input,
            self.section_input,
        ):
            widget.setObjectName("DataField")
            widget.setMinimumHeight(36)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(1, 1)

        field_rows = [
            ("Faculty", self.faculty_name_input),
            ("Designation", self.designation_input),
            ("Subject", self.subject_name_input),
            ("Department", self.branch_input),
            ("Year & Sem", self.semester_input),
            ("Section", self.section_input),
        ]

        for row_index, (label_text, field_widget) in enumerate(field_rows):
            label = QLabel(label_text)
            label.setObjectName("FieldLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            label.setMinimumWidth(96)
            grid.addWidget(label, row_index, 0)
            grid.addWidget(field_widget, row_index, 1)

        layout.addLayout(grid)

        self.generate_button = QPushButton("  Generate Lesson Plan")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.setIcon(self._standard_icon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.generate_button.clicked.connect(self._generate_lesson_plan)
        self.generate_button.setStyleSheet(
            f"QPushButton {{ background: {PALETTE['primary']}; color: #fff; font-size: 13px; font-weight: 700; border-radius: 8px; }}"
            f"QPushButton:hover {{ background: {PALETTE['primary_hover']}; }}"
            f"QPushButton:disabled {{ background: #1c2430; color: #667385; }}"
        )
        layout.addWidget(self.generate_button)
        return panel

    def _build_empty_state_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(16)
        layout.addStretch(1)

        card = ElevatedPanel("EmptyStateCard", "empty")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(12)

        icon_label = QLabel()
        icon_label.setObjectName("EmptyStateIcon")
        icon_label.setPixmap(self._standard_icon(QStyle.StandardPixmap.SP_MessageBoxInformation).pixmap(54, 54))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Preview will appear here")
        title.setObjectName("EmptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body = QLabel(
            "Load the required inputs, confirm faculty details, and generate the lesson plan to unlock the live preview workspace."
        )
        body.setObjectName("EmptyStateBody")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)

        steps = QLabel(
            "1. Upload academic calendar, holiday list, syllabus, and timetable.\n"
            "2. Confirm subject metadata in the workflow rail.\n"
            "3. Generate to populate the lesson plan, monthly plan, and coverage report."
        )
        steps.setObjectName("EmptyStateSteps")
        steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        steps.setWordWrap(True)

        card_layout.addWidget(icon_label)
        card_layout.addWidget(title)
        card_layout.addWidget(body)
        card_layout.addWidget(steps)

        layout.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        self._apply_shadow(card, blur=18, y_offset=8, alpha=0.07)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.result_context_label = QLabel("")
        self.result_context_label.setObjectName("ResultContextLabel")
        self.result_context_label.setWordWrap(True)

        tabs_shell = ElevatedPanel("ResultsShell", "results-shell")
        shell_layout = QVBoxLayout(tabs_shell)
        shell_layout.setContentsMargins(12, 12, 12, 12)
        shell_layout.setSpacing(10)

        tabs = QTabWidget()
        tabs.setObjectName("PreviewTabs")
        tabs.setDocumentMode(True)
        tabs.tabBar().setExpanding(False)
        for key, title in (
            ("lesson_plan", "Lesson Plan"),
            ("monthly_plan", "Monthly Plan"),
            ("coverage_report", "Coverage Report"),
        ):
            table = QTableView()
            table.setObjectName("PreviewTable")
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setShowGrid(False)
            table.verticalHeader().setVisible(False)
            table.horizontalHeader().setStretchLastSection(True)
            table.setWordWrap(True)
            tabs.addTab(table, title)
            self.preview_tables[key] = table

        layout.addWidget(self.result_context_label)
        shell_layout.addWidget(tabs, stretch=1)
        layout.addWidget(tabs_shell, stretch=1)
        return page

    def _create_panel(self, title: str, subtitle: str = "") -> tuple[QWidget, QVBoxLayout]:
        panel = ElevatedPanel("SectionPanel", "panel")
        self._apply_shadow(panel, blur=26, y_offset=12, alpha=0.1)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("SectionSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)

        body_layout = QVBoxLayout()
        body_layout.setSpacing(6)
        layout.addLayout(body_layout)
        return panel, body_layout

    def _apply_styles(self) -> None:
        self.setStyleSheet(load_stylesheet())
        # Keep the inline generate-button override for specificity
        self.generate_button.setStyleSheet(
            f"QPushButton {{ background: {PALETTE['primary']}; color: #fff; font-size: 13px; font-weight: 700; border-radius: 8px; }}"
            f"QPushButton:hover {{ background: {PALETTE['primary_hover']}; }}"
            f"QPushButton:disabled {{ background: #1c2430; color: #667385; }}"
        )

    def _install_field_watchers(self) -> None:
        self.faculty_name_input.textChanged.connect(self._on_configuration_changed)
        self.subject_name_input.currentTextChanged.connect(self._on_configuration_changed)
        self.branch_input.textChanged.connect(self._on_configuration_changed)
        self.semester_input.currentTextChanged.connect(self._on_configuration_changed)
        self.section_input.currentTextChanged.connect(self._on_configuration_changed)

    def _setup_accessibility(self) -> None:
        # Accessible names for screen readers
        self.generate_button.setAccessibleName("Generate lesson plan")
        self.generate_button.setAccessibleDescription("Parse uploaded inputs and generate the lesson plan")
        self.export_pdf_button.setAccessibleName("Download lesson plan as PDF")
        self.export_excel_button.setAccessibleName("Export lesson plan as Excel")
        self.export_word_button.setAccessibleName("Export lesson plan as Word")
        self.install_requirements_button.setAccessibleName("Install Python requirements")
        self.faculty_name_input.setAccessibleName("Faculty name")
        self.designation_input.setAccessibleName("Designation")
        self.subject_name_input.setAccessibleName("Subject name")
        self.branch_input.setAccessibleName("Department or branch")
        self.semester_input.setAccessibleName("Year and semester")
        self.section_input.setAccessibleName("Section")

        for key, card in self.upload_cards.items():
            card.button.setAccessibleName(f"Upload {self.upload_labels[key]}")
            card.button.setAccessibleDescription(UPLOAD_HINTS[key])

        # Tooltips
        self.generate_button.setToolTip("Generate lesson plan from uploaded inputs (Ctrl+G)")
        self.export_pdf_button.setToolTip("Export lesson plan as PDF (Ctrl+S)")
        self.export_excel_button.setToolTip("Export lesson plan as Excel (Ctrl+E)")
        self.export_word_button.setToolTip("Export lesson plan as Word document")
        self.faculty_name_input.setToolTip("Enter the faculty member's full name")
        self.branch_input.setToolTip("Enter the department code: CSE, ECE, EEE, etc.")
        self.semester_input.setToolTip("Select or type year-semester, e.g. I-I, II-II")
        self.section_input.setToolTip("Select the class section")

        # Keyboard shortcuts
        self.generate_button.setShortcut("Ctrl+G")
        self.export_pdf_button.setShortcut("Ctrl+S")
        self.export_excel_button.setShortcut("Ctrl+E")

        # Tab order — use focusProxy so Qt resolves the correct internal widget
        tab_chain = [
            self.faculty_name_input,
            self.designation_input,
            self.subject_name_input,
            self.branch_input,
            self.semester_input,
            self.section_input,
            self.generate_button,
        ]
        for i in range(len(tab_chain) - 1):
            first, second = tab_chain[i], tab_chain[i + 1]
            if first.window() == second.window():
                self.setTabOrder(first, second)

    def _initialize_empty_previews(self) -> None:
        empty_frame = pd.DataFrame()
        for key, table in self.preview_tables.items():
            model = PandasTableModel(empty_frame)
            self.preview_models[key] = model
            table.setModel(model)

    def _standard_icon(self, standard_pixmap: QStyle.StandardPixmap):
        return self.style().standardIcon(standard_pixmap)

    def _apply_shadow(self, widget: QWidget, blur: int, y_offset: int, alpha: float) -> None:
        shadow = QGraphicsDropShadowEffect(widget)
        color = QColor(PALETTE["shadow"])
        color.setAlphaF(alpha)
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y_offset)
        shadow.setColor(color)
        widget.setGraphicsEffect(shadow)

    def _missing_required_inputs(self) -> list[str]:
        return [label for key, label in self.upload_labels.items() if not self.input_files[key]]

    def _can_generate(self) -> bool:
        return not self._missing_required_inputs() and bool(self._selected_subject_name())

    def _select_file(self, input_key: str) -> None:
        filter_text = "Supported Files (*.pdf *.docx *.txt *.jpg *.jpeg *.png *.xlsx *.csv)"
        selected_file, _ = QFileDialog.getOpenFileName(self, f"Select {self.upload_labels[input_key]}", "", filter_text)
        if not selected_file:
            return

        try:
            detected = validate_file_type(selected_file)
            saved_path = persist_uploaded_file(selected_file, input_key)
            self.input_errors.pop(input_key, None)
            self.input_files[input_key] = saved_path
            self.parsed_documents[input_key] = None
            self.input_summaries[input_key] = f"{saved_path.name} [{detected['type'].upper()}]"

            if input_key == "syllabus":
                self._load_syllabus_catalog(saved_path)
        except ProcessingError as exc:
            logger.warning("File upload failed for %s: %s", input_key, exc)
            self._handle_input_error(input_key, str(exc))
            self._show_error(str(exc))
            return

        logger.info("File loaded: %s [%s] for %s", saved_path.name, detected['type'].upper(), input_key)
        self._clear_generated_results()
        self._refresh_ui_state(
            tone="info",
            title=f"{self.upload_labels[input_key]} loaded",
            detail=f"{self.input_summaries[input_key]} is ready for generation.",
        )

    def _handle_input_error(self, input_key: str, message: str) -> None:
        self.input_errors[input_key] = message
        self.input_files[input_key] = None
        self.parsed_documents[input_key] = None
        self.input_summaries[input_key] = message

        if input_key == "syllabus":
            self.syllabus_catalog = []
            self.subject_name_input.blockSignals(True)
            self.subject_name_input.clear()
            self.subject_name_input.setEditText("")
            self.subject_name_input.blockSignals(False)
            self.semester_input.blockSignals(True)
            self.semester_input.clear()
            self.semester_input.setEditText("")
            self.semester_input.blockSignals(False)

        self._clear_generated_results()
        self._refresh_ui_state(
            tone="error",
            title=f"{self.upload_labels[input_key]} could not be loaded",
            detail=message,
        )

    def _load_syllabus_catalog(self, path: Path) -> None:
        parsed = load_parsed_document(path)
        catalog = CourseCatalogParser().parse(parsed)
        self.parsed_documents["syllabus"] = parsed
        self.syllabus_catalog = list(catalog.get('subjects', []))
        self._populate_semester_options(list(catalog.get('year_sems', [])))
        self._refresh_subject_options()
        if self.syllabus_catalog:
            self.statusBar().showMessage(f"Loaded {len(self.syllabus_catalog)} subject options from {path.name}")

    def _populate_section_options(self) -> None:
        self.section_input.clear()
        self.section_input.addItems(["A", "B", "C", "D"])

    def _populate_semester_options(self, values: list[str]) -> None:
        current_text = self.semester_input.currentText().strip()
        self.semester_input.blockSignals(True)
        self.semester_input.clear()
        for value in values:
            self.semester_input.addItem(value)
        if current_text and current_text not in values:
            self.semester_input.setEditText(current_text)
        elif values:
            self.semester_input.setCurrentIndex(0)
        else:
            self.semester_input.setEditText(current_text)
        self.semester_input.blockSignals(False)

    def _refresh_subject_options(self, _text: str = "") -> None:
        selected_text = self._subject_display_text().strip()
        selected_year_sem = self.semester_input.currentText().strip()
        options = self._catalog_subjects_for_year_sem(selected_year_sem)
        if not options:
            options = list(self.syllabus_catalog)

        self.subject_name_input.blockSignals(True)
        self.subject_name_input.clear()
        for subject in options:
            self.subject_name_input.addItem(str(subject.get('display_name', '')), subject)

        if selected_text:
            index = self.subject_name_input.findText(selected_text)
            if index >= 0:
                self.subject_name_input.setCurrentIndex(index)
            else:
                self.subject_name_input.setEditText(selected_text)
        elif options:
            self.subject_name_input.setCurrentIndex(0)
        else:
            self.subject_name_input.setEditText('')
        self.subject_name_input.blockSignals(False)

        if not self.bundle:
            self._refresh_ui_state()

    def _catalog_subjects_for_year_sem(self, year_sem: str) -> list[dict[str, object]]:
        cleaned = year_sem.strip()
        if not cleaned:
            return list(self.syllabus_catalog)
        return [subject for subject in self.syllabus_catalog if str(subject.get('year_sem', '')).strip() == cleaned]

    def _selected_subject_record(self) -> dict[str, object] | None:
        current_index = self.subject_name_input.currentIndex()
        if current_index >= 0:
            data = self.subject_name_input.itemData(current_index)
            if isinstance(data, dict):
                return data

        typed_text = self.subject_name_input.currentText().strip().lower()
        if not typed_text:
            return None
        for subject in self.syllabus_catalog:
            display_name = str(subject.get('display_name', '')).strip().lower()
            course_title = str(subject.get('course_title', '')).strip().lower()
            if typed_text in {display_name, course_title}:
                return subject
        return None

    def _subject_display_text(self) -> str:
        record = self._selected_subject_record()
        if record:
            return str(record.get('display_name', '')).strip()
        return self.subject_name_input.currentText().strip()

    def _selected_subject_name(self) -> str:
        record = self._selected_subject_record()
        if record:
            return str(record.get('course_title', '')).strip() or self.subject_name_input.currentText().strip()
        return self.subject_name_input.currentText().strip()

    def _selected_syllabus(self, parsed_document: ParsedDocument) -> dict[str, object]:
        record = self._selected_subject_record()
        if record and isinstance(record.get('syllabus'), dict):
            return dict(record['syllabus'])
        return SyllabusParser().parse(parsed_document)

    def _on_configuration_changed(self, _text: str = "") -> None:
        if self.bundle is not None:
            self._clear_generated_results()
            self._refresh_ui_state(
                tone="info",
                title="Results need regeneration",
                detail="A subject or faculty detail changed. Generate again to refresh the preview and exports.",
            )
            return
        self._refresh_ui_state()

    def _clear_generated_results(self) -> None:
        self.bundle = None
        self._initialize_empty_previews()

    def _generate_lesson_plan(self) -> None:
        missing = self._missing_required_inputs()
        if missing:
            message = f"Missing required inputs: {', '.join(missing)}"
            self._refresh_ui_state(tone="error", title="Required uploads missing", detail=message)
            self._show_error(message)
            return
        if not self._selected_subject_name():
            message = "Subject Name is required to process the timetable and syllabus catalog."
            self._refresh_ui_state(tone="error", title="Subject name required", detail=message)
            self._show_error(message)
            return

        self.is_generating = True
        self.generate_button.setText("Generating...")
        self._refresh_ui_state(
            tone="info",
            title="Generating lesson plan",
            detail="Parsing uploaded inputs — the UI will remain responsive.",
        )

        worker = _GenerationWorker(
            input_files=dict(self.input_files),
            parsed_documents=dict(self.parsed_documents),
            upload_labels=dict(self.upload_labels),
            subject_name=self._selected_subject_name(),
            faculty_info_snapshot=self._faculty_info(),
            syllabus_record=self._selected_subject_record(),
        )
        worker.finished.connect(self._on_generation_finished)
        worker.failed.connect(self._on_generation_failed)
        self._generation_worker = worker
        worker.start()

    def _on_generation_finished(self, bundle: LessonPlanBundle) -> None:
        worker = getattr(self, '_generation_worker', None)
        if worker is not None:
            # Cache any documents the worker parsed
            for key in ('academic_calendar', 'holiday_list', 'syllabus', 'timetable'):
                resolved = getattr(worker, '_resolved', {})
                if key in resolved and self.parsed_documents.get(key) is None:
                    self.parsed_documents[key] = resolved[key]
            self._generation_worker = None

        self.is_generating = False
        self.generate_button.setText("Generate Lesson Plan")
        self.bundle = bundle
        self._update_previews(bundle)
        self._refresh_ui_state(
            tone="success",
            title="Lesson plan generated successfully",
            detail=f"Prepared {len(bundle.lesson_plan)} lesson-plan rows. Review the preview or choose a destination folder when saving the PDF.",
        )
        QMessageBox.information(
            self,
            "Generation Complete",
            f"Generated {len(bundle.lesson_plan)} lesson-plan rows in memory. Use the PDF save button and choose a destination folder before saving the file.",
        )

    def _on_generation_failed(self, message: str) -> None:
        self._generation_worker = None
        self.is_generating = False
        self.generate_button.setText("Generate Lesson Plan")
        self._clear_generated_results()
        self._refresh_ui_state(tone="error", title="Generation failed", detail=message)
        self._show_error(message)

    def _ensure_parsed_documents(self, keys: tuple[str, ...]) -> dict[str, ParsedDocument]:
        resolved: dict[str, ParsedDocument] = {}
        missing_paths: dict[str, Path] = {}

        for key in keys:
            parsed = self.parsed_documents.get(key)
            if parsed is not None:
                resolved[key] = parsed
                continue

            path = self.input_files.get(key)
            if path is None:
                raise ProcessingError(f"{self.upload_labels[key]} is missing.")
            missing_paths[key] = path

        if len(missing_paths) == 1:
            key, path = next(iter(missing_paths.items()))
            parsed = load_parsed_document(path)
            self.parsed_documents[key] = parsed
            resolved[key] = parsed
        elif missing_paths:
            with ThreadPoolExecutor(max_workers=min(4, len(missing_paths))) as executor:
                future_map = {
                    executor.submit(load_parsed_document, path): key
                    for key, path in missing_paths.items()
                }
                for future in as_completed(future_map):
                    key = future_map[future]
                    parsed = future.result()
                    self.parsed_documents[key] = parsed
                    resolved[key] = parsed

        for key in keys:
            parsed = self.parsed_documents.get(key)
            if parsed is None:
                raise ProcessingError(f"{self.upload_labels[key]} could not be parsed.")
            resolved[key] = parsed

        return resolved

    def _export_excel(self) -> None:
        if not self.bundle:
            self._show_error("Generate a lesson plan before exporting.")
            return
        export_dir = self._choose_export_directory("Excel bundle")
        if export_dir is None:
            return
        try:
            outputs = self._export_excel_to_directory(export_dir)
        except ProcessingError as exc:
            self._refresh_ui_state(tone="error", title="Excel export failed", detail=str(exc))
            self._show_error(str(exc))
            return
        self._refresh_ui_state(
            tone="success",
            title="Excel exported",
            detail=f"Excel bundle exported to {outputs['lesson_plan']}",
        )
        QMessageBox.information(self, "Excel Exported", f"Files saved in:\n{outputs['lesson_plan'].parent}")

    def _export_word(self) -> None:
        if not self.bundle:
            self._show_error("Generate a lesson plan before exporting.")
            return
        export_dir = self._choose_export_directory("Word document")
        if export_dir is None:
            return
        try:
            output_path = self._export_word_to_directory(export_dir)
        except ProcessingError as exc:
            self._refresh_ui_state(tone="error", title="Word export failed", detail=str(exc))
            self._show_error(str(exc))
            return
        self._refresh_ui_state(
            tone="success",
            title="Word exported",
            detail=f"Word document exported to {output_path}",
        )
        QMessageBox.information(self, "Word Exported", f"File saved:\n{output_path}")

    def _export_pdf(self) -> None:
        if not self.bundle:
            self._show_error("Generate a lesson plan before exporting.")
            return
        export_dir = self._choose_export_directory("PDF document")
        if export_dir is None:
            return
        try:
            output_path = self._export_pdf_to_directory(export_dir)
        except ProcessingError as exc:
            logger.error("PDF export failed: %s", exc)
            self._refresh_ui_state(tone="error", title="PDF export failed", detail=str(exc))
            self._show_error(str(exc))
            return
        self._refresh_ui_state(
            tone="success",
            title="PDF exported",
            detail=f"PDF exported to {output_path}",
        )
        QMessageBox.information(self, "PDF Exported", f"File saved:\n{output_path}")

    def _export_all_formats(self) -> None:
        if not self.bundle:
            self._show_error("Generate a lesson plan before exporting.")
            return

        export_dir = self._choose_export_directory("all formats")
        if export_dir is None:
            return

        try:
            excel_outputs = self._export_excel_to_directory(export_dir)
            word_path = self._export_word_to_directory(export_dir)
            pdf_path = self._export_pdf_to_directory(export_dir)
        except ProcessingError as exc:
            message = (
                f"{exc}\n\nThe combined export stopped before finishing. "
                "Some files may already be saved in the selected destination."
            )
            self._refresh_ui_state(tone="error", title="Combined export failed", detail=str(exc))
            self._show_error(message)
            return

        target_folder = excel_outputs["lesson_plan"].parent
        self._refresh_ui_state(
            tone="success",
            title="All formats exported",
            detail=f"Excel, Word, and PDF files were exported to {target_folder}",
        )
        QMessageBox.information(
            self,
            "All Formats Exported",
            "Saved Excel, Word, and PDF outputs in:\n"
            f"{target_folder}\n\n"
            f"Word: {word_path.name}\n"
            f"PDF: {pdf_path.name}",
        )

    def _update_previews(self, bundle: LessonPlanBundle) -> None:
        frame_map = {
            'lesson_plan': bundle.lesson_plan,
            'monthly_plan': bundle.monthly_plan,
            'coverage_report': bundle.coverage_report,
        }
        for key, frame in frame_map.items():
            model = PandasTableModel(frame, copy=False)
            self.preview_models[key] = model
            self.preview_tables[key].setModel(model)
            self.preview_tables[key].resizeColumnsToContents()
            self.preview_tables[key].verticalHeader().setDefaultSectionSize(28)

    def _set_workspace_ready(self, ready: bool) -> None:
        self.preview_stack.setCurrentWidget(self.results_page if ready else self.empty_state_page)
        self.summary_strip.setVisible(ready)

    def _refresh_ui_state(self, tone: str | None = None, title: str | None = None, detail: str | None = None) -> None:
        self._update_upload_cards()
        self.generate_button.setEnabled((not self.is_generating) and self._can_generate())
        self._set_export_enabled((not self.is_generating) and self.bundle is not None)
        self.install_requirements_button.setEnabled(self.install_process is None)
        self._set_workspace_ready(self.bundle is not None)
        self._update_workspace_header()
        self._update_summary_cards()

        if tone is None or title is None or detail is None:
            tone, title, detail = self._default_status_state()

        self._set_status_strip(tone, title, detail)
        self._set_topbar_state(tone, title)
        self.topbar_formula_badge.setText(self._topbar_formula_text())
        self.statusBar().showMessage(detail)

    def _choose_export_directory(self, export_label: str) -> Path | None:
        selected = QFileDialog.getExistingDirectory(
            self,
            f"Select destination folder for {export_label}",
            str(self.last_export_directory),
        )
        if not selected:
            self.statusBar().showMessage(f"{export_label} export cancelled.")
            return None

        target = Path(selected)
        self.last_export_directory = target
        return target

    def _export_excel_to_directory(self, export_dir: Path) -> dict[str, Path]:
        if not self.bundle:
            raise ProcessingError("Generate a lesson plan before exporting.")
        return export_bundle_to_excel(self.bundle, export_dir)

    def _export_word_to_directory(self, export_dir: Path) -> Path:
        if not self.bundle:
            raise ProcessingError("Generate a lesson plan before exporting.")
        return export_bundle_to_word(self.bundle, export_dir)

    def _export_pdf_to_directory(self, export_dir: Path) -> Path:
        if not self.bundle:
            raise ProcessingError("Generate a lesson plan before exporting.")
        return export_bundle_to_pdf(self.bundle, export_dir)

    def _update_upload_cards(self) -> None:
        for key, card in self.upload_cards.items():
            if key in self.input_errors:
                card.set_state("invalid", self.input_summaries[key])
            elif self.input_files[key]:
                card.set_state("loaded", self.input_summaries[key])
            else:
                card.set_state("empty", self.input_summaries[key])

    def _update_workspace_header(self) -> None:
        if self.bundle:
            metadata = self.bundle.metadata
            faculty = metadata.get("faculty_info", {})
            course_title = str(metadata.get("course_title", "Lesson Plan Preview")).strip() or "Lesson Plan Preview"
            self.workspace_title_label.setText(course_title)

            detail_parts = []
            if faculty.get("course_code"):
                detail_parts.append(str(faculty["course_code"]).strip())
            if faculty.get("faculty_name"):
                detail_parts.append(str(faculty["faculty_name"]).strip())
            if faculty.get("semester"):
                detail_parts.append(str(faculty["semester"]).strip())
            if faculty.get("section"):
                detail_parts.append(f"Section {str(faculty['section']).strip()}")

            subtitle = " | ".join(part for part in detail_parts if part)
            if not subtitle:
                subtitle = "Review the generated lesson-plan tables and save the final PDF from this workspace."
            self.workspace_subtitle_label.setText(subtitle)
            self.workspace_badge.setText("Preview Ready")
            self.result_context_label.setText(
                f"Coverage summary generated for {metadata.get('planned_lectures', 0)} planned lectures across "
                f"{metadata.get('teaching_days', 0)} teaching days."
            )
            self.result_context_label.show()
            return

        self.workspace_title_label.setText("Preview Workspace")
        self.workspace_badge.setText("Awaiting Inputs")
        self.result_context_label.hide()

        missing = self._missing_required_inputs()
        if missing:
            self.workspace_subtitle_label.setText(
                f"Upload the remaining required inputs to activate the generation workspace: {', '.join(missing)}."
            )
        elif not self._selected_subject_name():
            self.workspace_subtitle_label.setText(
                "All required files are loaded. Confirm the subject selection to enable lesson plan generation."
            )
        else:
            self.workspace_subtitle_label.setText(
                "All required inputs are ready. Generate the lesson plan to open the premium preview workspace."
            )

    def _update_summary_cards(self) -> None:
        if not self.bundle:
            for chip in self.summary_chips.values():
                chip.set_value("--")
            return

        metadata = self.bundle.metadata
        self.summary_chips["planned_lectures"].set_value(str(metadata.get("planned_lectures", 0)))
        self.summary_chips["teaching_days"].set_value(str(metadata.get("teaching_days", 0)))
        branches = metadata.get("planned_branches", [])
        branch_count = len(branches) if isinstance(branches, list) else 0
        self.summary_chips["branches"].set_value(str(branch_count or 1))
        self.summary_chips["deliverables"].set_value("1")

    def _default_status_state(self) -> tuple[str, str, str]:
        if self.input_errors:
            key = next(iter(self.input_errors))
            return ("error", f"{self.upload_labels[key]} needs attention", self.input_errors[key])

        if self.is_generating:
            return (
                "info",
                "Generating lesson plan",
                "Parsing the uploaded inputs and preparing the preview workspace.",
            )

        missing = self._missing_required_inputs()
        if missing:
            return (
                "info",
                "Complete the required uploads",
                f"{len(missing)} input file(s) still required: {', '.join(missing)}.",
            )

        if not self._selected_subject_name():
            return (
                "info",
                "Confirm the subject selection",
                "All required files are loaded. Pick or type the subject name to enable generation.",
            )

        if self.bundle:
            return (
                "success",
                "Lesson plan ready",
                f"Generated {len(self.bundle.lesson_plan)} rows. Review the preview or save the PDF.",
            )

        return (
            "ready",
            "Ready to generate",
            "All required inputs are loaded and the workflow is ready for lesson-plan generation.",
        )

    def _set_status_strip(self, tone: str, title: str, detail: str) -> None:
        icon_map = {
            "info": QStyle.StandardPixmap.SP_MessageBoxInformation,
            "success": QStyle.StandardPixmap.SP_DialogApplyButton,
            "error": QStyle.StandardPixmap.SP_MessageBoxCritical,
            "ready": QStyle.StandardPixmap.SP_MessageBoxWarning,
        }
        icon = self._standard_icon(icon_map.get(tone, QStyle.StandardPixmap.SP_MessageBoxInformation))
        self.status_strip.setProperty("tone", tone)
        self.status_strip_title.setText(title)
        self.status_strip_detail.setText(detail)
        self.status_icon_label.setPixmap(icon.pixmap(22, 22))
        refresh_widget_style(self.status_strip)

    def _set_topbar_state(self, tone: str, title: str) -> None:
        self.topbar_status_badge.setProperty("tone", tone)
        self.topbar_status_badge.setText(title)
        refresh_widget_style(self.topbar_status_badge)

    def _topbar_formula_text(self) -> str:
        if self.install_process is not None:
            return "Environment update in progress -> Installing project dependencies"

        if self.bundle:
            metadata = self.bundle.metadata
            branch_list = metadata.get("planned_branches", [])
            branch = branch_list[0] if isinstance(branch_list, list) and branch_list else self.branch_input.text().strip()
            return (
                f"Output ready -> {branch or 'Dept'} folder | "
                f"PDF ready for export"
            )

        missing = self._missing_required_inputs()
        total = len(self.upload_labels)
        loaded = total - len(missing)
        if missing:
            return f"Input progress -> {loaded}/{total} files loaded"
        if not self._selected_subject_name():
            return "All inputs loaded -> confirm subject mapping to enable generation"
        return "Aligned workflow ready -> Generate lesson plan and save the PDF"

    def _open_templates_folder(self) -> None:
        templates_dir = project_root() / "templates"
        if not templates_dir.exists():
            self._show_error("Templates folder not found. Please reinstall the application.")
            return
        os.startfile(str(templates_dir))  # noqa: S606

    def _install_requirements(self) -> None:
        if self.install_process is not None:
            return

        requirements_path = project_root() / "requirements.txt"
        if not requirements_path.exists():
            message = f"requirements.txt was not found at {requirements_path}."
            self._refresh_ui_state(tone="error", title="Requirements file missing", detail=message)
            self._show_error(message)
            return

        confirmation = QMessageBox.question(
            self,
            "Install Requirements",
            "Install or update the project requirements using the current Python environment?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

        process = QProcess(self)
        process.setWorkingDirectory(str(project_root()))
        process.setProgram(sys.executable)
        process.setArguments(["-m", "pip", "install", "-r", str(requirements_path)])
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.finished.connect(self._on_requirements_install_finished)
        process.errorOccurred.connect(self._on_requirements_install_error)

        self.install_process = process
        self.install_requirements_button.setText("Installing...")
        self.install_requirements_button.setEnabled(False)
        self._refresh_ui_state(
            tone="info",
            title="Installing requirements",
            detail="Running pip install -r requirements.txt using the current Python environment.",
        )
        process.start()

    def _on_requirements_install_finished(self, exit_code: int, exit_status) -> None:
        process = self.install_process
        if process is None:
            return

        output = bytes(process.readAllStandardOutput()).decode("utf-8", errors="ignore")
        self.install_process = None
        self.install_requirements_button.setText("Install Requirements")

        if exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0:
            detail = "Project requirements were installed successfully."
            self._refresh_ui_state(tone="success", title="Requirements installed", detail=detail)
            QMessageBox.information(self, "Install Requirements", detail)
            process.deleteLater()
            return

        message = self._format_install_error(output) or f"pip exited with code {exit_code}."
        self._refresh_ui_state(tone="error", title="Requirements install failed", detail=message)
        self._show_error(message)
        process.deleteLater()

    def _on_requirements_install_error(self, _error) -> None:
        process = self.install_process
        if process is None:
            return

        message = process.errorString() or "The dependency installer could not be started."
        self.install_process = None
        self.install_requirements_button.setText("Install Requirements")
        self._refresh_ui_state(tone="error", title="Requirements install failed", detail=message)
        self._show_error(message)
        process.deleteLater()

    def _format_install_error(self, output: str) -> str:
        cleaned_lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not cleaned_lines:
            return ""
        return "\n".join(cleaned_lines[-8:])

    def _faculty_info(self, syllabus: dict[str, object] | None = None) -> dict[str, str]:
        course_title = self._selected_subject_name()
        course_code = ''
        if syllabus:
            course_title = str(syllabus.get('course_title', course_title)).strip() or course_title
            course_code = str(syllabus.get('course_code', '')).strip()
        return {
            'faculty_name': self.faculty_name_input.text().strip(),
            'designation': self.designation_input.currentText().strip(),
            'subject_name': course_title,
            'course_code': course_code,
            'branch': self.branch_input.text().strip(),
            'semester': self.semester_input.currentText().strip(),
            'section': self.section_input.currentText().strip(),
        }

    def _set_export_enabled(self, enabled: bool) -> None:
        self.export_pdf_button.setEnabled(enabled)
        self.export_excel_button.setEnabled(enabled)
        self.export_word_button.setEnabled(enabled)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Lesson Plan Generator", message)

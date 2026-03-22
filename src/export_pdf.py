"""PDF export using ReportLab for formatted lesson plans."""
from __future__ import annotations

from pathlib import Path

from .lesson_plan_format import (
    LAB_MAIN_COLUMN_WIDTHS,
    SUMMARY_TABLE_COLUMN_WIDTHS,
    THEORY_MAIN_COLUMN_WIDTHS,
    formatted_lesson_plan_frame,
    lab_date_row_spans,
    summary_values,
    week_row_spans,
)
from .utils import LessonPlanBundle, ProcessingError, header_image_path, report_output_paths

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:  # pragma: no cover - depends on local environment
    colors = None
    TA_CENTER = None
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    inch = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None


PDF_HEADER_WIDTH = 7.2
PDF_HEADER_GAP = 0.15
LAB_SIGNOFF_TOP_SPACER = 0.42
THEORY_SIGNOFF_TOP_SPACER = 0.32


def export_bundle_to_pdf(bundle: LessonPlanBundle, output_dir: str | Path) -> Path:
    if SimpleDocTemplate is None:
        raise ProcessingError('PDF export requires reportlab.')

    pdf_path = report_output_paths(bundle, output_dir)['lesson_plan_pdf']

    header_path = header_image_path()
    header_height = _header_height_inches(header_path)
    top_margin = max(0.45, header_height + PDF_HEADER_GAP + 0.32) * inch

    document = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=0.28 * inch,
        leftMargin=0.28 * inch,
        topMargin=top_margin,
        bottomMargin=0.45 * inch,
    )
    styles = _build_styles()
    summary = summary_values(bundle)
    available_width = document.width
    lab_mode = bool(summary['is_lab'])

    elements = [
        Paragraph(summary['department_name'], styles['Department']),
        Spacer(1, 0.12 * inch),
        Paragraph(summary['plan_title'], styles['TitleCenter']),
        Spacer(1, 0.12 * inch),
        _summary_table(summary, available_width, styles),
        Spacer(1, 0.12 * inch),
    ]

    if lab_mode:
        elements.append(_lab_lesson_plan_table(bundle, available_width, styles))
        elements.append(Spacer(1, LAB_SIGNOFF_TOP_SPACER * inch))
        elements.append(_signoff_table(summary['sign_labels'], available_width))
    else:
        elements.append(Spacer(1, THEORY_SIGNOFF_TOP_SPACER * inch))
        elements.append(_signoff_table(summary['sign_labels'], available_width))
        elements.append(Spacer(1, 0.08 * inch))
        elements.append(_regulation_table(summary, available_width))
        elements.append(_theory_lesson_plan_table(bundle, available_width, styles))

    elements.append(Spacer(1, 0.12 * inch))
    elements.extend(_books_flowables('TEXT BOOKS:', bundle.metadata.get('text_books', []), styles))
    elements.append(Spacer(1, 0.10 * inch))
    elements.extend(_books_flowables('REFERENCE BOOKS:', bundle.metadata.get('reference_books', []), styles))

    document.build(
        elements,
        onFirstPage=lambda canvas, doc: _draw_pdf_header(canvas, doc, header_path),
        onLaterPages=lambda canvas, doc: _draw_pdf_header(canvas, doc, header_path),
    )
    return pdf_path


def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Department', parent=styles['Normal'], fontName='Times-Bold', fontSize=11, leading=13, alignment=TA_CENTER, spaceAfter=0))
    styles.add(ParagraphStyle(name='TitleCenter', parent=styles['Normal'], fontName='Times-Bold', fontSize=14, leading=16, alignment=TA_CENTER, spaceAfter=0))
    styles.add(ParagraphStyle(name='SignLine', parent=styles['Normal'], fontName='Times-Bold', fontSize=9.5, leading=11, alignment=TA_CENTER, spaceAfter=0))
    styles.add(ParagraphStyle(name='BookHeading', parent=styles['Normal'], fontName='Times-Bold', fontSize=10, leading=12, spaceAfter=2))
    styles.add(ParagraphStyle(name='BookItem', parent=styles['Normal'], fontName='Times-Roman', fontSize=9.2, leading=11, spaceAfter=1))
    styles.add(ParagraphStyle(name='TableHeader', parent=styles['Normal'], fontName='Times-Bold', fontSize=7.4, leading=8.4, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='TableCell', parent=styles['Normal'], fontName='Times-Roman', fontSize=7.3, leading=8.4))
    styles.add(ParagraphStyle(name='TableCellCenter', parent=styles['Normal'], fontName='Times-Roman', fontSize=7.3, leading=8.4, alignment=TA_CENTER))
    return styles


def _summary_table(summary: dict[str, str], available_width: float, styles):
    data = [
        [
            _pdf_cell('Subject\nCode', styles['TableHeader']),
            _pdf_cell('Subject Name', styles['TableHeader']),
            _pdf_cell('Class/Sem', styles['TableHeader']),
            _pdf_cell('Faculty Name /\nDesignation', styles['TableHeader']),
            _pdf_cell('Number of\nStudents', styles['TableHeader']),
            _pdf_cell(summary['total_label_display'], styles['TableHeader']),
            _pdf_cell('', styles['TableHeader']),
        ],
        [
            _pdf_cell(summary['course_code'], styles['TableCellCenter']),
            _pdf_cell(summary['course_title_display'], styles['TableCellCenter']),
            _pdf_cell(summary['class_sem_display'], styles['TableCellCenter']),
            _pdf_cell(summary['faculty_display_summary'], styles['TableCellCenter']),
            _pdf_cell(summary['student_count'], styles['TableCellCenter']),
            _pdf_cell(summary['lecture_label'], styles['TableCellCenter']),
            _pdf_cell(summary['tutorial_label'], styles['TableCellCenter']),
        ],
        [
            _pdf_cell('', styles['TableCellCenter']),
            _pdf_cell('', styles['TableCellCenter']),
            _pdf_cell('', styles['TableCellCenter']),
            _pdf_cell('', styles['TableCellCenter']),
            _pdf_cell('', styles['TableCellCenter']),
            _pdf_cell(summary['lecture_count'], styles['TableCellCenter']),
            _pdf_cell(summary['tutorial_count'], styles['TableCellCenter']),
        ],
    ]
    col_widths = _scale_widths(SUMMARY_TABLE_COLUMN_WIDTHS, available_width)
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ('SPAN', (5, 0), (6, 0)),
                ('SPAN', (0, 1), (0, 2)),
                ('SPAN', (1, 1), (1, 2)),
                ('SPAN', (2, 1), (2, 2)),
                ('SPAN', (3, 1), (3, 2)),
                ('SPAN', (4, 1), (4, 2)),
                ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Times-Bold'),
                ('FONTNAME', (0, 2), (-1, -1), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8.5),
                ('LEADING', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _regulation_table(summary: dict[str, str], available_width: float):
    table = Table([[f"Regulation: {summary['regulation']}     Academic Year: {summary['academic_year']}"]], colWidths=[available_width])
    table.setStyle(
        TableStyle(
            [
                ('GRID', (0, 0), (-1, -1), 0.6, colors.black),
                ('FONTNAME', (0, 0), (-1, -1), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _signoff_table(labels: tuple[str, str, str], available_width: float):
    col_widths = _scale_widths([2.25, 1.70, 2.35], available_width)
    table = Table([[labels[0], labels[1], labels[2]]], colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ('FONTNAME', (0, 0), (-1, -1), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9.5),
                ('LEADING', (0, 0), (-1, -1), 11),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _theory_lesson_plan_table(bundle: LessonPlanBundle, available_width: float, styles):
    frame = formatted_lesson_plan_frame(bundle.lesson_plan, lab_mode=False)
    table_data = [[_pdf_cell(column, styles['TableHeader']) for column in frame.columns]]
    for row in frame.astype(str).values.tolist():
        table_data.append([
            _pdf_cell(value, styles['TableCellCenter']) if index != 3 else _pdf_cell(value, styles['TableCell'])
            for index, value in enumerate(row)
        ])
    col_widths = _scale_widths(THEORY_MAIN_COLUMN_WIDTHS, available_width)
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    commands = [
        ('GRID', (0, 0), (-1, -1), 0.45, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.4),
        ('LEADING', (0, 0), (-1, -1), 8.6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]
    for start_index, end_index, _label in week_row_spans(frame):
        if end_index > start_index:
            commands.append(('SPAN', (1, start_index + 1), (1, end_index + 1)))
    table.setStyle(TableStyle(commands))
    return table


def _lab_lesson_plan_table(bundle: LessonPlanBundle, available_width: float, styles):
    frame = formatted_lesson_plan_frame(bundle.lesson_plan, lab_mode=True)
    table_data = [[_pdf_cell(column, styles['TableHeader']) for column in frame.columns]]
    for row in frame.astype(str).values.tolist():
        table_data.append([
            _pdf_cell(value, styles['TableCellCenter']) if index != 2 else _pdf_cell(value, styles['TableCell'])
            for index, value in enumerate(row)
        ])
    col_widths = _scale_widths(LAB_MAIN_COLUMN_WIDTHS, available_width)
    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    commands = [
        ('GRID', (0, 0), (-1, -1), 0.45, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('LEADING', (0, 0), (-1, -1), 8.8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]
    for start_index, end_index, _label in lab_date_row_spans(frame):
        if end_index > start_index:
            commands.append(('SPAN', (4, start_index + 1), (4, end_index + 1)))
    table.setStyle(TableStyle(commands))
    return table



def _pdf_cell(text: str, style):
    escaped = (
        str(text)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('\n', '<br/>')
    )
    return Paragraph(escaped, style)


def _books_flowables(title: str, entries, styles) -> list:
    items = [str(entry).strip() for entry in entries if str(entry).strip()]
    flowables = [Paragraph(title, styles['BookHeading'])]
    if not items:
        flowables.append(Paragraph('1. -', styles['BookItem']))
        return flowables

    for index, entry in enumerate(items, start=1):
        flowables.append(Paragraph(f'{index}. {entry}', styles['BookItem']))
    return flowables


def _scale_widths(widths_in_inches: list[float], available_width: float) -> list[float]:
    total = sum(widths_in_inches)
    if total <= 0:
        return [available_width / max(len(widths_in_inches), 1)] * len(widths_in_inches)
    scale = available_width / (total * inch)
    return [width * inch * scale for width in widths_in_inches]


def _draw_pdf_header(canvas, doc, image_path: Path | None) -> None:
    if image_path is None:
        return

    canvas.saveState()
    width = min(PDF_HEADER_WIDTH * inch, doc.pagesize[0] - doc.leftMargin - doc.rightMargin)
    height = _header_height_inches(image_path, width / inch) * inch
    x = doc.leftMargin + ((doc.pagesize[0] - doc.leftMargin - doc.rightMargin) - width) / 2
    y = doc.pagesize[1] - height - 0.16 * inch
    canvas.drawImage(str(image_path), x, y, width=width, height=height, preserveAspectRatio=True, mask='auto')
    canvas.restoreState()


def _header_height_inches(image_path: Path | None, width_inches: float = PDF_HEADER_WIDTH) -> float:
    if image_path is None:
        return 0.0
    try:
        from PIL import Image
    except ImportError:
        return 0.9

    with Image.open(image_path) as image:
        if image.width == 0:
            return 0.9
        return width_inches * (image.height / image.width)

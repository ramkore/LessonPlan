# AI Lesson Plan Generator

Desktop lesson-plan generator for engineering faculty. The application accepts academic calendars, holiday lists, subject syllabi, and branchwise class or individual timetables in multiple file formats, then produces structured lesson plans and summary reports.

## Features

- Accepts `PDF`, `DOCX`, `TXT`, `JPG`, `JPEG`, `PNG`, `XLSX`, and `CSV`
- Uses OCR for scanned image inputs
- Generates:
  - `lesson_plan.xlsx` / `.docx` / `.pdf`
  - `monthly_teaching_plan.xlsx`
  - `syllabus_coverage_report.xlsx`
- PyQt6 desktop GUI for uploads, generation, preview, and export
- Supports branchwise timetable extracts from either class timetables or individual faculty timetables
- Dark-themed modern UI with keyboard shortcuts

## Prerequisites

- **Python 3.11+**
- **Tesseract OCR** (required for scanned images and image-only PDFs) — install and add to system `PATH`

## Installation

```bash
# Install production dependencies
pip install -r requirements.txt

# Or for development (includes linting, testing, type checking)
pip install -r requirements-dev.txt
```

## Usage

```bash
python main.py
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+G` | Generate lesson plan |
| `Ctrl+S` | Export PDF |
| `Ctrl+E` | Export Excel |

## Architecture

```
src/
  main.py              Entry point with startup health checks
  gui.py               PyQt6 main window (orchestration)
  theme.py             Color palette, dimensions, stylesheet loading
  widgets.py           Reusable UI components (UploadCard, SummaryChip, etc.)
  calendar_processor.py  Academic calendar and holiday processing
  timetable_parser.py    Timetable parsing and subject period extraction
  syllabus_parser.py     Syllabus content extraction (units, topics, experiments)
  course_catalog.py      Multi-subject course catalog parsing
  lesson_generator.py    Core lesson plan generation algorithm
  lesson_plan_format.py  Output formatting (column widths, templates)
  export_excel.py        Excel export with formatting
  export_word.py         Word document export
  export_pdf.py          PDF export using ReportLab
  file_detector.py       File type validation (extensions, size limits)
  pdf_parser.py          PDF text and table extraction
  doc_parser.py          DOCX/TXT parsing
  excel_parser.py        Spreadsheet parsing (CSV, XLSX)
  image_ocr_parser.py    Image OCR using pytesseract
  utils.py               Shared dataclasses, caching, file I/O
  logger.py              Logging configuration
```

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing

# Lint
python -m ruff check src/ tests/

# Type check
python -m mypy src/ --ignore-missing-imports
```

## License

MIT License - Pallavi Engineering College, 2026

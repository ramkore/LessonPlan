# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-21

### Added
- PyQt6 desktop GUI with dark theme, keyboard shortcuts, and accessible widgets
- Multi-format input support: PDF, DOCX, TXT, JPG, JPEG, PNG, XLSX, CSV
- OCR processing for scanned images and image-only PDFs via pytesseract
- Academic calendar parsing with holiday exclusion and teaching day extraction
- Branchwise timetable parsing from class or individual faculty timetables
- Syllabus parsing with unit/topic/experiment extraction and course outcome mapping
- Multi-subject course catalog parsing from structured PDF tables
- Core lesson plan generation algorithm with topic distribution and scheduling
- Excel export with formatted headers, merged cells, and signature rows
- Word document export with structured lesson plan tables
- PDF export using ReportLab with college header images
- Monthly teaching plan and syllabus coverage report generation
- Startup health checks for courses.json, header.png, and Tesseract OCR
- Rotating file logger with configurable output directory
- Document caching with restricted pickle unpickler for security
- Path traversal validation on uploaded file names
- Excel formula injection escaping for exported cell values
- OCR operation timeouts (30s per page, 10s per cell)
- High-DPI scaling support with PassThrough rounding policy
- Keyboard shortcuts: Ctrl+G (generate), Ctrl+S (export PDF), Ctrl+E (export Excel)
- Accessible names, tooltips, and tab order for all interactive widgets
- 53 automated tests covering parsers, generators, exporters, and utilities
- Ruff linting, mypy type checking, and pytest coverage configuration
- Pre-commit hooks for code quality enforcement
- GitHub Actions CI pipeline for automated lint, type check, and test

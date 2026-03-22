"""Application entry point with startup health checks."""
from __future__ import annotations

import json
import shutil
import sys

from .logger import configure_logging, get_logger
from .utils import ensure_directories, project_root

logger = get_logger(__name__)


def _run_startup_health_checks() -> dict[str, bool]:
    results: dict[str, bool] = {}

    courses_path = project_root() / "data" / "courses.json"
    if courses_path.exists():
        try:
            json.loads(courses_path.read_text(encoding="utf-8"))
            results["courses_json"] = True
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("courses.json is invalid: %s", exc)
            results["courses_json"] = False
    else:
        logger.warning("courses.json not found at %s", courses_path)
        results["courses_json"] = False

    header_path = project_root() / "assets" / "header.png"
    if not header_path.exists():
        logger.warning("header.png not found at %s — PDF exports may lack header images", header_path)
        results["header_png"] = False
    else:
        results["header_png"] = True

    if shutil.which("tesseract"):
        results["tesseract"] = True
    else:
        logger.warning("Tesseract OCR not found on PATH — image/scanned PDF parsing will fail")
        results["tesseract"] = False

    return results


def main() -> int:
    configure_logging()
    ensure_directories()
    health = _run_startup_health_checks()
    if health.get("courses_json"):
        logger.info("Startup health checks passed")
    else:
        logger.warning("Some startup checks failed: %s", health)

    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        logger.error(
            "PyQt6 is required to run the desktop application. "
            "Install dependencies with: pip install -r requirements.txt"
        )
        return 1

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    from .gui import LessonPlanWindow

    app = QApplication(sys.argv)
    app.setApplicationName("AI Lesson Plan Generator")
    window = LessonPlanWindow()
    window.show()
    return app.exec()

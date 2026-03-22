"""Logging configuration with rotating file handler and console output."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_file_path() -> Path:
    # Import here to avoid circular import (utils imports nothing from logger)
    from .utils import project_root
    log_dir = project_root() / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / "lesson_plan.log"


def configure_logging(level: int = logging.INFO) -> None:
    """Call once at application startup to configure root logger."""
    root = logging.getLogger()
    if root.handlers:
        # Already configured (e.g., during tests). Do not add duplicate handlers.
        return

    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler - INFO and above
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler - DEBUG and above
    try:
        file_handler = RotatingFileHandler(
            _log_file_path(),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # Non-fatal: log directory may not be writable in some deployments
        pass


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Usage: logger = get_logger(__name__)"""
    return logging.getLogger(name)

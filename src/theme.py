"""Theme constants and stylesheet loading for the PyQt6 desktop application."""
from __future__ import annotations

from pathlib import Path

PALETTE = {
    "canvas": "#090e14",
    "topbar": "#0f1621",
    "topbar_edge": "#1f2b39",
    "panel": "#10161f",
    "panel_alt": "#1c2430",
    "surface": "#171e28",
    "surface_soft": "#0d131b",
    "border": "#273241",
    "border_strong": "#364357",
    "text": "#f4f7fb",
    "text_muted": "#9aa8be",
    "text_soft": "#6f7d93",
    "primary": "#2f6fdd",
    "primary_hover": "#3f83f3",
    "accent": "#2fb463",
    "accent_soft": "#173021",
    "info_soft": "#102538",
    "success_soft": "#163222",
    "warning_soft": "#382b15",
    "danger_soft": "#38161d",
    "shadow": "#02060b",
    "table_header": "#2a5988",
    "selection": "#214061",
    "splitter": "#253140",
}

SPACING = {
    "page": 16,
    "section": 14,
    "card": 14,
    "small": 10,
}

RADII = {
    "panel": 16,
    "card": 12,
    "field": 10,
    "pill": 16,
}

TYPE_SCALE = {
    "section": 15,
    "metric": 22,
}

DIMENSIONS = {
    "window_default": (1520, 940),
    "window_minimum": (1280, 800),
    "splitter_left": 418,
    "splitter_right": 992,
    "workflow_min_width": 400,
    "workflow_max_width": 448,
    "topbar_height": 56,
    "button_min_height": 36,
    "export_button_height": 38,
    "generate_button_height": 40,
    "upload_button_min_width": 160,
    "field_min_height": 36,
    "field_label_min_width": 96,
}


def _stylesheet_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "styles.qss"


def load_stylesheet() -> str:
    path = _stylesheet_path()
    template = path.read_text(encoding="utf-8") if path.exists() else ""
    for key, value in PALETTE.items():
        template = template.replace(f"{{PALETTE[{key}]}}", value)
    for key, value in RADII.items():
        template = template.replace(f"{{RADII[{key}]}}", str(value))
    return template

"""Reusable PyQt6 widget classes for the lesson plan application."""
from __future__ import annotations

import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import DIMENSIONS


def refresh_widget_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class ElevatedPanel(QFrame):
    def __init__(self, object_name: str, variant: str) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setProperty("variant", variant)
        self.setFrameShape(QFrame.Shape.NoFrame)


class UploadCard(ElevatedPanel):
    state_labels = {
        "empty": "Empty",
        "loaded": "Loaded",
        "invalid": "Invalid",
    }

    def __init__(self, title: str, hint: str, button_text: str, icon) -> None:
        super().__init__("UploadCard", "upload-card")
        self.setProperty("state", "empty")

        layout = QVBoxLayout(self)
        self.button = QPushButton(button_text)
        self.button.setObjectName("UploadButton")
        self.button.setIcon(icon)
        self.button.setText(title)
        self.button.setMinimumHeight(DIMENSIONS["button_min_height"])
        self.button.setMinimumWidth(DIMENSIONS["upload_button_min_width"])

        self.path_label = QLabel("No file selected yet.")
        self.path_label.setObjectName("CardPathLabel")
        self.path_label.setWordWrap(False)
        self.path_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self.button)
        row.addWidget(self.path_label, stretch=1)

        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(0)
        layout.addLayout(row)

    def set_state(self, state: str, detail: str) -> None:
        self.setProperty("state", state)
        self.path_label.setText(detail)
        refresh_widget_style(self)


class SummaryChip(ElevatedPanel):
    def __init__(self, label: str) -> None:
        super().__init__("SummaryChip", "summary-chip")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(2)
        self.value_label = QLabel("--")
        self.value_label.setObjectName("SummaryValue")
        self.caption_label = QLabel(label)
        self.caption_label.setObjectName("SummaryCaption")
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class PandasTableModel(QAbstractTableModel):
    def __init__(self, frame: pd.DataFrame, *, copy: bool = True) -> None:
        super().__init__()
        self._frame = frame.copy() if copy else frame

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._frame.index)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._frame.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            value = self._frame.iat[index.row(), index.column()]
            if isinstance(value, pd.Timestamp):
                return value.strftime("%d-%m-%Y")
            if pd.isna(value):
                return ""
            return str(value)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._frame.columns[section])
        return str(section + 1)

"""
ui/pages/paths_page.py
Editor page for track / path definitions.

Responsibilities (this file):
  • Display and edit path rows in a QTableWidget.
  • Convert rows ↔ storage.models.PathRecord via to_dict / from_dict.
  • Report the length of the currently-selected path (used by SostavPage).

Validation is delegated to validation.validators.validate_paths().
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
)

from storage.models import PathRecord
from ui.pages.base_page import BasePage
from validation.validators import validate_paths, ValidationError

# Column indices
_COL_TRACK_ID  = 0
_COL_NAME      = 1
_COL_X         = 2
_COL_Z         = 3
_COL_LENGTH_MM = 4
_COL_SELECTED  = 5


class PathsPage(BasePage):
    """QWidget that lets the user define railway tracks."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["track_id", "Название", "X", "Z", "Длина (мм)", "Выбор"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить путь")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

    # ------------------------------------------------------------------ #
    #  Public — row management                                             #
    # ------------------------------------------------------------------ #

    def add_row(self, record: PathRecord | None = None) -> None:
        """Insert a new row, optionally pre-filled from *record*."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        r = record or PathRecord()
        self.table.setItem(row, _COL_TRACK_ID,  QTableWidgetItem(r.track_id))
        self.table.setItem(row, _COL_NAME,      QTableWidgetItem(r.name))
        self.table.setItem(row, _COL_X,         QTableWidgetItem(str(r.x)))
        self.table.setItem(row, _COL_Z,         QTableWidgetItem(str(r.z)))
        self.table.setItem(row, _COL_LENGTH_MM, QTableWidgetItem(str(r.length_mm)))

        chk = QCheckBox()
        self.table.setCellWidget(row, _COL_SELECTED, chk)

    # ------------------------------------------------------------------ #
    #  Public — data access                                                #
    # ------------------------------------------------------------------ #

    def get_selected_path_length(self) -> float:
        """Return the length (mm) of the first checked path, or the first row's
        length, or 0 if the table is empty."""
        for row in range(self.table.rowCount()):
            chk = self.table.cellWidget(row, _COL_SELECTED)
            if chk and chk.isChecked():
                return self._float(row, _COL_LENGTH_MM)

        if self.table.rowCount() > 0:
            return self._float(0, _COL_LENGTH_MM)

        return 0.0

    def to_records(self) -> list[PathRecord]:
        """Return all rows as a list of PathRecord objects."""
        return [
            PathRecord(
                track_id=  self._text(row, _COL_TRACK_ID),
                name=      self._text(row, _COL_NAME),
                x=         self._float(row, _COL_X),
                z=         self._float(row, _COL_Z),
                length_mm= self._float(row, _COL_LENGTH_MM),
            )
            for row in range(self.table.rowCount())
        ]

    def validate(self) -> list[str]:
        """Run validation and apply visual highlights.

        Returns a list of error messages (empty → valid).
        """
        records = [r.to_dict() for r in self.to_records()]
        errors  = validate_paths(records)
        self._apply_highlights(errors)
        return [e.message for e in errors]

    # ------------------------------------------------------------------ #
    #  BasePage interface                                                   #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> list[dict]:
        return [r.to_dict() for r in self.to_records()]

    def from_dict(self, data: list[dict]) -> None:
        self.table.setRowCount(0)
        for raw in data:
            self.add_row(PathRecord.from_dict(raw))

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _float(self, row: int, col: int) -> float:
        try:
            return float(self._text(row, col))
        except ValueError:
            return 0.0

    def _apply_highlights(self, errors: list[ValidationError]) -> None:
        from PyQt6.QtGui import QColor
        _FIELD_TO_COL = {
            "track_id":  _COL_TRACK_ID,
            "length_mm": _COL_LENGTH_MM,
        }
        # Clear all highlights first
        for row in range(self.table.rowCount()):
            for col in _FIELD_TO_COL.values():
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("#ffffff"))

        for err in errors:
            col = _FIELD_TO_COL.get(err.field)
            if col is None:
                continue
            item = self.table.item(err.row, col)
            if item:
                item.setBackground(QColor("#ffcccc"))

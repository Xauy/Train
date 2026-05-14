"""
ui/pages/paths_page.py
Editor page for track / path definitions.

Responsibilities (this file):
  • Display and edit path rows in a QTableWidget.
  • Convert rows ↔ storage.models.PathRecord via to_dict / from_dict.
  • Auto-compute and display the Euclidean length whenever coordinates change.
  • Report the length of the currently-selected path (used by SostavPage).

Validation is delegated to validation.validators.validate_paths().
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt
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
_COL_X1        = 2
_COL_Y1        = 3
_COL_Z1        = 4
_COL_X2        = 5
_COL_Y2        = 6
_COL_Z2        = 7
_COL_LENGTH_MM = 8   # read-only — computed from coordinates
_COL_SELECTED  = 9

# Coordinate columns that trigger a length recalculation on change
_COORD_COLS = {_COL_X1, _COL_Y1, _COL_Z1, _COL_X2, _COL_Y2, _COL_Z2}


class PathsPage(BasePage):
    """QWidget that lets the user define railway tracks."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            ["track_id", "Название",
             "X1", "Y1", "Z1",
             "X2", "Y2", "Z2",
             "Длина (мм)", "Выбор"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._on_item_changed)
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

        # Block signals while populating so _on_item_changed doesn't
        # fire for each coordinate cell individually.
        self.table.blockSignals(True)
        r = record or PathRecord()
        self.table.setItem(row, _COL_TRACK_ID, QTableWidgetItem(r.track_id))
        self.table.setItem(row, _COL_NAME,     QTableWidgetItem(r.name))
        self.table.setItem(row, _COL_X1,       QTableWidgetItem(str(r.x1)))
        self.table.setItem(row, _COL_Y1,       QTableWidgetItem(str(r.y1)))
        self.table.setItem(row, _COL_Z1,       QTableWidgetItem(str(r.z1)))
        self.table.setItem(row, _COL_X2,       QTableWidgetItem(str(r.x2)))
        self.table.setItem(row, _COL_Y2,       QTableWidgetItem(str(r.y2)))
        self.table.setItem(row, _COL_Z2,       QTableWidgetItem(str(r.z2)))

        # Length — read-only display cell
        len_item = QTableWidgetItem(f"{r.length_mm:.2f}")
        len_item.setFlags(len_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, _COL_LENGTH_MM, len_item)

        chk = QCheckBox()
        self.table.setCellWidget(row, _COL_SELECTED, chk)
        self.table.blockSignals(False)

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
                track_id=self._text(row, _COL_TRACK_ID),
                name=    self._text(row, _COL_NAME),
                x1=self._float(row, _COL_X1), y1=self._float(row, _COL_Y1), z1=self._float(row, _COL_Z1),
                x2=self._float(row, _COL_X2), y2=self._float(row, _COL_Y2), z2=self._float(row, _COL_Z2),
            )
            for row in range(self.table.rowCount())
        ]

    def validate(self) -> list[str]:
        """Run validation and apply visual highlights.

        Returns a list of error messages (empty → valid).
        """
        records = []
        for r in self.to_records():
            d = r.to_dict()
            # length_mm is no longer stored in JSON but the validator still
            # needs it — supply the computed value.
            d["length_mm"] = r.length_mm
            records.append(d)
        errors = validate_paths(records)
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
            "length_mm": _COL_LENGTH_MM,  # zero-length path → highlight computed cell
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

    # ------------------------------------------------------------------ #
    #  Private — live length computation                                   #
    # ------------------------------------------------------------------ #

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        """Recompute and display the path length when a coordinate changes."""
        if item.column() in _COORD_COLS:
            self._update_length(item.row())

    def _update_length(self, row: int) -> None:
        """Recalculate the Euclidean length for *row* and update the cell."""
        x1 = self._float(row, _COL_X1); y1 = self._float(row, _COL_Y1); z1 = self._float(row, _COL_Z1)
        x2 = self._float(row, _COL_X2); y2 = self._float(row, _COL_Y2); z2 = self._float(row, _COL_Z2)
        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)

        self.table.blockSignals(True)
        len_item = self.table.item(row, _COL_LENGTH_MM)
        if len_item is None:
            len_item = QTableWidgetItem()
            len_item.setFlags(len_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, _COL_LENGTH_MM, len_item)
        len_item.setText(f"{length:.2f}")
        self.table.blockSignals(False)

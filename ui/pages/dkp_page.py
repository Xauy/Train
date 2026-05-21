"""
ui/pages/dkp_page.py
Editor page for ДКП (trackside detection sensor) definitions.

Responsibilities (this file):
  • Display and edit DKP rows.
  • Convert rows ↔ physics.models.DKPConfig dicts via to_dict / from_dict.
  • Translate ValidationError objects from validation.validators into
    cell highlights.

DKPs are POINT triggers — s_mm is the exact crossing position; there is
no detection zone (no zone_mm column).  The «Направление» column is a
dropdown with three values: LeftToRight, RightToLeft, Both.

Legacy project files that still contain "zone_mm" or "Any" for
direction are accepted transparently:
  • zone_mm is ignored on load.
  • "Any"  is normalised to "Both" by the QComboBox lookup.

No validation logic lives here.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QComboBox,
)

from ui.pages.base_page import BasePage
from validation.validators import validate_dkp_sensors, ValidationError

# Column indices
_COL_SENSOR_ID  = 0
_COL_TRACK_ID   = 1
_COL_S_MM       = 2
_COL_TYPE       = 3
_COL_ENABLED    = 4
_COL_DIRECTION  = 5
_COL_DELETE     = 6

_COLUMN_COUNT = 7

# Direction-filter dropdown values, in display order.
_DIRECTION_VALUES: tuple[str, ...] = ("Both", "LeftToRight", "RightToLeft")
# Legacy values mapped to current ones (for old project files).
_DIRECTION_ALIASES: dict[str, str] = {
    "Any": "Both",
    "":    "Both",
}

# Maps field names (from ValidationError) to column indices
_FIELD_TO_COL: dict[str, int] = {
    "s_mm":    _COL_S_MM,
}


class DkpPage(BasePage):
    """QWidget that lets the user define trackside detection sensors."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels([
            "sensor_id", "track_id", "s_mm",
            "Тип системы", "Включён", "Направление", "",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить строку ДКП")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

    # ------------------------------------------------------------------ #
    #  Public — row management                                             #
    # ------------------------------------------------------------------ #

    def add_row(self, record: dict | None = None) -> None:
        """Insert a new row, optionally pre-filled from a DKPConfig dict."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        r = record or {}
        self.table.setItem(row, _COL_SENSOR_ID,
                           QTableWidgetItem(str(r.get("sensor_id", f"DKP_{row + 1}"))))
        self.table.setItem(row, _COL_TRACK_ID,
                           QTableWidgetItem(str(r.get("track_id", ""))))
        self.table.setItem(row, _COL_S_MM,
                           QTableWidgetItem(str(r.get("s_mm", 0))))

        # Sensor type — fixed dropdown
        type_combo = QComboBox()
        type_combo.addItems(["Fox", "Mongoose"])
        idx = type_combo.findText(str(r.get("sensor_type", "Fox")))
        type_combo.setCurrentIndex(max(idx, 0))
        self.table.setCellWidget(row, _COL_TYPE, type_combo)

        # Enabled — checkbox
        chk = QCheckBox()
        chk.setChecked(bool(r.get("enabled", True)))
        self.table.setCellWidget(row, _COL_ENABLED, chk)

        # Direction filter — dropdown.  Legacy "Any" maps to "Both".
        raw_dir = str(r.get("direction_filter", "Both"))
        dir_value = _DIRECTION_ALIASES.get(raw_dir, raw_dir)
        dir_combo = QComboBox()
        dir_combo.addItems(_DIRECTION_VALUES)
        d_idx = dir_combo.findText(dir_value)
        dir_combo.setCurrentIndex(d_idx if d_idx >= 0 else 0)
        self.table.setCellWidget(row, _COL_DIRECTION, dir_combo)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_row)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    # ------------------------------------------------------------------ #
    #  Public — validation                                                 #
    # ------------------------------------------------------------------ #

    def validate(self, path_lengths: dict[str, float]) -> list[str]:
        """Run DKP validation against *path_lengths* and highlight errors.

        Returns a list of error messages (empty → valid).
        """
        errors = validate_dkp_sensors(self.to_dict(), path_lengths)
        self._apply_highlights(errors)
        return [e.message for e in errors]

    # ------------------------------------------------------------------ #
    #  BasePage interface                                                   #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> list[dict]:
        rows = []
        for row in range(self.table.rowCount()):
            type_combo = self.table.cellWidget(row, _COL_TYPE)
            dir_combo  = self.table.cellWidget(row, _COL_DIRECTION)
            chk        = self.table.cellWidget(row, _COL_ENABLED)
            rows.append({
                "sensor_id":        self._text(row, _COL_SENSOR_ID),
                "track_id":         self._text(row, _COL_TRACK_ID),
                "s_mm":             self._float(row, _COL_S_MM),
                "sensor_type":      type_combo.currentText() if type_combo else "Fox",
                "enabled":          chk.isChecked() if chk else True,
                "direction_filter": dir_combo.currentText() if dir_combo else "Both",
            })
        return rows

    def from_dict(self, data: list[dict]) -> None:
        self.table.setRowCount(0)
        for record in data:
            self.add_row(record)

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _delete_row(self) -> None:
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, _COL_DELETE) is btn:
                self.table.removeRow(row)
                return

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
        # Clear existing highlights
        for row in range(self.table.rowCount()):
            for col in _FIELD_TO_COL.values():
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("#ffffff"))
        # Apply error highlights
        for err in errors:
            col = _FIELD_TO_COL.get(err.field)
            if col is None:
                continue
            item = self.table.item(err.row, col)
            if item:
                item.setBackground(QColor("#ffcccc"))

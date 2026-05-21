"""
ui/dialogs/axle_positions_dialog.py
Modal dialog for editing the longitudinal positions of a wagon's axles.

The dialog shows one row per axle.  Each row holds the offset (мм) from
the wagon's front face — same convention as physics.models.AxleDef.

Result format
─────────────
get_axles() returns ``list[dict]`` where each dict is
``{"offset_mm": float}``.  This is the canonical JSON form used by both
storage.models.AxleDef and physics.models.AxleDef, so callers can hand
it straight to ``AxleDef.from_dict`` or persist it as-is.

Inputs
──────
*initial_axles* — list of dicts in the same format.  If shorter than
*count*, missing entries are added with ``offset_mm = 0``; if longer,
the tail is truncated.  Pre-existing values are preserved across count
changes.

The dialog itself is decoupled from the wagon record — it operates on
plain dicts and has no Qt dependencies on WagonsDialog.
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
)

# Column indices
_COL_NUM    = 0
_COL_OFFSET = 1


class AxlePositionsDialog(QDialog):
    """Per-wagon axle-position editor.

    Usage::

        dlg = AxlePositionsDialog(
            self,
            count=4,
            initial_axles=[{"offset_mm": 1500}, {"offset_mm": 3500}],
            wagon_length_mm=20000.0,    # optional, only used for validation
        )
        if dlg.exec() == AxlePositionsDialog.DialogCode.Accepted:
            axles = dlg.get_axles()     # → list[dict]
    """

    def __init__(
        self,
        parent=None,
        *,
        count: int = 0,
        initial_axles: list[dict] | None = None,
        wagon_length_mm: float | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Положение осей вагона")
        self.resize(420, 360)

        self._wagon_length_mm = wagon_length_mm
        # The list of dicts we return on accept — kept in sync with the table.
        self._axles: List[dict] = []

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Смещение каждой оси (мм) отсчитывается от передней "
            "грани вагона по направлению движения."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        if wagon_length_mm is not None and wagon_length_mm > 0:
            len_label = QLabel(f"Длина вагона: {wagon_length_mm:.0f} мм")
            layout.addWidget(len_label)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["№ оси", "Смещение, мм"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.ok_btn     = QPushButton("Сохранить")
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addStretch()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.ok_btn.clicked.connect(self._on_accept)
        self.cancel_btn.clicked.connect(self.reject)

        self._populate(count=count, initial_axles=initial_axles or [])

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def get_axles(self) -> list[dict]:
        """Return the current axle list as plain dicts.

        Only call this after the dialog was accepted; the returned list
        reflects what was in the table at accept time.
        """
        return [dict(a) for a in self._axles]    # defensive copy

    # ------------------------------------------------------------------ #
    #  Private                                                             #
    # ------------------------------------------------------------------ #

    def _populate(self, *, count: int, initial_axles: list[dict]) -> None:
        """Fill the table with *count* rows, reusing values from *initial_axles*."""
        count = max(0, int(count))
        self.table.setRowCount(count)

        for row in range(count):
            # Read offset from initial_axles if available, else default to 0.
            if row < len(initial_axles):
                try:
                    offset = float(initial_axles[row].get("offset_mm", 0.0))
                except (TypeError, ValueError):
                    offset = 0.0
            else:
                offset = 0.0

            # № column — read-only
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, _COL_NUM, num_item)

            # Offset cell — editable
            off_item = QTableWidgetItem(f"{offset:g}")
            self.table.setItem(row, _COL_OFFSET, off_item)

    def _on_accept(self) -> None:
        """Validate input and close the dialog with .accept()."""
        new_axles: List[dict] = []
        errors: List[str] = []

        for row in range(self.table.rowCount()):
            text = self._text(row, _COL_OFFSET)
            try:
                offset = float(text) if text else 0.0
            except ValueError:
                errors.append(f"Ось {row + 1}: «{text}» — не число.")
                continue

            if offset < 0:
                errors.append(
                    f"Ось {row + 1}: смещение не может быть отрицательным "
                    f"(сейчас {offset})."
                )
                continue

            if (self._wagon_length_mm is not None
                    and self._wagon_length_mm > 0
                    and offset > self._wagon_length_mm):
                errors.append(
                    f"Ось {row + 1}: смещение {offset} мм превышает длину вагона "
                    f"({self._wagon_length_mm:.0f} мм)."
                )
                continue

            new_axles.append({"offset_mm": offset})

        if errors:
            QMessageBox.warning(
                self, "Некорректные данные",
                "\n".join(errors),
            )
            return

        self._axles = new_axles
        self.accept()

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

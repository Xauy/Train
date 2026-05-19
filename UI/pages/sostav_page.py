"""
ui/pages/sostav_page.py
Editor page for train composition (Состав).

Bug fixed vs. original:
  The original _make_delete_handler(row) captured the row index at creation
  time.  After a higher row was deleted the stored index became stale.
  The fix uses the sender()-search pattern (same as DkpPage) so the correct
  live row is always found at click time.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QLabel, QComboBox, QMessageBox,
)

from ui.dialogs.wagons_dialog import WagonsDialog
from ui.pages.base_page import BasePage

# Column indices
_COL_NUM    = 0
_COL_NAME   = 1
_COL_COUNT  = 2
_COL_BASE   = 3
_COL_LENGTH = 4
_COL_HEIGHT = 5
_COL_DELETE = 6
_COL_MODEL = 7

class SostavPage(BasePage):
    """QWidget that lets the user assemble a train composition."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # ── Composition table ──────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Номер в составе", "Название", "Кол-во",
            "База", "Длина", "Высота", "Удалить", "3D модель"
        ])
        self.table.setColumnHidden(_COL_MODEL, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить элемент состава")
        add_btn.clicked.connect(lambda: self.add_row({}))
        layout.addWidget(add_btn)

        # ── Info panel ────────────────────────────────────────────────
        info_layout = QVBoxLayout()

        self.length_label = QLabel("Длина 0 мм")
        info_layout.addWidget(self.length_label)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("Начальная координата:"))
        self.start_coord_edit = QLineEdit()
        self.start_coord_edit.setPlaceholderText("Начальная координата")
        coord_layout.addWidget(self.start_coord_edit)
        info_layout.addLayout(coord_layout)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Начальное направление:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["LeftToRight", "RightToLeft", "Stop"])
        dir_layout.addWidget(self.direction_combo)
        info_layout.addLayout(dir_layout)

        layout.addLayout(info_layout)

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def set_length(self, length_mm: float) -> None:
        self.length_label.setText(f"Длина {length_mm:.0f} мм")

    def add_row(self, record: dict | None = None) -> None:
        """Insert a new row, optionally pre-filled from *record*."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        r = record or {}

        # № — button that opens the wagon browser
        btn_num = QPushButton(str(r.get("wagon_label", "Выбрать вагон")))
        btn_num.clicked.connect(self._open_wagon_browser)
        self.table.setCellWidget(row, _COL_NUM, btn_num)

        # Создаём нередактируемые элементы для свойств вагона
        self._set_read_only_item(row, _COL_NAME, str(r.get("name", "")))
        self.table.setItem(row, _COL_COUNT, QTableWidgetItem(str(r.get("count", ""))))
        self._set_read_only_item(row, _COL_BASE, str(r.get("base", "")))
        self._set_read_only_item(row, _COL_LENGTH, str(r.get("length", "")))
        self._set_read_only_item(row, _COL_HEIGHT, str(r.get("height", "")))

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_row)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

        # model_path: сохраняем как скрытый элемент
        model_path = record.get("model_path", "")
        self._set_read_only_item(row, _COL_MODEL, model_path)

    # ------------------------------------------------------------------ #
    #  BasePage interface                                                   #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> list[dict]:
        rows = []
        for row in range(self.table.rowCount()):
            btn = self.table.cellWidget(row, _COL_NUM)
            rows.append({
                "wagon_label": btn.text() if btn else "",
                "name":   self._text(row, _COL_NAME),
                "count":  self._text(row, _COL_COUNT),
                "base":   self._text(row, _COL_BASE),
                "length": self._text(row, _COL_LENGTH),
                "height": self._text(row, _COL_HEIGHT),
                "model_path": self._text(row, _COL_MODEL),
            })
        return rows

    def from_dict(self, data: list[dict]) -> None:
        self.table.setRowCount(0)
        for record in data:
            self.add_row(record)

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _open_wagon_browser(self) -> None:
        """Find the row that owns the clicked button and open wagon dialog."""
        btn = self.sender()
        row = self._find_row(btn, _COL_NUM)
        if row < 0:
            return

        dlg = WagonsDialog(self)
        if dlg.exec() == WagonsDialog.DialogCode.Accepted:
            label = f"{dlg.selected_id} - {dlg.selected_name}"
            btn.setText(label)
            # Заполняем readonly-ячейки данными из диалога
            self._set_read_only_item(row, _COL_NAME,   dlg.selected_name   or "")
            self._set_read_only_item(row, _COL_BASE,   dlg.selected_base   or "")
            self._set_read_only_item(row, _COL_LENGTH, dlg.selected_length or "")
            self._set_read_only_item(row, _COL_HEIGHT, dlg.selected_height or "")
            self._set_read_only_item(row, _COL_MODEL, dlg.selected_model or "")

    def _delete_row(self) -> None:
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        row = self._find_row(btn, _COL_DELETE)
        if row >= 0:
            self.table.removeRow(row)

    def _find_row(self, widget, col: int) -> int:
        """Return the row whose cell widget in *col* is *widget*, or -1."""
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, col) is widget:
                return row
        return -1

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _set_read_only_item(self, row: int, col: int, text: str) -> None:
        """Create or update a read-only QTableWidgetItem in the given cell."""
        item = self.table.item(row, col)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, col, item)
        item.setText(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
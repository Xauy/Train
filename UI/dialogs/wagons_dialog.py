"""
ui/dialogs/wagons_dialog.py
Modal dialog for browsing and selecting a wagon from the wagon library.

On accept, selected_id and selected_name are populated.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QComboBox, QTableWidgetItem, QHeaderView, QMessageBox,
)

# Column indices
_COL_ID      = 0
_COL_NAME    = 1
_COL_TYPE    = 2
_COL_BASE    = 3
_COL_LENGTH  = 4
_COL_HEIGHT  = 5
_COL_DELETE  = 6


class WagonsDialog(QDialog):
    """Dialog that lets the user pick a wagon from an editable list."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Браузер вагонов")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Название", "Тип", "База", "Длина",
            "Высота", "",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить вагон")
        self.select_btn = QPushButton("Выбрать")
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # Набор возвращаемых значений
        self.selected_id: str | None = None
        self.selected_name: str | None = None
        self.selected_base: str | None = None
        self.selected_length: str | None = None
        self.selected_height: str | None = None

        self.add_btn.clicked.connect(self._add_wagon)
        self.select_btn.clicked.connect(self._select_wagon)
        self.cancel_btn.clicked.connect(self.reject)

    # ------------------------------------------------------------------ #
    #  Private                                                             #
    # ------------------------------------------------------------------ #

    def _add_wagon(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, _COL_ID, QTableWidgetItem(""))
        self.table.setItem(row, _COL_NAME, QTableWidgetItem(""))
        self.table.setItem(row, _COL_BASE, QTableWidgetItem(""))
        self.table.setItem(row, _COL_LENGTH, QTableWidgetItem(""))
        self.table.setItem(row, _COL_HEIGHT, QTableWidgetItem(""))
        r = {}
        combo = QComboBox()
        combo.addItems(["Цистерна", "Крытый", "Полувагон", "Платформа", "Думпкар", "Хоппер", "Транспортер"])
        idx = combo.findText(str(r.get("sensor_type", "Цистерна")))
        combo.setCurrentIndex(max(idx, 0))
        self.table.setCellWidget(row, _COL_TYPE, combo)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_wagon)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    def _delete_wagon(self) -> None:
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, _COL_DELETE) is btn:
                self.table.removeRow(row)
                return

    def _select_wagon(self) -> None:
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите вагон из таблицы")
            return
        id_item   = self.table.item(current_row, _COL_ID)
        name_item = self.table.item(current_row, _COL_NAME)
        base_item = self.table.item(current_row, _COL_BASE)
        length_item = self.table.item(current_row, _COL_LENGTH)
        height_item = self.table.item(current_row, _COL_HEIGHT)

        self.selected_id     = id_item.text()     if id_item     else ""
        self.selected_name   = name_item.text()   if name_item   else ""
        self.selected_base   = base_item.text()   if base_item   else ""
        self.selected_length = length_item.text() if length_item else ""
        self.selected_height = height_item.text() if height_item else ""
        self.accept()

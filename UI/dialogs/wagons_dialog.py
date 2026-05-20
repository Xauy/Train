"""
ui/dialogs/wagons_dialog.py
Modal dialog for browsing and selecting a wagon from the wagon library.

On accept, selected_id and selected_name are populated.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QComboBox, QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox,
)
from storage.wagon_repository import load_wagons, save_wagons

# Column indices
_COL_ID      = 0
_COL_NAME    = 1
_COL_TYPE    = 2
_COL_BASE    = 3
_COL_LENGTH  = 4
_COL_HEIGHT  = 5
_COL_MODEL   = 6
_COL_DELETE  = 7


class WagonsDialog(QDialog):
    """Dialog that lets the user pick a wagon from an editable list."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Браузер вагонов")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Название", "Тип", "База", "Длина",
            "Высота", "3d модель (путь)", "",
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
        self.selected_type: str | None = None
        self.selected_base: str | None = None
        self.selected_length: str | None = None
        self.selected_height: str | None = None
        self.selected_model: str | None = None

        self.add_btn.clicked.connect(self._add_wagon)
        self.select_btn.clicked.connect(self._select_wagon)
        self.cancel_btn.clicked.connect(self.reject)

        # Загружаем сохранённые данные при открытии
        self._load_from_repository()

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def _load_from_repository(self) -> None:
        """Clear the table and fill it with data from the JSON file."""
        wagons = load_wagons()
        self.table.setRowCount(0)
        for w in wagons:
            self._add_row_from_data(w)

    def _save_to_repository(self) -> None:
        """Extract all rows from the table and save them to the JSON file."""
        wagons = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, _COL_TYPE)
            wagon_type = combo.currentText() if combo else "Цистерна"
            model_btn = self.table.cellWidget(row, _COL_MODEL)
            model_path = model_btn.text() if model_btn else ""
            wagons.append({
                "id": self._text(row, _COL_ID),
                "name": self._text(row, _COL_NAME),
                "type": wagon_type,
                "base": self._text(row, _COL_BASE),
                "length": self._text(row, _COL_LENGTH),
                "height": self._text(row, _COL_HEIGHT),
                "model_path": model_path,
            })
        save_wagons(wagons)

    def closeEvent(self, event) -> None:
        """Save the current table contents before closing."""
        self._save_to_repository()
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    #  Row helpers                                                         #
    # ------------------------------------------------------------------ #

    def _add_row_from_data(self, data: dict) -> None:
        """Insert a row and fill it with values from *data*."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, _COL_ID, QTableWidgetItem(data.get("id", "")))
        self.table.setItem(row, _COL_NAME, QTableWidgetItem(data.get("name", "")))
        self.table.setItem(row, _COL_BASE, QTableWidgetItem(data.get("base", "")))
        self.table.setItem(row, _COL_LENGTH, QTableWidgetItem(data.get("length", "")))
        self.table.setItem(row, _COL_HEIGHT, QTableWidgetItem(data.get("height", "")))

        model_btn = QPushButton(data.get("model_path", "") or "Выбрать .obj")
        model_btn.clicked.connect(self._choose_model)
        self.table.setCellWidget(row, _COL_MODEL, model_btn)

        # QComboBox для типа вагона
        combo = QComboBox()
        combo.addItems([
            "Цистерна", "Крытый", "Полувагон", "Платформа",
            "Думпкар", "Хоппер", "Транспортер"
        ])
        idx = combo.findText(data.get("type", "Цистерна"))
        combo.setCurrentIndex(max(idx, 0))
        self.table.setCellWidget(row, _COL_TYPE, combo)

        # Кнопка удаления
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_wagon)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    # ------------------------------------------------------------------ #
    #  Private                                                      #
    # ------------------------------------------------------------------ #

    def _add_wagon(self) -> None:
        """Add an empty row (user will fill it in)."""
        self._add_row_from_data({})

    def _choose_model(self) -> None:
        """Открыть проводник для выбора файла .obj и записать путь в кнопку."""
        btn = self.sender()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать 3D-модель", "",
            "OBJ Files (*.obj);;All Files (*)"
        )
        if file_path:
            btn.setText(file_path)

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
        id_item = self.table.item(current_row, _COL_ID)
        name_item = self.table.item(current_row, _COL_NAME)
        type_combo = self.table.cellWidget(current_row, _COL_TYPE)
        base_item = self.table.item(current_row, _COL_BASE)
        length_item = self.table.item(current_row, _COL_LENGTH)
        height_item = self.table.item(current_row, _COL_HEIGHT)
        model_btn = self.table.cellWidget(current_row, _COL_MODEL)
        model_path = model_btn.text() if model_btn else ""
        self.selected_model = model_path
        self._save_to_repository()

        self.selected_id = id_item.text() if id_item else ""
        self.selected_name = name_item.text() if name_item else ""
        self.selected_type = type_combo.currentText() if type_combo else ""
        self.selected_base = base_item.text() if base_item else ""
        self.selected_length = length_item.text() if length_item else ""
        self.selected_height = height_item.text() if height_item else ""
        self.accept()
    # ------------------------------------------------------------------ #
    #  Utility                                                            #
    # ------------------------------------------------------------------ #

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""
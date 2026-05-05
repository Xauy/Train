from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QLabel, QComboBox, QMessageBox
)
from wagons_dialog import WagonsDialog


class SostavPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Таблица состава
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["Номер в составе", "Название", "Кол-во", "База", "Длина", "Высота", "Изменить", "Удалить"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить элемент состава")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

        # Информационная панель
        info_layout = QVBoxLayout()
        self.length_label = QLabel("Длина 0 мм")
        info_layout.addWidget(self.length_label)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("Начальная координата:"))
        self.start_coord_edit = QLineEdit()
        self.start_coord_edit.setPlaceholderText("Начальная координата")
        coord_layout.addWidget(self.start_coord_edit)
        info_layout.addLayout(coord_layout)

        direction_layout = QHBoxLayout()
        direction_layout.addWidget(QLabel("Начальное направление:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Вперёд", "Назад", "Стоять"])
        direction_layout.addWidget(self.direction_combo)
        info_layout.addLayout(direction_layout)

        layout.addLayout(info_layout)

    def set_length(self, length_mm: int):
        self.length_label.setText(f"Длина {length_mm} мм")

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        btn_number = QPushButton("Выбрать вагон")
        btn_number.clicked.connect(self._make_wagon_selector(row))
        self.table.setCellWidget(row, 0, btn_number)

        for col in range(1, 6):
            self.table.setItem(row, col, QTableWidgetItem(""))

        edit_btn = QPushButton("Изменить")
        edit_btn.clicked.connect(lambda: QMessageBox.information(self, "Заглушка", "Функция изменения"))
        self.table.setCellWidget(row, 6, edit_btn)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._make_delete_handler(row))
        self.table.setCellWidget(row, 7, del_btn)

    def _make_wagon_selector(self, row):
        def handler():
            dlg = WagonsDialog(self)
            if dlg.exec() == WagonsDialog.DialogCode.Accepted:
                btn = self.table.cellWidget(row, 0)
                if btn:
                    btn.setText(f"{dlg.selected_id} - {dlg.selected_name}")
        return handler

    def _make_delete_handler(self, row):
        def handler():
            self.table.removeRow(row)
        return handler
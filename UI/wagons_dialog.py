from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)


class WagonsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Браузер вагонов")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Название", "Тип", "База", "Длина", "Высота", "3d модель (путь)", ""]
        )
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

        self.selected_id = None
        self.selected_name = None

        self.add_btn.clicked.connect(self._add_wagon)
        self.select_btn.clicked.connect(self._select_wagon)
        self.cancel_btn.clicked.connect(self.reject)

    def _create_delete_handler(self, row):
        def handler():
            self.table.removeRow(row)
        return handler

    def _add_wagon(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(self.table.columnCount() - 1):
            self.table.setItem(row, col, QTableWidgetItem(""))
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._create_delete_handler(row))
        self.table.setCellWidget(row, self.table.columnCount() - 1, del_btn)

    def _select_wagon(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите вагон из таблицы")
            return
        self.selected_id = self.table.item(current_row, 0).text() if self.table.item(current_row, 0) else ""
        self.selected_name = self.table.item(current_row, 1).text() if self.table.item(current_row, 1) else ""
        self.accept()
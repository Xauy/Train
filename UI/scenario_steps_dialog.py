from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QMessageBox
)


class ScenarioStepsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создание сценария")
        self.resize(700, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["№", "Начал. Скорость", "Ускорение", "Порог скорости", "Поведение", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Добавить сценарий")
        self.select_btn = QPushButton("Выбрать")
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.selected_step_number = None

        self.add_btn.clicked.connect(self._add_step)
        self.select_btn.clicked.connect(self._select_step)
        self.cancel_btn.clicked.connect(self.reject)

    def _insert_step_row(self, row, data):
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(data[0])))
        self.table.setItem(row, 1, QTableWidgetItem(str(data[1])))
        self.table.setItem(row, 2, QTableWidgetItem(str(data[2])))
        self.table.setItem(row, 3, QTableWidgetItem(str(data[3])))
        chk = QCheckBox()
        chk.setChecked(data[4])
        self.table.setCellWidget(row, 4, chk)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._create_delete_handler(row))
        self.table.setCellWidget(row, 5, del_btn)

    def _create_delete_handler(self, row):
        def handler():
            self.table.removeRow(row)
            self._renumber_steps()
        return handler

    def _renumber_steps(self):
        for row in range(self.table.rowCount()):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

    def _add_step(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QTableWidgetItem("0"))
        self.table.setItem(row, 2, QTableWidgetItem("0"))
        self.table.setItem(row, 3, QTableWidgetItem("0"))
        chk = QCheckBox()
        self.table.setCellWidget(row, 4, chk)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._create_delete_handler(row))
        self.table.setCellWidget(row, 5, del_btn)

    def _select_step(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите строку с шагом")
            return
        num_item = self.table.item(current_row, 0)
        if num_item:
            self.selected_step_number = num_item.text()
        else:
            self.selected_step_number = ""
        self.accept()
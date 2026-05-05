from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from scenario_steps_dialog import ScenarioStepsDialog


class ScenarioPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["№", "Название", "Кол-во шагов", "Статус", ""])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить сценарий")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)

        btn = QPushButton(str(row + 1))
        btn.clicked.connect(lambda checked, button=btn: self._open_steps_dialog(button))
        self.table.setCellWidget(row, 0, btn)

        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem(""))

        chk = QCheckBox()
        self.table.setCellWidget(row, 3, chk)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._make_delete_handler(row))
        self.table.setCellWidget(row, 4, del_btn)

    def _open_steps_dialog(self, button):
        dlg = ScenarioStepsDialog(self)
        if dlg.exec() == ScenarioStepsDialog.DialogCode.Accepted and dlg.selected_step_number is not None:
            button.setText(dlg.selected_step_number)

    def _make_delete_handler(self, row):
        def handler():
            self.table.removeRow(row)
        return handler
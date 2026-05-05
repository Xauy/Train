from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QComboBox
)


class DkpPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "track_id", "Тип системы", "Статус", "Направление", "zone_mm"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить строку ДКП")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        combo = QComboBox()
        combo.addItems(["Автоблокировка", "Релейная", "Микропроцессорная"])
        self.table.setCellWidget(row, 2, combo)
        chk = QCheckBox()
        self.table.setCellWidget(row, 3, chk)
        self.table.setItem(row, 4, QTableWidgetItem(""))
        self.table.setItem(row, 5, QTableWidgetItem(""))
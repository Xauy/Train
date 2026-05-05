from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)


class PathsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["track_id", "Название", "X", "Z", "Длина(мм)", "Выбор"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить путь")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(5):
            self.table.setItem(row, col, QTableWidgetItem(""))
        chk = QCheckBox()
        self.table.setCellWidget(row, 5, chk)

    # Возвращает длину первого отмеченного пути или 0.
    def get_selected_path_length(self) -> int:
        for row in range(self.table.rowCount()):
            chk_widget = self.table.cellWidget(row, 5)
            if chk_widget and chk_widget.isChecked():
                item = self.table.item(row, 4)
                if item:
                    try:
                        return int(item.text())
                    except ValueError:
                        return 0
        if self.table.rowCount() > 0:
            item = self.table.item(0, 4)
            if item:
                try:
                    return int(item.text())
                except ValueError:
                    return 0
        return 0
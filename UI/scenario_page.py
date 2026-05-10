from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from scenario_steps_dialog import ScenarioStepsDialog

# Column indices
_COL_NUM    = 0
_COL_NAME   = 1
_COL_COUNT  = 2
_COL_STATUS = 3
_COL_DELETE = 4


class ScenarioPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["№", "Название", "Кол-во шагов", "Статус", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить сценарий")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

        # Parallel list: one entry per table row, holds the list of step dicts.
        # Updated whenever the steps dialog is accepted.
        self._steps_data: list[list[dict]] = []

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._steps_data.append([])

        # № button — opens the steps dialog for this row
        btn = QPushButton(str(row + 1))
        btn.clicked.connect(self._open_steps_dialog)
        self.table.setCellWidget(row, _COL_NUM, btn)

        self.table.setItem(row, _COL_NAME,  QTableWidgetItem(""))
        self.table.setItem(row, _COL_COUNT, QTableWidgetItem("0"))

        chk = QCheckBox()
        self.table.setCellWidget(row, _COL_STATUS, chk)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_row)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    def to_dict(self) -> list[dict]:
        result = []
        for row in range(self.table.rowCount()):
            chk = self.table.cellWidget(row, _COL_STATUS)
            result.append({
                "name":    self._cell_text(row, _COL_NAME),
                "active":  chk.isChecked() if chk else False,
                "steps":   list(self._steps_data[row]),
            })
        return result

    def from_dict(self, data: list[dict]):
        self.table.setRowCount(0)
        self._steps_data.clear()

        for record in data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            steps = record.get("steps", [])
            self._steps_data.append(list(steps))

            btn = QPushButton(str(row + 1))
            btn.clicked.connect(self._open_steps_dialog)
            self.table.setCellWidget(row, _COL_NUM, btn)

            self.table.setItem(row, _COL_NAME,  QTableWidgetItem(str(record.get("name", ""))))
            self.table.setItem(row, _COL_COUNT, QTableWidgetItem(str(len(steps))))

            chk = QCheckBox()
            chk.setChecked(bool(record.get("active", False)))
            self.table.setCellWidget(row, _COL_STATUS, chk)

            del_btn = QPushButton("Удалить")
            del_btn.clicked.connect(self._delete_row)
            self.table.setCellWidget(row, _COL_DELETE, del_btn)

    # ------------------------------------------------------------------ #
    #  Private                                                             #
    # ------------------------------------------------------------------ #

    def _open_steps_dialog(self):
        """Find which row the button belongs to, open dialog with its steps."""
        btn = self.sender()
        row = self._find_row_of_widget(btn, _COL_NUM)
        if row < 0:
            return

        existing_steps = self._steps_data[row] if row < len(self._steps_data) else []
        dlg = ScenarioStepsDialog(self, initial_steps=existing_steps)

        if dlg.exec() == ScenarioStepsDialog.DialogCode.Accepted:
            steps = dlg.get_steps()
            self._steps_data[row] = steps
            # Update step count cell
            self.table.setItem(row, _COL_COUNT, QTableWidgetItem(str(len(steps))))

    def _delete_row(self):
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        row = self._find_row_of_widget(btn, _COL_DELETE)
        if row < 0:
            return
        self.table.removeRow(row)
        del self._steps_data[row]

    def _find_row_of_widget(self, widget, col: int) -> int:
        """Return the table row whose cell widget in *col* is *widget*, or -1."""
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, col) is widget:
                return row
        return -1

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

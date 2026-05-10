from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox
)
from PyQt6.QtCore import QTime

# Column indices
_COL_NUM        = 0
_COL_DURATION   = 1
_COL_V0         = 2
_COL_ACCEL      = 3
_COL_THRESHOLD  = 4
_COL_BEHAVIOR   = 5
_COL_DELETE     = 6

_BEHAVIORS = ["LeftToRight", "RightToLeft", "Stop"]


class ScenarioStepsDialog(QDialog):
    def __init__(self, parent=None, initial_steps: list[dict] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Создание сценария")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "№", "Продолжительность", "Нач. скорость",
            "Ускорение", "Порог скорости", "Поведение", ""
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.add_btn    = QPushButton("Добавить шаг")
        self.select_btn = QPushButton("Выбрать")
        self.cancel_btn = QPushButton("Отмена")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.select_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.selected_step_number: str | None = None

        self.add_btn.clicked.connect(self._add_step)
        self.select_btn.clicked.connect(self._select_step)
        self.cancel_btn.clicked.connect(self.reject)

        # Populate with existing steps if provided
        if initial_steps:
            self.set_steps(initial_steps)

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def get_steps(self) -> list[dict]:
        """Return all steps as a list of dicts (matches ScenarioStep schema)."""
        steps = []
        for row in range(self.table.rowCount()):
            time_edit = self.table.cellWidget(row, _COL_DURATION)
            duration_ms = (
                time_edit.time().msecsSinceStartOfDay()
                if time_edit else 0
            )

            behavior_combo = self.table.cellWidget(row, _COL_BEHAVIOR)
            behavior = behavior_combo.currentText() if behavior_combo else "LeftToRight"

            steps.append({
                "duration_ms":       duration_ms,
                "v0_mms":            self._float(row, _COL_V0),
                "accel_mms2":        self._float(row, _COL_ACCEL),
                "v_threshold_mms":   self._float(row, _COL_THRESHOLD),
                "behavior":          behavior,
            })
        return steps

    def set_steps(self, steps: list[dict]):
        """Populate the table from a list of step dicts."""
        self.table.setRowCount(0)
        for step in steps:
            self._insert_row(
                duration_ms=step.get("duration_ms", 0),
                v0=step.get("v0_mms", 0.0),
                accel=step.get("accel_mms2", 0.0),
                threshold=step.get("v_threshold_mms", 0.0),
                behavior=step.get("behavior", "LeftToRight"),
            )

    # ------------------------------------------------------------------ #
    #  Private — row management                                            #
    # ------------------------------------------------------------------ #

    def _add_step(self):
        self._insert_row(duration_ms=0, v0=0.0, accel=0.0, threshold=0.0,
                         behavior="LeftToRight")

    def _insert_row(self, *, duration_ms: int, v0: float, accel: float,
                    threshold: float, behavior: str):
        from PyQt6.QtWidgets import QTimeEdit

        row = self.table.rowCount()
        self.table.insertRow(row)

        # № — read-only numbering
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setFlags(num_item.flags() & ~(num_item.flags() & 0x2))  # not editable
        self.table.setItem(row, _COL_NUM, num_item)

        # Продолжительность — QTimeEdit hh:mm:ss
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("hh:mm:ss")
        time_edit.setTime(QTime.fromMSecsSinceStartOfDay(duration_ms))
        self.table.setCellWidget(row, _COL_DURATION, time_edit)

        # Numeric fields
        self.table.setItem(row, _COL_V0,        QTableWidgetItem(str(v0)))
        self.table.setItem(row, _COL_ACCEL,     QTableWidgetItem(str(accel)))
        self.table.setItem(row, _COL_THRESHOLD, QTableWidgetItem(str(threshold)))

        # Поведение — QComboBox
        combo = QComboBox()
        combo.addItems(_BEHAVIORS)
        idx = combo.findText(behavior)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, _COL_BEHAVIOR, combo)

        # Delete button — uses sender() to find its own row at call time
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_step)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    def _delete_step(self):
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, _COL_DELETE) is btn:
                self.table.removeRow(row)
                self._renumber_steps()
                break

    def _renumber_steps(self):
        for row in range(self.table.rowCount()):
            self.table.setItem(row, _COL_NUM, QTableWidgetItem(str(row + 1)))

    def _select_step(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите строку с шагом")
            return
        num_item = self.table.item(current_row, _COL_NUM)
        self.selected_step_number = num_item.text() if num_item else ""
        self.accept()

    # ------------------------------------------------------------------ #
    #  Private — helpers                                                   #
    # ------------------------------------------------------------------ #

    def _float(self, row: int, col: int) -> float:
        item = self.table.item(row, col)
        try:
            return float(item.text()) if item else 0.0
        except ValueError:
            return 0.0

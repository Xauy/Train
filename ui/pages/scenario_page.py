"""
ui/pages/scenario_page.py
Editor page for simulation scenarios (Сценарий).

Each row represents one named scenario.  The step list for each scenario is
stored in a parallel list (_steps_data) and edited via ScenarioStepsDialog.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
)

from storage.models import ScenarioRecord, ScenarioStep
from ui.dialogs.scenario_steps_dialog import ScenarioStepsDialog
from ui.pages.base_page import BasePage

# Column indices
_COL_NUM    = 0
_COL_NAME   = 1
_COL_COUNT  = 2
_COL_STATUS = 3
_COL_DELETE = 4


class ScenarioPage(BasePage):
    """QWidget for creating and managing simulation scenarios."""

    def __init__(self, parent=None) -> None:
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

        # Parallel list — one entry per row, holds the list of step dicts.
        self._steps_data: list[list[dict]] = []

    # ------------------------------------------------------------------ #
    #  Public — row management                                             #
    # ------------------------------------------------------------------ #

    def add_row(self, record: ScenarioRecord | None = None) -> None:
        """Insert a new row, optionally pre-filled from *record*."""
        row = self.table.rowCount()
        r   = record or ScenarioRecord(scenario_id=f"SC_{row + 1}", name="")
        self.table.insertRow(row)

        # _steps_data stores raw step dicts so ScenarioStepsDialog can
        # consume them directly.  ScenarioRecord.steps is List[ScenarioStep],
        # so convert to dicts here.
        self._steps_data.append([s.to_dict() for s in r.steps])

        btn = QPushButton(str(row + 1))
        btn.clicked.connect(self._open_steps_dialog)
        self.table.setCellWidget(row, _COL_NUM, btn)

        self.table.setItem(row, _COL_NAME,  QTableWidgetItem(r.name))
        self.table.setItem(row, _COL_COUNT, QTableWidgetItem(str(len(r.steps))))

        chk = QCheckBox()
        self.table.setCellWidget(row, _COL_STATUS, chk)

        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_row)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    # ------------------------------------------------------------------ #
    #  BasePage interface                                                   #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> list[dict]:
        return [r.to_dict() for r in self._to_records()]

    def from_dict(self, data: list[dict]) -> None:
        self.table.setRowCount(0)
        self._steps_data.clear()
        for raw in data:
            self.add_row(ScenarioRecord.from_dict(raw))

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _to_records(self) -> list[ScenarioRecord]:
        records = []
        for row in range(self.table.rowCount()):
            records.append(ScenarioRecord(
                scenario_id=f"SC_{row + 1}",
                name=       self._text(row, _COL_NAME),
                steps=      [ScenarioStep.from_dict(s) for s in self._steps_data[row]],
            ))
        return records

    def _open_steps_dialog(self) -> None:
        btn = self.sender()
        row = self._find_row(btn, _COL_NUM)
        if row < 0:
            return

        existing = self._steps_data[row] if row < len(self._steps_data) else []
        dlg = ScenarioStepsDialog(self, initial_steps=existing)

        if dlg.exec() == ScenarioStepsDialog.DialogCode.Accepted:
            steps = dlg.get_steps()
            self._steps_data[row] = steps
            self.table.setItem(row, _COL_COUNT, QTableWidgetItem(str(len(steps))))

    def _delete_row(self) -> None:
        btn = self.sender()
        row = self._find_row(btn, _COL_DELETE)
        if row >= 0:
            self.table.removeRow(row)
            del self._steps_data[row]

    def _find_row(self, widget, col: int) -> int:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, col) is widget:
                return row
        return -1

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox, QComboBox,
    QMessageBox
)

# Column indices
_COL_SENSOR_ID  = 0
_COL_TRACK_ID   = 1
_COL_S_MM       = 2
_COL_TYPE       = 3
_COL_ENABLED    = 4
_COL_DIRECTION  = 5
_COL_ZONE_MM    = 6
_COL_DELETE     = 7


class DkpPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "sensor_id", "track_id", "s_mm",
            "Тип системы", "Включён", "Направление", "zone_mm", ""
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        add_btn = QPushButton("Добавить строку ДКП")
        add_btn.clicked.connect(self.add_row)
        layout.addWidget(add_btn)

    # ------------------------------------------------------------------ #
    #  Public                                                              #
    # ------------------------------------------------------------------ #

    def add_row(self):
        row = self.table.rowCount()

        self.table.insertRow(row)

        # sensor_id — editable, default DKP_N
        self.table.setItem(row, _COL_SENSOR_ID, QTableWidgetItem(f"DKP_{row + 1}"))

        # track_id — editable
        self.table.setItem(row, _COL_TRACK_ID, QTableWidgetItem(""))

        # s_mm — editable, numeric
        self.table.setItem(row, _COL_S_MM, QTableWidgetItem("0"))

        # Тип системы — QComboBox with Fox / Mongoose
        combo = QComboBox()
        combo.addItems(["Fox", "Mongoose"])
        self.table.setCellWidget(row, _COL_TYPE, combo)

        # Включён — QCheckBox, checked by default
        chk = QCheckBox()
        chk.setChecked(True)
        self.table.setCellWidget(row, _COL_ENABLED, chk)

        # Направление — editable
        self.table.setItem(row, _COL_DIRECTION, QTableWidgetItem(""))

        # zone_mm — editable, numeric
        self.table.setItem(row, _COL_ZONE_MM, QTableWidgetItem("100"))

        # Delete button
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_row)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    def validate(self, path_lengths: dict[str, float]) -> list[str]:
        """Check that every s_mm is within the referenced path length.

        path_lengths: {track_id: length_mm}
        Returns a list of error strings; empty list means OK.
        """
        errors = []
        for row in range(self.table.rowCount()):
            sensor_id = self._cell_text(row, _COL_SENSOR_ID)
            track_id  = self._cell_text(row, _COL_TRACK_ID)
            s_mm_text = self._cell_text(row, _COL_S_MM)

            try:
                s_mm = float(s_mm_text)
            except ValueError:
                errors.append(f"[{sensor_id}] s_mm не является числом: '{s_mm_text}'")
                self._highlight(row, _COL_S_MM, error=True)
                continue

            if s_mm < 0:
                errors.append(f"[{sensor_id}] s_mm не может быть отрицательным")
                self._highlight(row, _COL_S_MM, error=True)
                continue

            if track_id in path_lengths:
                if s_mm > path_lengths[track_id]:
                    errors.append(
                        f"[{sensor_id}] s_mm={s_mm} превышает длину пути "
                        f"'{track_id}' ({path_lengths[track_id]} мм)"
                    )
                    self._highlight(row, _COL_S_MM, error=True)
                    continue

            self._highlight(row, _COL_S_MM, error=False)

        return errors

    def to_dict(self) -> list[dict]:
        rows = []
        for row in range(self.table.rowCount()):
            combo   = self.table.cellWidget(row, _COL_TYPE)
            chk     = self.table.cellWidget(row, _COL_ENABLED)
            rows.append({
                "sensor_id":        self._cell_text(row, _COL_SENSOR_ID),
                "track_id":         self._cell_text(row, _COL_TRACK_ID),
                "s_mm":             self._float(row, _COL_S_MM),
                "sensor_type":      combo.currentText() if combo else "Fox",
                "enabled":          chk.isChecked() if chk else True,
                "direction_filter": self._cell_text(row, _COL_DIRECTION),
                "zone_mm":          self._float(row, _COL_ZONE_MM),
            })
        return rows

    def from_dict(self, data: list[dict]):
        self.table.setRowCount(0)
        for record in data:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, _COL_SENSOR_ID, QTableWidgetItem(str(record.get("sensor_id", ""))))
            self.table.setItem(row, _COL_TRACK_ID,  QTableWidgetItem(str(record.get("track_id", ""))))
            self.table.setItem(row, _COL_S_MM,       QTableWidgetItem(str(record.get("s_mm", 0))))

            combo = QComboBox()
            combo.addItems(["Fox", "Mongoose"])
            sensor_type = record.get("sensor_type", "Fox")
            idx = combo.findText(sensor_type)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            self.table.setCellWidget(row, _COL_TYPE, combo)

            chk = QCheckBox()
            chk.setChecked(bool(record.get("enabled", True)))
            self.table.setCellWidget(row, _COL_ENABLED, chk)

            self.table.setItem(row, _COL_DIRECTION, QTableWidgetItem(str(record.get("direction_filter", ""))))
            self.table.setItem(row, _COL_ZONE_MM,   QTableWidgetItem(str(record.get("zone_mm", 100))))

            del_btn = QPushButton("Удалить")
            del_btn.clicked.connect(self._delete_row)
            self.table.setCellWidget(row, _COL_DELETE, del_btn)

    # ------------------------------------------------------------------ #
    #  Private                                                             #
    # ------------------------------------------------------------------ #

    def _delete_row(self):
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, _COL_DELETE) is btn:
                self.table.removeRow(row)
                break

    def _cell_text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _float(self, row: int, col: int) -> float:
        try:
            return float(self._cell_text(row, col))
        except ValueError:
            return 0.0

    def _highlight(self, row: int, col: int, *, error: bool):
        from PyQt6.QtGui import QColor
        item = self.table.item(row, col)
        if item:
            item.setBackground(QColor("#ffcccc") if error else QColor("#ffffff"))

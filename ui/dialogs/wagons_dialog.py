"""
ui/dialogs/wagons_dialog.py
Modal dialog for browsing and selecting a wagon from the wagon library.

On accept, selected_id and selected_name are populated.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QComboBox, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QSpinBox,
)
from storage.wagon_repository import load_wagons, save_wagons
from physics.wagon_defaults import supported_wagon_types
from ui.dialogs.axle_positions_dialog import AxlePositionsDialog

# Column indices
_COL_ID         = 0
_COL_NAME       = 1
_COL_TYPE       = 2
_COL_BASE       = 3
_COL_LENGTH     = 4
_COL_HEIGHT     = 5
_COL_AXLE_COUNT = 6   # QSpinBox — number of axles
_COL_AXLES      = 7   # QPushButton — opens AxlePositionsDialog
_COL_MODEL      = 8
_COL_DELETE     = 9

_COLUMN_COUNT = 10

# Sensible bounds for the axle-count spinbox.
_MIN_AXLES = 0
_MAX_AXLES = 32


class WagonsDialog(QDialog):
    """Dialog that lets the user pick a wagon from an editable list."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Браузер вагонов")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels([
            "ID", "Название", "Тип", "База", "Длина", "Высота",
            "Кол-во осей", "Оси", "3d модель (путь)", "",
        ])
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

        # Набор возвращаемых значений
        self.selected_id: str | None = None
        self.selected_name: str | None = None
        self.selected_type: str | None = None
        self.selected_base: str | None = None
        self.selected_length: str | None = None
        self.selected_height: str | None = None
        self.selected_model: str | None = None
        # Axle list — list[dict] with shape [{"offset_mm": float}, …].
        # Empty list means "no explicit axles configured" — the caller
        # can derive a 2-bogie default from base/length.
        self.selected_axles: list[dict] = []
        # Per-row axle storage, parallel to table rows. Each entry is the
        # current list[dict] for that wagon row.  Kept here (not just in
        # QTableWidget cells) so the count spinbox and the «Оси» button
        # can read/write a structured value without re-parsing UI text.
        self._row_axles: list[list[dict]] = []

        self.add_btn.clicked.connect(self._add_wagon)
        self.select_btn.clicked.connect(self._select_wagon)
        self.cancel_btn.clicked.connect(self.reject)

        # Загружаем сохранённые данные при открытии
        self._load_from_repository()

    # ------------------------------------------------------------------ #
    #  Persistence                                                        #
    # ------------------------------------------------------------------ #

    def _load_from_repository(self) -> None:
        """Clear the table and fill it with data from the JSON file."""
        wagons = load_wagons()
        self.table.setRowCount(0)
        self._row_axles.clear()
        for w in wagons:
            self._add_row_from_data(w)

    def _save_to_repository(self) -> None:
        """Extract all rows from the table and save them to the JSON file."""
        wagons = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, _COL_TYPE)
            wagon_type = combo.currentText() if combo else "Цистерна"
            model_btn = self.table.cellWidget(row, _COL_MODEL)
            model_path = model_btn.text() if model_btn else ""
            spin = self.table.cellWidget(row, _COL_AXLE_COUNT)
            axle_count = int(spin.value()) if spin else 0
            axles = self._row_axles[row] if row < len(self._row_axles) else []
            wagons.append({
                "id": self._text(row, _COL_ID),
                "name": self._text(row, _COL_NAME),
                "type": wagon_type,
                "base": self._text(row, _COL_BASE),
                "length": self._text(row, _COL_LENGTH),
                "height": self._text(row, _COL_HEIGHT),
                "model_path": model_path,
                "axle_count": axle_count,
                "axles": [dict(a) for a in axles],   # defensive copy
            })
        save_wagons(wagons)

    def closeEvent(self, event) -> None:
        """Save the current table contents before closing."""
        self._save_to_repository()
        super().closeEvent(event)

    # ------------------------------------------------------------------ #
    #  Row helpers                                                         #
    # ------------------------------------------------------------------ #

    def _add_row_from_data(self, data: dict) -> None:
        """Insert a row and fill it with values from *data*."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        self.table.setItem(row, _COL_ID, QTableWidgetItem(data.get("id", "")))
        self.table.setItem(row, _COL_NAME, QTableWidgetItem(data.get("name", "")))
        self.table.setItem(row, _COL_BASE, QTableWidgetItem(data.get("base", "")))
        self.table.setItem(row, _COL_LENGTH, QTableWidgetItem(data.get("length", "")))
        self.table.setItem(row, _COL_HEIGHT, QTableWidgetItem(data.get("height", "")))

        model_btn = QPushButton(data.get("model_path", "") or "Выбрать .obj")
        model_btn.clicked.connect(self._choose_model)
        self.table.setCellWidget(row, _COL_MODEL, model_btn)

        # QComboBox для типа вагона
        combo = QComboBox()
        combo.addItems(supported_wagon_types())
        idx = combo.findText(data.get("type", "Цистерна"))
        combo.setCurrentIndex(max(idx, 0))
        self.table.setCellWidget(row, _COL_TYPE, combo)

        # ── Axles ────────────────────────────────────────────────────
        # Normalise the stored axle list, then choose a count.  Priority:
        #   1) explicit axle_count field (legacy / future use),
        #   2) length of the axles list,
        #   3) default of 4 axles (typical 2-bogie wagon).
        raw_axles = data.get("axles", []) or []
        axles: list[dict] = []
        for entry in raw_axles:
            if isinstance(entry, dict):
                try:
                    axles.append({"offset_mm": float(entry.get("offset_mm", 0.0))})
                except (TypeError, ValueError):
                    axles.append({"offset_mm": 0.0})

        try:
            explicit_count = int(data.get("axle_count", -1))
        except (TypeError, ValueError):
            explicit_count = -1
        if explicit_count >= 0:
            count = explicit_count
        elif axles:
            count = len(axles)
        else:
            count = 4

        count = max(_MIN_AXLES, min(_MAX_AXLES, count))

        # Pad / truncate the stored list to match count.
        if len(axles) < count:
            axles.extend({"offset_mm": 0.0} for _ in range(count - len(axles)))
        elif len(axles) > count:
            axles = axles[:count]

        # Parallel storage — index matches table row.
        self._row_axles.append(axles)

        # QSpinBox для количества осей
        spin = QSpinBox()
        spin.setRange(_MIN_AXLES, _MAX_AXLES)
        spin.setValue(count)
        spin.valueChanged.connect(self._on_axle_count_changed)
        self.table.setCellWidget(row, _COL_AXLE_COUNT, spin)

        # Кнопка «Оси» — открывает AxlePositionsDialog
        axle_btn = QPushButton(self._axles_button_label(count))
        axle_btn.clicked.connect(self._edit_axle_positions)
        self.table.setCellWidget(row, _COL_AXLES, axle_btn)

        # Кнопка удаления
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._delete_wagon)
        self.table.setCellWidget(row, _COL_DELETE, del_btn)

    # ------------------------------------------------------------------ #
    #  Private                                                      #
    # ------------------------------------------------------------------ #

    def _add_wagon(self) -> None:
        """Add an empty row (user will fill it in)."""
        self._add_row_from_data({})

    def _choose_model(self) -> None:
        """Открыть проводник для выбора файла .obj и записать путь в кнопку."""
        btn = self.sender()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбрать 3D-модель", "",
            "OBJ Files (*.obj);;All Files (*)"
        )
        if file_path:
            btn.setText(file_path)

    def _delete_wagon(self) -> None:
        """Find the row that owns the clicked button and remove it."""
        btn = self.sender()
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, _COL_DELETE) is btn:
                self.table.removeRow(row)
                if row < len(self._row_axles):
                    del self._row_axles[row]
                return

    def _select_wagon(self) -> None:
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Ошибка", "Выберите вагон из таблицы")
            return
        id_item = self.table.item(current_row, _COL_ID)
        name_item = self.table.item(current_row, _COL_NAME)
        type_combo = self.table.cellWidget(current_row, _COL_TYPE)
        base_item = self.table.item(current_row, _COL_BASE)
        length_item = self.table.item(current_row, _COL_LENGTH)
        height_item = self.table.item(current_row, _COL_HEIGHT)
        model_btn = self.table.cellWidget(current_row, _COL_MODEL)
        model_path = model_btn.text() if model_btn else ""
        self.selected_model = model_path
        self._save_to_repository()

        self.selected_id = id_item.text() if id_item else ""
        self.selected_name = name_item.text() if name_item else ""
        self.selected_type = type_combo.currentText() if type_combo else ""
        self.selected_base = base_item.text() if base_item else ""
        self.selected_length = length_item.text() if length_item else ""
        self.selected_height = height_item.text() if height_item else ""
        # Axles — defensive copy of the structured list for this row.
        if current_row < len(self._row_axles):
            self.selected_axles = [dict(a) for a in self._row_axles[current_row]]
        else:
            self.selected_axles = []
        self.accept()

    # ------------------------------------------------------------------ #
    #  Axle handlers                                                       #
    # ------------------------------------------------------------------ #

    def _on_axle_count_changed(self, new_count: int) -> None:
        """QSpinBox.valueChanged → keep _row_axles and the button label
        in sync.  Editing the count never opens the positions dialog;
        it just resizes the underlying list (preserving existing values).
        """
        spin = self.sender()
        row = self._find_row(spin, _COL_AXLE_COUNT)
        if row < 0:
            return

        new_count = max(_MIN_AXLES, min(_MAX_AXLES, int(new_count)))
        axles = self._row_axles[row]
        if len(axles) < new_count:
            axles.extend({"offset_mm": 0.0} for _ in range(new_count - len(axles)))
        elif len(axles) > new_count:
            del axles[new_count:]

        btn = self.table.cellWidget(row, _COL_AXLES)
        if btn is not None:
            btn.setText(self._axles_button_label(new_count))

    def _edit_axle_positions(self) -> None:
        """Open AxlePositionsDialog for the wagon whose «Оси» button was clicked."""
        btn = self.sender()
        row = self._find_row(btn, _COL_AXLES)
        if row < 0:
            return

        spin = self.table.cellWidget(row, _COL_AXLE_COUNT)
        count = int(spin.value()) if spin else len(self._row_axles[row])

        # Optional context: pass the wagon length so the dialog can flag
        # offsets that exceed it.  Parse leniently — bad input → no limit.
        try:
            wagon_length = float(self._text(row, _COL_LENGTH))
        except ValueError:
            wagon_length = None

        dlg = AxlePositionsDialog(
            self,
            count=count,
            initial_axles=self._row_axles[row],
            wagon_length_mm=wagon_length if (wagon_length and wagon_length > 0) else None,
        )
        if dlg.exec() == AxlePositionsDialog.DialogCode.Accepted:
            new_axles = dlg.get_axles()
            self._row_axles[row] = new_axles
            # Re-sync the spinbox in case dlg changed the effective count
            # (currently the dialog preserves count, but be defensive).
            if spin is not None and spin.value() != len(new_axles):
                spin.blockSignals(True)
                spin.setValue(len(new_axles))
                spin.blockSignals(False)
            btn.setText(self._axles_button_label(len(new_axles)))

    def _find_row(self, widget, col: int) -> int:
        """Return the row whose cell widget in *col* is *widget*, or -1."""
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, col) is widget:
                return row
        return -1

    @staticmethod
    def _axles_button_label(count: int) -> str:
        """Format the «Оси» button caption — Russian noun agreement."""
        if count == 0:
            return "Нет осей"
        # 1 ось, 2-4 оси, 5+ осей — but in practice 1/2/4/6/8 dominate;
        # keep the noun form readable without a full pluralisation lib.
        if count == 1:
            return "1 ось"
        if 2 <= count <= 4:
            return f"{count} оси"
        return f"{count} осей"
    # ------------------------------------------------------------------ #
    #  Utility                                                            #
    # ------------------------------------------------------------------ #

    def _text(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QComboBox, QLineEdit, QLabel, QDialog,
    QMessageBox, QAbstractItemView
)

# ----------------------------------------------------------------------
# Диалог выбора вагонов (браузер вагонов)
# ----------------------------------------------------------------------
class WagonsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Браузер вагонов")
        self.resize(800, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Тип", "База", "Длина", "Высота", "3d модель (путь)", ""])
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


# ----------------------------------------------------------------------
# Диалог для работы со сценариями
# ----------------------------------------------------------------------
class ScenarioStepsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создание сценария")
        self.resize(700, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["№", "Начал. Скорость", "Ускорение", "Порог скорости", "Поведение", ""])
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


# ----------------------------------------------------------------------
# Главное окно приложения
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Железнодорожный симулятор")
        self.resize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Панель с тремя кнопками
        button_layout = QHBoxLayout()
        self.btn_dkp = QPushButton("ДКП")
        self.btn_sostav = QPushButton("Состав")
        self.btn_scenario = QPushButton("Сценарий")
        button_layout.addWidget(self.btn_dkp)
        button_layout.addWidget(self.btn_sostav)
        button_layout.addWidget(self.btn_scenario)
        main_layout.addLayout(button_layout)

        # Стек страниц
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack)

        # Создаём страницы
        self.create_paths_page()   # индекс 0
        self.create_dkp_page()     # индекс 1
        self.create_sostav_page()  # индекс 2
        self.create_scenario_page()# индекс 3

        # Начальная страница - Пути (скрытая вкладка, но видимая таблица)
        self.stack.setCurrentIndex(0)
        self.current_mode = "paths"

        # Подключаем сигналы кнопок
        self.btn_dkp.clicked.connect(self.on_dkp_clicked)
        self.btn_sostav.clicked.connect(self.on_sostav_clicked)
        self.btn_scenario.clicked.connect(self.on_scenario_clicked)

    # ------------------------------------------------------------------
    # Страница "Пути"
    # ------------------------------------------------------------------
    def create_paths_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.paths_table = QTableWidget()
        self.paths_table.setColumnCount(6)
        self.paths_table.setHorizontalHeaderLabels(["track_id", "Название", "X", "Z", "Длина(мм)", "Выбор"])
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.paths_table)

        add_btn = QPushButton("Добавить путь")
        add_btn.clicked.connect(self.add_path_row)
        layout.addWidget(add_btn)

        self.stack.addWidget(page)

    def add_path_row(self):
        row = self.paths_table.rowCount()
        self.paths_table.insertRow(row)
        for col in range(5):
            self.paths_table.setItem(row, col, QTableWidgetItem(""))
        chk = QCheckBox()
        chk.stateChanged.connect(self.on_path_selection_changed)
        self.paths_table.setCellWidget(row, 5, chk)

    def on_path_selection_changed(self):
        self.update_sostav_length()

    def get_selected_path_length(self):
        for row in range(self.paths_table.rowCount()):
            chk_widget = self.paths_table.cellWidget(row, 5)
            if chk_widget and chk_widget.isChecked():
                item = self.paths_table.item(row, 4)
                if item:
                    try:
                        return int(item.text())
                    except:
                        return 0
        if self.paths_table.rowCount() > 0:
            item = self.paths_table.item(0, 4)
            if item:
                try:
                    return int(item.text())
                except:
                    return 0
        return 0

    # ------------------------------------------------------------------
    # Страница "ДКП"
    # ------------------------------------------------------------------
    def create_dkp_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.dkp_table = QTableWidget()
        self.dkp_table.setColumnCount(6)
        self.dkp_table.setHorizontalHeaderLabels(["ID", "track_id", "Тип системы", "Статус", "Направление", "zone_mm"])
        self.dkp_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.dkp_table)

        add_btn = QPushButton("Добавить строку ДКП")
        add_btn.clicked.connect(self.add_dkp_row)
        layout.addWidget(add_btn)

        self.stack.addWidget(page)

    def add_dkp_row(self):
        row = self.dkp_table.rowCount()
        self.dkp_table.insertRow(row)
        self.dkp_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.dkp_table.setItem(row, 1, QTableWidgetItem(""))
        combo = QComboBox()
        combo.addItems(["Автоблокировка", "Релейная", "Микропроцессорная"])
        self.dkp_table.setCellWidget(row, 2, combo)
        chk = QCheckBox()
        self.dkp_table.setCellWidget(row, 3, chk)
        self.dkp_table.setItem(row, 4, QTableWidgetItem(""))
        self.dkp_table.setItem(row, 5, QTableWidgetItem(""))

    # ------------------------------------------------------------------
    # Страница "Состав"
    # ------------------------------------------------------------------
    def create_sostav_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.sostav_table = QTableWidget()
        self.sostav_table.setColumnCount(8)
        self.sostav_table.setHorizontalHeaderLabels(
            ["Номер в составе", "Название", "Кол-во", "База", "Длина", "Высота", "Изменить", "Удалить"])
        self.sostav_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.sostav_table)

        add_btn = QPushButton("Добавить элемент состава")
        add_btn.clicked.connect(self.add_sostav_row)
        layout.addWidget(add_btn)

        info_layout = QVBoxLayout()
        self.length_label = QLabel("Длина 0 мм")
        info_layout.addWidget(self.length_label)

        coord_layout = QHBoxLayout()
        coord_layout.addWidget(QLabel("Начальная координата:"))
        self.start_coord_edit = QLineEdit()
        self.start_coord_edit.setPlaceholderText("Начальная координата")
        coord_layout.addWidget(self.start_coord_edit)
        info_layout.addLayout(coord_layout)

        # Комбобокс
        direction_layout = QHBoxLayout()
        direction_layout.addWidget(QLabel("Начальное направление:"))
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["Вперёд", "Назад", "Стоять"])
        direction_layout.addWidget(self.direction_combo)
        info_layout.addLayout(direction_layout)

        layout.addLayout(info_layout)

        self.stack.addWidget(page)

    def _create_wagon_selector(self, row):
        def handler():
            dlg = WagonsDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                btn = self.sostav_table.cellWidget(row, 0)
                if btn:
                    btn.setText(f"{dlg.selected_id} - {dlg.selected_name}")
        return handler

    def _create_sostav_delete_handler(self, row):
        def handler():
            self.sostav_table.removeRow(row)
        return handler

    def add_sostav_row(self):
        row = self.sostav_table.rowCount()
        self.sostav_table.insertRow(row)
        btn_number = QPushButton("Выбрать вагон")
        btn_number.clicked.connect(self._create_wagon_selector(row))
        self.sostav_table.setCellWidget(row, 0, btn_number)
        for col in range(1, 6):
            self.sostav_table.setItem(row, col, QTableWidgetItem(""))
        edit_btn = QPushButton("Изменить")
        edit_btn.clicked.connect(lambda: QMessageBox.information(self, "Заглушка", "Функция изменения"))
        self.sostav_table.setCellWidget(row, 6, edit_btn)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._create_sostav_delete_handler(row))
        self.sostav_table.setCellWidget(row, 7, del_btn)

    def update_sostav_length(self):
        length = self.get_selected_path_length()
        self.length_label.setText(f"Длина {length} мм")

    # ------------------------------------------------------------------
    # Страница "Сценарий"
    # ------------------------------------------------------------------
    def create_scenario_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.scenario_table = QTableWidget()
        self.scenario_table.setColumnCount(5)
        self.scenario_table.setHorizontalHeaderLabels(["№", "Название", "Кол-во шагов", "Статус", ""])
        self.scenario_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.scenario_table)

        add_btn = QPushButton("Добавить сценарий")
        add_btn.clicked.connect(self.add_scenario_row)
        layout.addWidget(add_btn)

        self.stack.addWidget(page)

    # Открывает диалог шагов и меняет текст кнопки на выбранный номер шага.
    def _open_scenario_dialog(self, button):
        dlg = ScenarioStepsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_step_number is not None:
            button.setText(dlg.selected_step_number)

    def _create_scenario_delete_handler(self, row):
        def handler():
            self.scenario_table.removeRow(row)
        return handler

    def add_scenario_row(self):
        row = self.scenario_table.rowCount()
        self.scenario_table.insertRow(row)
        btn = QPushButton(str(row + 1))
        btn.clicked.connect(lambda checked, button=btn: self._open_scenario_dialog(button))
        self.scenario_table.setCellWidget(row, 0, btn)
        self.scenario_table.setItem(row, 1, QTableWidgetItem(""))
        self.scenario_table.setItem(row, 2, QTableWidgetItem(""))
        chk = QCheckBox()
        self.scenario_table.setCellWidget(row, 3, chk)
        del_btn = QPushButton("Удалить")
        del_btn.clicked.connect(self._create_scenario_delete_handler(row))
        self.scenario_table.setCellWidget(row, 4, del_btn)

    # ------------------------------------------------------------------
    # Логика переключения режимов (кнопки ДКП/Состав/Сценарий -> Пути)
    # ------------------------------------------------------------------
    def reset_buttons_to_default(self):
        self.btn_dkp.setText("ДКП")
        self.btn_sostav.setText("Состав")
        self.btn_scenario.setText("Сценарий")

    def on_dkp_clicked(self):
        if self.btn_dkp.text() == "Пути":
            self.stack.setCurrentIndex(0)
            self.reset_buttons_to_default()
            self.current_mode = "paths"
        else:
            self.stack.setCurrentIndex(1)
            self.reset_buttons_to_default()
            self.btn_dkp.setText("Пути")
            self.current_mode = "dkp"

    def on_sostav_clicked(self):
        if self.btn_sostav.text() == "Пути":
            self.stack.setCurrentIndex(0)
            self.reset_buttons_to_default()
            self.current_mode = "paths"
        else:
            self.stack.setCurrentIndex(2)
            self.reset_buttons_to_default()
            self.btn_sostav.setText("Пути")
            self.current_mode = "sostav"
            self.update_sostav_length()

    def on_scenario_clicked(self):
        if self.btn_scenario.text() == "Пути":
            self.stack.setCurrentIndex(0)
            self.reset_buttons_to_default()
            self.current_mode = "paths"
        else:
            self.stack.setCurrentIndex(3)
            self.reset_buttons_to_default()
            self.btn_scenario.setText("Пути")
            self.current_mode = "scenario"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
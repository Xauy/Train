from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget
)
from paths_page import PathsPage
from dkp_page import DkpPage
from sostav_page import SostavPage
from scenario_page import ScenarioPage


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

        # Создаём экземпляры страниц
        self.paths_page = PathsPage()
        self.dkp_page = DkpPage()
        self.sostav_page = SostavPage()
        self.scenario_page = ScenarioPage()

        self.stack.addWidget(self.paths_page)   # 0
        self.stack.addWidget(self.dkp_page)     # 1
        self.stack.addWidget(self.sostav_page)  # 2
        self.stack.addWidget(self.scenario_page)# 3

        # Изначально показываем страницу путей
        self.stack.setCurrentWidget(self.paths_page)
        self.current_mode = "paths"

        # Назначаем обработчики кнопок
        self.btn_dkp.clicked.connect(self.on_dkp_clicked)
        self.btn_sostav.clicked.connect(self.on_sostav_clicked)
        self.btn_scenario.clicked.connect(self.on_scenario_clicked)

    def reset_buttons_to_default(self):
        self.btn_dkp.setText("ДКП")
        self.btn_sostav.setText("Состав")
        self.btn_scenario.setText("Сценарий")

    def on_dkp_clicked(self):
        if self.btn_dkp.text() == "Пути":
            self.stack.setCurrentWidget(self.paths_page)
            self.reset_buttons_to_default()
            self.current_mode = "paths"
        else:
            self.stack.setCurrentWidget(self.dkp_page)
            self.reset_buttons_to_default()
            self.btn_dkp.setText("Пути")
            self.current_mode = "dkp"

    def on_sostav_clicked(self):
        if self.btn_sostav.text() == "Пути":
            self.stack.setCurrentWidget(self.paths_page)
            self.reset_buttons_to_default()
            self.current_mode = "paths"
        else:
            self.stack.setCurrentWidget(self.sostav_page)
            self.reset_buttons_to_default()
            self.btn_sostav.setText("Пути")
            self.current_mode = "sostav"
            # При переключении на Состав сразу получаем длину из Путей
            length = self.paths_page.get_selected_path_length()
            self.sostav_page.set_length(length)

    def on_scenario_clicked(self):
        if self.btn_scenario.text() == "Пути":
            self.stack.setCurrentWidget(self.paths_page)
            self.reset_buttons_to_default()
            self.current_mode = "paths"
        else:
            self.stack.setCurrentWidget(self.scenario_page)
            self.reset_buttons_to_default()
            self.btn_scenario.setText("Пути")
            self.current_mode = "scenario"
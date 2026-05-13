"""
ui/main_window.py
Application main window.

Owns the shared ProjectData and is the only place that calls
ProjectStore.save() / ProjectStore.load().  Pages are orchestrated here;
they communicate upward via their to_dict / from_dict interface.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QFileDialog, QMessageBox,
)

from storage.models import ProjectData
from storage.project_store import ProjectStore
from ui.pages.paths_page import PathsPage
from ui.pages.dkp_page import DkpPage
from ui.pages.sostav_page import SostavPage
from ui.pages.scenario_page import ScenarioPage


class MainWindow(QMainWindow):
    """Top-level window that hosts all editor pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Железнодорожный симулятор")
        self.resize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ── Navigation buttons ────────────────────────────────────────
        nav = QHBoxLayout()
        self.btn_dkp      = QPushButton("ДКП")
        self.btn_sostav   = QPushButton("Состав")
        self.btn_scenario = QPushButton("Сценарий")
        self.btn_save     = QPushButton("Сохранить")
        self.btn_load     = QPushButton("Открыть")
        nav.addWidget(self.btn_dkp)
        nav.addWidget(self.btn_sostav)
        nav.addWidget(self.btn_scenario)
        nav.addStretch()
        nav.addWidget(self.btn_save)
        nav.addWidget(self.btn_load)
        root.addLayout(nav)

        # ── Page stack ────────────────────────────────────────────────
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.paths_page    = PathsPage()
        self.dkp_page      = DkpPage()
        self.sostav_page   = SostavPage()
        self.scenario_page = ScenarioPage()

        self.stack.addWidget(self.paths_page)    # 0
        self.stack.addWidget(self.dkp_page)      # 1
        self.stack.addWidget(self.sostav_page)   # 2
        self.stack.addWidget(self.scenario_page) # 3

        self.stack.setCurrentWidget(self.paths_page)
        self._current_mode = "paths"

        # ── Signal wiring ─────────────────────────────────────────────
        self.btn_dkp.clicked.connect(self._on_dkp_clicked)
        self.btn_sostav.clicked.connect(self._on_sostav_clicked)
        self.btn_scenario.clicked.connect(self._on_scenario_clicked)
        self.btn_save.clicked.connect(self._save_project)
        self.btn_load.clicked.connect(self._load_project)

    # ------------------------------------------------------------------ #
    #  Navigation                                                          #
    # ------------------------------------------------------------------ #

    def _reset_nav_labels(self) -> None:
        self.btn_dkp.setText("ДКП")
        self.btn_sostav.setText("Состав")
        self.btn_scenario.setText("Сценарий")

    def _on_dkp_clicked(self) -> None:
        if self._current_mode == "dkp":
            self.stack.setCurrentWidget(self.paths_page)
            self._reset_nav_labels()
            self._current_mode = "paths"
        else:
            self.stack.setCurrentWidget(self.dkp_page)
            self._reset_nav_labels()
            self.btn_dkp.setText("Пути")
            self._current_mode = "dkp"

    def _on_sostav_clicked(self) -> None:
        if self._current_mode == "sostav":
            self.stack.setCurrentWidget(self.paths_page)
            self._reset_nav_labels()
            self._current_mode = "paths"
        else:
            self.stack.setCurrentWidget(self.sostav_page)
            self._reset_nav_labels()
            self.btn_sostav.setText("Пути")
            self._current_mode = "sostav"
            length = self.paths_page.get_selected_path_length()
            self.sostav_page.set_length(length)

    def _on_scenario_clicked(self) -> None:
        if self._current_mode == "scenario":
            self.stack.setCurrentWidget(self.paths_page)
            self._reset_nav_labels()
            self._current_mode = "paths"
        else:
            self.stack.setCurrentWidget(self.scenario_page)
            self._reset_nav_labels()
            self.btn_scenario.setText("Пути")
            self._current_mode = "scenario"

    # ------------------------------------------------------------------ #
    #  Persistence                                                         #
    # ------------------------------------------------------------------ #

    def _collect_project(self) -> ProjectData:
        """Gather all page states into a single ProjectData."""
        from storage.models import PathRecord, ScenarioRecord

        paths = [PathRecord.from_dict(d) for d in self.paths_page.to_dict()]
        return ProjectData(
            paths=     paths,
            sensors=   self.dkp_page.to_dict(),
            wagons=    self.sostav_page.to_dict(),
            scenarios= [ScenarioRecord.from_dict(d) for d in self.scenario_page.to_dict()],
        )

    def _apply_project(self, data: ProjectData) -> None:
        """Push a loaded ProjectData into all pages."""
        self.paths_page.from_dict([p.to_dict() for p in data.paths])
        self.dkp_page.from_dict(data.sensors)
        self.sostav_page.from_dict(data.wagons)
        self.scenario_page.from_dict([s.to_dict() for s in data.scenarios])

    def _save_project(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            ProjectStore.save(self._collect_project(), path)
            QMessageBox.information(self, "Сохранено", f"Проект сохранён:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def _load_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть проект", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            data = ProjectStore.load(path)
            self._apply_project(data)
            QMessageBox.information(self, "Открыто", f"Проект загружен:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка загрузки", str(exc))

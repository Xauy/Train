"""
ui/main_window.py
Application main window.

Changes vs. original (plan section 4.4):
  • QMenuBar with «Файл» menu added:
      – Новый проект     (Ctrl+N)
      – Открыть…         (Ctrl+O)
      – Сохранить        (Ctrl+S)
      – Сохранить как…   (Ctrl+Shift+S)
  • self._current_file tracks the path to the currently open project.
  • Window title updated to "Хамелеон — <basename>" when a file is open.
  • ProjectIO used for save/load (replaces direct ProjectStore calls).
  • Existing toolbar buttons kept for quick access; File menu is primary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QStackedWidget, QFileDialog, QMessageBox,
    QMenuBar, QMenu,
)

from storage.models import ProjectData, PathRecord, ScenarioRecord
from storage.project_io import ProjectIO
from storage.project_store import ProjectStore
from ui.pages.paths_page import PathsPage
from ui.pages.dkp_page import DkpPage
from ui.pages.sostav_page import SostavPage
from ui.pages.scenario_page import ScenarioPage

_APP_TITLE = "Хамелеон"
_FILE_FILTER = "Проект Хамелеон (*.chameleon.json);;JSON (*.json)"


class MainWindow(QMainWindow):
    """Top-level window that hosts all editor pages."""

    def __init__(self) -> None:
        super().__init__()
        self._current_file: Optional[str] = None
        self._update_title()
        self.resize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ── Menu bar ──────────────────────────────────────────────────
        self._build_menu_bar()

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
        # Toolbar buttons delegate to the same actions as the menu.
        self.btn_save.clicked.connect(self._action_save.trigger)
        self.btn_load.clicked.connect(self._action_open.trigger)

    # ------------------------------------------------------------------ #
    #  Menu bar (plan 4.4)                                                 #
    # ------------------------------------------------------------------ #

    def _build_menu_bar(self) -> None:
        """Create the File menu with standard actions."""
        menu_bar: QMenuBar = self.menuBar()
        file_menu: QMenu = menu_bar.addMenu("Файл")

        # Новый проект
        self._action_new = QAction("Новый проект", self)
        self._action_new.setShortcut(QKeySequence("Ctrl+N"))
        self._action_new.triggered.connect(self._cmd_new)
        file_menu.addAction(self._action_new)

        file_menu.addSeparator()

        # Открыть…
        self._action_open = QAction("Открыть…", self)
        self._action_open.setShortcut(QKeySequence("Ctrl+O"))
        self._action_open.triggered.connect(self._cmd_open)
        file_menu.addAction(self._action_open)

        file_menu.addSeparator()

        # Сохранить
        self._action_save = QAction("Сохранить", self)
        self._action_save.setShortcut(QKeySequence("Ctrl+S"))
        self._action_save.triggered.connect(self._cmd_save)
        file_menu.addAction(self._action_save)

        # Сохранить как…
        self._action_save_as = QAction("Сохранить как…", self)
        self._action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._action_save_as.triggered.connect(self._cmd_save_as)
        file_menu.addAction(self._action_save_as)

    # ------------------------------------------------------------------ #
    #  File menu command handlers (plan 4.4)                               #
    # ------------------------------------------------------------------ #

    def _cmd_new(self) -> None:
        """Clear all pages and reset the current file reference."""
        reply = QMessageBox.question(
            self,
            "Новый проект",
            "Создать новый проект? Несохранённые изменения будут утеряны.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._clear_all_pages()
        self._current_file = None
        self._update_title()

    def _cmd_open(self) -> None:
        """Show an open-file dialog and load the selected project."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть проект", "", _FILE_FILTER
        )
        if not path:
            return
        self._load_from_path(path)

    def _cmd_save(self) -> None:
        """Save to the current file, or prompt for a path if none is set."""
        if self._current_file:
            self._save_to_path(self._current_file)
        else:
            self._cmd_save_as()

    def _cmd_save_as(self) -> None:
        """Prompt for a new file path and save."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект как…", "", _FILE_FILTER
        )
        if not path:
            return
        # Ensure the canonical extension is present.
        if not path.endswith(".chameleon.json") and not path.endswith(".json"):
            path += ".chameleon.json"
        self._save_to_path(path)

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
    #  Persistence helpers                                                 #
    # ------------------------------------------------------------------ #

    def _pages_dict(self) -> dict:
        """Return the pages dict expected by ProjectIO.save()."""
        return {
            "paths":    self.paths_page,
            "dkps":     self.dkp_page,
            "sostav":   self.sostav_page,
            "scenario": self.scenario_page,
        }

    def _save_to_path(self, path: str) -> None:
        """Perform the actual save; update state on success."""
        try:
            ProjectIO.save(path, self._pages_dict())
            self._current_file = path
            self._update_title()
            QMessageBox.information(
                self, "Сохранено", f"Проект сохранён:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def _load_from_path(self, path: str) -> None:
        """Load project from *path* and populate all pages."""
        try:
            data = ProjectIO.load(path)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Ошибка загрузки", str(exc))
            return

        # Optionally report structural warnings without blocking load.
        warnings = ProjectIO.validate_structure(data)
        if warnings:
            msg = "Проект загружен с предупреждениями:\n\n" + "\n".join(
                f"• {w}" for w in warnings
            )
            QMessageBox.warning(self, "Предупреждения", msg)

        try:
            self._apply_project_data(data)
        except Exception as exc:
            QMessageBox.critical(
                self, "Ошибка при применении данных", str(exc)
            )
            return

        self._current_file = path
        self._update_title()
        QMessageBox.information(
            self, "Открыто", f"Проект загружен:\n{path}"
        )

    def _apply_project_data(self, data: dict) -> None:
        """Push loaded data dict into all editor pages."""
        self.paths_page.from_dict(data.get("paths", []))
        self.dkp_page.from_dict(data.get("dkps", []))
        self.sostav_page.from_dict(data.get("wagons", []))
        self.scenario_page.from_dict(data.get("scenarios", []))

    def _clear_all_pages(self) -> None:
        """Reset every page to its blank state."""
        self.paths_page.from_dict([])
        self.dkp_page.from_dict([])
        self.sostav_page.from_dict([])
        self.scenario_page.from_dict([])

    # ------------------------------------------------------------------ #
    #  Window title                                                        #
    # ------------------------------------------------------------------ #

    def _update_title(self) -> None:
        """Set window title to '<App> — <filename>' or just '<App>'."""
        if self._current_file:
            basename = Path(self._current_file).name
            self.setWindowTitle(f"{_APP_TITLE} — {basename}")
        else:
            self.setWindowTitle(_APP_TITLE)

    # ------------------------------------------------------------------ #
    #  Legacy compatibility — keep _collect_project / _apply_project       #
    #  so any external callers of the old API don't break.                 #
    # ------------------------------------------------------------------ #

    def _collect_project(self) -> ProjectData:
        """Gather all page states into a single ProjectData (legacy API)."""
        paths = [PathRecord.from_dict(d) for d in self.paths_page.to_dict()]
        return ProjectData(
            paths=    paths,
            sensors=  self.dkp_page.to_dict(),
            wagons=   self.sostav_page.to_dict(),
            scenarios=[ScenarioRecord.from_dict(d)
                       for d in self.scenario_page.to_dict()],
        )

    def _apply_project(self, data: ProjectData) -> None:
        """Push a loaded ProjectData into all pages (legacy API)."""
        self.paths_page.from_dict([p.to_dict() for p in data.paths])
        self.dkp_page.from_dict(data.sensors)
        self.sostav_page.from_dict(data.wagons)
        self.scenario_page.from_dict(
            [s.to_dict() for s in data.scenarios]
        )

"""
ui/main_window.py
Application main window.

Changes vs. previous version:
  • [4.4] QMenuBar with «Файл» menu:
      – Новый проект     (Ctrl+N)
      – Открыть…         (Ctrl+O)
      – Сохранить        (Ctrl+S)
      – Сохранить как…   (Ctrl+Shift+S)
  • [3.6] «Симуляция» button on the nav bar:
      – Collects all page data into a SimConfig.
      – Constructs SimulationEngine.
      – Opens SceneWindow as an independent top-level window.
  • self._current_file tracks the path to the currently open project.
  • Window title updated to "Хамелеон — <basename>" when a file is open.
  • ProjectIO used for save/load (replaces direct ProjectStore calls).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

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

# Physics / simulation imports  (lazy to avoid heavy import on startup)
from physics.models import (
    SimConfig, TrainConfig, DKPConfig, WagonDef, AxleDef,
    WagonSlot, ScenarioStep as PhysicsScenarioStep,
)
from physics.wagon_defaults import resolve_model_path
from physics.simulation_engine import SimulationEngine
from ui.scene_window import SceneWindow

_APP_TITLE   = "Хамелеон"
_FILE_FILTER = "Проект Хамелеон (*.chameleon.json);;JSON (*.json)"


class MainWindow(QMainWindow):
    """Top-level window that hosts all editor pages."""

    def __init__(self) -> None:
        super().__init__()
        self._current_file: Optional[str] = None
        self._scene_window: Optional[SceneWindow] = None   # keep reference so GC won't kill it
        self._update_title()
        self.resize(1000, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ── Menu bar ──────────────────────────────────────────────────
        self._build_menu_bar()

        # ── Navigation buttons ────────────────────────────────────────
        nav = QHBoxLayout()
        self.btn_dkp        = QPushButton("ДКП")
        self.btn_sostav     = QPushButton("Состав")
        self.btn_scenario   = QPushButton("Сценарий")
        self.btn_simulation = QPushButton("▶  Симуляция")
        self.btn_save       = QPushButton("Сохранить")
        self.btn_load       = QPushButton("Открыть")
        nav.addWidget(self.btn_dkp)
        nav.addWidget(self.btn_sostav)
        nav.addWidget(self.btn_scenario)
        nav.addWidget(self.btn_simulation)
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
        self.btn_simulation.clicked.connect(self._on_simulation_clicked)
        self.btn_save.clicked.connect(self._action_save.trigger)
        self.btn_load.clicked.connect(self._action_open.trigger)

    # ------------------------------------------------------------------ #
    #  Menu bar (plan 4.4)                                                 #
    # ------------------------------------------------------------------ #

    def _build_menu_bar(self) -> None:
        menu_bar: QMenuBar = self.menuBar()
        file_menu: QMenu   = menu_bar.addMenu("Файл")

        self._action_new = QAction("Новый проект", self)
        self._action_new.setShortcut(QKeySequence("Ctrl+N"))
        self._action_new.triggered.connect(self._cmd_new)
        file_menu.addAction(self._action_new)

        file_menu.addSeparator()

        self._action_open = QAction("Открыть…", self)
        self._action_open.setShortcut(QKeySequence("Ctrl+O"))
        self._action_open.triggered.connect(self._cmd_open)
        file_menu.addAction(self._action_open)

        file_menu.addSeparator()

        self._action_save = QAction("Сохранить", self)
        self._action_save.setShortcut(QKeySequence("Ctrl+S"))
        self._action_save.triggered.connect(self._cmd_save)
        file_menu.addAction(self._action_save)

        self._action_save_as = QAction("Сохранить как…", self)
        self._action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self._action_save_as.triggered.connect(self._cmd_save_as)
        file_menu.addAction(self._action_save_as)

    # ------------------------------------------------------------------ #
    #  File menu command handlers (plan 4.4)                               #
    # ------------------------------------------------------------------ #

    def _cmd_new(self) -> None:
        reply = QMessageBox.question(
            self, "Новый проект",
            "Создать новый проект? Несохранённые изменения будут утеряны.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._clear_all_pages()
        self._current_file = None
        self._update_title()

    def _cmd_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Открыть проект", "", _FILE_FILTER
        )
        if not path:
            return
        self._load_from_path(path)

    def _cmd_save(self) -> None:
        if self._current_file:
            self._save_to_path(self._current_file)
        else:
            self._cmd_save_as()

    def _cmd_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект как…", "", _FILE_FILTER
        )
        if not path:
            return
        if not path.endswith(".chameleon.json") and not path.endswith(".json"):
            path += ".chameleon.json"
        self._save_to_path(path)

    # ------------------------------------------------------------------ #
    #  Simulation (plan 3.6)                                              #
    # ------------------------------------------------------------------ #

    def _on_simulation_clicked(self) -> None:
        """Build a SimConfig from all pages, create the engine and open SceneWindow."""
        try:
            sim_config = self._build_sim_config()
            path_data  = self._collect_path_data()
        except ValueError as exc:
            QMessageBox.critical(self, "Ошибка конфигурации", str(exc))
            return

        # Validate via engine before opening the window.
        engine = SimulationEngine(sim_config)
        errors = engine.validate()
        if errors:
            QMessageBox.critical(
                self,
                "Ошибка конфигурации симуляции",
                "Запуск невозможен:\n\n" + "\n".join(f"• {e}" for e in errors),
            )
            return

        # Keep strong reference; without it the window is garbage-collected.
        self._scene_window = SceneWindow(engine, sim_config, path_data, parent=self)
        self._scene_window.show()

    def _build_sim_config(self) -> SimConfig:
        """Assemble a SimConfig from the current UI state.

        Reads data from all four editor pages and converts them into the
        physics.models dataclasses expected by SimulationEngine.

        Raises
        ------
        ValueError
            If required data is missing or inconsistent (e.g. empty wagon
            sequence, empty scenario, missing track_id).
        """
        # ── Wagon library from SostavPage ─────────────────────────────
        wagon_rows: List[dict] = self.sostav_page.to_dict()
        if not wagon_rows:
            raise ValueError(
                "Состав не заполнен.\n"
                "Добавьте хотя бы один вагон на странице «Состав»."
            )

        wagon_library: Dict[str, WagonDef] = {}
        wagon_sequence: List[WagonSlot]    = []

        for row in wagon_rows:
            wagon_id = str(row.get("wagon_label", row.get("name", ""))).strip()
            if not wagon_id:
                continue

            # Build a minimal WagonDef from the UI fields.
            # The UI stores display values; we convert to floats with safe fallback.
            length_mm = _safe_float(row.get("length", 20_000.0), 20_000.0)
            height_mm = _safe_float(row.get("height", 4_000.0),   4_000.0)
            base_mm   = _safe_float(row.get("base",   18_000.0), 18_000.0)
            count     = max(1, int(_safe_float(row.get("count", 1), 1)))

            # Derive two bogie axles from the base distance if no explicit
            # axle data is available (the UI does not currently expose axles).
            overhang = (length_mm - base_mm) / 2.0
            axles = [
                AxleDef(offset_mm=max(0.0, overhang)),
                AxleDef(offset_mm=max(0.0, overhang + base_mm)),
            ]

            if wagon_id not in wagon_library:
                # Resolve the 3-D model: explicit path wins; otherwise fall
                # back to the type's default in <project>/models/, if present.
                resolved_model = resolve_model_path(
                    explicit_path=str(row.get("model_path", "")),
                    wagon_type=   str(row.get("type", "")),
                )
                wagon_library[wagon_id] = WagonDef(
                    wagon_id=   wagon_id,
                    name=       str(row.get("name", wagon_id)),
                    length_mm=  length_mm,
                    height_mm=  height_mm,
                    axles=      axles,
                    model_path= resolved_model,
                )

            wagon_sequence.append(WagonSlot(wagon_id=wagon_id, count=count))

        if not wagon_sequence:
            raise ValueError(
                "Не удалось построить состав: ни один вагон не имеет идентификатора."
            )

        # ── Path lookup: take the first (or selected) path ────────────
        path_records = self.paths_page.to_dict()
        if not path_records:
            raise ValueError(
                "Не задано ни одного пути.\n"
                "Добавьте пути на странице «Пути»."
            )

        # Use the path that is checked (selected) in the paths table, or the first.
        first_path = path_records[0]
        for pr in path_records:
            pass   # could check selection checkbox here; use first for now

        track_id = str(first_path.get("track_id", "")).strip()
        if not track_id:
            raise ValueError(
                "Первый путь не имеет track_id.\n"
                "Задайте идентификатор пути на странице «Пути»."
            )

        # ── TrainConfig ───────────────────────────────────────────────
        start_coord_text = self.sostav_page.start_coord_edit.text().strip()
        s0_mm = _safe_float(start_coord_text, 0.0)
        direction = self.sostav_page.direction_combo.currentText()

        train_config = TrainConfig(
            train_id=       "TRAIN_1",
            track_id=       track_id,
            s0_mm=          s0_mm,
            direction=      direction,
            wagon_sequence= wagon_sequence,
        )

        # ── DKP sensors ───────────────────────────────────────────────
        dkp_records: List[dict] = self.dkp_page.to_dict()
        dkp_configs: List[DKPConfig] = []
        for d in dkp_records:
            try:
                dkp_configs.append(DKPConfig(
                    sensor_id=        str(d.get("sensor_id", "")).strip(),
                    track_id=         str(d.get("track_id", track_id)).strip() or track_id,
                    s_mm=             float(d.get("s_mm", 0.0)),
                    zone_mm=          max(1.0, float(d.get("zone_mm", 100.0))),
                    sensor_type=      str(d.get("sensor_type", "Fox")),
                    enabled=          bool(d.get("enabled", True)),
                    direction_filter= str(d.get("direction_filter", "Any")),
                ))
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Ошибка в данных ДКП «{d.get('sensor_id', '?')}»: {exc}"
                ) from exc

        # ── Scenario steps ────────────────────────────────────────────
        scenario_rows: List[dict] = self.scenario_page.to_dict()
        if not scenario_rows:
            raise ValueError(
                "Сценарий не содержит ни одного сценария.\n"
                "Добавьте сценарий на странице «Сценарий»."
            )

        # Use the first scenario's steps.
        first_scenario = scenario_rows[0]
        raw_steps: List[dict] = first_scenario.get("steps", [])
        if not raw_steps:
            raise ValueError(
                f"Первый сценарий «{first_scenario.get('name', '—')}» "
                f"не содержит шагов.\n"
                f"Добавьте шаги на странице «Сценарий»."
            )

        phys_steps: List[PhysicsScenarioStep] = []
        for i, s in enumerate(raw_steps):
            try:
                phys_steps.append(PhysicsScenarioStep(
                    duration_ms=     max(0, int(s.get("duration_ms", 0))),
                    v0_mms=          float(s.get("v0_mms", 0.0)),
                    accel_mms2=      float(s.get("accel_mms2", 0.0)),
                    v_threshold_mms= max(0.0, float(s.get("v_threshold_mms", 0.0))),
                    behavior=        str(s.get("behavior", "LeftToRight")),
                ))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Ошибка в шаге {i + 1} сценария: {exc}") from exc

        return SimConfig(
            train=         train_config,
            dkps=          dkp_configs,
            steps=         phys_steps,
            wagon_library= wagon_library,
        )

    def _collect_path_data(self) -> List[dict]:
        """Return path dicts suitable for SceneWindow's renderer.

        These are the raw to_dict() results from PathsPage — SceneWindow
        extracts x1/y1/z1/x2/y2/z2 from them directly.
        """
        return self.paths_page.to_dict()

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
        return {
            "paths":    self.paths_page,
            "dkps":     self.dkp_page,
            "sostav":   self.sostav_page,
            "scenario": self.scenario_page,
        }

    def _save_to_path(self, path: str) -> None:
        try:
            ProjectIO.save(path, self._pages_dict())
            self._current_file = path
            self._update_title()
            QMessageBox.information(self, "Сохранено", f"Проект сохранён:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка сохранения", str(exc))

    def _load_from_path(self, path: str) -> None:
        try:
            data = ProjectIO.load(path)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Ошибка загрузки", str(exc))
            return

        warnings = ProjectIO.validate_structure(data)
        if warnings:
            msg = "Проект загружен с предупреждениями:\n\n" + "\n".join(
                f"• {w}" for w in warnings
            )
            QMessageBox.warning(self, "Предупреждения", msg)

        try:
            self._apply_project_data(data)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка при применении данных", str(exc))
            return

        self._current_file = path
        self._update_title()
        QMessageBox.information(self, "Открыто", f"Проект загружен:\n{path}")

    def _apply_project_data(self, data: dict) -> None:
        self.paths_page.from_dict(data.get("paths", []))
        self.dkp_page.from_dict(data.get("dkps", []))
        self.sostav_page.from_dict(data.get("wagons", []))
        self.scenario_page.from_dict(data.get("scenarios", []))

    def _clear_all_pages(self) -> None:
        self.paths_page.from_dict([])
        self.dkp_page.from_dict([])
        self.sostav_page.from_dict([])
        self.scenario_page.from_dict([])

    # ------------------------------------------------------------------ #
    #  Window title                                                        #
    # ------------------------------------------------------------------ #

    def _update_title(self) -> None:
        if self._current_file:
            basename = Path(self._current_file).name
            self.setWindowTitle(f"{_APP_TITLE} — {basename}")
        else:
            self.setWindowTitle(_APP_TITLE)

    # ------------------------------------------------------------------ #
    #  Legacy compatibility                                                #
    # ------------------------------------------------------------------ #

    def _collect_project(self) -> ProjectData:
        paths = [PathRecord.from_dict(d) for d in self.paths_page.to_dict()]
        return ProjectData(
            paths=    paths,
            sensors=  self.dkp_page.to_dict(),
            wagons=   self.sostav_page.to_dict(),
            scenarios=[ScenarioRecord.from_dict(d)
                       for d in self.scenario_page.to_dict()],
        )

    def _apply_project(self, data: ProjectData) -> None:
        self.paths_page.from_dict([p.to_dict() for p in data.paths])
        self.dkp_page.from_dict(data.sensors)
        self.sostav_page.from_dict(data.wagons)
        self.scenario_page.from_dict(
            [s.to_dict() for s in data.scenarios]
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(value, default: float) -> float:
    """Parse *value* as float; return *default* on any error."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

"""
storage/project_io.py
High-level project persistence façade (plan section 4.3).

ProjectIO is a thin orchestration layer on top of ProjectStore:
  • save()               — gathers to_dict() from all pages, writes JSON.
  • load()               — reads JSON, calls from_dict() on all pages.
  • validate_structure() — cross-checks referential integrity of loaded data.

No Qt widgets are imported here so this module is unit-testable standalone.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import List, Optional

from storage.models import (
    ProjectData, PathRecord, DKPRecord, WagonRecord,
    TrainRecord, ScenarioRecord, ScenarioStep,
    AxleDef, WagonSequenceEntry,
)

# Current on-disk schema version produced by this module.
CURRENT_VERSION = "0.2"
SUPPORTED_VERSIONS: frozenset[str] = frozenset({"0.2"})

ENCODING = "utf-8"
INDENT = 2


class ProjectIO:
    """Static methods for saving, loading, and validating project files.

    Usage::

        # Save
        pages = {
            'paths':    paths_page,
            'dkps':     dkp_page,
            'sostav':   sostav_page,
            'scenario': scenario_page,
        }
        ProjectIO.save("my.chameleon.json", pages)

        # Load
        data = ProjectIO.load("my.chameleon.json")
        paths_page.from_dict(data["paths"])
        dkp_page.from_dict(data["dkps"])
        sostav_page.from_dict(data["wagons"])
        scenario_page.from_dict(data["scenarios"])
    """

    # ------------------------------------------------------------------ #
    #  Save                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def save(path: str | Path, pages: dict) -> None:
        """Collect to_dict() from all editor pages and write to *path*.

        *pages* must contain these keys (values are page widget instances):
          • ``'paths'``    — PathsPage
          • ``'dkps'``     — DkpPage
          • ``'sostav'``   — SostavPage
          • ``'scenario'`` — ScenarioPage

        The method calls each page's ``to_dict()`` and assembles a complete
        project document.  The file is written as UTF-8 JSON with 2-space
        indent.

        Raises
        ------
        KeyError
            If a required page key is absent from *pages*.
        OSError
            If the file cannot be written (permissions, disk full, etc.).
        """
        paths_page    = pages["paths"]
        dkp_page      = pages["dkps"]
        sostav_page   = pages["sostav"]
        scenario_page = pages["scenario"]

        payload: dict = {
            "version":  CURRENT_VERSION,
            "paths":    paths_page.to_dict(),
            "dkps":     dkp_page.to_dict(),
            "wagons":   sostav_page.to_dict(),
            "train":    ProjectIO._default_train_record(),
            "scenarios": scenario_page.to_dict(),
        }

        path = Path(path)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=INDENT),
            encoding=ENCODING,
        )

    # ------------------------------------------------------------------ #
    #  Load                                                                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def load(path: str | Path) -> dict:
        """Read *path* and return a normalised project dict.

        The returned dict always contains the keys:
          ``version``, ``paths``, ``dkps``, ``wagons``, ``train``,
          ``scenarios``

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        ValueError
            If the JSON is malformed, the version is unsupported, or a
            required top-level section is missing.
        """
        path = Path(path)
        try:
            raw_text = path.read_text(encoding=ENCODING)
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл проекта не найден: {path}")

        try:
            data: dict = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Некорректный JSON в файле проекта: {exc}") from exc

        version = data.get("version", "<отсутствует>")
        if version not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"Версия проекта '{version}' не поддерживается. "
                f"Поддерживаемые версии: {', '.join(sorted(SUPPORTED_VERSIONS))}."
            )

        required = {"paths", "dkps", "wagons"}
        missing = required - data.keys()
        if missing:
            raise ValueError(
                f"В файле проекта отсутствуют обязательные разделы: "
                f"{', '.join(sorted(missing))}."
            )

        # Migrate legacy formats if necessary (currently a no-op for 0.2).
        data = ProjectIO._migrate(data, from_version=version)

        # Normalise optional sections so callers never see KeyError.
        data.setdefault("train", ProjectIO._default_train_record())
        data.setdefault("scenarios", [])

        return data

    # ------------------------------------------------------------------ #
    #  Structural validation                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def validate_structure(data: dict) -> List[str]:
        """Cross-check referential integrity of *data* after loading.

        Checks
        ------
        1. Every ``track_id`` referenced by a DKP exists in ``paths``.
        2. ``s_mm`` of every DKP is within ``[0, length_mm]`` of its path.
        3. Every ``wagon_id`` in ``train.wagon_sequence`` exists in
           ``wagons``.

        Returns
        -------
        list[str]
            Human-readable error descriptions in Russian.  Empty list
            means the data is internally consistent.
        """
        errors: List[str] = []

        # Build a path_id → length_mm lookup.
        path_lengths: dict[str, float] = {}
        for raw_path in data.get("paths", []):
            tid = str(raw_path.get("track_id", "")).strip()
            try:
                rec = PathRecord.from_dict(raw_path)
                path_lengths[tid] = rec.length_mm
            except Exception:
                pass  # malformed path records are caught by validators.py

        # Check DKP records.
        for i, raw_dkp in enumerate(data.get("dkps", []), start=1):
            sid     = raw_dkp.get("sensor_id", f"ДКП #{i}")
            tid     = str(raw_dkp.get("track_id", "")).strip()
            raw_s   = raw_dkp.get("s_mm", 0)

            if tid and tid not in path_lengths:
                errors.append(
                    f"[{sid}] track_id '{tid}' не найден в списке путей."
                )
                continue

            try:
                s_mm = float(raw_s)
            except (TypeError, ValueError):
                errors.append(f"[{sid}] s_mm не является числом: '{raw_s}'.")
                continue

            if tid and s_mm > path_lengths[tid]:
                errors.append(
                    f"[{sid}] s_mm={s_mm} превышает длину пути "
                    f"'{tid}' ({path_lengths[tid]:.2f} мм)."
                )
            if s_mm < 0:
                errors.append(f"[{sid}] s_mm не может быть отрицательным.")

        # Check wagon_sequence references.
        wagon_ids = {
            str(w.get("wagon_id", ""))
            for w in data.get("wagons", [])
        }
        train = data.get("train", {})
        for entry in train.get("wagon_sequence", []):
            wid = str(entry.get("wagon_id", ""))
            if wid and wid not in wagon_ids:
                errors.append(
                    f"Состав ссылается на несуществующий вагон: '{wid}'."
                )

        return errors

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _migrate(data: dict, from_version: str) -> dict:
        """Apply any format migrations needed for older project files.

        Currently only v0.2 exists, so this is a no-op.  Add branches
        here when a v0.3 schema is introduced.
        """
        # from_version == "0.2" → nothing to do
        return data

    @staticmethod
    def _default_train_record() -> dict:
        """Return a minimal default TrainRecord dict."""
        return {
            "train_id":       "TRAIN_1",
            "track_id":       "",
            "s0_mm":          0.0,
            "direction":      "LeftToRight",
            "wagon_sequence": [],
        }

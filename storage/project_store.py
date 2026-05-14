"""
storage/project_store.py
Handles reading and writing project files (*.chameleon.json, v0.2).

All Qt-specific code and all physics logic stay out of this module so it
can be unit-tested without a display.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import ProjectData


class ProjectStore:
    """Responsible for persisting a ProjectData to/from a JSON file.

    Usage::

        data = ProjectStore.load("my_project.chameleon.json")
        ...
        ProjectStore.save(data, "my_project.chameleon.json")
    """

    ENCODING:           str       = "utf-8"
    INDENT:             int       = 2
    EXTENSION:          str       = ".chameleon.json"
    SUPPORTED_VERSIONS: frozenset = frozenset({"0.2"})

    # ------------------------------------------------------------------ save

    @staticmethod
    def save(data: ProjectData, path: str | Path) -> None:
        """Serialise *data* and write it to *path* (creates or overwrites).

        The ``version`` field is always stamped to the current format version
        regardless of the value stored in *data*.
        """
        payload = data.to_dict()
        payload["version"] = "0.2"          # guarantee correct version on disk
        with open(path, "w", encoding=ProjectStore.ENCODING) as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=ProjectStore.INDENT)

    # ------------------------------------------------------------------ load

    @staticmethod
    def load(path: str | Path) -> ProjectData:
        """Read *path* and return a fully populated ProjectData.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist.
        ValueError
            If the JSON is malformed, the version is unsupported, or a
            required top-level key is missing.
        """
        with open(path, "r", encoding=ProjectStore.ENCODING) as fh:
            try:
                raw: dict = json.load(fh)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in project file: {exc}") from exc

        # Version check
        version = raw.get("version", "<missing>")
        if version not in ProjectStore.SUPPORTED_VERSIONS:
            raise ValueError(
                f"Unsupported project version '{version}'. "
                f"Supported: {', '.join(sorted(ProjectStore.SUPPORTED_VERSIONS))}."
            )

        # Required top-level keys
        required = {"paths", "dkps", "wagons", "train", "scenario"}
        missing = required - raw.keys()
        if missing:
            raise ValueError(
                f"Project file is missing required sections: "
                f"{', '.join(sorted(missing))}."
            )

        raw = ProjectStore._migrate(raw, from_version=version)
        return ProjectData.from_dict(raw)

    # ------------------------------------------------------------------ private

    @staticmethod
    def _migrate(data: dict, from_version: str) -> dict:
        """Apply any format migrations needed when loading an older file.

        Currently only version 0.2 exists, so this is a no-op.
        Add transformation logic here when a new version is introduced.
        """
        # from_version == "0.2" → nothing to do
        return data

"""
storage/project_store.py
Handles reading and writing the project JSON file.

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

        data = ProjectStore.load("my_project.json")
        ...
        ProjectStore.save(data, "my_project.json")
    """

    ENCODING = "utf-8"
    INDENT   = 2

    @staticmethod
    def save(data: ProjectData, path: str | Path) -> None:
        """Serialise *data* and write it to *path* (creates or overwrites)."""
        with open(path, "w", encoding=ProjectStore.ENCODING) as fh:
            json.dump(data.to_dict(), fh, ensure_ascii=False, indent=ProjectStore.INDENT)

    @staticmethod
    def load(path: str | Path) -> ProjectData:
        """Read *path* and return a fully populated ProjectData."""
        with open(path, "r", encoding=ProjectStore.ENCODING) as fh:
            raw = json.load(fh)
        return ProjectData.from_dict(raw)

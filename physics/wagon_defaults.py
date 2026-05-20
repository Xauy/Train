"""
physics/wagon_defaults.py
Default 3-D model resolver for each wagon type.

Each canonical wagon type (as shown in the dropdown of WagonsDialog) is
mapped to a fixed filename inside the project's ``models/`` directory.
If the user did not pick an explicit ``.obj`` path for a wagon, the
scene window will use the default model for the wagon's type — provided
the corresponding file exists on disk.

How to add a default model
──────────────────────────
1. Author or download an ``.obj`` file for the wagon body.  Orientation
   does not matter — SceneWindow auto-detects the longest axis and lays
   the model along the track.  Triangulated meshes work best; quads are
   handled if ``trimesh`` is installed.
2. Place it in the project's ``models/`` directory:

        chameleon/
        ├── main.py
        ├── models/                 ← add files here
        │   ├── cisterna.obj
        │   ├── kryty.obj
        │   └── …
        └── …

3. Name it exactly as listed in ``DEFAULT_MODEL_FILES`` below.  The map
   is keyed on the Russian type name shown in the UI dropdown.

| Wagon type (UI) | Required filename     |
| --------------- | --------------------- |
| Цистерна        | ``cisterna.obj``      |
| Крытый          | ``kryty.obj``         |
| Полувагон       | ``poluvagon.obj``     |
| Платформа       | ``platforma.obj``     |
| Думпкар         | ``dumpkar.obj``       |
| Хоппер          | ``hopper.obj``        |
| Транспортер     | ``transporter.obj``   |

If a wagon has no explicit model and no default file is present for its
type, the scene renders the original Box fallback — nothing breaks.

This module has no Qt dependency and can be unit-tested standalone.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Folder name (relative to the project root) where default models live.
MODELS_DIRNAME: str = "models"

# Type → filename mapping.  Keys are the exact UI labels from the wagon-type
# dropdown in WagonsDialog; values are the expected file names.
DEFAULT_MODEL_FILES: Dict[str, str] = {
    "Цистерна":    "cisterna.obj",
    "Крытый":      "kryty.obj",
    "Полувагон":   "poluvagon.obj",
    "Платформа":   "platforma.obj",
    "Думпкар":     "dumpkar.obj",
    "Хоппер":      "hopper.obj",
    "Транспортер": "transporter.obj",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _project_root() -> Path:
    """Return the project root directory (the folder that contains main.py).

    This module lives at ``<root>/physics/wagon_defaults.py`` so the root
    is two ``parent`` hops up.
    """
    return Path(__file__).resolve().parent.parent


def _models_dir() -> Path:
    """Return the absolute path to the ``models/`` directory."""
    return _project_root() / MODELS_DIRNAME


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def default_model_path(wagon_type: str) -> Optional[str]:
    """Return the absolute path to the default model for *wagon_type*.

    Returns
    -------
    str
        Absolute filesystem path to the ``.obj`` file when the type is
        recognised AND the file actually exists on disk.
    None
        If the type is unknown, has no default mapping, or the expected
        file is not present.  Callers should treat ``None`` as "render
        the Box fallback".

    The check is case-sensitive on the *filename* but does a normalised
    lookup on the wagon type — surrounding whitespace is trimmed before
    matching, so values coming from a UI text field always work.
    """
    if not wagon_type:
        return None

    key = wagon_type.strip()
    filename = DEFAULT_MODEL_FILES.get(key)
    if filename is None:
        return None

    path = _models_dir() / filename
    if not path.is_file():
        return None

    return str(path)


def resolve_model_path(explicit_path: str, wagon_type: str) -> str:
    """Choose the model path to use for a wagon.

    Priority:
      1. If *explicit_path* is non-empty and points to an existing file,
         it wins.  This is the path the user picked manually in
         WagonsDialog via «Выбрать .obj».
      2. Otherwise, fall back to the default for *wagon_type*, if a
         default file is bundled in ``models/``.
      3. Otherwise return an empty string — SceneWindow will render the
         Box fallback.

    Notes
    -----
    The explicit path is tested with ``os.path.isfile`` to avoid
    propagating a path that the user typed but never created.  An
    explicit path that doesn't exist falls through to the default —
    this is friendlier than silently using a broken value.
    """
    if explicit_path:
        explicit_path = explicit_path.strip()
        if explicit_path and os.path.isfile(explicit_path):
            return explicit_path

    default = default_model_path(wagon_type)
    return default or ""


def supported_wagon_types() -> list[str]:
    """Return the canonical list of wagon types that have a default mapping."""
    return list(DEFAULT_MODEL_FILES.keys())


def expected_filename(wagon_type: str) -> Optional[str]:
    """Return the *required filename* for a wagon type (without checking disk).

    Useful for UI hints ("place the file at models/cisterna.obj") and
    for tooling that wants to list what files the application looks for.
    """
    if not wagon_type:
        return None
    return DEFAULT_MODEL_FILES.get(wagon_type.strip())

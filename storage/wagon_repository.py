"""
ui/dialogs/wagon_repository.py
Simple JSON-based persistence for the wagon library.

Provides:
    load_wagons() -> list[dict]
    save_wagons(wagons: list[dict]) -> None
"""

import json
import os
from typing import Any

# Файл будет создаваться в текущей рабочей директории.
LIBRARY_FILE = "wagon_library.json"


def load_wagons() -> list[dict[str, Any]]:
    """Return the list of wagons stored in the JSON file."""
    if not os.path.exists(LIBRARY_FILE):
        return []
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_wagons(wagons: list[dict[str, Any]]) -> None:
    """Save the list of wagons to the JSON file."""
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(wagons, f, ensure_ascii=False, indent=2)
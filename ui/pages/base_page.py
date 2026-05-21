"""
ui/pages/base_page.py
Abstract base class that every editor page must implement.

Enforcing to_dict / from_dict at the base class level guarantees that
ProjectStore can always call these methods without type-checking each page.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Union

from PyQt6.QtWidgets import QWidget


class BasePage(QWidget):
    """Abstract editor page.

    Subclasses must implement:
      • to_dict()   — return a JSON-compatible list or dict representing the
                       current state of the page.
      • from_dict() — restore the page from the same structure.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

    @abstractmethod
    def to_dict(self) -> Union[list, dict]:
        """Serialise the page's current state to a JSON-compatible structure."""

    @abstractmethod
    def from_dict(self, data: Union[list, dict]) -> None:
        """Restore the page's state from a JSON-compatible structure."""

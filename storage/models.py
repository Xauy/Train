"""
storage/models.py
Project-level data containers.

These are the plain-Python objects that flow between the UI pages and the
JSON store.  Physics models (WagonDef, DKPConfig, …) live in physics.models;
this module covers the data that the editor UI introduces:
  – PathRecord  : one track/path entry
  – ScenarioRecord: one named scenario with its steps
  – ProjectData : the full serialisable project document
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PathRecord:
    """One track / path as entered on the Пути (Paths) page."""
    track_id:  str   = ""
    name:      str   = ""
    x:         float = 0.0
    z:         float = 0.0
    length_mm: float = 0.0

    def to_dict(self) -> dict:
        return {
            "track_id":  self.track_id,
            "name":      self.name,
            "x":         self.x,
            "z":         self.z,
            "length_mm": self.length_mm,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PathRecord":
        return cls(
            track_id=  str(d.get("track_id", "")),
            name=      str(d.get("name", "")),
            x=         float(d.get("x", 0.0)),
            z=         float(d.get("z", 0.0)),
            length_mm= float(d.get("length_mm", 0.0)),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScenarioRecord:
    """One scenario entry as stored in the Сценарий (Scenario) page.

    *steps* is a list of raw dicts that map 1-to-1 with
    physics.models.ScenarioStep.to_dict() / from_dict().
    """
    name:   str        = ""
    active: bool       = False
    steps:  List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name":   self.name,
            "active": self.active,
            "steps":  list(self.steps),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScenarioRecord":
        return cls(
            name=   str(d.get("name", "")),
            active= bool(d.get("active", False)),
            steps=  list(d.get("steps", [])),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ProjectData:
    """Full, serialisable project document.

    *sensors* and *wagons* are stored as raw dicts so they can be round-
    tripped without importing physics models here.  Call
    physics.models.DKPConfig.from_dict() / WagonDef.from_dict() when you
    need typed objects.
    """
    paths:     List[PathRecord]     = field(default_factory=list)
    sensors:   List[dict]           = field(default_factory=list)
    wagons:    List[dict]           = field(default_factory=list)
    scenarios: List[ScenarioRecord] = field(default_factory=list)
    train:     dict                 = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "paths":     [p.to_dict()  for p in self.paths],
            "sensors":   self.sensors,
            "wagons":    self.wagons,
            "scenarios": [s.to_dict()  for s in self.scenarios],
            "train":     self.train,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectData":
        return cls(
            paths=     [PathRecord.from_dict(p)     for p in d.get("paths",     [])],
            sensors=   d.get("sensors",   []),
            wagons=    d.get("wagons",    []),
            scenarios= [ScenarioRecord.from_dict(s) for s in d.get("scenarios", [])],
            train=     d.get("train", {}),
        )

    def path_lengths(self) -> dict[str, float]:
        """Return {track_id: length_mm} — used by DKP validation."""
        return {p.track_id: p.length_mm for p in self.paths}

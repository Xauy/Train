"""
storage/models.py
Project-level data containers (schema v0.2).

These are the plain-Python objects that flow between the UI pages and the
JSON store.  Each class maps 1-to-1 to a record in *.chameleon.json.

Class hierarchy
───────────────
  ProjectData
    ├── paths    : List[PathRecord]
    ├── dkps     : List[DKPRecord]
    ├── wagons   : List[WagonRecord]   → each contains List[AxleDef]
    ├── train    : TrainRecord         → contains List[WagonSequenceEntry]
    └── scenario : ScenarioRecord      → contains List[ScenarioStep]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class PathRecord:
    """One track / path as entered on the Пути (Paths) page.

    Geometry is stored as two 3-D endpoints (мм).
    *length_mm* is NOT persisted — it is computed from the coordinates
    so the JSON stays the single source of truth.
    """
    track_id: str   = ""
    name:     str   = ""
    x1: float = 0.0
    y1: float = 0.0
    z1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    z2: float = 0.0

    @property
    def length_mm(self) -> float:
        """Euclidean length of the segment (мм)."""
        dx = self.x2 - self.x1
        dy = self.y2 - self.y1
        dz = self.z2 - self.z1
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "name":     self.name,
            "x1": self.x1, "y1": self.y1, "z1": self.z1,
            "x2": self.x2, "y2": self.y2, "z2": self.z2,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PathRecord":
        return cls(
            track_id=str(d.get("track_id", "")),
            name=    str(d.get("name", "")),
            x1=float(d.get("x1", 0.0)), y1=float(d.get("y1", 0.0)), z1=float(d.get("z1", 0.0)),
            x2=float(d.get("x2", 0.0)), y2=float(d.get("y2", 0.0)), z2=float(d.get("z2", 0.0)),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Nested / helper records
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AxleDef:
    """One axle of a wagon.

    *offset_mm* — longitudinal distance from the wagon's front face (мм),
    measured in the direction of travel.
    """
    offset_mm: float = 0.0

    def to_dict(self) -> dict:
        return {"offset_mm": self.offset_mm}

    @classmethod
    def from_dict(cls, d: dict) -> "AxleDef":
        return cls(offset_mm=float(d["offset_mm"]))


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WagonSequenceEntry:
    """One entry in a train's wagon_sequence list."""
    wagon_id: str  = ""
    count:    int  = 1
    reversed: bool = False   # True → wagon coupled tail-first

    def to_dict(self) -> dict:
        return {
            "wagon_id": self.wagon_id,
            "count":    self.count,
            "reversed": self.reversed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WagonSequenceEntry":
        return cls(
            wagon_id=str(d.get("wagon_id", "")),
            count=   int(d.get("count", 1)),
            reversed=bool(d.get("reversed", False)),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScenarioStep:
    """One timed step in a scenario.

    Fields
    ------
    duration_ms      : step duration (мс)
    v0_mms           : initial speed at the start of the step (мм/с)
    accel_mms2       : constant acceleration (мм/с²); negative = braking
    v_threshold_mms  : speed cap (мм/с); 0 = no limit
    behavior         : 'LeftToRight' | 'RightToLeft' | 'Stop'
    """
    duration_ms:     int   = 0
    v0_mms:          float = 0.0
    accel_mms2:      float = 0.0
    v_threshold_mms: float = 0.0
    behavior:        str   = "LeftToRight"

    ALLOWED_BEHAVIORS: frozenset = frozenset({"LeftToRight", "RightToLeft", "Stop"})

    def to_dict(self) -> dict:
        return {
            "duration_ms":     self.duration_ms,
            "v0_mms":          self.v0_mms,
            "accel_mms2":      self.accel_mms2,
            "v_threshold_mms": self.v_threshold_mms,
            "behavior":        self.behavior,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScenarioStep":
        return cls(
            duration_ms=    int(d["duration_ms"]),
            v0_mms=         float(d["v0_mms"]),
            accel_mms2=     float(d["accel_mms2"]),
            v_threshold_mms=float(d["v_threshold_mms"]),
            behavior=       str(d["behavior"]),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Top-level records
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DKPRecord:
    """Trackside axle-counter sensor as entered on the ДКП page."""
    sensor_id:        str   = ""
    track_id:         str   = ""
    s_mm:             float = 0.0   # longitudinal position along the path
    sensor_type:      str   = "Fox" # 'Fox' | 'Mongoose'
    enabled:          bool  = True
    direction_filter: str   = "Any" # 'Any' | 'LeftToRight' | 'RightToLeft'
    zone_mm:          float = 100.0 # half-width of the trigger zone

    SENSOR_TYPES:      frozenset = frozenset({"Fox", "Mongoose"})
    DIRECTION_FILTERS: frozenset = frozenset({"Any", "LeftToRight", "RightToLeft"})

    def to_dict(self) -> dict:
        return {
            "sensor_id":        self.sensor_id,
            "track_id":         self.track_id,
            "s_mm":             self.s_mm,
            "sensor_type":      self.sensor_type,
            "enabled":          self.enabled,
            "direction_filter": self.direction_filter,
            "zone_mm":          self.zone_mm,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DKPRecord":
        return cls(
            sensor_id=       str(d["sensor_id"]),
            track_id=        str(d["track_id"]),
            s_mm=            float(d["s_mm"]),
            sensor_type=     str(d.get("sensor_type", "Fox")),
            enabled=         bool(d.get("enabled", True)),
            direction_filter=str(d.get("direction_filter", "Any")),
            zone_mm=         float(d.get("zone_mm", 100.0)),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WagonRecord:
    """Wagon / locomotive model card from the project library."""
    wagon_id:      str             = ""
    name:          str             = ""
    wagon_type:    str             = ""  # 'motor' | 'trailer' | 'loco' | …
    length_mm:     float           = 0.0
    height_mm:     float           = 0.0
    bogie_base_mm: float           = 0.0
    axles:         List[AxleDef]   = field(default_factory=list)
    model_path:    str             = ""  # path to 3-D asset (glTF / OBJ)

    def to_dict(self) -> dict:
        return {
            "wagon_id":      self.wagon_id,
            "name":          self.name,
            "wagon_type":    self.wagon_type,
            "length_mm":     self.length_mm,
            "height_mm":     self.height_mm,
            "bogie_base_mm": self.bogie_base_mm,
            "axles":         [a.to_dict() for a in self.axles],
            "model_path":    self.model_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WagonRecord":
        return cls(
            wagon_id=     str(d["wagon_id"]),
            name=         str(d.get("name", "")),
            wagon_type=   str(d.get("wagon_type", "")),
            length_mm=    float(d["length_mm"]),
            height_mm=    float(d.get("height_mm", 0.0)),
            bogie_base_mm=float(d.get("bogie_base_mm", 0.0)),
            axles=        [AxleDef.from_dict(a) for a in d.get("axles", [])],
            model_path=   str(d.get("model_path", "")),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TrainRecord:
    """Train composition and initial placement."""
    train_id:       str                    = "TRAIN_1"
    track_id:       str                    = ""
    s0_mm:          float                  = 0.0
    direction:      str                    = "LeftToRight"
    wagon_sequence: List[WagonSequenceEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "train_id":       self.train_id,
            "track_id":       self.track_id,
            "s0_mm":          self.s0_mm,
            "direction":      self.direction,
            "wagon_sequence": [e.to_dict() for e in self.wagon_sequence],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrainRecord":
        return cls(
            train_id= str(d.get("train_id", "TRAIN_1")),
            track_id= str(d.get("track_id", "")),
            s0_mm=    float(d.get("s0_mm", 0.0)),
            direction=str(d.get("direction", "LeftToRight")),
            wagon_sequence=[
                WagonSequenceEntry.from_dict(e)
                for e in d.get("wagon_sequence", [])
            ],
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScenarioRecord:
    """One named scenario — an ordered list of motion steps."""
    scenario_id: str               = "SC_1"
    name:        str               = ""
    steps:       List[ScenarioStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "name":        self.name,
            "steps":       [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScenarioRecord":
        return cls(
            scenario_id=str(d.get("scenario_id", "SC_1")),
            name=       str(d.get("name", "")),
            steps=      [ScenarioStep.from_dict(s) for s in d.get("steps", [])],
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ProjectData:
    """Full, serialisable project document (v0.2).

    Maps 1-to-1 to the top level of *.chameleon.json.
    """
    version:  str                = "0.2"
    paths:    List[PathRecord]   = field(default_factory=list)
    dkps:     List[DKPRecord]    = field(default_factory=list)
    wagons:   List[WagonRecord]  = field(default_factory=list)
    train:    TrainRecord        = field(default_factory=TrainRecord)
    scenario: ScenarioRecord     = field(default_factory=ScenarioRecord)

    def to_dict(self) -> dict:
        return {
            "version":  self.version,
            "paths":    [p.to_dict() for p in self.paths],
            "dkps":     [d.to_dict() for d in self.dkps],
            "wagons":   [w.to_dict() for w in self.wagons],
            "train":    self.train.to_dict(),
            "scenario": self.scenario.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectData":
        return cls(
            version= str(d.get("version", "0.2")),
            paths=   [PathRecord.from_dict(p)  for p in d.get("paths",  [])],
            dkps=    [DKPRecord.from_dict(dk)  for dk in d.get("dkps",  [])],
            wagons=  [WagonRecord.from_dict(w) for w in d.get("wagons", [])],
            train=   TrainRecord.from_dict(d["train"])       if d.get("train")    else TrainRecord(),
            scenario=ScenarioRecord.from_dict(d["scenario"]) if d.get("scenario") else ScenarioRecord(),
        )

    def path_lengths(self) -> dict[str, float]:
        """Return {track_id: length_mm} — used by DKP validation."""
        return {p.track_id: p.length_mm for p in self.paths}

"""
physics/models.py
Chameleon — railway simulator

All immutable configuration and runtime-state dataclasses live here.
The simulation engine (engine.py) imports them; the UI imports them too
so there is a single source of truth for the data model.

Sections:
  2.2  Configuration dataclasses  (SimConfig and its components)
  2.3  State dataclasses          (SimState and its components)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2.2 — Configuration models
#  Built once before the simulation starts; never mutated during a run.
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class AxleDef:
    """A single wheelset (axle) within a wagon.

    offset_mm is measured from the front face of the wagon toward the rear,
    along the direction of travel.  The first axle in the list is always the
    one closest to the front of the wagon.
    """
    offset_mm: float

    def __post_init__(self) -> None:
        if self.offset_mm < 0:
            raise ValueError(f"AxleDef.offset_mm must be ≥ 0, got {self.offset_mm}")

    def to_dict(self) -> dict:
        return {"offset_mm": self.offset_mm}

    @classmethod
    def from_dict(cls, d: dict) -> "AxleDef":
        return cls(offset_mm=float(d["offset_mm"]))


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WagonDef:
    """Geometric description of one wagon type.

    wagon_id is the unique identifier used in WagonRecord JSON and in
    TrainConfig.wagon_sequence.

    axles must contain at least 2 entries and be ordered front-to-rear.
    No axle offset may exceed length_mm.
    """
    wagon_id:   str
    name:       str
    length_mm:  float
    height_mm:  float
    axles:      List[AxleDef]
    model_path: str = ""   # optional path to a 3-D asset (.obj); empty → fallback Box

    def __post_init__(self) -> None:
        if self.length_mm <= 0:
            raise ValueError(f"WagonDef '{self.wagon_id}': length_mm must be > 0")
        if len(self.axles) < 2:
            raise ValueError(f"WagonDef '{self.wagon_id}': at least 2 axles required")
        for axle in self.axles:
            if axle.offset_mm > self.length_mm:
                raise ValueError(
                    f"WagonDef '{self.wagon_id}': axle offset {axle.offset_mm} mm "
                    f"exceeds wagon length {self.length_mm} mm"
                )

    @property
    def axle_count(self) -> int:
        return len(self.axles)

    def to_dict(self) -> dict:
        return {
            "wagon_id":   self.wagon_id,
            "name":       self.name,
            "length_mm":  self.length_mm,
            "height_mm":  self.height_mm,
            "axles":      [a.to_dict() for a in self.axles],
            "model_path": self.model_path,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WagonDef":
        return cls(
            wagon_id=   str(d["wagon_id"]),
            name=       str(d["name"]),
            length_mm=  float(d["length_mm"]),
            height_mm=  float(d["height_mm"]),
            axles=      [AxleDef.from_dict(a) for a in d["axles"]],
            model_path= str(d.get("model_path", "")),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class WagonSlot:
    """One entry in TrainConfig.wagon_sequence.

    A slot references a wagon type by wagon_id and can repeat it *count*
    times placed consecutively.  Setting reversed=True mirrors the axle
    offsets so the wagon is coupled rear-first.
    """
    wagon_id: str
    count:    int  = 1
    reversed: bool = False

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError(f"WagonSlot '{self.wagon_id}': count must be ≥ 1")

    def to_dict(self) -> dict:
        return {
            "wagon_id": self.wagon_id,
            "count":    self.count,
            "reversed": self.reversed,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "WagonSlot":
        return cls(
            wagon_id= str(d["wagon_id"]),
            count=    int(d.get("count", 1)),
            reversed= bool(d.get("reversed", False)),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TrainConfig:
    """Full composition and starting position of the train.

    direction controls the initial sense of positive motion:
      'LeftToRight' — s increases (train moves toward higher s_mm values)
      'RightToLeft' — s decreases
    """
    train_id:       str
    track_id:       str
    s0_mm:          float
    direction:      str
    wagon_sequence: List[WagonSlot]

    _VALID_DIRECTIONS = {"LeftToRight", "RightToLeft"}

    def __post_init__(self) -> None:
        if self.direction not in self._VALID_DIRECTIONS:
            raise ValueError(
                f"TrainConfig '{self.train_id}': direction must be one of "
                f"{self._VALID_DIRECTIONS}, got '{self.direction}'"
            )
        if self.s0_mm < 0:
            raise ValueError(f"TrainConfig '{self.train_id}': s0_mm must be ≥ 0")
        if not self.wagon_sequence:
            raise ValueError(f"TrainConfig '{self.train_id}': wagon_sequence is empty")

    def expand(self, wagon_library: dict[str, WagonDef]) -> List[WagonDef]:
        """Return a flat ordered list of WagonDef objects for this train.

        wagon_library maps wagon_id → WagonDef.
        Raises KeyError if a wagon_id is not found in the library.
        If a slot has reversed=True, the axle list is mirrored.
        """
        result: List[WagonDef] = []
        for slot in self.wagon_sequence:
            template = wagon_library[slot.wagon_id]
            for _ in range(slot.count):
                if not slot.reversed:
                    result.append(template)
                else:
                    mirrored_axles = [
                        AxleDef(offset_mm=template.length_mm - a.offset_mm)
                        for a in reversed(template.axles)
                    ]
                    result.append(WagonDef(
                        wagon_id=   template.wagon_id + "_rev",
                        name=       template.name + " (обратно)",
                        length_mm=  template.length_mm,
                        height_mm=  template.height_mm,
                        axles=      mirrored_axles,
                        model_path= template.model_path,
                    ))
        return result

    def to_dict(self) -> dict:
        return {
            "train_id":       self.train_id,
            "track_id":       self.track_id,
            "s0_mm":          self.s0_mm,
            "direction":      self.direction,
            "wagon_sequence": [s.to_dict() for s in self.wagon_sequence],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TrainConfig":
        return cls(
            train_id=       str(d["train_id"]),
            track_id=       str(d["track_id"]),
            s0_mm=          float(d["s0_mm"]),
            direction=      str(d["direction"]),
            wagon_sequence= [WagonSlot.from_dict(s) for s in d["wagon_sequence"]],
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class DKPConfig:
    """Static description of one trackside detection sensor (ДКП).

    The sensor is a point trigger at ``s_mm`` along its path; each axle
    fires the sensor at most once per simulation run, on the tick when
    it crosses the point.

    direction_filter restricts which crossing directions generate an event:
      'Both'        — both directions (default)
      'LeftToRight' — only when the axle moves toward higher s values
      'RightToLeft' — only when the axle moves toward lower s values

    The legacy value 'Any' is accepted on load as a synonym for 'Both' so
    older project files continue to work; new saves emit 'Both'.
    """
    sensor_id:        str
    track_id:         str
    s_mm:             float
    sensor_type:      str   # 'Fox' | 'Mongoose'
    enabled:          bool
    direction_filter: str   # 'Both' | 'LeftToRight' | 'RightToLeft'

    _VALID_TYPES   = {"Fox", "Mongoose"}
    _VALID_FILTERS = {"Both", "LeftToRight", "RightToLeft"}
    _LEGACY_FILTER_ALIASES = {"Any": "Both"}

    def __post_init__(self) -> None:
        # Normalise legacy filter values transparently.
        if self.direction_filter in self._LEGACY_FILTER_ALIASES:
            self.direction_filter = self._LEGACY_FILTER_ALIASES[self.direction_filter]

        if self.sensor_type not in self._VALID_TYPES:
            raise ValueError(
                f"DKPConfig '{self.sensor_id}': sensor_type must be one of "
                f"{self._VALID_TYPES}, got '{self.sensor_type}'"
            )
        if self.direction_filter not in self._VALID_FILTERS:
            raise ValueError(
                f"DKPConfig '{self.sensor_id}': direction_filter must be one of "
                f"{self._VALID_FILTERS}, got '{self.direction_filter}'"
            )

    def to_dict(self) -> dict:
        return {
            "sensor_id":        self.sensor_id,
            "track_id":         self.track_id,
            "s_mm":             self.s_mm,
            "sensor_type":      self.sensor_type,
            "enabled":          self.enabled,
            "direction_filter": self.direction_filter,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DKPConfig":
        # Legacy 'zone_mm' is ignored on load — point triggering replaces it.
        return cls(
            sensor_id=        str(d["sensor_id"]),
            track_id=         str(d["track_id"]),
            s_mm=             float(d["s_mm"]),
            sensor_type=      str(d.get("sensor_type", "Fox")),
            enabled=          bool(d.get("enabled", True)),
            direction_filter= str(d.get("direction_filter", "Both")),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ScenarioStep:
    """One phase of motion in the simulation scenario.

    duration_ms   — how long this step lasts (ms of simulation time).
    v0_mms        — speed at the very start of this step (mm/s).
    accel_mms2    — constant acceleration applied each tick (mm/s²).
                    Use 0 for constant-speed cruising.
    v_threshold   — speed cap for this step (mm/s).  0 = uncapped.
    behavior      — 'LeftToRight' | 'RightToLeft' | 'Stop'
    """
    duration_ms:     int
    v0_mms:          float
    accel_mms2:      float
    v_threshold_mms: float
    behavior:        str

    _VALID_BEHAVIORS = {"LeftToRight", "RightToLeft", "Stop"}

    def __post_init__(self) -> None:
        if self.behavior not in self._VALID_BEHAVIORS:
            raise ValueError(
                f"ScenarioStep: behavior must be one of {self._VALID_BEHAVIORS}, "
                f"got '{self.behavior}'"
            )
        if self.duration_ms < 0:
            raise ValueError("ScenarioStep: duration_ms must be ≥ 0")
        if self.v_threshold_mms < 0:
            raise ValueError("ScenarioStep: v_threshold_mms must be ≥ 0")

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
            duration_ms=     int(d["duration_ms"]),
            v0_mms=          float(d.get("v0_mms", 0.0)),
            accel_mms2=      float(d.get("accel_mms2", 0.0)),
            v_threshold_mms= float(d.get("v_threshold_mms", 0.0)),
            behavior=        str(d.get("behavior", "LeftToRight")),
        )


# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SimConfig:
    """Top-level configuration object passed to SimulationEngine.

    wagon_library maps wagon_id → WagonDef and is used to resolve the
    train's wagon_sequence into a flat list of physical vehicles.

    dt_ms is the simulation tick interval in milliseconds.
    """
    train:         TrainConfig
    dkps:          List[DKPConfig]
    steps:         List[ScenarioStep]
    wagon_library: dict[str, WagonDef]
    dt_ms:         int = 16

    def __post_init__(self) -> None:
        if self.dt_ms <= 0:
            raise ValueError(f"SimConfig: dt_ms must be > 0, got {self.dt_ms}")
        if not self.steps:
            raise ValueError("SimConfig: steps list is empty")

    def to_dict(self) -> dict:
        return {
            "train":         self.train.to_dict(),
            "dkps":          [d.to_dict() for d in self.dkps],
            "steps":         [s.to_dict() for s in self.steps],
            "wagon_library": {wid: w.to_dict() for wid, w in self.wagon_library.items()},
            "dt_ms":         self.dt_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SimConfig":
        library = {
            wid: WagonDef.from_dict(wd)
            for wid, wd in d.get("wagon_library", {}).items()
        }
        return cls(
            train=         TrainConfig.from_dict(d["train"]),
            dkps=          [DKPConfig.from_dict(x) for x in d.get("dkps", [])],
            steps=         [ScenarioStep.from_dict(x) for x in d["steps"]],
            wagon_library= library,
            dt_ms=         int(d.get("dt_ms", 16)),
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2.3 — Simulation state models
#  Created fresh on every tick; emitted via Qt signals.
#  Read-only snapshots — the engine owns the mutable originals.
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class AxisState:
    """Position of one physical axle at a single point in time."""
    wagon_index: int
    axle_index:  int
    s_mm:        float
    s_prev_mm:   float

    @property
    def moved_right(self) -> bool:
        return self.s_mm > self.s_prev_mm

    @property
    def delta_mm(self) -> float:
        return self.s_mm - self.s_prev_mm

    def crossed_interval(self, lo: float, hi: float) -> bool:
        """Return True if the axle's movement this tick overlapped [lo, hi]."""
        travel_lo = min(self.s_mm, self.s_prev_mm)
        travel_hi = max(self.s_mm, self.s_prev_mm)
        return travel_lo <= hi and travel_hi >= lo


# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DKPEvent:
    """One sensor-trigger event recorded during a simulation run."""
    t_ms:        int
    sensor_id:   str
    sensor_type: str
    wagon_index: int
    axle_index:  int
    direction:   str
    v_mms:       float
    s_axis_mm:   float

    def to_dict(self) -> dict:
        return {
            "t_ms":        self.t_ms,
            "sensor_id":   self.sensor_id,
            "sensor_type": self.sensor_type,
            "wagon_index": self.wagon_index,
            "axle_index":  self.axle_index,
            "direction":   self.direction,
            "v_mms":       self.v_mms,
            "s_axis_mm":   self.s_axis_mm,
        }


# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SimState:
    """Full snapshot of the simulation at the end of one tick.

    Emitted by SimulationEngine on every timer firing.
    """
    t_ms:            int
    step_index:      int
    step_elapsed_ms: int
    v_mms:           float
    direction:       str
    s_head_mm:       float
    axes:            tuple[AxisState, ...]
    running:         bool
    paused:          bool

    @property
    def speed_kmh(self) -> float:
        """Convenience conversion: mm/s → km/h."""
        return self.v_mms * 3.6 / 1_000

    @property
    def axis_count(self) -> int:
        return len(self.axes)

    def axis(self, wagon_index: int, axle_index: int) -> AxisState | None:
        for a in self.axes:
            if a.wagon_index == wagon_index and a.axle_index == axle_index:
                return a
        return None

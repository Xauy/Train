"""
validation/validators.py
Pure validation functions — no Qt dependency.

Each public function returns a list of ValidationError objects.
An empty list means the input is valid.

The UI pages call these functions and translate the results into visual
highlights; the validators themselves know nothing about widgets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ValidationError:
    """One validation problem.

    *row*    — 0-based index into the table / list that was checked.
    *field*  — name of the offending field (matches the column/key name).
    *message*— human-readable Russian description shown in the UI.
    """
    row:     int
    field:   str
    message: str


# ─────────────────────────────────────────────────────────────────────────────


def validate_dkp_sensors(
    sensors:      List[dict],
    path_lengths: dict[str, float],
) -> List[ValidationError]:
    """Validate a list of DKP sensor dicts against the known path lengths.

    Rules checked:
      • s_mm must be parseable as a float.
      • s_mm must be ≥ 0.
      • If the sensor's track_id is known, s_mm must not exceed that path's length.
      • zone_mm must be > 0.

    Args:
        sensors:      List of dicts as produced by DkpPage.to_dict().
        path_lengths: Mapping {track_id: length_mm} from PathRecord.

    Returns:
        List of ValidationError; empty list means all sensors are valid.
    """
    errors: List[ValidationError] = []

    for row, sensor in enumerate(sensors):
        sensor_id = sensor.get("sensor_id") or f"строка {row + 1}"
        track_id  = sensor.get("track_id", "")
        raw_s     = sensor.get("s_mm", 0)
        zone_mm   = sensor.get("zone_mm", 0)

        # ── s_mm ──────────────────────────────────────────────────────────
        try:
            s_mm = float(raw_s)
        except (TypeError, ValueError):
            errors.append(ValidationError(
                row=row, field="s_mm",
                message=f"[{sensor_id}] s_mm не является числом: '{raw_s}'",
            ))
            continue

        if s_mm < 0:
            errors.append(ValidationError(
                row=row, field="s_mm",
                message=f"[{sensor_id}] s_mm не может быть отрицательным",
            ))
            continue

        if track_id in path_lengths and s_mm > path_lengths[track_id]:
            errors.append(ValidationError(
                row=row, field="s_mm",
                message=(
                    f"[{sensor_id}] s_mm={s_mm} превышает длину пути "
                    f"'{track_id}' ({path_lengths[track_id]} мм)"
                ),
            ))

        # ── zone_mm ───────────────────────────────────────────────────────
        try:
            zone = float(zone_mm)
        except (TypeError, ValueError):
            zone = 0.0

        if zone <= 0:
            errors.append(ValidationError(
                row=row, field="zone_mm",
                message=f"[{sensor_id}] zone_mm должен быть > 0",
            ))

    return errors


# ─────────────────────────────────────────────────────────────────────────────


def validate_paths(paths: List[dict]) -> List[ValidationError]:
    """Validate a list of path/track dicts.

    Rules checked:
      • track_id must not be empty.
      • track_id must be unique within the list.
      • length_mm must be > 0.
    """
    errors:   List[ValidationError] = []
    seen_ids: set[str]              = set()

    for row, path in enumerate(paths):
        track_id  = str(path.get("track_id", "")).strip()
        raw_len   = path.get("length_mm", 0)

        if not track_id:
            errors.append(ValidationError(
                row=row, field="track_id",
                message=f"Строка {row + 1}: track_id не может быть пустым",
            ))
        elif track_id in seen_ids:
            errors.append(ValidationError(
                row=row, field="track_id",
                message=f"Строка {row + 1}: track_id '{track_id}' не уникален",
            ))
        else:
            seen_ids.add(track_id)

        try:
            length = float(raw_len)
        except (TypeError, ValueError):
            errors.append(ValidationError(
                row=row, field="length_mm",
                message=f"Строка {row + 1}: length_mm не является числом: '{raw_len}'",
            ))
            continue

        if length <= 0:
            errors.append(ValidationError(
                row=row, field="length_mm",
                message=f"Строка {row + 1}: length_mm должен быть > 0",
            ))

    return errors


# ─────────────────────────────────────────────────────────────────────────────


def validate_scenario_steps(steps: List[dict]) -> List[ValidationError]:
    """Validate a list of ScenarioStep dicts.

    Rules checked:
      • duration_ms must be ≥ 0.
      • v_threshold_mms must be ≥ 0.
      • behavior must be one of the known values.
    """
    VALID_BEHAVIORS = {"LeftToRight", "RightToLeft", "Stop"}
    errors: List[ValidationError] = []

    for row, step in enumerate(steps):
        label = f"Шаг {row + 1}"

        dur = step.get("duration_ms", 0)
        try:
            if int(dur) < 0:
                errors.append(ValidationError(
                    row=row, field="duration_ms",
                    message=f"{label}: duration_ms должен быть ≥ 0",
                ))
        except (TypeError, ValueError):
            errors.append(ValidationError(
                row=row, field="duration_ms",
                message=f"{label}: duration_ms не является целым числом",
            ))

        thr = step.get("v_threshold_mms", 0)
        try:
            if float(thr) < 0:
                errors.append(ValidationError(
                    row=row, field="v_threshold_mms",
                    message=f"{label}: v_threshold_mms должен быть ≥ 0",
                ))
        except (TypeError, ValueError):
            errors.append(ValidationError(
                row=row, field="v_threshold_mms",
                message=f"{label}: v_threshold_mms не является числом",
            ))

        behavior = step.get("behavior", "")
        if behavior not in VALID_BEHAVIORS:
            errors.append(ValidationError(
                row=row, field="behavior",
                message=f"{label}: недопустимое поведение '{behavior}'",
            ))

    return errors

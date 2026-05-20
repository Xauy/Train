"""
physics/dkp_logger.py
File-based logger for DKP (axle-counter) trigger events.

For each simulation run, three log files are written into a fresh
timestamped directory under ``<project_root>/logs/``:

    logs/
      20260520_114213/
        dkp_fox.log         — only Fox-type sensor events
        dkp_mongoose.log    — only Mongoose-type sensor events
        dkp_all.log         — every event, regardless of system

Each line records the trigger time, the wagon identifier, and the
direction of movement.  Sensor ID, axle index within the wagon, and
the axle's instantaneous speed are also included because they're
nearly free and make the log actually readable when one wagon
crosses a sensor multiple times.

This module has no Qt dependency and can be exercised standalone.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import IO, Mapping, Optional

from physics.models import DKPEvent


# Folder name (relative to the project root) that holds all run-folders.
LOGS_DIRNAME: str = "logs"

# Header line written at the top of every log file.  Tab-separated so it
# also opens cleanly in a spreadsheet.
_HEADER: str = (
    "# DKP event log — Chameleon\n"
    "# Columns: wall_time  sim_t_ms  sensor_id  sensor_type  "
    "wagon_id  direction  axle_index  v_mms\n"
)


def _project_root() -> Path:
    """Return the project root (the folder that contains main.py).

    This module lives at ``<root>/physics/dkp_logger.py``.
    """
    return Path(__file__).resolve().parent.parent


def _logs_root() -> Path:
    """Return the absolute path to the ``logs/`` directory."""
    return _project_root() / LOGS_DIRNAME


class DKPEventLogger:
    """Three-file DKP event logger.

    Usage::

        wagon_ids = {i: w.wagon_id for i, w in enumerate(engine._wagons)}
        logger = DKPEventLogger(wagon_ids)
        logger.open()
        # … connect engine.dkp_triggered to logger.log_event …
        logger.close()

    Or as a context manager::

        with DKPEventLogger(wagon_ids) as logger:
            ...

    All file I/O is line-buffered so the log is readable even if the
    process is killed before close().
    """

    def __init__(
        self,
        wagon_id_by_index: Mapping[int, str],
        *,
        run_dir: Optional[Path] = None,
    ) -> None:
        """Set up the logger.

        Parameters
        ----------
        wagon_id_by_index
            Maps the integer ``wagon_index`` carried by DKPEvent to the
            human-readable wagon id shown in the log.  Built once at
            simulation start from the engine's wagon list.
        run_dir
            Override directory for this run's log files.  When ``None``
            (the default), a fresh subdirectory of ``logs/`` named with
            a UTC timestamp is created.  Mainly useful for tests.
        """
        self._wagon_ids = dict(wagon_id_by_index)
        self._run_dir = run_dir
        self._fox_file:  Optional[IO[str]] = None
        self._mon_file:  Optional[IO[str]] = None
        self._all_file:  Optional[IO[str]] = None

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                          #
    # ------------------------------------------------------------------ #

    def open(self) -> Path:
        """Create the run directory and open all three log files.

        Returns the absolute path to the run directory so the caller
        can show it to the user or include it in the UI.
        """
        if self._run_dir is None:
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self._run_dir = _logs_root() / stamp
        self._run_dir.mkdir(parents=True, exist_ok=True)

        # ``buffering=1`` → line-buffered, so the file is readable
        # live even while the simulation is running.
        self._fox_file = open(
            self._run_dir / "dkp_fox.log", "w", encoding="utf-8", buffering=1,
        )
        self._mon_file = open(
            self._run_dir / "dkp_mongoose.log", "w", encoding="utf-8", buffering=1,
        )
        self._all_file = open(
            self._run_dir / "dkp_all.log", "w", encoding="utf-8", buffering=1,
        )

        for f in (self._fox_file, self._mon_file, self._all_file):
            f.write(_HEADER)

        return self._run_dir

    def close(self) -> None:
        """Flush and close all log files.  Safe to call more than once."""
        for attr in ("_fox_file", "_mon_file", "_all_file"):
            f = getattr(self, attr)
            if f is not None:
                try:
                    f.flush()
                    f.close()
                except OSError:
                    pass
                setattr(self, attr, None)

    # Context-manager sugar -----------------------------------------------

    def __enter__(self) -> "DKPEventLogger":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def log_event(self, event: DKPEvent) -> None:
        """Write *event* to dkp_all.log plus the per-system file.

        Unknown sensor types are written only to the combined file.
        If open() was never called, the call is a silent no-op so the
        host UI can wire the signal up early without ordering risk.
        """
        if self._all_file is None:
            return

        line = self._format_line(event)
        self._all_file.write(line)

        if event.sensor_type == "Fox" and self._fox_file is not None:
            self._fox_file.write(line)
        elif event.sensor_type == "Mongoose" and self._mon_file is not None:
            self._mon_file.write(line)

    @property
    def run_dir(self) -> Optional[Path]:
        """The directory where this run's logs are being written, or ``None``
        if the logger has not been opened yet."""
        return self._run_dir

    # ------------------------------------------------------------------ #
    #  Internals                                                          #
    # ------------------------------------------------------------------ #

    def _format_line(self, event: DKPEvent) -> str:
        """Produce one tab-separated log line ending in ``\\n``."""
        wall_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        wagon_id  = self._wagon_ids.get(event.wagon_index,
                                        f"#{event.wagon_index}")
        # Columns kept fixed-order so external tools (awk, pandas.read_csv
        # with sep='\t', etc.) can parse them by position.
        return (
            f"{wall_time}\t"
            f"{event.t_ms}\t"
            f"{event.sensor_id}\t"
            f"{event.sensor_type}\t"
            f"{wagon_id}\t"
            f"{event.direction}\t"
            f"{event.axle_index}\t"
            f"{event.v_mms:.2f}\n"
        )

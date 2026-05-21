"""
physics/simulation_engine.py
Chameleon — railway simulator

Implements plan sections 2.4 – 2.6:
  2.4  SimulationEngine class — public API and QTimer wiring
  2.5  _tick() — kinematics, axis update, DKP detection, step advance
  2.6  validate() — pre-start integrity checks; start() raises on failure

Design constraints (from section 2.1):
  • No UI imports.  All communication with the UI goes through Qt signals.
  • The engine is testable without a running QApplication by patching QTimer
    and calling _tick() manually.

Coordinate convention (from ТЗ v0.2):
  • s_mm increases from the start point of the path toward the end point.
  • Positive velocity → train moves toward higher s (LeftToRight).
  • Negative velocity → train moves toward lower s  (RightToLeft).
  • The "head" of the train is its leading axle, i.e. wagon 0 / axle 0.
    All other axes are offset *behind* the head by a cumulative distance.

Kinematics convention (updated):
  Velocity is a continuous quantity.  A scenario step's *behavior* field
  sets only the SIGN of the applied acceleration, never the velocity
  itself.  Velocity carries over between steps; v0_mms is consulted only
  to seed the very first step at simulation start (_reset_state).
  A train rolling in one direction that enters a step pointing the other
  way will smoothly decelerate through zero and accelerate the opposite
  way — never instantly snap.  See _tick() Step Б for the full rules.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from physics.models import (
    SimConfig,
    SimState,
    AxisState,
    DKPEvent,
    ScenarioStep,
    WagonDef,
)


class SimulationEngine(QObject):
    """Discrete-time railway simulation engine.

    Lifecycle
    ---------
    1. Construct with a fully validated SimConfig.
    2. (Optionally) call validate() to surface config errors before start.
    3. Call start() — raises ValueError if validate() finds problems.
    4. The engine fires tick_updated every dt_ms milliseconds.
    5. Call pause() / resume() to suspend and continue without resetting.
    6. Call stop() to halt and reset all mutable state.
    7. After sim_finished or stop(), call get_event_log() to retrieve events.

    Thread safety
    -------------
    QTimer fires in the Qt main-thread event loop, so all signal emissions
    happen on the same thread as the UI.  No additional locking is needed.
    """

    # ------------------------------------------------------------------ #
    #  Signals (plan 2.4)                                                  #
    # ------------------------------------------------------------------ #

    # Emitted every tick with a frozen SimState snapshot.
    tick_updated: pyqtSignal = pyqtSignal(object)

    # Emitted when any axis crosses a DKP zone this tick.
    dkp_triggered: pyqtSignal = pyqtSignal(object)

    # Emitted when the scenario advances to the next step; payload = new index.
    step_changed: pyqtSignal = pyqtSignal(int)

    # Emitted once when the last step's duration is exhausted.
    sim_finished: pyqtSignal = pyqtSignal()

    # ------------------------------------------------------------------ #
    #  Construction                                                        #
    # ------------------------------------------------------------------ #

    def __init__(self, config: SimConfig, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._config = config

        # Pre-expand the wagon sequence once so _tick() doesn't repeat work.
        # wagon_library maps wagon_id → WagonDef.
        self._wagons: List[WagonDef] = config.train.expand(config.wagon_library)

        # Cumulative front-face offsets of each wagon from the train head.
        # wagon_front_offset[i] = sum of lengths of wagons 0 … i-1.
        self._wagon_front_offsets: List[float] = []
        running_offset = 0.0
        for wagon in self._wagons:
            self._wagon_front_offsets.append(running_offset)
            running_offset += wagon.length_mm

        # Mutable simulation state — reset on every start().
        self._t_ms:            int   = 0
        self._step_index:      int   = 0
        self._step_elapsed_ms: int   = 0
        self._v_mms:           float = 0.0
        self._s_head_mm:       float = config.train.s0_mm
        self._direction:       str   = config.train.direction

        # Previous-tick axis positions for crossing detection (plan 2.5 Г/Д).
        # Initialised in _reset_axes().
        self._s_prev: List[List[float]] = []  # [wagon_i][axle_j]

        # Append-only event log for the current run.
        self._event_log: List[DKPEvent] = []

        # Tracks which (sensor_id, wagon_index, axle_index, direction)
        # quadruples have already fired in the current run.  Used to
        # enforce the "once per direction per axle per sensor" rule
        # (plan: point trigger).  Including the direction in the key
        # lets a 'Both'-filter sensor produce two events for an axle
        # that passes the point in one direction and then reverses.
        self._dkp_fired: set[tuple[str, int, int, str]] = set()

        # Qt timer — interval set from config; connected to _tick.
        self._timer = QTimer(self)
        self._timer.setInterval(config.dt_ms)
        self._timer.timeout.connect(self._tick)

        # Flags
        self._running: bool = False
        self._paused:  bool = False

    # ------------------------------------------------------------------ #
    #  Public API (plan 2.4)                                               #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Validate config, reset all state, and start the timer.

        Raises
        ------
        ValueError
            If validate() returns any errors.  The message contains all
            problems joined with newlines.
        """
        errors = self.validate()
        if errors:
            raise ValueError(
                "Симуляция не может быть запущена:\n" + "\n".join(f"• {e}" for e in errors)
            )

        self._reset_state()
        self._running = True
        self._paused  = False
        self._timer.start()

    def pause(self) -> None:
        """Suspend ticking without resetting state."""
        if self._running and not self._paused:
            self._timer.stop()
            self._paused = True

    def resume(self) -> None:
        """Continue ticking after a pause."""
        if self._running and self._paused:
            self._paused = False
            self._timer.start()

    def stop(self) -> None:
        """Stop the timer and reset all mutable state."""
        self._timer.stop()
        self._running = False
        self._paused  = False
        self._reset_state()

    def get_state(self) -> SimState:
        """Return a frozen snapshot of the current simulation state."""
        return self._build_state()

    def get_event_log(self) -> List[DKPEvent]:
        """Return all DKP events recorded since the last start()."""
        return list(self._event_log)

    # ------------------------------------------------------------------ #
    #  Validation (plan 2.6)                                               #
    # ------------------------------------------------------------------ #

    def validate(self) -> List[str]:
        """Check config integrity before start().

        Rules
        -----
        1. Every DKP whose track_id is non-empty must reference a track_id
           that exists in config.train (currently single-track model: must
           match train.track_id).
        2. Each enabled DKP's s_mm must be in [0, path_length].  Because
           path geometry is not stored in SimConfig (it lives in storage
           models), we only enforce the lower bound here and skip the upper
           bound check when no path length is available.  The upper-bound
           check is done by ProjectIO.validate_structure() before the engine
           is constructed.
        3. The wagon list must contain at least one wagon, and every wagon
           must have at least 2 axles.
        4. The scenario step list must not be empty.
        5. s0_mm must be ≥ 0.

        Returns an empty list when the config is valid.
        """
        errors: List[str] = []
        cfg = self._config

        # Rule 3 — wagons
        if not self._wagons:
            errors.append("Состав не содержит ни одного вагона.")
        else:
            for i, wagon in enumerate(self._wagons):
                if wagon.axle_count < 2:
                    errors.append(
                        f"Вагон {i} ('{wagon.name}'): минимум 2 оси, "
                        f"обнаружено {wagon.axle_count}."
                    )

        # Rule 4 — steps
        if not cfg.steps:
            errors.append("Список шагов сценария пуст.")

        # Rule 5 — s0_mm
        if cfg.train.s0_mm < 0:
            errors.append(
                f"Начальная координата состава s0_mm={cfg.train.s0_mm} "
                f"не может быть отрицательной."
            )

        # Rule 1 & 2 — DKP positions
        train_track = cfg.train.track_id
        for dkp in cfg.dkps:
            if dkp.track_id and dkp.track_id != train_track:
                errors.append(
                    f"ДКП '{dkp.sensor_id}': track_id '{dkp.track_id}' "
                    f"не совпадает с путём состава '{train_track}'."
                )
            if dkp.s_mm < 0:
                errors.append(
                    f"ДКП '{dkp.sensor_id}': s_mm={dkp.s_mm} "
                    f"не может быть отрицательным."
                )

        return errors

    # ------------------------------------------------------------------ #
    #  Internal — state management                                         #
    # ------------------------------------------------------------------ #

    def _reset_state(self) -> None:
        """Restore all mutable fields to their initial (start-of-run) values."""
        cfg = self._config
        self._t_ms            = 0
        self._step_index      = 0
        self._step_elapsed_ms = 0
        self._direction       = cfg.train.direction
        self._s_head_mm       = cfg.train.s0_mm
        self._event_log       = []
        self._dkp_fired.clear()

        # Seed v from the first step's v0, if steps exist.
        self._v_mms = cfg.steps[0].v0_mms if cfg.steps else 0.0

        self._reset_axes()

    def _reset_axes(self) -> None:
        """Initialise s_prev from the current head position."""
        self._s_prev = []
        for wi, wagon in enumerate(self._wagons):
            front_offset = self._wagon_front_offsets[wi]
            axle_prevs: List[float] = []
            for axle in wagon.axles:
                s = self._s_head_mm - (front_offset + axle.offset_mm)
                axle_prevs.append(s)
            self._s_prev.append(axle_prevs)

    # ------------------------------------------------------------------ #
    #  Internal — tick (plan 2.5)                                          #
    # ------------------------------------------------------------------ #

    def _tick(self) -> None:
        """Advance the simulation by one dt_ms step.

        Executed in the Qt main-thread event loop on every timer timeout.
        Implements the algorithm described in plan section 2.5 (steps А–Ж).
        """
        cfg = self._config

        # ── Step А: determine current ScenarioStep ─────────────────────
        if self._step_index >= len(cfg.steps):
            # Scenario is already exhausted — should not normally reach here
            # because we stop on transition, but guard anyway.
            self._timer.stop()
            self._running = False
            self.sim_finished.emit()
            return

        current_step: ScenarioStep = cfg.steps[self._step_index]
        dt_s: float = cfg.dt_ms / 1000.0

        # ── Step Б: apply kinematics ───────────────────────────────────
        # Velocity is treated as a continuous quantity that carries
        # across ticks (and across step transitions — see Step Е).
        # *behavior* sets the SIGN of the applied acceleration, not the
        # sign of velocity:
        #
        #   LeftToRight → accel_sign = +1   (push toward +s)
        #   RightToLeft → accel_sign = -1   (push toward -s)
        #   Stop        → accel_sign = -sign(v)  (oppose current motion)
        #
        # This means a train rolling right-to-left that enters a
        # LeftToRight step does NOT teleport its velocity to zero; it
        # smoothly decelerates, stops, and then accelerates leftward,
        # all under a single constant acceleration.  v_threshold caps
        # the speed only in the direction we're being pushed, so a
        # train decelerating against its current direction is never
        # artificially clipped.
        if current_step.behavior == "Stop":
            # Decelerate toward zero by applying accel opposite to v.
            # Once v reaches zero, hold there (accel_sign becomes 0).
            if self._v_mms > 0:
                accel_sign = -1.0
            elif self._v_mms < 0:
                accel_sign = +1.0
            else:
                accel_sign = 0.0
            v_new = self._v_mms + accel_sign * current_step.accel_mms2 * dt_s
            # Detect zero-crossing: if the velocity flipped sign, the
            # train has stopped; pin it at zero instead of overshooting
            # into the opposite direction.
            if accel_sign != 0.0 and v_new * self._v_mms < 0:
                v_new = 0.0
        else:
            accel_sign = +1.0 if current_step.behavior == "LeftToRight" else -1.0
            v_new = self._v_mms + accel_sign * current_step.accel_mms2 * dt_s
            # Cap |v| at v_threshold ONLY when v is in the direction
            # we're being pushed — a train still moving against accel
            # is decelerating and must not be clipped.
            if (current_step.v_threshold_mms > 0
                    and v_new * accel_sign > 0
                    and abs(v_new) > current_step.v_threshold_mms):
                v_new = accel_sign * current_step.v_threshold_mms

        self._v_mms = v_new

        # Reflect the actual direction of motion in the high-level
        # _direction field so the HUD shows reality, not intent.
        if self._v_mms > 0:
            self._direction = "LeftToRight"
        elif self._v_mms < 0:
            self._direction = "RightToLeft"
        # else: keep previous _direction so a stopped train still
        # remembers which way it last rolled (useful for the HUD label).

        # ── Step В: advance the head coordinate ────────────────────────
        s_head_new = self._s_head_mm + self._v_mms * dt_s

        # ── Step Г: compute new axis positions (save prev first) ───────
        # s_prev is still the positions from the last tick.
        new_s: List[List[float]] = []
        for wi, wagon in enumerate(self._wagons):
            front_offset = self._wagon_front_offsets[wi]
            axle_curr: List[float] = []
            for axle in wagon.axles:
                # An axle at offset_mm behind the wagon's front face sits at:
                #   s_axis = s_head_new − (cumulative front offset + axle offset)
                # This is independent of direction: s_head is always the
                # leading point, and every axle trails behind it.
                s = s_head_new - (front_offset + axle.offset_mm)
                axle_curr.append(s)
            new_s.append(axle_curr)

        # ── Step Д: check DKP triggers ─────────────────────────────────
        #
        # Each sensor is a point trigger at s = dkp.s_mm.  An axle fires
        # the sensor at most once per crossing direction per simulation
        # run, on the tick when its position crosses that point.  A
        # crossing is detected by checking whether s = dkp.s_mm lies in
        # the half-open interval spanned by the axle's previous and
        # current positions:
        #
        #   LeftToRight (s increasing):   s_prev <= s_mm < s_curr
        #   RightToLeft (s decreasing):   s_curr < s_mm <= s_prev
        #
        # A stationary axle (s_prev == s_curr) cannot cross anything and
        # is skipped automatically.  Each (sensor, wagon, axle, dir)
        # quadruple is remembered in self._dkp_fired so a repeated pass
        # in the SAME direction does not re-trigger.  A pass in the
        # OPPOSITE direction is a distinct event and will fire — which
        # is what 'Both' means: trigger on each direction, once per
        # direction.  The fired set is cleared by _reset_state().
        for dkp in cfg.dkps:
            if not dkp.enabled:
                continue

            trigger_s = dkp.s_mm
            no_filter = dkp.direction_filter == "Both"

            for wi, wagon in enumerate(self._wagons):
                for aj, axle in enumerate(wagon.axles):
                    s_prev = self._s_prev[wi][aj]
                    s_curr = new_s[wi][aj]

                    # Detect a directional crossing of the trigger point.
                    if s_prev <= trigger_s < s_curr:
                        crossing_dir = "LeftToRight"
                    elif s_curr < trigger_s <= s_prev:
                        crossing_dir = "RightToLeft"
                    else:
                        continue

                    # Apply direction filter.
                    if not no_filter and dkp.direction_filter != crossing_dir:
                        continue

                    # Suppress repeated passes in the SAME direction.
                    # Note the direction component in the key — this is
                    # what lets a 'Both' sensor fire twice (once per
                    # direction) when a wagon passes and then reverses.
                    key = (dkp.sensor_id, wi, aj, crossing_dir)
                    if key in self._dkp_fired:
                        continue

                    event = DKPEvent(
                        t_ms=        self._t_ms,
                        sensor_id=   dkp.sensor_id,
                        sensor_type= dkp.sensor_type,
                        wagon_index= wi,
                        axle_index=  aj,
                        direction=   crossing_dir,
                        v_mms=       abs(self._v_mms),
                        s_axis_mm=   s_curr,
                    )
                    self._event_log.append(event)
                    self._dkp_fired.add(key)
                    self.dkp_triggered.emit(event)

        # Commit new positions and head coordinate.
        self._s_prev    = new_s
        self._s_head_mm = s_head_new

        # ── Step Е: advance time and switch steps if due ───────────────
        self._t_ms            += cfg.dt_ms
        self._step_elapsed_ms += cfg.dt_ms

        if self._step_elapsed_ms >= current_step.duration_ms:
            self._step_elapsed_ms = 0
            self._step_index      += 1
            self.step_changed.emit(self._step_index)

            if self._step_index >= len(cfg.steps):
                # All steps exhausted — simulation complete.
                self._timer.stop()
                self._running = False
                # Emit the final state snapshot before finishing.
                self.tick_updated.emit(self._build_state())
                self.sim_finished.emit()
                return

            # Carry momentum across the step boundary — velocity is
            # whatever physics has produced by the end of the previous
            # step.  We do NOT reset to next_step.v0_mms here; that
            # field is only used once, at simulation start (see
            # _reset_state).  Teleporting velocity at every transition
            # would defeat the whole point of "direction changes
            # acceleration, not speed".

        # ── Step Ж: emit state snapshot ────────────────────────────────
        self.tick_updated.emit(self._build_state())

    # ------------------------------------------------------------------ #
    #  Internal — snapshot builder                                         #
    # ------------------------------------------------------------------ #

    def _build_state(self) -> SimState:
        """Construct an immutable SimState from current mutable fields."""
        axes: List[AxisState] = []
        for wi, wagon in enumerate(self._wagons):
            front_offset = self._wagon_front_offsets[wi]
            for aj, axle in enumerate(wagon.axles):
                s_curr = self._s_head_mm - (front_offset + axle.offset_mm)
                s_prev = (
                    self._s_prev[wi][aj]
                    if self._s_prev and wi < len(self._s_prev) and aj < len(self._s_prev[wi])
                    else s_curr
                )
                axes.append(AxisState(
                    wagon_index=wi,
                    axle_index= aj,
                    s_mm=       s_curr,
                    s_prev_mm=  s_prev,
                ))

        return SimState(
            t_ms=            self._t_ms,
            step_index=      self._step_index,
            step_elapsed_ms= self._step_elapsed_ms,
            v_mms=           self._v_mms,
            direction=       self._direction,
            s_head_mm=       self._s_head_mm,
            axes=            tuple(axes),
            running=         self._running,
            paused=          self._paused,
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

# (No module-level helpers currently — velocity clamping is inline in _tick.)

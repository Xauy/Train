"""
ui/scene_window.py
Chameleon — 3D simulation scene window.

Changes in this version:
  [1] BOUNDARY STOP — if the head or tail of the train reaches the rail
      endpoint (s ≤ 0 or s ≥ path length), the engine is paused and a
      warning is shown.  Checked every tick in _check_boundary().

  [2] WAGON VERTICAL OFFSET — wagon Box and axle Markers are rendered
      at the correct Z-height: box centre = rail_z + half_height so the
      bottom face sits exactly on the rail plane.  Axle markers sit at
      rail level (z = 0 by default, or z from path geometry).

  [3] DKP AXIS COUNTER — _DKPVisual keeps a running count of axis
      passages and updates a Text visual above the diamond after each
      flash.  Counter resets to 0 when the simulation is stopped.

  [4] COUPLER CONNECTIONS — a single Line visual (_coupler_line) spans
      all wagon junction points (rear of wagon i = front of wagon i+1).
      Updated every tick along with wagon positions.

  [5] OBJ 3-D MODELS — if a wagon's WagonDef has a non-empty model_path
      that points to a readable .obj file, the wagon is rendered as a
      VisPy Mesh built from that file's geometry.  The mesh is:
          • centered at the model's bounding-box center,
          • uniformly scaled so its longest axis matches wagon.length_mm,
          • oriented assuming X = length (forward), Y = width, Z = up
            (standard rail-asset convention).
      If the file is missing, unreadable, or the parser fails for any
      reason, the wagon falls back to the original Box rendering
      silently — the simulation always runs.

      OBJ loading uses a built-in minimal parser (vertices + triangular
      faces only); no external dependency is required.  If `trimesh`
      is available it is used preferentially for robustness on complex
      files (quads, negative indices, materials, groups).

Dependencies:
  pip install vispy pyopengl
  pip install trimesh           # optional, improves OBJ compatibility
"""

from __future__ import annotations

import math
import os
import logging
from typing import Dict, List, Optional, Tuple

import numpy as np

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QToolBar, QMessageBox, QSizePolicy, QComboBox,
    QPlainTextEdit, QFrame,
)

try:
    import vispy
    import vispy.scene
    import vispy.scene.visuals as visuals
    from vispy.scene import SceneCanvas
    from vispy.app import use_app
    use_app("pyqt6")
except ImportError as _err:
    raise ImportError(
        "VisPy is required for the 3D scene window.\n"
        "Install it with:  pip install vispy pyopengl\n"
        f"Original error: {_err}"
    ) from _err

from physics.models import SimConfig, SimState, DKPEvent, WagonDef, DKPConfig
from physics.simulation_engine import SimulationEngine
from physics.dkp_logger import DKPEventLogger


# ─────────────────────────────────────────────────────────────────────────────
#  Track geometry constants  (mm)
# ─────────────────────────────────────────────────────────────────────────────

GAUGE_MM         = 1520.0
RAIL_OFFSET      = GAUGE_MM / 2.0
SLEEPER_STEP_MM  = 600.0
SLEEPER_OVERHANG = GAUGE_MM * 0.40
DKP_POLE_HEIGHT  = GAUGE_MM * 0.60
DKP_HEAD_HALF    = GAUGE_MM * 0.18

# Coupler geometry
COUPLER_DIAMETER = GAUGE_MM * 0.08   # visual thickness represented as marker size
_COUPLER_COLOR   = (0.70, 0.72, 0.76, 1.0)   # light steel coupler bar

# Wagons are rendered 5% longer than their physical length (2.5% beyond each
# end) so adjacent wagon bodies visually overlap at the coupler, making the
# connection look solid rather than leaving a gap.
_WAGON_VISUAL_OVERLAP = 0.05


# ─────────────────────────────────────────────────────────────────────────────
#  Colour palette
# ─────────────────────────────────────────────────────────────────────────────

_BG             = (0.07, 0.07, 0.09, 1.0)
_GRID           = (0.16, 0.17, 0.20, 1.0)

_RAIL           = (0.72, 0.74, 0.78, 1.0)
_SLEEPER        = (0.30, 0.26, 0.22, 1.0)

_DKP_POLE       = (0.50, 0.54, 0.60, 1.0)
_DKP_FOX_IDLE   = (0.12, 0.88, 0.92, 1.0)
_DKP_MON_IDLE   = (0.96, 0.54, 0.08, 1.0)
_DKP_FLASH      = (1.00, 1.00, 1.00, 1.0)
_DKP_LABEL      = (0.76, 0.88, 1.00, 1.0)
_DKP_COUNT      = (0.95, 0.95, 0.60, 1.0)   # warm yellow — axis count readout

_WAGON_BODY     = (0.20, 0.33, 0.52, 1.0)
_WAGON_EDGE     = (0.50, 0.68, 0.90, 0.50)
_AXLE_FACE      = (0.95, 0.84, 0.18, 1.0)
_AXLE_EDGE      = (1.00, 1.00, 1.00, 0.45)

_TRACK_LABEL    = (0.60, 0.72, 0.94, 1.0)

_DKP_FLASH_MS   = 320

# Live DKP log panel (right side of the scene window)
_DKP_LOG_WIDTH      = 300
_DKP_LOG_MAX_LINES    = 2000
_DKP_LOG_PANEL_STYLE  = (
    "QFrame#dkpLogPanel { background:#0c0e12; border-left:1px solid #252930; }"
    "QLabel#dkpLogTitle { color:#6878a0; font-size:11px; padding:6px 8px 2px; }"
    "QPlainTextEdit#dkpLogView { background:#0a0c10; color:#b8c8e0;"
    "  border:none; font-family:'Courier New',monospace; font-size:11px;"
    "  padding:4px 6px; selection-background-color:#2a3a5e; }"
)
_DKP_DIR_LABELS = {
    "LeftToRight": "слева→направо",
    "RightToLeft": "справа→налево",
}

# ── Camera controls ─────────────────────────────────────────────────────
# Available camera modes (also the labels shown in the toolbar dropdown).
# Internal IDs are English; display labels are Russian.
_CAM_MODE_TURNTABLE = "turntable"   # default — orbit around center
_CAM_MODE_TOP       = "top"         # locked top-down (elevation=90°)
_CAM_MODE_FLY       = "fly"         # vispy FlyCamera (WASD/QE inside the canvas)
_CAM_MODE_FOLLOW    = "follow"      # turntable whose center tracks the lead wagon

_CAM_MODE_LABELS: tuple[tuple[str, str], ...] = (
    (_CAM_MODE_TURNTABLE, "Орбита"),
    (_CAM_MODE_TOP,       "Сверху"),
    (_CAM_MODE_FLY,       "Свободная"),
    (_CAM_MODE_FOLLOW,    "Следить"),
)

# Default turntable angles used by Сброс / first frame.
_CAM_DEFAULT_FOV       = 40.0
_CAM_DEFAULT_ELEVATION = 28.0
_CAM_DEFAULT_AZIMUTH   = -60.0

# Keyboard step sizes (applied per key press in turntable / top modes).
_CAM_PAN_FRACTION  = 0.07   # fraction of camera distance per pan key press
_CAM_ORBIT_DEG     = 6.0    # azimuth/elevation degrees per orbit key press
_CAM_ZOOM_FACTOR   = 1.18   # multiplicative zoom step (>1 = zoom in)

_LOG = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  [5] OBJ loader + per-wagon mesh helpers
# ─────────────────────────────────────────────────────────────────────────────

# Per-process cache: absolute_path → (vertices Nx3 float32, faces Mx3 uint32)
# Populated lazily on first request; entries persist until the process exits.
_OBJ_CACHE: Dict[str, Optional[Tuple[np.ndarray, np.ndarray]]] = {}

# Optional trimesh — preferred when available because it handles a wider
# range of OBJ dialects (quads, negative indices, groups, materials).
try:
    import trimesh as _trimesh
    _HAS_TRIMESH = True
except Exception:
    _trimesh = None
    _HAS_TRIMESH = False


def _load_obj_mesh(path: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Load *path* and return (vertices, faces) or None on failure.

    Vertices are float32, shape (N, 3).  Faces are uint32, shape (M, 3) —
    polygons are triangulated by fan from the first vertex of the face.

    The result is cached so that repeated calls (one per wagon) are cheap.
    Failures are cached as None so the warning is logged only once per path.
    """
    if not path:
        return None

    abs_path = os.path.abspath(path)
    if abs_path in _OBJ_CACHE:
        return _OBJ_CACHE[abs_path]

    if not os.path.isfile(abs_path):
        _LOG.warning("OBJ file not found, falling back to Box: %s", abs_path)
        _OBJ_CACHE[abs_path] = None
        return None

    # ── Preferred path: trimesh ────────────────────────────────────────
    if _HAS_TRIMESH:
        try:
            mesh = _trimesh.load(abs_path, force="mesh", process=False)
            if (mesh is not None
                    and hasattr(mesh, "vertices")
                    and hasattr(mesh, "faces")
                    and len(mesh.vertices) > 0
                    and len(mesh.faces) > 0):
                verts = np.asarray(mesh.vertices, dtype=np.float32)
                faces = np.asarray(mesh.faces, dtype=np.uint32)
                _OBJ_CACHE[abs_path] = (verts, faces)
                return _OBJ_CACHE[abs_path]
        except Exception as exc:
            _LOG.warning(
                "trimesh failed to load %s (%s); falling back to built-in parser.",
                abs_path, exc,
            )

    # ── Fallback: built-in minimal OBJ parser ──────────────────────────
    try:
        result = _parse_obj_simple(abs_path)
    except Exception as exc:
        _LOG.warning("Failed to parse OBJ %s: %s", abs_path, exc)
        result = None

    _OBJ_CACHE[abs_path] = result
    return result


def _parse_obj_simple(path: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Minimal pure-Python OBJ parser.

    Handles:
      • ``v x y z``    — vertex positions (extra components ignored).
      • ``f a b c …``  — face entries; tokens may be ``v``, ``v/vt``,
        ``v/vt/vn``, or ``v//vn``; only the vertex index is used.
      • Negative indices (OBJ spec): -1 = last vertex defined so far.
      • Polygon faces with > 3 vertices are triangulated as a fan from
        the first vertex.

    Ignores everything else (normals, texcoords, groups, materials, smoothing).
    Returns (vertices, faces) or None if the file contains no usable geometry.
    """
    verts: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int]] = []

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            head = parts[0]

            if head == "v" and len(parts) >= 4:
                try:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                except ValueError:
                    continue

            elif head == "f" and len(parts) >= 4:
                # Resolve every token to a 0-based vertex index.
                idx: List[int] = []
                for tok in parts[1:]:
                    first = tok.split("/", 1)[0]
                    if not first:
                        continue
                    try:
                        i = int(first)
                    except ValueError:
                        continue
                    if i > 0:
                        idx.append(i - 1)        # OBJ is 1-based
                    elif i < 0:
                        idx.append(len(verts) + i)  # negative = from end
                    # i == 0 is invalid; skip silently

                # Triangulate as a fan from the first vertex.
                if len(idx) >= 3:
                    for k in range(1, len(idx) - 1):
                        faces.append((idx[0], idx[k], idx[k + 1]))

    if not verts or not faces:
        return None

    vert_arr = np.asarray(verts, dtype=np.float32)
    face_arr = np.asarray(faces, dtype=np.uint32)

    # Defensive: drop face entries that reference out-of-range indices.
    n = len(vert_arr)
    valid = (face_arr >= 0).all(axis=1) & (face_arr < n).all(axis=1)
    face_arr = face_arr[valid]
    if len(face_arr) == 0:
        return None

    return vert_arr, face_arr


def _orient_and_scale_obj(
    verts: np.ndarray,
    target_length_mm: float,
) -> np.ndarray:
    """Reorient + scale + ground a wagon mesh for the scene's coordinate system.

    The scene uses **world X = along the track**, **world Z = up**.  An OBJ
    file has no canonical axis convention, so we detect it from the
    bounding-box extents:

      • the LONGEST  axis → mapped to X (wagon length, along track)
      • the SHORTEST axis → mapped to Y (wagon width, across track)
      • the MEDIUM   axis → mapped to Z (wagon height, vertical)

    Empirically this orientation matches typical rail-car OBJ exports:
    the barrel/body's longest dimension lies along the track, the thin
    profile faces sideways across the gauge, and the taller cross-axis
    (with running boards, brake gear, ladders) points up.

    (An earlier version mapped medium → Y / shortest → Z, but for the
    cistern asset that left the wagon rolled 90° around its own axis
    with the underframe showing on top.  This convention puts the
    underframe at the bottom and the dome on top.)

    After remapping, the mesh is:
      • uniformly scaled so its new X-extent equals *target_length_mm*
        (Y, Z scale by the same factor so proportions are preserved),
      • centered on origin in X and Y,
      • shifted UP so its lowest point sits at z = 0 (wagon base on rails).

    The caller then only needs to translate by (x_world, y_world, z_rail).
    """
    if verts.size == 0:
        return verts

    bb_min = verts.min(axis=0)
    bb_max = verts.max(axis=0)
    extents = bb_max - bb_min

    # Order axes by extent: ascending → [shortest, medium, longest].
    order = list(np.argsort(extents))
    longest_ax  = order[2]
    medium_ax   = order[1]
    shortest_ax = order[0]

    # Permutation: longest → X (length), shortest → Y (width), medium → Z (height).
    perm = [longest_ax, shortest_ax, medium_ax]
    permuted = verts[:, perm].astype(np.float32)

    # Recompute bbox in the permuted frame.
    pmin = permuted.min(axis=0)
    pmax = permuted.max(axis=0)
    pext = pmax - pmin

    # Uniform scale by the new X extent so wagon length matches the slot.
    new_length = float(pext[0])
    if new_length > 1e-6 and target_length_mm > 0:
        scale = target_length_mm / new_length
        permuted = permuted * scale
        pmin = pmin * scale
        pmax = pmax * scale
        pext = pext * scale

    # Center on X and Y, ground on Z (lowest point at z = 0).
    cx = (pmin[0] + pmax[0]) * 0.5
    cy = (pmin[1] + pmax[1]) * 0.5
    z_floor = pmin[2]
    permuted[:, 0] -= cx
    permuted[:, 1] -= cy
    permuted[:, 2] -= z_floor

    return permuted.astype(np.float32)


# ─────────────────────────────────────────────────────────────────────────────
#  Path geometry helper
# ─────────────────────────────────────────────────────────────────────────────

class _PathGeom:
    """Cached geometry for one straight track segment."""

    def __init__(self, d: dict) -> None:
        self.track_id: str = str(d.get("track_id", ""))
        self.name:     str = str(d.get("name", ""))
        self.p1 = np.array(
            [float(d.get("x1", 0.0)), float(d.get("y1", 0.0)), float(d.get("z1", 0.0))],
            dtype=np.float64,
        )
        self.p2 = np.array(
            [float(d.get("x2", 0.0)), float(d.get("y2", 0.0)), float(d.get("z2", 0.0))],
            dtype=np.float64,
        )
        delta          = self.p2 - self.p1
        self.length    = float(np.linalg.norm(delta))
        self.unit_vec  = (delta / self.length) if self.length > 0.0 else np.array([1., 0., 0.])
        self.perp_vec  = np.array([-self.unit_vec[1], self.unit_vec[0], 0.0])
        self.up_vec    = np.array([0.0, 0.0, 1.0])
        self.rotation_deg = math.degrees(math.atan2(self.unit_vec[1], self.unit_vec[0]))

    def s_to_xyz(self, s_mm: float) -> np.ndarray:
        return self.p1 + self.unit_vec * s_mm

    def s_to_xyz_off(self, s_mm: float, lateral: float, vertical: float = 0.0) -> np.ndarray:
        return (
            self.p1
            + self.unit_vec * s_mm
            + self.perp_vec * lateral
            + self.up_vec   * vertical
        )

    @property
    def midpoint(self) -> np.ndarray:
        return (self.p1 + self.p2) * 0.5

    # [2] helper: Z coordinate of the rail surface at position s_mm
    def rail_z(self, s_mm: float) -> float:
        """Z-height of the rail plane at s_mm (interpolated along segment)."""
        t = s_mm / self.length if self.length > 0 else 0.0
        return float(self.p1[2] + t * (self.p2[2] - self.p1[2]))


# ─────────────────────────────────────────────────────────────────────────────
#  DKP visual bundle  (pole + diamond head + halo + counter)
# ─────────────────────────────────────────────────────────────────────────────

class _DKPVisual:
    """Visual bundle for one DKP sensor.

    Parts:
      shaft  — vertical Line from ground to pole top
      head   — diamond (closed Line strip); Fox=cyan, Mongoose=orange
      halo   — Markers disc; grows white on flash
      count  — Text visual showing cumulative axis count  [NEW]
    """

    def __init__(self, geom: _PathGeom, dkp: DKPConfig, scene: object) -> None:
        self._idle_color: tuple = (
            _DKP_FOX_IDLE if dkp.sensor_type == "Fox" else _DKP_MON_IDLE
        )
        self._count: int = 0   # [3] cumulative axis passages

        lateral = -(RAIL_OFFSET + GAUGE_MM * 0.28)
        base    = geom.s_to_xyz_off(dkp.s_mm, lateral, 0.0).astype(np.float32)
        top     = geom.s_to_xyz_off(dkp.s_mm, lateral, DKP_POLE_HEIGHT).astype(np.float32)
        head_c  = top.copy()

        # Shaft
        self._shaft = visuals.Line(
            pos=np.array([base, top], dtype=np.float32),
            color=_DKP_POLE, width=2, method="gl", parent=scene,
        )

        # Diamond head
        hs = DKP_HEAD_HALF
        u  = geom.unit_vec.astype(np.float32)
        pts_diamond = np.array([
            head_c + u * hs,
            head_c + np.array([0., 0.,  hs], np.float32),
            head_c - u * hs,
            head_c + np.array([0., 0., -hs], np.float32),
            head_c + u * hs,
        ], dtype=np.float32)
        self._head = visuals.Line(
            pos=pts_diamond, color=self._idle_color,
            width=3, method="gl", connect="strip", parent=scene,
        )

        # Halo
        self._halo = visuals.Markers(parent=scene)
        self._halo_pos = head_c.reshape(1, 3)
        self._set_halo_idle()

        # ID + type label (static)
        lbl = dkp.sensor_id
        if dkp.sensor_type:
            lbl += f" [{dkp.sensor_type}]"
        if not dkp.enabled:
            lbl += "  ○"
        id_label_pos = head_c + np.array([0., 0., hs * 1.5], np.float32)
        visuals.Text(
            text=lbl, pos=id_label_pos,
            color=_DKP_LABEL, font_size=7,
            anchor_x="left", anchor_y="bottom", parent=scene,
        )

        # [3] Axis counter — dynamic Text, stored for update
        self._count_pos = (head_c + np.array([0., 0., hs * 3.0], np.float32))
        self._count_text = visuals.Text(
            text="0 осей",
            pos=self._count_pos,
            color=_DKP_COUNT,
            font_size=8,
            bold=True,
            anchor_x="left",
            anchor_y="bottom",
            parent=scene,
        )

    # ── internal helpers ───────────────────────────────────────────────

    def _set_halo_idle(self) -> None:
        c = self._idle_color
        self._halo.set_data(
            pos=self._halo_pos, size=20,
            face_color=(*c[:3], 0.20),
            edge_color=c, edge_width=1.8,
        )

    def _set_halo_flash(self) -> None:
        self._halo.set_data(
            pos=self._halo_pos, size=32,
            face_color=(1., 1., 1., 0.40),
            edge_color=_DKP_FLASH, edge_width=2.5,
        )

    # ── public API ─────────────────────────────────────────────────────

    def flash(self) -> None:
        """Trigger: flash white and increment axis counter."""
        self._head.set_data(color=_DKP_FLASH)
        self._set_halo_flash()
        # [3] increment and refresh counter text
        self._count += 1
        self._count_text.text = f"{self._count} {'ось' if self._count == 1 else 'осей'}"

    def reset_flash(self) -> None:
        """Restore idle colours (counter is NOT reset here)."""
        self._head.set_data(color=self._idle_color)
        self._set_halo_idle()

    def reset_counter(self) -> None:
        """[3] Reset axis count to zero — called on engine stop."""
        self._count = 0
        self._count_text.text = "0 осей"


# ─────────────────────────────────────────────────────────────────────────────
#  Main window
# ─────────────────────────────────────────────────────────────────────────────

class SceneWindow(QMainWindow):
    """Standalone 3D visualisation window for one simulation run."""

    def __init__(
        self,
        engine:     SimulationEngine,
        sim_config: SimConfig,
        path_data:  List[dict],
        parent:     Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._config = sim_config
        self._steps  = sim_config.steps
        self._paused = False

        self._paths: Dict[str, _PathGeom] = {}
        for d in path_data:
            g = _PathGeom(d)
            self._paths[g.track_id] = g

        self._wagons: List[WagonDef]           = engine._wagons
        self._wagon_front_offsets: List[float] = engine._wagon_front_offsets

        self.setWindowTitle("Хамелеон — 3D-сцена")
        self.resize(1280, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._build_toolbar()

        content = QWidget()
        content_row = QHBoxLayout(content)
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(0)

        self._canvas = SceneCanvas(keys="interactive", bgcolor=_BG, show=False)
        cw = self._canvas.native
        cw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Let the canvas accept keyboard focus when clicked — this is
        # what lets WASD/arrow-key camera control reach our window-level
        # keyPressEvent.  Without StrongFocus, Qt's tab-only focus would
        # leave keystrokes with whichever toolbar widget has the cursor.
        cw.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        content_row.addWidget(cw, stretch=1)

        self._wagon_ids_by_index = {i: w.wagon_id for i, w in enumerate(self._wagons)}
        self._dkp_log_view = self._build_dkp_log_panel()
        content_row.addWidget(self._dkp_log_view)

        root.addWidget(content, stretch=1)

        self._view = self._canvas.central_widget.add_view()
        # Camera mode is mutable — start in turntable. The current mode
        # string (one of _CAM_MODE_*) drives _on_tick's follow logic and
        # the keyboard-step dispatcher.
        self._cam_mode: str = _CAM_MODE_TURNTABLE
        self._apply_camera_mode(_CAM_MODE_TURNTABLE)

        # Runtime-updated scene objects
        self._dkp_visuals:   Dict[str, _DKPVisual] = {}
        # Each entry is either a visuals.Box (fallback) or a visuals.Mesh (OBJ).
        self._wagon_visuals: List[object]            = []
        # Cached MatrixTransform per wagon — reset+reuse each tick instead of
        # allocating a new object per wagon per tick.
        self._wagon_transforms: List                 = []
        # Per-wagon vertical offset added to z_rail to position the visual:
        #   Box → wagon_h/2 (centre to base);  Mesh → 0 (base already at z=0).
        self._wagon_z_offsets: List[float]           = []
        self._axle_visuals:  List[visuals.Markers]   = []
        self._coupler_line:  Optional[visuals.Line]  = None   # [4]
        # Precomputed numpy arrays for vectorised per-tick computation.
        self._wagon_front_offsets_np: np.ndarray = np.empty(0, dtype=np.float64)
        self._wagon_lengths_np:       np.ndarray = np.empty(0, dtype=np.float64)
        self._wagon_heights_np:       np.ndarray = np.empty(0, dtype=np.float64)
        self._wagon_z_offsets_np:     np.ndarray = np.empty(0, dtype=np.float64)

        # Build static scene
        self._init_ground_grid()
        self._init_tracks()
        self._init_dkp_markers()
        self._init_wagon_visuals()

        self._view.camera.set_range()

        engine.tick_updated.connect(self._on_tick)
        engine.dkp_triggered.connect(self._on_dkp_triggered)
        engine.step_changed.connect(self._on_step_changed)
        engine.sim_finished.connect(self._on_sim_finished)

        # ── DKP event logging ──────────────────────────────────────────
        # One run, three files (Fox / Mongoose / All), inside a fresh
        # timestamped directory under <project>/logs/.  Built from the
        # engine's expanded wagon list so the log shows human ids
        # instead of opaque indices.
        try:
            self._dkp_logger: Optional[DKPEventLogger] = DKPEventLogger(
                self._wagon_ids_by_index,
            )
            self._dkp_log_dir = self._dkp_logger.open()
            _LOG.info("DKP events will be logged to %s", self._dkp_log_dir)
        except OSError as exc:
            # Disk full / permissions / read-only mount — never let logging
            # break the simulation.  Just warn and continue without a logger.
            _LOG.warning("Could not open DKP log files: %s", exc)
            self._dkp_logger = None
            self._dkp_log_dir = None

        self._set_state_idle()

    # ================================================================== #
    #  Toolbar                                                            #
    # ================================================================== #

    def _build_dkp_log_panel(self) -> QFrame:
        """Right-side panel showing DKP trigger events in real time."""
        panel = QFrame()
        panel.setObjectName("dkpLogPanel")
        panel.setFixedWidth(_DKP_LOG_WIDTH)
        panel.setStyleSheet(_DKP_LOG_PANEL_STYLE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("События ДКП")
        title.setObjectName("dkpLogTitle")
        layout.addWidget(title)

        view = QPlainTextEdit()
        view.setObjectName("dkpLogView")
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setPlaceholderText("Срабатывания ДКП появятся здесь во время прогона…")
        layout.addWidget(view, stretch=1)

        self._dkp_log_text = view
        return panel

    def _format_dkp_log_line(self, event: DKPEvent) -> str:
        """One-line summary for the live log panel."""
        wagon_id = self._wagon_ids_by_index.get(
            event.wagon_index, f"#{event.wagon_index}",
        )
        dir_lbl = _DKP_DIR_LABELS.get(event.direction, event.direction)
        stype = f" [{event.sensor_type}]" if event.sensor_type else ""
        return (
            f"{_fmt_time(event.t_ms)}  {event.sensor_id}{stype}  "
            f"{wagon_id} ось {event.axle_index + 1}  {dir_lbl}  "
            f"{event.v_mms:.0f} мм/с"
        )

    def _append_dkp_log(self, event: DKPEvent) -> None:
        view = self._dkp_log_text
        view.appendPlainText(self._format_dkp_log_line(event))
        doc = view.document()
        if doc.blockCount() > _DKP_LOG_MAX_LINES:
            cursor = view.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            cursor.movePosition(
                cursor.MoveOperation.Down,
                cursor.MoveMode.KeepAnchor,
                doc.blockCount() - _DKP_LOG_MAX_LINES,
            )
            cursor.removeSelectedText()
        bar = view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _clear_dkp_log(self) -> None:
        self._dkp_log_text.clear()

    def _build_toolbar(self) -> None:
        tb: QToolBar = self.addToolBar("Управление")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setStyleSheet(
            "QToolBar { background:#101318; border-bottom:1px solid #252930; spacing:4px; }"
            "QPushButton { background:#1a1f28; color:#c8d4e8;"
            "  border:1px solid #353d4d; border-radius:4px;"
            "  padding:3px 14px; font-size:12px; }"
            "QPushButton:hover { background:#242d3e; border-color:#5070a0; }"
            "QPushButton:disabled { color:#3a3f4a; border-color:#1e2228; }"
            "QLabel { color:#6878a0; font-family:'Courier New',monospace;"
            "  font-size:12px; padding:0 8px; }"
            "QComboBox { background:#1a1f28; color:#c8d4e8;"
            "  border:1px solid #353d4d; border-radius:4px;"
            "  padding:2px 6px; font-size:12px; min-width:52px; }"
            "QComboBox:hover { border-color:#5070a0; }"
            "QComboBox:disabled { color:#3a3f4a; border-color:#1e2228; }"
            "QComboBox::drop-down { border:none; width:18px; }"
            "QComboBox QAbstractItemView { background:#1a1f28; color:#c8d4e8;"
            "  selection-background-color:#2a3a5e; border:1px solid #353d4d; }"
        )

        self._btn_start = QPushButton("▶  Пуск")
        self._btn_pause = QPushButton("⏸  Пауза")
        self._btn_stop  = QPushButton("⏹  Стоп")
        for btn in (self._btn_start, self._btn_pause, self._btn_stop):
            btn.setFixedHeight(28)
            btn.setMinimumWidth(100)
            tb.addWidget(btn)

        tb.addSeparator()

        # ── Speed multiplier ────────────────────────────────────────────
        tb.addWidget(QLabel("Скорость:"))
        self._speed_mult_combo = QComboBox()
        for lbl, val in [
            ("×0.25", 0.25), ("×0.5", 0.5), ("×1", 1.0),
            ("×2", 2.0), ("×3", 3.0), ("×5", 5.0), ("×10", 10.0),
        ]:
            self._speed_mult_combo.addItem(lbl, val)
        self._speed_mult_combo.setCurrentIndex(2)   # ×1 default
        self._speed_mult_combo.setFixedHeight(28)
        self._speed_mult_combo.currentIndexChanged.connect(
            lambda idx: self._cmd_set_speed(self._speed_mult_combo.itemData(idx))
        )
        tb.addWidget(self._speed_mult_combo)

        tb.addSeparator()

        # ── Fast-forward ────────────────────────────────────────────────
        tb.addWidget(QLabel("Перемотка:"))
        self._ff_amount_combo = QComboBox()
        for lbl, secs in [("5 с", 5), ("10 с", 10), ("30 с", 30),
                           ("60 с", 60), ("5 мин", 300)]:
            self._ff_amount_combo.addItem(lbl, secs)
        self._ff_amount_combo.setCurrentIndex(1)   # 10 s default
        self._ff_amount_combo.setFixedHeight(28)
        tb.addWidget(self._ff_amount_combo)

        self._btn_ff = QPushButton("⏩")
        self._btn_ff.setFixedHeight(28)
        self._btn_ff.setMinimumWidth(44)
        self._btn_ff.clicked.connect(
            lambda: self._cmd_fast_forward(self._ff_amount_combo.currentData())
        )
        tb.addWidget(self._btn_ff)

        tb.addSeparator()

        self._step_label  = QLabel("Шаг: —")
        self._speed_label = QLabel("0 мм/с  ·  0.00 км/ч")
        self._clock_label = QLabel("00:00.000")
        for lbl in (self._step_label, self._speed_label, self._clock_label):
            tb.addWidget(lbl)

        self._btn_start.clicked.connect(self._cmd_start)
        self._btn_pause.clicked.connect(self._cmd_pause)
        self._btn_stop.clicked.connect(self._cmd_stop)

        # ── Camera controls ─────────────────────────────────────────────
        tb.addSeparator()

        cam_label = QLabel("Камера:")
        tb.addWidget(cam_label)

        self._cam_combo = QComboBox()
        for mode_id, mode_label in _CAM_MODE_LABELS:
            self._cam_combo.addItem(mode_label, mode_id)
        self._cam_combo.setCurrentIndex(0)
        # Lambda passes the user-selected mode_id (stored as itemData).
        self._cam_combo.currentIndexChanged.connect(
            lambda idx: self._apply_camera_mode(self._cam_combo.itemData(idx))
        )
        tb.addWidget(self._cam_combo)

        # Preset-view buttons.  Each button just applies a fixed pose
        # to the current camera (or switches to turntable if the user
        # is in fly mode, where elevation/azimuth aren't meaningful).
        self._btn_view_iso  = QPushButton("Изометрия")
        self._btn_view_top  = QPushButton("Сверху")
        self._btn_view_side = QPushButton("Сбоку")
        self._btn_view_reset = QPushButton("Сброс")
        for btn, preset in (
            (self._btn_view_iso,   "iso"),
            (self._btn_view_top,   "top"),
            (self._btn_view_side,  "side"),
            (self._btn_view_reset, "reset"),
        ):
            btn.setFixedHeight(28)
            btn.setMinimumWidth(78)
            btn.clicked.connect(lambda _checked=False, p=preset: self._apply_preset_view(p))
            tb.addWidget(btn)

    # ================================================================== #
    #  Camera control                                                     #
    # ================================================================== #
    #
    # Modes supported:
    #   turntable — orbit around a fixed center (VisPy default).
    #   top       — like turntable but elevation locked to 90° so the
    #               user can only pan and zoom.  Best for layout views.
    #   fly       — VisPy FlyCamera; WASD moves the eye through the
    #               scene.  Mouse capture works inside the canvas.
    #   follow    — turntable whose center is updated each tick to the
    #               lead wagon's world position.  Useful for long trains.
    #
    # Keyboard works in turntable / top / follow modes.  In fly mode we
    # leave navigation to VisPy's own handler (the canvas takes focus).
    #
    # Keyboard map (when the canvas has the application's attention):
    #   W / S or ↑ / ↓ — pan forward / back along the camera's azimuth
    #   A / D or ← / → — pan left / right
    #   Q / E          — orbit left / right (azimuth)
    #   R / F          — orbit up / down (elevation)
    #   + / -  (or Z/X) — zoom in / out
    #   Space          — reset to default isometric view
    #   1 / 2 / 3 / 4  — preset views: isometric / top / side / reset

    def _apply_camera_mode(self, mode: str) -> None:
        """Switch the active camera.  Idempotent; falls back to turntable
        if the requested mode is unknown.
        """
        if mode not in {_CAM_MODE_TURNTABLE, _CAM_MODE_TOP,
                        _CAM_MODE_FLY, _CAM_MODE_FOLLOW}:
            mode = _CAM_MODE_TURNTABLE

        self._cam_mode = mode

        if mode == _CAM_MODE_FLY:
            # FlyCamera ignores fov-style parameters; just hand it the view.
            try:
                from vispy.scene.cameras import FlyCamera
                self._view.camera = FlyCamera()
            except Exception as exc:
                _LOG.warning("FlyCamera unavailable (%s); using turntable.", exc)
                self._view.camera = "turntable"
                self._cam_mode = _CAM_MODE_TURNTABLE
        else:
            self._view.camera = "turntable"
            cam = self._view.camera
            cam.fov = _CAM_DEFAULT_FOV
            if mode == _CAM_MODE_TOP:
                cam.elevation = 90.0
                cam.azimuth   = 0.0
            elif mode in (_CAM_MODE_TURNTABLE, _CAM_MODE_FOLLOW):
                cam.elevation = _CAM_DEFAULT_ELEVATION
                cam.azimuth   = _CAM_DEFAULT_AZIMUTH

            # When switching mode mid-run, frame the scene afresh so the
            # user sees something sensible (instead of an arbitrary
            # leftover center from the previous camera).
            try:
                cam.set_range()
            except Exception:
                pass

        # Keep the toolbar combo in sync if the change came from a hotkey
        # or from a code path other than the combo itself.
        if hasattr(self, "_cam_combo"):
            idx = next(
                (i for i, (mid, _) in enumerate(_CAM_MODE_LABELS) if mid == self._cam_mode),
                0,
            )
            if self._cam_combo.currentIndex() != idx:
                self._cam_combo.blockSignals(True)
                self._cam_combo.setCurrentIndex(idx)
                self._cam_combo.blockSignals(False)

        self._canvas.update()

    def _apply_preset_view(self, preset: str) -> None:
        """Snap the camera to one of the named poses.

        Presets imply turntable-style camera, so if we're in fly mode
        we drop back to turntable first.  In follow mode we keep the
        center-tracking behaviour but reset angles.
        """
        if self._cam_mode == _CAM_MODE_FLY:
            self._apply_camera_mode(_CAM_MODE_TURNTABLE)

        cam = self._view.camera
        if preset == "iso":
            cam.elevation = _CAM_DEFAULT_ELEVATION
            cam.azimuth   = _CAM_DEFAULT_AZIMUTH
        elif preset == "top":
            cam.elevation = 90.0
            cam.azimuth   = 0.0
        elif preset == "side":
            cam.elevation = 0.0
            cam.azimuth   = -90.0
        elif preset == "reset":
            cam.fov       = _CAM_DEFAULT_FOV
            cam.elevation = _CAM_DEFAULT_ELEVATION
            cam.azimuth   = _CAM_DEFAULT_AZIMUTH
            try:
                cam.set_range()
            except Exception:
                pass
        self._canvas.update()

    def _camera_pan(self, dx_frac: float, dy_frac: float) -> None:
        """Pan the camera center on the ground plane.

        *dx_frac* / *dy_frac* are fractions of the camera's current
        distance, so a single key press feels equally responsive at any
        zoom level.  The pan is performed in the *camera's* X/Y, which
        for turntable is the world X/Y rotated by the azimuth.
        """
        cam = self._view.camera
        if not hasattr(cam, "center"):
            return

        # Distance to scene: TurntableCamera stores it as .distance.
        # Some camera variants name it differently — fall back to 1.0.
        dist = float(getattr(cam, "distance", 1.0) or 1.0)
        step = dist * _CAM_PAN_FRACTION

        # Build an azimuth-aware basis so "forward" tracks where the
        # user is looking, not world +Y.
        az = math.radians(float(getattr(cam, "azimuth", 0.0)))
        # +Y in screen → forward into the scene; +X in screen → right.
        fx, fy = -math.sin(az), math.cos(az)    # forward unit (ground)
        rx, ry =  math.cos(az), math.sin(az)    # right unit   (ground)

        cx, cy, cz = cam.center
        cam.center = (
            cx + rx * step * dx_frac + fx * step * dy_frac,
            cy + ry * step * dx_frac + fy * step * dy_frac,
            cz,
        )
        self._canvas.update()

    def _camera_orbit(self, d_az: float, d_el: float) -> None:
        """Add deltas to azimuth and elevation, clamping elevation."""
        cam = self._view.camera
        if hasattr(cam, "azimuth"):
            cam.azimuth = float(cam.azimuth) + d_az
        if hasattr(cam, "elevation"):
            new_el = float(cam.elevation) + d_el
            # Clamp slightly inside ±90° to avoid the gimbal flip.
            cam.elevation = max(-89.0, min(89.0, new_el))
        self._canvas.update()

    def _camera_zoom(self, factor: float) -> None:
        """Multiplicative zoom — factor>1 zooms in, factor<1 zooms out.

        Works by scaling .distance on turntable; FlyCamera ignores this
        (it has its own movement model).
        """
        cam = self._view.camera
        if hasattr(cam, "distance") and cam.distance is not None:
            try:
                cam.distance = float(cam.distance) / factor
            except (TypeError, ValueError):
                pass
        elif hasattr(cam, "scale_factor"):
            try:
                cam.scale_factor = float(cam.scale_factor) / factor
            except (TypeError, ValueError):
                pass
        self._canvas.update()

    def keyPressEvent(self, event) -> None:
        """Window-level hotkeys for camera control.

        We only consume keys that map to camera actions; everything else
        is forwarded to Qt so existing shortcuts (Escape on dialogs, etc.)
        still work.  Fly mode skips this handler entirely so the canvas
        can run its own navigation.
        """
        if self._cam_mode == _CAM_MODE_FLY:
            super().keyPressEvent(event)
            return

        key = event.key()
        # WASD / arrows → pan.  dx_frac is +right, dy_frac is +forward.
        if key in (Qt.Key.Key_W, Qt.Key.Key_Up):
            self._camera_pan(0.0, +1.0)
        elif key in (Qt.Key.Key_S, Qt.Key.Key_Down):
            self._camera_pan(0.0, -1.0)
        elif key in (Qt.Key.Key_A, Qt.Key.Key_Left):
            self._camera_pan(-1.0, 0.0)
        elif key in (Qt.Key.Key_D, Qt.Key.Key_Right):
            self._camera_pan(+1.0, 0.0)
        # Q/E → orbit azimuth; R/F → orbit elevation
        elif key == Qt.Key.Key_Q:
            self._camera_orbit(-_CAM_ORBIT_DEG, 0.0)
        elif key == Qt.Key.Key_E:
            self._camera_orbit(+_CAM_ORBIT_DEG, 0.0)
        elif key == Qt.Key.Key_R:
            self._camera_orbit(0.0, +_CAM_ORBIT_DEG)
        elif key == Qt.Key.Key_F:
            self._camera_orbit(0.0, -_CAM_ORBIT_DEG)
        # Zoom: + / =, - / _, Z, X
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Z):
            self._camera_zoom(_CAM_ZOOM_FACTOR)
        elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_X):
            self._camera_zoom(1.0 / _CAM_ZOOM_FACTOR)
        elif key == Qt.Key.Key_Space:
            self._apply_preset_view("reset")
        elif key == Qt.Key.Key_1:
            self._apply_preset_view("iso")
        elif key == Qt.Key.Key_2:
            self._apply_preset_view("top")
        elif key == Qt.Key.Key_3:
            self._apply_preset_view("side")
        elif key == Qt.Key.Key_4:
            self._apply_preset_view("reset")
        else:
            super().keyPressEvent(event)
            return

        event.accept()

    # ================================================================== #
    #  Scene initialisation                                               #
    # ================================================================== #

    def _init_ground_grid(self) -> None:
        all_pts = [p for g in self._paths.values() for p in (g.p1, g.p2)]
        if not all_pts:
            return

        pts  = np.array(all_pts)
        span = max(
            pts[:, 0].max() - pts[:, 0].min(),
            pts[:, 1].max() - pts[:, 1].min(),
            1.0,
        )
        pad   = span * 0.30
        min_x, max_x = pts[:, 0].min() - pad, pts[:, 0].max() + pad
        min_y, max_y = pts[:, 1].min() - pad, pts[:, 1].max() + pad
        step = max(span / 8.0, 1.0)

        lines, conn = [], []
        for coord, lo, hi, ax in (
            (np.arange(min_x, max_x + step * .01, step), min_y, max_y, "x"),
            (np.arange(min_y, max_y + step * .01, step), min_x, max_x, "y"),
        ):
            for v in coord:
                idx = len(lines)
                if ax == "x":
                    lines += [[v, lo, 0.], [v, hi, 0.]]
                else:
                    lines += [[lo, v, 0.], [hi, v, 0.]]
                conn.append([idx, idx + 1])

        if lines:
            visuals.Line(
                pos=np.array(lines, dtype=np.float32),
                color=(*_GRID[:3], 0.45), width=1, method="gl",
                connect=np.array(conn, dtype=np.uint32),
                parent=self._view.scene,
            )

    def _init_tracks(self) -> None:
        for geom in self._paths.values():
            if geom.length < 1.0:
                continue
            self._draw_rails(geom)
            self._draw_sleepers(geom)
            self._draw_track_label(geom)

    def _draw_rails(self, geom: _PathGeom) -> None:
        for side in (+1.0, -1.0):
            r1 = geom.s_to_xyz_off(0.0,         side * RAIL_OFFSET).astype(np.float32)
            r2 = geom.s_to_xyz_off(geom.length, side * RAIL_OFFSET).astype(np.float32)
            visuals.Line(
                pos=np.array([r1, r2], dtype=np.float32),
                color=_RAIL, width=3, method="gl", parent=self._view.scene,
            )

    def _draw_sleepers(self, geom: _PathGeom) -> None:
        n = max(2, int(geom.length / SLEEPER_STEP_MM))
        pts, conn = [], []
        for i in range(n + 1):
            s   = min(i * SLEEPER_STEP_MM, geom.length)
            lft = geom.s_to_xyz_off(s, -(RAIL_OFFSET + SLEEPER_OVERHANG)).astype(np.float32)
            rgt = geom.s_to_xyz_off(s,  (RAIL_OFFSET + SLEEPER_OVERHANG)).astype(np.float32)
            idx = len(pts)
            pts += [lft, rgt]
            conn.append([idx, idx + 1])
        visuals.Line(
            pos=np.array(pts, dtype=np.float32),
            color=(*_SLEEPER[:3], 0.70), width=2, method="gl",
            connect=np.array(conn, dtype=np.uint32),
            parent=self._view.scene,
        )

    def _draw_track_label(self, geom: _PathGeom) -> None:
        lbl = geom.track_id + (f"  {geom.name}" if geom.name else "")
        pos = geom.s_to_xyz_off(geom.length * 0.5, 0.0, DKP_POLE_HEIGHT * 0.55)
        visuals.Text(
            text=lbl, pos=pos.astype(np.float32),
            color=_TRACK_LABEL, font_size=9,
            anchor_x="center", anchor_y="bottom", parent=self._view.scene,
        )

    def _init_dkp_markers(self) -> None:
        for dkp in self._config.dkps:
            geom = self._paths.get(dkp.track_id)
            if geom is None:
                continue
            self._dkp_visuals[dkp.sensor_id] = _DKPVisual(geom, dkp, self._view.scene)

    def _init_wagon_visuals(self) -> None:
        geom = self._paths.get(self._config.train.track_id)
        if geom is None:
            return

        # Build numpy arrays from the wagon list once so _on_tick can vectorise.
        self._wagon_front_offsets_np = np.array(self._wagon_front_offsets, dtype=np.float64)
        self._wagon_lengths_np = np.array([w.length_mm for w in self._wagons], dtype=np.float64)
        self._wagon_heights_np = np.array(
            [w.height_mm if w.height_mm > 0 else w.length_mm * 0.13 for w in self._wagons],
            dtype=np.float64,
        )

        for wi, wagon in enumerate(self._wagons):
            s_front = self._config.train.s0_mm - self._wagon_front_offsets[wi]
            s_rear  = s_front - wagon.length_mm

            wagon_h = wagon.height_mm if wagon.height_mm > 0 else wagon.length_mm * 0.13
            z_rail  = geom.rail_z((s_front + s_rear) / 2.0)

            wagon_len = float(np.linalg.norm(
                geom.s_to_xyz(s_front) - geom.s_to_xyz(s_rear)
            ))
            wagon_w = GAUGE_MM * 0.88

            # [5] Build the visual (Mesh from .obj, or Box fallback) and
            #     learn its local-Z base offset.
            #       • Mesh: base is at local z=0  → z_base_offset = 0
            #       • Box : centre is at local z=0 → z_base_offset = h/2
            wagon_visual, z_base_offset = self._make_wagon_visual(
                wagon=wagon,
                wagon_len=wagon_len * (1.0 + _WAGON_VISUAL_OVERLAP),
                wagon_w=wagon_w,
                wagon_h=wagon_h,
            )
            self._wagon_z_offsets.append(z_base_offset)

            # [2] Place the visual so its base sits on the rail surface.
            z_center = z_rail + z_base_offset
            pf = geom.s_to_xyz_off(s_front, 0.0, z_center).astype(np.float32)
            pr = geom.s_to_xyz_off(s_rear,  0.0, z_center).astype(np.float32)
            center = (pf + pr) * 0.5

            t = vispy.scene.transforms.MatrixTransform()
            t.rotate(geom.rotation_deg, (0, 0, 1))
            t.translate(center.astype(np.float64))
            wagon_visual.transform = t
            self._wagon_transforms.append(t)
            self._wagon_visuals.append(wagon_visual)

            # Axle wheel markers — sit at rail level (z_rail)
            axle_pts = [
                geom.s_to_xyz_off(s_front - ax.offset_mm, 0.0, z_rail).astype(np.float32)
                for ax in wagon.axles
            ]
            if axle_pts:
                m = visuals.Markers(parent=self._view.scene)
                m.set_data(
                    pos=np.array(axle_pts, dtype=np.float32),
                    size=10, face_color=_AXLE_FACE,
                    edge_color=_AXLE_EDGE, edge_width=1.5,
                )
                self._axle_visuals.append(m)

        # Finalise z-offset array now that the loop has populated the list.
        self._wagon_z_offsets_np = np.array(self._wagon_z_offsets, dtype=np.float64)

        # [4] Coupler line — one polyline through all junction points
        self._coupler_line = visuals.Line(
            pos=self._coupler_points(self._config.train.s0_mm, geom),
            color=_COUPLER_COLOR, width=4, method="gl",
            connect="strip", parent=self._view.scene,
        )

    # ================================================================== #
    #  [5] Wagon visual factory — Mesh from .obj or Box fallback         #
    # ================================================================== #

    def _make_wagon_visual(
        self,
        wagon:     WagonDef,
        wagon_len: float,
        wagon_w:   float,
        wagon_h:   float,
    ):
        """Return (visual, z_base_offset) for one wagon.

        * If wagon.model_path points to a readable .obj file → returns a
          visuals.Mesh whose vertices have been reoriented (longest axis →
          world X), uniformly scaled (X-extent = wagon_len), centered in
          X/Y, and shifted so the base sits at local z = 0.
          z_base_offset is then **0** — the per-tick translate just adds
          z_rail and the wagon stands ON the rails.

        * Otherwise → returns the original visuals.Box of dimensions
          wagon_len × wagon_h × wagon_w, with its centre at local origin.
          z_base_offset is **wagon_h / 2** so the per-tick translate adds
          (z_rail + wagon_h/2) to put the box bottom on the rails.

        The returned visual is already parented to self._view.scene; the
        caller still needs to assign its .transform.
        """
        model_path = getattr(wagon, "model_path", "") or ""

        if model_path:
            mesh_data = _load_obj_mesh(model_path)
            if mesh_data is not None:
                verts_raw, faces = mesh_data
                verts = _orient_and_scale_obj(verts_raw, target_length_mm=wagon_len)
                try:
                    mesh = visuals.Mesh(
                        vertices=verts,
                        faces=faces,
                        color=(*_WAGON_BODY[:3], 1.0),
                        shading="smooth",
                        parent=self._view.scene,
                    )
                    # Mesh base already at local z=0 — no extra lift needed.
                    return mesh, 0.0
                except Exception as exc:
                    _LOG.warning(
                        "VisPy Mesh construction failed for %s (%s); "
                        "using Box fallback.",
                        model_path, exc,
                    )

        # Fallback — original Box rendering, centred at local origin.
        box = visuals.Box(
            width=wagon_len, height=wagon_h, depth=wagon_w,
            color=(*_WAGON_BODY[:3], 0.85), edge_color=_WAGON_EDGE,
            parent=self._view.scene,
        )
        return box, wagon_h / 2.0

    # ================================================================== #
    #  Engine signal handlers                                             #
    # ================================================================== #

    def _on_tick(self, state: SimState) -> None:
        geom = self._paths.get(self._config.train.track_id)
        if geom is None:
            return

        # [1] Boundary check — stop if train exits the track
        if self._check_boundary(state, geom):
            return   # engine already paused; skip position update

        # Group axes by wagon index once — O(M) instead of O(N×M).
        axes_by_wagon: Dict[int, list] = {}
        for ax in state.axes:
            axes_by_wagon.setdefault(ax.wagon_index, []).append(ax)

        # Vectorised wagon-centre computation ─────────────────────────────
        s_fronts = state.s_head_mm - self._wagon_front_offsets_np        # (N,)
        s_rears  = s_fronts - self._wagon_lengths_np                      # (N,)
        s_mids   = (s_fronts + s_rears) * 0.5                            # (N,)

        inv_len  = 1.0 / geom.length if geom.length > 0 else 0.0
        z_rails  = geom.p1[2] + s_mids * inv_len * (geom.p2[2] - geom.p1[2])  # (N,)
        z_centers = z_rails + self._wagon_z_offsets_np                   # (N,)

        # World centres: p1 + unit_vec * s_mid, Z replaced by z_center.
        centers = (
            geom.p1[np.newaxis, :]
            + geom.unit_vec[np.newaxis, :] * s_mids[:, np.newaxis]
        ).astype(np.float64)
        centers[:, 2] = z_centers

        rotation_deg = geom.rotation_deg

        lead_center: Optional[np.ndarray] = None

        for wi in range(len(self._wagons)):
            center = centers[wi]
            if wi == 0:
                lead_center = center.astype(np.float32)

            # Reuse the cached transform — no Python object allocation per tick.
            t = self._wagon_transforms[wi]
            t.reset()
            t.rotate(rotation_deg, (0, 0, 1))
            t.translate(center)

            if wi < len(self._axle_visuals):
                wagon_axes = axes_by_wagon.get(wi)
                if wagon_axes:
                    z_r = float(z_rails[wi])
                    axle_pts = [
                        geom.s_to_xyz_off(a.s_mm, 0.0, z_r).astype(np.float32)
                        for a in wagon_axes
                    ]
                    self._axle_visuals[wi].set_data(
                        pos=np.array(axle_pts, dtype=np.float32),
                        size=10, face_color=_AXLE_FACE,
                        edge_color=_AXLE_EDGE, edge_width=1.5,
                    )

        # [4] Update coupler line
        if self._coupler_line is not None:
            self._coupler_line.set_data(
                pos=self._coupler_points(state.s_head_mm, geom),
            )

        # Follow-mode camera tracking — slide the orbit centre to the
        # lead wagon, keeping the user's azimuth/elevation/zoom intact.
        if (self._cam_mode == _CAM_MODE_FOLLOW
                and lead_center is not None
                and hasattr(self._view.camera, "center")):
            self._view.camera.center = (
                float(lead_center[0]),
                float(lead_center[1]),
                float(lead_center[2]),
            )

        v_mms = abs(state.v_mms)
        self._speed_label.setText(f"{v_mms:.0f} мм/с  ·  {state.speed_kmh:.2f} км/ч")
        self._clock_label.setText(_fmt_time(state.t_ms))
        self._step_label.setText(f"Шаг: {state.step_index + 1}/{len(self._steps)}")
        self._canvas.update()

    def _on_dkp_triggered(self, event: DKPEvent) -> None:
        # Persist the event before any visual work — keeps logging
        # robust if the rendering code later raises.
        if self._dkp_logger is not None:
            try:
                self._dkp_logger.log_event(event)
            except OSError as exc:
                _LOG.warning("DKP log write failed: %s", exc)

        self._append_dkp_log(event)

        bundle = self._dkp_visuals.get(event.sensor_id)
        if bundle:
            bundle.flash()
            self._canvas.update()
            QTimer.singleShot(_DKP_FLASH_MS, lambda: self._reset_dkp(event.sensor_id))

    def _reset_dkp(self, sensor_id: str) -> None:
        bundle = self._dkp_visuals.get(sensor_id)
        if bundle:
            bundle.reset_flash()
            self._canvas.update()

    def _on_step_changed(self, idx: int) -> None:
        self._step_label.setText(f"Шаг: {idx + 1}/{len(self._steps)}")

    def _on_sim_finished(self) -> None:
        self._set_state_idle()
        self._clock_label.setText(_fmt_time(self._engine._t_ms))

    def closeEvent(self, event) -> None:
        """Flush and close DKP log files before the window goes away."""
        if self._dkp_logger is not None:
            try:
                self._dkp_logger.close()
            except OSError as exc:
                _LOG.warning("Failed to close DKP log files: %s", exc)
        super().closeEvent(event)

    # ================================================================== #
    #  [1] Boundary enforcement                                           #
    # ================================================================== #

    def _check_boundary(self, state: SimState, geom: _PathGeom) -> bool:
        """Pause the engine and warn if the train has left the track.

        Returns True if a boundary violation was detected (caller skips
        the rest of the tick's visual update in that case).
        """
        if not self._wagons:
            return False

        # Head of the train
        s_head = state.s_head_mm
        # Tail: front of the last wagon minus its length
        last_wagon   = self._wagons[-1]
        last_offset  = self._wagon_front_offsets[-1]
        s_tail = s_head - last_offset - last_wagon.length_mm

        violated = False
        if s_head > geom.length + 1.0:
            violated = True
            msg = (f"Состав вышел за конец пути «{geom.track_id}».\n"
                   f"Голова: {s_head/1000:.2f} м  /  Длина пути: {geom.length/1000:.2f} м")
        elif s_tail < -1.0:
            violated = True
            msg = (f"Состав вышел за начало пути «{geom.track_id}».\n"
                   f"Хвост: {s_tail/1000:.2f} м")

        if violated:
            self._engine.pause()
            self._paused = True
            self._set_state_paused()
            QMessageBox.warning(self, "Граница пути", msg)

        return violated

    # ================================================================== #
    #  [4] Coupler geometry                                               #
    # ================================================================== #

    def _coupler_points(self, s_head_mm: float, geom: _PathGeom) -> np.ndarray:
        """Build the polyline of coupler junction points (vectorised).

        The polyline visits:
          front of wagon 0, rear of wagon 0 / front of wagon 1,
          rear of wagon 1 / front of wagon 2, … rear of last wagon.
        """
        n = len(self._wagons)
        if n == 0:
            p = geom.s_to_xyz(s_head_mm).astype(np.float32)
            return np.array([p, p], dtype=np.float32)

        s_fronts = s_head_mm - self._wagon_front_offsets_np   # (N,)
        s_rears  = s_fronts - self._wagon_lengths_np          # (N,)

        # One arc-length per output point: front of wagon 0, then rear of each.
        s_all = np.empty(n + 1, dtype=np.float64)
        s_all[0]  = s_fronts[0]
        s_all[1:] = s_rears

        # Coupler Z: rail height at each wagon's front + 30 % of body height.
        inv_len = 1.0 / geom.length if geom.length > 0 else 0.0
        z_rail_f   = geom.p1[2] + s_fronts * inv_len * (geom.p2[2] - geom.p1[2])
        z_coupler  = z_rail_f + self._wagon_heights_np * 0.30  # (N,)

        z_all = np.empty(n + 1, dtype=np.float64)
        z_all[0]  = z_coupler[0]
        z_all[1:] = z_coupler

        pts = (
            geom.p1[np.newaxis, :]
            + geom.unit_vec[np.newaxis, :] * s_all[:, np.newaxis]
        ).astype(np.float32)
        pts[:, 2] = z_all.astype(np.float32)
        return pts

    # ================================================================== #
    #  Control button handlers                                            #
    # ================================================================== #

    def _cmd_start(self) -> None:
        errors = self._engine.validate()
        if errors:
            QMessageBox.critical(
                self, "Ошибка конфигурации",
                "Симуляция не может быть запущена:\n\n" +
                "\n".join(f"• {e}" for e in errors),
            )
            return
        try:
            self._engine.start()
        except ValueError as exc:
            QMessageBox.critical(self, "Ошибка запуска", str(exc))
            return
        self._clear_dkp_log()
        self._paused = False
        self._set_state_running()

    def _cmd_pause(self) -> None:
        if not self._paused:
            self._engine.pause()
            self._paused = True
            self._set_state_paused()
        else:
            self._engine.resume()
            self._paused = False
            self._set_state_running()

    def _cmd_stop(self) -> None:
        self._engine.stop()
        self._paused = False
        self._speed_label.setText("0 мм/с  ·  0.00 км/ч")
        self._clock_label.setText("00:00.000")
        self._step_label.setText("Шаг: —")
        # [3] Reset all DKP counters on stop
        for bundle in self._dkp_visuals.values():
            bundle.reset_counter()
        self._canvas.update()
        self._set_state_idle()

    def _cmd_set_speed(self, multiplier: float) -> None:
        self._engine.set_speed_multiplier(multiplier)

    def _cmd_fast_forward(self, seconds: int) -> None:
        self._engine.fast_forward(float(seconds))

    # ================================================================== #
    #  Button state machine                                               #
    # ================================================================== #

    def _set_state_idle(self) -> None:
        self._btn_start.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_pause.setText("⏸  Пауза")
        self._btn_stop.setEnabled(False)
        self._speed_mult_combo.setEnabled(False)
        self._ff_amount_combo.setEnabled(False)
        self._btn_ff.setEnabled(False)

    def _set_state_running(self) -> None:
        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_pause.setText("⏸  Пауза")
        self._btn_stop.setEnabled(True)
        self._speed_mult_combo.setEnabled(True)
        self._ff_amount_combo.setEnabled(True)
        self._btn_ff.setEnabled(True)

    def _set_state_paused(self) -> None:
        self._btn_start.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_pause.setText("▶  Продолжить")
        self._btn_stop.setEnabled(True)
        self._speed_mult_combo.setEnabled(True)
        self._ff_amount_combo.setEnabled(True)
        self._btn_ff.setEnabled(True)

    # ================================================================== #
    #  Canvas access  (for output_writer.py §5.3)                        #
    # ================================================================== #

    @property
    def canvas(self) -> SceneCanvas:
        return self._canvas


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_time(t_ms: int) -> str:
    total_s = t_ms // 1000
    ms_part = t_ms % 1000
    return f"{total_s // 60:02d}:{total_s % 60:02d}.{ms_part:03d}"

"""Machine-frame stations of the channel mechanism -- SolidWorks-free.

The rocker-pivot and lever-fulcrum shaft axes (machine x, y) are OWNED by
``cad/config/machine/channels.yaml`` (``channels.rocker_pivot_xy_mm`` /
``channels.lever_fulcrum_xy_mm``), the cylinder-gear shaft axis by
``cone_line.X_DRUM`` / ``cone_line.Y_DRIVE`` and the cylinder gears' mesh
lock by ``gear_train.cylinder_lock_phase_deg``; this module
is the one read point the channel/drive-train assemblies' placement and the
offline error budget (``error_budget.py``) import, so none copies a literal
(a copy is exactly the drift ``check:budget`` exists to catch). Same
drawing-free convention as ``magnifying_lever_geom``.
"""

from __future__ import annotations

import _config
from cone_line import X_DRUM, Y_DRIVE

ROCKER_PIVOT_XY: tuple[float, float] = tuple(
    float(v) for v in _config.machine("channels", "rocker_pivot_xy_mm")
)  # rocker pivot shaft axis (x, y); machine frame (crank at -X)
LEVER_FULCRUM_XY: tuple[float, float] = tuple(
    float(v) for v in _config.machine("channels", "lever_fulcrum_xy_mm")
)  # lever fulcrum shaft axis (x, y); machine frame
CAM_SHAFT_XY: tuple[float, float] = (
    X_DRUM,
    Y_DRIVE,
)  # cylinder-gear (drum) shaft axis (x, y); machine frame. FIXED by the frame:
# a cam or rod-pin tolerance moves the part, never this axis.
CYLINDER_LOCK_PHASE_DEG: float = float(
    _config.machine("gear_train", "cylinder_lock_phase_deg")
)  # the drive train turns every cylinder gear this far to mesh tooth-in-gap
# MHA-DT-12 cuts its cam lobe that same angle clockwise of the tooth crest
# (dt_cylinder_gear_phase_band.CAM_LOBE_OFFSET_DEG reads the same lock), so
# the lock leaves every lobe vertical at crank home (owner ruling 2026-11-20
# on #749, "B"). The rod length, the channel's rest pose and the error
# budget's cam phase start here.
CAM_HOME_PHASE_DEG: float = 0.0

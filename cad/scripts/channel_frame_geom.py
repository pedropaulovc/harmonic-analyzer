"""Machine-frame stations of the channel mechanism -- SolidWorks-free.

The rocker-pivot and lever-fulcrum shaft axes (machine x, y) are OWNED by
``cad/config/machine/channels.yaml`` (``channels.rocker_pivot_xy_mm`` /
``channels.lever_fulcrum_xy_mm``), the cylinder-gear shaft axis by
``cone_pivot_post_installation.DRUM_X`` + ``gear_train.drive_axis_y_mm`` and
the cams' home phase by ``gear_train.cylinder_lock_phase_deg``; this module
is the one read point the channel/drive-train assemblies' placement and the
offline error budget (``error_budget.py``) import, so none copies a literal
(a copy is exactly the drift ``check:budget`` exists to catch). Same
drawing-free convention as ``magnifying_lever_geom``.
"""

from __future__ import annotations

import _config
from cone_pivot_post_installation import DRUM_X

ROCKER_PIVOT_XY: tuple[float, float] = tuple(
    float(v) for v in _config.machine("channels", "rocker_pivot_xy_mm")
)  # rocker pivot shaft axis (x, y); machine frame (crank at -X)
LEVER_FULCRUM_XY: tuple[float, float] = tuple(
    float(v) for v in _config.machine("channels", "lever_fulcrum_xy_mm")
)  # lever fulcrum shaft axis (x, y); machine frame
CAM_SHAFT_XY: tuple[float, float] = (
    DRUM_X,
    float(_config.machine("gear_train", "drive_axis_y_mm")),
)  # cylinder-gear (drum) shaft axis (x, y); machine frame. FIXED by the frame:
# a cam or rod-pin tolerance moves the part, never this axis.
CYLINDER_LOCK_PHASE_DEG: float = float(
    _config.machine("gear_train", "cylinder_lock_phase_deg")
)  # every cam lobe sits this far off vertical at crank home (tooth-in-gap lock)

"""Machine-frame stations of the channel mechanism -- SolidWorks-free.

The rocker-pivot and lever-fulcrum shaft axes (machine x, y) are OWNED by
``cad/config/machine/channels.yaml`` (``channels.rocker_pivot_xy_mm`` /
``channels.lever_fulcrum_xy_mm``); this module is the one read point both
the channel assembly's placement and the offline error budget
(``error_budget.py``) import, so neither copies a literal (a copy is exactly
the drift ``check:budget`` exists to catch). Same drawing-free convention as
``magnifying_lever_geom``.
"""

from __future__ import annotations

import _config

ROCKER_PIVOT_XY: tuple[float, float] = tuple(
    float(v) for v in _config.machine("channels", "rocker_pivot_xy_mm")
)  # rocker pivot shaft axis (x, y); machine frame (crank at -X)
LEVER_FULCRUM_XY: tuple[float, float] = tuple(
    float(v) for v in _config.machine("channels", "lever_fulcrum_xy_mm")
)  # lever fulcrum shaft axis (x, y); machine frame

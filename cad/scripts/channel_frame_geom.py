"""Machine-frame stations of the channel mechanism -- SolidWorks-free.

The rocker-pivot and lever-fulcrum shaft axes (machine x, y) are owned by the
channel assembly's placement but are also inputs of the offline error budget
(``error_budget.py``), so they live here where both can import them; the
assembly must not copy them (a copy is exactly the drift ``check:budget``
exists to catch). Same drawing-free convention as ``magnifying_lever_geom``.
"""

from __future__ import annotations

ROCKER_PIVOT_XY = (
    72.9,
    253.8,
)  # rocker pivot shaft axis (x, y); machine frame (crank at -X)
LEVER_FULCRUM_XY = (199.9, 1061.4)  # lever fulcrum shaft axis (x, y); machine frame
# (2026-08-02 top-frame rederive: casting top face 1036.2 + ball rise 25.2;
# was 1065.9 off the old 1040.7 rail top)

"""Measuring-stick engraved-scale geometry -- SolidWorks-free, drawing-free.

The scale is OWNED by ``cad/config/machine/amplitude.yaml``
(``amplitude.stick_division_spacing_mm`` / ``stick_division_count`` /
``stick_minor_per_division``): it is the rule the operator reads amplitude-bar
stations against, so it belongs with the amplitude subsystem, not in a helper.
This module is the one read point ``build_measuring_stick`` (the engraved
ticks + the ``DivisionSpacing`` global), ``measuring_stick_spec`` (the print
notes that quote the pitch) and the offline ``error_budget`` (station ->
stick-reading conversion) import, so none of them copies a literal -- a copy is
exactly the drift ``check:budget`` exists to catch. Same drawing-free
convention as ``channel_frame_geom`` / ``magnifying_lever_geom``.
"""

from __future__ import annotations

import _config

DIVISION_SPACING: float = float(
    _config.machine("amplitude", "stick_division_spacing_mm")
)  # pitch of the full ticks, mm
DIVISION_COUNT: int = int(
    _config.machine("amplitude", "stick_division_count")
)  # full ticks 0..10
MINOR_PER_DIVISION: int = int(
    _config.machine("amplitude", "stick_minor_per_division")
)  # tenths per division
MINOR_SPACING: float = DIVISION_SPACING / MINOR_PER_DIVISION  # 1.42
SCALE_SPAN: float = (DIVISION_COUNT - 1) * DIVISION_SPACING  # 0-to-10 span, 142.0

"""Measuring-stick engraved-scale geometry -- SolidWorks-free, drawing-free.

The scale is OWNED by ``cad/config/machine/amplitude.yaml``
(``amplitude.stick_division_spacing_mm`` / ``stick_division_count`` /
``stick_minor_per_division``): it is the rule the operator reads amplitude-bar
stations against, so it belongs with the amplitude subsystem, not in a helper.
This module is the single configuration read point for ``ms_stick_spec``
and the offline ``error_budget`` station-to-reading conversion. Neither
copies the graduation pitch. It has no drawing or SolidWorks dependencies.
The unchanged scale spans 142 mm at 14.2 mm per full division.
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

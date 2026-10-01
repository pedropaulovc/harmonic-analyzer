r"""The hub-flange ↔ 120T disc joint: three #0-80 disc screws on one circle.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The one
authority for the screw pattern that two parts cut and must agree on: the
brass hub's flange (MHA-159, ``transgear_disc_hub_spec``) carries the Ø1.7
clearance holes and the 120T disc (MHA-070, ``rack_pinion_spec``) the #0-80
taps; the three 91794A055 fillister screws (MHA-161) join them (contract
§2.4-2.6, ruling 4).

Both parts' local frames put the gear axis on Z through the origin, with the
pattern's 0° on local +X and the angles counter-clockwise seen from +Z.  Both
parts sit in the machine unrotated, so local +X is the machine's +X.
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_band_mm

SCREW_THREAD = "#0-80"
SCREW_COUNT = 3
SCREW_ANGLES_DEG = (0.0, 120.0, 240.0)
BOLT_CIRCLE_DIA = 16.4
# Printed at .XXX: ±0.13 on the diameter is the ±0.065 radial hole-position
# band every stack of the joint uses (contract §8, "hole position ±0.065").
BOLT_CIRCLE_PLACES = 3
BOLT_CIRCLE_POSITION_TOL = printed_band_mm(BOLT_CIRCLE_PLACES) / 2.0

if len(SCREW_ANGLES_DEG) != SCREW_COUNT:
    raise AssertionError("one pattern angle per disc screw")


def screw_centres() -> tuple[tuple[float, float], ...]:
    """``(x, y)`` of each screw axis in either part's local frame (mm)."""
    radius = BOLT_CIRCLE_DIA / 2.0
    return tuple(
        (radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle)))
        for angle in SCREW_ANGLES_DEG
    )


# The equation factors both parts' sketches use to drive the 120° and 240°
# centres from the one "BoltCircleDia" global: x = BC / 4, |y| = BC · √3 / 4.
BOLT_CIRCLE_X_FACTOR = 0.25
BOLT_CIRCLE_Y_FACTOR = math.sqrt(3.0) / 4.0

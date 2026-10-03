r"""The hub-flange ↔ 120T disc joint: three #0-80 disc screws on one circle,
and the hub's spigot the disc pilots on.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The one
authority for what two parts cut and must agree on: the brass hub's flange
(MHA-159, ``transgear_disc_hub_spec``) carries the Ø1.7 clearance holes and
the 120T disc (MHA-070, ``rack_pinion_spec``) the #0-80 taps; the three
91794A055 fillister screws (MHA-161) join them on a Ø19 circle, the
smallest that keeps the disc's taps 2.0 clear of its Ø13.1 bore at the worst
case (``rack_pinion_spec`` checks it; the heads stand 1.5 clear of the
Ø13.2 hub body).  The hub's rear spigot passes the disc's bore and seats on
the MHA-110 sleeve's step face (R9-68): its diameter is the disc's locating
fit and its length the disc front face's station ahead of the step, so the
disc's, the sleeve's and the hub's specs and the cluster fit read it here.
Nothing here imports either part's spec, so the disc's spec reads the joint
without reaching the hub's (which reads the cluster fit, which reads the
disc).

Both parts' local frames put the gear axis on Z through the origin, with the
pattern's 0° on local +X and the angles counter-clockwise seen from +Z.  Both
parts sit in the machine unrotated, so local +X is the machine's +X.
"""

from __future__ import annotations

import math

from _printed_tolerance import printed_band_mm

SCREW_THREAD = "#0-80"
# MHA-161, McMaster 91794A055 (diagnostics.diag_mcmaster_fillister sizes it).
SCREW_SKU = "91794A055"
SCREW_COUNT = 3
SCREW_ANGLES_DEG = (0.0, 120.0, 240.0)
# The flange's drilled clearance hole the disc's taps are spotted through.
SCREW_HOLE_DIA = 1.7
BOLT_CIRCLE_DIA = 19.0
# Printed at .XXX: ±0.13 on the diameter is the ±0.065 radial hole-position
# band every stack of the joint uses (contract §8, "hole position ±0.065").
BOLT_CIRCLE_PLACES = 3
BOLT_CIRCLE_POSITION_TOL = printed_band_mm(BOLT_CIRCLE_PLACES) / 2.0

if len(SCREW_ANGLES_DEG) != SCREW_COUNT:
    raise AssertionError("one pattern angle per disc screw")

# The hub's spigot (R9-68): Ø13.1 h6 (ISO, 10-18 mm) in the disc's H7 bore,
# the smallest h6 size that keeps 2.0 of wall over the hub's Ø9 H7 bore at
# the worst case.  Its length runs from the flange's rear face (the disc's
# front face) to its end on the sleeve's step, printed .XXX.
SPIGOT_DIA = 13.1
SPIGOT_DIA_BAND = (0.0, -0.011)  # (upper, lower) deviations, h6
SPIGOT_DIA_PLACES = 3
SPIGOT_LENGTH = 3.65
SPIGOT_LENGTH_PLACES = 3
SPIGOT_LENGTH_BAND = printed_band_mm(SPIGOT_LENGTH_PLACES)


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

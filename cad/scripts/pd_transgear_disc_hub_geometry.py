r"""The hub-flange ↔ reducer-disc joint: three #0-80 disc screws on one circle,
and the hub's spigot the disc pilots on.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` import.  The one
authority for what two parts cut and must agree on: the brass hub's flange
(MHA-PD-17, ``transgear_disc_hub_spec``) carries the #51 (.067) clearance
holes and the reducer disc (MHA-PD-06, ``rack_pinion_spec``) the #0-80 taps;
the three 91794A055 fillister screws (MHA-PD-VN-55) join them on a Ø.748
circle, which keeps the disc's taps .080 clear of its Ø.501 bore at the worst
case (``rack_pinion_spec`` checks it; the heads stand clear of the Ø.52 hub
body).  The hub's rear spigot passes the disc's bore and seats on
the MHA-PD-10 sleeve's step face (R9-68): its diameter is the disc's locating
fit and its length the disc front face's station ahead of the step, so the
disc's, the sleeve's and the hub's specs and the cluster fit read it here.
Nothing here imports either part's spec, so the disc's spec reads the joint
without reaching the hub's (which reads the cluster fit, which reads the
disc).

Decimal inch (#290): both sheets print inches; every nominal below is the
exact millimetre value of its printed inch size.

Both parts' local frames put the gear axis on Z through the origin, with the
pattern's 0° on local +X and the angles counter-clockwise seen from +Z.  Both
parts sit in the machine unrotated, so local +X is the machine's +X.
"""

from __future__ import annotations

import math

import _config
from _fit_shaft_h import SHAFT_H
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from pd_cluster_stack_band import PRINTED_LENGTH_BAND_IN

# The hub sheet prints the bolt circle; the disc reads the same unit.
UNIT = drawing_unit(
    "parts/pd-transgear-disc-hub", _config.parts("pd-transgear-disc-hub")
)


SCREW_THREAD = "#0-80"
# MHA-PD-VN-55, McMaster 91794A055 (_mcmaster_91794a055 sizes it).
SCREW_COUNT = 3
SCREW_ANGLES_DEG = (0.0, 120.0, 240.0)
# The flange's drilled clearance hole the disc's taps are spotted through:
# a #51 drill.
SCREW_HOLE_DIA = 1.7018  # .067
BOLT_CIRCLE_DIA = 18.9992  # .748
# Printed at .XXX: ±.005 on the diameter is the ±.0025 radial hole-position
# band every stack of the joint uses (contract §8, "hole position").
BOLT_CIRCLE_PLACES = 3
BOLT_CIRCLE_POSITION_TOL = printed_band_mm(BOLT_CIRCLE_PLACES, unit=UNIT) / 2.0

if len(SCREW_ANGLES_DEG) != SCREW_COUNT:
    raise AssertionError("one pattern angle per disc screw")

# The retained hub spigot (R9-68): Ø.501 SHAFT_H in the disc's .501 REAM_H7
# bore (an owned .5010 reamer), the disc pilot and screw-to-bore wall
# envelope.  Its length runs from the flange's rear face to its end on the
# sleeve's step: a term of the disc cluster's printed stack
# (transgear_cluster_fit), printed at the cluster's band (#2038 owner ruling
# 2026-10-28), four places to carry it.
SPIGOT_DIA = 12.7254  # .501
SPIGOT_DIA_BAND = SHAFT_H  # (upper, lower) deviations: 0/-.0008
SPIGOT_DIA_PLACES = 4
SPIGOT_LENGTH = 3.6576  # .144
SPIGOT_LENGTH_PLACES = 4
SPIGOT_LENGTH_BAND = PRINTED_LENGTH_BAND_IN


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

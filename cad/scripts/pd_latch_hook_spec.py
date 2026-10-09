r"""MHA-PD-014 latch hook: the printed bands, the walls and the screw-head
clearance they hold, and the sheet's marked dimensions.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Geometry and frame: ``pd_latch_hook_geometry``.

One formed 0.8 (0.032 in) 1095 spring-steel part: a base on the support
bar's back face under two #4-40 screws (MHA-VN-043), a 90 deg ear at its +X
end, and an arm hanging from the ear's lower edge, rolled R80 flatwise to
lie square to the MHA-VN-042 latch pin, with a pin hole and a finger tab.
Latching: pull the tab along +U, the arm flexes flatwise and the strip slides
off the pin; lift the hanger and the pin's crowned end rides up the tab and
the strip until it snaps into the hole.

Process (the sheet's notes): the blank is the flat pattern; every form is
made annealed; fit to the bar, clamp the hanger at full feed mesh, set the
annealed arm square on the pin with the strip's far face at its drawn
station, and match-drill the pin hole from the pin; remove, harden and
temper blue, reinstall.  The order of cutting, bending and drilling is the
shop's.

How the sheet locates things:

* screw-hole X from the ear's outer face (x = 0), Y from the base's low-Y
  edge (y = 0), both ±POSITION_TOL at .XX: the Ø3.2 drilled hole's float
  over the basic #4-40 major, less the MHA-PD-007 bar taps' own ±0.065, is
  what each printed position may spend (the fixed-fastener stack, as the
  guide lock's on its screws);
* the base length ±BASE_LENGTH_TOL at .XX: the .XX row's ±0.51 would thin
  the far screw hole's -X edge wall to 1.79;
* the width ±WIDTH_TOL: the ear's +Y edge in the guide-lock sweep (the
  paper-drive assembly's check) and the screw holes' y-edge walls;
* the ear height and the arm's two front-edge heights (its z band, from the
  base's underside) at .X;
* the inside bend radius R1.2 +0.3/-0.2 (R1.5 the largest the screw head
  clears); the 90 deg bend at the title block's angular row;
* every formed arm feature (roll, straight, tab) ±FORMED_BAND at .X, the
  radii to the inside surface; the far face at the pin, located in X and Y
  from the origin, only as a reference (REFERENCE_DIMENSIONS): a hand-rolled
  R80 holds no tighter band there, and the fit-up sets the strip on the pin
  (square, its face at that station) before the hole is match-drilled;
* the pin hole: size only, drilled +0.10/0, match-drilled at assembly from
  the pin (the model keeps it at the geometry's nominal);
* the flat pattern (a hidden reference sketch shown beside the side view):
  the blank's length across the bend and the arm's developed stations of the
  taper and the full round's centre, at .X.
* the formed overall height, the ear's top edge to the full round's tip: a
  reference only, at DRAWING_REFERENCE_PRECISION.

Walls (policy rule 12) are judged at the worst case of those bands, with the
sheet rounding each printed value to its places.  The pin hole is drilled on
the pin, so its walls take its model place; where the pin sits on the bar is
the paper-drive assembly's to hold.
"""

from __future__ import annotations

import math

from _printed_tolerance import angular_band_deg, drilled_oversize_mm, printed_deviations
from pd_latch_hook_geometry import (
    ARM_Z0,
    ARM_Z1,
    BASE_LENGTH,
    BBOX_Y,
    EAR_HEIGHT,
    INSIDE_BEND_R,
    INSIDE_BEND_R_MAX,
    PIN_HOLE_DIA,
    PIN_HOLE_ZL,
    ROUND_R,
    SCREW_HOLE_DIA,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    SHEET_T,
    SHEET_T_PLUS,
    WIDTH,
)
from pd_support_bar_spec import HOLE_POSITION_BAND as BAR_TAP_BAND
from vn_latch_hook_bracket_screw_spec import HEAD_DIA, MAJOR_DIA, MAJOR_DIA_MIN

# --- Printed bands -----------------------------------------------------------
HOLE_BAND = (drilled_oversize_mm(), 0.0)  # (upper, lower): drilled, never under
HOLE_PLACES = 2
# The screws' fit (the fixed-fastener stack): each screw stands in its bar
# tap up to the bar's per-axis band off the model (radial reach hypot(b, b));
# the smallest drilled hole clears the basic major by CLEARANCE_RADIAL_MIN;
# the hook's printed hole position, at .XX, gets the widest band whose
# reach at the printed limits (the rounding to .XX included) keeps the
# stack inside that clearance.
CLEARANCE_RADIAL_MIN = (SCREW_HOLE_DIA - MAJOR_DIA) / 2.0
BAR_TAP_RADIAL = math.hypot(BAR_TAP_BAND, BAR_TAP_BAND)
POSITION_PLACES = 2
WIDTH_TOL = 0.10  # ± on the 8.00 width (sheared blank): the lock sweep
WIDTH_PLACES = 2
BASE_LENGTH_TOL = 0.25  # ±: the far screw hole's -X edge wall
BASE_LENGTH_PLACES = 2
EAR_HEIGHT_PLACES = 1
ARM_BAND_PLACES = 1  # the arm's z-band edges, from the base's underside
FORMED_BAND = 0.5  # ± on every formed arm feature (roll, straight, tab)
FORMED_PLACES = 1
# The far face at the pin prints X and Y from the origin as references: the
# fit-up sets the annealed arm square on the pin with the face at the drawn
# station, so the formed band, not a printed coordinate band, is what the
# hanger joints' far-face margin spends along U.
BEND_TOL_DEG = angular_band_deg()  # the ear's 90 deg bend, title-block row
BEND_R_PLACES = 1
BEND_R_BAND = (INSIDE_BEND_R_MAX - INSIDE_BEND_R, -0.2)  # (upper, lower)
ROOT_R_PLACES = 1
ROUND_R_PLACES = 2  # the full round, half the 11.50 low band
FLAT_PLACES = 1  # the flat pattern's lengths

WALL_TARGET = 2.0
WALL_FLOOR = 1.5
HEAD_CLEARANCE_FLOOR = 0.2  # screw head rim to the inside bend radius


def _position(value: float, tol: float | None = None) -> tuple[float, float]:
    """(lower, upper) deviation of a printed screw-hole position."""
    tol = POSITION_TOL if tol is None else tol
    return printed_deviations(value, POSITION_PLACES, (-tol, tol))


def _position_radial(tol: float) -> float:
    """The stack's radial reach at a ±``tol`` print: the bar tap's, plus each
    hole's farthest printed corner off its model (the rounding included)."""

    def reach(value: float) -> float:
        return max(abs(d) for d in _position(value, tol))

    return BAR_TAP_RADIAL + max(
        math.hypot(reach(-x), reach(SCREW_HOLE_Y)) for x in SCREW_HOLE_X
    )


_POSITION_STEP = 10.0**-POSITION_PLACES
_POSITION_STEPS = max(
    (
        k
        for k in range(1, math.ceil(CLEARANCE_RADIAL_MIN / _POSITION_STEP))
        if _position_radial(k * _POSITION_STEP) <= CLEARANCE_RADIAL_MIN + 1e-9
    ),
    default=0,
)
# ± on the screw-hole positions: 0.05 (0.06 would reach 0.180 > 0.178).
POSITION_TOL = round(_POSITION_STEPS * _POSITION_STEP, POSITION_PLACES)
if POSITION_TOL <= 0.0:
    raise AssertionError(
        "MHA-VN-043 screws in the MHA-PD-007 bar taps through the MHA-PD-014 hook: "
        f"no .XX position band fits the radial clearance {CLEARANCE_RADIAL_MIN:.4f}"
    )
SCREW_POSITION_RADIAL = _position_radial(POSITION_TOL)


def _row(value: float, places: int) -> tuple[float, float]:
    """(lower, upper) deviation of a title-block dimension from the model."""
    return printed_deviations(value, places)


_WIDTH_LOW = printed_deviations(WIDTH, WIDTH_PLACES, (-WIDTH_TOL, WIDTH_TOL))[0]
_BASE_LOW = printed_deviations(
    BASE_LENGTH, BASE_LENGTH_PLACES, (-BASE_LENGTH_TOL, BASE_LENGTH_TOL)
)[0]
_HOLE_GROW = max(HOLE_BAND) / 2.0
_SCREW_R = SCREW_HOLE_DIA / 2.0
_PIN_R = PIN_HOLE_DIA / 2.0


def _screw_y_edges() -> tuple[float, float]:
    """Screw holes to the nearer of the base's two y edges."""
    low = SCREW_HOLE_Y - _SCREW_R
    high = WIDTH - SCREW_HOLE_Y - _SCREW_R
    pos_low, pos_high = _position(SCREW_HOLE_Y)
    low_worst = low + pos_low - _HOLE_GROW
    high_worst = high + _WIDTH_LOW - pos_high - _HOLE_GROW
    return min(low, high), min(low_worst, high_worst)


def _screw_x_edge() -> tuple[float, float]:
    """The far screw hole to the base's -X end."""
    x = -SCREW_HOLE_X[0]  # printed distance from the ear's outer face
    nominal = BASE_LENGTH - x - _SCREW_R
    return nominal, nominal + _BASE_LOW - _position(x)[1] - _HOLE_GROW


def _screw_web() -> tuple[float, float]:
    """Web between the two screw holes."""
    far, near = -SCREW_HOLE_X[0], -SCREW_HOLE_X[1]
    nominal = far - near - 2.0 * _SCREW_R
    worst = nominal + _position(far)[0] - _position(near)[1] - 2.0 * _HOLE_GROW
    return nominal, worst


def _pin_front_edge() -> tuple[float, float]:
    """The pin hole to the arm's front edge below the taper."""
    nominal = PIN_HOLE_ZL - _PIN_R - ARM_Z0
    return nominal, nominal - _row(ARM_Z0, ARM_BAND_PLACES)[1] - _HOLE_GROW


def _pin_rear_edge() -> tuple[float, float]:
    """The pin hole to the arm's rear edge (the ear's top)."""
    nominal = ARM_Z1 - PIN_HOLE_ZL - _PIN_R
    return nominal, nominal + _row(EAR_HEIGHT, EAR_HEIGHT_PLACES)[0] - _HOLE_GROW


if abs(ARM_Z1 - EAR_HEIGHT) > 1e-9:
    raise AssertionError("the arm's rear edge is not the ear's top")

WALLS: dict[str, tuple[float, float]] = {
    "screw holes to the base's y edges": _screw_y_edges(),
    "far screw hole to the base's -X end": _screw_x_edge(),
    "web between the screw holes": _screw_web(),
    "pin hole to the arm's front edge": _pin_front_edge(),
    "pin hole to the arm's rear edge": _pin_rear_edge(),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET - 1e-9:
        raise AssertionError(
            f"MHA-PD-014 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under the {WALL_TARGET} target"
        )


def head_clearance(
    inside_r: float, sheet_t: float, position_dev: float, head_float: float
) -> float:
    """Gap, along X, from the ear-side screw head's rim to where the inside
    bend radius leaves the base's top face.

    The head (Ø``HEAD_DIA``, the catalogue maximum) sits on the base top; the
    radius starts ``sheet_t + inside_r`` in from the ear's outer face and
    only rises away from the head.  ``position_dev`` moves the hole toward the
    ear (+X); ``head_float`` is how far the screw, held by the bar's tap, can
    sit off the hole's axis toward the ear."""
    head_rim = SCREW_HOLE_X[1] + position_dev + head_float + HEAD_DIA / 2.0
    fillet_start = -(sheet_t + inside_r)
    return fillet_start - head_rim


HEAD_CLEARANCE_NOMINAL = head_clearance(INSIDE_BEND_R, SHEET_T, 0.0, 0.0)
# The worst case: the largest bend radius, the thickest sheet, the printed
# distance from the ear's outer face at its lower limit (the hole nearest the
# ear), and the largest drilled hole floating over the smallest 2A major.
HEAD_FLOAT_MAX = (SCREW_HOLE_DIA + max(HOLE_BAND) - MAJOR_DIA_MIN) / 2.0
HEAD_CLEARANCE_WORST = head_clearance(
    INSIDE_BEND_R + BEND_R_BAND[0],
    SHEET_T + SHEET_T_PLUS,
    -_position(-SCREW_HOLE_X[1])[0],
    HEAD_FLOAT_MAX,
)
if HEAD_CLEARANCE_WORST < HEAD_CLEARANCE_FLOOR - 1e-9:
    raise AssertionError(
        f"latch hook screw head to bend radius {HEAD_CLEARANCE_WORST:.3f} under "
        f"{HEAD_CLEARANCE_FLOOR}: move the screw pair -X"
    )

# --- Sheet text --------------------------------------------------------------
# The title block's MATERIAL cell (the registry row's ``material``); the
# heat treatment is its FINISH cell, so no note restates either.
MATERIAL_TITLE = f"{SHEET_T:.1f} (0.032) 1095 spring steel"
DRAWING_NOTES = "\n".join(
    (
        "1. FLAT PATTERN: THIN OUTLINE RIGHT OF SIDE VIEW. FORM ANNEALED.",
        "2. FIT ANNEALED ON MHA-PD-007; CLAMP HANGER AT FULL MESH.",
        "3. SET ARM SQUARE ON PIN, FACE AT DRAWN STATION; MATCH-DRILL PIN HOLE.",
        "4. REMOVE FOR HEAT TREATMENT, REINSTALL. RADII TO INSIDE SURFACE.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"
# The base-and-ear section stands beside the side view, out of projection
# with the front view, so it is labelled.
BOTTOM_VIEW_NOTE = "BOTTOM VIEW"
PAIR_CALLOUT = "2X"
SCREW_HOLE_CALLOUT = "DRILL THRU"
# One line: an above-callout (note 3 says where and when it is drilled).
PIN_HOLE_CALLOUT = "MATCH-DRILL"
ROUND_CALLOUT = "FULL ROUND"
FLAT_ROUND_CALLOUT = "TO FULL-ROUND CENTRE"
# Rule 7: the formed overall height, the ear's top edge to the full round's
# tip, a reference left of the side view (the front view's 70.4 to the pin
# stays its own dimension).
OVERALL_HEIGHT = BBOX_Y[1] - BBOX_Y[0]  # 96.5
DRAWING_REFERENCE_PRECISION = 1

# The flat pattern: a hidden reference sketch on the Right plane, beside the
# formed side view; the drawing shows it there only, a thin solid outline.
FLAT_SKETCH = "FlatBlank"
REFERENCE_SKETCHES = (FLAT_SKETCH,)

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The second screw hole shares its size
# and Y with the first (same globals) and prints once under "2X".
FORMED_DIMENSIONS: dict[str, set[str]] = {
    "ArmProfile": {"RollStart", "RollR", "StraightLen", "TabR", "TabEndX"},
}
# The far face at the pin: printed in parentheses (see the band comment).
REFERENCE_DIMENSIONS = frozenset({"FaceX", "FaceY"})
POSITION_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "ScrewHoleProfile": ("ScrewX1", "ScrewX2", "ScrewY"),
}
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BaseEarProfile": {"BaseLength", "EarHeight"},
    "BaseEar": {"Width"},
    "InsideBend": {"InsideBendR"},
    "ScrewHoleProfile": {"ScrewX1", "ScrewX2", "ScrewY", "ScrewDia"},
    "ArmProfile": FORMED_DIMENSIONS["ArmProfile"] | REFERENCE_DIMENSIONS,
    "Arm": {"ArmLowZ"},
    "TaperProfile": {"ArmFrontZ"},
    "RootRelief": {"RootR"},
    "RoundProfile": {"RoundR"},
    "PinHoleProfile": {"PinHoleDia"},
    FLAT_SKETCH: {"FlatLength", "DevTaper1", "DevTaper2", "DevRoundC"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BaseEarProfile": {
        "BaseLength": BASE_LENGTH_PLACES,
        "EarHeight": EAR_HEIGHT_PLACES,
    },
    "BaseEar": {"Width": WIDTH_PLACES},
    "InsideBend": {"InsideBendR": BEND_R_PLACES},
    "ScrewHoleProfile": {
        "ScrewX1": POSITION_PLACES,
        "ScrewX2": POSITION_PLACES,
        "ScrewY": POSITION_PLACES,
        "ScrewDia": HOLE_PLACES,
    },
    "ArmProfile": {
        name: FORMED_PLACES for name in sorted(DRAWING_DIMENSIONS["ArmProfile"])
    },
    "Arm": {"ArmLowZ": ARM_BAND_PLACES},
    "TaperProfile": {"ArmFrontZ": ARM_BAND_PLACES},
    "RootRelief": {"RootR": ROOT_R_PLACES},
    "RoundProfile": {"RoundR": ROUND_R_PLACES},
    "PinHoleProfile": {"PinHoleDia": HOLE_PLACES},
    FLAT_SKETCH: {
        name: FLAT_PLACES for name in sorted(DRAWING_DIMENSIONS[FLAT_SKETCH])
    },
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked dimension must state its decimal places")
if abs(2.0 * ROUND_R - (ARM_Z1 - ARM_Z0)) > 1e-9:
    raise AssertionError("the full round is not half the low band")

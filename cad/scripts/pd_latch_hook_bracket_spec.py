r"""MHA-PD-021 latch-hook bracket: the printed bands, the walls and the head
clearance they hold, and the sheet's marked dimensions.

PURE DATA, no SolidWorks/COM calls and no ``build_*`` module in its import
closure.  Geometry and frame: ``pd_latch_hook_bracket_geometry``.

How the sheet locates things (holes drilled after bending, R9-10):

* screw-hole X from the flap's outer face (x = 0), hole Y from the base's
  low-Y edge (y = 0), both ±POSITION_TOL: the pair lands on the MHA-PD-007
  bar's #4-40 taps (themselves ±0.065) with ~0.18 radial float, and the
  title block's .XXX ±0.13 would leave the y-edge ligament 1.94 and the
  head 0.14 off the bend fillet;
* rivet holes: not located on the sheet.  They are match-drilled through
  the MHA-PD-014 hook at assembly, after the hook is set to latch the MHA-VN-042
  pin (R9-15); the model keeps them at the hook's nominal ``RIVET_YZ``;
* the width at ±WIDTH_TOL: the base must stay inside the bar's lock-free
  band (0.5 each side of the 8.0 base), and the y-edge ligament of the screw
  holes is 2.00 at that band; the title block's .XX row would thin it to 1.74;
* the base length at .XX (title block): at .X the screw hole's -X edge
  wall would be 2.900 - 0.8 - 0.065 - 0.05 = 1.985, under the 2.0 target;
  the flap height at .X (title block);
* both hole sizes drilled, +0.10 / 0.

Walls (policy rule 12) are judged at the worst case of those bands, with the
sheet rounding each printed value to its places.  The rivet holes' walls are
judged over the hook's set (HOOK_SET_YZ as printed, ±HOOK_SET_RANGE, in the
flap plane) and the hook's own printed pitch band.
"""

from __future__ import annotations

from _printed_tolerance import printed_deviations
from pd_latch_hook_bracket_geometry import (
    BASE_LENGTH,
    FLAP_HEIGHT,
    INSIDE_BEND_R,
    INSIDE_BEND_R_MAX,
    RIVET_HOLE_DIA,
    RIVET_YZ,
    SCREW_HOLE_DIA,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    SHEET_T,
    SHEET_T_PLUS,
    WIDTH,
)
from vn_latch_hook_bracket_screw_spec import HEAD_DIA, MAJOR_DIA_MIN
from pd_latch_hook_geometry import RIVET_PITCH

# --- Printed bands -----------------------------------------------------------
HOLE_BAND = (0.10, 0.0)  # (upper, lower): drilled, never under size
POSITION_TOL = 0.065  # ± on every hole position
POSITION_PLACES = 3
WIDTH_TOL = 0.25  # ± on the 8.00 width: the lock-free band and the ligament
WIDTH_PLACES = 2
BASE_LENGTH_PLACES = 2  # .XX: the screw hole's -X edge wall
FLAP_HEIGHT_PLACES = 1  # .X: the top rivet's edge wall holds at ±0.8
HOLE_PLACES = 2

WALL_TARGET = 2.0
HEAD_CLEARANCE_FLOOR = 0.2  # R9-10: screw head to the bend fillet
# How far the hook may be set from its nominal, in the flap plane (y and z),
# before the rivet holes are match-drilled through it: it covers the hook's
# .XX pin-hole run band, which the set takes up (R9-24, R9-26).
HOOK_SET_RANGE = 0.51
HOOK_PITCH_PLACES = 3  # the hook prints its rivet pitch at .XXX
# Sheet 4's hook-set-and-riveted step measures the set hook on its rivet
# holes from this sheet's own datums: both centres HOOK_SET_YZ[0] above the
# flap's lower edge (y = 0), the front one's HOOK_SET_YZ[1] rear of the bar's
# back face (the base's underside, z = 0), each printed at .XX and held to
# ±HOOK_SET_RANGE.  Machinist review of 0316d0951: "its drawn place" gave the
# fitter nothing to measure from.
HOOK_SET_PLACES = 2
HOOK_SET_YZ = RIVET_YZ[0]
HOOK_SET_Y_DEV, HOOK_SET_Z_DEV = (
    printed_deviations(value, HOOK_SET_PLACES, (-HOOK_SET_RANGE, HOOK_SET_RANGE))
    for value in HOOK_SET_YZ
)


def _position(value: float) -> tuple[float, float]:
    """(lower, upper) deviation of a printed hole position from the model."""
    return printed_deviations(value, POSITION_PLACES, (-POSITION_TOL, POSITION_TOL))


def _row(value: float, places: int) -> tuple[float, float]:
    """(lower, upper) deviation of a title-block dimension from the model."""
    return printed_deviations(value, places)


_WIDTH_LOW = printed_deviations(WIDTH, WIDTH_PLACES, (-WIDTH_TOL, WIDTH_TOL))[0]
_SCREW_R = SCREW_HOLE_DIA / 2.0
_SCREW_R_MAX = _SCREW_R + max(HOLE_BAND) / 2.0
_RIVET_R = RIVET_HOLE_DIA / 2.0
_RIVET_R_MAX = _RIVET_R + max(HOLE_BAND) / 2.0
_RIVET_Y = RIVET_YZ[0][0]
(_RIVET_Z_LOW, _RIVET_Z_HIGH) = (RIVET_YZ[0][1], RIVET_YZ[1][1])

if RIVET_YZ[0][0] != RIVET_YZ[1][0]:
    raise AssertionError("the sheet prints one Y for both rivet holes")


def _screw_y_edges() -> tuple[float, float]:
    """Screw holes to the nearer of the base's two y edges."""
    low = SCREW_HOLE_Y - _SCREW_R
    high = WIDTH - SCREW_HOLE_Y - _SCREW_R
    pos_low, pos_high = _position(SCREW_HOLE_Y)
    low_worst = low + pos_low - (_SCREW_R_MAX - _SCREW_R)
    high_worst = high + _WIDTH_LOW - pos_high - (_SCREW_R_MAX - _SCREW_R)
    return min(low, high), min(low_worst, high_worst)


def _screw_x_edge() -> tuple[float, float]:
    """The far screw hole to the base's -X edge."""
    x = -SCREW_HOLE_X[0]  # printed distance from the flap's outer face
    nominal = BASE_LENGTH - x - _SCREW_R
    worst = (
        nominal
        + _row(BASE_LENGTH, BASE_LENGTH_PLACES)[0]
        - _position(x)[1]
        - (_SCREW_R_MAX - _SCREW_R)
    )
    return nominal, worst


# The flap's holes copy the hook's: both move together over the set range,
# and their pitch is the hook's printed pitch.  Conservatively, the full
# pitch deviation is charged to whichever hole the wall is judged at.
_PITCH_LOW, _PITCH_HIGH = printed_deviations(RIVET_PITCH, HOOK_PITCH_PLACES)
_RIVET_GROW = _RIVET_R_MAX - _RIVET_R

if abs((_RIVET_Z_HIGH - _RIVET_Z_LOW) - RIVET_PITCH) > 1e-6:
    raise AssertionError("the flap's rivet holes are not at the hook's pitch")


def _rivet_y_edges() -> tuple[float, float]:
    """Rivet holes to the nearer of the flap's two y edges."""
    low = _RIVET_Y - _RIVET_R
    high = WIDTH - _RIVET_Y - _RIVET_R
    return (
        min(low, high),
        min(low + HOOK_SET_Y_DEV[0], high + _WIDTH_LOW - HOOK_SET_Y_DEV[1])
        - _RIVET_GROW,
    )


def _rivet_top_edge() -> tuple[float, float]:
    """The upper rivet hole to the flap's top edge."""
    nominal = FLAP_HEIGHT - _RIVET_Z_HIGH - _RIVET_R
    worst = (
        nominal
        + _row(FLAP_HEIGHT, FLAP_HEIGHT_PLACES)[0]
        - HOOK_SET_Z_DEV[1]
        - _PITCH_HIGH
        - _RIVET_GROW
    )
    return nominal, worst


def _rivet_bend() -> tuple[float, float]:
    """The lower rivet hole to where the inside bend fillet leaves the flap's
    inner face (the hook's face): thickest sheet, largest printed radius."""
    nominal = _RIVET_Z_LOW - _RIVET_R - (SHEET_T + INSIDE_BEND_R)
    fillet_top = SHEET_T + SHEET_T_PLUS + INSIDE_BEND_R_MAX
    worst = _RIVET_Z_LOW + HOOK_SET_Z_DEV[0] - _PITCH_HIGH - _RIVET_R_MAX - fillet_top
    return nominal, worst


def _rivet_web() -> tuple[float, float]:
    """Web between the two rivet holes (the hook's pitch, copied)."""
    nominal = RIVET_PITCH - 2.0 * _RIVET_R
    return nominal, nominal + _PITCH_LOW - 2.0 * _RIVET_GROW


WALLS: dict[str, tuple[float, float]] = {
    "screw holes to the base's y edges": _screw_y_edges(),
    "screw hole to the base's -X edge": _screw_x_edge(),
    "rivet holes to the flap's y edges": _rivet_y_edges(),
    "upper rivet hole to the flap's top edge": _rivet_top_edge(),
    "lower rivet hole to the inside bend fillet": _rivet_bend(),
    "web between the rivet holes": _rivet_web(),
}
for _name, (_nominal, _worst) in WALLS.items():
    if _worst < WALL_TARGET - 1e-9:
        raise AssertionError(
            f"MHA-PD-021 {_name} wall {_worst:.3f} at the printed worst case is "
            f"under the {WALL_TARGET} target"
        )


def head_clearance(
    inside_r: float, sheet_t: float, position_dev: float, head_float: float
) -> float:
    """Gap, along X, from the flap-side screw head's rim to where the inside
    bend fillet leaves the base's top face.

    The head (Ø``HEAD_DIA``, the catalogue maximum) sits on the base top; the
    fillet starts ``sheet_t + inside_r`` in from the flap's outer face and
    only rises away from the head.  ``position_dev`` moves the hole toward the
    flap (+X); ``head_float`` is how far the screw, held by the bar's tap,
    can sit off the hole's axis toward the flap."""
    head_rim = SCREW_HOLE_X[1] + position_dev + head_float + HEAD_DIA / 2.0
    fillet_start = -(sheet_t + inside_r)
    return fillet_start - head_rim


HEAD_CLEARANCE_NOMINAL = head_clearance(INSIDE_BEND_R, SHEET_T, 0.0, 0.0)
# The worst case: R1.0 bend, the thickest sheet, the printed distance from the
# flap's outer face at its lower limit (the hole nearest the flap), and the
# largest drilled hole floating over the smallest 2A thread major.
HEAD_FLOAT_MAX = (SCREW_HOLE_DIA + max(HOLE_BAND) - MAJOR_DIA_MIN) / 2.0
HEAD_CLEARANCE_WORST = head_clearance(
    INSIDE_BEND_R_MAX,
    SHEET_T + SHEET_T_PLUS,
    -_position(-SCREW_HOLE_X[1])[0],
    HEAD_FLOAT_MAX,
)
if HEAD_CLEARANCE_WORST < HEAD_CLEARANCE_FLOOR - 1e-9:
    raise AssertionError(
        f"bracket screw head to bend fillet {HEAD_CLEARANCE_WORST:.3f} under "
        f"{HEAD_CLEARANCE_FLOOR}: move the screw pair -X"
    )

# --- Sheet text --------------------------------------------------------------
BEND_NOTE = f"INSIDE BEND R{INSIDE_BEND_R_MAX:.1f} MAX; DRILL HOLES AFTER BENDING."
# The stock is the title block's MATERIAL cell (the registry row's
# ``material``) and its general note breaks edges, so the one note is the bend.
MATERIAL_TITLE = f"{SHEET_T:.1f} (16 GA) CR sheet, A1008 CS"
DRAWING_NOTES = "1. BEND 90 DEG. " + BEND_NOTE
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"
HOLE_CALLOUT = "DRILL THRU"
RIVET_HOLE_CALLOUT = "DRILL AT ASSEMBLY THROUGH MHA-PD-014"
PAIR_CALLOUT = "2X"

# Marked model dimensions and the places the model authors on them
# (drawing-simplicity policy rule 2).  The second hole of each pair shares
# its size (and the screw holes one position) with the first (same globals)
# and prints once under the pair's "2X".  The rivet holes print their size
# only: their location is the hook's, taken at assembly.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "BracketProfile": {"BaseLength", "FlapHeight"},
    "Bracket": {"Width"},
    "ScrewHoleProfile": {"ScrewX1", "ScrewX2", "ScrewY", "ScrewDia"},
    "RivetHoleProfile": {"RivetDia"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "BracketProfile": {
        "BaseLength": BASE_LENGTH_PLACES,
        "FlapHeight": FLAP_HEIGHT_PLACES,
    },
    "Bracket": {"Width": WIDTH_PLACES},
    "ScrewHoleProfile": {
        "ScrewX1": POSITION_PLACES,
        "ScrewX2": POSITION_PLACES,
        "ScrewY": POSITION_PLACES,
        "ScrewDia": HOLE_PLACES,
    },
    "RivetHoleProfile": {"RivetDia": HOLE_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}
# Dimensions carrying the explicit ± position band (the rest print their
# title-block row or the drilled band).
POSITION_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "ScrewHoleProfile": ("ScrewX1", "ScrewX2", "ScrewY"),
}

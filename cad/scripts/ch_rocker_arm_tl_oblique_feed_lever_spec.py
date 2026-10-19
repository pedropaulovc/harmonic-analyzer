r"""Pure-data contract for the oblique-trammel jig's feed lever (MHA-CH-06-TL-26).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The
operator swings the carrier plate (MHA-CH-06-TL-21) on its two pivot pins by
this lever while the spindle cuts the strap's R800/R816 edges. The lever is
bolted flat on the carrier's top face at the middle of its -Y edge and runs
out toward the operator (carrier -Y), held by two 5/16-18 UNC SHCS into the
carrier's tapped lever stations ``carrier.LEVER_HOLES``.

Material and stock: 6061-T6 aluminium flat bar 1/2 x 1 in (12.70 x 25.40),
sawn to 300 long. Width and thickness stay as bought; only the length, the
two holes and the grip-end corners are machined.

Frame (SolidWorks model, and the ``PRECHIPS_SOLIDS`` frame): origin at the
lever's inner end, on its bottom face (the face on the carrier) and its back
long side. +X along the lever toward the operator (carrier -Y), +Y up through
the 12.70 thickness (carrier +Z), the 25.40 width along -Z (Z 0 to
-LEVER_WIDTH). The bolt holes lie on the mid-width line Z = -HOLE_Y, over the
carrier's X = 0. The inner end sits at carrier Y = ``carrier.LEVER_INNER_END_Y``
(-15), so a carrier station (0, y) is lever X = -15 - y. Overall stock in this
frame: X 0 to 300, Y 0 to 12.70, Z 0 to -25.40.

Holes: the stations are read from the carrier spec, never retyped (TrammelJig
ruling 2026-10-16: carrier (0, -22) and (0, -38), 16 pitch); they land at
lever X 7 and 23. Each is a native Hole Wizard 5/16 screw clearance, normal
fit (Ø8.74), THRU (fastener policy: UNC wizard holes everywhere). The screws
locate in the carrier's threads and the lever only has to clear them, so no
band is tighter than the title block. Rule 18 is the carrier's (its tapped
plate). The two 5/16-18 SHCS heads (Ø0.469 in max, ASME B18.3) stand 4.09
apart on the carrier's 16 pitch; the gap is read from the carrier stations,
not from the lever's bands, because the clearance holes float on the screws.

Rule 17 (walls, 2.0 target, 1.5 floor) at worst case: each station at its
two-place title-block band, the drilled hole at its title-block oversize:
inner hole to inner end 2.07, hole to hole 6.14, hole to the back side 7.77,
to the front side (stock width at its one-place band) 6.97.

Grip end: both plan corners broken R6 for the hand. No tight bands.
"""

from __future__ import annotations

from typing import Any

import ch_rocker_arm_tl_oblique_carrier_spec as carrier
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
_X = printed_band_mm(1)
_XX = printed_band_mm(2)
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(), 0.0)

# --- Lever: 6061-T6 1/2 x 1 in flat, sawn to length ----------------------
LEVER_LENGTH = 300.0
LEVER_WIDTH = round(1.0 * INCH, 9)  # 25.4 stock
LEVER_THICK = round(0.5 * INCH, 9)  # 12.7 stock
SIZE_PLACES = 1
THICK_PLACES = 2

# --- Bolt holes: on the carrier's lever stations ------------------------
if any(abs(x) > 1e-9 for x, _y in carrier.LEVER_HOLES):
    raise AssertionError("carrier lever stations are off the lever centre line")
HOLE_X: tuple[float, ...] = tuple(
    round(carrier.LEVER_INNER_END_Y - y, 9) for _x, y in carrier.LEVER_HOLES
)
HOLE_Y = round(LEVER_WIDTH / 2.0, 9)  # 12.7 from the back long side
HOLE_X_PLACES = 2
HOLE_Y_PLACES = 2
SCREW_THREAD = "5/16-18"
SCREW_HEAD_DIA_MAX = round(0.469 * INCH, 9)  # ASME B18.3 5/16 SHCS head
CLEARANCE_SPEC = HoleSpec("clearance", "5/16", fit="normal")
HOLE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)  # 8.738
HEAD_GAP = abs(HOLE_X[1] - HOLE_X[0]) - SCREW_HEAD_DIA_MAX
if HEAD_GAP < 2.0:
    raise AssertionError(f"feed lever SHCS heads gap {HEAD_GAP:.2f} < 2.0")

# --- Grip end: both plan corners broken -----------------------------------
CORNER_R = 6.0
CORNER_PLACES = 1

_HOLE_R_MAX = (HOLE_DIA + DRILLED_BAND[0]) / 2.0
_WIDTH_MIN = LEVER_WIDTH - _X
WALLS_MM: dict[str, float] = {
    "inner hole to inner end": HOLE_X[0] - _XX - _HOLE_R_MAX,
    "hole to hole": (HOLE_X[1] - _XX) - (HOLE_X[0] + _XX) - 2.0 * _HOLE_R_MAX,
    "hole to back side": HOLE_Y - _XX - _HOLE_R_MAX,
    "hole to front side": _WIDTH_MIN - (HOLE_Y + _XX) - _HOLE_R_MAX,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < 2.0:
        raise AssertionError(
            f"feed lever {_wall} wall {_mm:.3f} under drawing-guidelines.md rule 17"
        )

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LeverProfile": {"LeverLength", "LeverWidth"},
    "Lever": {"LeverThick"},
    "BoltHoles": {"Hole1X", "Hole2X", "Hole1Y"},
    "GripCorner": {"GripCornerR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LeverProfile": {"LeverLength": SIZE_PLACES, "LeverWidth": SIZE_PLACES},
    "Lever": {"LeverThick": THICK_PLACES},
    "BoltHoles": {
        "Hole1X": HOLE_X_PLACES,
        "Hole2X": HOLE_X_PLACES,
        "Hole1Y": HOLE_Y_PLACES,
    },
    "GripCorner": {"GripCornerR": CORNER_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked feed lever dimension needs authored places")
for _name, _value in (
    ("LeverLength", LEVER_LENGTH),
    ("LeverWidth", LEVER_WIDTH),
    ("LeverThick", LEVER_THICK),
    ("Hole1X", HOLE_X[0]),
    ("Hole2X", HOLE_X[1]),
    ("Hole1Y", HOLE_Y),
    ("GripCornerR", CORNER_R),
):
    if abs(_value - round(_value, DRAWING_PRECISION_BY_NAME[_name])) > 1e-9:
        raise AssertionError(f"feed lever {_name} {_value} does not print as modelled")

# Width and thickness are the bar as bought.
CALLOUTS_BELOW = {"LeverWidth": "STOCK", "LeverThick": "STOCK"}
# Both holes stand on the one Y station the part prints (Hole1Y); the one
# printed fillet stands for both corners. A custom prefix replaces
# SolidWorks' own "R", so it carries it (draw_pd_guide_lock).
DIMENSION_PREFIXES = {"Hole1Y": "2X ", "GripCornerR": "2X R"}
HOLE_CALLOUT_PROCESS = "DRILL"

SURFACE_FINISHES = ()
DRAWING_NOTES = ""
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"


_MEASURED = {
    "status": "measured",
    "by": "placeholder (realistic, remeasure: #1413)",
    "date": "2026-10-16",
    "instrument": (
        "digital calipers, height gauge and indicator; physical component sizes/fit only"
    ),
}


def _hole(name: str, x: float) -> dict[str, Any]:
    return {
        "name": name,
        "shape": "cylinder",
        "at_mm": [x, 0.0, -HOLE_Y],
        "axis": [0.0, 1.0, 0.0],
        "dia_mm": HOLE_DIA,
        "length_mm": LEVER_THICK,
        "void": True,
        "cuts": ["feed lever"],
        "measured": dict(_MEASURED),
    }


# The lever as made, in the model frame above; the corner radii are left to
# the CAD part.
PRECHIPS_SOLIDS: list[dict[str, Any]] = [
    {
        "name": "feed lever",
        "shape": "box",
        "at_mm": [0.0, 0.0, -LEVER_WIDTH],
        "size_mm": [LEVER_LENGTH, LEVER_THICK, LEVER_WIDTH],
        "note": (
            "MHA-CH-06-TL-26, 6061-T6 1/2 x 1 flat; bolted on the carrier "
            "(MHA-CH-06-TL-21) top by 2 x 5/16-18 SHCS"
        ),
        "measured": dict(_MEASURED),
    },
    *(_hole(f"bolt hole {index}", x) for index, x in enumerate(HOLE_X, start=1)),
]

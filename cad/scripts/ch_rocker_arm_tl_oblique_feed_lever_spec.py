r"""Pure-data contract for the oblique-trammel jig's feed lever (MHA-CH-06-TL-26).

Shop fixture, not a machine part (cad/docs/subsystem-identities.md). The
operator swings the carrier plate (MHA-CH-06-TL-21) on its two pivot pins by
this lever while the spindle cuts the strap's R800/R816 edges. The lever is
bolted flat on the carrier's top face at the middle of its -Y edge and runs
out toward the operator (carrier -Y), held by two 5/16-18 UNC SHCS into the
carrier's tapped lever stations ``carrier.LEVER_HOLES``.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths
stay physical millimetres, each the exact millimetres of its printed inch
value.

Material and stock: 6061-T6 aluminium flat bar 1/2 x 1 in, sawn to 11.8
long. Width and thickness stay as bought and print their stock fractions as
references, the supplier's band governing (``WIDTH_STOCK_BAND``); only the
length, the two holes and the grip-end corners are machined.

Frame (SolidWorks model, and the ``PRECHIPS_SOLIDS`` frame): origin at the
lever's inner end, on its bottom face (the face on the carrier) and its back
long side. +X along the lever toward the operator (carrier -Y), +Y up through
the 1/2 thickness (carrier +Z), the 1 width along -Z (Z 0 to -LEVER_WIDTH).
The bolt holes lie on the mid-width line Z = -HOLE_Y, over the carrier's
X = 0. The inner end sits at carrier Y = ``carrier.LEVER_INNER_END_Y``
(-.59), so a carrier station (0, y) is lever X = -.59 - y.

Holes: the stations are read from the carrier spec, never retyped (TrammelJig
ruling 2026-10-16, on the inch grid: carrier y -.87 and -1.50); they land at
lever X .28 and .91. Each is a native Hole Wizard 5/16 screw clearance, normal
fit (Ø.344), THRU (fastener policy: UNC wizard holes everywhere). The screws
locate in the carrier's threads and the lever only has to clear them, so no
band is tighter than the title block. Rule 18 is the carrier's (its tapped
plate). The two 5/16-18 SHCS heads (Ø.469 max, ASME B18.3) stand ``HEAD_GAP``
apart on the carrier's pitch; the gap is read from the carrier stations, not
from the lever's bands, because the clearance holes float on the screws.

Rule 17 (walls, .080 target, .060 floor) at worst case: each station at its
two-place title-block band, the drilled hole at its title-block oversize, the
stock width at its supplier band (``WALLS_MM``).

Grip end: both plan corners broken R.2 for the hand. No tight bands; the
overall length, read by no fit or wall, takes the title block's .X.
"""

from __future__ import annotations

from typing import Any

import _config
import ch_rocker_arm_tl_oblique_carrier_spec as carrier
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import drilled_oversize_mm, printed_band_mm

INCH = 25.4
UNIT = drawing_unit(
    "parts/ch-rocker-arm-tl-oblique-feed-lever",
    _config.parts("ch-rocker-arm-tl-oblique-feed-lever"),
)
_XX = printed_band_mm(2, unit=UNIT)
# Title-block DRILLED HOLES: plus allowance, zero minus (_printed_tolerance).
DRILLED_BAND = (drilled_oversize_mm(unit=UNIT), 0.0)

# --- Lever: 6061-T6 1/2 x 1 in flat, sawn to length ----------------------
LEVER_LENGTH = 299.72  # 11.8
LEVER_WIDTH = round(1.0 * INCH, 9)  # 1 stock
LEVER_THICK = round(0.5 * INCH, 9)  # 1/2 stock
# OnlineMetals' 6061-T6511 extruded rectangle bar
# (https://www.onlinemetals.com/en/aluminum-tolerances): 1.000-1.499 ±.012,
# .500-.749 ±.009. Both sizes print as stock references.
WIDTH_STOCK_BAND = 0.3048  # .012
THICK_STOCK_BAND = 0.2286  # .009
STOCK_FRACTION_DENOMINATORS = {"LeverWidth": 1, "LeverThick": 2}  # (1), (1/2)
SIZE_PLACES = 1  # the overall length
STOCK_PLACES = 2
THICK_PLACES = STOCK_PLACES

# --- Bolt holes: on the carrier's lever stations ------------------------
if any(abs(x) > 1e-9 for x, _y in carrier.LEVER_HOLES):
    raise AssertionError("carrier lever stations are off the lever centre line")
HOLE_X: tuple[float, ...] = tuple(
    round(carrier.LEVER_INNER_END_Y - y, 9) for _x, y in carrier.LEVER_HOLES
)  # .28, .91
HOLE_Y = round(LEVER_WIDTH / 2.0, 9)  # .50 from the back long side
HOLE_X_PLACES = 2
HOLE_Y_PLACES = 2
SCREW_THREAD = "5/16-18"
SCREW_HEAD_DIA_MAX = round(0.469 * INCH, 9)  # ASME B18.3 5/16 SHCS head
CLEARANCE_SPEC = HoleSpec("clearance", "5/16", fit="normal")
HOLE_DIA = blind_cut_dia_mm(CLEARANCE_SPEC)  # .344
HOLE_CALLOUT_PRECISION = {"hw-diam": 3}  # every Hole Wizard length prints .XXX
HEAD_GAP = abs(HOLE_X[1] - HOLE_X[0]) - SCREW_HEAD_DIA_MAX
if HEAD_GAP < 2.0:
    raise AssertionError(f"feed lever SHCS heads gap {HEAD_GAP:.2f} < 2.0")

# --- Grip end: both plan corners broken -----------------------------------
CORNER_R = 5.08  # .2
CORNER_PLACES = 1

_HOLE_R_MAX = (HOLE_DIA + DRILLED_BAND[0]) / 2.0
_WIDTH_MIN = LEVER_WIDTH - WIDTH_STOCK_BAND
WALLS_MM: dict[str, float] = {
    "inner hole to inner end": HOLE_X[0] - _XX - _HOLE_R_MAX,
    "hole to hole": (HOLE_X[1] - _XX) - (HOLE_X[0] + _XX) - 2.0 * _HOLE_R_MAX,
    "hole to back side": HOLE_Y - _XX - _HOLE_R_MAX,
    "hole to front side": _WIDTH_MIN - (HOLE_Y + _XX) - _HOLE_R_MAX,
}
for _wall, _mm in WALLS_MM.items():
    if _mm < WALL_TARGET_MM:
        raise AssertionError(
            f"feed lever {_wall} wall {_mm:.3f} under drawing-guidelines.md rule 17"
        )

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "LeverProfile": {"LeverLength", "LeverWidth"},
    # The stock thickness: a reference sketch, not the extrusion's depth,
    # whose import has no drawing-view attachment (farm r1).
    "LeverThickReference": {"LeverThick"},
    "BoltHoles": {"Hole1X", "Hole2X", "Hole1Y"},
    "GripCorner": {"GripCornerR"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "LeverProfile": {"LeverLength": SIZE_PLACES, "LeverWidth": STOCK_PLACES},
    "LeverThickReference": {"LeverThick": THICK_PLACES},
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
    ("Hole1X", HOLE_X[0]),
    ("Hole2X", HOLE_X[1]),
    ("Hole1Y", HOLE_Y),
    ("GripCornerR", CORNER_R),
):
    _places = DRAWING_PRECISION_BY_NAME[_name]
    if abs(_value / INCH - round(_value / INCH, _places)) > 1e-9:
        raise AssertionError(f"feed lever {_name} {_value} does not print as modelled")

# Width and thickness are the bar as bought: their stock references carry
# STOCK and the supplier's band under them (rule 1, machinist review).
STOCK_DIMENSIONS = frozenset({"LeverWidth", "LeverThick"})
STOCK_CALLOUTS = {
    name: "STOCK\n±" + f"{band / 25.4:.3f}".lstrip("0")
    for name, band in (
        ("LeverWidth", WIDTH_STOCK_BAND),
        ("LeverThick", THICK_STOCK_BAND),
    )
}
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

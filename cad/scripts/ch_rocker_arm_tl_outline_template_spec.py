r"""Pure-data contract for the rocker arm's outline template (MHA-CH-006-TL-13).

Shop gauge, not a machine part (cad/docs/subsystem-identities.md). An annealed
O1 plate carrying the rocker arm's finished outline: the R800 top and R816
bottom arcs about the pivot, the radial tip lands and the tapered ends, plus a
locating hole for a pin gauge in the arm's reamed pivot bore. The arm is
scribed from it (S5) and its outline is checked against it (S7: top-edge
height, radii, arc lengths, tip lands).

Every edge derives from the rocker's own CAD source (``ch_rocker_arm_spec``),
never from a render. The one deliberate offset: the whole arc system sits
0.25 higher than the rocker model's nominal. The rocker print lets both arcs
come out 0..+0.5 high (``ch_rocker_arm_spec.TOP_EDGE_BAND``, printed as a
0.5 surface profile, outside on the top arc and inside on the bottom one), so
the template aims at the middle of that zone and leaves its whole width to
the filing that follows it.

Frame: origin on the pivot-hole axis in the face laid on the arm, +Y toward
the arcs' common centre (the mirror line is the Y axis), +X toward the
rocker's connecting-rod end, the plate Z0..THICK.
"""

from __future__ import annotations

import math

import ch_rocker_arm_spec as rocker
from _printed_tolerance import printed_band_mm

R_TOP = rocker.R_TOP
R_BOTTOM = rocker.R_BOTTOM

# The aim: the middle of the rocker's one-sided top-edge band.
_ROCKER_TOP_LOW = rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[1]
_ROCKER_TOP_HIGH = rocker.TOP_EDGE_ABOVE_PIVOT + rocker.TOP_EDGE_BAND[0]
TOP_ABOVE_PIVOT = round((_ROCKER_TOP_LOW + _ROCKER_TOP_HIGH) / 2.0, 2)  # 8.25
CENTER_Y = TOP_ABOVE_PIVOT + R_TOP  # 808.25
BOTTOM_BELOW_PIVOT = round(R_BOTTOM - CENTER_Y, 2)  # 7.75
# The rocker's bottom arc rides the same concentric zone: its nominal sits
# ARM_DEPTH under the top arc, and the band moves both arcs together.
_ROCKER_BOTTOM_BELOW = rocker.ARM_DEPTH - rocker.TOP_EDGE_ABOVE_PIVOT  # 8.0
_ROCKER_BOTTOM_LOW = _ROCKER_BOTTOM_BELOW - rocker.TOP_EDGE_BAND[0]
_ROCKER_BOTTOM_HIGH = _ROCKER_BOTTOM_BELOW - rocker.TOP_EDGE_BAND[1]
if abs(R_BOTTOM - R_TOP - rocker.ARM_DEPTH) > 1e-9:
    raise AssertionError("rocker arcs are no longer ARM_DEPTH apart")
if abs(TOP_ABOVE_PIVOT + BOTTOM_BELOW_PIVOT - rocker.ARM_DEPTH) > 1e-9:
    raise AssertionError(
        "template arcs are no longer ARM_DEPTH apart on the mirror line"
    )
if (
    abs(
        rocker.CENTER_Y
        - rocker.PIVOT_MID_Y
        + (TOP_ABOVE_PIVOT - rocker.TOP_EDGE_ABOVE_PIVOT)
        - CENTER_Y
    )
    > 1e-9
):
    raise AssertionError(
        "template arc centre is not the rocker's, raised by the aim offset"
    )

# Shop acceptance (inventory gauges.arm-outline-template, Pedro 2026-10-11):
# within +/-0.03 of nominal about the pivot. On the sheet it is the band on
# both apex heights, measured from the pin gauge in the hole.
APEX_BAND = (0.03, -0.03)
APEX_PLACES = 2
for _low, _high, _nominal in (
    (_ROCKER_TOP_LOW, _ROCKER_TOP_HIGH, TOP_ABOVE_PIVOT),
    (_ROCKER_BOTTOM_LOW, _ROCKER_BOTTOM_HIGH, BOTTOM_BELOW_PIVOT),
):
    if not _low < _nominal + APEX_BAND[1] < _nominal + APEX_BAND[0] < _high:
        raise AssertionError("template apex band leaves the rocker's arc zone")
    # The gauge spends at most a quarter of the zone it sets.
    if APEX_BAND[0] - APEX_BAND[1] > 0.25 * (_high - _low) + 1e-9:
        raise AssertionError(
            "template apex band spends more than a quarter of the rocker zone"
        )

# The arcs end where the rocker's do: its 11.5 in / 10.5 in arc lengths
# (``_ALPHA_TOP`` / ``_ALPHA_BOT`` half-angles), the end stations printed at
# three places and the model carrying the printed value. The half-angles are
# re-derived from the rounded stations so the sketch closes exactly.
END_PLACES = 3
TOP_END_X = round(R_TOP * math.sin(rocker._ALPHA_TOP), END_PLACES)  # 145.240
BOT_END_X = round(R_BOTTOM * math.sin(rocker._ALPHA_BOT), END_PLACES)  # 132.757
if (
    abs(TOP_END_X - rocker.TOP_END_X) > 0.5e-3
    or abs(BOT_END_X - rocker.BOT_END_X) > 0.5e-3
):
    raise AssertionError("template end stations drifted from the rocker's")
ALPHA_TOP = math.asin(TOP_END_X / R_TOP)
ALPHA_BOT = math.asin(BOT_END_X / R_BOTTOM)
TOP_END_Y = CENTER_Y - R_TOP * math.cos(ALPHA_TOP)  # 21.545
BOT_END_Y = CENTER_Y - R_BOTTOM * math.cos(ALPHA_BOT)  # 3.122
# Each tip land is radial (square to the top arc), TIP_FACE long, outward
# from the top arc's end; the tapered end runs from its foot to the bottom
# arc's end.
TIP_FACE = rocker.TIP_FACE  # 5.588 = 0.22 in, exact at three places
if abs(TIP_FACE - round(TIP_FACE, END_PLACES)) > 1e-9:
    raise AssertionError("tip land length no longer prints exactly at three places")
TIP_X = TOP_END_X + TIP_FACE * math.sin(ALPHA_TOP)  # 146.255
TIP_Y = TOP_END_Y - TIP_FACE * math.cos(ALPHA_TOP)  # 16.050
# The end stations print at three places: their band is about a quarter of
# the rocker's own two-place band on the same ends.
if printed_band_mm(END_PLACES) > 0.26 * printed_band_mm(2):
    raise AssertionError(
        "template end-station band spends more than a quarter of the rocker's"
    )

# Pivot locating hole: the rocker's Ø6.5 bore, reamed to H7 (+0.015/0) so
# a 0.2550 in class ZZ minus pin gauge (6.472-6.477) locates it in the arm's
# bore. The play it leaves stays inside the apex acceptance.
PIVOT_HOLE_DIA = rocker.PIVOT_HOLE_DIA
PIVOT_HOLE_BAND = (0.015, 0.0)
PIVOT_PLACES = 3
# The fit and its mate are named on the bore's own callout.
PIVOT_CALLOUT = "REAM, SLIP FIT ON PIN GAUGE"
# Both arcs' shared centre lies on the pivot bore's vertical centreline,
# CENTER_Y above the bore: off any sheet, so the radius callouts say so.
ARC_CENTER_CALLOUT = "CENTER ON PIVOT CL"
PIN_GAUGE_MIN = round((0.2550 - 0.0002) * 25.4, 3)  # 6.472
PIN_GAUGE_MAX = round(0.2550 * 25.4, 3)  # 6.477
if PIN_GAUGE_MAX >= PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[1]:
    raise AssertionError("pin gauge does not enter the template hole")
if PIN_GAUGE_MAX >= rocker.PIVOT_HOLE_DIA + rocker.PIVOT_HOLE_BAND[1]:
    raise AssertionError("pin gauge does not enter the rocker's pivot bore")
PIN_PLAY_MAX = round((PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0] - PIN_GAUGE_MIN) / 2.0, 4)
if PIN_PLAY_MAX >= APEX_BAND[0]:
    raise AssertionError("pin-gauge play in the template hole eats the whole apex band")

# Plate: O1 ground flat stock, 1/8 in, thickness as supplied.
THICK = 3.175
THICK_PLACES = 3
THICK_CALLOUT = "GROUND FLAT STOCK"
# drawing-guidelines.md rule 17 (walls and webs): the thinnest web, between the hole and the bottom arc.
WEB_MIN = round(
    BOTTOM_BELOW_PIVOT + APEX_BAND[1] - (PIVOT_HOLE_DIA + PIVOT_HOLE_BAND[0]) / 2.0, 4
)
if min(WEB_MIN, THICK - printed_band_mm(THICK_PLACES)) < 1.5 - 1e-9:
    raise AssertionError(
        "outline template falls under the drawing-guidelines.md rule 17 (walls and webs) floor"
    )


def outline_points(n: int = 200) -> list[tuple[float, float]]:
    """The closed outline, bottom arc rod->tail, tail tip, top arc tail->rod, rod tip."""
    points: list[tuple[float, float]] = []
    for i in range(n + 1):
        a = ALPHA_BOT - 2.0 * ALPHA_BOT * i / n
        points.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    points.append((-TIP_X, TIP_Y))
    for i in range(n + 1):
        a = -ALPHA_TOP + 2.0 * ALPHA_TOP * i / n
        points.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
    points.append((TIP_X, TIP_Y))
    return points


def outline_area() -> float:
    """Shoelace area of the outline (no hole), exact enough for the volume gate."""
    points = outline_points()
    area = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


PLATE_VOLUME = (outline_area() - math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2) * THICK

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "OutlineProfile": {
        "TopRadius",
        "BottomRadius",
        "TopTailX",
        "TopRodX",
        "BottomTailX",
        "BottomRodX",
        "RodTipLen",
        "TailTipLen",
    },
    "ApexReference": {"TopAbovePivot", "BottomBelowPivot"},
    "PivotHoleProfile": {"PivotDia"},
    "Plate": {"Thick"},
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "OutlineProfile": {
        "TopRadius": 2,
        "BottomRadius": 2,
        "TopTailX": END_PLACES,
        "TopRodX": END_PLACES,
        "BottomTailX": END_PLACES,
        "BottomRodX": END_PLACES,
        "RodTipLen": END_PLACES,
        "TailTipLen": END_PLACES,
    },
    "ApexReference": {"TopAbovePivot": APEX_PLACES, "BottomBelowPivot": APEX_PLACES},
    "PivotHoleProfile": {"PivotDia": PIVOT_PLACES},
    "Plate": {"Thick": THICK_PLACES},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError(
        "every marked outline-template dimension needs authored places"
    )
# Bands other than the title block's, keyed (feature, dimension).
DRAWING_BANDS: dict[tuple[str, str], tuple[float, float]] = {
    ("ApexReference", "TopAbovePivot"): APEX_BAND,
    ("ApexReference", "BottomBelowPivot"): APEX_BAND,
    ("PivotHoleProfile", "PivotDia"): PIVOT_HOLE_BAND,
}

DRAWING_NOTES = "\n".join(
    (
        "LAYOUT AND PROFILE GAUGE FOR THE ROCKER ARM.",
        "ARC AND TIP-LAND EDGES ARE SCRIBING EDGES: SHARP, EXEMPT FROM TITLE-BLOCK EDGE-BREAK REQUIREMENT.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW\nSCALE 1:4"

# prechips models a fixture as boxes and cylinders only, so the bound shop
# inventory carries the plate's envelope (its outline's extents by the plate
# thickness) with the pivot hole as a void, in this module's frame.
PRECHIPS_SOLIDS: list[dict[str, object]] = [
    {
        "name": "plate",
        "supply": "made",
        "shape": "box",
        "at_mm": [round(-TIP_X, 3), round(-BOTTOM_BELOW_PIVOT, 3), 0.0],
        "size_mm": [
            round(2.0 * TIP_X, 3),
            round(TOP_END_Y + BOTTOM_BELOW_PIVOT, 3),
            THICK,
        ],
        "note": "outline envelope; the arcs, tip lands and tapered ends are inside it",
    },
    {
        "name": "pivot-hole",
        "shape": "cylinder",
        "void": True,
        "at_mm": [0.0, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "dia_mm": PIVOT_HOLE_DIA,
        "length_mm": THICK,
        "locates": "pin gauge in the rocker's pivot bore",
    },
]

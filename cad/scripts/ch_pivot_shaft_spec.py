r"""Pure-data dimensional contract shared by the rocker pivot shaft (MHA-CH-05)
and its drawing.

A plain O.250 rod (user, 2026-10-10: the old turned shoulder and its reliefs
are gone). Hub 19 bears through a MHA-CH-VN-56 thrust washer on the north ear's
inner face and the MHA-CH-VN-54 spring pushes the bank north from the south ear
(``rocker_bank_layout``); the
shaft itself is held, axially and in rotation, by one #4-40 set screw down
through each MHA-CH-08 ear's arch apex, each biting a FLAT milled on the
shaft at that ear's mid-plane, so the cup never burrs the round the ear bore
runs on. The body carries the 20 rocker hubs and journals in both ears, and
both ends are domed DOME_HEIGHT proud of their ears, like the cylinder
arbor's ends.

The shop faces and domes both ends to the overall length, tip to tip; its
cylinder is the span over both installed MHA-CH-08 ears
(``rocker_bank_layout.PIVOT_SHAFT_LENGTH``), and fit-up sets the north tip
DOME_HEIGHT proud of the north ear, so nothing is cut at assembly. Each flat
is stationed from its own end's tip (drawing-guidelines.md rule 11: each
end's features from that end, the overall length tying the two), so the bar
is the same either way round; the layout checks the flats at the worst case.
This spec cannot import the layout, which reads the flats from here.

Part frame: axis along Z, origin on the axis at the NORTH end of the cylinder,
the body running toward -Z, the flats facing +Y. It is modelled as one
Right-plane half-profile revolved (sketch +x -> model -Z), so the diameter
imports into the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)), one revolved crown at
each end, and one Right-plane cut for both flats, whose length, across-flat
and stations, with the overall length between the two tips, import into the
same view.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each the exact decimal of its printed inch value; the
overall length is the ears' span plus both domes snapped to its .XX
(``rocker_bank_layout``).
"""

from __future__ import annotations

import math

import _config
from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from ch_pivot_bracket_spec import EAR_T, SET_SCREW_POINT_DIA

UNIT = drawing_unit("parts/ch-pivot-shaft", _config.parts("ch-pivot-shaft"))
MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_DIA_BAND = SHAFT_H
DOME_HEIGHT = 1.524  # .06: both ends, like the cylinder arbor's (user, #743 Q4)
DOME_SPHERE_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + DOME_HEIGHT**2) / (2.0 * DOME_HEIGHT)
if not 0.0 < DOME_HEIGHT <= SHAFT_DIA / 2.0:
    raise AssertionError("an end crown must be a dome, never past a hemisphere")

DOME_CALLOUT = "BOTH ENDS"
# Each flat prints once, stationed from its own end's tip.
FLAT_STATION_CALLOUT = "BOTH ENDS"

# The title block's printed .XX band, which an accepted part is checked
# against.
LINEAR_2PL = printed_band_mm(2, unit=UNIT)
LENGTH_BAND = LINEAR_2PL  # the overall length, tip to tip, prints at .XX

# --- set-screw flats (user, 2026-10-10) ----------------------------------------
# One flat under each ear's apex screw, on the ear's mid-plane: half an ear in
# from its cylinder end (the north one's model station), which is DOME_HEIGHT
# more from that end's tip, the face the shop measures it from.
NORTH_FLAT_STATION = EAR_T / 2.0
FLAT_TIP_STATION = NORTH_FLAT_STATION + DOME_HEIGHT  # .22, each from its tip
FLAT_STATION_BAND = LINEAR_2PL  # stations print at .XX
# The cup the flat must take whole: the screw's 45 deg x one-pitch point.
SET_SCREW_CUP_DIA = SET_SCREW_POINT_DIA  # 1.575
# The across-flat, which a micrometer reads, prints at .XX like every other
# size a set-screw seat needs (machinist review: three places served no
# function). The depth runs .030...050: at its shallowest the flat's chord
# still takes the cup with over 1.2 mm to spare each side, the screw itself
# rolling the flat square under it as it is driven; at its deepest it takes
# under a quarter of the rod.
FLAT_AF = 5.334  # .21
FLAT_DEPTH = SHAFT_DIA - FLAT_AF  # .04
FLAT_DEPTH_RANGE = (FLAT_DEPTH - LINEAR_2PL, FLAT_DEPTH + LINEAR_2PL)


def flat_chord(depth: float) -> float:
    """The flat's width across the rod at ``depth``."""
    radius = SHAFT_DIA / 2.0
    return 2.0 * math.sqrt(radius**2 - (radius - depth) ** 2)


if flat_chord(FLAT_DEPTH_RANGE[0]) < SET_SCREW_CUP_DIA + 2.0 * 0.5:
    raise AssertionError("a shallow flat is too narrow for the set-screw cup")
if FLAT_DEPTH_RANGE[1] >= SHAFT_DIA / 4.0:
    raise AssertionError("a deep flat takes a quarter of the rod")
# Length: .24 at .XX. The cup must stay wholly on the flat over the fit-up's
# axial wander, which at the far (south) ear also carries the overall
# length's band, the north tip being the one set, and no rocker hub may ride
# over the flat's edge (rocker_bank_layout checks both).
FLAT_LENGTH = 6.096  # .24
FLAT_LENGTH_RANGE = (FLAT_LENGTH - LINEAR_2PL, FLAT_LENGTH + LINEAR_2PL)

# Probe station (part z, mm) that names the O.250 face: the body clear of the
# north flat.
BODY_PROBE_Z_MM = -(EAR_T + 10.0)

# drawing-guidelines.md rule 5 (avoid excessive GD&T): a shaft carries no frames and no datums. drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): roughness only on
# the running face -- the round the 20 hubs rock on and the two ears journal.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_bearing",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=BODY_PROBE_Z_MM),
        display_unit=UNIT,
    ),
)

# The diameter lives on the revolved half-profile, the dome height and its
# sphere radius on the north crown's own profile (the south crown is driven by
# the same globals and prints as "BOTH ENDS"), the flats and the overall
# length on the flats' cut profile, whose construction axis runs tip to tip so
# the length and both stations start on a tip. The radius prints as a
# spherical REFERENCE: the height on the toleranced diameter fixes it, and it
# tells the shop the crown is a sphere (PR #1317 machinist review: the height
# alone left the profile open).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia"},
    "NorthCapProfile": {"DomeHeight", "Radius"},
    "FlatProfile": {"OverallLength", "FlatLength", "FlatAF", "FlatStation"},
}

# Decimal places are the tolerance (drawing-guidelines.md rule 3 (decimal places carry the tolerance)). The O.D. carries the
# running band at four places (.2500 +.0000/-.0008). The dome height and its
# reference radius print at .XX; the overall length, the stations and the
# flat's length and across-flat hold each cup on its flat at .XX.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 4},
    "NorthCapProfile": {"DomeHeight": 2, "Radius": 2},
    "FlatProfile": {
        "OverallLength": 2,
        "FlatLength": 2,
        "FlatAF": 2,
        "FlatStation": 2,
    },
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
) or len(_PRECISION_NAMES) != sum(len(names) for names in DRAWING_DIMENSIONS.values()):
    raise AssertionError(
        "DRAWING_PRECISION and DRAWING_DIMENSIONS must name the same dims"
    )
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# Part-specific facts a machinist cannot read off the views (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
# A 6.4:.25 slender bar is turned between centres; both flats face the same
# way, because one screw on each ear sets the shaft's roll.
DRAWING_NOTES = "\n".join(
    (
        "CENTRES OK.",
        "BOTH FLATS IN LINE, ONE SIDE.",
    )
)
# The title block declares 1:1, so the off-scale pictorial must say so.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

V_DOME = math.pi * DOME_HEIGHT**2 * (3.0 * DOME_SPHERE_RADIUS - DOME_HEIGHT) / 3.0


def segment_area(depth: float) -> float:
    """The rod's circular segment a flat ``depth`` deep removes."""
    radius = SHAFT_DIA / 2.0
    return radius**2 * math.acos((radius - depth) / radius) - (radius - depth) * (
        flat_chord(depth) / 2.0
    )


V_FLAT = segment_area(FLAT_DEPTH) * FLAT_LENGTH  # each flat

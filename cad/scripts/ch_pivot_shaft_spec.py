r"""Pure-data dimensional contract shared by the rocker pivot shaft (MHA-CH-005)
and its drawing.

A plain O6.35 rod (user, 2026-10-10: the old turned shoulder and its reliefs
are gone). Hub 19 bears through a MHA-CH-009 thrust washer on the north ear's
inner face and the MHA-VN-053 spring pushes the bank north from the south ear
(``rocker_bank_layout``); the
shaft itself is held, axially and in rotation, by one #4-40 set screw down
through each MHA-CH-008 ear's arch apex, each biting a FLAT milled on the
shaft at that ear's mid-plane, so the cup never burrs the round the ear bore
runs on. The body carries the 20 rocker hubs and journals in both ears, and
both ends are domed DOME_HEIGHT proud of their ears, like the cylinder
arbor's ends.

The cylinder IS the span over both installed MHA-CH-008 ears, which the fitter
measures, so the plain (south) end is cut and domed to fit. Its nominal is the
bank's geometry (``rocker_bank_layout.PIVOT_SHAFT_LENGTH``), as is the south
flat's station; the layout checks the north one against NORTH_FLAT_STATION.
This spec cannot import the layout, which reads the flats from here.

Part frame: axis along Z, origin on the axis at the NORTH end of the cylinder,
the body running toward -Z, the flats facing +Y. It is modelled as one
Right-plane half-profile revolved (sketch +x -> model -Z), so the diameter
and length import into the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)), one revolved crown at
each end, and one Right-plane cut for both flats, whose length, across-flat
and stations import into the same view.
"""

from __future__ import annotations

import math

from _fit_shaft_h import SHAFT_H
from _gtol_cylinder import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from ch_pivot_bracket_spec import EAR_T, SET_SCREW_POINT_DIA


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_DIA_BAND = SHAFT_H
DOME_HEIGHT = 0.0625 * MM_PER_IN  # 1/16 both ends (was 1.5), like the cylinder arbor's (user, #743 Q4)
DOME_SPHERE_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + DOME_HEIGHT**2) / (2.0 * DOME_HEIGHT)
if not 0.0 < DOME_HEIGHT <= SHAFT_DIA / 2.0:
    raise AssertionError("an end crown must be a dome, never past a hemisphere")

# The print's one statement of how the length is set (the channel assembly
# steps carry the same measurement).
LENGTH_CALLOUT = "CUT TO FIT: SPAN OVER BOTH MHA-CH-008 EARS"
DOME_CALLOUT = "BOTH ENDS"

# The title block's PRINTED bands, which an accepted part is checked against
# (not the inch grades behind them: .XX prints +/-0.51, not 0.508). Literals,
# pinned to the title block by test_ch_pivot_shaft_drawing: reading _config
# here would put title_block on rocker_bank_layout's and every channel
# part's recipe.
LINEAR_1PL = 0.8
LINEAR_2PL = 0.51
LINEAR_3PL = 0.13

# --- set-screw flats (user, 2026-10-10) ----------------------------------------
# One flat under each ear's apex screw, on the ear's mid-plane: the north one
# half an ear in from the north end (the end fit-up sets flush with the north
# ear's outer face), the south one at the layout's station.
NORTH_FLAT_STATION = EAR_T / 2.0
FLAT_STATION_BAND = LINEAR_2PL  # stations print at .XX
# The cup the flat must take whole: the screw's 45 deg x one-pitch point.
SET_SCREW_CUP_DIA = SET_SCREW_POINT_DIA  # 1.575
# Depth: .020 in (was 0.5), the common set-screw flat on a 1/4 shaft (about
# 0.08D); a 3-place inch decimal because 1/32 (0.79) would move this sub-1/4
# feature +56%. It prints as the across-flat (.230), which a micrometer
# reads, at .XXX, so the depth runs 0.38..0.64; at its shallowest the flat's
# chord still takes the cup with 0.5 to spare each side, the screw itself
# rolling the flat square under it as it is driven.
FLAT_DEPTH = 0.020 * MM_PER_IN
FLAT_AF = SHAFT_DIA - FLAT_DEPTH  # 5.842 (.230)
FLAT_DEPTH_RANGE = (FLAT_DEPTH - LINEAR_3PL, FLAT_DEPTH + LINEAR_3PL)


def flat_chord(depth: float) -> float:
    """The flat's width across the rod at ``depth``."""
    radius = SHAFT_DIA / 2.0
    return 2.0 * math.sqrt(radius**2 - (radius - depth) ** 2)


if flat_chord(FLAT_DEPTH_RANGE[0]) < SET_SCREW_CUP_DIA + 2.0 * 0.5:
    raise AssertionError("a shallow flat is too narrow for the set-screw cup")
# Length: 3/16 (was 5.0) at .XX. The cup must stay wholly on the flat over
# the fit-up's axial wander (rocker_bank_layout checks it at the south ear,
# which .X could not hold once the north ear's thickness band joined the
# south chain), and no rocker hub may ride over the flat's edge (also
# checked there).
FLAT_LENGTH = 0.1875 * MM_PER_IN
FLAT_LENGTH_RANGE = (FLAT_LENGTH - LINEAR_2PL, FLAT_LENGTH + LINEAR_2PL)

# Probe station (part z, mm) that names the O6.35 face: the body clear of the
# north flat.
BODY_PROBE_Z_MM = -(EAR_T + 10.0)

# drawing-guidelines.md rule 5 (avoid excessive GD&T): a shaft carries no frames and no datums. drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): roughness only on
# the running face -- the round the 20 hubs rock on and the two ears journal.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_bearing",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=BODY_PROBE_Z_MM),
    ),
)

# The diameter and length live on the revolved half-profile, the dome height
# and its sphere radius on the north crown's own profile (the south crown is
# driven by the same globals and prints as "BOTH ENDS"), the flats on their
# one cut's profile. The radius prints as a spherical REFERENCE: the height
# on the toleranced diameter fixes it, and it tells the shop the crown is a
# sphere (PR #1317 machinist review: the height alone left the profile open).
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {"ShaftDia", "ShaftLength"},
    "NorthCapProfile": {"DomeHeight", "Radius"},
    "FlatProfile": {"FlatLength", "FlatAF", "NorthFlatStation", "SouthFlatStation"},
}

# Decimal places are the tolerance (drawing-guidelines.md rule 3 (decimal places carry the tolerance)). The O.D. carries the
# running band at three places (1/4 in = 6.350 exactly), the across-flat the
# depth band its sizing above assumes. The dome only has to read as a dome
# and the flat's length is checked at .XX. The stations hold each flat under
# its screw at .XX. The cylinder length is a REFERENCE the cut-to-fit callout
# governs: one place, like the dome's reference sphere radius.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {"ShaftDia": 3, "ShaftLength": 1},
    "NorthCapProfile": {"DomeHeight": 1, "Radius": 1},
    "FlatProfile": {
        "FlatLength": 2,
        "FlatAF": 3,
        "NorthFlatStation": 2,
        "SouthFlatStation": 2,
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
# A 159:6.35 slender bar is turned between centres; both flats face the same
# way, because one screw on each ear sets the shaft's roll; the plain end is
# cut and domed at assembly, so the shop supplies it long.
STOCK_LENGTH = 174.625  # 6-7/8 in (was 175)
DRAWING_NOTES = "\n".join(
    (
        "CENTRES OK.",
        "BOTH FLATS IN LINE, ONE SIDE.",
        f"SUPPLY {STOCK_LENGTH} LONG, PLAIN END UNCUT.",
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

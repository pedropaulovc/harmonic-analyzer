r"""Pure-data dimensional contract shared by the rocker pivot shaft (MHA-065)
and its drawing.

#743 PR2, Reading 1 (user, Q4): the shaft is held by the brackets, with no
keeper. It is turned from O10 bar and leaves an integral O10 x 1.5 SHOULDER
one ear thickness from its north end. The shoulder's north face bears on the
north ear's inner face, so the shaft cannot move north, and rocker 19's hub
bears on its south face. Southward the whole stack closes on the MHA-148
washer at the south ear. The north journal runs through the north ear, the
body carries the 20 rocker hubs and journals in the south ear, and both ends
are domed DOME_HEIGHT proud of their ears, like the cylinder arbor's ends.

The cylinder IS the span over both installed MHA-123 ears, which the fitter
measures, so the plain (south) end is cut and domed to fit. Its nominal is the
bank's geometry (``rocker_bank_layout.PIVOT_SHAFT_LENGTH``). This spec cannot
import the layout, which reads the shoulder from here.

Part frame: axis along Z, origin on the axis at the NORTH (shouldered) end of
the cylinder, the body running toward -Z. It is modelled as one Right-plane
half-profile revolved (sketch +x -> model -Z), so every turned diameter and
length imports into the side view (policy rule 7), plus one revolved crown at
each end.
"""

from __future__ import annotations

import math

from _fit_limits import SHAFT_H
from _gtol_spec import CylinderFace
from _surface_finish import MACHINED_UM, SurfaceFinishControl
from pivot_bracket_spec import EAR_T


MM_PER_IN = 25.4

SHAFT_DIA = 0.25 * MM_PER_IN
SHAFT_DIA_BAND = SHAFT_H
SHOULDER_DIA = 10.0  # the O10 bar it is turned from; = the rocker hub O.D.
SHOULDER_LENGTH = 1.5
JOURNAL_LENGTH = EAR_T  # shoulder face to the north end: one ear thickness
DOME_HEIGHT = 1.5  # both ends, like the cylinder arbor's (user, #743 Q4)
DOME_SPHERE_RADIUS = ((SHAFT_DIA / 2.0) ** 2 + DOME_HEIGHT**2) / (2.0 * DOME_HEIGHT)
if not 0.0 < DOME_HEIGHT <= SHAFT_DIA / 2.0:
    raise AssertionError("an end crown must be a dome, never past a hemisphere")

# The print's one statement of how the length is set (the channel assembly
# steps carry the same measurement).
LENGTH_CALLOUT = "CUT TO FIT: SPAN OVER BOTH MHA-123 EARS"
DOME_CALLOUT = "BOTH ENDS"

# Probe stations (part z, mm) that name each O6.35 face: the body just past
# the shoulder, and the north journal at mid-length.
BODY_PROBE_Z_MM = -(JOURNAL_LENGTH + SHOULDER_LENGTH + 10.0)
JOURNAL_PROBE_Z_MM = -JOURNAL_LENGTH / 2.0

# Rule 3: a shaft carries no frames and no datums. Rule 5: roughness only on
# the running faces -- the body the 20 hubs rock on (it also journals in the
# south ear) and the north journal in the north ear.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "pivot_bearing",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=BODY_PROBE_Z_MM),
    ),
    SurfaceFinishControl(
        "pivot_journal",
        MACHINED_UM,
        CylinderFace(SHAFT_DIA, contains_z_mm=JOURNAL_PROBE_Z_MM),
    ),
)

# Every printed dimension lives on the revolved half-profile, except the dome
# height, which the north crown's own profile owns (the south crown is driven
# by the same global and prints as "BOTH ENDS").
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "ShaftProfile": {
        "ShaftDia",
        "ShoulderDia",
        "ShaftLength",
        "ShoulderLength",
        "JournalLength",
    },
    "NorthCapProfile": {"DomeHeight"},
}

# Decimal places are the tolerance (policy rule 2). The O.D. carries the
# running band at three places (1/4 in = 6.350 exactly). The shoulder's O.D.
# and length stand the ear off the ch0/ch19 amplitude bars, judged at the
# .XX grade (test_rocker_bank_layout). The journal only has to bear in the
# ear and the dome only has to read as a dome: one place each. The cylinder
# length is a REFERENCE the cut-to-fit callout governs: one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "ShaftProfile": {
        "ShaftDia": 3,
        "ShoulderDia": 2,
        "ShaftLength": 1,
        "ShoulderLength": 2,
        "JournalLength": 1,
    },
    "NorthCapProfile": {"DomeHeight": 1},
}
_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if any(
    name not in DRAWING_DIMENSIONS.get(feature, frozenset())
    for feature, name in _PRECISION_NAMES
) or len(_PRECISION_NAMES) != sum(len(names) for names in DRAWING_DIMENSIONS.values()):
    raise AssertionError("DRAWING_PRECISION and DRAWING_DIMENSIONS must name the same dims")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

# Part-specific facts a machinist cannot read off the views (policy rule 6).
# The O.D. is a catalog stock size only on the body; the shoulder needs the
# O10 bar, and a 157:6.35 slender bar is turned between centres. The plain
# end is cut and domed at assembly, so the shop supplies it long.
STOCK_LENGTH = 175
DRAWING_NOTES = "\n".join(
    (
        "STOCK 10 BAR; CENTRES OK.",
        f"SUPPLY {STOCK_LENGTH} LONG, PLAIN END UNCUT.",
        "NO FLATS.",
    )
)
# The title block declares 1:1, so the off-scale pictorial must say so.
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

V_DOME = math.pi * DOME_HEIGHT**2 * (3.0 * DOME_SPHERE_RADIUS - DOME_HEIGHT) / 3.0

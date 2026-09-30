r"""Pure-data dimensional contract shared by the crank handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned, ebonized oak pear grip on the
crank-arm pivot: a waisted neck, a smooth twin-arc swell to the Ø21 max, and a
blunt butt.  User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-150 on a turned
tenon, and the bright disc at the butt is a flanged steel cup MHA-153 in a
counterbore, the pivot screw's slotted head recessed inside it.  The oak
therefore ends in a tenon at the crank end and a trimmed butt face with a
counterbore at the other.

After the machinist reviews (user rulings 2026-09-29): the tenon and the
counterbore are turned and bored to suit the ferrule and cup they take, the
handle's end play is fitted on the MHA-139 shoulder at assembly, so the oak's
lengths are routine (.X) sizes, and the butt grew (Ø10 -> Ø11.5 theoretical)
so the cup keeps 1.5 mm sections.

The pear silhouette is two internally-tangent arcs, so the swell/neck/butt
DIAMETERS derive from the profile geometry and cannot be marked without
over-defining; the drawing dimensions the clean AXIAL stations from the
tenon shoulder (datum B) and gives the diameters as a basic-profile note.
The nominals drive the part's named equation globals AND the drawing's
coordinate math (``test_crank_handle_drawing.py``).

Frame: the handle axis is local +X and x=0 is the ferrule's arm-bearing face,
the plane the drive train seats on the arm.  No oak reaches x=0: the tenon
stops short of the ferrule's end, so only brass bears on the arm.
"""

from __future__ import annotations

import math

from crank_hub_geometry import GENERAL_1PL_TOL_MM
from crank_handle_butt_cup_spec import (
    BODY_DIA as CUP_BODY_DIA,
    BODY_DIA_TOL as CUP_BODY_DIA_TOL,
    BODY_LENGTH_MAX as CUP_BODY_LENGTH_MAX,
    FLANGE_DIA as CUP_FLANGE_DIA,
    FLANGE_THICKNESS as CUP_FLANGE_THICKNESS,
)
from crank_handle_ferrule_spec import (
    BORE_DIA as FERRULE_BORE_DIA,
    LENGTH as FERRULE_LENGTH,
    TENON_GLUE_LINE as FERRULE_TENON_GLUE_LINE,
)

# 2026-09-02 user re-read of the pass-2 model against ch11 p.14 and the ch30
# p002 front view: overall 58 from the arm face, swell 21 across at 0.62 of
# the length, neck Ø11.  The basic profile still runs the whole 58: the
# ferrule and the cup flange now take its two ends.
HANDLE_LENGTH = 58.0  # basic: ferrule arm face to cup flange face
HANDLE_MAX_DIA = 21.0  # max diameter at the swell
NECK_R = 5.5  # waist at the tenon shoulder (neck Ø11)
PEAK_X = 36.0  # axial station of the maximum diameter, from x=0
# Theoretical butt radius at HANDLE_LENGTH.  Ø10 in the photo re-derive; grown
# (user rulings 2026-09-29, MHA-153 and MHA-022 reviews) to Ø14 so the oak
# round the cup counterbore keeps 1.5 mm at its worst case and the trim face
# is as wide as the cup flange.
CAP_R = 7.0
# The turned grip contour's allowance, on diameter, against its two arcs: the
# wood grip is checked by eye and template, not by a profile frame (MHA-022
# review, user ruling 2026-09-29).
CONTOUR_ALLOWANCE_DIA = 0.5
PIVOT_BORE_DIA = 6.125  # final reamed bore limits 6.10-6.15
# Symmetric ream band about the mid nominal: 6.15 MAX / 6.10 MIN.
PIVOT_BORE_BAND = (0.025, -0.025)

# The tenon shoulder (datum B) is where the ferrule seats, FERRULE_LENGTH from
# the arm face.
SHOULDER_X = FERRULE_LENGTH
# The tenon is turned to suit the actual MHA-150 bore for an epoxy line; the
# model carries the size that line gives on a nominal bore.
TENON_GLUE_LINE = FERRULE_TENON_GLUE_LINE
TENON_DIA = FERRULE_BORE_DIA - sum(TENON_GLUE_LINE) / 2.0
# Short enough that the longest tenon stops short of the shortest ferrule's
# arm face, so the oak never bears on the arm.
TENON_LENGTH = 5.0
TENON_X0 = SHOULDER_X - TENON_LENGTH

# The butt is trimmed where the cup flange seats: the flange face lands on the
# basic HANDLE_LENGTH.  Wood from datum B to the trim face, a routine size.
TRIM_X = HANDLE_LENGTH - CUP_FLANGE_THICKNESS
WOOD_LENGTH = TRIM_X - SHOULDER_X
# The counterbore is bored to suit the actual MHA-153 body for an epoxy line.
COUNTERBORE_GLUE_LINE = (0.05, 0.15)
COUNTERBORE_DIA = CUP_BODY_DIA + sum(COUNTERBORE_GLUE_LINE) / 2.0
COUNTERBORE_DEPTH = 9.0
TENON_R = TENON_DIA / 2.0
COUNTERBORE_R = COUNTERBORE_DIA / 2.0

_FRONT_DX = PEAK_X - SHOULDER_X
_FRONT_DH = HANDLE_MAX_DIA / 2.0 - NECK_R
FRONT_PROFILE_R = (_FRONT_DX**2 + _FRONT_DH**2) / (2.0 * _FRONT_DH)
_REAR_DX = HANDLE_LENGTH - PEAK_X
_REAR_DH = HANDLE_MAX_DIA / 2.0 - CAP_R
REAR_PROFILE_R = (_REAR_DX**2 + _REAR_DH**2) / (2.0 * _REAR_DH)
REAR_PROFILE_CY = HANDLE_MAX_DIA / 2.0 - REAR_PROFILE_R
# The oak's radius where the butt is trimmed.
TRIM_R = REAR_PROFILE_CY + math.sqrt(REAR_PROFILE_R**2 - (TRIM_X - PEAK_X) ** 2)

# The title block's .X band on the routine sizes below.
_GENERAL_1PL = GENERAL_1PL_TOL_MM
# Oak left around the counterbore at its mouth, under the cup flange, when the
# largest cup body takes the widest glue line.
_COUNTERBORE_MAX = CUP_BODY_DIA + CUP_BODY_DIA_TOL + COUNTERBORE_GLUE_LINE[1]
COUNTERBORE_MOUTH_WALL = (TRIM_R - CONTOUR_ALLOWANCE_DIA / 4.0) - _COUNTERBORE_MAX / 2.0

for _ok, _what in (
    (
        TENON_LENGTH + _GENERAL_1PL < FERRULE_LENGTH - _GENERAL_1PL,
        "the longest tenon reaches the shortest ferrule's arm face",
    ),
    (TENON_LENGTH - _GENERAL_1PL >= 4.0, "the shortest tenon leaves under 4.0 of glue length"),
    (TENON_R < NECK_R, "the tenon leaves no shoulder for the ferrule to seat on"),
    (
        COUNTERBORE_DEPTH - _GENERAL_1PL > CUP_BODY_LENGTH_MAX,
        "the cup body can bottom in the shallowest counterbore before its flange seats",
    ),
    (
        COUNTERBORE_MOUTH_WALL >= 1.5,
        "oak at the counterbore mouth is under 1.5 at the contour allowance",
    ),
    (
        abs(CUP_FLANGE_DIA - 2.0 * TRIM_R) <= 0.1,
        "the cup flange does not match the oak at the trim face",
    ),
    (COUNTERBORE_R > PIVOT_BORE_DIA / 2.0, "counterbore is inside the pivot bore"),
):
    if not _ok:
        raise AssertionError(f"MHA-022: {_what}")

# Marked dimensions.  The profile sketch owns the tenon, the wood length from
# datum B, the peak station from datum B and the counterbore; the bore sketch
# owns the reamed bore.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {
        "TenonDia",
        "TenonLength",
        "WoodLength",
        "PeakStation",
        "CounterboreDia",
        "CounterboreDepth",
    },
    "PivotBoreProfile": {"PivotBoreDia"},
}
# Decimal places are the tolerance (policy rule 2): the reamed bore prints its
# band and the basic peak station at two places; every other size is routine
# (.X), the two fitted diameters as references under their to-suit callouts.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HandleProfile": {
        "TenonDia": 1,
        "TenonLength": 1,
        "WoodLength": 1,
        "PeakStation": 1,
        "CounterboreDia": 1,
        "CounterboreDepth": 1,
    },
    "PivotBoreProfile": {"PivotBoreDia": 2},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-022 dimension needs authored places")
# The MHA-022 review (user ruling 2026-09-29) dropped the datums, the three
# feature-control frames and the basic profile: a decorative oak grip is
# turned to its arcs by eye and template, within a contour allowance.
REFERENCE_DIMENSIONS = frozenset({"TenonDia", "CounterboreDia"})
# Tenon end to butt face: a reference overall for stock cut-off, printed from
# the sheet (the profile carries no such dimension).  Its places are
# specification, read by the sheet from here (policy rule 2).
OVERALL_REFERENCE = TENON_LENGTH + WOOD_LENGTH
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall length reference": 1}

FERRULE_NUMBER = "MHA-150"
CUP_NUMBER = "MHA-153"
SCREW_NUMBER = "MHA-139"

_PEAK_B = PEAK_X - SHOULDER_X
_END_B = HANDLE_LENGTH - SHOULDER_X
DRAWING_NOTES = "\n".join(
    (
        "AXIAL STATIONS ARE FROM THE TENON SHOULDER; THE COUNTERBORE DEPTH IS",
        "  FROM THE BUTT FACE.",
        f"TURN THE TENON TO SUIT THE {FERRULE_NUMBER} FERRULE BORE AND BORE THE BUTT",
        f"  COUNTERBORE TO SUIT THE {CUP_NUMBER} CUP BODY, EACH FOR "
        f"{TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f} DIAMETRAL",
        "  CLEARANCE; EPOXY BOTH IN AT ASSEMBLY.",
        f"THE REAMED BORE RUNS ON THE {SCREW_NUMBER} SHOULDER; ITS LIMITS APPLY FULL LENGTH.",
        f"GRIP CONTOUR: <MOD-DIAM>{2.0 * NECK_R:.1f} AT THE SHOULDER, <MOD-DIAM>{HANDLE_MAX_DIA:.1f} AT "
        f"{_PEAK_B:.1f}; ARCS",
        f"  R{FRONT_PROFILE_R:.1f} AND R{REAR_PROFILE_R:.1f}, TANGENT AT {_PEAK_B:.1f}, RUNNING ON TO "
        f"<MOD-DIAM>{2.0 * CAP_R:.1f} AT {_END_B:.1f}",
        f"  (PAST THE BUTT FACE). TURN WITHIN {CONTOUR_ALLOWANCE_DIA:.1f} ON DIAMETER.",
        "USE CLEAR STRAIGHT GRAIN PARALLEL TO TURNING AXIS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

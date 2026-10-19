r"""Pure-data dimensional contract shared by the crank handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned, ebonized oak pear grip on the
crank-arm pivot.  User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-DT-034 on a turned
tenon, and the bright disc at the butt a steel cup MHA-DT-035 in a counterbore,
the pivot screw's slotted head recessed inside it.

User rulings 2026-09-30 (ch30 eight-views-4, the true side view, and the
approved CadQuery concept v4): the grip leaves the ferrule face flush with its
OD, flares down to a slim waist, swells in an S-curve to the Ø21 maximum at
0.72 of the length, and domes down to an end round on a flat oak end round
the bonded cup.  Five tangent arcs, in turn:

* flare      -- concave, from the ferrule OD at the shoulder to the waist;
* S concave  -- from the waist (horizontal tangent) to the inflection;
* S convex   -- from the inflection to the swell (horizontal tangent);
* dome       -- convex, from the swell towards the butt;
* end round  -- convex, tangent to the dome, cresting on the flat oak end.

The sheet prints what the turner sets out and calipers: the stations from the
tenon end face, the waist, swell and crest diameters and the end round, at the
title block's .X band; the tangencies fix the other radii, which print as
references (MHA-DT-008 machinist review of 2026-10-18: the contour had lived in
a note).

Frame: the handle axis is local +X and x=0 is the ferrule's arm-bearing face,
the plane the drive train seats on the arm.  No oak reaches x=0: the tenon
stops short of the ferrule's end, so only brass bears on the arm.
"""

from __future__ import annotations

import math

from dt_crank_hub_geometry import EDGE_BREAK_MAX_MM, GENERAL_1PL_TOL_MM
from dt_crank_handle_butt_cup_spec import (
    BODY_CHAMFER_MIN as CUP_BODY_CHAMFER_MIN,
    BODY_DIA as CUP_BODY_DIA,
    BODY_DIA_TOL as CUP_BODY_DIA_TOL,
    OVERALL_LENGTH as CUP_LENGTH,
)
from dt_crank_handle_ferrule_spec import (
    BORE_DIA as FERRULE_BORE_DIA,
    BORE_DIA_TOL as FERRULE_BORE_DIA_TOL,
    LENGTH as FERRULE_LENGTH,
    INSTALLED_OUTER_DIA as FERRULE_OUTER_DIA,
    STOCK_DIA_MIN as FERRULE_STOCK_DIA_MIN,
    SEAT_MOUTH_CHAMFER_MAX as FERRULE_SEAT_MOUTH_CHAMFER_MAX,
    SEAT_MOUTH_CHAMFER_MIN as FERRULE_SEAT_MOUTH_CHAMFER_MIN,
    TENON_GLUE_LINE as FERRULE_TENON_GLUE_LINE,
    TENON_GLUE_LENGTH_FLOOR,
    TENON_LENGTH,
)

# 2026-09-02 user re-read: overall 58 from the arm face; the ferrule and the
# cup take its two ends.
HANDLE_LENGTH = 58.0  # basic: ferrule arm face to cup face
HANDLE_MAX_DIA = 21.0  # max diameter at the swell
# The title block's .X band governs every grip size (MHA-DT-008 machinist
# review of 2026-10-18: a tighter contour allowance had no mate to justify it).
_GENERAL_1PL = GENERAL_1PL_TOL_MM
# Reamed running bore on the MHA-DT-032 Ø4.00 shoulder: limits 4.10-4.15,
# printed as 4.10 +0.05/0 so the two-place nominal is the limit itself (local
# review of fbf82ad96: 4.125 at two places printed 4.13 +/-0.025).
PIVOT_BORE_DIA = 4.10
PIVOT_BORE_BAND = (0.05, 0.0)

# The tenon shoulder is where the ferrule seats, FERRULE_LENGTH from the arm
# face.  The oak leaves it flush with the ferrule's OD (user, handle2.png).
SHOULDER_X = FERRULE_LENGTH
SHOULDER_R = FERRULE_OUTER_DIA / 2.0
# The tenon is turned to suit the actual MHA-DT-034 bore for an epoxy line; the
# model carries the size that line gives on a nominal bore.
TENON_GLUE_LINE = FERRULE_TENON_GLUE_LINE
TENON_DIA = FERRULE_BORE_DIA - sum(TENON_GLUE_LINE) / 2.0
# Short enough that the longest tenon stops short of the shortest ferrule's
# arm face, so the oak never bears on the arm.
TENON_X0 = SHOULDER_X - TENON_LENGTH
TENON_R = TENON_DIA / 2.0
# Owner ruling A on #1661, drawing-guidelines.md rule 16 (design for the
# cutter: say the largest acceptable inside radius): the tenon root and the
# counterbore's floor corner are each modelled AT this limit and print the
# single limit "R0.3 MAX" (swTolMAX prints the nominal, so nominal = limit;
# the band runs from sharp up to it).  The ferrule's seat-mouth chamfer and
# the cup's body chamfer each clear it (asserted below).
INSIDE_CORNER_R_MAX = 0.3
INSIDE_CORNER_R_BAND = (0.0, -INSIDE_CORNER_R_MAX)  # (upper, lower)
INSIDE_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R0.3 MAX"

# Grip stations (x from the arm face) and radii, fitted to eight-views-4.
WAIST_X = 12.0
WAIST_R = 9.5 / 2.0
INFLECTION_X = 20.0
PEAK_X = 42.0
PEAK_R = HANDLE_MAX_DIA / 2.0

# The counterbore is bored to suit the actual MHA-DT-035 body for an epoxy line.
COUNTERBORE_GLUE_LINE = (0.05, 0.15)
COUNTERBORE_DIA = CUP_BODY_DIA + sum(COUNTERBORE_GLUE_LINE) / 2.0
COUNTERBORE_R = COUNTERBORE_DIA / 2.0
# Unprinted design margin: the walls budget 0.10 of wander between the reamed
# bore and the turned outside (local reviews of 1f3067ef2 and 4b46c8b53).  No
# run-out prints (MHA-DT-008 machinist review of 2026-10-18: a TIR on a
# hand-cranked wooden grip is over-specification); the cup's position is
# absorbed at fit-up instead.
BORE_ECCENTRICITY = 0.10
# The MHA-DT-035 cup can sit off the bore axis by this eccentricity plus half its
# widest glue line, 0.175 -- more than the screw's head and floor-hole
# clearances plus its float in the bore take up (0.165, local review of
# 4b46c8b53).  So the cup is epoxied in centred on the waxed MHA-DT-032 screw
# through it and the bore (user ruling 2026-09-30, MHA-DT-000 step 7): it
# cures where the screw fits, and the screw only turns about its own axis after.
CUP_OFFSET_MAX = BORE_ECCENTRICITY + COUNTERBORE_GLUE_LINE[1] / 2.0
# The printed limit on the counterbore (bored to suit the cup).
COUNTERBORE_DIA_MAX = round(
    CUP_BODY_DIA + CUP_BODY_DIA_TOL + COUNTERBORE_GLUE_LINE[1] + 0.05, 1
)
# The butt: a flat oak end on the cup-face plane, the end round cresting on it
# at this diameter.  Wide enough that the oak round the largest counterbore
# holds the 2.0 wall target with the crest turned its .X band small and the
# outside and the counterbore each off the bore by the eccentricity in opposite
# directions (MHA-DT-008 machinist review of 2026-10-18: a Ø9.4 crest left a
# 0.45 lip over the counterbore, feathering to nothing).
CREST_DIA = 14.0
END_ROUND_R = 1.5
END_ROUND_CY = CREST_DIA / 2.0

# Flare: concave, centre above the waist, through the shoulder point.
FLARE_R = ((WAIST_X - SHOULDER_X) ** 2 + (SHOULDER_R - WAIST_R) ** 2) / (
    2.0 * (SHOULDER_R - WAIST_R)
)
FLARE_CENTER = (WAIST_X, WAIST_R + FLARE_R)
# S-curve: two arcs, horizontal at the waist and at the swell, tangent at the
# inflection, so their centres are |S| apart with S = R_concave + R_convex.
_S_DX, _S_DH = PEAK_X - WAIST_X, PEAK_R - WAIST_R
_S = (_S_DX**2 + _S_DH**2) / (2.0 * _S_DH)
S_CONCAVE_R = _S * (INFLECTION_X - WAIST_X) / _S_DX
S_CONVEX_R = _S - S_CONCAVE_R
S_CONCAVE_CENTER = (WAIST_X, WAIST_R + S_CONCAVE_R)
S_CONVEX_CENTER = (PEAK_X, PEAK_R - S_CONVEX_R)
INFLECTION = (
    S_CONCAVE_CENTER[0] + S_CONCAVE_R / _S * (S_CONVEX_CENTER[0] - S_CONCAVE_CENTER[0]),
    S_CONCAVE_CENTER[1] + S_CONCAVE_R / _S * (S_CONVEX_CENTER[1] - S_CONCAVE_CENTER[1]),
)
# End round: crest (rightmost point) on the cup face at END_ROUND_CY, so its
# centre sits END_ROUND_R inside that face.
END_ROUND_CX = HANDLE_LENGTH - END_ROUND_R
END_ROUND_CENTER = (END_ROUND_CX, END_ROUND_CY)
# Dome: convex, centre below the swell (horizontal tangent there), internally
# tangent to the end round:
# (Cx - Xp)^2 + (Cy - Yp + Rd)^2 = (Rd - R)^2, solved for Rd in closed form.
_D_DX = END_ROUND_CX - PEAK_X
_D_DY = END_ROUND_CY - PEAK_R
DOME_R = (END_ROUND_R**2 - _D_DX**2 - _D_DY**2) / (2.0 * (_D_DY + END_ROUND_R))
DOME_CENTER = (PEAK_X, PEAK_R - DOME_R)
# The oak ends on the cup-face plane, flush with the cup, which bottoms in
# the counterbore.
OAK_END_X = HANDLE_LENGTH
COUNTERBORE_DEPTH = round(CUP_LENGTH, 6)
COUNTERBORE_FLOOR_X = OAK_END_X - COUNTERBORE_DEPTH
_d = math.hypot(END_ROUND_CX - DOME_CENTER[0], END_ROUND_CY - DOME_CENTER[1])
DOME_END = (
    DOME_CENTER[0] + DOME_R * (END_ROUND_CX - DOME_CENTER[0]) / _d,
    DOME_CENTER[1] + DOME_R * (END_ROUND_CY - DOME_CENTER[1]) / _d,
)


def profile_radius(x: float) -> float:
    """The grip's nominal radius at station ``x`` (shoulder to oak end)."""

    def upper(center: tuple[float, float], r: float) -> float:
        # Clamped: the end round's crest sits exactly on the oak end station.
        return center[1] + math.sqrt(max(0.0, r * r - (x - center[0]) ** 2))

    def lower(center: tuple[float, float], r: float) -> float:
        return center[1] - math.sqrt(r * r - (x - center[0]) ** 2)

    if x <= WAIST_X:
        return lower(FLARE_CENTER, FLARE_R)
    if x <= INFLECTION[0]:
        return lower(S_CONCAVE_CENTER, S_CONCAVE_R)
    if x <= PEAK_X:
        return upper(S_CONVEX_CENTER, S_CONVEX_R)
    if x <= DOME_END[0]:
        return upper(DOME_CENTER, DOME_R)
    return upper(END_ROUND_CENTER, END_ROUND_R)


WOOD_LENGTH = OAK_END_X - SHOULDER_X

# The oak round the largest counterbore at the butt, its thinnest place: the
# crest turned its .X band small, off the bore by the eccentricity one way and
# the counterbore the other.
BUTT_WALL_MIN = (
    (CREST_DIA - _GENERAL_1PL) / 2.0
    - 2.0 * BORE_ECCENTRICITY
    - COUNTERBORE_DIA_MAX / 2.0
)
# drawing-guidelines.md rule 17's target wall for wood.
WALL_TARGET_MM = 2.0
# The tenon is turned to suit the actual ferrule bore (Codex P1/P2 on #1139):
# the largest banded bore with the tightest glue line gives the largest tenon,
# and the smallest bore with the widest line the smallest.
TENON_DIA_MAX = FERRULE_BORE_DIA + FERRULE_BORE_DIA_TOL - FERRULE_TENON_GLUE_LINE[0]
TENON_DIA_MIN = FERRULE_BORE_DIA - FERRULE_BORE_DIA_TOL - FERRULE_TENON_GLUE_LINE[1]
# The shoulder the ferrule seats on, radially, at its worst: the oak turned
# its .X band small at the shoulder over the largest tenon.
FERRULE_SEAT_RADIAL_MIN = ((2.0 * SHOULDER_R - _GENERAL_1PL) - TENON_DIA_MAX) / 2.0
# The shortest tenon's unbroken bonded length inside the ferrule, less the
# title-block edge break on the tenon end and the ferrule's seat-mouth chamfer
# at its largest (owner ruling A on #1661; the 0.4 upper limit is what keeps
# this at 3.55, half the ferrule's length and more).  The tenon root's R0.3
# MAX sits inside that chamfer, so it costs no further length.
TENON_GLUE_LENGTH_MIN = round(
    TENON_LENGTH - _GENERAL_1PL - EDGE_BREAK_MAX_MM - FERRULE_SEAT_MOUTH_CHAMFER_MAX, 6
)
# The ferrule rides the tenon (true to the bore within the eccentricity) on
# its glue line, so it can sit this far off the bore; the skim, true to the
# bore, takes it down to the contour (local review of 47cb8a46b, user ruling
# 2026-10-01).
FERRULE_OFFSET_MAX = BORE_ECCENTRICITY + TENON_GLUE_LINE[1] / 2.0
# Brass left at the thin side: the smallest skimmed OD, off the bore by the
# skim's own wander, over the largest bore on the ferrule's offset.
FERRULE_SKIMMED_WALL_MIN = (
    (2.0 * SHOULDER_R - _GENERAL_1PL) / 2.0
    - BORE_ECCENTRICITY
    - ((FERRULE_BORE_DIA + FERRULE_BORE_DIA_TOL) / 2.0 + FERRULE_OFFSET_MAX)
)
# drawing-guidelines.md rule 17's wall floor.
TENON_WALL_FLOOR_MM = 1.5
# Arm face to the shortest tenon's end: the shortest .X ferrule less the
# longest .X tenon, so the oak never bears on the arm.
TENON_END_GAP_MIN = round(
    (FERRULE_LENGTH - _GENERAL_1PL) - (TENON_LENGTH + _GENERAL_1PL), 6
)
# Oak between the smallest tenon and the largest reamed pivot bore.
TENON_WALL_MIN = (
    (TENON_DIA_MIN - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0])) / 2.0 - BORE_ECCENTRICITY
)
# Oak at the waist over the largest bore, the waist turned its .X band small.
WAIST_WALL_MIN = (
    (2.0 * WAIST_R - _GENERAL_1PL) - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0])
) / 2.0 - BORE_ECCENTRICITY

for _ok, _what in (
    (
        TENON_END_GAP_MIN > 0.0,
        "the longest tenon reaches the shortest ferrule's arm face",
    ),
    (
        TENON_GLUE_LENGTH_MIN >= TENON_GLUE_LENGTH_FLOOR,
        f"the shortest tenon leaves under {TENON_GLUE_LENGTH_FLOOR:g} of unbroken glue length",
    ),
    (
        FERRULE_SEAT_RADIAL_MIN >= 0.5,
        "the largest fitted tenon leaves under 0.5 of shoulder for the ferrule",
    ),
    (
        TENON_WALL_MIN >= TENON_WALL_FLOOR_MM,
        "the smallest fitted tenon leaves under 1.5 over the bore",
    ),
    (
        FERRULE_STOCK_DIA_MIN / 2.0
        >= (2.0 * SHOULDER_R + _GENERAL_1PL) / 2.0 + FERRULE_OFFSET_MAX + BORE_ECCENTRICITY,
        "the smallest ferrule stock, off-centre, does not clean up in the skim",
    ),
    (
        FERRULE_SKIMMED_WALL_MIN >= 1.5,
        "the skimmed ferrule, off-centre, leaves under 1.5 of brass",
    ),
    (WAIST_WALL_MIN >= 1.5, "the waist leaves under 1.5 over the bore"),
    (
        BUTT_WALL_MIN >= WALL_TARGET_MM,
        "the butt leaves under 2.0 of oak round the counterbore",
    ),
    (WAIST_R < SHOULDER_R and WAIST_R < PEAK_R, "the waist is not the neck's minimum"),
    (
        DOME_CENTER[0] < END_ROUND_CX < HANDLE_LENGTH and 0.0 < END_ROUND_R < DOME_R,
        "the end round does not sit inside the dome",
    ),
    (
        DOME_END[0] > PEAK_X and DOME_END[1] > END_ROUND_CY,
        "the dome does not run from the swell down to the end round",
    ),
    # A 45-degree chamfer of leg c clears an inside fillet of radius R when
    # c >= R: the fillet ends R along each face.
    (
        FERRULE_SEAT_MOUTH_CHAMFER_MIN >= INSIDE_CORNER_R_MAX,
        "the smallest ferrule seat-mouth chamfer fouls the tenon root radius",
    ),
    (
        CUP_BODY_CHAMFER_MIN >= INSIDE_CORNER_R_MAX,
        "the smallest cup body chamfer fouls the counterbore floor radius",
    ),
    (COUNTERBORE_R > PIVOT_BORE_DIA / 2.0, "counterbore is inside the pivot bore"),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-008: {_what}")

# Marked dimensions, all on the one revolve profile: the tenon, the reamed bore,
# the stations from the tenon end face, the grip diameters and the end round,
# the counterbore, the two inside corners' single limits, and the
# tangency-fixed radii as references.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {
        "PivotBoreDia",
        "TenonLength",
        "TenonDia",
        "ShoulderDia",
        "WaistStation",
        "WaistDia",
        "InflectionStation",
        "PeakStation",
        "PeakDia",
        "CrestDia",
        "EndRoundR",
        "OverallLength",
        "CounterboreDepth",
        "CounterboreDia",
        "FlareR",
        "SConcaveR",
        "SConvexR",
        "DomeR",
        "TenonRootRadius",
        "CounterboreFloorRadius",
    },
}
# Decimal places are the tolerance (drawing-guidelines.md rule 3 (decimal places
# carry the tolerance)): the reamed bore prints its band at two places; every
# other size is routine (.X), the fitted tenon and counterbore as references
# under their to-suit notes, and the inside corners' R0.3 MAX limits print at
# one place.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HandleProfile": {
        name: 2 if name == "PivotBoreDia" else 1
        for name in DRAWING_DIMENSIONS["HandleProfile"]
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-008 dimension needs authored places")
# Fitted to the ferrule and the cup (user ruling 2026-09-29): references.
REFERENCE_DIMENSIONS = frozenset({"TenonDia", "CounterboreDia", "CounterboreDepth"})
# Driven by the tangencies: references.
REFERENCE_RADII = frozenset({"FlareR", "SConcaveR", "SConvexR", "DomeR"})
# Every axial station reads from the tenon's end face, the one faced end, so
# the oak's overall (for stock cut-off) is a marked dimension of its own.
OVERALL_LENGTH = OAK_END_X - TENON_X0

FERRULE_NUMBER = "MHA-DT-034"
CUP_NUMBER = "MHA-DT-035"
SCREW_NUMBER = "MHA-DT-032"
FERRULE_NAME = "FERRULE"
CUP_NAME = "BUTT CUP"
SCREW_NAME = "PIVOT SCREW"

# The matched fits, each flagged on its feature (drawing-guidelines.md rules 4
# and 7): the mate by name and number, and the acceptance.  Short lines keep
# each block narrow beside its neighbours on the sheet.
TENON_FIT_NOTE = (
    f"TURN TO SUIT {FERRULE_NAME}\n"
    f"{FERRULE_NUMBER} BORE, {TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f}\n"
    "DIAMETRAL CLEARANCE"
)
COUNTERBORE_FIT_NOTE = (
    f"BORE TO SUIT {CUP_NAME}\n"
    f"{CUP_NUMBER} BODY, {COUNTERBORE_GLUE_LINE[0]:.2f}-{COUNTERBORE_GLUE_LINE[1]:.2f}\n"
    f"DIAMETRAL CLEARANCE, <MOD-DIAM>{COUNTERBORE_DIA_MAX:.1f} MAX;\n"
    "DEPTH SEATS ITS FACE FLUSH"
)
# The inside corners' single limits name the part that seats on each
# (drawing-guidelines.md rule 4): short lines, each block standing in a narrow
# gap beside the section.
TENON_ROOT_CALLOUT = f"{FERRULE_NAME}\nSEAT"
COUNTERBORE_FLOOR_CALLOUT = f"{CUP_NAME}\nSEAT"
PIVOT_BORE_CALLOUT = f"REAM THRU\nRUNS ON {SCREW_NAME}\n{SCREW_NUMBER} SHOULDER"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

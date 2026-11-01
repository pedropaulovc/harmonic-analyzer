r"""Pure-data dimensional contract shared by the crank handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned, ebonized oak pear grip on the
crank-arm pivot.  User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-DT-34 on a turned
tenon, and the bright disc at the butt a steel cup MHA-DT-35 in a counterbore,
the pivot screw's slotted head recessed inside it.

User rulings 2026-09-30 (ch30 eight-views-4, the true side view, and the
approved CadQuery concept v4): the grip leaves the ferrule face flush with its
OD, flares down to a slim waist, swells in an S-curve to the maximum at
0.72 of the length, and domes down to an end round on a flat oak end round
the bonded cup.  Five tangent arcs, in turn:

* flare      -- concave, from the ferrule OD at the shoulder to the waist;
* S concave  -- from the waist (horizontal tangent) to the inflection;
* S convex   -- from the inflection to the swell (horizontal tangent);
* dome       -- convex, from the swell towards the butt;
* end round  -- convex, tangent to the dome, cresting on the flat oak end.

The sheet prints what the turner sets out and calipers: the stations from the
tenon end face, the waist, swell and crest diameters and the end round, at the
title block's .XX band (the walls read them, so .X is not open to them); the
tangencies fix the other radii, which print as references (MHA-DT-08
machinist review of 2026-10-18: the contour had lived in a note).

Owner ruling B on #1375 enlarges the cup body to retain its pocket wall and
derives the butt crest from that cup's largest counterbore, the .XX band,
both eccentricities, and the rule-17 oak wall target plus a radial margin.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``).  Every
nominal is the exact millimetre decimal of its printed inch value, and every
band, edge break and wall limit below is the inch title block's.

Frame: the handle axis is local +X and x=0 is the ferrule's arm-bearing face,
the plane the drive train seats on the arm.  No oak reaches x=0: the tenon
stops short of the ferrule's end, so only brass bears on the arm.
"""

from __future__ import annotations

import math

import _config
from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import edge_break_chamfer_mm, printed_band_mm
from _title_block_units import render_number
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
    SEAT_MOUTH_BREAK_MAX as FERRULE_SEAT_MOUTH_BREAK_MAX,
    TENON_GLUE_LINE as FERRULE_TENON_GLUE_LINE,
    TENON_GLUE_LENGTH_FLOOR,
    TENON_LENGTH,
)

UNIT = drawing_unit("parts/dt-crank-handle", _config.parts("dt-crank-handle"))
MM_PER_IN = 25.4


def inch_text(value_mm: float, places: int) -> str:
    """``value_mm`` as this sheet prints it: ``.395``, ``2.28``."""
    return render_number(round(value_mm / MM_PER_IN, places), "in", places)


def _to_grid(value_mm: float, places: int, rounding) -> float:
    """``value_mm`` moved onto the printed inch grid by ``rounding``
    (``math.ceil`` or ``math.floor``), as exact millimetres."""
    steps = rounding(round(value_mm / MM_PER_IN * 10**places, 6))
    return round(steps / 10**places * MM_PER_IN, 6)


EDGE_BREAK_MAX_MM = edge_break_chamfer_mm(unit=UNIT)

# 2026-09-02 user re-read: overall from the arm face; the ferrule and the
# cup take its two ends.
HANDLE_LENGTH = 57.912  # 2.28 basic: ferrule arm face to cup face
HANDLE_MAX_DIA = 21.082  # .83 at the swell
# The title block's .XX band governs every grip size (MHA-DT-08 machinist
# review of 2026-10-18: a tighter contour allowance had no mate to justify it).
_GENERAL_2PL = printed_band_mm(2, unit=UNIT)
# Reamed running bore on the MHA-DT-32 shoulder (#290 fit F12): a .1610
# chucking reamer cuts .1610-.1615.  The checks read that band; the sheet
# prints the bore as a reference over the running clearance it gives on the
# shoulder (MHA-DT-08 review of 29af6f44d: a .0005 band in oak was
# over-specification), the fleet's matched-fit form.
PIVOT_BORE_DIA = 4.0894  # .1610
PIVOT_BORE_BAND = (0.0127, 0.0)  # +.0005/.0000

# The tenon shoulder is where the ferrule seats, FERRULE_LENGTH from the arm
# face.  The oak leaves it flush with the ferrule's OD (user, handle2.png).
SHOULDER_X = FERRULE_LENGTH
SHOULDER_R = FERRULE_OUTER_DIA / 2.0
# The tenon is turned to suit the actual MHA-DT-34 bore for an epoxy line; the
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
# single limit "R.012 MAX" (swTolMAX prints the nominal, so nominal = limit;
# the band runs from sharp up to it).  The tenon root sits in the shoulder
# relief below, behind the ferrule's seat face, and the cup's body chamfer
# clears the counterbore's floor corner (both asserted below).
INSIDE_CORNER_R_MAX = 0.3048  # .012
INSIDE_CORNER_R_BAND = (0.0, -INSIDE_CORNER_R_MAX)  # (upper, lower)
INSIDE_CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.012 MAX"

# Grip stations (x from the arm face; the sheet prints them from the tenon end
# face, .08 in) and radii, fitted to eight-views-4.
WAIST_X = 11.938  # .47; .39 from the tenon end
WAIST_R = 9.398 / 2.0  # Ø.37
INFLECTION_X = 20.066  # .79; .71 from the tenon end
PEAK_X = 41.91  # 1.65; 1.57 from the tenon end
PEAK_R = HANDLE_MAX_DIA / 2.0

# The counterbore is bored to suit the actual MHA-DT-35 body for an epoxy line.
COUNTERBORE_GLUE_LINE = (0.0508, 0.1524)  # .002-.006
COUNTERBORE_DIA = CUP_BODY_DIA + sum(COUNTERBORE_GLUE_LINE) / 2.0
COUNTERBORE_R = COUNTERBORE_DIA / 2.0
# Unprinted design margin: the walls budget .004 of wander between the reamed
# bore and the turned outside (local reviews of 1f3067ef2 and 4b46c8b53).  No
# run-out prints (MHA-DT-08 machinist review of 2026-10-18: a TIR on a
# hand-cranked wooden grip is over-specification); the cup's position is
# absorbed at fit-up instead.
BORE_ECCENTRICITY = 0.1016  # .004
# The MHA-DT-35 cup can sit off the bore axis by this eccentricity plus half its
# widest glue line -- more than the screw's head and floor-hole clearances plus
# its float in the bore take up (local review of 4b46c8b53).  So the cup is
# epoxied in centred on the waxed MHA-DT-32 screw through it and the bore
# (user ruling 2026-09-30, MHA-DT-00 step 7): it cures where the screw fits,
# and the screw only turns about its own axis after.
CUP_OFFSET_MAX = BORE_ECCENTRICITY + COUNTERBORE_GLUE_LINE[1] / 2.0
# The printed limit on the counterbore (bored to suit the cup): the largest
# body, the widest glue line and .002 of margin, up to the next thousandth.
COUNTERBORE_DIA_MAX = _to_grid(
    CUP_BODY_DIA + CUP_BODY_DIA_TOL + COUNTERBORE_GLUE_LINE[1] + 0.0508, 3, math.ceil
)
# Owner ruling B on #1375: the flat oak end on the cup-face plane keeps the
# rule-17 wall target plus a radial design margin.  Derive its crest from the
# cup-driven counterbore limit, the .XX diameter band and the outside and
# counterbore each off the bore by the eccentricity in opposite directions, up
# to the next printed hundredth.
BUTT_WALL_RULING_MARGIN_MM = 0.0508  # .002
BUTT_WALL_DESIGN_MIN_MM = round(WALL_TARGET_MM + BUTT_WALL_RULING_MARGIN_MM, 6)
CREST_DIA = _to_grid(
    COUNTERBORE_DIA_MAX
    + _GENERAL_2PL
    + 2.0 * (2.0 * BORE_ECCENTRICITY + BUTT_WALL_DESIGN_MIN_MM),
    2,
    math.ceil,
)
END_ROUND_R = 1.524  # .06
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
# crest turned its .XX band small, off the bore by the eccentricity one way and
# the counterbore the other.
BUTT_WALL_MIN = round(
    (CREST_DIA - _GENERAL_2PL) / 2.0
    - 2.0 * BORE_ECCENTRICITY
    - COUNTERBORE_DIA_MAX / 2.0,
    6,
)
# The tenon is turned to suit the actual ferrule bore (Codex P1/P2 on #1139):
# the largest banded bore with the tightest glue line gives the largest tenon,
# and the smallest bore with the widest line the smallest.
TENON_DIA_MAX = FERRULE_BORE_DIA + FERRULE_BORE_DIA_TOL - FERRULE_TENON_GLUE_LINE[0]
TENON_DIA_MIN = FERRULE_BORE_DIA - FERRULE_BORE_DIA_TOL - FERRULE_TENON_GLUE_LINE[1]
# The shoulder the ferrule seats on, radially, before the root relief: the oak
# turned its .XX band small at the shoulder over the largest tenon.
_SEAT_RADIAL_UNRELIEVED = ((2.0 * SHOULDER_R - _GENERAL_2PL) - TENON_DIA_MAX) / 2.0
FERRULE_SEAT_RADIAL_FLOOR = 0.5
# Owner ruling 2026-10-24 (#1900, option 4): the tenon root is relieved so the
# MHA-DT-34 seat mouth needs only the title block's edge break, not ruling A's
# chamfer, and keeps that brass in its wall.  The relief is a 45-degree cone
# cut into the SHOULDER at the root, its leg the same along the shoulder face
# from the tenon OD and along the tenon behind the face.  A groove in the
# tenon cannot do it: the smallest fitted tenon keeps only a hair of oak over
# its rule-17 floor round the pivot bore (TENON_WALL_MIN), far less than the
# depth that would swallow the root round, while a shoulder relief leaves the
# tenon whole.  The R.012 MAX root round sits in the relief's 45-degree
# corner, tangent R (1 + sqrt 2) back from it along the tenon, so the leg's
# minimum keeps that whole round behind the seat face (no oak at the ferrule's
# mouth, whatever its break).  Its maximum leaves the ferrule its flat
# shoulder after the title-block break on the relief's outer edge, where the
# cone meets the shoulder face, and after the relief and the skimmed shoulder
# OD land off each other: the relief is turned with the tenon, true to the
# pivot bore within BORE_ECCENTRICITY, and the shoulder is skimmed with
# MHA-DT-34 after cure, true to it within the same again (codjiflo on PR
# #1989).  Each limit is rounded inward to the printed thousandth; the leg
# prints their mid-band, which must itself print at .XXX, as the band must.
_RELIEF_TO_SKIM_OFFSET_MAX = 2.0 * BORE_ECCENTRICITY
TENON_ROOT_ROUND_REACH = INSIDE_CORNER_R_MAX * (1.0 + math.sqrt(2.0))
TENON_ROOT_RELIEF_PLACES = 3
TENON_ROOT_RELIEF_MIN = _to_grid(
    TENON_ROOT_ROUND_REACH, TENON_ROOT_RELIEF_PLACES, math.ceil
)
TENON_ROOT_RELIEF_MAX = _to_grid(
    _SEAT_RADIAL_UNRELIEVED
    - _RELIEF_TO_SKIM_OFFSET_MAX
    - EDGE_BREAK_MAX_MM
    - FERRULE_SEAT_RADIAL_FLOOR,
    TENON_ROOT_RELIEF_PLACES,
    math.floor,
)
if not TENON_ROOT_RELIEF_MIN < TENON_ROOT_RELIEF_MAX:
    raise AssertionError(
        "MHA-DT-08: no tenon-root relief keeps the root round behind the ferrule "
        "seat face and leaves the ferrule its shoulder"
    )
TENON_ROOT_RELIEF = round((TENON_ROOT_RELIEF_MIN + TENON_ROOT_RELIEF_MAX) / 2.0, 6)
TENON_ROOT_RELIEF_TOL = round((TENON_ROOT_RELIEF_MAX - TENON_ROOT_RELIEF_MIN) / 2.0, 6)
if any(
    abs(_to_grid(value, TENON_ROOT_RELIEF_PLACES, round) - value) > 1e-6
    for value in (TENON_ROOT_RELIEF, TENON_ROOT_RELIEF_TOL)
):
    raise AssertionError(
        "MHA-DT-08: the tenon-root relief band does not print at .XXX"
    )
# The flat shoulder left to the ferrule on the thin side, outside the largest
# relief landed off-centre and the break on its edge.
FERRULE_SEAT_RADIAL_MIN = (
    _SEAT_RADIAL_UNRELIEVED
    - _RELIEF_TO_SKIM_OFFSET_MAX
    - TENON_ROOT_RELIEF_MAX
    - EDGE_BREAK_MAX_MM
)
# The shortest tenon's unbroken bonded length inside the ferrule, less the
# title-block edge break on the tenon end and the break on the ferrule's seat
# mouth (owner ruling 2026-10-24, #1900).  The relief and the root round in it
# stand behind the seat face, so they cost no bonded length.
TENON_GLUE_LENGTH_MIN = round(
    TENON_LENGTH - _GENERAL_2PL - EDGE_BREAK_MAX_MM - FERRULE_SEAT_MOUTH_BREAK_MAX, 6
)
# Owner ruling 2026-10-24 (#1900): the ferrule cures on a mandrel through the
# pivot bore, so its bore sits on that axis within the same eccentricity the
# walls budget for anything turned true to the reamed bore, not riding the
# tenon on its glue line (user ruling 2026-10-01).  MHA-DT-00 step 7 states it;
# the skim, true to the bore, takes the ring to the contour.
FERRULE_OFFSET_MAX = BORE_ECCENTRICITY
# Brass left at the thin side: the smallest skimmed OD, off the bore by the
# skim's own wander, over the largest bore on the ferrule's offset.
FERRULE_SKIMMED_WALL_MIN = (
    (2.0 * SHOULDER_R - _GENERAL_2PL) / 2.0
    - BORE_ECCENTRICITY
    - ((FERRULE_BORE_DIA + FERRULE_BORE_DIA_TOL) / 2.0 + FERRULE_OFFSET_MAX)
)
# drawing-guidelines.md rule 17's wall floor, on an inch sheet .060.
TENON_WALL_FLOOR_MM = WALL_FLOOR_MM
# The same brass at the seat face, where the bore mouth's break comes off it
# (#1900: the plain-bore figure above missed the mouth); the OD's seat-end edge
# is the skim line it shares with the oak shoulder, so it takes no break.
# It clears the floor but not the .080 target: owner ruling 2026-10-24 (#1900)
# accepts it as minor exception RV-01 in dt-crank-handle-ferrule.yaml, and
# MHA-DT-34 prints it as WALL ... MIN AT SEAT FACE.
FERRULE_MOUTH_WALL_MIN = round(
    FERRULE_SKIMMED_WALL_MIN - FERRULE_SEAT_MOUTH_BREAK_MAX, 6
)
# At the arm face both edges are exposed and each takes the title block's
# break, the bore mouth's and the skimmed OD's (codjiflo on PR #1989), so the
# face plane keeps less than the floor: owner ruling 2026-10-26 (#1900, arm
# face) accepts down to 1.25 mm as minor exception RV-02, printed WALL ... MIN
# AT ARM FACE.
FERRULE_ARM_FACE_WALL_MIN = round(
    FERRULE_SKIMMED_WALL_MIN - FERRULE_SEAT_MOUTH_BREAK_MAX - EDGE_BREAK_MAX_MM, 6
)
FERRULE_ARM_FACE_WALL_ACCEPTED_MM = 1.25
# Arm face to the shortest tenon's end: the shortest .XX ferrule less the
# longest .XX tenon, so the oak never bears on the arm.
TENON_END_GAP_MIN = round(
    (FERRULE_LENGTH - _GENERAL_2PL) - (TENON_LENGTH + _GENERAL_2PL), 6
)
# Oak between the smallest tenon and the largest reamed pivot bore.
TENON_WALL_MIN = (
    (TENON_DIA_MIN - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0])) / 2.0 - BORE_ECCENTRICITY
)
# Oak at the waist over the largest bore, the waist turned its .XX band small.
WAIST_WALL_MIN = (
    (2.0 * WAIST_R - _GENERAL_2PL) - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0])
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
        FERRULE_SEAT_RADIAL_MIN >= FERRULE_SEAT_RADIAL_FLOOR,
        "the largest fitted tenon and root relief leave under "
        f"{FERRULE_SEAT_RADIAL_FLOOR:g} of shoulder for the ferrule",
    ),
    (
        TENON_WALL_MIN >= TENON_WALL_FLOOR_MM,
        "the smallest fitted tenon leaves under .060 over the bore",
    ),
    (
        FERRULE_STOCK_DIA_MIN / 2.0
        >= (2.0 * SHOULDER_R + _GENERAL_2PL) / 2.0 + FERRULE_OFFSET_MAX + BORE_ECCENTRICITY,
        "the smallest ferrule stock, off-centre, does not clean up in the skim",
    ),
    (
        FERRULE_SKIMMED_WALL_MIN >= TENON_WALL_FLOOR_MM,
        "the skimmed ferrule, off-centre, leaves under .060 of brass",
    ),
    (
        FERRULE_MOUTH_WALL_MIN >= TENON_WALL_FLOOR_MM,
        "the skimmed ferrule, off-centre, leaves under .060 of brass at its broken "
        "seat mouth (#1900)",
    ),
    (
        FERRULE_ARM_FACE_WALL_MIN >= FERRULE_ARM_FACE_WALL_ACCEPTED_MM,
        "the skimmed ferrule, off-centre, leaves under the owner-accepted "
        f"{FERRULE_ARM_FACE_WALL_ACCEPTED_MM:g} mm of brass at its arm face, both edges "
        "broken (#1900)",
    ),
    (WAIST_WALL_MIN >= WALL_FLOOR_MM, "the waist leaves under .060 over the bore"),
    (
        BUTT_WALL_MIN >= BUTT_WALL_DESIGN_MIN_MM >= WALL_TARGET_MM,
        "the butt leaves under the .080 target and its margin of oak round the "
        "counterbore (owner ruling B on #1375)",
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
    # A fillet of radius R in the relief's 45-degree root is tangent to the
    # tenon R (1 + sqrt 2) back from the root, so the smallest relief keeps it
    # behind the seat face and the ferrule's mouth meets no oak.
    (
        TENON_ROOT_RELIEF_MIN >= TENON_ROOT_ROUND_REACH,
        "the smallest tenon-root relief lets the root round reach the ferrule seat face",
    ),
    (
        CUP_BODY_CHAMFER_MIN >= INSIDE_CORNER_R_MAX,
        "the smallest cup body chamfer fouls the counterbore floor radius",
    ),
    (COUNTERBORE_R > PIVOT_BORE_DIA / 2.0, "counterbore is inside the pivot bore"),
):
    if not _ok:
        raise AssertionError(f"MHA-DT-08: {_what}")

# Marked dimensions, all on the one revolve profile: the tenon, the reamed bore,
# the stations from the tenon end face, the grip diameters and the end round,
# the counterbore, the tenon-root relief, the two inside corners' single
# limits, and the tangency-fixed radii and the S-curve's tangent-point diameter
# as references.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {
        "PivotBoreDia",
        "TenonLength",
        "TenonDia",
        "ShoulderDia",
        "WaistStation",
        "WaistDia",
        "InflectionStation",
        "InflectionDia",
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
        "TenonRootRelief",
        "TenonRootRadius",
        "CounterboreFloorRadius",
    },
}
# Decimal places are the tolerance (drawing-guidelines.md rule 3 (decimal places
# carry the tolerance)): the root relief prints its own band naming the
# ferrule it serves (rule 4), the inside corners' R.012 MAX limits and the
# fitted bore, tenon and counterbore diameters (references under their fit
# callouts) at three; every other size at two, the .XX band the walls are
# judged at.
_PRECISION_EXCEPTIONS = {
    "PivotBoreDia": 3,
    "TenonRootRelief": TENON_ROOT_RELIEF_PLACES,
    "TenonRootRadius": 3,
    "CounterboreFloorRadius": 3,
    "TenonDia": 3,
    "CounterboreDia": 3,
}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HandleProfile": {
        name: _PRECISION_EXCEPTIONS.get(name, 2)
        for name in DRAWING_DIMENSIONS["HandleProfile"]
    },
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
if set(DRAWING_PRECISION_BY_NAME) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("every marked MHA-DT-08 dimension needs authored places")
# Fitted to the ferrule and the cup (user ruling 2026-09-29), and the reamed
# bore under its running clearance: references.
REFERENCE_DIMENSIONS = frozenset(
    {"PivotBoreDia", "TenonDia", "CounterboreDia", "CounterboreDepth"}
)
# Driven by the tangencies: references.
REFERENCE_RADII = frozenset({"FlareR", "SConcaveR", "SConvexR", "DomeR"})
# The tangent point the inflection station ends on, where the S-curve's
# concave arc meets its convex one: its diameter, fixed by the tangencies,
# prints as a reference so the turner reads the template point there
# (MHA-DT-08 machinist review of 69eda6e4c).  The convex arc meets the dome
# at the swell, on the peak station, whose diameter already prints.
TANGENT_POINT_DIAMETERS = frozenset({"InflectionDia"})
# Every axial station reads from the tenon's end face, the one faced end, so
# the oak's overall (for stock cut-off) is a marked dimension of its own.
OVERALL_LENGTH = OAK_END_X - TENON_X0

FERRULE_NUMBER = "MHA-DT-34"
CUP_NUMBER = "MHA-DT-35"
SCREW_NUMBER = "MHA-DT-32"
FERRULE_NAME = "FERRULE"
CUP_NAME = "BUTT CUP"

# The matched fits, each flagged on its feature (drawing-guidelines.md rules 4
# and 7): the mate by name and number, and the acceptance.  Short lines keep
# each block narrow beside its neighbours on the sheet.
# The tenon's oak over the pivot bore sits between the rule-17 floor and the
# target, so its callout states it as a plain fact (rule 20; #290 review of
# b28d38a16), rounded down to the printed thousandth.
TENON_FIT_NOTE = (
    f"TURN TO SUIT {FERRULE_NAME}\n"
    f"{FERRULE_NUMBER} BORE, {inch_text(TENON_GLUE_LINE[0], 3)}-"
    f"{inch_text(TENON_GLUE_LINE[1], 3)}\n"
    "DIAMETRAL CLEARANCE;\n"
    f"WALL {inch_text(math.floor(TENON_WALL_MIN / 0.0254) * 0.0254, 3)} MIN"
)
COUNTERBORE_FIT_NOTE = (
    f"BORE TO SUIT {CUP_NAME}\n"
    f"{CUP_NUMBER} BODY, {inch_text(COUNTERBORE_GLUE_LINE[0], 3)}-"
    f"{inch_text(COUNTERBORE_GLUE_LINE[1], 3)}\n"
    f"DIAMETRAL CLEARANCE, <MOD-DIAM>{inch_text(COUNTERBORE_DIA_MAX, 3)} MAX;\n"
    "DEPTH SEATS ITS FACE FLUSH"
)
# The inside corners' single limits name the part that seats on each
# (drawing-guidelines.md rule 4): short lines, each block standing in a narrow
# gap beside the section.
TENON_ROOT_CALLOUT = f"{FERRULE_NAME}\nSEAT"
COUNTERBORE_FLOOR_CALLOUT = f"{CUP_NAME}\nSEAT"
# The root relief's band serves the ferrule (rule 4): its leg on the shoulder
# face, at 45 degrees, the mate named by number (farm r3 review of
# 8abe1a641), seating on the shoulder outside it.  Rows of 10 characters at
# most fit the gap left of the tenon end.
TENON_ROOT_RELIEF_CALLOUT = f"X 45 DEG;\n{FERRULE_NUMBER}\nSEATS\nOUTSIDE IT"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

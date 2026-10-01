r"""Pure-data dimensional contract shared by the crank handle and its
manufacturing drawing.

PURE DATA, no SolidWorks/COM imports.  A turned, ebonized oak pear grip on the
crank-arm pivot.  User ruling 2026-09-29 (ch11 p.14 and p.15 photographs): the
bright ring at the crank end is a separate brass ferrule MHA-152 on a turned
tenon, and the bright disc at the butt a steel cup MHA-153 in a counterbore,
the pivot screw's slotted head recessed inside it.

User rulings 2026-09-30 (ch30 eight-views-4, the true side view, and the
approved CadQuery concept v4): the grip leaves the ferrule face flush with its
OD, flares down to a slim waist, swells in an S-curve to the Ø21 maximum at
0.72 of the length, and domes down to an end round turned across the oak AND
the bonded cup together, so wood and steel read as one rounded butt.  Five
tangent arcs, in turn:

* flare      -- concave, from the ferrule OD at the shoulder to the waist;
* S concave  -- from the waist (horizontal tangent) to the inflection;
* S convex   -- from the inflection to the swell (horizontal tangent);
* dome       -- convex, from the swell towards the butt;
* end round  -- convex, tangent to the dome, down to the counterbore mouth.

Every centre except the end round's sits on a station with a horizontal
tangent (the waist or the swell), so the radii follow from the stations and
diameters below; the end round is solved from its tangency to the dome.  The
diameters derive from the geometry, so the drawing dimensions the axial
stations and states the contour in a note, turned within an allowance and
checked with a template (MHA-022 review, user ruling 2026-09-29).

Frame: the handle axis is local +X and x=0 is the ferrule's arm-bearing face,
the plane the drive train seats on the arm.  No oak reaches x=0: the tenon
stops short of the ferrule's end, so only brass bears on the arm.
"""

from __future__ import annotations

import math

from crank_hub_geometry import EDGE_BREAK_MAX_MM, GENERAL_1PL_TOL_MM
from crank_handle_butt_cup_spec import (
    BODY_DIA as CUP_BODY_DIA,
    BODY_DIA_TOL as CUP_BODY_DIA_TOL,
    OVERALL_LENGTH as CUP_LENGTH,
)
from crank_handle_ferrule_spec import (
    BORE_DIA as FERRULE_BORE_DIA,
    BORE_DIA_TOL as FERRULE_BORE_DIA_TOL,
    LENGTH as FERRULE_LENGTH,
    OUTER_DIA as FERRULE_OUTER_DIA,
    OUTER_DIA_TOL as FERRULE_OUTER_DIA_TOL,
    TENON_GLUE_LINE as FERRULE_TENON_GLUE_LINE,
)

# 2026-09-02 user re-read: overall 58 from the arm face; the ferrule and the
# cup take its two ends.
HANDLE_LENGTH = 58.0  # basic: ferrule arm face to cup face
HANDLE_MAX_DIA = 21.0  # max diameter at the swell
# The turned grip contour's allowance, on diameter, against its arcs: the wood
# grip is checked by eye and template, not by a profile frame (MHA-022 review,
# user ruling 2026-09-29).
CONTOUR_ALLOWANCE_DIA = 0.5
# Reamed running bore on the MHA-139 Ø4.00 shoulder: limits 4.10-4.15,
# printed as 4.10 +0.05/0 so the two-place nominal is the limit itself (local
# review of fbf82ad96: 4.125 at two places printed 4.13 +/-0.025).
PIVOT_BORE_DIA = 4.10
PIVOT_BORE_BAND = (0.05, 0.0)

# The tenon shoulder is where the ferrule seats, FERRULE_LENGTH from the arm
# face.  The oak leaves it flush with the ferrule's OD (user, handle2.png).
SHOULDER_X = FERRULE_LENGTH
SHOULDER_R = FERRULE_OUTER_DIA / 2.0
# The tenon is turned to suit the actual MHA-152 bore for an epoxy line; the
# model carries the size that line gives on a nominal bore.
TENON_GLUE_LINE = FERRULE_TENON_GLUE_LINE
TENON_DIA = FERRULE_BORE_DIA - sum(TENON_GLUE_LINE) / 2.0
# Short enough that the longest tenon stops short of the shortest ferrule's
# arm face, so the oak never bears on the arm.
TENON_LENGTH = 5.0
TENON_X0 = SHOULDER_X - TENON_LENGTH
TENON_R = TENON_DIA / 2.0

# Grip stations (x from the arm face) and radii, fitted to eight-views-4.
WAIST_X = 12.0
WAIST_R = 9.5 / 2.0
INFLECTION_X = 20.0
PEAK_X = 42.0
PEAK_R = HANDLE_MAX_DIA / 2.0
# The dome is the circle through the swell (horizontal tangent) and this
# theoretical point on the cup face plane; the end round replaces it at the
# butt.
DOME_THEORETICAL_R = 6.0

# The counterbore is bored to suit the actual MHA-153 body for an epoxy line;
# the oak ends at its mouth, the end round running out on the cup.
COUNTERBORE_GLUE_LINE = (0.05, 0.15)
COUNTERBORE_DIA = CUP_BODY_DIA + sum(COUNTERBORE_GLUE_LINE) / 2.0
COUNTERBORE_R = COUNTERBORE_DIA / 2.0
# The sheet prints the 1.5 wall over the bore as an inspectable minimum
# rather than a method (the MHA-022 machinist review of crank-v4-16 called a
# one-setup/mandrel note over-specification).  The walls budget 0.10 of
# eccentricity between the bore and the turned outside (local reviews of
# 1f3067ef2 and 4b46c8b53).
BORE_ECCENTRICITY = 0.10
# The MHA-153 cup can sit off the bore axis by this eccentricity plus half its
# widest glue line, 0.175 -- more than the screw's head and floor-hole
# clearances plus its float in the bore take up (0.165, local review of
# 4b46c8b53).  So the cup is epoxied in centred on the waxed MHA-139 screw
# through it and the bore (user ruling 2026-09-30): it cures where the screw
# fits, and the screw only turns about its own axis after.
CUP_OFFSET_MAX = BORE_ECCENTRICITY + COUNTERBORE_GLUE_LINE[1] / 2.0
# The printed limit on the counterbore (bored to suit the cup).
COUNTERBORE_DIA_MAX = round(
    CUP_BODY_DIA + CUP_BODY_DIA_TOL + COUNTERBORE_GLUE_LINE[1] + 0.05, 1
)
# The end round is turned on the oak only and crests square to the axis on
# the cup-face plane (the handle's basic length), outside the counterbore:
# the steel cup stays flat and uncut (local review of fbf82ad96, recommended
# option taken when the question timed out).  Crossing the cup, the crest
# had to clear the pocket by the cup's whole possible offset and could skim
# only ~0.001 off the steel.  The crest clears the largest counterbore turned
# its whole contour allowance small and off the mandrel axis by the bore's
# eccentricity, so turning never touches the cup.  Between the crest and the
# counterbore mouth the oak ends in a flat face on that plane.
END_ROUND_CY = COUNTERBORE_DIA_MAX / 2.0 + CONTOUR_ALLOWANCE_DIA / 2.0 + BORE_ECCENTRICITY

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
# Dome: convex, centre below the swell.
DOME_R = ((HANDLE_LENGTH - PEAK_X) ** 2 + (PEAK_R - DOME_THEORETICAL_R) ** 2) / (
    2.0 * (PEAK_R - DOME_THEORETICAL_R)
)
DOME_CENTER = (PEAK_X, PEAK_R - DOME_R)


# End round: crest (rightmost point) on the cup face at END_ROUND_CY, so its
# centre sits END_ROUND_R inside that face, internally tangent to the dome:
# (L - R - Xd)^2 + (Cy - Yd)^2 = (Rd - R)^2, solved for R in closed form.
_E_DX = HANDLE_LENGTH - DOME_CENTER[0]
_E_DY = END_ROUND_CY - DOME_CENTER[1]
END_ROUND_R = (DOME_R**2 - _E_DX**2 - _E_DY**2) / (2.0 * (DOME_R - _E_DX))
END_ROUND_CX = HANDLE_LENGTH - END_ROUND_R
END_ROUND_CENTER = (END_ROUND_CX, END_ROUND_CY)
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

# The title block's .X band on the routine sizes below.
_GENERAL_1PL = GENERAL_1PL_TOL_MM
# The oak's end face round the counterbore mouth is 0.45 wide at nominal and
# can feather to nothing at the worst case -- a named drawing-simplicity-policy
# exception (user ruling 2026-09-30): the bonded steel cup backs the edge.
# One millimetre in from the oak's end the oak round the largest
# counterbore, with the contour turned its whole allowance small and the
# bore's eccentricity, holds the 1.5 floor again.
FEATHER_DEPTH = 1.0
OAK_WALL_BEHIND_FEATHER = (
    profile_radius(OAK_END_X - FEATHER_DEPTH)
    - COUNTERBORE_DIA_MAX / 2.0
    - CONTOUR_ALLOWANCE_DIA / 2.0
    - BORE_ECCENTRICITY
)
# The tenon is turned to suit the actual ferrule bore (Codex P1/P2 on #1139):
# the largest banded bore with the tightest glue line gives the largest tenon,
# and the smallest bore with the widest line the smallest.
TENON_DIA_MAX = FERRULE_BORE_DIA + FERRULE_BORE_DIA_TOL - FERRULE_TENON_GLUE_LINE[0]
TENON_DIA_MIN = FERRULE_BORE_DIA - FERRULE_BORE_DIA_TOL - FERRULE_TENON_GLUE_LINE[1]
# The shoulder the ferrule seats on, radially, at its worst: the oak turned
# its whole allowance small at the shoulder over the largest tenon.
FERRULE_SEAT_RADIAL_MIN = (
    (2.0 * SHOULDER_R - CONTOUR_ALLOWANCE_DIA) - TENON_DIA_MAX
) / 2.0
# The shortest tenon's unbroken bonded length inside the ferrule, less the
# title-block edge break on the tenon end and on the ferrule's bore mouth
# (local review of 21bb244c5): 3.7, half the ferrule's length and more.
TENON_GLUE_LENGTH_MIN = round(TENON_LENGTH - _GENERAL_1PL - 2.0 * EDGE_BREAK_MAX_MM, 6)
# The printed minimum oak wall over the bore (checked at the tenon end face).
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
# Oak at the waist over the largest bore, the contour its whole allowance small.
WAIST_WALL_MIN = (
    (2.0 * WAIST_R - CONTOUR_ALLOWANCE_DIA) - (PIVOT_BORE_DIA + PIVOT_BORE_BAND[0])
) / 2.0 - BORE_ECCENTRICITY

for _ok, _what in (
    (
        TENON_END_GAP_MIN > 0.0,
        "the longest tenon reaches the shortest ferrule's arm face",
    ),
    (
        TENON_GLUE_LENGTH_MIN >= 3.5,
        "the shortest tenon leaves under 3.5 of unbroken glue length",
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
        2.0 * FERRULE_OUTER_DIA_TOL <= CONTOUR_ALLOWANCE_DIA,
        "turning the shoulder flush with the ferrule leaves the contour allowance",
    ),
    (WAIST_WALL_MIN >= 1.5, "the waist leaves under 1.5 over the bore"),
    (
        OAK_WALL_BEHIND_FEATHER >= 1.5,
        "oak 1.0 in from the feathered end is under 1.5 round the counterbore",
    ),
    (WAIST_R < SHOULDER_R and WAIST_R < PEAK_R, "the waist is not the neck's minimum"),
    (
        DOME_CENTER[0] < END_ROUND_CX < HANDLE_LENGTH and 0.0 < END_ROUND_R < DOME_R,
        "the end round does not sit inside the dome",
    ),
    (
        abs(END_ROUND_CX + END_ROUND_R - HANDLE_LENGTH) < 1e-9,
        "the end round does not crest on the cup-face plane",
    ),
    (
        END_ROUND_CY - CONTOUR_ALLOWANCE_DIA / 2.0 - BORE_ECCENTRICITY
        >= COUNTERBORE_DIA_MAX / 2.0 - 1e-9,
        "turning the end round can reach the cup",
    ),
    (COUNTERBORE_R > PIVOT_BORE_DIA / 2.0, "counterbore is inside the pivot bore"),
):
    if not _ok:
        raise AssertionError(f"MHA-022: {_what}")

# Marked dimensions.  The profile sketch owns the tenon, the oak overall from
# the tenon end, the peak station and the counterbore; the bore sketch owns
# the reamed bore.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "HandleProfile": {
        "TenonDia",
        "TenonLength",
        "OverallLength",
        "PeakStation",
        "CounterboreDia",
        "CounterboreDepth",
    },
    "PivotBoreProfile": {"PivotBoreDia"},
}
# Decimal places are the tolerance (policy rule 2): the reamed bore prints its
# band at two places; every other size is routine (.X), the fitted tenon and
# counterbore as references under their to-suit callouts.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HandleProfile": {
        "TenonDia": 1,
        "TenonLength": 1,
        "OverallLength": 1,
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
REFERENCE_DIMENSIONS = frozenset({"TenonDia", "CounterboreDia", "CounterboreDepth"})
# Every axial station reads from the tenon's end face, the one faced end, so
# the oak's overall (for stock cut-off) is a marked dimension of its own.
OVERALL_LENGTH = OAK_END_X - TENON_X0

FERRULE_NUMBER = "MHA-152"
CUP_NUMBER = "MHA-153"
SCREW_NUMBER = "MHA-139"


def _e(x: float) -> float:
    """A station from the tenon end face, as the sheet prints it."""
    return x - TENON_X0


# Named exception: MHA-022 oak feathers (drawing-simplicity-policy.md, "Named exceptions").
DRAWING_NOTES = "\n".join(
    (
        "AXIAL STATIONS ARE FROM THE TENON END FACE.",
        f"TURN THE TENON TO SUIT THE {FERRULE_NUMBER} FERRULE BORE AND BORE THE BUTT",
        f"  COUNTERBORE TO SUIT THE {CUP_NUMBER} CUP BODY, EACH FOR "
        f"{TENON_GLUE_LINE[0]:.2f}-{TENON_GLUE_LINE[1]:.2f} DIAMETRAL",
        f"  CLEARANCE, COUNTERBORE <MOD-DIAM>{COUNTERBORE_DIA_MAX:.1f} MAX, DEPTH TO SEAT THE CUP",
        f"  FACE FLUSH; EPOXY BOTH IN, THE CUP CENTRED ON THE WAXED {SCREW_NUMBER} SCREW.",
        f"AFTER CURE, TURN THE SHOULDER FLUSH WITH {FERRULE_NUMBER} AND THE END ROUND ON",
        f"  THE OAK ONLY, CLEAR OF {CUP_NUMBER}; AT WORST THE OAK FEATHERS AT THE CUP.",
        f"THE REAMED BORE RUNS ON THE {SCREW_NUMBER} SHOULDER; ITS LIMITS APPLY FULL LENGTH.",
        f"MIN OAK WALL {TENON_WALL_FLOOR_MM:.1f} OVER THE BORE, CORNERS EXCEPTED.",
        f"GRIP CONTOUR, TANGENT ARCS IN TURN: R{FLARE_R:.1f} FROM THE SHOULDER TO A",
        f"  <MOD-DIAM>{2.0 * WAIST_R:.1f} WAIST AT {_e(WAIST_X):.1f}; "
        f"R{S_CONCAVE_R:.1f} AND R{S_CONVEX_R:.1f} (INFLECTION AT {_e(INFLECTION_X):.1f})",
        f"  TO <MOD-DIAM>{HANDLE_MAX_DIA:.1f} AT {_e(PEAK_X):.1f}; R{DOME_R:.1f}; "
        f"R{END_ROUND_R:.1f} END ROUND TO A FLAT OAK END, CREST "
        f"<MOD-DIAM>{2.0 * END_ROUND_CY:.1f}.",
        f"  TURN WITHIN {CONTOUR_ALLOWANCE_DIA:.1f} ON DIAMETER; CHECK WITH A TEMPLATE.",
        "USE CLEAR STRAIGHT GRAIN PARALLEL TO TURNING AXIS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

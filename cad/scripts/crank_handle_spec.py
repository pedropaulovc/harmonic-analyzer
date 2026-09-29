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

from _fit_limits import band_text
from crank_handle_butt_cup_spec import (
    BODY_DIA as CUP_BODY_DIA,
    BODY_DIA_TOL as CUP_BODY_DIA_TOL,
    BODY_LENGTH as CUP_BODY_LENGTH,
    FLANGE_DIA as CUP_FLANGE_DIA,
    FLANGE_THICKNESS as CUP_FLANGE_THICKNESS,
    OVERALL_LENGTH_TOL as CUP_OVERALL_LENGTH_TOL,
    FLANGE_THICKNESS_TOL as CUP_FLANGE_THICKNESS_TOL,
)
from crank_handle_ferrule_spec import (
    BORE_DIA as FERRULE_BORE_DIA,
    BORE_DIA_BAND as FERRULE_BORE_DIA_BAND,
    LENGTH as FERRULE_LENGTH,
    LENGTH_TOL as FERRULE_LENGTH_TOL,
)

# 2026-09-02 user re-read of the pass-2 model against ch11 p.14 and the ch30
# p002 front view: overall 58 from the arm face, swell 21 across at 0.62 of
# the length, neck Ø11, butt Ø10.  The basic profile still runs the whole 58:
# the ferrule and the cup flange now take its two ends.
HANDLE_LENGTH = 58.0  # basic: ferrule arm face to cup flange face
HANDLE_MAX_DIA = 21.0  # max diameter at the swell
NECK_R = 5.5  # waist at the tenon shoulder (neck Ø11)
PEAK_X = 36.0  # axial station of the maximum diameter, from x=0
CAP_R = 5.0  # theoretical butt radius at HANDLE_LENGTH (Ø10)
PIVOT_BORE_DIA = 6.125  # final reamed bore limits 6.10-6.15
# Symmetric ream band about the mid nominal: 6.15 MAX / 6.10 MIN.
PIVOT_BORE_BAND = (0.025, -0.025)

# The tenon shoulder (datum B) is where the ferrule seats, FERRULE_LENGTH from
# the arm face.
SHOULDER_X = FERRULE_LENGTH
# The tenon slips inside the ferrule bore for an epoxy line: 0.03-0.12 on
# diameter.  Symmetric band.
TENON_DIA = 9.95
TENON_DIA_TOL = 0.02
# The tenon stops short of the ferrule's arm face at the .X worst case, so the
# oak never bears on the arm.
TENON_LENGTH = 6.0
TENON_X0 = SHOULDER_X - TENON_LENGTH

# The butt is trimmed where the cup flange seats: the flange face lands on the
# basic HANDLE_LENGTH.  Wood from datum B to the trim face, (upper, lower):
# unilateral, the butt may come short of the basic profile but never long.
TRIM_X = HANDLE_LENGTH - CUP_FLANGE_THICKNESS
WOOD_LENGTH = TRIM_X - SHOULDER_X
WOOD_LENGTH_BAND = (0.000, -0.250)
# The counterbore takes the cup body for an epoxy line (+0.05/0).
COUNTERBORE_DIA = 9.45
COUNTERBORE_DIA_BAND = (0.05, 0.0)
COUNTERBORE_DEPTH = 5.0
# Collar/ferrule OD kept by name for the drawing's end view reach.
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


def _limits(nominal: float, band: tuple[float, float]) -> tuple[float, float]:
    upper, lower = band
    return nominal + lower, nominal + upper


_TENON_MAX = TENON_DIA + TENON_DIA_TOL
_TENON_MIN = TENON_DIA - TENON_DIA_TOL
_FERRULE_BORE_MIN, _FERRULE_BORE_MAX = _limits(FERRULE_BORE_DIA, FERRULE_BORE_DIA_BAND)
_CBORE_MIN, _CBORE_MAX = _limits(COUNTERBORE_DIA, COUNTERBORE_DIA_BAND)
_CUP_BODY_MAX = CUP_BODY_DIA + CUP_BODY_DIA_TOL
_CUP_BODY_MIN = CUP_BODY_DIA - CUP_BODY_DIA_TOL
_CUP_BODY_LENGTH_MAX = CUP_BODY_LENGTH + CUP_OVERALL_LENGTH_TOL + CUP_FLANGE_THICKNESS_TOL
# The title block's .X band on the two routine (.X) sizes below.
_GENERAL_1PL = 0.8
TENON_GLUE_LINE = (_FERRULE_BORE_MIN - _TENON_MAX, _FERRULE_BORE_MAX - _TENON_MIN)
CUP_GLUE_LINE = (_CBORE_MIN - _CUP_BODY_MAX, _CBORE_MAX - _CUP_BODY_MIN)
# Oak left around the counterbore at its mouth, under the cup flange.
COUNTERBORE_MOUTH_WALL = TRIM_R - _CBORE_MAX / 2.0

for _ok, _what in (
    (TENON_GLUE_LINE[0] > 0.0, "tenon can bind in the MHA-150 ferrule"),
    (TENON_GLUE_LINE[1] <= 0.15, "tenon glue line is over 0.15"),
    (CUP_GLUE_LINE[0] > 0.0, "cup body can bind in the counterbore"),
    (CUP_GLUE_LINE[1] <= 0.15, "cup glue line is over 0.15"),
    (
        TENON_LENGTH + _GENERAL_1PL < FERRULE_LENGTH - FERRULE_LENGTH_TOL,
        "the longest tenon reaches the ferrule's arm face",
    ),
    (TENON_R < NECK_R, "the tenon leaves no shoulder for the ferrule to seat on"),
    (
        COUNTERBORE_DEPTH - _GENERAL_1PL > _CUP_BODY_LENGTH_MAX,
        "the cup body can bottom in the shallowest counterbore before its flange seats",
    ),
    (COUNTERBORE_MOUTH_WALL >= 0.6, "oak at the counterbore mouth is under 0.6"),
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
# Decimal places are the tolerance (policy rule 2): the stack, fit and basic
# stations at two places; the routine tenon length and counterbore depth .X;
# the reamed bore at two with its own band.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "HandleProfile": {
        "TenonDia": 2,
        "TenonLength": 1,
        "WoodLength": 2,
        "PeakStation": 2,
        "CounterboreDia": 2,
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
BASIC_DIMENSIONS = frozenset({"PeakStation"})

_B = f"{0.0:.2f}"
_PEAK_B = PEAK_X - SHOULDER_X
_END_B = HANDLE_LENGTH - SHOULDER_X
DRAWING_NOTES = "\n".join(
    (
        f"DATUM A IS THE <MOD-DIAM>{PIVOT_BORE_DIA:.2f} REAMED BORE AXIS. DATUM B IS THE TENON",
        "  SHOULDER FACE. FINAL BORE LIMITS APPLY FULL LENGTH.",
        f"ALL AXIAL STATIONS ARE FROM B; {WOOD_LENGTH:.2f}{band_text(WOOD_LENGTH_BAND)} IS WOOD, B TO BUTT FACE.",
        f"BASIC TRUE GRIP PROFILE (ALL VALUES BASIC): <MOD-DIAM>{2.0 * NECK_R:.2f} AT X{_B};",
        f"  <MOD-DIAM>{HANDLE_MAX_DIA:.2f} AT X{_PEAK_B:.2f}; <MOD-DIAM>{2.0 * CAP_R:.2f} AT X{_END_B:.2f}. TWO CIRCULAR ARCS",
        f"  TANGENT AT X{_PEAK_B:.2f}: R{FRONT_PROFILE_R:.6f} FROM X{_B} TO X{_PEAK_B:.2f};",
        f"  R{REAR_PROFILE_R:.6f} FROM X{_PEAK_B:.2f} TO X{_END_B:.2f}.",
        "PROFILE 0.50 | A | B APPLIES TO BOTH ARCS FROM B TO THE ACTUAL BUTT",
        f"  FACE; THEORETICAL PROFILE EXTENDS TO X{_END_B:.2f}.",
        "SHOULDER AND BUTT EDGES SHARP. NO BLEND, RADIUS, OR CHAMFER.",
        "USE CLEAR STRAIGHT GRAIN PARALLEL TO TURNING AXIS.",
    )
)
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"


# Manufacturing GD&T limits consumed by the part's drawing projection.
GEOMETRIC_TOLERANCES_MM: dict[str, str] = {
    "shoulder perpendicularity": "0.10",
    "tenon total runout": "0.10",
    "turned handle profile": "0.50",
}

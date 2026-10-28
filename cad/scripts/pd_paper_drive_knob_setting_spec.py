"""The reducer's S-K setting as model dimensions (MHA-PD-00 VIEW K).

The matched knob bore K is jig-bored on the mill DRO from the arm's reamed
pin bore S, before the MHA-PD-23 pin is pressed into it (its one turned shank
is the pressed pin's running axis): the arm trammed on its pivot bore P and
S, the DRO zeroed on S, the plate tapped till its knob bore indicates true at
K's two coordinates from S, along the arm toward P and across it to the
plate's notch side. K is aimed at the middle of the +x/-0 set band
(``pd_rack_pinion_spec.CENTRE_DISTANCE_WINDOW``) so the DRO and indicator
setting error, worst case, stays inside it at both ends
(test_pd_paper_drive_assembly_drawing). The two coordinates are DRO counts:
of the counts about the mid-band point on the nominal S-K line, the one
nearest the band's middle, which leaves the most margin at both ends.

``build_pd_paper_drive_assembly`` authors these as one hidden construction
sketch in the assembly, on its Front plane (sketch x, y = machine x, y): P to
S along the arm, S to Q along it toward P, Q to K across it, and the S-K
line, on which the nominal centre N stands at CENTRE_DISTANCE from S. S to N
is the set band itself, a toleranced model dimension (+x/-0); the two DRO
coordinates to the aimed K are references. All three are marked for
MHA-PD-00, whose sheet 5 VIEW K prints them and whose arm-plate-located
step cites it; the step prints no value of its own. No solid or pose
changes.
"""

from __future__ import annotations

import math

import _paper_drive_placement as placement
import pd_rack_pinion_spec as disc
import pd_transgear_arm_geometry as arm

FEATURE = "KnobSettingReference"
ALONG_DIMENSION = "KnobSetAlong"
ACROSS_DIMENSION = "KnobSetAcross"
CENTRE_DIMENSION = "KnobSetCentre"
DRAWING_DIMENSIONS = {FEATURE: {ALONG_DIMENSION, ACROSS_DIMENSION, CENTRE_DIMENSION}}
PLACES = 3
DRAWING_PRECISION = {
    FEATURE: {
        ALONG_DIMENSION: PLACES,
        ACROSS_DIMENSION: PLACES,
        CENTRE_DIMENSION: PLACES,
    }
}
# The set band on S to N, as (lower, upper) deviations: +x/-0.
CENTRE_TOLERANCE_MM = (
    disc.CENTRE_DISTANCE_SET_BAND[1],
    disc.CENTRE_DISTANCE_SET_BAND[0],
)

# The installed mill DRO's display count (shop inventory
# machines.PM-30MV.resolution_mm; test_pd_paper_drive_assembly_drawing
# holds the two equal).
DRO_COUNT_MM = 0.005
# K aimed at the band's middle, on the nominal S-K line.
K_SET_CENTRE_DISTANCE_MM = sum(disc.CENTRE_DISTANCE_WINDOW) / 2.0
_S_TO_K = (arm.KNOB_BORE_STATION - arm.PIN_STATION, arm.KNOB_BORE_OFFSET)
_S_TO_K_UNIT = (_S_TO_K[0] / math.hypot(*_S_TO_K), _S_TO_K[1] / math.hypot(*_S_TO_K))
# From S: toward the pivot along the arm, and across it to the plate's notch
# side (both negative in the arm frame).
K_AIM_FROM_S_MM = (
    -_S_TO_K_UNIT[0] * K_SET_CENTRE_DISTANCE_MM,
    -_S_TO_K_UNIT[1] * K_SET_CENTRE_DISTANCE_MM,
)


def dro_count_candidates() -> list[tuple[float, float]]:
    """The DRO counts about the aim, one count either way on each axis."""
    along, across = (round(value / DRO_COUNT_MM) for value in K_AIM_FROM_S_MM)
    return [
        (round((along + i) * DRO_COUNT_MM, 6), round((across + j) * DRO_COUNT_MM, 6))
        for i in (-1, 0, 1)
        for j in (-1, 0, 1)
    ]


def _off_middle(point: tuple[float, float]) -> tuple[float, float]:
    # Radially off the band's middle, then off the nominal line.
    return (
        abs(math.hypot(*point) - K_SET_CENTRE_DISTANCE_MM),
        abs(point[0] * _S_TO_K_UNIT[1] - point[1] * _S_TO_K_UNIT[0]),
    )


K_FROM_S_ALONG_MM, K_FROM_S_ACROSS_MM = min(dro_count_candidates(), key=_off_middle)
if K_FROM_S_ALONG_MM <= 0.0 or K_FROM_S_ACROSS_MM <= 0.0:
    raise AssertionError("K is no longer toward the pivot and the notch side of S")

# The chain's points in the machine frame (the assembly's Front plane).
P_XY = placement.PIVOT_XY
S_XY = placement.STUD_XY
if abs(math.dist(P_XY, S_XY) - arm.PIN_STATION) > 1e-9:
    raise AssertionError("the pressed stud no longer sits at the arm's pin station")
Q_XY = (
    S_XY[0] - K_FROM_S_ALONG_MM * arm.ARM_U[0],
    S_XY[1] - K_FROM_S_ALONG_MM * arm.ARM_U[1],
)
K_XY = (
    Q_XY[0] - K_FROM_S_ACROSS_MM * arm.ARM_N[0],
    Q_XY[1] - K_FROM_S_ACROSS_MM * arm.ARM_N[1],
)
# The nominal centre N on the aimed S-K line.
_S_TO_K_AIM = (K_XY[0] - S_XY[0], K_XY[1] - S_XY[1])
_NOMINAL_SCALE = disc.CENTRE_DISTANCE / math.hypot(*_S_TO_K_AIM)
N_XY = (
    S_XY[0] + _S_TO_K_AIM[0] * _NOMINAL_SCALE,
    S_XY[1] + _S_TO_K_AIM[1] * _NOMINAL_SCALE,
)

# Native IDisplayDimension.SetText compartments (swDimensionTextParts_e):
# 1/2 prefix/suffix, the reference parentheses (S to N's set band governs
# K, not the title block); 3 the one-line above-callout naming the
# coordinate.
REFERENCE_DIMENSIONS = frozenset({ALONG_DIMENSION, ACROSS_DIMENSION})
SETTING_CALLOUTS = {
    ALONG_DIMENSION: (3, "ALONG"),
    ACROSS_DIMENSION: (3, "ACROSS"),
}

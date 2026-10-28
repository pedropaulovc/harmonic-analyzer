"""The reducer's S-K setting as model dimensions (MHA-PD-00 step 10).

The matched knob bore K is jig-bored on the mill DRO from the pressed
MHA-PD-23 pin S: the arm trammed on its pivot bore P and S, the DRO zeroed on
S, the plate tapped till its knob bore indicates true at K's two coordinates
from S, along the arm toward P and across it to the plate's notch side. K is
aimed at the middle of the +x/-0 set band
(``pd_rack_pinion_spec.CENTRE_DISTANCE_WINDOW``) so the DRO and indicator
setting error, worst case, stays inside it at both ends
(test_pd_paper_drive_assembly_drawing).

``build_pd_paper_drive_assembly`` authors these as one hidden construction
chain in the assembly, on its Front plane (sketch x, y = machine x, y): P to
S along the arm, S to Q along it toward P, Q to K across it. Its two setting
dimensions are marked for MHA-PD-00, whose sheet 5 view prints them and step
10 cites; the step prints no value of its own. No solid or pose changes.
"""

from __future__ import annotations

import math

import _paper_drive_placement as placement
import pd_rack_pinion_spec as disc
import pd_transgear_arm_geometry as arm

FEATURE = "KnobSettingReference"
ALONG_DIMENSION = "KnobSetAlong"
ACROSS_DIMENSION = "KnobSetAcross"
DRAWING_DIMENSIONS = {FEATURE: {ALONG_DIMENSION, ACROSS_DIMENSION}}
PLACES = 3
DRAWING_PRECISION = {FEATURE: {ALONG_DIMENSION: PLACES, ACROSS_DIMENSION: PLACES}}

# K aimed at the band's middle, on the nominal S-K line.
K_SET_CENTRE_DISTANCE_MM = sum(disc.CENTRE_DISTANCE_WINDOW) / 2.0
_S_TO_K = (arm.KNOB_BORE_STATION - arm.PIN_STATION, arm.KNOB_BORE_OFFSET)
_SCALE = K_SET_CENTRE_DISTANCE_MM / math.hypot(*_S_TO_K)
# From S: toward the pivot along the arm, and across it to the plate's notch
# side (both negative in the arm frame).
K_FROM_S_ALONG_MM = -_S_TO_K[0] * _SCALE
K_FROM_S_ACROSS_MM = -_S_TO_K[1] * _SCALE
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

# Native IDisplayDimension.SetText compartments (swDimensionTextParts_e):
# 1/2 prefix/suffix, the reference parentheses (the set band, printed on the
# arm and plate sheets, governs K, not the title block); 3 the one-line
# above-callout naming the coordinate.
REFERENCE_DIMENSIONS = frozenset({ALONG_DIMENSION, ACROSS_DIMENSION})
SETTING_CALLOUTS = {
    ALONG_DIMENSION: (3, "ALONG"),
    ACROSS_DIMENSION: (3, "ACROSS"),
}

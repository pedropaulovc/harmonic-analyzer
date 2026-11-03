"""Pure-data drawing contract for the rocker pivot bracket (MHA-CH-08).

Split from ``ch_pivot_bracket_spec`` on purpose: that module is the section
contract ``rocker_bank_layout``, ``ch_pivot_shaft_spec``, the channel assembly
and the bracket's two fixtures import, so a drawing-only edit there would
re-key all of them. This module is imported only by the part build (which
authors the marks, places, bands and PMI) and its drawing
(``fr_rocker_arm_support_drawing_spec``'s precedent).
"""

from __future__ import annotations

import math

from _gtol_planar import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from ch_pivot_bracket_sides import HEAD_TO_EAR_FACE_MIN
from ch_pivot_bracket_spec import DRILL_GROWTH, UNIT

# The foot seats on the rocker-arm support's apex and sets the pivot height:
# the one static seat that locates the part (drawing-guidelines.md rule 6), so
# it carries the seat grade. PlanarFace offsets run along the outward normal,
# so the -Y seat at y = 0 sits at 0.
SURFACE_FINISHES = (
    SurfaceFinishControl(
        "foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0), display_unit=UNIT
    ),
)

# The cross-bore holds the drilled-hole row's +.004/0 explicitly (upper,
# lower; fit F5): the apex set screw's full thread is counted at this largest
# bore (ch_pivot_bracket_spec.BORE_RADIUS_MAX), so the print must not leave
# the bore to the .XXX row's +/-.005.
BORE_DIA_BAND = (DRILL_GROWTH, 0.0)

# The foot-to-ear inside corner (drawing-guidelines.md rule 16): the largest
# radius the shop may leave there, so it can pick a rigid cutter. The
# hold-down screw's head seats on the foot top beside the ear's outboard face
# (ch_pivot_bracket_sides.HEAD_TO_EAR_FACE_MIN, the worst-case gap), so a
# corner radius past that gap would lift the head's edge; the limit is that
# gap rounded DOWN to the inch places it prints at. The part models the
# corner AT the limit and prints it as the single limit "R.02 MAX" (swTolMAX
# prints the nominal, so nominal = limit; the band runs from sharp up to it).
CORNER_R_PLACES = 2
CORNER_R_MAX = (
    math.floor(HEAD_TO_EAR_FACE_MIN / 25.4 * 10**CORNER_R_PLACES + 1e-9)
    / 10**CORNER_R_PLACES
    * 25.4
)
CORNER_R_BAND = (0.0, -CORNER_R_MAX)  # (upper, lower)
CORNER_R_TOL_TYPE = 6  # swTolType_e.swTolMAX: prints "R.02 MAX"
if not 0.0 < CORNER_R_MAX <= HEAD_TO_EAR_FACE_MIN:
    raise AssertionError(
        "the foot-to-ear corner has no printable radius the screw head clears"
        f" ({HEAD_TO_EAR_FACE_MIN:.4f})"
    )

# Hidden reference sketches (drawing-simplicity-policy.md `How the repository
# implements the guidelines`): the bore's and the hold-down hole's lateral
# locations off the west side face, the apex tap's station off the ear's
# inboard face, and the overall height off the seat (rule 10: every height
# from the seat, #1371) are manufacturing dimensions no feature dimension
# measures (the profiles are X-centred, the wizard tap is placed from the
# origin, and the arch's centre sits off the bore). Each gets a one-line
# construction sketch whose single driving dimension IS the value; the part
# saves them blanked and the drawing shows each in the one view that
# dimensions it.
REFERENCE_SKETCHES = (
    "BoreLateralReference",
    "HoleLateralReference",
    "SetScrewReference",
    "HeightReference",
)

DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "FootProfile": {"FootW", "FootLen"},
    "Foot": {"FootHt"},
    "Ear": {"EarThick"},
    # The arch: the boss's own RADIUS, printed as modelled.
    "ArchProfile": {"ArchRadius"},
    "ShaftBoreProfile": {"BoreCz", "ShaftBoreDia"},
    "HoleProfile": {"HoleStation", "HoleDia"},
    "BoreLateralReference": {"BoreLateral"},
    "HoleLateralReference": {"HoleLateral"},
    "SetScrewReference": {"SetScrewLocation"},
    "HeightReference": {"OverallHeight"},
    # The foot-to-ear inside corner's single-limit radius (CORNER_R_MAX).
    "CornerFillet": {"CornerRadius"},
}

# Decimal places ARE the tolerance statement, so the MODEL owns them:
# build_ch_pivot_bracket applies this map to the .SLDPRT and the drawing only
# reads it back. Inch places, .XX unless stated:
# - the foot's sides and the hole's centring ride the .XX band the ligament
#   check spends (ch_pivot_bracket_spec EDGE_BAND, HOLE_X_BAND), and the arch
#   radius, the overall height and the bore height the bands the set screw's
#   full thread is counted at (ARCH_R_BAND, HEIGHT_BAND);
# - the foot length and the hold-down station ride the title block's .XX
#   (ch_pivot_bracket_sides proves the foot for them); the ear thickness and
#   tap station carry their own +/-.004, so print .XXX;
# - the foot height sits at .XX in the support's seat-screw reach
#   (rocker_bracket_seat_layout.FOOT_H_RANGE);
# - the bore lateral is a routine location of a fitted bore; the cross-bore
#   (+.004/0) and the drilled hold-down hole print their size at .XXX;
# - the corner radius is a single limit at CORNER_R_PLACES (rule 3: no extra
#   places on radii).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FootProfile": {"FootW": 2, "FootLen": 2},
    "Foot": {"FootHt": 2},
    "Ear": {"EarThick": 3},
    "ArchProfile": {"ArchRadius": 2},
    "ShaftBoreProfile": {"BoreCz": 2, "ShaftBoreDia": 3},
    "HoleProfile": {"HoleStation": 2, "HoleDia": 3},
    "BoreLateralReference": {"BoreLateral": 2},
    "HoleLateralReference": {"HoleLateral": 2},
    "SetScrewReference": {"SetScrewLocation": 3},
    "HeightReference": {"OverallHeight": 2},
    "CornerFillet": {"CornerRadius": CORNER_R_PLACES},
}

_PRECISION_NAMES = [
    (feature, name) for feature, names in DRAWING_PRECISION.items() for name in names
]
if {feature: set(names) for feature, names in DRAWING_PRECISION.items()} != (
    DRAWING_DIMENSIONS
):
    raise AssertionError("DRAWING_PRECISION and DRAWING_DIMENSIONS disagree")
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: DRAWING_PRECISION[feature][name] for feature, name in _PRECISION_NAMES
}
if len(DRAWING_PRECISION_BY_NAME) != len(_PRECISION_NAMES):
    raise AssertionError("DRAWING_PRECISION repeats a dimension name across features")

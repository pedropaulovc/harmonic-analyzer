"""Pure-data drawing contract for the rocker pivot bracket (MHA-CH-008).

Split from ``ch_pivot_bracket_spec`` on purpose: that module is the section
contract ``rocker_bank_layout``, ``ch_pivot_shaft_spec``, the channel assembly
and the bracket's two fixtures import, so a drawing-only edit there would
re-key all of them. This module is imported only by the part build (which
authors the marks, places, bands and PMI) and its drawing
(``fr_rocker_arm_support_drawing_spec``'s precedent).
"""

from __future__ import annotations

from _gtol_planar import PlanarFace
from _surface_finish import SEAT_UM, SurfaceFinishControl
from ch_pivot_bracket_spec import DRILL_GROWTH

# The foot seats on the rocker-arm support's apex and sets the pivot height:
# the one static seat that locates the part (drawing-guidelines.md rule 6), so
# it carries the seat grade. PlanarFace offsets run along the outward normal,
# so the -Y seat at y = 0 sits at 0.
SURFACE_FINISHES = (
    SurfaceFinishControl("foot_seat", SEAT_UM, PlanarFace((0, -1, 0), 0.0)),
)

# The reamed cross-bore holds the drilled-hole row's +0.10/0 explicitly
# (upper, lower): the apex set screw's full thread is counted at this largest
# bore (ch_pivot_bracket_spec.BORE_RADIUS_MAX), so the print must not leave
# the reamed bore to the .XX row's +/-0.51.
BORE_DIA_BAND = (DRILL_GROWTH, 0.0)

# Hidden reference sketches (drawing-simplicity-policy.md `How the repository
# implements the guidelines`): the bore's and the hold-down hole's lateral
# locations off the west side face, and the apex tap's station off the ear's
# inboard face, are manufacturing dimensions no feature dimension measures
# (the profiles are X-centred and the wizard tap is placed from the origin).
# Each gets a one-line construction sketch on the part outline whose single
# driving dimension IS the value; the part saves them blanked and the drawing
# shows each in the one view that dimensions it.
REFERENCE_SKETCHES = (
    "BoreLateralReference",
    "HoleLateralReference",
    "SetScrewReference",
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
}

# Decimal places ARE the tolerance statement, so the MODEL owns them:
# build_ch_pivot_bracket applies this map to the .SLDPRT and the drawing only
# reads it back. Every value is .XX:
# - the foot's sides and the hole's centring ride the .XX band the ligament
#   check spends (ch_pivot_bracket_spec EDGE_BAND, HOLE_X_BAND), and the arch
#   radius the band the set screw's full thread is counted at (ARCH_R_BAND);
# - the foot length, ear thickness, hole station and tap station carry their
#   own +/-0.10 at two places;
# - the foot height sits at .XX in the support's seat-screw reach
#   (rocker_bracket_seat_layout.FOOT_H_RANGE);
# - the bore height and bore lateral are routine locations of a fitted bore,
#   and the drilled holes print their drill size to two places.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "FootProfile": {"FootW": 2, "FootLen": 2},
    "Foot": {"FootHt": 2},
    "Ear": {"EarThick": 2},
    "ArchProfile": {"ArchRadius": 2},
    "ShaftBoreProfile": {"BoreCz": 2, "ShaftBoreDia": 2},
    "HoleProfile": {"HoleStation": 2, "HoleDia": 2},
    "BoreLateralReference": {"BoreLateral": 2},
    "HoleLateralReference": {"HoleLateral": 2},
    "SetScrewReference": {"SetScrewLocation": 2},
}

# Places for the one dimension the SHEET derives, keyed by the recipe's own
# label: the parenthesised overall height, a band-free restatement of the
# bore height plus the arch radius. Two places, like the two it sums.
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"overall height": 2}

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

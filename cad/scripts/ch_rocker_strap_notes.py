r"""Rocker strap (MHA-CH-13) drawing-only data: the marked-dimension and
precision contract, the callouts, and the isometric label the part build
stamps into the SLDPRT.

Kept out of ``ch_rocker_strap_spec`` (the ``ch_rocker_arm_notes`` split).
Imported ONLY by ``build_ch_rocker_strap``, ``draw_ch_rocker_strap`` and the
offline test. The fork fit's wording is the finished part's
(``ch_rocker_arm_notes``), so the two prints name that mate alike.
"""

from __future__ import annotations

from ch_rocker_arm_notes import STRAP_FIT_CALLOUT
from ch_rocker_strap_spec import HUB_NUMBER

__all__ = [
    "DIMENSION_CALLOUTS",
    "DRAWING_DIMENSIONS",
    "DRAWING_PRECISION",
    "DRAWING_PRECISION_BY_NAME",
    "HOLE_CALLOUT",
    "ISOMETRIC_VIEW_NOTE",
    "STRAP_FIT_CALLOUT",
    "TIP_LAND_ANGLE_PREFIX",
    "TIP_LAND_PREFIX",
]

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). One sketch,
# ``StrapProfile``, carries the outline and the hub hole, and every printed
# location runs from the hub hole's centre (rule 10: from a real feature):
# the top edge's height over it (one-sided plus) and the bottom edge's depth
# under it (one-sided minus) -- the finished part's bands -- both on the
# hole's vertical centreline, the symmetry axis both arcs' centres lie on;
# both tip lands' and both taper feet's offsets, each arc's radius, the
# tip land and its angle from the hole's vertical centreline (the lands are
# radial to the arcs' centre, which is off the sheet). The thickness is the
# ``Strap`` extrude's depth, on the end view.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {
        "HoleDia",
        "TopAbovePivot",
        "BottomBelowPivot",
        "TopRadius",
        "BottomRadius",
        "TailTipX",
        "RodTipX",
        "BottomTailX",
        "BottomRodX",
        "RodTipLen",
        "TipLandAngle",
    },
    "Strap": {"StrapThickness"},
}
# The hole at four places with its press band; the thickness at three with
# its band; both edges at three with their one-sided bands, the .315 the
# finished MHA-CH-06 prints (at two places the 8 mm nominal rounds to .31 and
# shifts each edge's limits .005 off the rocker's profile zone); the radii at
# one (noncritical sizes: each edge is held at the centreline by its own
# height, and a .1 radius error moves the 5.76 half-chord's sagitta .002);
# the offsets and the land at two (the title block's .XX); the land angle at
# one, under the title block's angular +/-1 deg.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "HoleDia": 4,
        "TopAbovePivot": 3,
        "BottomBelowPivot": 3,
        "TopRadius": 1,
        "BottomRadius": 1,
        "TailTipX": 2,
        "RodTipX": 2,
        "BottomTailX": 2,
        "BottomRodX": 2,
        "RodTipLen": 2,
        "TipLandAngle": 1,
    },
    "Strap": {"StrapThickness": 3},
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: decimals
    for dimensions in DRAWING_PRECISION.values()
    for name, decimals in dimensions.items()
}
if {name for names in DRAWING_DIMENSIONS.values() for name in names} != set(
    DRAWING_PRECISION_BY_NAME
):
    raise AssertionError("every marked strap dimension needs authored places")

# Both lands print as one 2X (the J land is the K land's mirror), and so does
# their angle.
TIP_LAND_PREFIX = "2X "
TIP_LAND_ANGLE_PREFIX = "2X "

# drawing-guidelines.md rule 4: the press band names its mate and the fit;
# the interference follows from both parts' limits. The hole's two edges stay
# sharp, overriding the title block's edge break for this hole only (a break
# would leave a ring groove round the pressed hub's root, where MHA-CH-06
# prints the hub-to-strap root as a MAX radius): a short requirement written
# at its leader (rule 7). Below rows (an ABOVE-compartment line break never
# prints).
HOLE_EDGE_CALLOUT = "BOTH EDGES SHARP, NO BURR"
HOLE_CALLOUT = f"REAM THRU\nPRESS FIT ON {HUB_NUMBER}\n{HOLE_EDGE_CALLOUT}"
# A location dimension carries its value and band only (rule 7), and each
# arc prints its own radius (rule 26: no "concentric" or "centre above"
# sentence), so only the sizes carry words.
DIMENSION_CALLOUTS: dict[str, str] = {
    "HoleDia": HOLE_CALLOUT,
    "StrapThickness": STRAP_FIT_CALLOUT,
}

ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

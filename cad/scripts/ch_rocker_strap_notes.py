r"""Rocker strap (MHA-CH-013) drawing-only data: the marked-dimension and
precision contract, the callouts, and the notes the part build stamps into
the SLDPRT.

Kept out of ``ch_rocker_strap_spec`` (the ``ch_rocker_arm_notes`` split).
Imported ONLY by ``build_ch_rocker_strap``, ``draw_ch_rocker_strap`` and the
offline test. The mates' wording is the finished part's
(``ch_rocker_arm_notes``), so the two prints name each mate alike.
"""

from __future__ import annotations

from ch_rocker_arm_notes import (
    STRAP_FIT_CALLOUT,
    TOP_EDGE_MATE_CALLOUT,
)
from ch_rocker_hub_fit import INTERFERENCE_TEXT
from ch_rocker_strap_spec import HUB_NUMBER, R_TOP, ROCKER_NUMBER

__all__ = [
    "BOTTOM_EDGE_CALLOUT",
    "DIMENSION_CALLOUTS",
    "DRAWING_DIMENSIONS",
    "DRAWING_NOTES",
    "DRAWING_PRECISION",
    "DRAWING_PRECISION_BY_NAME",
    "HOLE_CALLOUT",
    "HOLE_EDGE_CALLOUT",
    "ISOMETRIC_VIEW_NOTE",
    "STRAP_FIT_CALLOUT",
    "TIP_LAND_CALLOUT",
    "TIP_LAND_PREFIX",
    "TOP_EDGE_MATE_CALLOUT",
    "TOP_RADIUS_CALLOUT",
]

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). One sketch,
# ``StrapProfile``, carries the outline and the hub hole, and every printed
# location runs from the hub hole's centre (rule 10: from a real feature):
# the top edge's height over it (+0.50/0) and the bottom edge's depth under
# it (0/-0.50) -- the finished part's bands -- both tip lands' and both taper
# feet's offsets, the R800 and the tip land. The concentric R816 follows from
# those (never a second, stacking size). The thickness is the ``Strap``
# extrude's depth, on the end view.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {
        "HoleDia",
        "TopAbovePivot",
        "BottomBelowPivot",
        "TopRadius",
        "TailTipX",
        "RodTipX",
        "BottomTailX",
        "BottomRodX",
        "RodTipLen",
    },
    "Strap": {"StrapThickness"},
}
# The hole at three places with its H7 band; the thickness at three with its
# ±0.025; both edges at two with their one-sided 0.50; the radius at one (a
# noncritical size: a 0.8 radius error moves the 146 mm half-chord's sagitta
# 0.01); the offsets and the land at two (the title block's ±0.51).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "HoleDia": 3,
        "TopAbovePivot": 2,
        "BottomBelowPivot": 2,
        "TopRadius": 1,
        "TailTipX": 2,
        "RodTipX": 2,
        "BottomTailX": 2,
        "BottomRodX": 2,
        "RodTipLen": 2,
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

# Both lands print as one 2X (the J land is the K land's mirror).
TIP_LAND_PREFIX = "2X "

# The hole's two edges stay sharp, overriding the title block's R0.25 /
# C0.25 break for this hole only: a break would leave a ring groove round the
# pressed hub's root, where MHA-CH-006 prints the hub-to-strap root as
# "2X R0.2 MAX" (a corner, not a groove).
HOLE_EDGE_CALLOUT = "BOTH EDGES SHARP, NO BURR"
# drawing-guidelines.md rule 4: the H7 band names its mate and the fit. Below
# rows (an ABOVE-compartment line break never prints).
HOLE_CALLOUT = (
    f"REAM THRU\n{HOLE_EDGE_CALLOUT}\nPRESS FIT ON {HUB_NUMBER} HUB\n{INTERFERENCE_TEXT}"
)
# The bottom edge's one-sided band is the joined part's lower profile (rule 4:
# the need it serves), and that edge is the R800's concentric arc. Two short
# rows: the text sits between the R800's leader and the hole's extension line.
BOTTOM_EDGE_CALLOUT = f"{ROCKER_NUMBER} PROFILE\nCONCENTRIC WITH R{R_TOP:.0f}"
# The arcs' centre (~808 mm off the sheet) and the lands' radial direction
# are geometry, so they ride on the dimensions they qualify rather than in a
# general note (r1 and r3 machinist reviews, rule 7).
TOP_RADIUS_CALLOUT = "CENTRE ABOVE HOLE"
TIP_LAND_CALLOUT = "RADIAL"
DIMENSION_CALLOUTS: dict[str, str] = {
    "HoleDia": HOLE_CALLOUT,
    "TopAbovePivot": TOP_EDGE_MATE_CALLOUT,
    "BottomBelowPivot": BOTTOM_EDGE_CALLOUT,
    "TopRadius": TOP_RADIUS_CALLOUT,
    "RodTipLen": TIP_LAND_CALLOUT,
    "StrapThickness": STRAP_FIT_CALLOUT,
}

# drawing-guidelines.md rule 7: the finish field's "after joining" needs the
# joint named (r1 machinist review).
DRAWING_NOTES = f"1. JOINED TO HUB {HUB_NUMBER} AS {ROCKER_NUMBER}."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:2"

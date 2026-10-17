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
    BOTTOM_RADIUS_CALLOUT,
    STRAP_FIT_CALLOUT,
    TOP_EDGE_MATE_CALLOUT,
)
from ch_rocker_hub_fit import INTERFERENCE_TEXT
from ch_rocker_strap_spec import HUB_NUMBER

__all__ = [
    "BOTTOM_RADIUS_CALLOUT",
    "DIMENSION_CALLOUTS",
    "DRAWING_DIMENSIONS",
    "DRAWING_NOTES",
    "DRAWING_PRECISION",
    "DRAWING_PRECISION_BY_NAME",
    "HOLE_CALLOUT",
    "ISOMETRIC_VIEW_NOTE",
    "STRAP_FIT_CALLOUT",
    "TIP_LAND_PREFIX",
    "TOP_EDGE_MATE_CALLOUT",
]

# --- Drawing contract (drawing-simplicity-policy.md `How the repository
# implements the guidelines`: the PART owns places and bands). One sketch,
# ``StrapProfile``, carries the outline and the hub hole, and every printed
# location runs from the hub hole's centre (rule 10: from a real feature):
# the top edge's height over it (+0.50/0, the finished part's band), both tip
# lands' and both taper feet's offsets, the two radii and the tip land. The
# thickness is the ``Strap`` extrude's depth, on the end view.
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "StrapProfile": {
        "HoleDia",
        "TopAbovePivot",
        "TopRadius",
        "BottomRadius",
        "TailTipX",
        "RodTipX",
        "BottomTailX",
        "BottomRodX",
        "RodTipLen",
    },
    "Strap": {"StrapThickness"},
}
# The hole at three places with its H7 band; the thickness at three with its
# ±0.025; the top edge at two with +0.50/0; the radii at one (noncritical
# sizes: a 0.8 radius error moves the 146 mm half-chord's sagitta 0.01); the
# offsets and the land at two (the title block's ±0.51).
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    "StrapProfile": {
        "HoleDia": 3,
        "TopAbovePivot": 2,
        "TopRadius": 1,
        "BottomRadius": 1,
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

# drawing-guidelines.md rule 4: the H7 band names its mate and the fit. Below
# rows (an ABOVE-compartment line break never prints).
HOLE_CALLOUT = f"REAM THRU\nPRESS FIT ON {HUB_NUMBER} HUB\n{INTERFERENCE_TEXT}"
DIMENSION_CALLOUTS: dict[str, str] = {
    "HoleDia": HOLE_CALLOUT,
    "TopAbovePivot": TOP_EDGE_MATE_CALLOUT,
    "BottomRadius": BOTTOM_RADIUS_CALLOUT,
    "StrapThickness": STRAP_FIT_CALLOUT,
}

# drawing-guidelines.md rule 7: one line a machinist cannot read off the
# views. The lands' angle is the arc half-angle, radial to a centre ~808 mm
# off the sheet.
DRAWING_NOTES = "1. ARC CENTRE DIRECTLY ABOVE THE HUB HOLE; TIP LANDS RADIAL TO IT."
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:4"

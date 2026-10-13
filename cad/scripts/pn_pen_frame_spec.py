r"""Pure-data dimensional contract shared by the pen stirrup frame build,
drawing and the carriage layout (``pn_pen_carriage_geom``).

PURE DATA, no SolidWorks/COM imports.  The stirrup is a plain rectangular brass
ring that hangs over the v-block's paper end (engineerguy 4/4, 9:15-10:34,
``balance_options.png`` panel C): its top rail rests on the block top, the
marker barrel passes through the window under the block, and the #4-40 thumb
screw threaded up through the bottom rail presses the barrel into the V-groove.

Part frame: ring in the XY plane, origin at the bottom-left outer corner of the
sketch (Front-plane) face, width along +X, height along +Y, depth along +Z; the
window centred in X.  The ring is symmetric about its X centre so it cannot be
mounted mirrored.  The tapped hole's axis is the named axis ``SetScrewAxis``
(x = OUTER_WIDTH / 2, z = FRAME_DEPTH / 2, along Y).

Every printed size is a native associative dimension (``DRAWING_DIMENSIONS``)
or the Hole Wizard callout; no note carries geometry.
"""

from __future__ import annotations

from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _printed_tolerance import printed_band_mm

# The window passes the 18-deep v-block with 1.0 a side.
OUTER_WIDTH = 28.0  # X (across the block depth)
RAIL_SIDE = 4.0  # side rails (local X)
# End rails (local Y). 6 gives the #4-40 thumb screw drawing-guidelines.md
# rule 18 (>= 1.5 D full thread) engagement: 6 - the tap's incomplete lead
# (~1 pitch-and-a-half) still leaves more than 1.5 x 2.845 = 4.27.
RAIL_END = 6.0
# Y: window height = block height + the marker barrel standing proud of the
# V-groove + the thumb screw's working throw (pn_pen_carriage_geom asserts it).
OUTER_HEIGHT = 40.0
FRAME_DEPTH = 8.0  # Z (along the block length)
WINDOW_WIDTH = OUTER_WIDTH - 2.0 * RAIL_SIDE
WINDOW_HEIGHT = OUTER_HEIGHT - 2.0 * RAIL_END

# The thumb screw threads INTO the bottom rail, so its hole is an exact #4-40
# tapped Hole Wizard feature drilled up from the bottom face. THROUGH_NEXT
# (not through-all) stops at the window cavity so the top rail is spared.
SET_SCREW_TAP_SPEC = HoleSpec("tapped", "#4-40", end="through_next")
SET_SCREW_TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size]
SET_SCREW_RADIAL_WALL = (
    min(OUTER_WIDTH, FRAME_DEPTH) / 2.0 - THREAD_MAJOR_MM[SET_SCREW_TAP_SPEC.size] / 2.0
)
if SET_SCREW_RADIAL_WALL < 1.5:  # drawing-guidelines.md rule 17 (walls and webs) floor
    raise AssertionError("#4-40 thumb-screw tap leaves the pen-frame rail too thin")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Front view: the outer envelope and the two rail widths (the
# window corner from the origin corner) fully define the ring.  Bottom view:
# the extrude depth and the tapped hole's two coordinates, each from a real
# outer face (drawing-guidelines.md rule 10), beside the hole's wizard
# callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {"OuterSpanX", "OuterHeightDim", "InnerAnchorX", "InnerAnchorY"},
    "Ring": {"Depth"},
    "ScrewHole": {"ScrewX", "ScrewZ"},
}

# Printed places (drawing-guidelines.md rule 3).  Every size prints .XX: at .X
# (+/-0.8) the window's worst case, 27.2 - 2 x 4.8 = 17.6, would not pass the
# 18-deep block; at .XX it is WINDOW_WIDTH_PRINTED_MIN below.
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 2 for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}
_BAND = printed_band_mm(2)
WINDOW_WIDTH_PRINTED_MIN = (OUTER_WIDTH - _BAND) - 2.0 * (RAIL_SIDE + _BAND)
# The thumb-screw thread's wall to the nearer face along Z at the printed worst
# case: the hole station and the depth both at their band limits.
SET_SCREW_PRINTED_WALL_MIN = (
    min(
        FRAME_DEPTH / 2.0 - _BAND,
        (FRAME_DEPTH - _BAND) - (FRAME_DEPTH / 2.0 + _BAND),
    )
    - THREAD_MAJOR_MM[SET_SCREW_TAP_SPEC.size] / 2.0
)
if SET_SCREW_PRINTED_WALL_MIN < 1.5:  # drawing-guidelines.md rule 17 floor
    raise AssertionError("printed bands let the #4-40 tap break the 1.5 wall floor")

DRAWING_NOTES = ""
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
BOTTOM_VIEW_NOTE = "BOTTOM VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 1:1"

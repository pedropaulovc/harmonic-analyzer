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
mounted mirrored.  The window's four internal corners carry WINDOW_CORNER_R.
The tapped hole's axis is the named axis ``SetScrewAxis``
(x = OUTER_WIDTH / 2, z = FRAME_DEPTH / 2, along Y).

Every printed size is a native associative dimension (``DRAWING_DIMENSIONS``)
or the Hole Wizard callout; no note carries geometry.

Issue #290: the sheet prints decimal inch (``drawing_unit: in``). Lengths stay
physical millimetres, each the exact decimal of the inch value it prints.
"""

from __future__ import annotations

import _config
from _hole_spec import HoleSpec, TAP_DRILL_MM, THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _package_units import drawing_unit
from _printed_tolerance import printed_band_mm

# The registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/pn-pen-frame", _config.parts("pn-pen-frame"))

# The window passes the v-block's .70-deep neck with .016 a side (the frame
# spec stays free of the block's spec; test_pn_pen_frame_drawing pins the copy).
V_BLOCK_DEPTH = 17.78  # .70
OUTER_WIDTH = 27.94  # 1.10, X (across the block depth)
RAIL_SIDE = 4.064  # .16, side rails (local X)
# End rails (local Y). .24 gives the #4-40 thumb screw drawing-guidelines.md
# rule 18 (>= 1.5 D full thread) engagement: .24 less the tap's incomplete
# lead (1.5 pitches) still leaves more than 1.5 x .112.
RAIL_END = 6.096  # .24
# Y: window height = block height + the marker barrel standing proud of the
# V-groove + the thumb screw's working throw (pn_pen_carriage_geom asserts it).
OUTER_HEIGHT = 40.132  # 1.58
# Z (along the block length): the stirrup stands between the block's paper
# end and its body step (pn_pen_carriage_geom).
FRAME_DEPTH = 7.874  # .31
WINDOW_WIDTH = OUTER_WIDTH - 2.0 * RAIL_SIDE  # .78
WINDOW_HEIGHT = OUTER_HEIGHT - 2.0 * RAIL_END  # 1.10
# The window's internal corners (drawing-guidelines.md rule 16: no sharp
# internal corner; as large as function allows).  The window's top edge seats
# on the v-block neck's top with .016 a side (pn_pen_carriage_geom asserts the
# side gap), so a radius over that gap would ride on the neck's top edges and
# lift the stirrup; R.04, the gap itself, is that largest radius.
WINDOW_CORNER_R = 1.016  # .04
# 1e-9: the gap equals the radius, up to the float subtraction.
if WINDOW_CORNER_R > (WINDOW_WIDTH - V_BLOCK_DEPTH) / 2.0 + 1e-9:
    raise AssertionError("window corner radius rides on the v-block's top edges")

# The thumb screw threads INTO the bottom rail, so its hole is an exact #4-40
# tapped Hole Wizard feature drilled up from the bottom face. THROUGH_NEXT
# (not through-all) stops at the window cavity so the top rail is spared.
SET_SCREW_TAP_SPEC = HoleSpec("tapped", "#4-40", end="through_next")
SET_SCREW_TAP_DRILL_DIA = TAP_DRILL_MM[SET_SCREW_TAP_SPEC.size]
SET_SCREW_RADIAL_WALL = (
    min(OUTER_WIDTH, FRAME_DEPTH) / 2.0 - THREAD_MAJOR_MM[SET_SCREW_TAP_SPEC.size] / 2.0
)
if SET_SCREW_RADIAL_WALL < WALL_TARGET_MM:  # drawing-guidelines.md rule 17
    raise AssertionError("#4-40 thumb-screw tap leaves the pen-frame rail too thin")

# --- Marked-dimension contract: feature -> the parametric dimension NAMES the
# print shows.  Front view: the outer envelope, the window's size and the
# window's lower-left corner from the left and bottom outer faces (rule 10),
# which together fully define the ring sketch; the one printed window-corner
# fillet stands for all four.  Bottom view: the extrude depth and the tapped
# hole's two coordinates, each from a real outer face, beside the hole's
# wizard callout. ---
DRAWING_DIMENSIONS: dict[str, set[str]] = {
    "RingProfile": {
        "OuterSpanX",
        "OuterHeightDim",
        "WindowWidth",
        "WindowHeight",
        "LeftWall",
        "BottomWall",
    },
    "Ring": {"Depth"},
    "WindowCorner": {"WindowCornerR"},
    "ScrewHole": {"ScrewX", "ScrewZ"},
}

# Printed places (drawing-guidelines.md rule 3).  Every rail, window and
# envelope size feeds a stack below, and the corner radius is bounded by the
# neck gap, so nothing prints .X: the title block's .XX everywhere except the
# tap's depth station ScrewZ, .XXX: at .XX the #4-40 thread's wall to the
# nearer face would fall to .155 - .01 - .01 - .056 = .079, under the rule 17
# .080 target (SET_SCREW_PRINTED_WALL_MIN); FRAME_DEPTH is fixed by the
# carriage's paper solve and the v-block's body step (pn_pen_carriage_geom),
# so geometry cannot buy the wall.
_THREE_PLACE = {"ScrewZ"}
DRAWING_PRECISION: dict[str, dict[str, int]] = {
    feature: {name: 3 if name in _THREE_PLACE else 2 for name in names}
    for feature, names in DRAWING_DIMENSIONS.items()
}
DRAWING_PRECISION_BY_NAME: dict[str, int] = {
    name: places
    for dimensions in DRAWING_PRECISION.values()
    for name, places in dimensions.items()
}


def _band(name: str) -> float:
    """The title-block +/- the named dimension prints at."""
    return printed_band_mm(DRAWING_PRECISION_BY_NAME[name], unit=UNIT)


# The window passes the v-block's neck at both parts' printed worst case: the
# window at its own band, the neck's two faces at the block's .XX row.
WINDOW_WIDTH_PRINTED_MIN = WINDOW_WIDTH - _band("WindowWidth")
if WINDOW_WIDTH_PRINTED_MIN <= V_BLOCK_DEPTH + 2.0 * printed_band_mm(2, unit=UNIT):
    raise AssertionError("printed window width may not pass the v-block")
# The two unprinted rails (right, top) at the printed worst case: the outer
# size small, the window's corner station and size large (rule 17).
RIGHT_WALL_PRINTED_MIN = (
    (OUTER_WIDTH - _band("OuterSpanX"))
    - (RAIL_SIDE + _band("LeftWall"))
    - (WINDOW_WIDTH + _band("WindowWidth"))
)
TOP_WALL_PRINTED_MIN = (
    (OUTER_HEIGHT - _band("OuterHeightDim"))
    - (RAIL_END + _band("BottomWall"))
    - (WINDOW_HEIGHT + _band("WindowHeight"))
)
if min(RIGHT_WALL_PRINTED_MIN, TOP_WALL_PRINTED_MIN) < WALL_TARGET_MM:
    raise AssertionError("an unprinted pen-frame rail falls under the rule 17 target")
# Full #4-40 thread in the bottom rail at its printed minimum, less the tap's
# incomplete lead (1.5 pitches), against rule 18's 1.5 D.
_TAP_PITCH = 25.4 / int(SET_SCREW_TAP_SPEC.size.split("-")[1])
BOTTOM_RAIL_FULL_THREAD_MIN = RAIL_END - _band("BottomWall") - 1.5 * _TAP_PITCH
if BOTTOM_RAIL_FULL_THREAD_MIN < 1.5 * THREAD_MAJOR_MM[SET_SCREW_TAP_SPEC.size]:
    raise AssertionError("printed bottom rail leaves the thumb screw under 1.5D")
# The thumb-screw thread's wall to the nearer face along Z at the printed worst
# case: the hole station and the depth both at their band limits.
SET_SCREW_PRINTED_WALL_MIN = (
    min(
        FRAME_DEPTH / 2.0 - _band("ScrewZ"),
        (FRAME_DEPTH - _band("Depth")) - (FRAME_DEPTH / 2.0 + _band("ScrewZ")),
    )
    - THREAD_MAJOR_MM[SET_SCREW_TAP_SPEC.size] / 2.0
)
if SET_SCREW_PRINTED_WALL_MIN < WALL_TARGET_MM:  # drawing-guidelines.md rule 17
    raise AssertionError("printed bands let the #4-40 tap break the .080 wall target")

DRAWING_NOTES = ""
FRONT_VIEW_NOTE = "FRONT VIEW SCALE 2:1"
BOTTOM_VIEW_NOTE = "BOTTOM VIEW SCALE 2:1"
ISOMETRIC_VIEW_NOTE = "ISOMETRIC VIEW SCALE 2:1"

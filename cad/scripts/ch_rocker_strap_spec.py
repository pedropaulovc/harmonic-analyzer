r"""Rocker strap (MHA-CH-13): the flat strap of the built-up rocker arm.

PURE DATA, no SolidWorks/COM imports. MHA-CH-06 may be built up
(``ch_rocker_arm_notes.BUILT_UP_PERMISSION_NOTE``): the turned hub MHA-CH-12
is pressed into this strap's Ø.400 reamed hole (``ch_rocker_hub_fit``). The
strap's outline, faces and thickness are FINISHED here and never cut again;
only the #47 rod-pin hole is added after joining (it is located from the
joined part's reamed bore, so it is not on this detail).

Frame: the MHA-CH-06 frame, so every value below is the finished part's own
(``ch_rocker_arm_spec``): origin on the bottom arc's midpoint, +X the rod
side, the hub hole on the mirror axis PIVOT_MID_Y up, the arcs' shared centre
CENTER_Y up. Nothing here is a new number.
"""

from __future__ import annotations

import math

import _config
from _package_units import drawing_unit
from _rocker_interface import ARM_DEPTH, CENTER_Y, CURVE_RADIUS, PIVOT_MID_Y, R_BOTTOM
from ch_rocker_arm_spec import (
    ARM_THICKNESS,
    ARM_THICKNESS_BAND,
    BOT_END_X,
    HUB_DIA,
    R_TOP,
    ROD_TIP_X,
    TIP_FACE,
    TOP_EDGE_ABOVE_PIVOT,
    TOP_EDGE_BAND,
    TOP_END_X,
    TOP_END_Y,
    _ALPHA_BOT,
    _ALPHA_TOP,
)

__all__ = [
    "ARM_DEPTH",
    "ARM_THICKNESS",
    "ARM_THICKNESS_BAND",
    "BOTTOM_EDGE_BAND",
    "BOTTOM_EDGE_BELOW_PIVOT",
    "BOT_END_X",
    "BOT_END_Y",
    "CENTER_Y",
    "CURVE_RADIUS",
    "DRAWING_REFERENCE_PRECISION",
    "HOLE_DIA",
    "HUB_NUMBER",
    "NUMBER",
    "PIVOT_MID_Y",
    "R_BOTTOM",
    "R_TOP",
    "ROCKER_NUMBER",
    "ROD_TIP_X",
    "ROD_TIP_Y",
    "TIP_FACE",
    "TOP_EDGE_ABOVE_PIVOT",
    "TOP_EDGE_BAND",
    "TOP_END_X",
    "TOP_END_Y",
    "UNIT",
    "strap_area",
]

NUMBER = "MHA-CH-13"
HUB_NUMBER = "MHA-CH-12"
ROCKER_NUMBER = "MHA-CH-06"

# #290: the registry row's drawing_unit (in) is this sheet's unit.
UNIT = drawing_unit("parts/ch-rocker-strap", _config.parts("ch-rocker-strap"))

# The hub hole: the finished hub O.D.'s nominal, reamed (ch_rocker_hub_fit).
HOLE_DIA = HUB_DIA

# The bottom edge's depth under the hole, on the mirror axis -- the
# finished part's lower profile (draw_ch_rocker_arm: zone TOP_EDGE_BAND[0],
# wholly in material, U0) said as a +/- from the hole the hub fills. It may
# only come out shallow, the top edge only high: the arcs' radial width is
# held from the hole, not stacked from two radii (r1 machinist review: two
# one-place radii left a .031 worst-case wall under the hole).
BOTTOM_EDGE_BELOW_PIVOT = PIVOT_MID_Y
BOTTOM_EDGE_BAND = (TOP_EDGE_BAND[1], -TOP_EDGE_BAND[0])  # (upper, lower)

# The sheet's one pure reference dimension: the parenthesised overall length
# across both tip corners, a band-free restatement of the two 5.76 offsets.
# One place, a noncritical overall size (drawing-guidelines.md).
DRAWING_REFERENCE_PRECISION: dict[str, int] = {"OverallLength": 1}

# The two vertices the spec does not export, from the same construction as
# build_ch_rocker_arm: each arc's end on its circle, and the tip land's outer
# end TIP_FACE out along the top arc's radius.
BOT_END_Y = CENTER_Y - R_BOTTOM * math.cos(_ALPHA_BOT)
_RAD_Y = (TOP_END_Y - CENTER_Y) / R_TOP
ROD_TIP_Y = TOP_END_Y + TIP_FACE * _RAD_Y


def strap_area() -> float:
    """The outline's area by shoelace over a densely sampled boundary
    (build_ch_rocker_arm._strap_area's construction), without the hole."""
    n = 200
    pts: list[tuple[float, float]] = []
    for i in range(n + 1):  # bottom arc, rod (+alpha) -> tail (-alpha)
        a = _ALPHA_BOT - 2.0 * _ALPHA_BOT * i / n
        pts.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    pts.append((-ROD_TIP_X, ROD_TIP_Y))  # tail end face: tail_b -> tail_tip
    for i in range(n + 1):  # top arc, tail (-alpha) -> rod (+alpha)
        a = -_ALPHA_TOP + 2.0 * _ALPHA_TOP * i / n
        pts.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
    pts.append((ROD_TIP_X, ROD_TIP_Y))  # rod tip face: rod_t -> rod_tip
    area = 0.0
    for i, (x1, y1) in enumerate(pts):
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0

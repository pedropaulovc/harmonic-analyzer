r"""Create the simplicity-policy machinist drawing for the cone tip block."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_leader_note,
    add_native_hole_callout,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hole_callout_precision,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_BORE_DIA,
    ADJUSTER_CSK,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_LEN,
    FLANGE_SLOT_CTOC,
    FLANGE_SLOT_Z,
    FLANGE_T,
    HEEL_RELIEF_HEIGHT,
    PINCH_BORE_DIA,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    SLIT_DEPTH,
    SLIT_W,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["cone_tip_block"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# I31: the foot flange runs the block 20.8 further south, 32.8 long in all;
# at 2:1 the plan and the side views no longer fit between the front view's
# dimensions and the sheet edge, so the sheet drops to 3:2.
SHEET_SCALE = (3.0, 2.0)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
FRONT_CENTER = (0.072, 0.129)
TOP_CENTER = (FRONT_CENTER[0], 0.222)
# Main eye-pass of the I31 render (7ab69742b): at x 0.166 the adjuster
# callout's longest line (54.5 mm, shoulder 57.1) ran over the right view's
# north face -- the gap between the front and right views was 58.2 mm.  The
# right view slides 5 mm along its projection row (ASME alignment is the
# shared y), and the removed views B and C slide with it so the gaps to
# their right keep their measured air.
RIGHT_CENTER = (0.171, FRONT_CENTER[1])
LEFT_CENTER = (0.243, FRONT_CENTER[1])
BACK_CENTER = (0.315, FRONT_CENTER[1])
SECTION_CENTER = (0.190, 0.225)
ISO_CENTER = (0.350, 0.215)
# A view centres on the part's box.  Along the cone axis that box runs from
# the north face to the flange's south end, so the block's own centre (the
# model origin) sits Z_MID north of each view's centre.
Z_NORTH = BLOCK_Z / 2.0
Z_SOUTH = -BLOCK_Z / 2.0 - FLANGE_LEN
Z_MID = (Z_NORTH + Z_SOUTH) / 2.0
FLANGE_SLOT_CENTER_Z = -BLOCK_Z / 2.0 - FLANGE_SLOT_Z


def _elevation_y(model_y: float, center: tuple[float, float]) -> float:
    return center[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


def _plan_y(model_z: float) -> float:
    """Sheet y of a model station in the plan (*Top shows +Z, north, down)."""
    return TOP_CENTER[1] - (model_z - Z_MID) * _S


def _right_x(model_z: float) -> float:
    """Sheet x of a model station in the right view (north on the left)."""
    return RIGHT_CENTER[0] - (model_z - Z_MID) * _S


# Imported value text measured on run 5637ac42: a four-character value
# ("1.20", "7.50") prints ~9.1 mm wide, a three-character one ("6.0", "7.5")
# ~6.4 mm, and a native arrowhead ~3.4 mm long.  Main's eye-pass of that run
# found values printed across their own witness lines and a hole centreline
# (d976281d ruling: no text on a line), so the values below are placed from
# these sizes rather than centred on a feature.
VALUE_TEXT_HALF_WIDTH = 0.0046
VALUE_TEXT_HALF_HEIGHT = 0.0019
ARROW_LENGTH = 0.0034
TEXT_CLEARANCE = 0.0015
# The 1.2 slot prints 1.8 mm wide, narrower than its value, so the arrows
# stand outside the slot walls and the text sits left of the left arrow's
# tail on the extended dimension line.  Left, because on the adjuster
# elevation PassageCenter's 7.50 span occupies the slot's right.
SLIT_TEXT_OFFSET = (
    SLIT_W * _S / 2.0 + ARROW_LENGTH + TEXT_CLEARANCE + VALUE_TEXT_HALF_WIDTH
)
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _elevation_y(0.0, FRONT_CENTER) - 0.012),
    "BlockHt": (FRONT_CENTER[0] - 0.033, FRONT_CENTER[1]),
    "SlitW": (
        FRONT_CENTER[0] - SLIT_TEXT_OFFSET,
        _elevation_y(BLOCK_HEIGHT, FRONT_CENTER) + 0.012,
    ),
}
# PassageCenter stands above SlitW on the adjuster elevation; the plan's
# north edge is the ceiling for both.
PASSAGE_CENTER_RISE = 0.024
# swDimArrowsOutside: set, not left to the document's smart arrows.
ARROWS_OUTSIDE = ("SlitW", "HeelReliefDepth", "FlangeSlotW")
_DIM_ARROWS_OUTSIDE = 1
# The plan.  Left of it: the block depth and the flange length, chained on
# one line, and the slot's arc-centre spacing between that line and the
# part.  Right of it: the slot's station from the body's south face, and the
# slot width's value (arrows outside) level with the slot's south half, past
# the end of that station's span.  Above the flange's south end, higher than
# the A-A cutting-plane arrow and its letter at that end: the slot's location
# from the +X face.
_PLAN_LEFT = TOP_CENTER[0] - BLOCK_X * _S / 2.0
_PLAN_RIGHT = TOP_CENTER[0] + BLOCK_X * _S / 2.0
# Both chain values sit on this line and the spacing's value midway to the
# part, so each moves half as far as the line: at -0.030 the I31 render
# printed "20.8" 0.7 mm from "8.42", which read as "20.88.42".  At -0.036
# the two values keep 3.8 mm of air.
PLAN_CHAIN_X = TOP_CENTER[0] - 0.036
FLANGE_SLOT_W_Z = FLANGE_SLOT_CENTER_Z - FLANGE_SLOT_CTOC * 0.4
FLANGE_SLOT_X_RISE = 0.016
TOP_KEEP = {
    "Depth": (PLAN_CHAIN_X, _plan_y(0.0)),
    "FlangeLen": (PLAN_CHAIN_X, _plan_y((-BLOCK_Z / 2.0 + Z_SOUTH) / 2.0)),
    "FlangeSlotCtoC": (
        (PLAN_CHAIN_X + _PLAN_LEFT) / 2.0,
        _plan_y(FLANGE_SLOT_CENTER_Z),
    ),
    "FlangeSlotZ": (
        TOP_CENTER[0] + 0.022,
        _plan_y(-BLOCK_Z / 2.0 - FLANGE_SLOT_Z / 2.0),
    ),
    "FlangeSlotW": (
        _PLAN_RIGHT + ARROW_LENGTH + TEXT_CLEARANCE + VALUE_TEXT_HALF_WIDTH,
        _plan_y(FLANGE_SLOT_W_Z),
    ),
    "FlangeSlotX": (
        TOP_CENTER[0] + BLOCK_X * _S / 4.0,
        _plan_y(Z_SOUTH) + FLANGE_SLOT_X_RISE,
    ),
}
# The part-hidden reference sketch section A dimensions (PinchRise).
SECTION_SKETCHES = ("PinchRiseReference",)
SECTION_KEEP = {
    "PinchRise": (
        SECTION_CENTER[0] + 0.060,
        _elevation_y(
            (ADJUSTER_AXIS_HEIGHT + PINCH_HEIGHT) / 2.0,
            SECTION_CENTER,
        ),
    )
}
# The half-block station below runs from the north face to the pinch-hole
# centre, so its value sits midway along its span.  Centred on the hole (run
# 5637ac42), the witness and centreline ended in the decimal point; at +0.003
# its dimension line printed on the block's top edge.
#
# I31 heel relief: the right view has north on the left, so the step is its
# lower-left notch.  The depth's dimension line runs through the notch's air
# half way up (at 3:2 the notch is only 8.3 mm tall), arrows outside, its value left of the north face;
# the height stands further left, so the depth's value sits between the
# height's two extension lines.  The flange thickness stands past the
# flange's south end, on the right.
_RIGHT_NORTH_X = _right_x(Z_NORTH)
HEEL_DEPTH_TEXT_X = _RIGHT_NORTH_X - ARROW_LENGTH - TEXT_CLEARANCE - VALUE_TEXT_HALF_WIDTH
HEEL_HEIGHT_LINE_X = HEEL_DEPTH_TEXT_X - VALUE_TEXT_HALF_WIDTH - 0.008
RIGHT_KEEP = {
    "PinchDepthCenter": (
        _right_x(BLOCK_Z / 4.0),
        _elevation_y(BLOCK_HEIGHT, RIGHT_CENTER) + 0.007,
    ),
    "HeelReliefDepth": (
        HEEL_DEPTH_TEXT_X,
        _elevation_y(HEEL_RELIEF_HEIGHT / 2.0, RIGHT_CENTER),
    ),
    "HeelReliefHt": (
        HEEL_HEIGHT_LINE_X,
        _elevation_y(HEEL_RELIEF_HEIGHT / 2.0, RIGHT_CENTER),
    ),
    "FlangeT": (
        _right_x(Z_SOUTH) + 0.010,
        _elevation_y(FLANGE_T / 2.0, RIGHT_CENTER),
    ),
}
LEFT_KEEP: dict[str, tuple[float, float]] = {}
# The bottom-row captions sit just under the views' feet.
CAPTION_Y = _elevation_y(0.0, FRONT_CENTER) - 0.004
# A centreline runs a short way past the part it marks.
AXIS_OVERRUN = 0.002
# Review C1: the left and rear views sit right of the right view, out of
# third-angle order, so each is a removed view named by a letter arrow on the
# view that shows the face it looks at.  VIEW B looks at the -X (pinch-thread)
# face: the arrow meets the front view's left edge between the 32.27 and
# 46.83 extension lines.  VIEW C looks at the -Z (shaft-entry) face, from
# the plan's upper (south) end, left of the A-A cutting-plane stem.  Each pair
# is (note upper-left, leader tip), sheet metres.
# The letters match the A-A cutting-plane letters (~5 mm, run 6cab17f6), and
# each note sits square to its face so the leader reads as a viewing arrow:
# B level with its tip, C centred above its tip.
VIEW_LETTER_HEIGHT = 0.005
_VIEW_B_TIP_Y = _elevation_y((ADJUSTER_AXIS_HEIGHT + BLOCK_HEIGHT) / 2.0, FRONT_CENTER)
VIEW_B_ARROW = (
    (
        FRONT_CENTER[0] - BLOCK_X * _S / 2.0 - 0.013,
        _VIEW_B_TIP_Y + VIEW_LETTER_HEIGHT / 2.0,
    ),
    (FRONT_CENTER[0] - BLOCK_X * _S / 2.0, _VIEW_B_TIP_Y),
)
VIEW_C_ARROW = (
    (TOP_CENTER[0] - 0.006 - 0.0018, _plan_y(Z_SOUTH) + 0.013),
    (TOP_CENTER[0] - 0.006, _plan_y(Z_SOUTH)),
)
DIMENSION_CALLOUTS = {
    "SlitDepth": "SLOT DEPTH",
}

# The adjuster's hole callout stands between the adjuster elevation and the
# right view, named by the ADJUSTER ENTRY note above it.  At y 0.115 (I31
# render) its shoulder sat at 106.6 mm, where the 5.56 heel height's outside
# arrow runs up to 108.5 mm: the callout rises 6 mm, still 7 mm under the
# SLOT DEPTH witness line at 141.3 mm.
ADJUSTER_CALLOUT_DX = 0.043
ADJUSTER_CALLOUT_Y = 0.121
ADJUSTER_ENTRY_RISE = 0.0135
# Fable review af561fa7 put the pinch clearance callout under the 6.0
# dimension, right of the SLOT DEPTH line; at y 0.1735 its text printed
# over the 6.0 (I31 render).  4.5 mm higher its shoulder clears the 6.0's
# printed value by 2.3 mm; the leader still drops to the hole just right of
# that value, as before.
PINCH_CLEARANCE_CALLOUT_XY = (RIGHT_CENTER[0] - 0.033, 0.178)
PINCH_THREAD_CALLOUT_XY = (LEFT_CENTER[0] + 0.016, 0.190)
ROTATED_NOTE_XY = (SECTION_CENTER[0] - 0.015, 0.195)


def _adjuster_axis_keep(
    adjuster_center: tuple[float, float],
) -> dict[str, tuple[float, float]]:
    """The adjuster-axis values, kept on whichever elevation shows its entry."""
    plus_x_side = 1.0 if adjuster_center == FRONT_CENTER else -1.0
    return {
        "AxisHeight": (
            adjuster_center[0] - 0.045,
            _elevation_y(ADJUSTER_AXIS_HEIGHT / 2.0, adjuster_center),
        ),
        "PassageCenter": (
            adjuster_center[0] + plus_x_side * BLOCK_X * _S / 4.0,
            _elevation_y(BLOCK_HEIGHT, adjuster_center) + PASSAGE_CENTER_RISE,
        ),
        "SlitDepth": (
            adjuster_center[0] + 0.043,
            _elevation_y(BLOCK_HEIGHT - SLIT_DEPTH / 2.0, adjuster_center),
        ),
    }


def _adjuster_callout_xy(adjuster_center: tuple[float, float]) -> tuple[float, float]:
    return (adjuster_center[0] + ADJUSTER_CALLOUT_DX, ADJUSTER_CALLOUT_Y)


def _sheet_notes(
    adjuster_center: tuple[float, float],
) -> tuple[tuple[str, float, float], ...]:
    """Every free note this sheet adds: (text, upper-left x, upper-left y)."""
    # The through thread shows the same rim from both ends; VIEW C (the
    # opposite elevation) is the shaft's entry.
    shaft_entry_center = BACK_CENTER if adjuster_center == FRONT_CENTER else FRONT_CENTER
    return (
        ("VIEW C\nSHAFT ENTRY", shaft_entry_center[0] - 0.021, CAPTION_Y),
        ("RIGHT VIEW\nPINCH CLEARANCE ENTRY", RIGHT_CENTER[0] - 0.026, CAPTION_Y),
        ("VIEW B\nPINCH THREAD ENTRY", LEFT_CENTER[0] - 0.023, CAPTION_Y),
        # Review: named above the thread callout it describes.
        (
            "ADJUSTER ENTRY",
            adjuster_center[0] + 0.023,
            ADJUSTER_CALLOUT_Y + ADJUSTER_ENTRY_RISE,
        ),
        ("ROTATED 90°", *ROTATED_NOTE_XY),
    )


# ---------------------------------------------------------------------------
# Sheet ink audit
#
# Main's eye-pass of the I31 farm render (7ab69742b) found three collisions no
# gate saw: "20.8" run into "8.42" on the plan (value text on value text), the
# pinch clearance callout printed over the right view's "6.0" (callout text on
# value text), and the adjuster callout's THRU ALL / BOTH ENDS printed over the
# right view's north face (callout text on a view's model outline), its
# shoulder also crossed by the 5.56 heel height's outside arrow (callout text
# on a dimension line).  The shared audit cannot see any of those classes:
# _drawing_common._dim_element boxes every display dimension and hole callout
# as a nominal 8 mm square with CollisionScope.NONE, _drawing_layout_check.
# _may_collide drops every pair holding a NONE element, and since ab28f4e49
# finalize_drawing no longer runs check_drawing_layout at all.
#
# So the sheet audits its own ink before it opens a document: every text
# block it places, boxed from where it places it and how large that text
# printed, against every other text block, every view's model silhouette, and
# the outside-arrow dimension lines that stand in the gaps between the views.
#
# Extents are (left, down, right, up) of the printed ink from the point the
# module commands, in sheet metres, measured on the I31 render's 300 dpi PNG
# (11.81 px/mm) by connected-component ink boxes and rounded outward to
# 0.1 mm.  A single value uses the module's value-text half sizes (4.6 x 1.9
# mm, over the 4.3 x 1.7 mm a four-character value measured).
_VALUE_EXTENT = (
    VALUE_TEXT_HALF_WIDTH,
    VALUE_TEXT_HALF_HEIGHT,
    VALUE_TEXT_HALF_WIDTH,
    VALUE_TEXT_HALF_HEIGHT,
)
_VALUE_EXTENTS = {
    # "3.97" with its stacked +0.1 / 0.0 deviations to the right.
    "FlangeSlotW": (0.0069, 0.0036, 0.0097, 0.0045),
    # "15.2" over its SLOT DEPTH callout line.
    "SlitDepth": (0.0129, 0.0046, 0.0124, 0.0045),
}
# Hole callouts: every line plus the shoulder the leader leaves from.
ADJUSTER_CALLOUT_EXTENT = (0.0295, 0.0086, 0.0278, 0.0078)
PINCH_CLEARANCE_CALLOUT_EXTENT = (0.0150, 0.0030, 0.0166, 0.0023)
PINCH_THREAD_CALLOUT_EXTENT = (0.0322, 0.0085, 0.0310, 0.0078)
# Free notes are placed by their upper-left corner.
_NOTE_EXTENTS = {
    "ADJUSTER ENTRY": (0.0, 0.0036, 0.0365, 0.0),
    "ROTATED 90°": (0.0, 0.0036, 0.0200, 0.0),
    "RIGHT VIEW\nPINCH CLEARANCE ENTRY": (0.0, 0.0081, 0.0581, 0.0),
    "VIEW B\nPINCH THREAD ENTRY": (0.0, 0.0081, 0.0476, 0.0),
    "VIEW C\nSHAFT ENTRY": (0.0, 0.0081, 0.0278, 0.0),
}
# SolidWorks places section A-A's "SECTION A-A / SCALE 3:2" label under the
# view; its ink relative to SECTION_CENTER.
SECTION_LABEL_BOX = (-0.0227, -0.0537, 0.0227, -0.0392)
# An outside arrow's dimension line runs this far past its extension line
# (arrowhead plus tail): 6.35 mm on the 5.56, 6.2-6.3 mm on the 6.0.
OUTSIDE_ARROW_RUN = 0.0064
# The 6.0's dimension line printed 2.8 mm under its value's centre.
PINCH_DEPTH_LINE_DROP = 0.0028
# A text block may not come nearer a view's model outline than this.
OUTLINE_CLEARANCE = 0.0005

Box = tuple[float, float, float, float]
Segment = tuple[tuple[float, float], tuple[float, float]]


def _extent_box(
    point: tuple[float, float], extent: tuple[float, float, float, float]
) -> Box:
    left, down, right, up = extent
    return (point[0] - left, point[1] - down, point[0] + right, point[1] + up)


def sheet_text_boxes(adjuster_center: tuple[float, float] = FRONT_CENTER) -> dict[str, Box]:
    """Every text block this module places, keyed by dimension or note name."""
    keeps = {
        **FRONT_KEEP,
        **_adjuster_axis_keep(adjuster_center),
        **TOP_KEEP,
        **SECTION_KEEP,
        **RIGHT_KEEP,
        **LEFT_KEEP,
    }
    boxes = {
        name: _extent_box(point, _VALUE_EXTENTS.get(name, _VALUE_EXTENT))
        for name, point in keeps.items()
    }
    boxes["adjuster callout"] = _extent_box(
        _adjuster_callout_xy(adjuster_center), ADJUSTER_CALLOUT_EXTENT
    )
    boxes["pinch clearance callout"] = _extent_box(
        PINCH_CLEARANCE_CALLOUT_XY, PINCH_CLEARANCE_CALLOUT_EXTENT
    )
    boxes["pinch thread callout"] = _extent_box(
        PINCH_THREAD_CALLOUT_XY, PINCH_THREAD_CALLOUT_EXTENT
    )
    for text, x, y in _sheet_notes(adjuster_center):
        boxes[text.split("\n")[0]] = _extent_box((x, y), _NOTE_EXTENTS[text])
    x0, y0, x1, y1 = SECTION_LABEL_BOX
    boxes["SECTION A-A label"] = (
        SECTION_CENTER[0] + x0,
        SECTION_CENTER[1] + y0,
        SECTION_CENTER[0] + x1,
        SECTION_CENTER[1] + y1,
    )
    return boxes


def sheet_view_silhouettes() -> dict[str, Box]:
    """Each view's model outline as rectangles (an L view is two)."""
    foot = _elevation_y(0.0, FRONT_CENTER)
    top = _elevation_y(BLOCK_HEIGHT, FRONT_CENTER)
    flange_top = _elevation_y(FLANGE_T, FRONT_CENTER)
    half_x = BLOCK_X * _S / 2.0
    boxes = {
        "front": (FRONT_CENTER[0] - half_x, foot, FRONT_CENTER[0] + half_x, top),
        "back": (BACK_CENTER[0] - half_x, foot, BACK_CENTER[0] + half_x, top),
        "plan": (
            TOP_CENTER[0] - half_x,
            _plan_y(Z_NORTH),
            TOP_CENTER[0] + half_x,
            _plan_y(Z_SOUTH),
        ),
        # Rotated 90 degrees: the block height runs across the sheet.
        "section A-A": (
            SECTION_CENTER[0] - BLOCK_HEIGHT * _S / 2.0,
            SECTION_CENTER[1] - (Z_NORTH - Z_SOUTH) * _S / 2.0,
            SECTION_CENTER[0] + BLOCK_HEIGHT * _S / 2.0,
            SECTION_CENTER[1] + (Z_NORTH - Z_SOUTH) * _S / 2.0,
        ),
    }
    # The right view has north on the left, VIEW B north on the right.
    for label, center, sign in (("right", RIGHT_CENTER, -1.0), ("view B", LEFT_CENTER, 1.0)):
        north, south_face, south_end = (
            center[0] + sign * (z - Z_MID) * _S
            for z in (Z_NORTH, -BLOCK_Z / 2.0, Z_SOUTH)
        )
        boxes[f"{label} body"] = (min(north, south_face), foot, max(north, south_face), top)
        boxes[f"{label} flange"] = (
            min(south_face, south_end),
            foot,
            max(south_face, south_end),
            flange_top,
        )
    return boxes


def sheet_dimension_lines() -> dict[str, Segment]:
    """The outside-arrow dimension lines that stand in the gaps between views."""
    heel_x = RIGHT_KEEP["HeelReliefHt"][0]
    depth_y = RIGHT_KEEP["PinchDepthCenter"][1] - PINCH_DEPTH_LINE_DROP
    return {
        "HeelReliefHt": (
            (heel_x, _elevation_y(0.0, RIGHT_CENTER) - OUTSIDE_ARROW_RUN),
            (heel_x, _elevation_y(HEEL_RELIEF_HEIGHT, RIGHT_CENTER) + OUTSIDE_ARROW_RUN),
        ),
        "PinchDepthCenter": (
            (_right_x(Z_NORTH) - OUTSIDE_ARROW_RUN, depth_y),
            (_right_x(0.0) + OUTSIDE_ARROW_RUN, depth_y),
        ),
    }


def _box_gap(a: Box, b: Box) -> float:
    """Air between two boxes along their clearer axis; negative when they overlap."""
    return max(b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def _segment_meets_box(segment: Segment, box: Box) -> bool:
    """Liang-Barsky: whether any part of ``segment`` lies inside ``box``."""
    (x0, y0), (x1, y1) = segment
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def sheet_ink_collisions(
    texts: dict[str, Box],
    silhouettes: dict[str, Box],
    lines: dict[str, Segment],
    *,
    text_clearance: float = TEXT_CLEARANCE,
    outline_clearance: float = OUTLINE_CLEARANCE,
) -> list[str]:
    """Every text block too near another, a view's outline, or a foreign line."""
    findings: list[str] = []
    names = sorted(texts)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            gap = _box_gap(texts[first], texts[second])
            if gap < text_clearance:
                findings.append(
                    f"text-on-text: {first!r} and {second!r} stand "
                    f"{gap * 1000.0:.2f} mm apart"
                )
    for name in names:
        for view, outline in sorted(silhouettes.items()):
            gap = _box_gap(texts[name], outline)
            if gap < outline_clearance:
                findings.append(
                    f"text-on-outline: {name!r} stands {gap * 1000.0:.2f} mm "
                    f"from the {view} outline"
                )
        for owner, segment in sorted(lines.items()):
            if owner != name and _segment_meets_box(segment, texts[name]):
                findings.append(f"text-on-line: {owner}'s dimension line crosses {name!r}")
    return findings


def assert_sheet_ink_clear(adjuster_center: tuple[float, float] = FRONT_CENTER) -> None:
    """Refuse a placement whose own text collides before any COM work is spent."""
    findings = sheet_ink_collisions(
        sheet_text_boxes(adjuster_center),
        sheet_view_silhouettes(),
        sheet_dimension_lines(),
    )
    if findings:
        raise RuntimeError(
            "cone-tip-block sheet ink collides:\n"
            + "\n".join(f"  - {finding}" for finding in findings)
        )
    _telemetry.debug("cone-tip-block sheet ink clear")


def _foot_edge(adapter: Any, view: Any, *, min_span_mm: float = 13.9) -> Any:
    """Return the longest real edge on the block's locating foot plane."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="tip-block foot edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        span = max(abs(p1[0] - p0[0]), abs(p1[2] - p0[2]))
        candidates.append((span, edge))
    if not candidates:
        raise RuntimeError("front view has no real edge on the locating foot plane")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < min_span_mm:
        raise RuntimeError(f"locating-foot edge span is only {span:.3f} mm")
    return edge


def _set_arrows_outside(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Stand each named dimension's arrows outside its extension lines."""
    remaining = set(names)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_OUTSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_OUTSIDE:
            raise RuntimeError(f"{name} did not keep its arrows outside")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"no dimension to set arrows outside: {sorted(remaining)}")


def _add_adjuster_axis(adapter: Any, section: Any) -> None:
    """Sketch the adjuster bore's axis across section A-A, owned by the view.

    The 8.85 pinch rise is measured from this axis to the pinch-bore centre;
    without the centreline its extension line reads as rising from nothing
    (review 2026-09-23).  The cutting plane is X = 0, so the adjuster axis
    (along Z) lies in it and projects as a line, while the pinch axis (along
    X) projects to a point -- run 71f5acc5 sketched that zero-length line and
    CreateCenterLine returned None.  Run 6cab17f6 then sketched it with sheet
    coordinates while the section was the active view, so it landed in the
    view's own sketch frame, off the sheet.  This is draw_top_frame's proven
    owned-centreline recipe: activate the view, map each sheet point through
    the view sketch's ModelToSketchTransform, and colour the segment black
    (a sketch line otherwise prints in the under-defined blue).
    """
    half = BLOCK_Z / 2000.0 + AXIS_OVERRUN * SHEET_SCALE[1] / SHEET_SCALE[0]
    ends = [
        model_point_in_view(
            adapter,
            section,
            (0.0, ADJUSTER_AXIS_HEIGHT / 1000.0, z),
            label=f"adjuster axis end {index}",
        )
        for index, z in enumerate((-half, half))
    ]
    length = math.dist(ends[0][:2], ends[1][:2])
    expected = 2.0 * half * SHEET_SCALE[0] / SHEET_SCALE[1]
    if abs(length - expected) > 0.0005:
        raise RuntimeError(
            f"adjuster axis projects {length:.4f} m long in section A-A, "
            f"expected {expected:.4f}"
        )
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for the adjuster axis")
    draw.ClearSelection2(True)
    sketch = _early_bound(section.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in ends:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        points.append(
            tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData)
        )
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    centerline = manager.CreateCenterLine(*points[0], *points[1])
    if centerline is None:
        raise RuntimeError("failed to sketch the adjuster axis in section A-A")
    segment = _early_bound(centerline, "ISketchSegment")
    segment.Color = 0
    if int(segment.Color) != 0:
        raise RuntimeError("adjuster axis colour did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section A-A adjuster axis")


def _circle_entity(
    adapter: Any,
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> Any:
    """Resolve a real circular edge by model size and vertical station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} circles"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        candidates.append((params[6], params[1], edge))
    if not candidates:
        raise RuntimeError(f"{label} view has no visible circular model edges")
    radius, center_y, edge = min(
        candidates,
        key=lambda item: abs(item[0] - radius_mm) + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no {label} circle matches radius {radius_mm:.3f} mm at "
            f"height {center_y_mm:.3f} mm; nearest is "
            f"R{radius:.3f} at {center_y:.3f} mm"
        )
    return edge

def _preferred_entry_circle(
    adapter: Any,
    candidates: tuple[
        tuple[Any, tuple[float, float]],
        tuple[Any, tuple[float, float]],
    ],
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> tuple[Any, tuple[float, float], Any]:
    """Use the first opposed view that exposes the requested real model edge."""
    matches: list[tuple[Any, tuple[float, float], Any]] = []
    for view, center in candidates:
        try:
            edge = _circle_entity(
                adapter,
                view,
                radius_mm=radius_mm,
                center_y_mm=center_y_mm,
                label=label,
            )
        except RuntimeError:
            continue
        matches.append((view, center, edge))
    if not matches:
        raise RuntimeError(f"{label} is absent from both opposed views")
    # The through thread exposes the same tap-drill rim from both sides.
    # Both selections still belong to the same native Hole Wizard feature; the
    # caller's candidate order supplies a stable sheet-side preference.
    return matches[0]

# Hole-callout order: drill line, thread line, then the prose (Main eye-pass
# af561fa7); the caption already names the pinch-thread jaw.
_PINCH_THREAD_QUALIFIER = "COAXIAL WITH CLEARANCE"
_PINCH_THREAD_NATIVE_TOKENS = frozenset(
    {"<hw-thrutapdrldia>", "<hw-threaddesc>", "<hw-threadclass>"}
)


def _pinch_thread_callout_definitions(
    definitions: dict[int, str],
) -> dict[int, str]:
    """Replace only the native extent words; keep every associative variable."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected pinch callout definition parts: {definitions!r}")
    original = "\n".join(definitions.values())
    missing = _PINCH_THREAD_NATIVE_TOKENS - {
        token for token in _PINCH_THREAD_NATIVE_TOKENS if token in original
    }
    if missing or original.count("<hw-thru>") != 2:
        raise RuntimeError(
            "unexpected native pinch-thread callout definition: "
            f"missing={sorted(missing)!r}, definitions={definitions!r}"
        )
    updated = {
        part: text.replace("<hw-thru>", "TO SLOT")
        for part, text in definitions.items()
    }
    thread_parts = [part for part, text in updated.items() if "<hw-threadclass>" in text]
    if len(thread_parts) != 1:
        raise RuntimeError(f"pinch thread line is not in one callout part: {updated!r}")
    thread_part = thread_parts[0]
    updated[thread_part] = f"{updated[thread_part].rstrip()}\n{_PINCH_THREAD_QUALIFIER}"
    rewritten = "\n".join(updated.values())
    if (
        "THRU ALL" in rewritten
        or rewritten.count("TO SLOT") != 2
        or any(token not in rewritten for token in _PINCH_THREAD_NATIVE_TOKENS)
    ):
        raise RuntimeError(f"pinch-thread callout rewrite lost semantics: {updated!r}")
    return updated


def _pinch_thread_callout_resolved(resolved_parts: dict[int, str]) -> bool:
    """Whether the resolved callout keeps both extents and qualifies the thread.

    GetText(1..4) resolves definition parts 5..8 in part order, which is not
    the sheet's line order: af561fa7 printed part 7 (the tap drill) above
    part 5 (the thread).  So the check is per part -- the qualifier ends the
    thread's own part, which then prints last -- not by string position.
    """
    joined = "\n".join(resolved_parts.values())
    thread = [text for text in resolved_parts.values() if "UNC" in text]
    return (
        "THRU ALL" not in joined
        and joined.count("TO SLOT") == 2
        and len(thread) == 1
        and thread[0].rstrip().endswith(f"TO SLOT\n{_PINCH_THREAD_QUALIFIER}")
    )


# E11/W1: the through thread's two countersinks are one chamfer feature; the
# callout names them under the thread line, so the hole reads in one place.
ADJUSTER_CSK_QUALIFIER = (
    f"90\u00b0 CSK \u00d8{ADJUSTER_BORE_DIA + 2.0 * ADJUSTER_CSK:.1f} BOTH ENDS"
)


def _adjuster_callout_definitions(definitions: dict[int, str]) -> dict[int, str]:
    """Append the countersink line to the one compartment holding the thread."""
    if set(definitions) != {5, 6, 7, 8}:
        raise RuntimeError(f"unexpected adjuster callout parts: {definitions!r}")
    thread_parts = [part for part, text in definitions.items() if "<hw-threadclass>" in text]
    if len(thread_parts) != 1:
        raise RuntimeError(f"adjuster thread line is not in one callout part: {definitions!r}")
    updated = dict(definitions)
    part = thread_parts[0]
    updated[part] = f"{updated[part].rstrip()}\n{ADJUSTER_CSK_QUALIFIER}"
    return updated


def _set_adjuster_callout_text(display: Any) -> None:
    """Name both countersinks under the native through-thread line."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    updated = _adjuster_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    resolved = {part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)}
    thread = [text for text in resolved.values() if "UNF" in text]
    if (
        persisted != updated
        or len(thread) != 1
        or not thread[0].rstrip().endswith(ADJUSTER_CSK_QUALIFIER)
    ):
        raise RuntimeError(
            "adjuster countersink line did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )


def _set_pinch_thread_callout_text(display: Any) -> None:
    """State the final two-jaw extent without severing Hole Wizard variables."""
    definitions = {
        part: str(display.GetText(part) or "")
        for part in (5, 6, 7, 8)
    }
    updated = _pinch_thread_callout_definitions(definitions)
    for definition_part, writable_part in ((5, 1), (6, 2), (7, 3), (8, 4)):
        if updated[definition_part] != definitions[definition_part]:
            display.SetText(writable_part, updated[definition_part])
    persisted = {
        part: str(display.GetText(part) or "")
        for part in (5, 6, 7, 8)
    }
    resolved_parts = {
        part: str(display.GetText(part) or "") for part in (1, 2, 3, 4)
    }
    resolved = "\n".join(resolved_parts.values())
    if persisted != updated or not _pinch_thread_callout_resolved(resolved_parts):
        raise RuntimeError(
            "pinch-thread native extent override did not persist: "
            f"definitions={persisted!r}, resolved={resolved!r}"
        )




def _audit_isometric_annotation_provenance(adapter: Any, view: Any) -> int:
    """Prove every isometric annotation is native cosmetic-thread ink (to hide)."""
    annotation_types = [
        int(_early_bound(raw, "IAnnotation").GetType())
        for raw in (_early_bound(view, "IView").GetAnnotations() or ())
    ]
    if not annotation_types or any(kind != 1 for kind in annotation_types):
        raise RuntimeError(
            "cone-tip isometric annotation provenance changed: "
            f"types={annotation_types!r}"
        )
    _telemetry.debug(
        f"cone-tip isometric: {len(annotation_types)} cosmetic-thread annotations"
    )
    return len(annotation_types)


_COSMETIC_THREAD_LAYER = "CONE-TIP-SECTION-THREADS-HIDDEN"


def _hide_cosmetic_threads(adapter: Any, view: Any, *, label: str) -> int:
    """Keep cosmetic-thread annotation ink out of a view (section, pictorial)."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if int(
            manager.AddLayer(
                _COSMETIC_THREAD_LAYER,
                "cosmetic thread ink hidden in cone-tip section",
                0,
                0,
                0,
            )
        ) != 1:
            raise RuntimeError("failed to add cone-tip section thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cone-tip section thread layer is not hidden")
    hidden = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError(f"cone-tip {label} cosmetic thread refused hidden layer")
        hidden += 1
    if not hidden:
        raise RuntimeError(f"cone-tip {label} has no cosmetic thread to hide")
    rebuild_drawing(adapter, label=f"hide {label} cosmetic threads")
    return hidden




async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-tip-block source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip block; adjuster carrier; split pinch clamp",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=SHEET_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, top, right, left, back, iso):
        set_hidden_lines_removed(adapter, view)

    # The top-view cutting plane passes through both orthogonal bore axes.  The
    # resulting solid-line section shows the through adjuster thread, its
    # countersinks, split jaws and pinch bore relationship without dashed
    # inference.
    #
    # PinchRise lives on the part-hidden PinchRiseReference sketch (995a7c94).
    # A derived view takes a hidden sketch's visibility from the part when it
    # is created and refuses the per-view override the targeted import uses
    # (lever's probe c0514e35, measured on a detail), so the section is made
    # and dimensioned while the part shows that sketch in memory.
    with hidden_sketches.part_sketches_shown(
        adapter, source_model, SECTION_SKETCHES, label="section A pinch rise"
    ):
        section = create_section_view(
            adapter,
            top,
            line_start=(TOP_CENTER[0], _plan_y(Z_NORTH) - 0.004),
            line_end=(TOP_CENTER[0], _plan_y(Z_SOUTH) + 0.004),
            view_xy=SECTION_CENTER,
            section_label="A",
            scale=SHEET_SCALE,
            label="adjuster and pinch-bore centre section",
        )
        set_hidden_lines_removed(adapter, section)
        section_annotations = hidden_sketches.curate_view_dimensions(
            adapter,
            section,
            keep=SECTION_KEEP,
            view_label="bore centre section",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        )
    _add_adjuster_axis(adapter, section)

    adjuster_view, adjuster_center, adjuster_edge = _preferred_entry_circle(
        adapter,
        ((front, FRONT_CENTER), (back, BACK_CENTER)),
        radius_mm=ADJUSTER_BORE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="through adjuster thread",
    )
    assert_sheet_ink_clear(adjuster_center)
    pinch_clearance_edge = _circle_entity(
        adapter,
        right,
        radius_mm=PINCH_CLEARANCE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch entry-jaw clearance",
    )
    pinch_thread_edge = _circle_entity(
        adapter,
        left,
        radius_mm=PINCH_BORE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch opposite-jaw thread",
    )
    front_keep = dict(FRONT_KEEP)
    back_keep: dict[str, tuple[float, float]] = {}
    adjuster_axis_keep = _adjuster_axis_keep(adjuster_center)
    if adjuster_view is front:
        front_keep.update(adjuster_axis_keep)
    else:
        back_keep.update(adjuster_axis_keep)

    # Views that dimension part-hidden reference sketches (995a7c94) import
    # through the opt-in helper, which shows each owner sketch in that view
    # only.  AxisHeight/PassageCenter go to whichever elevation shows the
    # adjuster entry, so only that one opts in; the other shows no sketch.
    adjuster_curate = hidden_sketches.curate_view_dimensions
    front_curate = adjuster_curate if adjuster_view is front else curate_view_dimensions
    back_curate = curate_view_dimensions if adjuster_view is front else adjuster_curate
    front_annotations = front_curate(
        adapter,
        front,
        keep=front_keep,
        view_label="adjuster entry elevation",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="pinch clearance entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    left_annotations = curate_view_dimensions(
        adapter,
        left,
        keep=LEFT_KEEP,
        view_label="pinch threaded entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    back_annotations = back_curate(
        adapter,
        back,
        keep=back_keep,
        view_label="adjuster threaded entry",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *section_annotations,
        *right_annotations,
        *left_annotations,
        *back_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _set_arrows_outside(adapter, annotations, ARROWS_OUTSIDE)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in (
        (front, "adjuster entry elevation"),
        (right, "pinch clearance entry"),
        (left, "pinch threaded entry"),
        (back, "adjuster threaded entry"),
    ):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add centre marks to {label} view")

    adjuster_callout = add_native_hole_callout(
        adapter,
        adjuster_view,
        edge=adjuster_edge,
        callout_xy=_adjuster_callout_xy(adjuster_center),
        label="through adjuster thread",
    )
    _set_adjuster_callout_text(adjuster_callout)
    pinch_clearance_callout = add_native_hole_callout(
        adapter,
        right,
        edge=pinch_clearance_edge,
        callout_xy=PINCH_CLEARANCE_CALLOUT_XY,
        label="pinch entry-jaw clearance",
    )
    set_hole_callout_precision(
        pinch_clearance_callout,
        {"hw-depth": 1},
        label="pinch clearance depth",
    )
    pinch_thread_callout = add_native_hole_callout(
        adapter,
        left,
        edge=pinch_thread_edge,
        callout_xy=PINCH_THREAD_CALLOUT_XY,
        label="pinch opposite-jaw thread",
    )
    _set_pinch_thread_callout_text(pinch_thread_callout)
    _audit_isometric_annotation_provenance(adapter, iso)
    # Main eye-pass af561fa7: the shaded pictorial carries no thread ink.
    _hide_cosmetic_threads(adapter, iso, label="isometric")

    _hide_cosmetic_threads(adapter, section, label="section")
    for text, x, y in _sheet_notes(adjuster_center):
        if add_note(adapter, text, x, y) is None:
            raise RuntimeError(f"failed to add the {text.lower()!r} note")
    # C1 verdict (2026-09-23): the native projected-view arrow is not
    # switchable through the documented API -- IProjectionArrow.Visible is
    # get-only and no document preference or IView member sets it; only the
    # PropertyManager "Arrow" box does.  Untested: an IProjectionArrow.SetLabel
    # side effect, a PropertyManager RunCommand route.  So each removed view
    # is named by a letter note whose straight leader is the viewing arrow.
    for letter, view, (text_xy, tip_xy) in (
        ("B", front, VIEW_B_ARROW),
        ("C", top, VIEW_C_ARROW),
    ):
        note = add_leader_note(
            adapter,
            letter,
            text_xy=text_xy,
            attach_xy=tip_xy,
            view=view,
            label=f"view {letter} viewing arrow",
        )
        # add_note leaves text at the document height; size the letter here
        # (the add_surface_finish char_height recipe) and prove the leader
        # tip did not move with it.
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        text_format = annotation.GetTextFormat(0)
        if text_format is None:
            raise RuntimeError(f"view {letter} arrow note has no text format")
        text_format.CharHeight = VIEW_LETTER_HEIGHT
        if not annotation.SetTextFormat(0, False, text_format):
            raise RuntimeError(f"failed to size the view {letter} arrow letter")
        rebuild_drawing(adapter, label=f"view {letter} arrow letter")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
            raise RuntimeError(f"view {letter} arrow tip moved when its letter was sized")

    foot_edge = _foot_edge(adapter, front)
    foot_y = _elevation_y(0.0, FRONT_CENTER)
    # Onto the foot edge itself, midway along its right half: at the corner
    # vertex (run 6cab17f6) it could name the side face as well as the seat.
    foot_right = (FRONT_CENTER[0] + BLOCK_X * _S / 4.0, foot_y)
    foot_finish = add_surface_finish(
        adapter,
        front,
        edge_entity=foot_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.034, foot_y - 0.013),
        leader_attach_xy=foot_right,
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        char_height=0.003,
        label="swing-platform locating foot seat",
    )
    finish_annotation = _early_bound(foot_finish.GetAnnotation(), "IAnnotation")
    if int(finish_annotation.GetLeaderCount()) != 1:
        raise RuntimeError("foot-seat finish does not have exactly one leader")
    leader_values = tuple(
        float(value) for value in finish_annotation.GetLeaderPointsAtIndex(0)
    )
    leader_points = tuple(
        leader_values[index : index + 3] for index in range(0, len(leader_values), 3)
    )
    if not any(
        abs(point[0] - foot_right[0]) < 1e-6
        and abs(point[1] - foot_right[1]) < 1e-6
        and abs(point[2]) < 1e-6
        for point in leader_points
    ):
        raise RuntimeError(
            "foot-seat finish leader missed the verified bottom-edge endpoint: "
            f"expected={foot_right!r}, points={leader_points!r}"
        )

    # Annotation insertion can regenerate a view with inherited display state;
    # every manufacturing view is explicitly HLR at export.
    for view in (front, top, right, left, back, section):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Block Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        # SolidWorks auto-inserts one descriptive "... Tapped Hole" note per
        # tapped Hole Wizard hole it shows: the adjuster's (I31 retired the
        # U30 foot tap, the second one run 66084ed9 counted).
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=1,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

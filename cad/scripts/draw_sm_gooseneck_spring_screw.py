r"""Create the MHA-SM-04 gooseneck spring screw manufacturing drawing.

The SLDPRT remains authoritative.  MHA-SM-04 is a slotted cheese-head screw
(owner rulings 2026-10-27, #1951): a flat-topped Ø11.50 x 6.60 head, its
under-face edge relieved for the spring's transition wire, over a plain
Ø6.35 body that is both the loop seat and the 1/4-28 UNF thread's blank.  A
screw carries no datum and no geometric-control frame (drawing-guidelines.md
rule 5 (avoid excessive GD&T)): the body Ø, the head Ø and the head's relief
chamfer print as the part's stacked LIMIT bands, the plain length as the part's
single ".14 MIN" and the full-thread station as its single ".225 MAX", both
from the under-head face, the under-head corner as its single "R.020 MAX"
(codjiflo round 4 on #1997), and every other size is an ordinary model
dimension at its part-authored places under the title block's band for those
places (.XX).  Decimal-inch sheet (#290); the model keeps its calibrated
millimetre nominals, which print rounded on the inch grid.

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the head on the
left and the thread tip on the right.  Axial sizes baseline from the
under-head face, the face that clamps the spring eye.  The head-end view is
the ``*Front`` orientation (looking down -Z onto the top face), which is
exactly the third-angle LEFT view of that profile, so it sits on the
profile's axis to its left and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck_spring_screw.py sm-gooseneck-spring-screw
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import import_cosmetic_threads
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from sm_gooseneck_spring_screw_geom import (
    BODY_DIA,
    BODY_DIA_TOL_TYPE,
    FULL_THREAD_STATION_MAX,
    FULL_THREAD_STATION_MAX_TOL_TYPE,
    HEAD_DIA,
    HEAD_DIA_TOL_TYPE,
    HEAD_H,
    HEAD_RELIEF_CHAMFER,
    HEAD_RELIEF_CHAMFER_TOL_TYPE,
    LENGTH,
    OVERALL_LENGTH,
    PLAIN_LENGTH_MIN,
    PLAIN_LENGTH_MIN_TOL_TYPE,
    PRINTED_BANDS,
    SLOT_DEPTH,
    SLOT_FLOOR_Z,
    SLOT_WIDTH,
    TIP_CHAMFER,
    UNDERHEAD_CORNER_R,
    UNDERHEAD_CORNER_R_TOL_TYPE,
)
from sm_gooseneck_spring_screw_spec import (
    DIMENSION_CALLOUTS_ABOVE_BY_NAME,
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
    THREAD_CALLOUT,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck_spring_screw"]
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

# Both orthographic views print at the sheet scale, so neither needs a caption.
# 4:1 lays the 26.10 profile 104.4 mm long and the 1.6 slot 6.4 mm wide.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
# The under-head face stays at sheet x 0.197, where the reviewed renders of
# the earlier screw put it (farm run 20261027T053051351Z): the 19.50 body
# keeps its places toward the tip and the 6.60 head grows toward the
# head-end view, the view's outline then 0.171-0.275 by 0.142-0.188.  The
# view centre is the model bounding box's: top z=HEAD_H to tip z=-LENGTH.
_BOX_MID_Z = (HEAD_H - LENGTH) / 2.0
UNDERHEAD_SHEET_X = 0.197
SIDE_CENTER = (UNDERHEAD_SHEET_X - _BOX_MID_Z * _S / 1000.0, 0.165)
# Third-angle left view of the head end, on the profile's axis.
END_CENTER = (0.085, SIDE_CENTER[1])
ISO_CENTER = (0.360, 0.215)
ISO_SCALE = (2, 1)


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left)."""
    return SIDE_CENTER[0] + (_BOX_MID_Z - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


TOP_X = _sheet_x(HEAD_H)
SLOT_FLOOR_X = _sheet_x(SLOT_FLOOR_Z)
UNDERHEAD_X = _sheet_x(0.0)
TIP_X = _sheet_x(-LENGTH)
# Where the body meets the tip chamfer.
THREAD_START_X = _sheet_x(-(LENGTH - TIP_CHAMFER))
# Where the head's relief chamfer meets its OD.
HEAD_RELIEF_X = _sheet_x(HEAD_RELIEF_CHAMFER)
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
BODY_TOP_Y = _sheet_y(BODY_DIA / 2.0)
BODY_BOTTOM_Y = _sheet_y(-BODY_DIA / 2.0)
# The printed plain-length and full-thread stations on the body's silhouette.
PLAIN_X = _sheet_x(-PLAIN_LENGTH_MIN)
FULL_THREAD_X = _sheet_x(-FULL_THREAD_STATION_MAX)
# The under-head corner round's centre (its arc the quarter down-left of it,
# tangent to the head face and the body) and its radius on the sheet.
UNDERHEAD_CORNER_R_SHEET = UNDERHEAD_CORNER_R * _S / 1000.0
UNDERHEAD_CORNER_CENTER_XY = (
    UNDERHEAD_X + UNDERHEAD_CORNER_R_SHEET,
    _sheet_y(BODY_DIA / 2.0 + UNDERHEAD_CORNER_R),
)

# Text blocks as rendered at this text height (layout audit of farm run
# 20261027T034356887Z): a dimension's block centres on its anchor,
# both ways; its last line sits on the dimension line (the underline), its
# ink ~1.0 mm over the line however the anchor is set (0.96 mm under
# 'CLEARS LEAD', 1.04 mm under 'MHA-SM-01', farm run 20261027T053051351Z);
# lines above it step 5.56 mm (a callout line, or the value over its
# callout) and 4.53 mm (a stacked LIMIT's upper over its lower); the first
# line's ink tops out 4.50 mm above its baseline.  Widths are the widest
# line's: the measured ones where that line rendered, else its Century
# Gothic advance at the scale the measured lines fix (4.667 um per font unit
# at 1000 units, ten rendered strings agreeing within 0.3 %).
_CALLOUT_PITCH = 0.00556
_LIMIT_PITCH = 0.00453
_FIRST_LINE_INK = 0.0045


def block_height(value_lines: int, callout_lines: int) -> float:
    """Sheet height of a dimension block from its underline to its top ink."""
    return (
        callout_lines * _CALLOUT_PITCH
        + (value_lines - 1) * _LIMIT_PITCH
        + _FIRST_LINE_INK
    )


def _callout_lines(name: str) -> int:
    text = (
        DIMENSION_CALLOUTS_BY_NAME.get(name) or DIMENSION_CALLOUTS_ABOVE_BY_NAME[name]
    )
    return len(text.splitlines())


# 'MHA-SM-VN-51' 34.09 mm (font advance; 'MHA-SM-VN-51 LOOP' rendered 48.41
# against its 48.42), the widest row of three blocks below.
_COUNTER_SPRING_WIDTH = 0.0341
# 'THREAD BLANK;' about 36 mm (estimated from the rendered capitals, 'LOOP
# CLEARS' 31.38 mm), wider than the 'MHA-SM-VN-51' row under it.
BODY_DIA_TEXT_WIDTH = 0.036
BODY_DIA_TEXT_HEIGHT = block_height(2, _callout_lines("BodyDia"))
# '3.60 min.' over 'PLAIN;' / 'MHA-SM-VN-51' / 'LOOP SEAT'.
PLAIN_LENGTH_TEXT_WIDTH = _COUNTER_SPRING_WIDTH
PLAIN_LENGTH_TEXT_HEIGHT = block_height(1, _callout_lines("PlainLength"))
# 'TO FULL THREAD' 35.69 mm (font advance) over '5.71 max.', 21.44 mm as
# '5.67 max.' rendered, on one line.
FULL_THREAD_TEXT_WIDTH = 0.0357
FULL_THREAD_VALUE_WIDTH = 0.0214
FULL_THREAD_TEXT_HEIGHT = block_height(1, _callout_lines("FullThread"))
# 'R0.5 max.' 21.69 mm (the vertical rod's 'R0.2 max.' rendered 21.69, farm
# run 20261027T054106110Z) over 'MHA-SM-VN-51' over 'LOOP CLEARS' 31.38 mm.
UNDERHEAD_CORNER_TEXT_WIDTH = _COUNTER_SPRING_WIDTH
# ' 2.00 ', as ' 1.00 ' rendered (farm run 20261010T190631112Z).
SLOT_DEPTH_TEXT_WIDTH = 0.0116
# The relief chamfer: '1.50' over '1.40' (its LIMIT band) over 'X 45 DEG;' /
# 'MHA-SM-VN-51' / 'WIRE CLEARS', the part number the widest row.
HEAD_RELIEF_TEXT_WIDTH = _COUNTER_SPRING_WIDTH
HEAD_RELIEF_TEXT_HEIGHT = block_height(2, _callout_lines("HeadReliefChamfer"))
# The head Ø: its LIMIT band over 'MHA-SM-VN-51' / 'WIRE CLEARS;' / 'LOOP
# OVERLAP' / '0.95 MIN'.  'LOOP OVERLAP' is about 34.3 mm at the 2.86 mm a
# capital the rendered 'LOOP CLEARS' (31.38 mm) shows, the widest row.
HEAD_DIA_TEXT_WIDTH = 0.0343
HEAD_DIA_TEXT_HEIGHT = block_height(2, _callout_lines("HeadDia"))

# Rows below the profile, 15 mm apart (text sits ~3 mm above its requested
# point, the dimension line ~5 mm below it), clear of the body Ø's text
# block above them.  Row 0 chains the head height and the under-head length
# from the under-head face; row 1 carries the reference overall.
_ROW_Y = (HEAD_TOP_Y - 0.093, HEAD_TOP_Y - 0.108)
# The body Ø's dimension line stands on the plain body 2.5 mm from the
# under-head face, clear of the corner round and of the round's radius
# leader, which passes over its upper arrow stub.
BODY_DIA_X = UNDERHEAD_X + 0.010
# The thread callout's leader lands on the edge where the body meets the tip
# chamfer.  The note stands up and right so the leader slants down-left onto
# that edge, under the plain length's row and short of the isometric.
THREAD_PICK = (THREAD_START_X, SIDE_CENTER[1] + 0.004)
THREAD_NOTE_XY = (THREAD_START_X + 0.011, SIDE_CENTER[1] + 0.035)
# The radial leaders' bend stands 1.6 mm short of the text's box and 2.8 mm
# under its anchor (radial dimensions as rendered: dt-pinion-arbor BackCapR
# and dt-pinion-lift-rod CapR, farm run 20261027T025804097Z).
RADIAL_BEND_GAP = 0.0016
RADIAL_BEND_DROP = 0.0028
# The under-head corner's "R0.5 MAX" reads up-right of the upper corner,
# right of the 5.71 station's extension line and under the two station rows,
# "MHA-SM-VN-51" / "LOOP CLEARS" under it.  Its arc is the quarter down-left
# of its centre; the text stands opposite, so SolidWorks lands the radial
# arrow on the circle's point facing the text and the arc's extension carries
# the arc out to it (draw_mg_magnifying_vertical_rod's relief roots).  The
# three-row block centres on its anchor with its shoulder under the last
# row, half a callout row lower per row under the value, and the leader
# leaves the shoulder's left end (draw_pn_pen_rod's three-row "R0.2 MAX"
# block: shoulder 8.35 mm under the anchor, farm audit 20261014T053239477Z).
# The leader leaves the circle 38 degrees above the axis direction, crossing
# only the two stations' extension lines.
UNDERHEAD_CORNER_LEADER_DEG = 38.0
UNDERHEAD_CORNER_TEXT_LEFT = FULL_THREAD_X + 0.004
UNDERHEAD_CORNER_TEXT_X = UNDERHEAD_CORNER_TEXT_LEFT + UNDERHEAD_CORNER_TEXT_WIDTH / 2.0
UNDERHEAD_CORNER_BEND_X = UNDERHEAD_CORNER_TEXT_LEFT - RADIAL_BEND_GAP
UNDERHEAD_CORNER_BEND_Y = UNDERHEAD_CORNER_CENTER_XY[1] + (
    UNDERHEAD_CORNER_BEND_X - UNDERHEAD_CORNER_CENTER_XY[0]
) * math.tan(math.radians(UNDERHEAD_CORNER_LEADER_DEG))
UNDERHEAD_CORNER_BEND_DROP = (
    RADIAL_BEND_DROP + _callout_lines("UnderHeadCornerR") * _CALLOUT_PITCH / 2.0
)
UNDERHEAD_CORNER_TEXT_HEIGHT = block_height(1, _callout_lines("UnderHeadCornerR"))
UNDERHEAD_CORNER_TEXT_XY = (
    UNDERHEAD_CORNER_TEXT_X,
    UNDERHEAD_CORNER_BEND_Y + UNDERHEAD_CORNER_BEND_DROP,
)
# Where the radial line from the bend meets the round's circle.
UNDERHEAD_CORNER_TIP_XY = (
    UNDERHEAD_CORNER_CENTER_XY[0]
    + UNDERHEAD_CORNER_R_SHEET * math.cos(math.radians(UNDERHEAD_CORNER_LEADER_DEG)),
    UNDERHEAD_CORNER_CENTER_XY[1]
    + UNDERHEAD_CORNER_R_SHEET * math.sin(math.radians(UNDERHEAD_CORNER_LEADER_DEG)),
)
UNDERHEAD_CORNER_TIP_TOL_M = 0.0002
# Two rows over the body, both from the under-head face, the longer
# outside: the plain length's dimension line 4.5 mm over the corner radius's
# top ink, the full-thread limit's 10 mm above it.
PLAIN_LENGTH_LINE_Y = UNDERHEAD_CORNER_BEND_Y + UNDERHEAD_CORNER_TEXT_HEIGHT + 0.0045
FULL_THREAD_LINE_Y = PLAIN_LENGTH_LINE_Y + 0.010
# The full-thread block centres over its own 22.8-mm span, above its line.
# Its extension lines rise 1.0 mm past the line, so the value '5.71 max.'
# (21.4 mm) takes the line between them and its callout stands above it
# (farm run 20261027T053051351Z).
FULL_THREAD_TEXT_XY = (
    (UNDERHEAD_X + FULL_THREAD_X) / 2.0,
    FULL_THREAD_LINE_Y + FULL_THREAD_TEXT_HEIGHT / 2.0,
)
# The plain length's span (14.4 mm) is narrower than its block, so the block
# stands right of every line it would otherwise meet: 3 mm clear of the
# full-thread block, which it shares a height with, and so of the 5.71
# station's extension line too.
PLAIN_LENGTH_TEXT_LEFT = (
    max(FULL_THREAD_TEXT_XY[0] + FULL_THREAD_TEXT_WIDTH / 2.0, FULL_THREAD_X) + 0.003
)
# The relief chamfer's axial leg: its 5.8-mm span is narrower than its
# block, so the block stands left of the span over the head, its dimension
# line 7 mm above the slot depth's and its right end 2.5 mm short of the
# full-thread block, clear of the slot depth's text under it.
HEAD_RELIEF_LINE_Y = HEAD_TOP_Y + 0.021
HEAD_RELIEF_TEXT_XY = (
    HEAD_RELIEF_X - 0.003 - HEAD_RELIEF_TEXT_WIDTH / 2.0,
    HEAD_RELIEF_LINE_Y + HEAD_RELIEF_TEXT_HEIGHT / 2.0,
)
SIDE_KEEP = {
    "HeadHeight": ((TOP_X + UNDERHEAD_X) / 2.0, _ROW_Y[0]),
    "UnderHeadLength": ((UNDERHEAD_X + TIP_X) / 2.0, _ROW_Y[0]),
    "OverallLength": ((TOP_X + TIP_X) / 2.0, _ROW_Y[1]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts
    # read like the lathe)): the head's stands between the profile and the
    # head-end view, its block centred on its vertical dimension line and its
    # right end 7 mm short of the head's top face.
    "HeadDia": (TOP_X - 0.007 - HEAD_DIA_TEXT_WIDTH / 2.0, SIDE_CENTER[1]),
    "HeadReliefChamfer": HEAD_RELIEF_TEXT_XY,
    # The slot depth reads from the top face, above the head.  Its 8-mm span
    # is narrower than its text, so the text stands outside, left of the top
    # face's extension line (the earlier crown rise's recipe, farm run
    # 20261010T190631112Z), clear of the station rows' face extension line.
    "SlotDepth": (
        TOP_X - 0.003 - SLOT_DEPTH_TEXT_WIDTH / 2.0,
        HEAD_TOP_Y + 0.012,
    ),
    "FullThread": FULL_THREAD_TEXT_XY,
    "PlainLength": (
        PLAIN_LENGTH_TEXT_LEFT + PLAIN_LENGTH_TEXT_WIDTH / 2.0,
        PLAIN_LENGTH_LINE_Y + PLAIN_LENGTH_TEXT_HEIGHT / 2.0,
    ),
    "UnderHeadCornerR": UNDERHEAD_CORNER_TEXT_XY,
    # The body Ø stands on the plain body; its text is offset below.
    "BodyDia": (BODY_DIA_X, SIDE_CENTER[1] - 0.012),
    # The tip chamfer's axial leg reads below-right of the tip.
    "TipChamfer": (TIP_X + 0.012, SIDE_CENTER[1] - 0.016),
}
# The body Ø's text goes on an OffsetText leader, hung right of its own
# dimension line: the leader meets the text's LEFT end, so with that end
# right of the line the leader descends beside the text, not through it, and
# the text stays clear of the under-head extension line (layout audit of farm
# run 20261010T190631112Z).  Its upper limit's top stays 2 mm under the
# body's lower silhouette and its right end short of the tip chamfer.  As
# rendered in farm run 20261027T034356887Z the leader's foot stood 2.1 mm
# right of the Ø line.
BODY_DIA_LEADER_GAP = 0.0021
BODY_DIA_TEXT_XY = (
    BODY_DIA_X + BODY_DIA_LEADER_GAP + BODY_DIA_TEXT_WIDTH / 2.0,
    BODY_BOTTOM_Y - 0.002 - BODY_DIA_TEXT_HEIGHT / 2.0,
)
# The slot width reads right of the head-end view, left of the head Ø.
END_KEEP = {
    "SlotWidth": (
        END_CENTER[0] + HEAD_DIA * _S / 2000.0 + 0.010,
        END_CENTER[1] + 0.010,
    ),
}
# A point on the threaded body's cylindrical face, clear of every dimension.
CENTERLINE_PICK = ((FULL_THREAD_X + THREAD_START_X) / 2.0, SIDE_CENTER[1] + 0.003)
ISO_NOTE_XY = (0.340, 0.180)
# Bottom-left, above the title-block line, like the other screw sheets.
NOTES_XY = (0.016, 0.070)

# Policy: native generation verifies persisted values, tolerances and
# reference state.  swTolType_e: NONE leaves the title block's band, LIMIT
# prints the model value plus each deviation, MIN / MAX print the model value
# as the part's single limit.  Each row is (nominal mm, tolerance type).
_TOL_NONE, _TOL_LIMIT, _TOL_MIN, _TOL_MAX = 0, 3, 5, 6
if (
    BODY_DIA_TOL_TYPE != _TOL_LIMIT
    or HEAD_DIA_TOL_TYPE != _TOL_LIMIT
    or HEAD_RELIEF_CHAMFER_TOL_TYPE != _TOL_LIMIT
    or PLAIN_LENGTH_MIN_TOL_TYPE != _TOL_MIN
    or FULL_THREAD_STATION_MAX_TOL_TYPE != _TOL_MAX
    or UNDERHEAD_CORNER_R_TOL_TYPE != _TOL_MAX
):
    raise AssertionError(
        "MHA-SM-04 body Ø, head Ø or relief chamfer is no longer LIMIT, plain "
        "length MIN, or full thread and under-head corner MAX"
    )
PRINTED_DIMENSIONS: dict[str, tuple[float, int]] = {
    "HeadDia": (HEAD_DIA, _TOL_LIMIT),
    "HeadHeight": (HEAD_H, _TOL_NONE),
    "HeadReliefChamfer": (HEAD_RELIEF_CHAMFER, _TOL_LIMIT),
    "UnderHeadLength": (LENGTH, _TOL_NONE),
    "BodyDia": (BODY_DIA, _TOL_LIMIT),
    "PlainLength": (PLAIN_LENGTH_MIN, _TOL_MIN),
    "FullThread": (FULL_THREAD_STATION_MAX, _TOL_MAX),
    "UnderHeadCornerR": (UNDERHEAD_CORNER_R, _TOL_MAX),
    "TipChamfer": (TIP_CHAMFER, _TOL_NONE),
    "SlotWidth": (SLOT_WIDTH, _TOL_NONE),
    "SlotDepth": (SLOT_DEPTH, _TOL_NONE),
    "OverallLength": (OVERALL_LENGTH, _TOL_NONE),
}
# Every LIMIT row's (lower, upper) deviations, mm: a LIMIT row without its
# band would skip the deviation readback, so the two must name the same rows.
LIMIT_DEVIATIONS: dict[str, tuple[float, float]] = {
    name: PRINTED_BANDS[name] for name in ("BodyDia", "HeadDia", "HeadReliefChamfer")
}
if set(LIMIT_DEVIATIONS) != {
    name for name, (_, kind) in PRINTED_DIMENSIONS.items() if kind == _TOL_LIMIT
}:
    raise AssertionError("MHA-SM-04 LIMIT rows and their deviations disagree")
# Unprinted controls: each chamfer's rise, held to its axial leg by
# equation, so the "X 45 DEG" callouts are true.
SOURCE_ONLY_DIMENSIONS: dict[str, tuple[float, int]] = {
    "TipChamferRise@ShankProfile": (TIP_CHAMFER, _TOL_NONE),
    "HeadReliefChamferRise@HeadProfile": (HEAD_RELIEF_CHAMFER, _TOL_NONE),
}


def _check_dimension_state(
    label: str, dimension: Any, expected: tuple[float, int]
) -> None:
    """Raise unless one native dimension holds its spec nominal and type."""
    nominal, tolerance_type = expected
    dimension = _early_bound(dimension, "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    value_mm = float(dimension.SystemValue) * 1000.0
    if not math.isclose(value_mm, nominal, abs_tol=1e-6):
        raise RuntimeError(
            f"MHA-SM-04 {label}: persisted nominal {value_mm!r} mm, spec "
            f"{nominal!r} mm; rebuild the source part"
        )
    if int(tolerance.Type) != tolerance_type:
        raise RuntimeError(
            f"MHA-SM-04 {label}: tolerance type {int(tolerance.Type)}, "
            f"spec {tolerance_type}; rebuild the source part"
        )
    if label in LIMIT_DEVIATIONS:
        lower, upper = LIMIT_DEVIATIONS[label]
        read = (
            float(tolerance.GetMinValue()) * 1000.0,
            float(tolerance.GetMaxValue()) * 1000.0,
        )
        if not all(
            math.isclose(a, b, abs_tol=1e-6) for a, b in zip(read, (lower, upper))
        ):
            raise RuntimeError(
                f"MHA-SM-04 {label}: LIMIT deviations {read!r} mm, spec "
                f"{(lower, upper)!r} mm; rebuild the source part"
            )


@_telemetry.traced("drawing.sm_gooseneck_spring_screw.underhead_corner")
def _dress_underhead_corner(
    adapter: Any, side: Any, annotations: Sequence[Any]
) -> None:
    """Prove the imported UnderHeadCornerR prints the round's R MAX over its
    "MHA-SM-VN-51 / LOOP CLEARS", and land its leader on the side view's
    upper corner (draw_mg_magnifying_vertical_rod._dress_relief_roots).

    Read back: radial, measuring UNDERHEAD_CORNER_R, the part's native
    swTolMAX and the callout below the value.  The text stands up-right of
    the round, opposite its down-left quarter: SolidWorks ends the radial
    leader at the circle point facing the text, so the arc's extension line
    carries the arc out to it.  The rebuilt arrow tip must sit on the upper
    round's circle, on the text's side of its centre.
    """
    (annotation,) = [
        item
        for item in annotations
        if dimension_name(adapter, item) == "UnderHeadCornerR"
    ]
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("MHA-SM-04 UnderHeadCornerR imported diametric, not radial")
    _check_dimension_state(
        "UnderHeadCornerR",
        display.GetDimension2(0),
        PRINTED_DIMENSIONS["UnderHeadCornerR"],
    )
    display.ArcExtensionLineOrOppositeSide = True
    if display.ArcExtensionLineOrOppositeSide is not True:
        raise RuntimeError("MHA-SM-04 UnderHeadCornerR refused its arc extension")
    rebuild_drawing(adapter, label="under-head corner radius leader")
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError("MHA-SM-04 UnderHeadCornerR has no rebuilt display data")
    data = _early_bound(raw, "IDisplayData")
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError("MHA-SM-04 UnderHeadCornerR must draw one radial arrow")
    arrow = tuple(float(v) for v in data.GetArrowHeadAtIndex2(0))
    if len(arrow) != 12 or not all(math.isfinite(v) for v in arrow):
        raise RuntimeError("MHA-SM-04 UnderHeadCornerR arrow coordinates incomplete")
    tip = (arrow[0], arrow[1])
    # The upper round's centre: Right-plane sketch (u, v) is model (-Z, Y).
    centre = model_point_in_view(
        adapter,
        side,
        (
            0.0,
            (BODY_DIA / 2.0 + UNDERHEAD_CORNER_R) / 1000.0,
            -UNDERHEAD_CORNER_R / 1000.0,
        ),
        label="under-head corner round centre",
    )
    off = (tip[0] - centre[0], tip[1] - centre[1])
    toward_text = (
        UNDERHEAD_CORNER_TEXT_XY[0] - centre[0],
        UNDERHEAD_CORNER_TEXT_XY[1] - centre[1],
    )
    if (
        abs(math.hypot(*off) - UNDERHEAD_CORNER_R_SHEET) > UNDERHEAD_CORNER_TIP_TOL_M
        or off[0] * toward_text[0] + off[1] * toward_text[1] <= 0.0
    ):
        raise RuntimeError(
            f"MHA-SM-04 UnderHeadCornerR arrow tip {tip} is not on the upper "
            f"round's circle facing its text (centre {centre}, "
            f"R {UNDERHEAD_CORNER_R_SHEET})"
        )
    _telemetry.info(
        f"under-head corner radius: MAX type, callout "
        f"{DIMENSION_CALLOUTS_BY_NAME['UnderHeadCornerR']!r}, arrow tip "
        f"{tip} on the upper round"
    )


@_telemetry.traced(
    "drawing.sm_gooseneck_spring_screw.shank_thread", label_param="label"
)
def _show_shank_thread(adapter: Any, view: Any, label: str) -> None:
    """Import the part's one cosmetic 1/4-28 into ``view`` and hide its
    automatic callout: the sheet's attached THREAD_CALLOUT is the one callout
    (draw_mg_magnifying_lever._hide_other_thread_callouts)."""
    seeds, instances = import_cosmetic_threads(adapter, view)
    if (seeds, instances) != (1, 1):
        raise RuntimeError(
            f"MHA-SM-04 {label} cosmetic threads: seeds/instances="
            f"{(seeds, instances)!r}, expected (1, 1)"
        )
    thread = _early_bound(_early_bound(view, "IView").GetFirstCThread(), "ICThread")
    note = thread.ThreadCallout
    if note is not None:
        annotation = _early_bound(
            _early_bound(note, "INote").GetAnnotation(), "IAnnotation"
        )
        annotation.Visible = 3  # swAnnotationHidden; drawing-local only
        if annotation.Visible != 3:
            raise RuntimeError(f"MHA-SM-04 {label}: automatic thread callout shows")


def _verify_source_dimensions(model: Any) -> None:
    """The unprinted callout controls, read from the opened source part."""
    for full_name, expected in SOURCE_ONLY_DIMENSIONS.items():
        dimension = model.Parameter(full_name)
        if dimension is None:
            raise RuntimeError(f"MHA-SM-04 source part lacks {full_name}")
        _check_dimension_state(full_name, dimension, expected)


def _verify_printed_dimensions(adapter: Any, views: Sequence[Any]) -> None:
    """Re-read every printed size after the last rebuild (settled check)."""
    found: dict[str, list[Any]] = {name: [] for name in PRINTED_DIMENSIONS}
    for view in views:
        for item in _early_bound(view, "IView").GetAnnotations() or ():
            annotation = _early_bound(item, "IAnnotation")
            name = dimension_name(adapter, annotation)
            if name in found:
                found[name].append(annotation)
    for name, expected in PRINTED_DIMENSIONS.items():
        if len(found[name]) != 1:
            raise RuntimeError(
                f"MHA-SM-04 sheet prints {name} {len(found[name])} times, not once"
            )
        display = _early_bound(
            found[name][0].GetSpecificAnnotation(), "IDisplayDimension"
        )
        _check_dimension_state(name, display.GetDimension2(0), expected)
        parenthesized = str(display.GetText(1) or "").startswith("(") and str(
            display.GetText(2) or ""
        ).endswith(")")
        if parenthesized != (name in REFERENCE_DIMENSIONS):
            raise RuntimeError(f"MHA-SM-04 {name}: reference state did not persist")
        if int(display.GetPrimaryPrecision2()) != DRAWING_PRECISION_BY_NAME[name]:
            raise RuntimeError(f"MHA-SM-04 {name}: display places did not persist")
        if (
            name in LIMIT_DEVIATIONS
            and int(display.GetPrimaryTolPrecision2())
            != DRAWING_PRECISION_BY_NAME[name]
        ):
            raise RuntimeError(f"MHA-SM-04 {name}: limit places did not persist")
        # The part authors every callout (swDimensionTextCalloutBelow = 4,
        # swDimensionTextCalloutAbove = 3); the drawing only reads them back.
        # SOLIDWORKS may hand lines back as CRLF.
        for slot, expected_by_name in (
            (4, DIMENSION_CALLOUTS_BY_NAME),
            (3, DIMENSION_CALLOUTS_ABOVE_BY_NAME),
        ):
            callout = str(display.GetText(slot) or "").replace("\r\n", "\n")
            if callout != expected_by_name.get(name, ""):
                raise RuntimeError(
                    f"MHA-SM-04 {name}: callout {callout!r} is not the part's"
                )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open gooseneck-spring-screw source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    _verify_source_dimensions(adapter.currentModel)
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck Spring Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: (
                "gooseneck spring clamp; slotted cheese-head screw; "
                f"{THREAD_CALLOUT}; steel"
            ),
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="head-end",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*side_annotations, *end_annotations]
    offset_dimension_text(adapter, side_annotations, {"BodyDia": BODY_DIA_TEXT_XY})
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _dress_underhead_corner(adapter, side, side_annotations)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-SM-04 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-SM-04 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-SM-04 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-SM-04 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_CALLOUT,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-SM-04 thread callout",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    # The shank's thread: thin minor-diameter lines on the side view and the
    # shaded thread on the isometric (ASME Y14.6 simplified representation).
    _show_shank_thread(adapter, side, "side view")
    _show_shank_thread(adapter, iso, "isometric")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck Spring Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(lambda: _verify_printed_dimensions(adapter, (side, end)),),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

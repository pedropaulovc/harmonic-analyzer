r"""Create the MHA-DT-32 crank handle pivot screw manufacturing drawing.

The SLDPRT remains authoritative.  A screw carries no datum and no
geometric-control frame (drawing-guidelines.md rule 5 (avoid excessive GD&T)): the running-fit shoulder keeps its
native size band and one bearing-surface finish, the tip chamfer its single
MAX limit, and every other size is an ordinary model dimension at its
part-authored places under the title block's bands (#2314).  The thread
relief's 45-degree lead prints in DETAIL A, a 10:1 native detail of the seat
corner (#2172), and the head seat on MHA-DT-35 -- the under-head radius's
single MAX limit and the head break's two limits -- in DETAIL B, a 20:1
native detail of the under-head face (#1757).

The screw axis is model +Z, so the ``*Right`` view already lays it horizontal
as it sits in the lathe: model +Z runs to paper-LEFT, putting the thread tip on
the left and the slotted head on the right.  Axial locations read from the
tip (see ``dt_crank_handle_pivot_screw_spec``).  The head-end view is
the ``*Back`` orientation, which is exactly the third-angle RIGHT view of that
profile, so it sits on the profile's axis to its right and shows the slot.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_crank_handle_pivot_screw.py dt-crank-handle-pivot-screw
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)

from _com import _early_bound, _read_member
from _check import check
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
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
from _surface_finish import surface_finish_by_key
import _telemetry
from dt_crank_handle_head_seat_spec import (
    HEAD_CHAMFER,
    HEAD_CHAMFER_LIMITS,
    LIMIT_TOL_TYPE,
    SCREW_DRAWING_DIMENSIONS as DRAWING_DIMENSIONS,
    SCREW_DRAWING_PRECISION_BY_NAME as DRAWING_PRECISION_BY_NAME,
    UNDER_HEAD_RADIUS_BAND,
    UNDER_HEAD_RADIUS_MAX,
    UNDER_HEAD_RADIUS_TOL_TYPE,
)
from dt_crank_handle_pivot_screw_notes import (
    HEAD_CHAMFER_CALLOUT,
    HEAD_DIA_CALLOUT,
    HEAD_LENGTH_CALLOUT,
    RELIEF_LEAD_CALLOUT,
    SHOULDER_FIT_CALLOUT,
    SHOULDER_LENGTH_CALLOUT,
    SHOULDER_LENGTH_NOTE,
    THREAD_NOTE,
    UNDER_HEAD_RADIUS_CALLOUT,
)
from dt_crank_handle_pivot_screw_spec import (
    HEAD_DIA,
    HEAD_LENGTH,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
    RELIEF_CALLOUT,
    RELIEF_DIA,
    RELIEF_END_STATION,
    RELIEF_LEAD,
    SEAT_EDGE_NOTE,
    SEAT_STATION,
    SHOULDER_DIA,
    SURFACE_FINISHES,
    THREAD_MODEL_DIA,
    THREAD_SIZE,
    TIP_CHAMFER,
    TIP_CHAMFER_CALLOUT,
)
from _fit_deviations import deviations


SPEC = DRAWINGS_BY_NAME["dt_crank_handle_pivot_screw"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
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
# 3:1 lays the 69.5 profile 208 mm long and the 1.0 slot 3 mm wide.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
SIDE_CENTER = (0.160, 0.165)
# Third-angle right view of the slotted head end, on the profile's axis.
END_CENTER = (0.322, SIDE_CENTER[1])
ISO_CENTER = (0.380, 0.225)
ISO_SCALE = (1, 1)


def _sheet_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z station on the side view (model +Z runs left).

    The view is centred on the model bbox, head face (z=0) to thread tip.
    """
    return SIDE_CENTER[0] + (OVERALL_LENGTH / 2.0 - model_z_mm) * _S / 1000.0


def _sheet_y(radius_mm: float) -> float:
    """Sheet Y of a point ``radius_mm`` above the screw axis (model +Y up)."""
    return SIDE_CENTER[1] + radius_mm * _S / 1000.0


HEAD_FACE_X = _sheet_x(0.0)
UNDERHEAD_X = _sheet_x(HEAD_LENGTH)
SEAT_X = _sheet_x(SEAT_STATION)
RELIEF_END_X = _sheet_x(RELIEF_END_STATION)
TIP_X = _sheet_x(OVERALL_LENGTH)
# Where the full thread meets the tip chamfer.
THREAD_START_X = _sheet_x(OVERALL_LENGTH - TIP_CHAMFER)
HEAD_TOP_Y = _sheet_y(HEAD_DIA / 2.0)
SHOULDER_TOP_Y = _sheet_y(SHOULDER_DIA / 2.0)
THREAD_TOP_Y = _sheet_y(THREAD_MODEL_DIA / 2.0)
THREAD_BOTTOM_Y = _sheet_y(-THREAD_MODEL_DIA / 2.0)
RELIEF_TOP_Y = _sheet_y(RELIEF_DIA / 2.0)
RELIEF_MID_X = (SEAT_X + RELIEF_END_X) / 2.0
# The relief floor runs from the foot of the 45-degree lead to the flank.
RELIEF_FLOOR_MID_X = (_sheet_x(SEAT_STATION + RELIEF_LEAD) + RELIEF_END_X) / 2.0

# Rows below the profile, 15 mm apart (text sits ~3 mm above its requested
# point and the dimension line ~5 mm below it).  Row 0 carries the thread
# length from the tip on the left and the head length from the under-head face
# on the right; row 1 the fitted shoulder length from the seat face; row 2 the
# reference overall.  Row 0 stands 34 mm below the axis so the relief Ø and
# the thread callout can print between it and the profile.  No extension line
# crosses a dimension line.
_ROW_Y = (SIDE_CENTER[1] - 0.034, SIDE_CENTER[1] - 0.049, SIDE_CENTER[1] - 0.064)
SIDE_KEEP = {
    "ThreadLength": ((TIP_X + SEAT_X) / 2.0, _ROW_Y[0]),
    # Right of the head face, outside its extension lines, so its callout
    # stands clear of them and of the under-head and overall extension lines
    # (farm r8 of f5256bf3d: at + 0.020 the 43-mm block's left end crossed
    # the head face's extension line).
    "HeadLength": (HEAD_FACE_X + 0.026, _ROW_Y[0]),
    # The fitted shoulder, seat face to under-head, its fit-up as its callout:
    # two 46-character rows (117 mm) between its 158-mm extension lines.
    "ShoulderLength": ((SEAT_X + UNDERHEAD_X) / 2.0, _ROW_Y[1]),
    "OverallLength": ((TIP_X + HEAD_FACE_X) / 2.0, _ROW_Y[2]),
    # Diameters on the side view (drawing-guidelines.md rule 11 (turned parts read like the lathe)).  The shoulder's dimension line
    # crosses the shoulder right of the relief Ø's callout below it; the
    # head's stands clear of the head face, left of the end view.  Fan-out
    # r1 (57234c1d71): at + 0.075 the 59-mm RUNNING FIT callout ended 3.6 mm
    # under the Ra 63 leader, so the line stands 3 mm right of the relief
    # callout's 46-mm block and the callout wraps at its 21-character row.
    "ShoulderDia": (SEAT_X + 0.062, SIDE_CENTER[1] + 0.030),
    # Above the head, so the callout under the value stands clear of its
    # extension lines and of the slot depth's text left of it.
    "HeadDia": (HEAD_FACE_X + 0.014, SIDE_CENTER[1] + 0.032),
    # The thread-relief groove against the seat face.  Its width from the seat
    # face reads above it alone; its Ø reads below it, the dimension line
    # standing on the floor so nothing crosses.  The 45-degree lead's own
    # dimension reads in detail A (DETAIL_KEEP).
    "ReliefWidth": (RELIEF_MID_X, SIDE_CENTER[1] + 0.022),
    "ReliefDia": (RELIEF_FLOOR_MID_X, SIDE_CENTER[1] - 0.016),
    # The tip chamfer's axial leg reads below-left of the tip, clear of the
    # thread size's extension line at the tip and of the callout above.
    "TipChamfer": (TIP_X - 0.020, SIDE_CENTER[1] - 0.016),
    # The slot shows as a notch in the head face; its depth reads above it.
    "SlotDepth": (HEAD_FACE_X - 0.0015, SIDE_CENTER[1] + 0.026),
}
# The relief Ø's dimension line stands on the floor (SIDE_KEEP); its text
# goes on an OffsetText leader so the seat-face extension line (the thread
# length's right side) cannot run through the callout.  With OffsetText the
# anchor is the CENTRE of the Ø line's bottom edge and the callout is centred
# under it (a dimension exposes no GetExtent), measured on farm run 69a2f961's
# render: the underline, where the leader lands, sits 5.6 mm below the anchor.
# Farm r8 of f5256bf3d rendered the inch callout at 2.5 mm a character, so
# its 18-character rows span 46 mm.  The text's left edge stands 12 mm right
# of the seat face (3.5 mm before the thread callout moved below the thread)
# and 28 mm below the axis, so the leader, dropping to the Ø line under the
# seat-face corner rather than through the shoulder, stays 5 mm clear of the
# thread callout's right end.  The shoulder Ø's arrow is right of it.
RELIEF_DIA_TEXT_WIDTH = 0.046
RELIEF_DIA_TEXT_UNDERLINE_DROP = 0.0056
RELIEF_DIA_TEXT_CLEARANCE = 0.012
RELIEF_DIA_TEXT_XY = (
    SEAT_X + RELIEF_DIA_TEXT_CLEARANCE + RELIEF_DIA_TEXT_WIDTH / 2.0,
    SIDE_CENTER[1] - 0.028,
)
# The 3-mm slot is narrower than the text, so the value stands above its
# extension lines rather than between them.
END_KEEP = {
    "SlotWidth": (END_CENTER[0] + 0.022, END_CENTER[1] + 0.010),
}
# The thread callout lands on the full thread's lower silhouette just in from
# the tip chamfer, from below: above the thread, its leader ran through where
# the relief lead's note stood (#290 review of b28d38a16).  Its
# 9-character text (23.5 mm on farm r10 of 4e4991e0a) stands 15 mm below the
# axis between the chamfer's extension line and the seat face's, which it
# crossed when it started 5.6 mm in from the thread start (r10).
THREAD_PICK = (THREAD_START_X + 0.0015, THREAD_BOTTOM_Y)
THREAD_NOTE_XY = (THREAD_START_X + 0.0021, SIDE_CENTER[1] - 0.015)
# DETAIL A (#2172): the 45-degree relief lead is 0.9 mm of sheet at 3:1, and
# the groove already carries the relief width above it and the Ø below it
# (the #2102 review found it too crowded for a third dimension), so a 10:1
# native detail carries the lead's model dimension and its words,
# as MHA-DT-08's detail B carries its tenon-root relief.  A detail imports
# only a dimension whose references it shows, so the fence takes in both ends
# of the lead and the seat-face corner.  It stays above the axis (no ink of
# the turning axis or the station reference line along it), and on the side
# view its 2.7-mm circle stays right of the relief Ø's dimension line.
DETAIL_LETTER = "A"
DETAIL_SCALE = (10, 1)
_DS = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
# (model station z, radius): mid-lead, halfway from the floor to the shoulder.
DETAIL_FOCUS_MM = (
    SEAT_STATION + RELIEF_LEAD / 2.0,
    (RELIEF_DIA + SHOULDER_DIA) / 4.0,
)
DETAIL_RADIUS_MM = 0.9
_FENCE_MARGIN_MM = 0.3
_LEAD_START = (SEAT_STATION, RELIEF_DIA / 2.0 + RELIEF_LEAD)
_LEAD_FOOT = (SEAT_STATION + RELIEF_LEAD, RELIEF_DIA / 2.0)
_SEAT_CORNER = (SEAT_STATION, SHOULDER_DIA / 2.0)
if (
    any(
        math.dist(DETAIL_FOCUS_MM, point) > DETAIL_RADIUS_MM - _FENCE_MARGIN_MM
        for point in (_LEAD_START, _LEAD_FOOT, _SEAT_CORNER)
    )
    or DETAIL_FOCUS_MM[1] <= DETAIL_RADIUS_MM
):
    raise AssertionError(
        "detail A's fence must take in the relief lead's ends and the seat-face "
        "corner, and stay above the axis"
    )
# Lower left, the sheet's one open field, under the groove: the circle spans
# x 0.096..0.114, y 0.041..0.059, and the lead's block above it (DETAIL_KEEP)
# tops out near y 0.083, 18 mm under the overall's row and left of the title
# block.
DETAIL_CENTER = (0.105, 0.050)
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * _DS
# The label hangs from its top centre 5 mm under the circle.
DETAIL_LABEL_XY = (DETAIL_CENTER[0], DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - 0.005)
# The circle's letter on the side view stands up-left of the fence, where the
# lead's note stood: 3 mm over the thread, left of the relief width's left
# extension line and under its dimension line.
DETAIL_LETTER_XY = (RELIEF_END_X - 0.005, SIDE_CENTER[1] + 0.0095)


def _detail_xy(model_z_mm: float, radius_mm: float) -> tuple[float, float]:
    """Sheet point of a model point in detail A (as the side view: +Z left)."""
    return (
        DETAIL_CENTER[0] + (DETAIL_FOCUS_MM[0] - model_z_mm) * _DS,
        DETAIL_CENTER[1] + (radius_mm - DETAIL_FOCUS_MM[1]) * _DS,
    )


# The lead's horizontal dimension prints its value, then its three callout
# rows, with the dimension line under the last row (the tip chamfer's block
# on farm run 20261104T070839859Z: value 5.1 mm over its keep, the first row
# on it, rows 5.5 mm apart, the line 2.5 mm under the last).  The block stands
# up-left of the circle: its line 4 mm over the circle's top, its 16-character
# rows (41 mm at 2.55 mm a character) ending 4 mm left of the lead foot's
# extension line, so the line runs to the arrows over open sheet.
RELIEF_LEAD_TEXT_WIDTH = 0.041
RELIEF_LEAD_LINE_DROP = 0.0135
DETAIL_KEEP = {
    "ReliefLead": (
        _detail_xy(*_LEAD_FOOT)[0] - 0.004 - RELIEF_LEAD_TEXT_WIDTH / 2.0,
        DETAIL_CENTER[1] + DETAIL_CROP_RADIUS + 0.004 + RELIEF_LEAD_LINE_DROP,
    ),
}
# DETAIL B (#1757): the head seat on MHA-DT-35.  The under-head radius (0.1)
# and the head's break (0.19) are under 0.6 mm of sheet at 3:1, so a 20:1
# native detail of the flat under-head face carries both model dimensions.
# The fence takes in the round's two tangent points and the break's two ends,
# and stays above the axis.
DETAIL_B_LETTER = "B"
DETAIL_B_SCALE = (20, 1)
_DBS = DETAIL_B_SCALE[0] / DETAIL_B_SCALE[1] / 1000.0
# (model station z, radius): just past the under-head face, halfway up it.
DETAIL_B_FOCUS_MM = (HEAD_LENGTH + 0.1, (SHOULDER_DIA + HEAD_DIA) / 4.0)
DETAIL_B_RADIUS_MM = 0.8
_DETAIL_B_MARGIN_MM = 0.2
_ROUND_ON_SHOULDER = (HEAD_LENGTH + UNDER_HEAD_RADIUS_MAX, SHOULDER_DIA / 2.0)
_ROUND_ON_FACE = (HEAD_LENGTH, SHOULDER_DIA / 2.0 + UNDER_HEAD_RADIUS_MAX)
_BREAK_ON_OD = (HEAD_LENGTH - HEAD_CHAMFER, HEAD_DIA / 2.0)
_BREAK_ON_FACE = (HEAD_LENGTH, HEAD_DIA / 2.0 - HEAD_CHAMFER)
if (
    any(
        math.dist(DETAIL_B_FOCUS_MM, point) > DETAIL_B_RADIUS_MM - _DETAIL_B_MARGIN_MM
        for point in (_ROUND_ON_SHOULDER, _ROUND_ON_FACE, _BREAK_ON_OD, _BREAK_ON_FACE)
    )
    or DETAIL_B_FOCUS_MM[1] <= DETAIL_B_RADIUS_MM
):
    raise AssertionError(
        "detail B's fence must take in the under-head round and the head break, "
        "and stay above the axis"
    )
# Bottom middle, right of detail A and left of the title block: the circle
# spans x 0.156..0.188, y 0.038..0.070, under the overall's row.
DETAIL_B_CENTER = (0.172, 0.054)
DETAIL_B_CROP_RADIUS = DETAIL_B_RADIUS_MM * _DBS
DETAIL_B_LABEL_XY = (
    DETAIL_B_CENTER[0],
    DETAIL_B_CENTER[1] - DETAIL_B_CROP_RADIUS - 0.005,
)
# The circle's letter on the side view stands up-left of the under-head
# corner, left of the head and right of the finish symbol's leader.
DETAIL_B_LETTER_XY = (UNDERHEAD_X - 0.006, SIDE_CENTER[1] + 0.016)


def _detail_b_xy(model_z_mm: float, radius_mm: float) -> tuple[float, float]:
    """Sheet point of a model point in detail B (as the side view: +Z left)."""
    return (
        DETAIL_B_CENTER[0] + (DETAIL_B_FOCUS_MM[0] - model_z_mm) * _DBS,
        DETAIL_B_CENTER[1] + (radius_mm - DETAIL_B_FOCUS_MM[1]) * _DBS,
    )


# The break's horizontal leg prints its two limits, then its three callout
# rows, with the dimension line under the last row (as the lead's): the line
# 4 mm over the break's top end, the block right of both extension lines so
# the line runs to the arrows over open sheet.  The radius's block stands
# up-left of the circle, on the round's centre side, where its leader reaches
# the arc through air above the shoulder (its arc extension drawn,
# draw_dt_crank_handle._dress_inside_corner).
HEAD_CHAMFER_TEXT_WIDTH = 0.041
DETAIL_B_KEEP = {
    "HeadChamfer": (
        _detail_b_xy(*_BREAK_ON_OD)[0] + 0.004 + HEAD_CHAMFER_TEXT_WIDTH / 2.0,
        _detail_b_xy(*_BREAK_ON_OD)[1] + 0.004 + RELIEF_LEAD_LINE_DROP,
    ),
    "UnderHeadRadius": (0.140, 0.074),
}
# The running shoulder's upper flank, right of the Ø dimension line and its
# callout block (farm r1 of eb22a22f1: at x - 0.050 the leader ran through
# the block's right end).
FINISH_PICK = (UNDERHEAD_X - 0.040, SHOULDER_TOP_Y)
FINISH_SYMBOL = (UNDERHEAD_X - 0.030, SIDE_CENTER[1] + 0.030)
# A point on the shoulder face, clear of the Ø dimension line.
CENTERLINE_PICK = (UNDERHEAD_X - 0.025, SIDE_CENTER[1] + 0.003)
# The seat edge's break note lands on the shoulder's silhouette 2.5 mm right
# of its seat-face corner (6 mm read as the shank, not the corner: #290 review
# of d72bdd039), from up and right, above the relief width and the shoulder
# Ø's callout blocks: landing on the seat face itself, its leader crossed the
# relief width's dimension line (farm r8 of f5256bf3d).  The note stands 24 mm
# right of the seat face so the leader passes right of that dimension line's
# outside arrow, which ends 6.4 mm right of the seat face (farm r13: from
# 20 mm and 2 mm the leader crossed it).
SEAT_EDGE_PICK = (SEAT_X + 0.0025, SHOULDER_TOP_Y)
SEAT_EDGE_NOTE_XY = (SEAT_X + 0.024, SIDE_CENTER[1] + 0.060)
# The relief Ø's arrows stand inside the groove: outside, the upper arrow's
# stub stood above the floor, where the old lead note's leader passed (#290
# review of f166646c4), beside detail A's fence.
_ARROWS_INSIDE = 0  # swDimArrowsSide_e.swDimArrowsInside
ISO_NOTE_XY = (0.352, 0.200)
# Numbered note 1's upper-left corner: right of the head length's callout
# (text ends near x 0.305), under the end view (bottom near y 0.158) and
# above the title block; its widest line (~36 characters at ~2.7 mm) ends
# short of the right border (0.4191).
NOTES_XY = (0.315, 0.145)


def _set_relief_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    matches = [a for a in annotations if dimension_name(adapter, a) == "ReliefDia"]
    if len(matches) != 1:
        raise RuntimeError("expected one MHA-DT-32 ReliefDia dimension")
    annotation = _early_bound(matches[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    display.ArrowSide = _ARROWS_INSIDE
    if int(display.ArrowSide) != _ARROWS_INSIDE:
        raise RuntimeError("MHA-DT-32 ReliefDia did not keep its arrows inside")


def _dress_head_seat(adapter: Any, annotations: list[Any]) -> None:
    """Prove detail B's imports print the model's head seat (#1757): the
    under-head radius as a radial R.004 MAX, its leader reaching the arc
    through an arc extension (its text stands on the round's centre side,
    off the arc's span), and the head break as its two native limits."""
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in ("UnderHeadRadius", "HeadChamfer"):
        if name not in by_name:
            raise RuntimeError(f"MHA-DT-32 detail B lacks its {name} dimension")
    radius = _early_bound(
        _early_bound(by_name["UnderHeadRadius"], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    if bool(radius.Diametric) or int(radius.Type2) != 5:  # swRadialDimension
        raise RuntimeError(
            "MHA-DT-32 UnderHeadRadius imported as a non-radial dimension"
        )
    dimension = _early_bound(radius.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    lower, upper = deviations(UNDER_HEAD_RADIUS_BAND)
    if (
        not math.isclose(
            float(dimension.SystemValue), UNDER_HEAD_RADIUS_MAX / 1000.0, abs_tol=1e-9
        )
        or int(tolerance.Type) != UNDER_HEAD_RADIUS_TOL_TYPE
        or not math.isclose(
            float(tolerance.GetMinValue()), lower / 1000.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(tolerance.GetMaxValue()), upper / 1000.0, abs_tol=1e-12
        )
        or bool(dimension.IsReference())
    ):
        raise RuntimeError("MHA-DT-32 UnderHeadRadius lost its model MAX limit")
    radius.ArcExtensionLineOrOppositeSide = True
    if not bool(radius.ArcExtensionLineOrOppositeSide):
        raise RuntimeError("MHA-DT-32 UnderHeadRadius refused its arc extension")
    chamfer = _early_bound(
        _early_bound(by_name["HeadChamfer"], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    dimension = _early_bound(chamfer.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    nominal = float(dimension.SystemValue) * 1000.0
    limits = (
        nominal + float(tolerance.GetMinValue()) * 1000.0,
        nominal + float(tolerance.GetMaxValue()) * 1000.0,
    )
    if (
        not math.isclose(nominal, HEAD_CHAMFER, abs_tol=1e-6)
        or int(tolerance.Type) != LIMIT_TOL_TYPE
        or any(
            not math.isclose(actual, expected, abs_tol=1e-6)
            for actual, expected in zip(limits, HEAD_CHAMFER_LIMITS, strict=True)
        )
    ):
        raise RuntimeError(f"MHA-DT-32 HeadChamfer lost its model limits: {limits}")


@dataclass(frozen=True)
class SideDetail:
    """One native circular detail of the side view, at sheet coordinates."""

    letter: str
    scale: tuple[int, int]
    focus_mm: tuple[float, float]  # (model station z, radius)
    radius_mm: float
    center: tuple[float, float]
    label_xy: tuple[float, float]
    letter_xy: tuple[float, float]


DETAILS = (
    SideDetail(
        DETAIL_LETTER,
        DETAIL_SCALE,
        DETAIL_FOCUS_MM,
        DETAIL_RADIUS_MM,
        DETAIL_CENTER,
        DETAIL_LABEL_XY,
        DETAIL_LETTER_XY,
    ),
    SideDetail(
        DETAIL_B_LETTER,
        DETAIL_B_SCALE,
        DETAIL_B_FOCUS_MM,
        DETAIL_B_RADIUS_MM,
        DETAIL_B_CENTER,
        DETAIL_B_LABEL_XY,
        DETAIL_B_LETTER_XY,
    ),
)


@_telemetry.traced("crank_handle_pivot_screw.side_detail")
def _side_detail(adapter: Any, side: Any, spec: SideDetail) -> Any:
    """Native detail of the side view (draw_dt_crank_handle._ferrule_seat_detail):
    fence, scale, outline, label and letter each read back."""
    name = f"detail {spec.letter}"
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(side, "IView")
    if not drawing.ActivateView(view_name(adapter, side)):
        raise RuntimeError(f"failed to activate {name}'s parent side view")
    draw.ClearSelection2(True)
    # The profile lies on the Right plane: model (x, y, z) = (0, radius, station).
    center = model_point_in_view(
        adapter,
        side,
        (0.0, spec.focus_mm[1] / 1000.0, spec.focus_mm[0] / 1000.0),
        label=f"{name} fence centre",
    )
    sheet_xy = [center[:2], (center[0] + spec.radius_mm * _S / 1000.0, center[1])]
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_xy:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    # Straight to the database: an inferred circle snaps onto nearby edges
    # (draw_dt_pinion_lever r2), and each fence sits on a corner of the
    # profile, so the fence is read back before use.
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError(f"failed to create {name}'s fence")
    arc = _early_bound(fence, "ISketchArc")
    placed = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    placed_centre = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XY"]
    if math.dist(placed_centre, points[0][:2]) > 1e-9 or not math.isclose(
        float(arc.GetRadius()), math.dist(points[0][:2], points[1][:2]), abs_tol=1e-9
    ):
        raise RuntimeError(f"{name}'s fence moved from where it was placed")
    draw.ClearSelection2(True)
    if not _early_bound(fence, "ISketchSegment").Select4(False, None):
        raise RuntimeError(f"failed to select {name}'s fence")
    detail = drawing.CreateDetailViewAt4(
        *spec.center,
        0.0,
        0,  # swDetViewSTANDARD
        *spec.scale,
        spec.letter,
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError(f"CreateDetailViewAt4 returned no {name}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in spec.scale])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(ratio) != 2 or not math.isclose(
        ratio[0] / ratio[1], spec.scale[0] / spec.scale[1]
    ):
        raise RuntimeError(f"{name} scale {ratio!r}, expected {spec.scale!r}")
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError(f"{name} has invalid bounds")
    span = 2.0 * spec.radius_mm * spec.scale[0] / spec.scale[1] / 1000.0
    _telemetry.info(
        f"{name} outline {outline[2] - outline[0]:.5f} x "
        f"{outline[3] - outline[1]:.5f} m (fence {span:.5f})"
    )
    if min(outline[2] - outline[0], outline[3] - outline[1]) < 0.95 * span:
        raise RuntimeError(f"{name} is smaller than its fence: {outline}")
    target = [
        position[axis] + spec.center[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to position {name}")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {name} label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*spec.label_xy, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError(f"failed to position {name}'s label")
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"{name}'s label position did not persist: {actual}")
    circles = [
        _early_bound(raw, "IDetailCircle")
        for raw in (_read_member(parent, "GetDetailCircles") or ())
    ]
    mine = [circle for circle in circles if str(circle.GetLabel()) == spec.letter]
    if len(mine) != 1:
        raise RuntimeError(
            f"expected one {name} circle on the side view, found "
            f"{[str(circle.GetLabel()) for circle in circles]}"
        )
    mine[0].SetLabelPosition(*spec.letter_xy)
    draw.EditRebuild3()
    letter = tuple(float(value) for value in mine[0].GetLabelPosition())
    if len(letter) != 2 or math.dist(letter, spec.letter_xy) > 1e-8:
        raise RuntimeError(f"{name}'s letter did not persist: {letter}")
    return detail


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-pivot-screw source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
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
            0: "Crank Handle Pivot Screw Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: f"crank handle pivot; slotted shoulder screw; {THREAD_SIZE}; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    # Both details first (draw_dt_crank_handle, after draw_ch_amplitude_bar
    # r743-6): a dimension already on the sheet is never imported again while
    # a deleted one is, and a native detail imported nothing after its
    # parent's import and deletions.  Each detail keeps its own and deletes
    # whatever else its fence shows; the side view's import then takes those
    # back and skips the ones the details hold.
    detail, seat_detail = (_side_detail(adapter, side, spec) for spec in DETAILS)
    set_hidden_lines_removed(adapter, detail)
    set_hidden_lines_removed(adapter, seat_detail)
    # The under-head round's tangent edges would draw a second line beside
    # the under-head face and the shoulder (draw_dt_crank_handle).
    for view, label in ((side, "side view"), (seat_detail, "detail B")):
        view.SetDisplayTangentEdges2(0)
        if int(view.GetDisplayTangentEdges2()) != 0:
            raise RuntimeError(f"failed to hide MHA-DT-32 {label} tangent edges")
        view.UpdateViewDisplayGeometry()
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="relief lead detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    seat_annotations = curate_view_dimensions(
        adapter,
        seat_detail,
        keep=DETAIL_B_KEEP,
        view_label="head seat detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
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
    annotations = [
        *side_annotations,
        *end_annotations,
        *detail_annotations,
        *seat_annotations,
    ]
    set_dimension_callouts(
        adapter, annotations, {"ReliefDia": RELIEF_CALLOUT}, location="below"
    )
    set_dimension_callouts(
        adapter,
        annotations,
        {
            "TipChamfer": TIP_CHAMFER_CALLOUT,
            "ShoulderLength": SHOULDER_LENGTH_CALLOUT,
            "ShoulderDia": SHOULDER_FIT_CALLOUT,
            "HeadDia": HEAD_DIA_CALLOUT,
            "HeadLength": HEAD_LENGTH_CALLOUT,
            "ReliefLead": RELIEF_LEAD_CALLOUT,
            "UnderHeadRadius": UNDER_HEAD_RADIUS_CALLOUT,
            "HeadChamfer": HEAD_CHAMFER_CALLOUT,
        },
        location="below",
    )
    offset_dimension_text(adapter, side_annotations, {"ReliefDia": RELIEF_DIA_TEXT_XY})
    _set_relief_arrows_inside(adapter, side_annotations)
    _dress_head_seat(adapter, seat_annotations)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [
            annotation
            for annotation in annotations
            if dimension_name(adapter, annotation) == name
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one MHA-DT-32 {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"MHA-DT-32 {name}")

    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to MHA-DT-32 head-end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=CENTERLINE_PICK,
        label="MHA-DT-32 turning axis",
    )
    add_attached_note(
        adapter,
        side,
        text=THREAD_NOTE,
        entity_xy=THREAD_PICK,
        note_xy=THREAD_NOTE_XY,
        label="MHA-DT-32 thread callout",
        entity_type="SILHOUETTE",
    )
    add_attached_note(
        adapter,
        side,
        text=SEAT_EDGE_NOTE,
        entity_xy=SEAT_EDGE_PICK,
        note_xy=SEAT_EDGE_NOTE_XY,
        label="MHA-DT-32 seat edge break",
        entity_type="SILHOUETTE",
    )
    add_surface_finish(
        adapter,
        side,
        edge_xy=FINISH_PICK,
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_shoulder"),
        label="MHA-DT-32 pivot-shoulder finish",
        entity_type="SILHOUETTE",
        char_height=0.0025,
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    if add_note(adapter, SHOULDER_LENGTH_NOTE, *NOTES_XY) is None:
        raise RuntimeError("failed to add the pivot screw's numbered note")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Pivot Screw Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

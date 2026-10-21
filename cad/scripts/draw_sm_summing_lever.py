r"""Create the curated machinist drawing for the summing lever.

The SLDPRT remains authoritative.  This recipe supplies only the summing-lever
views, dimension layout, hole callouts, and manufacturing notes;
sheet/template and export behavior lives in ``_drawing_common``.
Dimension import and curation live in ``_drawing_dimension_import``.

A large green cast-iron first-class lever hung on hex knife-edge trunnions (no
bore): a coefficients plate on the +X arm carrying the 20 channel-spring anchor
taps, a solid pivot cylinder (152.4 long, along Z), and a summation arm
reaching to the tapped counter-spring anchor boss on the -X arm.  Both spring
anchors are purchased eyebolts that thread straight into those taps, so the
print controls thread identity and position, never a seat bore.  Sheet 1
shows a 1:2 front profile (the boss, web and the end-rib outline), a
4:1 detail of the trunnion envelope and its knife-edge round, a
1:2 top plan (plate, ribs, cylinder, summation web, trunnion length, the
anchor taps and their pattern control, and the VIEW F arrow onto the -Z
end), a 1:1 partial section C-C of the plate's thickness, a 4:1 section H-H
cut in the front profile along the outer receiver tap through the -Z end
rib, and a 1:4 isometric; sheet 2 shows VIEW F at 1:1, the -Z end with the
two bracket receiver taps and the spring-anchor pad under the plate they sit
in, so the end rib's slant over each tap reads, and the tap row's centreline
through the hex centre.  The native row-height dimension locates that common
axis from the plate top, without a duplicate reference.  Removed VIEW K at
5:1 shows the stub-root rounds in plan; Detail J at 10:1 shows
the end-rib step's round onto the plate.  Their native arrow tips must land
on the finite material arcs after the final rebuild, before export; correct
radius/MAX metadata alone is insufficient.  Sheet 1 runs at 1:2.

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_summing_lever.py sm-summing-lever
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any, Callable, Iterable

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    view_name,
)

from _check import check
import _config
from _com import _early_bound, _read_member
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions, import_cosmetic_threads
from _drawing_annotation_extent import boxes_clear
from _drawing_layout_audit import _DISPLAY_PRIMITIVES, annotation_display
from _layout_audit import _detail_circles, display_box, estimated_text_runs
from _drawing_dimensions import (
    set_basic_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import ViewEdge, ViewEdges, scan_view_edges
from _drawing_finish import add_surface_finish
from _drawing_gdt import add_datum_feature, add_feature_control_frame
from _drawing_hidden_sketches import (
    curate_view_dimensions as curate_hidden_dimensions,
    part_sketches_shown,
)
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_leader_note
from _drawing_leaders import dimension_segments, set_near_side_diameter
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sections import create_section_view
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _section_axis import position_section_caption
from _surface_finish import MACHINED, MACHINED_UM, surface_finish_by_key
import _telemetry
from magnifying_bracket_joint_layout import (
    DRILL_DEPTH,
    DRILL_DEPTH_DEVIATIONS,
    LEVER_HOLE_POINTS,
    RIB_DEPTH,
    TAP_DRILL_DIA,
    THREAD_DEPTH,
)
from sm_summing_lever_notes import (
    BACK_VIEW_LETTER,
    BOSS_Z_CALLOUT,
    BRACKET_TAP_CALLOUT_PROCESS,
    CYLINDER_REFERENCE_Z,
    DIMENSION_CALLOUTS_ABOVE,
    DIMENSION_CALLOUTS_BELOW,
    DRAWING_DIMENSIONS,
    FRONT_VIEW_LETTER,
    MIDDLE_RIB_PLAN_NOTE,
    REFERENCE_DIMENSIONS,
    SPRING_TAP_CALLOUT_PROCESS,
    STUB_ROOT_VIEW_LETTER,
)
from sm_summing_lever_spec import (
    ANCHOR_H,
    ANCHOR_R,
    ARC_R,
    CHANNEL_PITCH,
    COUNTER_HOLE_SPEC,
    GEOMETRIC_TOLERANCES_MM,
    HEX_DEPTH,
    HEX_H,
    HEX_W,
    HOLE_COUNT,
    HOLE_END_OFFSET_LAST,
    HOLE_SPEC,
    HOLE_X,
    HOLE_Z_FIRST,
    HOLE_Z_LAST,
    INSIDE_CORNER_R_TOL_TYPE,
    KNIFE_RIDGE_R,
    KNIFE_RIDGE_R_TOL_TYPE,
    KNIFE_RIDGE_TANGENT_XY,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    RIB_END_R,
    RIB_PLATE_REACH,
    RIDGE_ANGLE_DEG,
    STUB_ROOT_R,
    SURFACE_FINISHES,
    TIP_X,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_summing_lever"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
HOLE_DIA = blind_cut_dia_mm(HOLE_SPEC)
# Tap-drill diameter of the boss's counter-anchor tap; the rim points below
# pick its circular edge, and the native callout prints the thread itself.
COUNTER_R = blind_cut_dia_mm(COUNTER_HOLE_SPEC) / 2.0

SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 2.0)  # 1:2
_S = SHEET_SCALE[0] / SHEET_SCALE[1]  # sheet-mm per model-mm (0.5)

# Front (down -Z) and top (down -Y) share the same X extent: anchor eye
# (TIP_X - ANCHOR_R) on the left to the plate right edge (PLATE_W).
_BBOX_CX = (TIP_X - ANCHOR_R + PLATE_W) / 2.0

FRONT_CENTER = (0.225, 0.235)
TOP_CENTER = (0.225, 0.130)  # aligned plan below the front profile
ISO_CENTER = (0.350, 0.225)
# 40 mm below the sheet's top band, so the view and its callouts centre in
# the field above the title block (machinist review r10: at 0.190 they
# bunched along the top edge over an empty lower two-thirds).
BACK_CENTER = (0.225, 0.150)
SHEET_NAMES = ("Lever Geometry", "Bracket Receiver")
# Separate cut-face-only middle profile: its 35.75 is a buried theoretical
# intersection, not the end ribs' visible plate-side face. Keep the existing
# two sheets and full-size text. Native settled checks, not these allocations,
# decide whether the added plan/section fit beside K, VIEW F and the isometric.
MIDDLE_RIB_PLAN_CENTER = (0.160, 0.061)
MIDDLE_RIB_PLAN_NOTE_XY = (0.077, 0.030)
MIDDLE_RIB_SECTION_ORIGIN = (0.205, 0.235)
MIDDLE_RIB_CAPTION_XY = (0.160, 0.216)
MIDDLE_RIB_DIMENSION_XY = (0.223, 0.259)
MIDDLE_RIB_SECTION_REGION = (0.117, 0.205, 0.270, 0.270)
MIDDLE_RIB_PLAN_REGION = (0.075, 0.010, 0.208, 0.118)

# Detail D: the trunnion envelope at 4:1, in the open field left of the front
# profile.  The fence (6 model mm) holds the hexagon (5.13 half-height, 3.5
# sheet mm to spare) and none of the rib or web outline (the R15.24 rib arc,
# 7.6 sheet mm out).  Centred on the axis, the hexagon prints at
# DETAIL_CENTER, its fence 24 mm round it: at 7.5 model mm (30 sheet mm) the
# flank angle's text, which must stand outside the fence, pushed its arc up
# into the ridge pair's line (stack r4 render).  The centre stands low enough
# that the ridge pair's line clears that arc and the callout over it stays
# under the border, and far enough right that the vertex height's four lines
# fit between the border and the fence.  The label hangs below the width's
# dimension line, clear of section C-C's caption.  D, not A: A is the datum
# letter (machinist review r5: one letter named both).
DETAIL_LETTER = "D"
DETAIL_CENTER = (0.079, 0.208)
DETAIL_SCALE = (4.0, 1.0)
DETAIL_RADIUS_MM = 6.0
DETAIL_LABEL_XY = (0.079, 0.176)
# The parent circle's letter, below the rib arc, tied to the 6 mm fence by
# the leader style's leader: machinist review r6 read the bare fence, the
# letter outside the rib arc, as an unsized feature.  The letter's top
# prints ~0.2235, its leader dropping ~9 mm from the fence across the arc,
# between the rib-arc and cylinder leaders.
DETAIL_LETTER_OFFSET = (0.0, -0.016)
KNIFE_SKETCHES = ("KnifeEnvelopeReference",)
# Detail E: the knife-edge vertex at 10:1, cut from Detail D, carrying datum
# A and the ridge round's R0.1 MAX (code review C09: D's top now holds the
# ridge-to-side dimensions, which a leader from the round would cross).  The
# fence, 1.5 model mm round the theoretical sharp (6 mm in D), holds the
# round and both flanks; at 10:1 it prints 15 mm round RIDGE_DETAIL_CENTER in
# the free field under section C-C, the label below it.
RIDGE_DETAIL_LETTER = "E"
RIDGE_DETAIL_CENTER = (0.070, 0.075)
RIDGE_DETAIL_SCALE = (10.0, 1.0)
RIDGE_DETAIL_RADIUS_MM = 1.5
RIDGE_DETAIL_LABEL_XY = (0.070, 0.052)
# E's letter up-right of the vertex in D, outside E's fence, between the +X
# ridge-to-side dimension's extension lines and under its dimension line
# (the vertex height's upper extension line runs left from the vertex).
RIDGE_DETAIL_LETTER_OFFSET = (0.009, 0.0045)

# The two local inside-corner ceilings live on sheet 2, not in sheet 1's
# crowded trunnion detail.  K is a removed plan, turned to project from F
# (+X left), cropped around the -Z stub's root.  Its -X side root, the
# model fillet's dimensioned first edge, is on the right of this view.
STUB_ROOT_CENTER = (0.080, 0.225)
STUB_ROOT_SCALE = (5.0, 1.0)
STUB_ROOT_CROP_RADIUS_MM = 6.5
STUB_ROOT_ANCHOR_MM = (0.0, 0.0, -PLATE_L / 2.0)
# Aim well inside the upper-left material quarter of the right-hand root.
# V2's (112,248) put the tip only 0.184 mm below the 0.35 mm end-face ink.
# The measured shelf offset at (108,240) targets a 0.897 mm tip/face gap.
STUB_ROOT_KEEP = {"StubRootRadius": (0.108, 0.240)}
STUB_ROOT_NOTE_XY = (0.0605, 0.189)
# Centre and tangent points of that -X root quarter, in model mm.  K looks
# along Y, so the cross-section's Y station does not affect its projection.
STUB_ROOT_ARC_MM = (
    (-HEX_W / 2.0 - STUB_ROOT_R, 0.0, -PLATE_L / 2.0 - STUB_ROOT_R),
    (-HEX_W / 2.0, 0.0, -PLATE_L / 2.0 - STUB_ROOT_R),
    (-HEX_W / 2.0 - STUB_ROOT_R, 0.0, -PLATE_L / 2.0),
)

# J enlarges only the -Z end rib's step-foot onto the plate top; its
# 1.2-model-mm fence in F keeps the receiver taps outside the detail.
RIB_END_DETAIL_LETTER = "J"
RIB_END_DETAIL_CENTER = (0.060, 0.065)
RIB_END_DETAIL_SCALE = (10.0, 1.0)
RIB_END_DETAIL_RADIUS_MM = 1.2
RIB_END_DETAIL_LABEL_XY = (0.060, 0.045)
RIB_END_DETAIL_LETTER_OFFSET = (-0.0055, 0.0085)
# J's material quarter is down-right of its centre in the back projection.
# Put its native text to that side, clear of the detail and its caption.
RIB_END_KEEP = {"RibEndRadius": (0.114, 0.065)}
RIB_END_ARC_MM = (
    (RIB_PLATE_REACH + RIB_END_R, PLATE_T / 2.0 + RIB_END_R, -PLATE_L / 2.0),
    (RIB_PLATE_REACH, PLATE_T / 2.0 + RIB_END_R, -PLATE_L / 2.0),
    (RIB_PLATE_REACH + RIB_END_R, PLATE_T / 2.0, -PLATE_L / 2.0),
)

# Section C-C: the plate's own thickness.  Every end view shows the end ribs
# over the plate and the spring-anchor pad below its free edge, so no view
# shows the 5.08 edge-on; a partial cut across the plate alone, between two
# spring taps (mid-pitch, clear of both), shows it at 1:1 under Detail D's
# label.  The cut runs in the plan from just outboard of the cylinder
# (R12.70) past the free edge; the value stands beyond the cut's inboard end,
# the caption above.  The cut looks up the sheet (machinist review r7: looking
# down it, the pad printed at the section's left, mirrored from the plan), so
# its arrows and letters stand 14..20 mm over it: the cut sits five pitches
# down the column from its old station, at sheet y ~0.139, its letters at
# ~0.153..0.159, under the -Z end rib (0.168) and over the mid rib's 5.08
# (its text 0.1355..0.139 right of the free edge, 4.8 mm right of the cut's
# arrow); its outboard end runs 8.5 mm past the free
# edge so that letter (x 0.259..0.265) clears the hole column's centre marks.
PLATE_SECTION_Z = HOLE_Z_LAST - (HOLE_COUNT // 2 + 1.5) * CHANNEL_PITCH
PLATE_SECTION_X = (14.0, PLATE_W + 8.5)
PLATE_SECTION_SCALE = (1, 1)
PLATE_SECTION_CENTER = (0.075, 0.130)
PLATE_SECTION_CAPTION_XY = (0.075, 0.150)
# Model mm in the cutting plane: the anchor landed on PLATE_SECTION_CENTER
# (the plate's mid-plane midway along the cut), and the value's text, 6 mm
# past the cut's inboard end on that mid-plane.
_PLATE_SECTION_ANCHOR_MM = (sum(PLATE_SECTION_X) / 2.0, 0.0, PLATE_SECTION_Z)
PLATE_SECTION_TEXT_MM = {"PlateThickness": (PLATE_SECTION_X[0] - 6.0, 0.0, PLATE_SECTION_Z)}

# Section H-H: the outer bracket receiver tap (x 29.7, 14.75 from the free
# edge) cut along its axis, so the thread reads inside the -Z end rib's full
# height with the solid plate beyond the drill point (machinist review r16
# read the taps as centred in section C-C's bare 5.08 plate).  The cut is
# taken in VIEW G, the end profile, where the line crosses only the rib and
# plate: in the plan its arrows would cross VIEW F's arrow or the 20X frame's
# leader, and in VIEW F its letters would sit on the 14.75/28.45 extension
# lines.  The line runs from 11 mm under the mid-plane (3 mm below the rib)
# to 16 mm over it and looks +X (arrows pointing right, letters right of the
# line), so the upper letter stands over the 0.44 step's extension lines
# (sheet y 0.2363) and under 35.75's dimension line (0.2484), the lower one
# in open field; looking -X, both would print on the boss.  The removed
# section, cut face only at 4:1 (machinist review r17: at 1:1 the blind
# drill barely read), is cropped by a circle round the end rib and
# TAP_SECTION_PLATE_BEYOND of plate past the rib, a break line where the
# plate is cut off, in the free field under the plan's boss-axis 76.20
# (0.092) between Detail E (x 0.086) and that dimension's extension line
# (x 0.197), its caption below it over the bottom border (0.012).  Its
# content spans about x 0.121..0.169 and y 0.044..0.084.  GetDetailCircleInfo2
# answers the crop's unprinted profile with a label point on the sheet
# (farm r17b/r17c, as draw_fr_nameplate's section A-A), which the layout
# audit reports as an outside-border, unmatched detail circle.
TAP_SECTION_LETTER = "H"
TAP_SECTION_HOLE = max(LEVER_HOLE_POINTS, key=lambda point: point[0])
TAP_SECTION_LINE_Y = (-11.0, 16.0)
TAP_SECTION_SCALE = (4, 1)
TAP_SECTION_PLATE_BEYOND = 4.0
_TAP_SECTION_FAR_Z = TAP_SECTION_HOLE[2] + RIB_DEPTH + TAP_SECTION_PLATE_BEYOND
# Centre the crop relative to the receiver depth, not the superseded rib.
# Its radius leaves the plate faces 0.20 beyond the break while retaining
# both full-height rib end corners. These are view extents, not part sizes.
_TAP_SECTION_ANCHOR_MM = (
    TAP_SECTION_HOLE[0], 0.0, TAP_SECTION_HOLE[2] + RIB_DEPTH / 2.0 + 1.1
)
TAP_SECTION_CROP_RADIUS = math.hypot(
    _TAP_SECTION_FAR_Z + 0.20 - _TAP_SECTION_ANCHOR_MM[2], PLATE_T / 2.0
)
TAP_SECTION_CENTER = (0.140, 0.064)
TAP_SECTION_CAPTION_XY = (0.145, 0.037)
# A long-break line (thin, one Z at mid-thickness) across the cut-off plate,
# overrunning both faces (model z, y), draw_fr_nameplate's SECTION_BREAK.
_TAP_BREAK_OVERRUN = 0.8
TAP_SECTION_BREAK = (
    (_TAP_SECTION_FAR_Z, PLATE_T / 2.0 + _TAP_BREAK_OVERRUN),
    (_TAP_SECTION_FAR_Z, 0.8),
    (_TAP_SECTION_FAR_Z + 0.6, 0.3),
    (_TAP_SECTION_FAR_Z - 0.6, -0.3),
    (_TAP_SECTION_FAR_Z, -0.8),
    (_TAP_SECTION_FAR_Z, -PLATE_T / 2.0 - _TAP_BREAK_OVERRUN),
)
# SolidWorks prints a section's cosmetic thread dashed, as a hidden thread
# (machinist review r17, rule 9); draw_pn_pen_v_block's precedent imports
# H-H's thread and moves it onto a visible thin continuous layer of its own.
TAP_THREAD_LAYER = "TAP-THREAD-SECTION"
_COSMETIC_THREAD_ANNOTATION = 1  # swAnnotationType_e.swCosmeticThread

# The -Z end rib's ordinary depth is named by
# build_sm_summing_lever._receiver_model_bands, and the receiver stations by
# its hidden coordinate sketch, outside the marked-dimension contract.
DIMENSIONS_BY_FEATURE: dict[str, set[str]] = {
    **DRAWING_DIMENSIONS,
    "EdgeRibBack": {"RibDepth"},
    "ReceiverCoordinates": {"ReceiverX0", "ReceiverX1", "ReceiverY0"},
}


def _top_xy(mx: float, mz: float) -> tuple[float, float]:
    """Sheet (x, y) of a model (X, Z) point in the top plan view (1:2)."""
    return (
        TOP_CENTER[0] + (mx - _BBOX_CX) * _S / 1000.0,
        TOP_CENTER[1] + mz * _S / 1000.0,
    )


def _end_face_edge(edges: ViewEdges, *, x_mm: float) -> ViewEdge:
    """The one visible line of the +Z end face crossing model ``x_mm``.

    In the plan the +Z end (bottom of the view) shows a single line at
    z = PLATE_L/2: the edge rib's outer top edge, which covers the plate's own
    end edge out to the rib's vertical end face at RIB_PLATE_REACH (35.75,
    0.44 proud of the plate there); the plate's end edge shows only beyond it.
    The end rib's inboard flange edge sits 5.08 mm up the sheet and the rib's
    underside edge (y < 0) is hidden, so exactly one visible +y line at that z
    spans the requested x; anything else is a changed model and fails loud.
    """
    z_mm = PLATE_L / 2.0
    matches = [
        item
        for item in edges.lines
        if all(abs(point[2] - z_mm) < 1e-6 and point[1] > -1e-6 for point in item.line)
        and min(point[0] for point in item.line) - 1e-6 <= x_mm
        and x_mm <= max(point[0] for point in item.line) + 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"summing lever +Z end face: expected one visible line at z={z_mm:g} "
            f"spanning x={x_mm:g} in the {edges.label!r} scan, found "
            f"{[item.line for item in matches]}"
        )
    return matches[0]


def _knife_detail(adapter: Any, front: Any) -> Any:
    """A native 4:1 detail of the trunnion end in the front profile."""
    return _detail_view(
        adapter,
        front,
        centre_mm=(0.0, 0.0, 0.0),
        radius_m=DETAIL_RADIUS_MM * _S / 1000.0,
        at_xy=DETAIL_CENTER,
        scale=DETAIL_SCALE,
        letter=DETAIL_LETTER,
        label_xy=DETAIL_LABEL_XY,
        letter_offset=DETAIL_LETTER_OFFSET,
        label="knife detail",
    )


def _ridge_detail(adapter: Any, detail: Any) -> Any:
    """A native 10:1 detail of Detail D's knife-edge vertex (Detail E)."""
    return _detail_view(
        adapter,
        detail,
        centre_mm=(0.0, HEX_H / 2.0, PLATE_L / 2.0 + HEX_DEPTH),
        radius_m=RIDGE_DETAIL_RADIUS_MM * DETAIL_SCALE[0] / 1000.0,
        at_xy=RIDGE_DETAIL_CENTER,
        scale=RIDGE_DETAIL_SCALE,
        letter=RIDGE_DETAIL_LETTER,
        label_xy=RIDGE_DETAIL_LABEL_XY,
        letter_offset=RIDGE_DETAIL_LETTER_OFFSET,
        label="ridge detail",
    )


def _rib_end_detail(adapter: Any, back: Any) -> Any:
    """Native Detail J of the -Z rib's round onto the plate top, from F."""
    return _detail_view(
        adapter,
        back,
        centre_mm=(RIB_PLATE_REACH, PLATE_T / 2.0, -PLATE_L / 2.0),
        radius_m=RIB_END_DETAIL_RADIUS_MM / 1000.0,
        at_xy=RIB_END_DETAIL_CENTER,
        scale=RIB_END_DETAIL_SCALE,
        letter=RIB_END_DETAIL_LETTER,
        label_xy=RIB_END_DETAIL_LABEL_XY,
        letter_offset=RIB_END_DETAIL_LETTER_OFFSET,
        label="rib end detail",
    )


def _detail_view(
    adapter: Any,
    parent_view: Any,
    *,
    centre_mm: tuple[float, float, float],
    radius_m: float,
    at_xy: tuple[float, float],
    scale: tuple[float, float],
    letter: str,
    label_xy: tuple[float, float],
    letter_offset: tuple[float, float],
    label: str,
) -> Any:
    """A native detail of ``parent_view``: its fence, ``radius_m`` on the
    sheet, round model point ``centre_mm``; the view centred on ``at_xy``,
    its label at ``label_xy``, the parent circle's letter ``letter_offset``
    from the fence centre, each position read back."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError(f"failed to activate the {label}'s parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter, parent_view, _metres(centre_mm), label=f"{label} centre"
    )
    # The fence is drawn in sheet space on the parent.
    radius = radius_m
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    # Direct to the database: inferred, the centre snapped onto the
    # hexagon's left flat and the rim point onto its right flat (farm r4
    # 2026-10-16: a fence of radius HEX_W centred 3.8 model mm off the axis,
    # clipping the hexagon's right shoulders).
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        fence = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if fence is None:
        raise RuntimeError(f"failed to create the {label} fence")
    arc = _early_bound(fence, "ISketchArc")
    fence_centre = _early_bound(arc.GetCenterPoint2(), "ISketchPoint")
    placed_centre = (float(fence_centre.X), float(fence_centre.Y))
    if (
        math.dist(placed_centre, points[0][:2]) > 1e-9
        or abs(float(arc.GetRadius()) - math.dist(points[0][:2], points[1][:2])) > 1e-9
    ):
        raise RuntimeError(
            f"{label} fence moved off its authored circle: {placed_centre}"
        )
    draw.ClearSelection2(True)
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection.CreateSelectData()
    selection_data.View = parent_view
    if not _early_bound(fence, "ISketchSegment").Select4(False, selection_data):
        raise RuntimeError(f"failed to select the {label} fence")
    if int(selection.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError(f"{label} fence is not the only selection")
    detail = drawing.CreateDetailViewAt4(
        *at_xy,
        0.0,
        2,  # swDetViewLEADER: a leader joins the letter to the fence
        *scale,
        letter,
        1,  # swDetCircleCIRCLE
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError(f"failed to create the {label}")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in scale])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError(f"{label} has invalid bounds: {outline!r}")
    target = [
        position[axis] + at_xy[axis] - (outline[axis] + outline[axis + 2]) / 2.0
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to position the {label}")
    draw.EditRebuild3()
    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label} label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    label_xyz = (*label_xy, 0.0)
    if not annotation.SetPosition2(*label_xyz):
        raise RuntimeError(f"failed to position the {label} label")
    circles = tuple(_read_member(parent, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"expected one {label} circle, found {len(circles)}")
    circle = _early_bound(circles[0], "IDetailCircle")
    letter_xy = tuple(center[i] + letter_offset[i] for i in range(2))
    circle.SetLabelPosition(*letter_xy)  # VT_VOID: the read-back is the proof
    draw.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if math.dist(actual, label_xyz) > 1e-8:
        raise RuntimeError(f"{label} label position did not persist: {actual}")
    placed = tuple(float(value) for value in circle.GetLabelPosition())
    if len(placed) != 2 or math.dist(placed, letter_xy) > 1e-8:
        raise RuntimeError(f"{label} letter position did not persist: {placed}")
    return detail


def _attach_radial_leaders(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str], *, label: str
) -> None:
    """Remove radial arc-extension and centre tails.

    ``ArcExtensionLineOrOppositeSide`` defaults to True, which sweeps the
    R138.8 summation arc through the top view and trails the R15.24 rib leader
    across the front view; ``SolidLeader`` defaults to True on this template
    and rules the leader on to the arc centre, off the view for R138.8 (both
    seen on the 2026-10 summing-lever renders).  Both are bool properties, so
    each assignment is proven only by reading it back.
    They do not force a text ray outside a finite arc's sector onto material:
    K/J also read back their actual arrow tips against their fillet quarters.
    """
    wanted = set(names)
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArcExtensionLineOrOppositeSide = False
        if bool(display.ArcExtensionLineOrOppositeSide):
            raise RuntimeError(f"{label}: {name} leader still rides the arc extension")
        display.SolidLeader = False
        if bool(display.SolidLeader):
            raise RuntimeError(f"{label}: {name} leader still runs to the arc centre")
        seen.add(name)
    missing = sorted(wanted - seen)
    if missing:
        raise RuntimeError(f"{label}: radial dimensions missing: {missing}")


def _shorten_radii(
    adapter: Any, annotations: Iterable[Any], names: Iterable[str], *, label: str
) -> None:
    """Foreshorten each named radius: ``IDisplayDimension::ShortenedRadius``
    draws the jogged radius, its line stopping short of a centre beyond the
    view, so no bare line runs from the arc centre to the text (machinist
    review r8: the R138.85's line read as a loose line in the plan).  A bool
    put SolidWorks ignores still returns, so each flag is read back
    (draw_pd_latch_hook._shorten_radii)."""
    wanted = set(names)
    seen = set()
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in wanted:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = True
        if not bool(display.ShortenedRadius):
            raise RuntimeError(f"{label}: {name} did not keep its shortened radius")
        seen.add(name)
    missing = sorted(wanted - seen)
    if missing:
        raise RuntimeError(f"{label}: radii to shorten missing: {missing}")


def _apply_callouts(adapter: Any, annotations: list[Any], *, label: str) -> None:
    """Write the notes module's callout text onto the dimensions this sheet
    kept, above or below the value."""
    present = {dimension_name(adapter, annotation) for annotation in annotations}
    for location, callouts in (
        ("above", DIMENSION_CALLOUTS_ABOVE),
        ("below", DIMENSION_CALLOUTS_BELOW),
    ):
        wanted = {name: text for name, text in callouts.items() if name in present}
        set_dimension_callouts(adapter, annotations, wanted, location=location)
    _telemetry.info(f"{label}: callouts on {sorted(present)}")


def _add_view_arrow(
    adapter: Any,
    top: Any,
    letter: str,
    arrow: tuple[tuple[float, float], tuple[float, float]],
) -> None:
    """A square lettered viewing arrow onto the face a removed view looks at."""
    text_xy, tip_xy = arrow
    label = f"view {letter} viewing arrow"
    note = add_leader_note(
        adapter,
        letter,
        text_xy=text_xy,
        attach_xy=tip_xy,
        view=top,
        label=label,
    )
    # add_note leaves text at the document height; size the letter here and
    # prove the leader tip did not move with it.
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    text_format = annotation.GetTextFormat(0)
    if text_format is None:
        raise RuntimeError(f"{label} note has no text format")
    text_format.CharHeight = VIEW_LETTER_HEIGHT
    if not annotation.SetTextFormat(0, False, text_format):
        raise RuntimeError(f"failed to size the {label} letter")
    rebuild_drawing(adapter, label=f"{label} letter")
    points = list(annotation.GetLeaderPointsAtIndex(0) or ())
    if len(points) < 6 or math.dist((points[-3], points[-2]), tip_xy) > 0.001:
        raise RuntimeError(f"{label} tip moved when its letter was sized")
    # The leader leaves the letter's nearer side, whose x is the glyph's
    # width: slide the letter by any miss so the arrow stands square.
    miss = tip_xy[0] - points[0]
    if abs(miss) > VIEW_ARROW_SQUARE_TOL:
        x, y, z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x + miss, y, z):
            raise RuntimeError(f"failed to square the {label}")
        rebuild_drawing(adapter, label=f"square {label}")
        points = list(annotation.GetLeaderPointsAtIndex(0) or ())
        if (
            len(points) < 6
            or math.dist((points[-3], points[-2]), tip_xy) > 0.001
            or abs(tip_xy[0] - points[0]) > VIEW_ARROW_SQUARE_TOL
        ):
            raise RuntimeError(f"{label} did not square: leader {points}")
    _telemetry.info(
        f"{label}: leader {points[0]:.5f},{points[1]:.5f} -> "
        f"{points[-3]:.5f},{points[-2]:.5f} (square when the x agree)"
    )


def _assert_native_max_radius(
    adapter: Any,
    annotations: list[Any],
    *,
    name: str,
    radius_mm: float,
    tol_type: int,
) -> None:
    """Read an imported fillet's native radial value and MAX tolerance."""
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(found) != 1:
        raise RuntimeError(f"expected one {name} on the sheet, found {len(found)}")
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError(f"{name} is not a radial dimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != tol_type:
        raise RuntimeError(f"{name} lost its native MAX type: {int(tolerance.Type)}")
    if not math.isclose(
        float(dimension.SystemValue), radius_mm / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError(f"{name} does not measure its modelled radius")
    _telemetry.info(
        f"{name}: native radius {float(dimension.SystemValue)!r} m, "
        f"tolerance type {int(tolerance.Type)}, text {display.GetText(1)!r}"
    )


def _assert_radius_arrow_lands(
    adapter: Any,
    view: Any,
    annotations: list[Any],
    *,
    name: str,
    arc_mm: tuple[tuple[float, float, float], ...],
) -> None:
    """Require the rebuilt native arrow on the material quarter, not its circle
    extension.  Uses the output fixture's native arrow-head readback pattern."""
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == name
    ]
    if len(found) != 1:
        raise RuntimeError(f"expected one {name} for its arrow landing, found {len(found)}")
    annotation = _early_bound(found[0], "IAnnotation")
    if annotation.IsDangling():
        raise RuntimeError(f"{name}: native radius is dangling")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    raw = display.GetDisplayData()
    if raw is None:
        raise RuntimeError(f"{name}: native radius has no rebuilt display data")
    data = _early_bound(raw, "IDisplayData")
    if int(data.GetArrowHeadCount()) != 1:
        raise RuntimeError(f"{name}: expected exactly one native radial arrow")
    arrow = tuple(float(value) for value in data.GetArrowHeadAtIndex2(0) or ())
    if len(arrow) != 12 or not all(math.isfinite(value) for value in arrow):
        raise RuntimeError(f"{name}: native arrow-head coordinates are incomplete")
    tip = arrow[:2]
    centre, start, end = model_points_in_view(
        adapter,
        view,
        [_metres(point) for point in arc_mm],
        label=f"{name} material quarter",
        names=("centre", "first tangent", "second tangent"),
    )
    axes = [
        tuple(point[i] - centre[i] for i in (0, 1))
        for point in (start, end)
    ]
    radius = math.dist(centre, start)
    if (
        not all(math.isfinite(value) for point in (centre, start, end) for value in point)
        or radius <= 0.0
        or not math.isclose(math.dist(centre, end), radius, rel_tol=1e-6, abs_tol=1e-9)
        or abs(sum(a * b for a, b in zip(*axes))) > 1e-6 * radius**2
    ):
        raise RuntimeError(f"{name}: projected fillet quarter is invalid")
    # Native display ink has the same 0.4-sheet-mm allowance as the output
    # fixture's material-arc proof.  Checking the quadrant as well as radius
    # rejects an arrow on the invisible continuation of the same circle.
    tolerance = 0.0004
    delta = tuple(tip[i] - centre[i] for i in (0, 1))
    if (
        abs(math.dist(tip, centre) - radius) > tolerance
        or any(
            sum(a * b for a, b in zip(delta, axis)) / radius < -tolerance
            for axis in axes
        )
    ):
        raise RuntimeError(
            f"{name}: native arrow does not land on its visible fillet arc: "
            f"tip={tip}, centre={centre}, tangents={(start, end)}, radius={radius:g}"
        )
    _telemetry.info(f"{name}: native arrow lands on its material quarter at {tip}")


# Datum A's box over the vertex in Detail E, inside E's 15 mm fence: the
# request is the box's foot, the box 7 mm tall (at 0.008 its top sat on the
# fence, r14).
RIDGE_DATUM_RISE = 0.006


def _ridge_datum(adapter: Any, ridge_detail: Any) -> Any:
    """Datum A on the knife-edge ridge itself, seen end-on in Detail E: the
    tag stands on the R0.1 round's arc at the vertex.  In the plan, A hung
    on the -Z ridge's tangent line down the stub's middle, which machinist
    review r9 read as a flat face, leaving no basic from A to the 20 holes;
    end-on it can only be the ridge line, the knife-edge pivot axis that the
    39.85 basic and the web arcs' "AXIS A" both name."""
    z_mm = PLATE_L / 2.0 + HEX_DEPTH
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    centre_y = HEX_H / 2.0 - KNIFE_RIDGE_R / math.sin(half)
    edges = scan_view_edges(ridge_detail, label="ridge detail datum")
    ridge_round = edges.circle_at(
        (0.0, centre_y, z_mm),
        KNIFE_RIDGE_R,
        axis=(0.0, 0.0, 1.0),
        label="+Z knife-edge ridge round",
    )
    crest, vertex = model_points_in_view(
        adapter,
        ridge_detail,
        [
            _metres((0.0, centre_y + KNIFE_RIDGE_R, z_mm)),
            _metres((0.0, HEX_H / 2.0, z_mm)),
        ],
        label="knife ridge datum",
        names=("crest", "vertex"),
    )
    return add_datum_feature(
        adapter,
        ridge_detail,
        edge_entity=ridge_round.edge,
        leader_attach_xy=crest,
        symbol_xy=(vertex[0], vertex[1] + RIDGE_DATUM_RISE),
        datum="A",
        label="knife-edge pivot axis",
    )


# The ridge centreline runs the +Z stub's length and 2 model mm past its
# outboard face: 1 sheet mm, ending 1.5 mm above 44.45's dimension line.
RIDGE_AXIS_OVERRUN_MM = 2.0


def _ridge_centerline(adapter: Any, top: Any) -> Any:
    """An owned centreline on the +Z knife ridge's theoretical sharp in the
    plan (draw_sm_knife_mount._add_section_axes's idiom): the round leaves
    no edge on the ridge itself, and rule 16 dimensions to the sharp."""
    return _owned_centerline(
        adapter,
        top,
        tuple(
            (0.0, HEX_H / 2.0, z)
            for z in (PLATE_L / 2.0, PLATE_L / 2.0 + HEX_DEPTH + RIDGE_AXIS_OVERRUN_MM)
        ),
        label="ridge centreline",
    )


def _owned_centerline(
    adapter: Any,
    view: Any,
    ends_mm: tuple[tuple[float, float, float], tuple[float, float, float]],
    *,
    label: str,
) -> Any:
    """A black centreline in ``view``'s sketch between two part-mm points.

    Its ends are model points projected to the sheet and taken into the
    view's sketch frame, placed direct to the database (an inferred end snaps
    onto nearby tangent lines 0.03 sheet mm away) and read back.
    Returns the ``ISketchSegment`` for a dimension to pick.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate the view for its {label}")
    draw.ClearSelection2(True)
    ends = model_points_in_view(
        adapter,
        view,
        [_metres(point) for point in ends_mm],
        label=f"{label} end",
        names=("start", "end"),
    )
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in ends:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateCenterLine(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if segment is None:
        raise RuntimeError(f"failed to create the {label}")
    line = _early_bound(segment, "ISketchLine")
    for expected, accessor in zip(points, ("GetStartPoint2", "GetEndPoint2")):
        placed = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
        actual = [float(adapter._get_attr_or_call(placed, axis)) for axis in "XYZ"]
        drift = max(abs(a - b) for a, b in zip(actual, expected))
        if drift > 1e-9:
            raise RuntimeError(
                f"{label} {accessor[3:-6].lower()} point sits "
                f"{drift * 1000.0:.4g} mm from where it was authored"
            )
    segment = _early_bound(segment, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError(f"{label} color did not persist")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=f"summing lever {label}")
    return segment


def _metres(point_mm: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(value / 1000.0 for value in point_mm)


def _plate_section(adapter: Any, top: Any) -> Callable[[], None]:
    """Section C-C across the plate (PLATE_SECTION_* above): cut face only,
    looking up the sheet so the free edge and its pad print on the right as
    in the plan, turned +Y up and landed on PLATE_SECTION_CENTER
    (draw_pd_platen's ``_orient_section``/``_centre_section``), carrying the
    plate thickness."""
    line = model_points_in_view(
        adapter,
        top,
        [_metres((x, PLATE_T / 2.0, PLATE_SECTION_Z)) for x in PLATE_SECTION_X],
        label="section C-C line",
        names=("inboard", "outboard"),
    )
    section = create_section_view(
        adapter,
        top,
        line_start=line[0],
        line_end=line[1],
        view_xy=PLATE_SECTION_CENTER,
        section_label="C",
        scale=PLATE_SECTION_SCALE,
        partial=True,
        label="plate thickness section",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section C-C cut face only")
    if not cut.GetDisplayOnlySurfaceCut():
        raise RuntimeError("section C-C retained geometry beyond the cutting plane")
    _hidden_lines_removed_without_greyed_pass(native)
    anchor = _metres(_PLATE_SECTION_ANCHOR_MM)
    above = _metres(
        (_PLATE_SECTION_ANCHOR_MM[0], 1.0, _PLATE_SECTION_ANCHOR_MM[2])
    )
    free_edge = _metres((PLATE_W, 0.0, PLATE_SECTION_Z))

    def turn_up(stage: str) -> None:
        for attempt in range(3):
            origin = model_point_in_view(adapter, native, anchor, label="C-C anchor")
            up = model_point_in_view(adapter, native, above, label="C-C +Y")
            dx, dy = up[0] - origin[0], up[1] - origin[1]
            if dy > 0.0 and abs(dx) <= 1e-7:
                return
            native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
            rebuild_drawing(
                adapter, label=f"section C-C turned ({stage}), pass {attempt}"
            )
        raise RuntimeError(f"section C-C does not run +Y up: ({dx:g}, {dy:g})")

    def free_edge_dx() -> float:
        origin = model_point_in_view(adapter, native, anchor, label="C-C anchor")
        edge = model_point_in_view(adapter, native, free_edge, label="C-C free edge")
        return edge[0] - origin[0]

    turn_up("as cut")
    if free_edge_dx() < 0.0:
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section C-C looks up the sheet")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section C-C cut direction did not persist")
        turn_up("reversed")
    if not free_edge_dx() > 0.0:
        raise RuntimeError("section C-C still prints the free edge on the left")
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"C-C centre, pass {attempt}"
        )
        if math.dist(projected, PLATE_SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + PLATE_SECTION_CENTER[axis] - projected[axis]
            for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre section C-C")
        rebuild_drawing(adapter, label=f"section C-C re-centred, pass {attempt}")
    else:
        raise RuntimeError(
            f"section C-C centre stands at {projected}, not {PLATE_SECTION_CENTER}"
        )
    keep = {
        name: model_point_in_view(
            adapter, native, _metres(point), label=f"C-C {name} text"
        )
        for name, point in PLATE_SECTION_TEXT_MM.items()
    }
    annotations = curate_view_dimensions(
        adapter,
        native,
        keep=keep,
        view_label="section C-C",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    position_section_caption(
        adapter, native, PLATE_SECTION_CAPTION_XY, label="plate section C-C"
    )
    return _style_plate_thickness_witnesses(adapter, native, annotations)


def _middle_rib_source_tangents(
    adapter: Any, view: Any,
) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...]:
    """Visible plate joins and buried vertex, read from the actual native sketch.

    These are sampled drawing-construction endpoints, not automatically
    model-linked lines. The settled callback proves coincidence for the current
    build. Returned points are part millimetres in the Front-plane sketch.
    """
    if view.ReferencedDocument is None:
        raise RuntimeError("missing paired native middle-rib tangents: no source part")
    part = _early_bound(view.ReferencedDocument, "IPartDoc")
    raw = part.FeatureByName("MiddleRibProfile")
    if raw is None:
        raise RuntimeError("missing paired native middle-rib tangents: no profile")
    raw_sketch = _early_bound(raw, "IFeature").GetSpecificFeature2()
    if raw_sketch is None:
        raise RuntimeError("missing paired native middle-rib tangents: no native sketch")
    sketch = _early_bound(raw_sketch, "ISketch")
    expected = (RIB_PLATE_REACH / 1000.0, 0.0, 0.0)
    tangents = []
    for raw_segment in sketch.GetSketchSegments() or ():
        segment = _early_bound(raw_segment, "ISketchSegment")
        if int(segment.GetType()) != 0:  # swSketchLINE
            continue
        line = _early_bound(segment, "ISketchLine")
        points = []
        for accessor in ("GetStartPoint2", "GetEndPoint2"):
            point = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
            xyz = tuple(float(adapter._get_attr_or_call(point, axis)) for axis in "XYZ")
            if not all(math.isfinite(value) for value in xyz):
                raise RuntimeError("invalid paired native middle-rib tangents")
            points.append(xyz)
        for vertex, other in (points, reversed(points)):
            if math.dist(vertex, expected) > 1e-9:
                continue
            if (
                not 0.0 < other[0] < vertex[0]
                or abs(other[1]) <= PLATE_T / 2000.0
                or abs(other[2]) > 1e-9
            ):
                raise RuntimeError("invalid paired native middle-rib tangents")
            fraction = (PLATE_T / 2000.0) / abs(other[1])
            join = tuple(
                (vertex[axis] + fraction * (other[axis] - vertex[axis])) * 1000.0
                for axis in range(3)
            )
            tangents.append((join, tuple(value * 1000.0 for value in vertex)))
    if len(tangents) != 2 or sorted(math.copysign(1.0, pair[0][1]) for pair in tangents) != [-1.0, 1.0]:
        raise RuntimeError("missing paired native middle-rib tangents")
    return tuple(sorted(tangents, key=lambda pair: -pair[0][1]))


def _require_middle_rib_layout(
    new_ink: dict[str, tuple[tuple[float, ...], tuple[float, ...]]],
    neighbor_ink: dict[str, tuple[float, ...]],
) -> None:
    """Contain every read-back primitive and keep foreign ink 2 mm away."""
    for label, box in neighbor_ink.items():
        if (
            len(box) != 4 or not all(math.isfinite(value) for value in box)
            or box[0] > box[2] or box[1] > box[3]
        ):
            raise RuntimeError(f"{label}: invalid foreign middle-rib ink: {box}")
    for label, (box, region) in new_ink.items():
        if (
            len(box) != 4 or len(region) != 4
            or not all(math.isfinite(value) for value in (*box, *region))
            or box[0] > box[2] or box[1] > box[3]
            or box[0] < region[0] or box[1] < region[1]
            or box[2] > region[2] or box[3] > region[3]
        ):
            raise RuntimeError(f"{label}: outside allocated middle-rib region: {box}")
        for other, other_box in neighbor_ink.items():
            if not boxes_clear(box, other_box, gap=0.002):
                raise RuntimeError(f"{label} crowds {other}: {box}, {other_box}")


def _middle_rib_annotation_box(
    adapter: Any, annotation: Any, *, label: str, text_only: bool = False,
    required_dimension: bool = False, required_text: bool = False,
    expected_text: str | None = None,
) -> tuple[float, ...] | None:
    """Conservatively union native note extents with measured display ink."""
    annotation = _early_bound(annotation, "IAnnotation")
    visible, kind = annotation.Visible, annotation.GetType()
    if type(kind) is not int or kind < 0:
        raise RuntimeError(f"{label}: unreadable native annotation type {kind!r}")
    if type(visible) is not int or visible not in (0, 1, 2, 3):
        raise RuntimeError(f"{label}: unreadable native annotation visibility {visible!r}")
    if required_dimension or required_text:
        if visible != 1 or annotation.IsDangling() is not False:
            raise RuntimeError(f"{label}: required native ink is hidden or dangling")
    if visible in (2, 3):
        return None
    if required_dimension and (type(kind) is not int or kind != 4):
        raise RuntimeError(f"{label}: required native ink is not a display dimension")
    display, errors = annotation_display(adapter, annotation)
    if errors:
        raise RuntimeError(f"{label}: native ink read refused: {errors}")
    # The shared collector records refusals, but an empty native row can be
    # filtered out. Match the native counts before accepting its geometry.
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    lengths = {"lines": 10, "arcs": 17, "arrows": 12, "triangles": 11}
    for key, member, _getters in (*_DISPLAY_PRIMITIVES, ("texts", "GetTextCount", ())):
        count = getattr(data, member)()
        rows = display.get(key, ())
        if type(count) is not int or count < 0 or len(rows) != count:
            raise RuntimeError(f"{label}: unreadable native {member} rows/count")
        if key == "texts":
            continue
        if key == "ellipses" and count:
            raise RuntimeError(f"{label}: native ellipse ink cannot be bounded by the display reader")
        for row in rows:
            if (
                not all(math.isfinite(value) for value in row)
                or (key in lengths and len(row) != lengths[key])
            ):
                raise RuntimeError(f"{label}: invalid native {key} ink {row!r}")
            if key in ("polylines", "polygons"):
                header, count_index = (7, 6) if key == "polylines" else (5, 4)
                if (
                    len(row) < header or row[count_index] < 0
                    or row[count_index] != int(row[count_index])
                    or len(row) != header + 3 * int(row[count_index])
                    or (key == "polylines" and (row[0] != 0.0 or row[1] != 0.0))
                ):
                    raise RuntimeError(f"{label}: unreadable native {key} ink {row!r}")
            if display_box({key: [row]}) is None:
                raise RuntimeError(f"{label}: unreadable native {key} stroke footprint")
    # Refuse unusable text instead of letting display_box silently drop a run.
    for text in display.get("texts", ()):
        if (
            type(text.get("t")) is not str
            or len(text.get("pos", ())) != 3
            or not all(math.isfinite(value) for value in text["pos"])
            or not math.isfinite(text.get("h", math.nan)) or text["h"] <= 0.0
            or not math.isfinite(text.get("ang", math.nan))
        ):
            raise RuntimeError(f"{label}: invalid native text ink {text!r}")
    if required_dimension or required_text:
        if not any(text["t"].strip() for text in display.get("texts", ())):
            raise RuntimeError(f"{label}: required native ink has no readable text")
    if expected_text is not None:
        drawn = "".join(text["t"] for text in display.get("texts", ()))
        if "".join(expected_text.upper().split()) not in "".join(drawn.upper().split()):
            raise RuntimeError(f"{label}: required native ink does not draw {expected_text!r}")
    if required_dimension and not any(
        len(line) == 10 and all(math.isfinite(value) for value in line)
        and (line[4], line[5]) != (line[7], line[8])
        for line in display.get("lines", ())
    ):
        raise RuntimeError(f"{label}: required native dimension has no drawn dimension strokes")
    if kind == 6:
        extent = tuple(float(value) for value in _early_bound(
            annotation.GetSpecificAnnotation(), "INote"
        ).GetExtent())
        if (
            len(extent) != 6 or not all(math.isfinite(value) for value in extent)
            or extent[0] >= extent[3] or extent[1] >= extent[4]
        ):
            raise RuntimeError(f"{label}: invalid native note extent {extent}")
        text_box = extent[0], extent[1], extent[3], extent[4]
        # Conservatively union the native extent and display ink. The extent
        # can already include leaders; do not replace it with estimated text.
        strokes = {key: rows for key, rows in display.items() if key != "texts"}
        box = None if text_only else display_box(strokes, advance=0.8)
        if box is None:
            return text_box
        return (
            min(text_box[0], box.xmin), min(text_box[1], box.ymin),
            max(text_box[2], box.xmax), max(text_box[3], box.ymax),
        )
    if text_only:
        display = {"texts": display.get("texts", ())}
    box = display_box(display, advance=0.8)
    estimates = estimated_text_runs(display)
    if estimates:
        _telemetry.info(
            f"{label}: {estimates} unreported glyph widths conservatively estimated; "
            "native strokes/positions/heights measured; PDF ink review still required"
        )
    if box is None and not text_only:
        raise RuntimeError(f"{label}: visible native annotation has no readable ink")
    return None if box is None else (box.xmin, box.ymin, box.xmax, box.ymax)


def _middle_rib_view_annotations(view: Any, *, label: str) -> tuple[Any, ...]:
    """Read the counted native annotation census without losing unknown ink."""
    count = view.GetAnnotationCount()
    raw = view.GetAnnotations()
    if (
        type(count) is not int or count < 0
        or (raw is not None and type(raw) not in (tuple, list))
        or len(raw or ()) != count
    ):
        raise RuntimeError(f"{label}: unreadable native annotation census {count!r}, {raw!r}")
    return tuple(_early_bound(item, "IAnnotation") for item in (raw or ()))


def _middle_rib_detail_ink(view: Any, *, label: str) -> dict[str, tuple[float, ...]]:
    """Native parent fences/labels, which GetOutline/GetAnnotations do not bound."""
    native_name = view_type = cropped = metadata = raw_circles = None
    try:
        native_name = view.Name
        view_type = view.Type
        cropped = view.IsCropped()
        metadata = view.GetDetailCircleCount2()
        raw_circles = view.GetDetailCircles()
    finally:
        circle_count = len(raw_circles) if type(raw_circles) in (tuple, list) else None
        _telemetry.debug(
            f"{label}: native detail census view={native_name!r}, Type={view_type!r}, "
            f"IsCropped={cropped!r}, GetDetailCircleCount2={metadata!r}, "
            f"len(GetDetailCircles)={circle_count!r}"
        )
    if (
        type(metadata) is not tuple or len(metadata) != 2
        or any(type(value) is not int or value < 0 for value in metadata)
    ):
        raise RuntimeError(f"{label}: invalid native detail-circle count/size {metadata!r}")
    count, size = metadata
    if raw_circles is not None and type(raw_circles) not in (tuple, list):
        raise RuntimeError(f"{label}: unreadable native detail-circle objects")
    circles = tuple(_early_bound(raw, "IDetailCircle") for raw in (raw_circles or ()))
    if not circles:
        # A detail view's crop can appear in GetDetailCircleInfo2 without being
        # a parent source circle. Only actual IDetailCircle objects are sources.
        if count and view.Type != 3:  # swDrawingDetailView
            raise RuntimeError(f"{label}: missing native parent detail-circle objects")
        return {}
    info = view.GetDetailCircleInfo2()
    labels = view.GetDetailCircleStrings()
    if (
        len(circles) != count
        or type(info) not in (tuple, list) or len(info) != size or not info
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in info)
        or info[0] != count
        or type(labels) not in (tuple, list) or len(labels) != count
        or any(type(text) is not str or not text.strip() for text in labels)
        or len(set(labels)) != count
        or sorted(circle.GetLabel() for circle in circles) != sorted(labels)
    ):
        raise RuntimeError(f"{label}: unreadable native detail-circle geometry/labels")
    # Validate the complete flat records before the shared decoder's tolerant
    # truncation handling; no missing fence, label or arrow may disappear.
    offset = 1
    for _number in range(count):
        if offset + 16 > size:
            raise RuntimeError(f"{label}: truncated native detail-circle geometry")
        arrows = info[offset + 15]
        if arrows < 0 or arrows != int(arrows) or offset + 16 + 9 * int(arrows) > size:
            raise RuntimeError(f"{label}: truncated native detail-circle arrows")
        offset += 16 + 9 * int(arrows)
    if any(value != 0.0 for value in info[offset:]):
        raise RuntimeError(f"{label}: nonzero unused native detail-circle geometry")
    ink = {}
    decoded = _detail_circles(info)
    if len(decoded) != count:
        raise RuntimeError(f"{label}: incomplete native detail-circle geometry")
    offset = 1
    for text, (center, start, end, text_pt, (height, _)) in zip(labels, decoded, strict=True):
        arrows = int(info[offset + 15])
        cx, cy = center
        radius = math.dist(center, start)
        if (
            radius <= 0.0 or height <= 0.0
            or not math.isclose(radius, math.dist(center, end), abs_tol=1e-7)
        ):
            raise RuntimeError(f"{label}: invalid native detail-circle radius/text height")
        # A complete circular envelope conservatively includes the source arc.
        # textPt is upper-left, as in the shared detail-circle audit reader.
        x, y = text_pt
        box = [
            min(cx - radius, x), min(cy - radius, y - height),
            max(cx + radius, x + 0.8 * height * len(text)), max(cy + radius, y),
        ]
        offset += 16
        for _index in range(int(arrows)):
            arrow = info[offset:offset + 9]
            if min(arrow[6:8]) <= 0.0 or math.hypot(arrow[3], arrow[4]) == 0.0:
                raise RuntimeError(f"{label}: invalid native detail-circle arrow")
            arrow_box = display_box({"arrows": [(*arrow, 0.0, 0.0, 1.0)]})
            if arrow_box is None:
                raise RuntimeError(f"{label}: unreadable native detail-circle arrow ink")
            box = [
                min(box[0], arrow_box.xmin), min(box[1], arrow_box.ymin),
                max(box[2], arrow_box.xmax), max(box[3], arrow_box.ymax),
            ]
            offset += 9
        ink[f"{label} detail {text}"] = tuple(box)
        _telemetry.info(
            f"{label} detail {text}: native fence/arrow/label position and height measured; "
            "unreported label width conservatively estimated; PDF ink review still required"
        )
    return ink


def _middle_rib_foreign_ink(
    adapter: Any, *, neighboring_views: tuple[Any, ...], sheet_view: Any,
    plan_note_annotation: Any,
) -> dict[str, tuple[float, ...]]:
    """Assemble foreign view bodies, captions, annotations and source details."""
    neighbors = {}
    for index, raw_view in enumerate((*neighboring_views, sheet_view)):
        view = _early_bound(raw_view, "IView")
        name = f"existing receiver view {index}"
        if index < len(neighboring_views):
            view.UpdateViewDisplayGeometry()
            neighbors[f"{name} outline"] = tuple(float(value) for value in view.GetOutline())
            neighbors.update(_middle_rib_detail_ink(view, label=name))
        annotations = list(_middle_rib_view_annotations(view, label=name))
        if index < len(neighboring_views):
            raw_notes = view.GetNotes()
            if raw_notes is not None and type(raw_notes) not in (tuple, list):
                raise RuntimeError(f"{name}: unreadable native view captions")
            if view.Type == 3 and len(raw_notes or ()) != 1:
                raise RuntimeError(f"{name}: missing native detail caption")
            for raw_note in raw_notes or ():
                note = _early_bound(raw_note, "INote")
                annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
                if not any(adapter.swApp.IsSame(annotation, other) == 1 for other in annotations):
                    annotations.append(annotation)
        for annotation_index, annotation in enumerate(annotations):
            if int(annotation.OwnerType) == 2 or adapter.swApp.IsSame(annotation, plan_note_annotation) == 1:
                continue
            box = _middle_rib_annotation_box(adapter, annotation, label=name)
            if box is not None:
                neighbors[f"{name} annotation {annotation_index}"] = box
    return neighbors


def _middle_rib_cut_ink(plan: Any) -> dict[str, tuple[float, ...]]:
    """The actual L-L line, both arrow envelopes and both letter envelopes."""
    sections = tuple(plan.GetSectionLines() or ())
    if len(sections) != 1 or str(_early_bound(sections[0], "IDrSection").GetLabel()) != "L":
        raise RuntimeError("middle-rib plan does not own its single L-L cutting line")
    values = tuple(float(value) for value in plan.GetSectionLineInfo2() or ())
    if len(values) < 3 or not all(math.isfinite(value) for value in values) or values[0] != 1:
        raise RuntimeError("invalid native middle-rib section-line ink")
    count, offset = int(values[2]), 3
    if count < 1 or values[2] != count or len(values) != 3 + count * 7 + 25:
        raise RuntimeError("invalid native middle-rib section-line ink length")
    boxes = {}
    for index in range(count):
        segment = values[offset:offset + 7]
        boxes[f"L-L cut segment {index}"] = (
            min(segment[1], segment[4]), min(segment[2], segment[5]),
            max(segment[1], segment[4]), max(segment[2], segment[5]),
        )
        offset += 7
    for index in range(2):
        arrow = values[offset:offset + 9]
        padding = max(arrow[6], arrow[7])
        if padding <= 0.0:
            raise RuntimeError("middle-rib cutting arrow has no native width/height")
        boxes[f"L-L cut arrow {index}"] = (
            min(arrow[0], arrow[3]) - padding, min(arrow[1], arrow[4]) - padding,
            max(arrow[0], arrow[3]) + padding, max(arrow[1], arrow[4]) + padding,
        )
        offset += 9
    height = values[offset + 6]
    if height <= 0.0:
        raise RuntimeError("middle-rib cutting letter has no native height")
    for index in range(2):
        x, y = values[offset + index * 3:offset + index * 3 + 2]
        # GetTextInfo's point is upper-left; one full height bounds a single L.
        boxes[f"L-L cut letter {index}"] = (x, y - height, x + height, y)
    return boxes


def _middle_rib_section(
    adapter: Any, *, neighboring_views: tuple[Any, ...],
) -> tuple[Any, Any, Callable[[], None]]:
    """Native cut-only L-L and its small associated plan, on receiver sheet 2."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    plan = _early_bound(place_view(
        adapter, str(SOURCE), "*Top", *MIDDLE_RIB_PLAN_CENTER, scale=(1, 2)
    ), "IView")
    set_hidden_lines_removed(adapter, plan)
    _set_tangent_edges(plan, visible=False)
    line = model_points_in_view(
        adapter, plan,
        [_metres((x, 0.0, 0.0)) for x in (TIP_X - ANCHOR_R - 8.0, PLATE_W + 8.0)],
        label="middle-rib L-L cutting line", names=("boss end", "plate end"),
    )
    section = _early_bound(create_section_view(
        adapter, plan, line_start=line[0], line_end=line[1],
        view_xy=MIDDLE_RIB_SECTION_ORIGIN, section_label="L", scale=(1, 1),
        partial=True, label="middle-rib theoretical intersection",
    ), "IView")
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="middle-rib cut face only")
    if not cut.GetDisplayOnlySurfaceCut():
        raise RuntimeError("middle-rib L-L includes end ribs beyond its cutting plane")
    _hidden_lines_removed_without_greyed_pass(section)
    origin_mm = (0.0, 0.0, 0.0)
    for attempt in range(3):
        origin, up = model_points_in_view(
            adapter, section, [_metres(origin_mm), _metres((0.0, 1.0, 0.0))],
            label="middle-rib orientation", names=("origin", "+Y"),
        )
        dx, dy = up[0] - origin[0], up[1] - origin[1]
        if dy > 0.0 and abs(dx) <= 1e-7:
            break
        section.Angle = float(section.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
        rebuild_drawing(adapter, label=f"middle-rib turned +Y up, pass {attempt}")
    else:
        raise RuntimeError("middle-rib L-L does not run +Y up")
    origin, right = model_points_in_view(
        adapter, section, [_metres(origin_mm), _metres((1.0, 0.0, 0.0))],
        label="middle-rib handedness", names=("origin", "+X"),
    )
    if right[0] <= origin[0]:
        cut.SetReversedCutDirection(not bool(cut.GetReversedCutDirection()))
        rebuild_drawing(adapter, label="middle-rib looks toward +Z")
        # Reversed section flips its handedness, not the model's +Y direction.
        origin, right, up = model_points_in_view(
            adapter, section, [_metres(origin_mm), _metres((1.0, 0.0, 0.0)), _metres((0.0, 1.0, 0.0))],
            label="middle-rib final handedness", names=("origin", "+X", "+Y"),
        )
        if right[0] <= origin[0] or up[1] <= origin[1] or abs(up[0] - origin[0]) > 1e-7:
            raise RuntimeError("middle-rib L-L has wrong native handedness")
    for attempt in range(4):
        section.UpdateViewDisplayGeometry()
        origin = model_point_in_view(adapter, section, _metres(origin_mm), label="L-L axis")
        if math.dist(origin, MIDDLE_RIB_SECTION_ORIGIN) <= 1e-4:
            break
        position = tuple(float(value) for value in section.Position)
        if not section.SetViewPosition(double_array([
            position[index] + MIDDLE_RIB_SECTION_ORIGIN[index] - origin[index]
            for index in (0, 1)
        ]), False):
            raise RuntimeError("failed to centre middle-rib L-L on its native axis")
        rebuild_drawing(adapter, label=f"middle-rib centred, pass {attempt}")
    else:
        raise RuntimeError("middle-rib L-L native axis did not settle")
    tangents = _middle_rib_source_tangents(adapter, section)
    extensions = [
        _owned_centerline(adapter, section, ends, label=f"middle-rib tangent extension {index}")
        for index, ends in enumerate(tangents)
    ]
    annotations = curate_view_dimensions(
        adapter, section, keep={"MidRibLeftX": MIDDLE_RIB_DIMENSION_XY},
        view_label="middle-rib L-L", dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    if len(annotations) != 1:
        raise RuntimeError("middle-rib L-L did not import its one native model dimension")
    reach_annotation = _early_bound(annotations[0], "IAnnotation")
    _apply_callouts(adapter, annotations, label="middle-rib L-L")
    position_section_caption(adapter, section, MIDDLE_RIB_CAPTION_XY, label="middle-rib L-L")
    captions = [
        _early_bound(raw, "INote") for raw in (section.GetNotes() or ())
        if "<VLLABEL>" in str(_early_bound(raw, "INote").PropertyLinkedText or "")
    ]
    if len(captions) != 1:
        raise RuntimeError("middle-rib L-L lost its native linked section caption")
    caption = captions[0]
    caption_annotation = _early_bound(caption.GetAnnotation(), "IAnnotation")
    if drawing.ActivateView(view_name(adapter, plan)) is not True:
        raise RuntimeError("failed to activate the middle-rib cut-location plan")
    plan_note = _early_bound(add_property_linked_note(
        adapter, "Middle Rib Plan Note", *MIDDLE_RIB_PLAN_NOTE_XY
    ), "INote")
    plan_note_annotation = _early_bound(plan_note.GetAnnotation(), "IAnnotation")

    def check() -> None:
        if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
            raise RuntimeError("could not activate receiver sheet for middle-rib proof")
        if not cut.GetDisplayOnlySurfaceCut() or _middle_rib_source_tangents(adapter, section) != tangents:
            raise RuntimeError("middle-rib native section/profile association changed")
        sketch = _early_bound(section.GetSketch(), "ISketch")
        transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
        utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
        for index, (segment, ends) in enumerate(zip(extensions, tangents, strict=True)):
            if int(segment.Color) != 0 or sum(
                adapter.swApp.IsSame(raw, segment) == 1
                for raw in (sketch.GetSketchSegments() or ())
            ) != 1:
                raise RuntimeError(f"middle-rib tangent extension {index} left its owning view")
            projected = model_points_in_view(
                adapter, section, [_metres(point) for point in ends],
                label=f"middle-rib tangent extension {index}", names=("join", "vertex"),
            )
            line = _early_bound(segment, "ISketchLine")
            for accessor, (x, y) in zip(("GetStartPoint2", "GetEndPoint2"), projected, strict=True):
                expected_point = _early_bound(utility.CreatePoint(
                    double_array([x, y, 0.0])
                ), "IMathPoint")
                expected = tuple(float(value) for value in _early_bound(
                    expected_point.MultiplyTransform(transform), "IMathPoint"
                ).ArrayData)
                point = _early_bound(adapter._get_attr_or_call(line, accessor), "ISketchPoint")
                actual = tuple(float(adapter._get_attr_or_call(point, axis)) for axis in "XYZ")
                if (
                    not all(math.isfinite(value) for value in (*actual, *expected))
                    or math.dist(actual, expected) > 1e-9
                ):
                    raise RuntimeError(f"middle-rib tangent extension {index} no longer meets its native profile")
        _middle_rib_annotation_box(
            adapter, reach_annotation, label="middle-rib theoretical reach",
            required_dimension=True,
        )
        captions_now = [
            _early_bound(raw, "INote") for raw in (section.GetNotes() or ())
            if "<VLLABEL>" in str(_early_bound(raw, "INote").PropertyLinkedText or "")
        ]
        if (
            len(captions_now) != 1
            or adapter.swApp.IsSame(captions_now[0].GetAnnotation(), caption_annotation) != 1
            or "SECTION L-L" not in " ".join(str(caption.GetText() or "").upper().split())
            or int(caption_annotation.OwnerType) != 0
        ):
            raise RuntimeError("middle-rib L-L lost its readable SECTION L-L caption")
        caption_box = _middle_rib_annotation_box(
            adapter, caption_annotation, label="middle-rib SECTION L-L caption", required_text=True,
            expected_text="SECTION L-L",
        )
        display = _early_bound(reach_annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        full_name = str(dimension.FullName)
        reach_mm = float(dimension.SystemValue) * 1000.0
        if (
            full_name.split("@")[:2] != ["MidRibLeftX", "MiddleRibProfile"]
            or not math.isfinite(reach_mm) or abs(reach_mm - RIB_PLATE_REACH) > 1e-7
            or reach_annotation.IsDangling()
            or int(reach_annotation.OwnerType) != 0
            or sum(adapter.swApp.IsSame(raw, reach_annotation) == 1 for raw in (section.GetAnnotations() or ())) != 1
            or str(display.GetText(3) or "") != DIMENSION_CALLOUTS_ABOVE["MidRibLeftX"]
            or str(plan_note.GetText() or "") != MIDDLE_RIB_PLAN_NOTE
            or int(plan_note_annotation.OwnerType) != 0
            or sum(adapter.swApp.IsSame(raw, plan_note_annotation) == 1 for raw in (plan.GetAnnotations() or ())) != 1
        ):
            raise RuntimeError("middle-rib L-L lost its native theoretical-reach dimension")
        _telemetry.info(f"middle-rib imported source {full_name}: {dimension.SystemValue} m")
        new_ink = {"middle-rib SECTION L-L caption": (caption_box, MIDDLE_RIB_SECTION_REGION)}
        for name, view, region in (
            ("middle-rib L-L", section, MIDDLE_RIB_SECTION_REGION),
            ("middle-rib cut plan", plan, MIDDLE_RIB_PLAN_REGION),
        ):
            view.UpdateViewDisplayGeometry()
            outline = tuple(float(value) for value in view.GetOutline())
            new_ink[f"{name} outline"] = (outline, region)
            view_annotations = list(_middle_rib_view_annotations(view, label=name))
            if view is section and not any(
                adapter.swApp.IsSame(raw, caption_annotation) == 1 for raw in view_annotations
            ):
                view_annotations.append(caption_annotation)
            for index, raw_annotation in enumerate(view_annotations):
                if adapter.swApp.IsSame(raw_annotation, plan_note_annotation) == 1:
                    continue
                box = _middle_rib_annotation_box(adapter, raw_annotation, label=f"{name} annotation {index}")
                if box is not None:
                    new_ink[f"{name} annotation {index}"] = (box, region)
                text_box = _middle_rib_annotation_box(
                    adapter, raw_annotation, label=f"{name} text {index}", text_only=True,
                )
                if text_box is not None and not boxes_clear(text_box, outline, gap=0.002):
                    raise RuntimeError(f"{name} text {index} crowds its own cut: {text_box}, {outline}")
        note_box = _middle_rib_annotation_box(
            adapter, plan_note_annotation, label="middle-rib plan label", required_text=True,
        )
        if note_box is None:
            raise RuntimeError("middle-rib cut plan lost its readable label")
        new_ink["middle-rib plan label"] = (note_box, MIDDLE_RIB_PLAN_REGION)
        plan_text_box = _middle_rib_annotation_box(
            adapter, plan_note_annotation, label="middle-rib plan label text", text_only=True,
        )
        if not boxes_clear(plan_text_box, new_ink["middle-rib cut plan outline"][0], gap=0.002):
            raise RuntimeError("middle-rib plan label crowds its own cut-location view")
        for name, box in _middle_rib_cut_ink(plan).items():
            new_ink[name] = (box, MIDDLE_RIB_PLAN_REGION)
        neighbors = _middle_rib_foreign_ink(
            adapter, neighboring_views=neighboring_views, sheet_view=drawing.GetFirstView(),
            plan_note_annotation=plan_note_annotation,
        )
        if not any(name.endswith(f" detail {RIB_END_DETAIL_LETTER}") for name in neighbors):
            raise RuntimeError("receiver view lost its native Detail J source fence/label")
        _require_middle_rib_layout(new_ink, neighbors)
        _telemetry.success(f"middle-rib native allocated ink: {new_ink}; foreign ink: {neighbors}")

    check()
    return section, plan, check


def _style_plate_thickness_witnesses(
    adapter: Any, view: Any, annotations: list[Any],
) -> Callable[[], None]:
    """Keep the imported thickness, but start both witnesses outside the bare cut.

    The extrusion dimension originates at the free edge, beyond the merged pad.
    Prove that origin before changing its native gaps; the final callback reads
    fresh projected geometry and actual ink, not merely the persisted settings.
    """
    label = "section C-C PlateThickness"
    gap_m, slop = 0.001, 1e-8
    if len(annotations) != 1:
        raise RuntimeError(f"{label}: expected one imported thickness annotation")
    annotation = _early_bound(annotations[0], "IAnnotation")

    def finite(value: Any) -> bool:
        return type(value) in (int, float) and math.isfinite(value)

    def same(first: Any, second: Any) -> bool:
        result = adapter.swApp.IsSame(first, second)
        return type(result) is int and result == 1

    def model_state() -> tuple[Any, Any, str, float, tuple[int, float, float]]:
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        if drawing.ActivateSheet(SHEET_NAMES[0]) is not True:
            raise RuntimeError(f"{label}: could not activate its geometry sheet")
        kind, owner_type = annotation.GetType(), annotation.OwnerType
        if (
            type(kind) is not int or kind != 4
            or type(owner_type) is not int or owner_type != 0
            or annotation.IsDangling() is not False
            or sum(same(raw, annotation) for raw in (view.GetAnnotations() or ())) != 1
        ):
            raise RuntimeError(f"{label}: imported thickness is detached from its view")
        raw_display = annotation.GetSpecificAnnotation()
        if raw_display is None:
            raise RuntimeError(f"{label}: missing native display dimension")
        display = _early_bound(raw_display, "IDisplayDimension")
        raw_dimension = display.GetDimension2(0)
        if raw_dimension is None:
            raise RuntimeError(f"{label}: missing native model dimension")
        dimension = _early_bound(raw_dimension, "IDimension")
        name, value = dimension.FullName, dimension.SystemValue
        if (
            type(name) is not str
            or name.split("@")[:2] != ["PlateThickness", "CoefficientsPlate"]
            or not finite(value)
            or abs(value - PLATE_T / 1000.0) > 1e-12
        ):
            raise RuntimeError(f"{label}: wrong model identity or thickness")
        raw_tolerance = dimension.Tolerance
        if raw_tolerance is None:
            raise RuntimeError(f"{label}: missing native model band")
        tolerance = _early_bound(raw_tolerance, "IDimensionTolerance")
        band = (tolerance.Type, tolerance.GetMinValue(), tolerance.GetMaxValue())
        if type(band[0]) is not int or not all(finite(v) for v in band[1:]):
            raise RuntimeError(f"{label}: invalid native model band")
        return display, dimension, name, value, band

    def geometry() -> tuple[tuple[float, float], tuple[float, float], float]:
        points = [
            model_point_in_view(
                adapter, view, _metres((x, y, PLATE_SECTION_Z)),
                label=f"{label} {edge} {face}",
            )
            for edge, x in (("bare cut", PLATE_SECTION_X[0]), ("free edge", PLATE_W))
            for face, y in (("bottom", -PLATE_T / 2.0), ("top", PLATE_T / 2.0))
        ]
        if any(len(point) != 2 or not all(finite(v) for v in point) for point in points):
            raise RuntimeError(f"{label}: nonfinite projected plate geometry")
        bottom, top, free_bottom, free_top = points
        span = free_bottom[0] - bottom[0]
        if (
            span <= 0.0
            or abs(span - (PLATE_W - PLATE_SECTION_X[0]) / 1000.0) > slop
            or abs(top[0] - bottom[0]) > slop
            or abs(top[1] - bottom[1] - PLATE_T / 1000.0) > slop
            or any(
                abs(free[0] - cut[0] - span) > slop
                or abs(free[1] - cut[1]) > slop
                for cut, free in ((bottom, free_bottom), (top, free_top))
            )
        ):
            raise RuntimeError(f"{label}: unexpected projected plate direction or scale")
        return bottom, top, span

    def gaps(display: Any, *, local: bool) -> tuple[float, float]:
        values = []
        for index in (0, 1):
            ok, use_doc, value = display.GetWitnessLineGap(index, False, 0.0)
            if (
                ok is not True or type(use_doc) is not bool
                or (local and use_doc is not False)
                or not finite(value) or value < 0.0
            ):
                raise RuntimeError(f"{label}: invalid native witness gap {index}")
            values.append(value)
        return tuple(values)

    def ink(
        display: Any, faces: tuple[tuple[float, float], tuple[float, float]],
        starts: tuple[float, float],
    ) -> tuple[tuple[tuple[float, float], ...], tuple[float, ...]]:
        raw_data = display.GetDisplayData()
        if raw_data is None:
            raise RuntimeError(f"{label}: missing native display data")
        data = _early_bound(raw_data, "IDisplayData")
        count = data.GetArrowHeadCount()
        if type(count) is not int or count != 2:
            raise RuntimeError(f"{label}: expected two visible native arrows")
        tips = []
        for index in (0, 1):
            row = tuple(data.GetArrowHeadAtIndex2(index))
            if len(row) != 12 or not all(finite(value) for value in row):
                raise RuntimeError(f"{label}: invalid native arrow coordinates")
            tips.append((row[0], row[1]))
        tips.sort(key=lambda point: point[1])
        segments = dimension_segments(annotation)
        if not segments or any(
            not all(finite(value) for point in stroke for value in point)
            for stroke in segments
        ):
            raise RuntimeError(f"{label}: invalid native witness coordinates")
        horizontal = [
            stroke for stroke in segments
            if abs(stroke[1][1] - stroke[0][1]) <= slop
            and abs(stroke[1][0] - stroke[0][0]) > slop
        ]
        if len(horizontal) != 2 or abs(tips[0][0] - tips[1][0]) > slop:
            raise RuntimeError(f"{label}: expected two horizontal native witnesses")
        tails = []
        for face, tip, start in zip(faces, tips, starts):
            matches = [
                stroke for stroke in horizontal
                if all(abs(point[1] - face[1]) <= slop for point in stroke)
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{label}: witness does not follow its plate face level")
            left, right = sorted(point[0] for point in matches[0])
            if (
                abs(tip[1] - face[1]) > slop
                or abs(right - start) > slop
                or not left < tip[0] < face[0] - gap_m
                or tip[0] > right + slop
            ):
                raise RuntimeError(f"{label}: unexpected native witness endpoint or arrow")
            tails.append(left)
        # Any extra horizontal continuation through the pad, or a skewed
        # stroke, is unexpected ink, not a shortened visible witness pair.
        if any(
            stroke not in horizontal
            and any(abs(point[0] - tips[0][0]) > slop for point in stroke)
            for stroke in segments
        ):
            raise RuntimeError(f"{label}: unexpected native dimension-line ink")
        return tuple(tips), tuple(tails)

    display, dimension, name, value, band = model_state()
    bottom, top, span = geometry()
    original_gaps = gaps(display, local=False)
    if any(abs(old - gap_m) > slop for old in original_gaps):
        raise RuntimeError(f"{label}: unexpected original native witness gaps")
    # Both actual witness starts must still derive from the model's free
    # edge, not a seam or another origin that happens to have the same value.
    tips, tails = ink(
        display, (bottom, top),
        tuple(face[0] + span - old for face, old in zip((bottom, top), original_gaps)),
    )
    expected_gaps = tuple(old + span for old in original_gaps)
    for index, gap in enumerate(expected_gaps):
        if display.SetWitnessLineGap(index, False, gap) is not True:
            raise RuntimeError(f"{label}: native witness gap {index} was refused")

    def check_witnesses() -> None:
        current, owner, current_name, current_value, current_band = model_state()
        if (
            not same(current, display) or not same(owner, dimension)
            or (current_name, current_value, current_band) != (name, value, band)
        ):
            raise RuntimeError(f"{label}: native model identity, value or band changed")
        actual_gaps = gaps(current, local=True)
        if any(abs(actual - expected) > slop for actual, expected in zip(actual_gaps, expected_gaps)):
            raise RuntimeError(f"{label}: native witness gaps did not persist")
        low, high, _span = geometry()
        actual_tips, actual_tails = ink(
            current, (low, high), (low[0] - gap_m, high[0] - gap_m),
        )
        if (
            any(math.dist(actual, expected) > slop for actual, expected in zip(actual_tips, tips))
            or any(abs(actual - expected) > slop for actual, expected in zip(actual_tails, tails))
        ):
            raise RuntimeError(f"{label}: native arrow tips or witness tails moved")

    # Read both native settings back before rebuilding, then prove the rebuilt
    # ink. The same proof runs after finalize_drawing's last regeneration.
    actual_gaps = gaps(display, local=True)
    if any(abs(actual - expected) > slop for actual, expected in zip(actual_gaps, expected_gaps)):
        raise RuntimeError(f"{label}: native witness gaps did not persist")
    rebuild_drawing(adapter, label="section C-C bare-cut witness gaps")
    check_witnesses()
    return check_witnesses


def _sheet_to_view_sketch(
    adapter: Any, view: Any, sheet_points: list[tuple[float, float]]
) -> list[tuple[float, ...]]:
    """Sheet points in ``view``'s own sketch (its ModelToSketchTransform),
    for fences and lines sketched into a view."""
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    return points


def _stub_root_view(adapter: Any) -> Any:
    """Removed Top K, turned to match F and cropped around the -Z root.

    The crop and recenter use section H-H's proven view-sketch circle and
    model-anchor readback, not the model view's padded outline centre.
    """
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(
        place_view(
            adapter, str(SOURCE), "*Top", *STUB_ROOT_CENTER, scale=STUB_ROOT_SCALE
        ),
        "IView",
    )
    _hidden_lines_removed_without_greyed_pass(native)
    _set_tangent_edges(native, visible=True)
    native.Angle = math.pi
    rebuild_drawing(adapter, label="stub root view turned")
    if not math.isclose(float(native.Angle), math.pi, abs_tol=1e-9):
        raise RuntimeError("stub root view did not retain its half turn")
    anchor = _metres(STUB_ROOT_ANCHOR_MM)
    fence = model_points_in_view(
        adapter,
        native,
        [
            anchor,
            _metres(
                (
                    STUB_ROOT_CROP_RADIUS_MM,
                    STUB_ROOT_ANCHOR_MM[1],
                    STUB_ROOT_ANCHOR_MM[2],
                )
            ),
        ],
        label="stub root crop circle",
        names=("centre", "rim"),
    )
    if not drawing.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate stub root view for its crop")
    draw.ClearSelection2(True)
    centre, rim = _sheet_to_view_sketch(adapter, native, fence)
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*centre, *rim)
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError("failed to create the stub root crop circle")
    if not _early_bound(circle, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select the stub root crop circle")
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="stub root view cropped")
    native.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in native.GetOutline())
    diameter = 2.0 * math.dist(fence[0], fence[1])
    if (
        status != 1
        or not bool(native.IsCropped())
        or max(outline[2] - outline[0], outline[3] - outline[1]) > diameter + 0.025
    ):
        raise RuntimeError(
            f"stub root view did not crop to {diameter * 1000.0:.1f} mm: "
            f"status {status}, outline {outline!r}"
        )
    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"K root, pass {attempt}"
        )
        if math.dist(projected, STUB_ROOT_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + STUB_ROOT_CENTER[axis] - projected[axis]
            for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to recenter stub root view")
        rebuild_drawing(adapter, label=f"stub root recentered, pass {attempt}")
    else:
        raise RuntimeError(
            f"stub root centre stands at {projected}, not {STUB_ROOT_CENTER}"
        )
    return native


def _thin_visible_layer(adapter: Any) -> None:
    """Create (once) TAP_THREAD_LAYER, black thin continuous, and read its
    state back: section H-H's cosmetic thread and its break line print on
    it."""
    manager = _early_bound(adapter.currentModel.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(TAP_THREAD_LAYER)
    if layer is None:
        # COLORREF black, swLineCONTINUOUS (0), swLW_THIN (0).
        if (
            int(manager.AddLayer(TAP_THREAD_LAYER, "section H-H tap thread", 0, 0, 0))
            != 1
        ):
            raise RuntimeError(f"failed to add layer {TAP_THREAD_LAYER}")
        layer = manager.GetLayer(TAP_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = True
    if not bool(layer.Visible) or int(layer.Style) != 0 or int(layer.Width) != 0:
        raise RuntimeError(
            f"layer {TAP_THREAD_LAYER} reads visible={layer.Visible!r}, style "
            f"{layer.Style!r}, width {layer.Width!r}; wanted visible thin continuous"
        )


def _section_thread_on_visible_layer(adapter: Any, section: Any) -> None:
    """Import section H-H's cosmetic thread and print it thin and solid.

    draw_pn_pen_v_block's ``_section_thread_on_visible_layer``: the layer is
    created thin continuous (``ILayerMgr::AddLayer``), its state and every
    thread annotation's layer read back.
    """
    threads = import_cosmetic_threads(adapter, section)
    if threads[1] < 1:
        raise RuntimeError("section H-H has no native cosmetic-thread instance")
    _thin_visible_layer(adapter)
    moved = 0
    for raw_annotation in _early_bound(section, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != _COSMETIC_THREAD_ANNOTATION:
            continue
        annotation.Layer = TAP_THREAD_LAYER
        if str(annotation.Layer or "") != TAP_THREAD_LAYER:
            raise RuntimeError(f"a cosmetic thread refused layer {TAP_THREAD_LAYER}")
        moved += 1
    if moved < 1:
        raise RuntimeError("section H-H lists no cosmetic-thread annotation to layer")
    rebuild_drawing(adapter, label=f"cosmetic threads to {TAP_THREAD_LAYER}")
    _telemetry.info(
        f"section H-H cosmetic threads: seeds/instances={threads!r}, {moved} on "
        f"{TAP_THREAD_LAYER}"
    )


def _tap_section(adapter: Any, front: Any) -> Any:
    """Section H-H along the outer receiver tap (TAP_SECTION_* above), cut in
    VIEW G: cut face only, looking +X, turned +Y up, cropped to the end rib
    and the plate beyond (draw_fr_nameplate's ``_crop_section``), its centre
    landed on TAP_SECTION_CENTER, a break line where the plate is cut off,
    and its cosmetic thread on a thin continuous layer."""
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    x_mm, _, end_z = TAP_SECTION_HOLE
    line = model_points_in_view(
        adapter,
        front,
        [_metres((x_mm, y, end_z)) for y in TAP_SECTION_LINE_Y],
        label="section H-H line",
        names=("below", "above"),
    )
    section = create_section_view(
        adapter,
        front,
        line_start=line[0],
        line_end=line[1],
        view_xy=TAP_SECTION_CENTER,
        section_label=TAP_SECTION_LETTER,
        scale=TAP_SECTION_SCALE,
        partial=True,
        label="receiver tap section",
    )
    native = _early_bound(section, "IView")
    cut = _early_bound(native.GetSection(), "IDrSection")
    # R2026x declares SetDisplayOnlySurfaceCut as a void setter; only its
    # dedicated bool getter may be truth-tested.
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="section H-H cut face only")
    if not cut.GetDisplayOnlySurfaceCut():
        raise RuntimeError("section H-H retained geometry beyond the cutting plane")

    def arrows_point_right() -> bool:
        # GetArrowInfo: each arrow's start (on the line) then its tip, in
        # sheet space; the tips point the direction of sight.
        info = [float(value) for value in (cut.GetArrowInfo() or ())]
        if len(info) != 12:
            raise RuntimeError(f"section H-H arrow info has {len(info)} values")
        return all(
            info[i + 3] - info[i] > 0.0 and abs(info[i + 4] - info[i + 1]) <= 1e-6
            for i in (0, 6)
        )

    if not arrows_point_right():
        reversed_cut = not bool(cut.GetReversedCutDirection())
        cut.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label="section H-H looks +X")
        if bool(cut.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section H-H cut direction did not persist")
        if not arrows_point_right():
            raise RuntimeError("section H-H arrows do not point right")
    _telemetry.info(
        f"section H-H arrows {tuple(cut.GetArrowInfo() or ())!r}, "
        f"letters {tuple(cut.GetTextInfo() or ())!r}"
    )
    _hidden_lines_removed_without_greyed_pass(native)
    anchor = _metres(_TAP_SECTION_ANCHOR_MM)
    above = _metres((_TAP_SECTION_ANCHOR_MM[0], 1.0, _TAP_SECTION_ANCHOR_MM[2]))
    for attempt in range(3):
        origin = model_point_in_view(adapter, native, anchor, label="H-H anchor")
        up = model_point_in_view(adapter, native, above, label="H-H +Y")
        dx, dy = up[0] - origin[0], up[1] - origin[1]
        if dy > 0.0 and abs(dx) <= 1e-7:
            break
        native.Angle = float(native.Angle) + math.pi / 2.0 - math.atan2(dy, dx)
        rebuild_drawing(adapter, label=f"section H-H turned, pass {attempt}")
    else:
        raise RuntimeError(f"section H-H does not run +Y up: ({dx:g}, {dy:g})")

    # Crop2(jagged, no outline, intensity) round a circle fence in the
    # section's own sketch, its centre and a rim point projected from the cut
    # plane; it returns swCropViewErrors_e, 1 NoError.
    rebuild_drawing(adapter, label="section H-H before crop")
    fence = model_points_in_view(
        adapter,
        native,
        [
            anchor,
            _metres(
                (
                    x_mm,
                    TAP_SECTION_CROP_RADIUS,
                    _TAP_SECTION_ANCHOR_MM[2],
                )
            ),
        ],
        label="section H-H crop circle",
        names=("centre", "rim"),
    )
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate section H-H for its crop")
    draw.ClearSelection2(True)
    before = tuple(float(value) for value in native.GetOutline())
    centre, rim = _sheet_to_view_sketch(adapter, native, fence)
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        circle = sketch_manager.CreateCircle(*centre, *rim)
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError("failed to create the section H-H crop circle")
    if not _early_bound(circle, "ISketchSegment").Select4(False, None):
        raise RuntimeError("failed to select the section H-H crop circle")
    status = int(native.Crop2(False, True, 0))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section H-H crop")
    native.UpdateViewDisplayGeometry()
    outline = tuple(float(value) for value in native.GetOutline())
    _telemetry.info(
        f"section H-H Crop2 status {status}: outline {before!r} -> {outline!r}, "
        f"crop circle {fence!r}"
    )
    # The outline carries a margin past the fence (draw_fr_nameplate r3: a
    # 68.8 mm fence read back 88.0 mm); the proof is the shrink.
    width = 2.0 * math.dist(fence[0], fence[1])
    if (
        status != 1
        or not bool(native.IsCropped())
        or outline[2] - outline[0] > width + 0.025
        or outline[2] - outline[0] > 0.25 * (before[2] - before[0])
    ):
        raise RuntimeError(
            f"section H-H did not crop to {width * 1000.0:.1f} mm: status {status}, "
            f"outline {before!r} -> {outline!r}"
        )

    for attempt in range(4):
        native.UpdateViewDisplayGeometry()
        projected = model_point_in_view(
            adapter, native, anchor, label=f"H-H centre, pass {attempt}"
        )
        if math.dist(projected, TAP_SECTION_CENTER) <= 1e-4:
            break
        position = tuple(float(value) for value in native.Position)
        moved = [
            position[axis] + TAP_SECTION_CENTER[axis] - projected[axis]
            for axis in (0, 1)
        ]
        if not native.SetViewPosition(double_array(moved), False):
            raise RuntimeError("failed to re-centre section H-H")
        rebuild_drawing(adapter, label=f"section H-H re-centred, pass {attempt}")
    else:
        raise RuntimeError(
            f"section H-H centre stands at {projected}, not {TAP_SECTION_CENTER}"
        )

    # The break line, thin, in the section's own sketch; AddToDB keeps sketch
    # inference from snapping its short segments onto the cut face's edges.
    # On the black thin layer: a layer-less view-sketch line prints grey
    # (machinist review 20261018 read the break as a construction line).
    _thin_visible_layer(adapter)
    break_points = model_points_in_view(
        adapter,
        native,
        [_metres((x_mm, y, z)) for z, y in TAP_SECTION_BREAK],
        label="section H-H break line",
    )
    if not ddoc.ActivateView(view_name(adapter, native)):
        raise RuntimeError("failed to activate section H-H for its break line")
    draw.ClearSelection2(True)
    points = _sheet_to_view_sketch(adapter, native, break_points)
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        for index in range(len(points) - 1):
            created = sketch_manager.CreateLine(*points[index], *points[index + 1])
            if created is None:
                raise RuntimeError(f"section H-H break line segment {index} failed")
            segment = _early_bound(created, "ISketchSegment")
            segment.Layer = TAP_THREAD_LAYER
            if str(segment.Layer or "") != TAP_THREAD_LAYER:
                raise RuntimeError(
                    f"section H-H break line segment {index} refused layer "
                    f"{TAP_THREAD_LAYER}"
                )
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="section H-H break line")
    _section_thread_on_visible_layer(adapter, native)
    position_section_caption(
        adapter, native, TAP_SECTION_CAPTION_XY, label="receiver tap section H-H"
    )
    return native


_SW_HIDDEN = 2  # swDisplayMode_e.swHIDDEN: hidden lines removed


def _hidden_lines_removed_without_greyed_pass(view: Any) -> None:
    """Set a newly created ``view`` to HLR without showing hidden lines.

    set_hidden_lines_removed passes through hidden-lines-visible to force a
    regen.  That pass is where the bracket taps' "#2-56 Tapped Hole" label,
    their threads hidden behind the plate in every sheet-1 view, grew on some
    builds only (#1591, farm 2026-10-17): on the plan right after its pass
    (ba33167e's stage log), on section C-C (493638fa), on neither in
    2fa756e1 and 802e4117 -- the one note the sweep's count varied by.  Each
    caller sets the view straight after creating it, before the recipe attaches
    dimensions or feature callouts, so the regen is not needed.  Farm seats
    placed all six sheet-1 views in HLR already (5a58480d), where the set is
    a no-op; that build,
    on the seat behind both 9-label builds, swept 8 and its PDF is
    pixel-identical to r18b's, which still had the pass.
    K and J use this same direct path immediately after placement.
    """
    bound = _early_bound(view, "IView")
    placed = int(bound.GetDisplayMode2())
    bound.SetDisplayMode4(False, _SW_HIDDEN, False, False, True)
    mode = int(bound.GetDisplayMode2())
    if mode != _SW_HIDDEN:
        raise RuntimeError(
            f"failed to set hidden-lines-removed drawing view (mode reads {mode})"
        )
    _telemetry.info(f"{bound.GetName2()} placed in display mode {placed}, now HLR")


def _set_tangent_edges(view: Any, *, visible: bool) -> None:
    """Keep K's fillet arcs; suppress root rings that read as steps in end views."""
    bound = _early_bound(view, "IView")
    mode = 2 if visible else 0  # swTangentEdgesVisible / swTangentEdgesHidden
    bound.SetDisplayTangentEdges2(mode)
    if int(bound.GetDisplayTangentEdges2()) != mode:
        raise RuntimeError(
            f"{bound.GetName2()}: tangent edges did not become "
            f"{'visible' if visible else 'hidden'}"
        )
    bound.UpdateViewDisplayGeometry()


def _remove_redundant_thread_notes(adapter: Any) -> None:
    """Inventory, delete and read back the actual automatic thread labels.

    Like draw_fr_top_frame, do not make their incidental count specification:
    #1591 already recorded view-dependent labels.  PR1709's failed leaf had
    four H-H cosmetic threads on TAP_THREAD_LAYER but no H-H label (7 total,
    not 8).  The three authored native callouts, not these notes, define holes.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    draw = adapter.currentModel
    labels = 0
    for sheet_name in SHEET_NAMES:
        sheet = _early_bound(ddoc.Sheet(sheet_name), "ISheet")
        for raw_view in sheet.GetViews() or ():
            view = _early_bound(raw_view, "IView")
            threads = 0
            found: list[str] = []
            hits: list[Any] = []
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                kind = int(annotation.GetType())
                if kind == _COSMETIC_THREAD_ANNOTATION:
                    threads += 1
                elif kind == 6:  # swNote
                    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
                    text = str(note.GetText() or "")
                    if "tapped hole" in text.lower():
                        found.append(f"{annotation.GetName()}={text!r}")
                        hits.append(annotation)
            labels += len(found)
            _telemetry.info(
                f"thread labels: {sheet_name}/{view_name(adapter, view)} "
                f"{threads} cosmetic threads, {len(found)} labels {found!r}"
            )
            for annotation in hits:
                draw.ClearSelection2(True)
                if not annotation.Select2(False, 0):
                    raise RuntimeError("failed to select an automatic tapped-hole note")
                draw.EditDelete()  # VT_VOID: the re-read below proves deletion.
            draw.ClearSelection2(True)
            survivors = [
                str(_early_bound(raw, "INote").GetText() or "")
                for raw in (view.GetNotes() or ())
                if "tapped hole" in str(_early_bound(raw, "INote").GetText() or "").lower()
            ]
            if survivors:
                raise RuntimeError(
                    f"{sheet_name}/{view_name(adapter, view)}: automatic tapped-hole "
                    f"notes survived deletion: {survivors!r}"
                )
    _telemetry.info(f"thread labels: {labels} in all")


def _finished_thread_annotation_check(
    adapter: Any, callouts: Iterable[tuple[str, Any, Any]]
) -> Callable[[], None]:
    """Keep the authored callouts' identity and native definitions through cleanup
    and the final settling rebuild, with no redundant note left on either sheet."""
    expected = []
    for label, view, raw_display in callouts:
        display = _early_bound(raw_display, "IDisplayDimension")
        if not display.IsHoleCallout():
            raise RuntimeError(f"{label}: authored annotation is not a native hole callout")
        expected.append((
            label, view, _early_bound(display.GetAnnotation(), "IAnnotation"),
            tuple(str(display.GetText(part) or "") for part in (5, 6, 7, 8)),
        ))

    def check_annotations() -> None:
        ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
        for sheet_name in SHEET_NAMES:
            sheet = _early_bound(ddoc.Sheet(sheet_name), "ISheet")
            for raw_view in sheet.GetViews() or ():
                view = _early_bound(raw_view, "IView")
                for raw_note in view.GetNotes() or ():
                    text = str(_early_bound(raw_note, "INote").GetText() or "")
                    if "tapped hole" in text.lower():
                        raise RuntimeError(
                            f"{sheet_name}/{view_name(adapter, view)}: redundant "
                            f"tapped-hole note remains: {text!r}"
                        )
        for label, view, original, definitions in expected:
            matches = [
                _early_bound(raw, "IAnnotation")
                for raw in (_early_bound(view, "IView").GetAnnotations() or ())
                if int(adapter.swApp.IsSame(raw, original)) == 1
            ]
            if len(matches) != 1:
                raise RuntimeError(f"{label}: authored native hole callout is missing")
            annotation = matches[0]
            if annotation.IsDangling():
                raise RuntimeError(f"{label}: authored native hole callout is dangling")
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            if not display.IsHoleCallout() or definitions != tuple(
                str(display.GetText(part) or "") for part in (5, 6, 7, 8)
            ):
                raise RuntimeError(f"{label}: authored native hole callout changed")

    return check_annotations


def _mounting_rims(edges: ViewEdges) -> list[Any]:
    """Back looks from -Z directly onto the blind taps' entry circles."""
    return [
        edges.circle_at(
            point, TAP_DRILL_DIA / 2.0, axis=(0.0, 0.0, 1.0),
            label=f"bracket receiver {index}",
        )
        for index, point in enumerate(LEVER_HOLE_POINTS)
    ]


# VIEW F's owned centreline continues through BOTH taps and the hex centre
# (#1607: stopping it at the holes left the row's relation to the axis unclear).
# ReceiverY0 already measures vertically from the plate-top/free-edge corner
# (PLATE_W, PLATE_T/2) to tap 0, whose Y is 0 (LEVER_HOLE_POINTS).  The former
# (2.54) REF from that same plate-top plane to this Y=0 centreline repeated
# ReceiverY0's interval without adding a requirement.  Keep the common axis
# and native 2.54 +/-0.05, not a second dimension with colliding ink.
RECEIVER_AXIS_START_MM = 39.5  # unchanged free-edge end: former 37.5 + 2 overrun
RECEIVER_AXIS_OVERRUN_MM = 2.0


def _receiver_row_centerline(adapter: Any, back: Any) -> Any:
    """Show the receiver row and hex centre on one axis, with no duplicate REF."""
    z_mm = -PLATE_L / 2.0
    return _owned_centerline(
        adapter,
        back,
        (
            (RECEIVER_AXIS_START_MM, 0.0, z_mm),
            (-(HEX_W / 2.0 + RECEIVER_AXIS_OVERRUN_MM), 0.0, z_mm),
        ),
        label="receiver row centreline",
    )


# Front profile at 1:2 (2026-10-15 baseline render): the pivot axis prints at
# (0.2352, 0.2352), the boss spans x 0.1925..0.2021, the end rib's R15.24 arc
# 7.6 mm round the axis, the web bar y 0.2338..0.2363 from the boss to that
# arc, the plate tip x 0.2535..0.2575. The END ribs share this clipped
# outline; the middle rib's tangent reaches a buried theoretical vertex
# instead (section L-L). The end-face 35.75 sits above this view,
# taking a leader from below left of the detail letter, the boss height left
# of the boss, and the web thickness standing above the web.  The cylinder
# is sized in the plan (TOP_KEEP): here the rib outline hides it.
# A radial leader runs along the line from the arc's centre to the end of its
# text block's BOTTOM line (farm r5: the R15.24 leader went to "AT BOSS
# AXIS"'s right end, through the detail letter).  The rib arc's four lines
# stand under the view, left of the 20X frame, their bottom line's right end
# at (0.2112, 0.2019): 234 deg round the axis, inside the arc's visible
# span (it meets the lower slant at ~244 deg).  That bottom line stands 1.75
# mm over the plan's R138.85 centre (0.1737, 0.2001), where that radius's
# line starts, and 4.3 mm right of it (machinist review r6: over it, the line
# read as a leader off this shelf); the top line stands under 19.05's lower
# arrow.
FRONT_KEEP = {
    "AnchorHeight": (0.183, 0.235),
    "WebThickness": (0.215, 0.247),
    "EdgeRibFrontArcR": (0.1948, 0.2120),
    "EdgeRibFrontEndTopX": (0.2443, 0.254),
    # Right of the plate tip, its three lines under the value (machinist
    # review r8: from what, and why the end stands proud of the plate; r10:
    # from the plate top face, not the mid-plane).  The keep centres the 21
    # mm block: at 0.246 its bottom line sat on the lower extension line, the
    # shelf underlining it and the upper arrow in its text (farm r12); at
    # 0.253 the shelf runs over the upper arrow and the top line stands under
    # the border.
    "EdgeRibFrontEndStep": (0.284, 0.253),
}
# Detail D at 4:1: the hexagon's centre prints at DETAIL_CENTER, its flats at
# x 0.0628/0.0952, its vertices at y 0.1875/0.2285, its upper shoulders at y
# 0.2183, the fence 0.024 round it.  SolidWorks centres a dimension's whole
# text block (value and callout lines, 5.5 mm a line) on its keep, and a
# linear dimension's line underlines the block's bottom line, 2.8 mm under
# the keep for one line (stack r4: a seven-line block keyed at 0.258 rose
# 9.7 mm over the border and dropped its line onto E's fence).
# The reference width stands right of its span, under the fence and above
# the boss diameter's four lines (top 0.1784), its line ~0.1817.  The vertex
# height stands left of the fence, its block level with the centre between
# the border and the fence, its three callout lines below the value; its
# extension lines cross only the side faces' extensions.  Code review C09
# (owner ruling T1): the ridge-to-side pair shares one dimension line at
# 0.2455 over the vertex, each text outside its own span, each with two
# callout lines under its value (keeps 5.5 mm higher for the same line):
# the +X one right of its extension lines and left of view G, its top line
# under the border; the -X one between the border and the -X extension
# line.  The flank-to-side angle, its seat line under its value, stands
# up-right of the +X shoulder, in the wedge opposite the solid's corner
# (inside the hexagon, machinist reviews r7/r8 read its text as a feature),
# its text outside the fence and its arc (~24 mm round the shoulder) topping
# out under the ridge pair's line; nothing else stands in that wedge (stack
# r4: the vertex height's line and text crossed the angle's text and
# extension).
DETAIL_KEEP = {
    "HexWidth": (0.125, 0.1845),
    "HexHeight": (0.0342, DETAIL_CENTER[1]),
    "RidgeFromLeft": (0.0378, 0.2538),
    "RidgeFromRight": (0.1355, 0.2538),
    "FlankToSide": (0.1164, 0.2309),
}
# Detail E: the round's R MAX up-right of the vertex, its text right of E's
# fence and of datum A's box (RIDGE_DATUM_RISE), its leader ~30 deg up the
# +X flank's side, ~8 mm right of the box's foot.
RIDGE_DETAIL_KEEP = {
    "KnifeRidgeRadius": (0.098, 0.091),
}
TOP_KEEP = {
    # Below the plate end, its witness lines 14 mm long: at 0.160 they ran
    # from the end up past every hole, boxing the column's right side (the
    # 20X callout's leader had to cross one). The line prints 2.8 mm under
    # the keep, at 0.0785: 2.9 mm under datum B's box, 2.3 mm over the 39.85
    # text (whose line, with 76.20's, dropped to 0.0695 for that), and the
    # text sits right of the span, clear of B.
    "PlateWidth": (0.266, 0.0813),
    # Right of the -Z rib's three lines (they end at x 0.4007; at 0.395 its
    # line crossed "DRILL", farm r7).  Its two callout lines (BODY END FACES,
    # 9 characters) end 2.9 mm inside the border.
    "PlateLength": (0.405, TOP_CENTER[1]),
    # -Z receiver rib (Top prints model +Z down): beside it, its witness lines
    # 17 mm from the free edge (x 0.2542; at 0.325 they ran 70 mm across the
    # field, machinist review r17), the line 5 mm right of section C-C's
    # outboard letter (x 0.259..0.265, top 0.161) and its text above the span.
    "RibDepth": (0.270, 0.1745),
    # The boss's diameter names the web arcs' ends under its value; its
    # four lines stand left of its leader, above the anchor tap's callout.
    "AnchorOuterDia": (0.145, 0.168),
    # Plan geometry (baseline render): the cylinder band x 0.2286..0.2417,
    # the -Z plate end at y 0.1681 with its stub to 0.179, the +Z end at
    # 0.0922, the summation web's arcs from the boss (x 0.2021) to the
    # cylinder ends.
    # Inside the web's upper arc (centre (0.1737, 0.2001), 69.4 sheet mm,
    # visible from -70 to -37 deg round it).  The leader starts at the text's
    # left end, at -60 deg and 46 mm from the centre, so it lands on the
    # visible arc: from -93 deg (farm r5) or -72 deg (r4) SolidWorks moved the
    # arrow to the opposite side, ruling the radius across the sheet.  Text
    # inside the arc rules the radius from its centre (farm r6), clear of
    # everything but the front view's rib-arc callout (see FRONT_KEEP).  The
    # text's far corner stays 7 mm inside the arc, 8 mm under the 21.72.
    # Foreshortened (_shorten_radii): the full line from the centre read as
    # a loose line (machinist review r8).
    "SummationArcRadius": (0.2096, 0.162),
    # Left of the -Z stub. Native text spanned x 213.0267..233.9732 mm
    # against the stub's x 232.2987 mm outline; move its anchor 5 mm left
    # to target 3.3 mm box clearance. Both stubs are one prism, so the length
    # remains the hidden KnifeStubReference's, along its -X side.
    "KnifeStubLength": (0.2185, 0.1735),
    # Left of the +Z end rib, above its span: below it the finish symbol and
    # the 76.20/39.85 row leave no room, and the web's lower arc reaches the
    # cylinder at x 0.226 there.  The text spans x 0.1979..0.2095, right of
    # the 76.20 X location's extension line (x 0.1972); the lower arrow
    # stands 3.8 mm left of the finish symbol's text; the text stands above
    # the boss Z location's datum-B extension line (y 0.0919).
    "EdgeRibThickness": (0.2095, 0.1035),
    # Outside the part, right of the free edge (machinist review b4df34ad9
    # r2/r3: inside the web, between the R138.85, the boss and the cylinder,
    # it read as crowded), as the -Z receiver rib's depth does: its extension lines run
    # from the rib's end across the hole column (one hole sits on the rib's
    # mid-plane, its rim 0.5 mm inside them) to the line 8 mm past the free
    # edge (x 0.2576), and the text stands right of the line, 6.2 mm over the
    # rib's upper face as the receiver depth's does: 4.8 mm right of section C-C's
    # outboard arrow (x 0.2617, tail y 0.139) and 4 mm over the 20X callout's
    # first line, whose left end moved to 0.277 for its extension lines.
    "MiddleRibThickness": (0.2655, 0.1374),
    # The cylinder's diameter across its band, from the part's hidden
    # CylinderReference line (machinist review r10: in the front view its
    # leader landed on the rib outline that hides it).  Its text stands left
    # of the band, 2.8 mm over the line, which the dimension line covers
    # (farm r11: the dimension line prints that far below its text): right
    # of the boss's 76.20 extension line (x 0.1972), 3 mm over the 5.08's
    # text and 2.3 mm clear of the web's lower arc.
    "CylinderDia": (0.209, _top_xy(0.0, -CYLINDER_REFERENCE_Z)[1] + 0.0028),
}
# Sheet 2, back view at 1:1 (model X reversed: the plate's free edge prints at
# sheet x 0.160, the taps at 0.1747 and 0.1884 on y 0.150, the plate top at
# y 0.1525, the spring pad from the free edge to x 0.170 down to y 0.1455,
# the cylinder's circle x 0.1917..0.2171, y 0.1373..0.1627).
# The receiver stations stand above the view: 14.75 nearer, its text left of
# the free edge, 28.45 above it, its text and the pattern's mate right of the
# span (a horizontal dimension stacks a callout below the value above its
# line).  Left of the free edge the padded tap length stands inboard, and the
# row height outboard, its text above and left of the length's upper arrow
# (at x 0.147 that arrow ran through it, farm r5); the pad's width hangs
# below and left of both, outside its extension lines.  The length's line
# stays at x 0.153 (its keep's x is its line's: at 0.135, farm r13, its
# upper arrow's tail crossed the row height's shoulder), its text on a
# shoulder left of it, the shoulder under its lowest line and the block
# centred over it, so its PLATE AND PAD (x 0.123..0.153) sits on the
# shoulder and the 7.00 above it, clear of the row height's lower arrow tail
# (x 0.143, down to y 0.1436).  The pad width's block and the view's label
# drop 7 and 9 mm (into empty sheet) to leave the PLATE AND PAD room above
# the 10.00 (at 5 mm, farm r13b, the two blocks stood 3.18 apart, under the
# audit's 3.48 text separation).
BACK_KEEP = {
    "SpringSeatThickness": (0.153, 0.133),
    "SpringPadWidth": (0.095, 0.116),
    # Leave the K viewing letter and its downward arrow clear below this block.
    "ReceiverX0": (0.220, 0.1955),
    # Each tight station names the bracket (machinist review r5): the 14.75's
    # two lines stand over the row height's one, which prints above its value.
    "ReceiverX1": (0.130, 0.1745),
    "ReceiverY0": (0.143, 0.1585),
}
# The back view's label, under the pad's width.  The point is its top left.
BACK_VIEW_NOTE_XY = (0.045, 0.130)
# Sheet 1's plan names sheet 2's view: a letter arrow onto the -Z end, the
# face VIEW F looks at (fr_rocker_arm_support's VIEW B arrow).  Its tip is
# on the receiver rib's outer edge at model x 21.4 (sheet x 0.246), between
# the hex stub (x 0.2335..0.2375) and the 20X frame's leader (x 0.2545); the
# letter stands 8 mm above the edge, under that frame (bottom y 0.192).
# The leader leaves the letter's right side, VIEW_F_LEADER_DX right of the
# note's left (farm r13: note x 0.24422, leader start 0.24775), so the note
# stands that far left of the tip and the arrow drops square onto the end
# face.  Centred over the tip it leant 9 degrees, and machinist review r13
# read it as looking down onto the rib, like the plan, not at the end face.
# (note upper-left, leader tip) in sheet metres.
VIEW_LETTER_HEIGHT = 0.005
VIEW_F_LEADER_DX = 0.00353
_VIEW_F_TIP = _top_xy(21.4, PLATE_L / 2.0)
VIEW_F_ARROW = (
    (_VIEW_F_TIP[0] - VIEW_F_LEADER_DX, _VIEW_F_TIP[1] + 0.013),
    _VIEW_F_TIP,
)
# Sheet 1's end profile is VIEW G, so the plan carries its arrow too: up onto
# the +Z end (datum B) at model x 7.2 (sheet x 0.2389), 1.4 mm right of the
# hex stub, with datum B's tag moved right to leave the letter room.  The
# letter hangs below the edge and the leader leaves its left side, so the
# note stands at the tip (the left margin is squared on readback); its foot
# stays 3 mm over the 76.20/39.85 dimension line (y 0.0784).
VIEW_ARROW_SQUARE_TOL = 0.0003
_VIEW_G_TIP = _top_xy(7.2, -PLATE_L / 2.0)
VIEW_G_ARROW = (
    (_VIEW_G_TIP[0] - 0.0004, _VIEW_G_TIP[1] - 0.005),
    _VIEW_G_TIP,
)
# VIEW G's label, under the end profile, right of Detail D's letter and
# leader (x 0.2452), 1 cm over the 20X frame's leader.  The point is its top
# left.
FRONT_VIEW_NOTE_XY = (0.258, 0.2120)


def _dress_bracket_depth_callout(callout: Any) -> None:
    """Keep native receiver depths; let the drill's decimals carry its general band."""
    from win32com.client.dynamic import Dispatch as dynamic_dispatch

    required_depths = {
        "hw-threaddepth": THREAD_DEPTH,
        "hw-tapdrldepth": DRILL_DEPTH,
    }
    for raw in callout.GetHoleCalloutVariables() or ():
        # Concrete callout interfaces alias the generic metadata DISPIDs.
        variable = dynamic_dispatch(raw._oleobj_)
        variable_name = str(variable.VariableName)
        if variable_name not in required_depths:
            continue
        length = _early_bound(raw, "ICalloutLengthVariable")
        expected_depth = required_depths.pop(variable_name)
        if abs(float(length.Length) * 1000.0 - expected_depth) > 1e-5:
            raise RuntimeError(f"bracket mounting callout has wrong {variable_name}")
        observed = (
            int(variable.ToleranceType),
            float(variable.ToleranceMin) * 1000.0,
            float(variable.ToleranceMax) * 1000.0,
        )
        _telemetry.info(
            f"bracket mounting callout {variable_name} imported tolerance "
            f"(type, lower mm, upper mm) = {observed!r}"
        )
        # Callout variables own their presentation, independently of the
        # source-model dimension tolerance. Keep the full thread's MIN.
        if variable_name == "hw-threaddepth":
            variable.ToleranceType = 5  # swTolType_e.swTolMIN
            if int(variable.ToleranceType) != 5:
                raise RuntimeError(
                    "bracket mounting callout full-thread depth did not "
                    "persist as a MIN limit"
                )
            continue
        lower, upper = DRILL_DEPTH_DEVIATIONS
        ordinary_band = float(_config.title_block("linear_2pl")["display"].removeprefix("±"))
        if not (
            math.isclose(lower, -ordinary_band)
            and math.isclose(upper, ordinary_band)
        ):
            raise RuntimeError("bracket tap drill depth must retain its ordinary symmetric band")
        # As for the knife-mount drill-angle callout, suppress only the
        # variable's explicit band. Native 6.50 then inherits .XX ±0.51;
        # the source Hole Wizard dimension keeps its bounded symmetric band.
        variable.ToleranceType = 0  # swTolType_e.swTolNONE
        length.Precision = 2
        if int(variable.ToleranceType) != 0 or int(length.Precision) != 2:
            raise RuntimeError(
                f"bracket mounting callout tolerance for {variable_name} did not "
                f"persist: wanted inherited .XX band {DRILL_DEPTH_DEVIATIONS!r} "
                "mm at 2 places"
            )
    if required_depths:
        raise RuntimeError(f"bracket tap callout omits native depths: {required_depths}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open summing-lever source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
            "Stub Root View Note",
            "Middle Rib Plan Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
            "Stub Root View Note",
            "Middle Rib Plan Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Summing Lever Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing lever; gray iron; knife-edge first-class lever",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="summing lever package")
    drawing = _early_bound(drawing_model, "IDrawingDoc")
    if not drawing.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate lever geometry sheet")

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    for view in (top, iso):
        _hidden_lines_removed_without_greyed_pass(view)
    _set_tangent_edges(front, visible=False)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    # The cylinder's diameter lives in a reference sketch the part saves
    # hidden (its band shows no silhouette to dimension): the hidden-owner
    # curate shows it in the plan, the one view that dimensions it.
    top_annotations = curate_hidden_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="top",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    # The trunnion width and vertex height live in a reference sketch the
    # part saves hidden (no single hexagon dimension is either).  The detail
    # is cut and dimensioned while the part shows it; the front view shows it
    # too, because the detail's items select through it.
    with part_sketches_shown(
        adapter,
        source_model,
        KNIFE_SKETCHES,
        label="knife envelope",
        base_view=front,
    ):
        detail = _knife_detail(adapter, front)
        _hidden_lines_removed_without_greyed_pass(detail)
        _set_tangent_edges(detail, visible=False)
        detail_annotations = curate_hidden_dimensions(
            adapter,
            detail,
            keep=DETAIL_KEEP,
            view_label="knife detail",
            dimensions_by_feature=DIMENSIONS_BY_FEATURE,
        )
    _attach_radial_leaders(
        adapter, front_annotations, ("EdgeRibFrontArcR",), label="front"
    )
    _attach_radial_leaders(
        adapter, top_annotations, ("SummationArcRadius",), label="top"
    )
    _shorten_radii(adapter, top_annotations, ("SummationArcRadius",), label="top")
    # The boss's Ø19.05 takes one arrow on its near rim, no line through the
    # centre: there it crossed the anchor tap callout's leader, which runs
    # through the tap's centre (machinist review r13, rule 14).
    [boss_dia] = [
        annotation
        for annotation in top_annotations
        if dimension_name(adapter, annotation) == "AnchorOuterDia"
    ]
    set_near_side_diameter(boss_dia, "boss diameter")
    ridge_detail = _ridge_detail(adapter, detail)
    _hidden_lines_removed_without_greyed_pass(ridge_detail)
    _set_tangent_edges(ridge_detail, visible=False)
    ridge_annotations = curate_hidden_dimensions(
        adapter,
        ridge_detail,
        keep=RIDGE_DETAIL_KEEP,
        view_label="ridge detail",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    _attach_radial_leaders(
        adapter, ridge_annotations, ("KnifeRidgeRadius",), label="ridge detail"
    )
    _assert_native_max_radius(
        adapter,
        ridge_annotations,
        name="KnifeRidgeRadius",
        radius_mm=KNIFE_RIDGE_R,
        tol_type=KNIFE_RIDGE_R_TOL_TYPE,
    )
    _ridge_datum(adapter, ridge_detail)
    _apply_callouts(
        adapter,
        [*front_annotations, *top_annotations, *detail_annotations],
        label="lever geometry",
    )
    # Derived values print in parentheses: linear, so the singular helper
    # (the plural forces a Ø glyph).
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in front_annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one front {name} to mark as reference")
        set_reference_dimension(adapter, matches[0], label=f"front {name}")

    # Counter-anchor tap native callout (thread + depth) in the top plan.  Pick
    # a point on the hole rim (not its centre) so SolidWorks catches the
    # circular edge: its left quadrant, the leader then running up-left to
    # text between the boss and the Ø19.05's text -- up-left over the mid
    # rib it ran through that rib's two-line callout (farm r1 2026-10-16,
    # leader-through-text), and down-left its text took the room the boss's
    # Z location needs (machinist review r4 B3).
    anchor_tap_edge = _top_xy(TIP_X - COUNTER_R, 0.0)
    anchor_callout = add_native_hole_callout(
        adapter,
        top,
        edge_xy=anchor_tap_edge,
        callout_xy=(0.145, 0.140),
        label="anchor tap",
    )

    # Datum A is the knife-edge pivot ridge, tagged on its round in Detail E
    # (_ridge_datum).  One sweep of the plan's visible edges serves every
    # named pick below.  The ridge is the hexagon's top vertex line, y =
    # HEX_H/2 (vertex-up sketch centred on the pivot axis,
    # build_sm_summing_lever._hex_knife), rounded at R0.1 MAX: the plan shows
    # the round's two tangent lines 0.05 sheet mm either side of it, and the
    # finish names the +X one (the edge of the upper-right face it controls)
    # by entity.  A SolidWorks Top view reverses model Z on the sheet: the
    # negative sheet offset selects the +Z ridge.
    top_edges = scan_view_edges(top, label="summing lever top plan")
    ridge_x, ridge_y = KNIFE_RIDGE_TANGENT_XY
    stub_mid_z = PLATE_L / 2.0 + HEX_DEPTH / 2.0
    finish_ridge = top_edges.exact_line_through(
        (ridge_x, ridge_y, stub_mid_z), label="+Z knife-edge ridge round"
    )
    # The ridge lands in a pocket closed by the 76.20 extension line (left),
    # the 76.20/39.85 dimension line (below) and the plate (above); the default
    # 43 mm body cannot fit, so the 2.5 mm body sits inside it (layout audit:
    # the old leader crossed 76.20's extension line and datum B's leader).
    # Its V stands 4 mm right of the 5.08 rib thickness's lower arrow (at
    # 0.208 it overprinted it, machinist review r9), the text ending 2.4 mm
    # short of the stub.
    add_surface_finish(
        adapter,
        top,
        edge_entity=finish_ridge.edge,
        leader_attach_xy=_top_xy(ridge_x, -stub_mid_z),
        symbol_xy=(0.216, 0.084),
        control=surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge"),
        label="knife-edge ridge finish",
        char_height=0.0025,
    )
    # Both knife edges seat (Detail D's 2X), so the -Z ridge carries the same
    # grade (machinist review r11, rule 6: one symbol left the other edge
    # open to as-cast).  The part's control names the +Z face only, so this
    # second symbol takes its catalog grade, held equal to the control's.
    # It stands over the -Z stub: right of 21.72's upper dimension line (x
    # 0.2235), its text 3 mm over the F arrow's letter and 2 mm under the
    # 20X position frame (y 0.192); its leader enters the stub's right side.
    knife_um = surface_finish_by_key(SURFACE_FINISHES, "knife_edge_ridge").roughness_um
    if knife_um != MACHINED_UM:
        raise AssertionError(f"-Z knife-edge symbol prints {MACHINED}, not {knife_um}")
    add_surface_finish(
        adapter,
        top,
        edge_entity=top_edges.exact_line_through(
            (ridge_x, ridge_y, -stub_mid_z), label="-Z knife-edge ridge round"
        ).edge,
        leader_attach_xy=_top_xy(ridge_x, stub_mid_z),
        symbol_xy=(0.233, 0.1828),
        roughness_ra=MACHINED,
        label="-Z knife-edge ridge finish",
        char_height=0.0025,
    )
    # X location of the anchor tap from the knife-edge pivot axis (the +Z
    # trunnion ridge, the finish's): a plain title-block dimension, both
    # endpoints named -- the ridge's theoretical sharp (rule 16), an owned
    # centreline down the +Z stub, and the tap's rim on the boss top (centre
    # (TIP_X, ANCHOR_H/2, 0), the hole wizard's placement in
    # build_sm_summing_lever._counter_anchor_tap).  The mid rib's apex shares
    # this station (its 76.20 in the front profile).
    ridge_dim_edge = _top_xy(0.0, -(PLATE_L / 2.0 + 0.3 * HEX_DEPTH))
    anchor_tap_bottom = _top_xy(TIP_X, -COUNTER_R)
    ridge_axis = _ridge_centerline(adapter, top)
    anchor_rim = top_edges.circle_at(
        (TIP_X, ANCHOR_H / 2.0, 0.0),
        COUNTER_R,
        axis=(0.0, 1.0, 0.0),
        label="counter-anchor tap rim",
    )
    ridge_entity_types = ("SKETCHSEGMENT", "EDGE")
    anchor_location = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=anchor_tap_bottom,
        text_xy=(0.216, 0.0723),
        label="anchor tap X location",
        orientation="horizontal",
        entity_types=ridge_entity_types,
        entities=(ridge_axis, anchor_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        anchor_location,
        expected_mm=-TIP_X,
        label="anchor tap X location",
        entities=(ridge_axis, anchor_rim.edge),
        entity_types=ridge_entity_types,
    )

    # Anchor-tap pattern control: datum B on the plate end the seed hole is
    # located from, BASIC row-X / start-Z / pitch coordinates off A|B, a
    # native thread callout, and a 20X position frame -- the inspectable
    # pattern definition (the notes no longer carry these numbers as prose).
    # The plan prints model +Z DOWN the sheet, so the end at the bottom of the
    # view is the +Z end: the seed hole (HOLE_Z_LAST, HOLE_END_OFFSET_LAST off
    # that end) is the bottom hole of the column.
    # Hang B's tag straight down right of the +Z trunnion stub, between it and
    # the 39.85 extension line: left of the stub it sat in the finish leader's
    # only path (layout audit); the 20X callout now hangs on the middle hole,
    # well away from this tag.  It stands 10.2 mm right of the pick, clear of
    # VIEW G's letter beside the stub (at 9.0 its frame touched the letter,
    # farm r16).
    # Every datum and dimension here names its entities: a coordinate
    # hit-test on the plate corner resolved to the rib flange 5.08 mm inboard
    # (datum B on the flange, start Z reading 3.35 for 8.43 -- #1105), and a
    # value check alone cannot tell the seed rim from the nineteen others at
    # the same X or any equal-pitch pair. The picks below are the rims'
    # model positions (the hole wizard's seed at HOLE_Z_LAST, the pattern
    # marching -Z by CHANNEL_PITCH; build_summing_lever).
    plate_end_edge = _top_xy(10.0, -PLATE_L / 2.0)
    end_edge = _end_face_edge(top_edges, x_mm=10.0)
    add_datum_feature(
        adapter,
        top,
        edge_entity=end_edge.edge,
        symbol_xy=(plate_end_edge[0] + 0.0102, plate_end_edge[1] - 0.0035),
        datum="B",
        label="plate +Z end face",
    )
    # Z location of the anchor boss (machinist review r4 B3: the plan located
    # it only in X): datum B to the tap's centre, half the plate length.  The
    # pick sits at the end line's inboard end (the rib's top edge at the
    # cylinder), so the extension line runs left under the web's lower arc,
    # not along the outline; the text stands in the span left of the boss,
    # under the anchor tap's callout and right of the Ø19.05's leader.
    boss_z_pick = _top_xy(
        min(point[0] for point in end_edge.line) + 1.0, -PLATE_L / 2.0
    )
    boss_z = add_edge_dimension(
        adapter,
        top,
        p0=boss_z_pick,
        p1=anchor_tap_edge,
        text_xy=(0.150, 0.111),
        label="anchor boss Z location",
        orientation="vertical",
        entities=(end_edge.edge, anchor_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        boss_z,
        expected_mm=PLATE_L / 2.0,
        label="anchor boss Z location",
        entities=(end_edge.edge, anchor_rim.edge),
    )
    # The mid rib shares the boss's station (machinist review r6: its 5.08
    # thickness had no location along the plate), so this one 76.20 names
    # both under its value.
    boss_z_display = _early_bound(boss_z, "IDisplayDimension")
    boss_z_display.SetText(4, BOSS_Z_CALLOUT)  # swDimensionTextCalloutBelow
    if "MID RIB" not in str(boss_z_display.GetText(4) or ""):
        raise RuntimeError(
            f"anchor boss Z callout did not persist: {boss_z_display.GetText(4)!r}"
        )
    seed_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, HOLE_Z_LAST),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole seed rim",
    )
    second_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, HOLE_Z_LAST - CHANNEL_PITCH),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole second rim",
    )
    seed_rim_right = _top_xy(HOLE_X + HOLE_DIA / 2.0, -HOLE_Z_LAST)
    # The start-Z and pitch texts ride with the hole column (tuned at the 0.8
    # arm offset, seed centre at sheet y 0.0961), so a station move keeps them.
    seed_y = seed_rim_right[1]
    row_x = add_edge_dimension(
        adapter,
        top,
        p0=ridge_dim_edge,
        p1=seed_rim_right,
        text_xy=(0.248, 0.0723),
        label="spring-hole row X",
        orientation="horizontal",
        entity_types=ridge_entity_types,
        entities=(ridge_axis, seed_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        row_x,
        expected_mm=HOLE_X,
        label="spring-hole row X",
        entities=(ridge_axis, seed_rim.edge),
        entity_types=ridge_entity_types,
    )
    set_basic_dimension(adapter, row_x, label="spring-hole row X")
    seed_rim_top = _top_xy(HOLE_X, -HOLE_Z_LAST + HOLE_DIA / 2.0)
    # The start Z (12.75) spans 6.4 mm of sheet (0.0919..0.0983); text between
    # the arrows would sit on its own line (3.35 there stood on 7.06's extension
    # line and 152.40's), so it hangs above the span.  Each of these vertical
    # dimensions draws its line at its text's right end (farm r1 2026-10-16:
    # the 19X 7.06 text 0.275..0.2958 with its line there), so the 12.75 text
    # starts 4 mm right of that line -- at 0.292 its shoulder crossed it -- and
    # stays left of the 152.40 line (0.396).
    start_z = add_edge_dimension(
        adapter,
        top,
        p0=plate_end_edge,
        p1=seed_rim_top,
        text_xy=(0.300, seed_y + 0.0099),
        label="spring-hole start Z",
        orientation="vertical",
        entities=(end_edge.edge, seed_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        start_z,
        expected_mm=HOLE_END_OFFSET_LAST,
        label="spring-hole start Z",
        entities=(end_edge.edge, seed_rim.edge),
    )
    set_basic_dimension(adapter, start_z, label="spring-hole start Z")
    second_rim_bottom = _top_xy(
        HOLE_X, -HOLE_Z_LAST + CHANNEL_PITCH - HOLE_DIA / 2.0
    )
    pitch = add_edge_dimension(
        adapter,
        top,
        p0=seed_rim_top,
        p1=second_rim_bottom,
        text_xy=(0.275, seed_y + 0.0054),
        label="spring-hole pitch",
        orientation="vertical",
        entities=(seed_rim.edge, second_rim.edge),
    )
    assert_dimension_measures(
        adapter,
        pitch,
        expected_mm=CHANNEL_PITCH,
        label="spring-hole pitch",
        entities=(seed_rim.edge, second_rim.edge),
    )
    set_basic_dimension(adapter, pitch, label="spring-hole pitch")
    # Twenty taps are nineteen pitches: the count rides the BASIC pitch as
    # its prefix, read back because SetText reports nothing.
    pitch_display = _early_bound(pitch, "IDisplayDimension")
    pitch_prefix = f"{HOLE_COUNT - 1}X "
    pitch_display.SetText(1, pitch_prefix)  # swDimensionTextPrefix
    if str(pitch_display.GetText(1) or "") != pitch_prefix:
        raise RuntimeError(
            f"spring-hole pitch count {pitch_prefix!r} did not persist: "
            f"{pitch_display.GetText(1)!r}"
        )
    # The 20X callout hangs on hole 7 (three below the middle), text in the
    # open field right of the column: with 44.45 below the plate end,
    # 0.100..0.185 there holds nothing but section C-C's free-edge arrow,
    # whose letter prints at x 0.259..0.265, y 0.136..0.143 (farm r3: the
    # leader off the middle hole, y 0.1336, ran 6.2 mm through the letter,
    # then at y 0.129..0.1355). Hole 7 (y 0.1230) keeps the leader clear
    # under it; the text centres on x 0.310 so the process line's 67 mm
    # (from x 0.277) clears that letter and the mid rib's 5.08 extension
    # lines, which end at x 0.267 (TOP_KEEP).  Every callout on
    # the end hole had to leave it downward and so crossed the plate-end
    # extension lines of 152.40 and the start-Z dimension -- steepening the
    # leader only traded that for text-on-line and arrow-near-text against
    # the 39.85 arrowhead and the start-Z overshoot (runs
    # 20260928T130915425Z, ...131249806Z, ...131507773Z).
    callout_hole_z = HOLE_Z_LAST - (HOLE_COUNT // 2 - 3) * CHANNEL_PITCH
    callout_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, callout_hole_z),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole callout rim",
    )
    spring_callout = add_native_hole_callout(
        adapter,
        top,
        edge=callout_rim.edge,
        callout_xy=(0.310, _top_xy(HOLE_X, -callout_hole_z)[1] + 0.0015),
        label="spring-hole pattern",
        process=SPRING_TAP_CALLOUT_PROCESS,
    )
    # The Top view reverses model Z, so -HOLE_Z_FIRST prints the seed hole at
    # the TOP of the column. The frame sits above the +Z trunnion stub with
    # its right stub ending over the rim, so the leader drops just past the
    # receiver rib's end and runs only ~5 mm over the plate (the diagonal
    # from 0.175 crossed the stub and flange: leader-over-part, 24 mm).  The
    # seed rim is named by entity and the arrow set on its upper-left
    # quadrant: a hit-test at its left quadrant landed the arrow on the
    # rib's end corner 1 mm left of the hole (machinist review r9).
    seed_rim = top_edges.circle_at(
        (HOLE_X, PLATE_T / 2.0, HOLE_Z_FIRST),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole seed rim",
    )
    rim_step = HOLE_DIA / 2.0 * math.sqrt(0.5)
    add_feature_control_frame(
        adapter,
        top,
        edge_entity=seed_rim.edge,
        leader_attach_xy=_top_xy(HOLE_X - rim_step, -HOLE_Z_FIRST + rim_step),
        frame_xy=(0.2133, 0.199),
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_MM["spring-hole pattern position"],
        datums=("A", "B"),
        diameter=True,
        quantity="20X",
        label="spring-hole pattern position",
    )
    check_plate_thickness = _plate_section(adapter, top)
    _tap_section(adapter, front)
    _add_view_arrow(adapter, top, BACK_VIEW_LETTER, VIEW_F_ARROW)
    _add_view_arrow(adapter, top, FRONT_VIEW_LETTER, VIEW_G_ARROW)
    add_property_linked_note(adapter, "Front View Note", *FRONT_VIEW_NOTE_XY)

    # The isometric's view label, under the iso.
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.205)

    if not drawing.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate bracket receiver sheet")
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=(1, 1))
    receiver_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4),
    )
    for view in (back, receiver_iso):
        set_hidden_lines_removed(adapter, view)
    _set_tangent_edges(back, visible=False)
    back_edges = scan_view_edges(back, label="bracket receiver face")
    mounting_rims = _mounting_rims(back_edges)
    # Right of the view, where the 2026-10-09 render seated it.
    mounting_callout = add_native_hole_callout(
        adapter, back, edge=mounting_rims[0].edge,
        callout_xy=(0.292, 0.115), label="two blind bracket mounting taps",
        process=BRACKET_TAP_CALLOUT_PROCESS,
    )
    _dress_bracket_depth_callout(mounting_callout)
    back_annotations = curate_hidden_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="bracket receiver",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    _apply_callouts(adapter, back_annotations, label="bracket receiver")
    _receiver_row_centerline(adapter, back)
    stub_root = _stub_root_view(adapter)
    stub_annotations = curate_view_dimensions(
        adapter,
        stub_root,
        keep=STUB_ROOT_KEEP,
        view_label="stub root",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    _attach_radial_leaders(
        adapter, stub_annotations, ("StubRootRadius",), label="stub root"
    )
    _apply_callouts(adapter, stub_annotations, label="stub root")
    _assert_native_max_radius(
        adapter,
        stub_annotations,
        name="StubRootRadius",
        radius_mm=STUB_ROOT_R,
        tol_type=INSIDE_CORNER_R_TOL_TYPE,
    )
    add_property_linked_note(adapter, "Stub Root View Note", *STUB_ROOT_NOTE_XY)
    # Down onto the rib arc's top, above the stub: K is a plan, not another
    # end view.  The 28.45 receiver block stands 14 mm higher to clear it.
    root_tip = model_point_in_view(
        adapter, back, _metres((0.0, ARC_R, -PLATE_L / 2.0)),
        label="K viewing arrow",
    )
    _add_view_arrow(
        adapter,
        back,
        STUB_ROOT_VIEW_LETTER,
        (
            (root_tip[0] - VIEW_F_LEADER_DX, root_tip[1] + 0.013),
            root_tip,
        ),
    )
    rib_end = _rib_end_detail(adapter, back)
    _hidden_lines_removed_without_greyed_pass(rib_end)
    _set_tangent_edges(rib_end, visible=True)
    rib_annotations = curate_view_dimensions(
        adapter,
        rib_end,
        keep=RIB_END_KEEP,
        view_label="rib end",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    _attach_radial_leaders(
        adapter, rib_annotations, ("RibEndRadius",), label="rib end"
    )
    _apply_callouts(adapter, rib_annotations, label="rib end")
    _assert_native_max_radius(
        adapter,
        rib_annotations,
        name="RibEndRadius",
        radius_mm=RIB_END_R,
        tol_type=INSIDE_CORNER_R_TOL_TYPE,
    )
    # The view label below the pad's width, left of the view and the receiver
    # callout's leader: at (0.205, 0.172) that leader ran through it (farm r1
    # 2026-10-16, leader-through-text).
    add_property_linked_note(adapter, "Back View Note", *BACK_VIEW_NOTE_XY)
    # The repeated isometric's label, where sheet 1 puts its own (machinist
    # review r12: unlabelled on this sheet).
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.205)
    _, _, check_middle_rib = _middle_rib_section(
        adapter, neighboring_views=(back, receiver_iso, stub_root, rib_end)
    )
    check_thread_annotations = _finished_thread_annotation_check(
        adapter,
        (
            ("anchor tap", top, anchor_callout),
            ("spring-hole pattern", top, spring_callout),
            ("two blind bracket mounting taps", back, mounting_callout),
        ),
    )
    _remove_redundant_thread_notes(adapter)
    check_thread_annotations()

    def check_corner_radius_landings() -> None:
        if not drawing.ActivateSheet(SHEET_NAMES[1]):
            raise RuntimeError("failed to activate receiver sheet for radius arrow proof")
        for view, radius_annotations, name, arc_mm in (
            (stub_root, stub_annotations, "StubRootRadius", STUB_ROOT_ARC_MM),
            (rib_end, rib_annotations, "RibEndRadius", RIB_END_ARC_MM),
        ):
            _assert_radius_arrow_lands(
                adapter, view, radius_annotations, name=name, arc_mm=arc_mm
            )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Lever Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        # This recipe deletes and proves its actual note inventory, as top-frame
        # does; the shared exact-count guard remains unchanged for other recipes.
        # Recheck after the final rebuild, before either drawing or PDF is saved.
        settled_checks=(
            check_thread_annotations, check_plate_thickness, check_corner_radius_landings,
            check_middle_rib,
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

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
shows a 1:2 front profile (the boss, web and the rib outline every rib
shares), a 4:1 detail of the trunnion envelope and its knife-edge round, a
1:2 top plan (plate, ribs, cylinder, summation web, trunnion length, the
anchor taps and their pattern control, and the VIEW F arrow onto the -Z
end), a 1:1 partial section C-C of the plate's thickness, a 4:1 section H-H
cut in the front profile along the outer receiver tap through the -Z end
rib, and a 1:4 isometric; sheet 2 shows VIEW F at 1:1, the -Z end with the
two bracket receiver taps and the spring-anchor pad under the plate they sit
in, so the end rib's slant over each tap reads, and the tap row's centreline
through the hex centre with the plate top's (2.54) REF from it.  Sheet 1
runs at 1:2.

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
from _drawing_leaders import set_near_side_diameter
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
    REFERENCE_DIMENSIONS,
    SPRING_TAP_CALLOUT_PROCESS,
)
from sm_summing_lever_spec import (
    ANCHOR_H,
    ANCHOR_R,
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
    KNIFE_RIDGE_R,
    KNIFE_RIDGE_R_TOL_TYPE,
    KNIFE_RIDGE_TANGENT_XY,
    PLATE_L,
    PLATE_T,
    PLATE_W,
    RIDGE_ANGLE_DEG,
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
# The crop circle's centre, on the mid-plane 4.75 in from the end face, lands
# on TAP_SECTION_CENTER; its radius holds the end face's corners (5.06
# half-height at x 29.7, 6.94 from the centre) and leaves the plate's faces
# 0.19 past the break, so the plate ends at the break line.
_TAP_SECTION_ANCHOR_MM = (TAP_SECTION_HOLE[0], 0.0, TAP_SECTION_HOLE[2] + 4.75)
TAP_SECTION_CROP_RADIUS = 7.2
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

# The -Z end rib's banded depth is named by
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
    """Stop each radial leader at its own arc.

    ``ArcExtensionLineOrOppositeSide`` defaults to True, which sweeps the
    R138.8 summation arc through the top view and trails the R15.24 rib leader
    across the front view; ``SolidLeader`` defaults to True on this template
    and rules the leader on to the arc centre, off the view for R138.8 (both
    seen on the 2026-10 summing-lever renders).  Both are bool properties, so
    each assignment is proven only by reading it back.
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
    """A letter arrow on the plan that names a removed view: square onto the
    end face it looks at."""
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


def _assert_knife_ridge_radius(adapter: Any, annotations: list[Any]) -> None:
    """Prove Detail E's KnifeRidgeRadius prints the part's R MAX: radial,
    measuring KNIFE_RIDGE_R, the native swTolMAX the part set
    (draw_ch_pivot_bracket._dress_corner_radius's readback)."""
    found = [
        annotation
        for annotation in annotations
        if dimension_name(adapter, annotation) == "KnifeRidgeRadius"
    ]
    if len(found) != 1:
        raise RuntimeError(
            f"expected one KnifeRidgeRadius in the ridge detail, found {len(found)}"
        )
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    if bool(display.Diametric):
        raise RuntimeError("the imported knife-ridge radius is not radial")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if int(tolerance.Type) != KNIFE_RIDGE_R_TOL_TYPE:
        raise RuntimeError(
            f"KnifeRidgeRadius lost its native MAX type: {int(tolerance.Type)}"
        )
    if not math.isclose(
        float(dimension.SystemValue), KNIFE_RIDGE_R / 1000.0, abs_tol=1e-9
    ):
        raise RuntimeError("KnifeRidgeRadius does not measure the ridge round")
    _telemetry.info(f"knife ridge radius: text {display.GetText(1)!r}, MAX type")


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


def _plate_section(adapter: Any, top: Any) -> list[Any]:
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
    return annotations


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
    """Set a sheet-1 ``view`` hidden-lines-removed, never showing hidden lines.

    set_hidden_lines_removed passes through hidden-lines-visible to force a
    regen.  That pass is where the bracket taps' "#2-56 Tapped Hole" label,
    their threads hidden behind the plate in every sheet-1 view, grew on some
    builds only (#1591, farm 2026-10-17): on the plan right after its pass
    (ba33167e's stage log), on section C-C (493638fa), on neither in
    2fa756e1 and 802e4117 -- the one note the sweep's count varied by.  Each
    caller sets the view straight after creating it, before anything is
    attached, so the regen is not needed.  Farm seats place all six sheet-1
    views in HLR already (5a58480d), where the set is a no-op; that build,
    on the seat behind both 9-label builds, swept 8 and its PDF is
    pixel-identical to r18b's, which still had the pass.
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


# VIEW F ties the plate top face, the origin of the bracket row's 2.54 +-0.05,
# to the trunnion axis (machinist gate 2026-10-17 on #1607: the row's
# centreline stopped at the holes, and only section C-C's 5.08 implied the
# plate's symmetry).  The plate is extruded mid-plane on the pivot
# (build_sm_summing_lever._coefficients_plate), so its top stands PLATE_T/2
# over the hex centre and the row lies on that axis.  An owned centreline
# runs from the free-edge side through both taps and the hex centre,
# RECEIVER_AXIS_OVERRUN_MM past the station and past the hex's flats; a
# (2.54) REF stands from it to the plate top at RECEIVER_AXIS_STATION_MM,
# where the -Z end shows the plate's own top edge (the end rib steps up at
# build_sm_summing_lever.RIB_PLATE_REACH, 35.75).  Its dimension line stands
# 2.8 mm inside the free edge, its text RECEIVER_AXIS_TEXT_RISE_MM above the
# plate top: between the free edge's and the outer tap's extension lines,
# under the 14.75's dimension line and above the rib's slant.
RECEIVER_AXIS_STATION_MM = 37.5
RECEIVER_AXIS_OVERRUN_MM = 2.0
RECEIVER_AXIS_TEXT_RISE_MM = 7.5


def _receiver_plate_top_edge(edges: ViewEdges) -> ViewEdge:
    """The -Z end's plate-top line under the axis reference's station.

    VIEW F looks at the -Z end face (z = -PLATE_L/2): from the end rib's step
    to the free edge, its only visible line at y = PLATE_T/2 is the plate's
    own top edge. Anything else is a changed model and fails loud.
    """
    z_mm = -PLATE_L / 2.0
    y_mm = PLATE_T / 2.0
    x_mm = RECEIVER_AXIS_STATION_MM
    matches = [
        item
        for item in edges.lines
        if all(abs(point[2] - z_mm) < 1e-6 and abs(point[1] - y_mm) < 1e-6 for point in item.line)
        and min(point[0] for point in item.line) - 1e-6 <= x_mm
        and x_mm <= max(point[0] for point in item.line) + 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"summing lever -Z plate top: expected one visible line at "
            f"y={y_mm:g} z={z_mm:g} spanning x={x_mm:g} in the {edges.label!r} "
            f"scan, found {[item.line for item in matches]}"
        )
    return matches[0]


def _receiver_axis_reference(adapter: Any, back: Any, edges: ViewEdges) -> Any:
    """VIEW F's row centreline through the hex centre and the (2.54) REF from
    it to the plate top (see RECEIVER_AXIS_STATION_MM)."""
    z_mm = -PLATE_L / 2.0
    station = RECEIVER_AXIS_STATION_MM
    axis = _owned_centerline(
        adapter,
        back,
        (
            (station + RECEIVER_AXIS_OVERRUN_MM, 0.0, z_mm),
            (-(HEX_W / 2.0 + RECEIVER_AXIS_OVERRUN_MM), 0.0, z_mm),
        ),
        label="receiver row centreline",
    )
    plate_top = _receiver_plate_top_edge(edges)
    axis_pick, top_pick, text_xy = model_points_in_view(
        adapter,
        back,
        [
            _metres((station, 0.0, z_mm)),
            _metres((station, PLATE_T / 2.0, z_mm)),
            _metres((station, PLATE_T / 2.0 + RECEIVER_AXIS_TEXT_RISE_MM, z_mm)),
        ],
        label="receiver axis reference",
        names=("axis", "plate top", "text"),
    )
    entity_types = ("SKETCHSEGMENT", "EDGE")
    reference = add_edge_dimension(
        adapter,
        back,
        p0=axis_pick,
        p1=top_pick,
        text_xy=text_xy,
        label="plate top from the trunnion axis",
        orientation="vertical",
        entity_types=entity_types,
        entities=(axis, plate_top.edge),
    )
    assert_dimension_measures(
        adapter,
        reference,
        expected_mm=PLATE_T / 2.0,
        label="plate top from the trunnion axis",
        entities=(axis, plate_top.edge),
        entity_types=entity_types,
    )
    set_reference_dimension(
        adapter,
        _early_bound(reference, "IDisplayDimension").GetAnnotation(),
        label="plate top from the trunnion axis",
    )
    return reference


# Front profile at 1:2 (2026-10-15 baseline render): the pivot axis prints at
# (0.2352, 0.2352), the boss spans x 0.1925..0.2021, the end rib's R15.24 arc
# 7.6 mm round the axis, the web bar y 0.2338..0.2363 from the boss to that
# arc, the plate tip x 0.2535..0.2575.  Every rib shares the +Z end rib's
# outline, so its dimensions sit here once: the 35.75 reach above the view,
# the rib end's step over the plate top right of the plate tip, the rib arc
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
    # Left of the -Z stub, under the 20X frame, its text centred on its line:
    # 2.8 mm left of the stub (at x 0.226 it touched datum A's old arrow, r6), its
    # lower arrow 2.5 mm right of the R138.85.  Both stubs are one prism, so the
    # stub's length is the hidden KnifeStubReference's, along its -X side.
    "KnifeStubLength": (0.2235, 0.1735),
    # Left of the +Z end rib, above its span: below it the finish symbol and
    # the 76.20/39.85 row leave no room, and the web's lower arc reaches the
    # cylinder at x 0.226 there.  The text spans x 0.1979..0.2095, right of
    # the 76.20 X location's extension line (x 0.1972); the lower arrow
    # stands 3.8 mm left of the finish symbol's text; the text stands above
    # the boss Z location's datum-B extension line (y 0.0919).
    "EdgeRibThickness": (0.2095, 0.1035),
    # Outside the part, right of the free edge (machinist review b4df34ad9
    # r2/r3: inside the web, between the R138.85, the boss and the cylinder,
    # it read as crowded), as the -Z rib's 7.30 does: its extension lines run
    # from the rib's end across the hole column (one hole sits on the rib's
    # mid-plane, its rim 0.5 mm inside them) to the line 8 mm past the free
    # edge (x 0.2576), and the text stands right of the line, 6.2 mm over the
    # rib's upper face as the 7.30's does: 4.8 mm right of section C-C's
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
    "SpringPadWidth": (0.130, 0.116),
    "ReceiverX0": (0.220, 0.1815),
    # Each tight station names the bracket (machinist review r5): the 14.75's
    # two lines stand over the row height's one, which prints above its value.
    "ReceiverX1": (0.130, 0.1745),
    "ReceiverY0": (0.143, 0.1585),
}
# The back view's label, under the pad's width.  The point is its top left.
BACK_VIEW_NOTE_XY = (0.110, 0.100)
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Back View Note",
            "Front View Note",
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
    _assert_knife_ridge_radius(adapter, ridge_annotations)
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
    _plate_section(adapter, top)
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
    back_edges = scan_view_edges(back, label="bracket receiver face")
    mounting_rims = _mounting_rims(back_edges)
    # Right of the view, where the 2026-10-09 render seated it.
    mounting_callout = add_native_hole_callout(
        adapter, back, edge=mounting_rims[0].edge,
        callout_xy=(0.292, 0.115), label="two blind bracket mounting taps",
        process=BRACKET_TAP_CALLOUT_PROCESS,
    )
    from win32com.client.dynamic import Dispatch as dynamic_dispatch
    required_depths = {
        "hw-threaddepth": THREAD_DEPTH,
        "hw-tapdrldepth": DRILL_DEPTH,
    }
    for raw in mounting_callout.GetHoleCalloutVariables() or ():
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
        # A hole callout variable carries its OWN tolerance (SW 2016+:
        # ICalloutVariable.ToleranceType; the model IDimensionTolerance does
        # not override it). Farm 2026-10-09: the cosmetic-thread depth band
        # did not reach hw-threaddepth, so author it here.  The full thread
        # prints as a minimum (machinist review r5/r6, rule 4): the drill's
        # own band bounds how deep a bottoming tap can cut, and the joint
        # proofs' shallowest thread (4.90) is under the printed 4.95.
        if variable_name == "hw-threaddepth":
            variable.ToleranceType = 5  # swTolType_e.swTolMIN
            if int(variable.ToleranceType) != 5:
                raise RuntimeError(
                    "bracket mounting callout full-thread depth did not "
                    "persist as a MIN limit"
                )
            continue
        # The drill depth is one-sided, +0.10/0 (joint DRILL_DEPTH_DEVIATIONS).
        lower, upper = DRILL_DEPTH_DEVIATIONS
        variable.ToleranceType = 2  # swTolType_e.swTolBILAT
        variable.ToleranceMin = lower / 1000.0
        variable.ToleranceMax = upper / 1000.0
        length.TolerancePrecision = 2
        if (
            int(variable.ToleranceType) != 2
            or abs(float(variable.ToleranceMin) * 1000.0 - lower) > 1e-5
            or abs(float(variable.ToleranceMax) * 1000.0 - upper) > 1e-5
            or int(length.TolerancePrecision) != 2
        ):
            raise RuntimeError(
                f"bracket mounting callout tolerance for {variable_name} did not "
                f"persist: wanted swTolBILAT (lower, upper) {DRILL_DEPTH_DEVIATIONS!r} "
                "mm at 2 places"
            )
    if required_depths:
        raise RuntimeError(f"bracket tap callout omits native depths: {required_depths}")
    back_annotations = curate_hidden_dimensions(
        adapter,
        back,
        keep=BACK_KEEP,
        view_label="bracket receiver",
        dimensions_by_feature=DIMENSIONS_BY_FEATURE,
    )
    _apply_callouts(adapter, back_annotations, label="bracket receiver")
    _receiver_axis_reference(adapter, back, back_edges)
    # The view label below the pad's width, left of the view and the receiver
    # callout's leader: at (0.205, 0.172) that leader ran through it (farm r1
    # 2026-10-16, leader-through-text).
    add_property_linked_note(adapter, "Back View Note", *BACK_VIEW_NOTE_XY)
    # The repeated isometric's label, where sheet 1 puts its own (machinist
    # review r12: unlabelled on this sheet).
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.205)
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
        settled_checks=(check_thread_annotations,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

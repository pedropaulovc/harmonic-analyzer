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
print controls thread identity and position, never a seat bore. Sheet 1
shows the 1:2 end profile and top plan and a 1:4 shaded isometric.
Sheet 2 shows VIEW F at 1:1, a complete 10:1 knife detail D cut from that
view, and the repeated shaded isometric. VIEW F carries the blind bracket
receivers, the uniform coefficient plate's visible free-end thickness and
the receiver row's centreline through the hex centre.
The ordinary views and native receiver drill/thread-depth callout retain
the manufacturing definition without auxiliary sections.

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
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    set_basic_dimension,
    set_dimension_callouts,
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
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import MACHINED, MACHINED_UM, surface_finish_by_key
import _telemetry
from magnifying_bracket_joint_layout import (
    DRILL_DEPTH,
    DRILL_DEPTH_DEVIATIONS,
    LEVER_HOLE_POINTS,
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
    SPRING_TAP_CALLOUT_PROCESS,
)
from sm_summing_lever_spec import (
    ANCHOR_H,
    ANCHOR_R,
    CHANNEL_PITCH,
    COEFFICIENT_BOTTOM_Y,
    COEFFICIENT_T,
    COEFFICIENT_TOP_Y,
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
    PLATE_W,
    RIB_BLEND_R,
    RIB_BLEND_R_TOL_TYPE,
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
# The receiver end profile occupies sheet 2's lower-right field, leaving
# the complete knife detail its own generous field on the left.
BACK_CENTER = (0.300, 0.100)
SHEET_NAMES = ("Lever Geometry", "Bracket Receiver")

# One complete 10:1 knife detail in sheet 2's open left field. A 6 mm model
# fence holds the entire envelope and ridge round without the pivot rib.
# It is cut from VIEW F so no extra parent view or cross-sheet move is needed.
DETAIL_LETTER = "D"
DETAIL_CENTER = (0.115, 0.150)
DETAIL_SCALE = (10.0, 1.0)
DETAIL_RADIUS_MM = 6.0
DETAIL_LABEL_XY = (0.115, 0.071)
# The parent circle's letter sits above the -Z knife vertex in VIEW F,
# away from the receiver stations to its left.
DETAIL_LETTER_OFFSET = (0.0, 0.016)
KNIFE_SKETCHES = ("KnifeEnvelopeReference",)
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

    The plan shows the common positive rib's outer top edge up to its
    tangent blend into the coefficient plate. Beyond the blend the actual
    plate-top edge is visible. Inboard flange and underside edges cannot
    substitute for this outer end face.
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


def _knife_detail(adapter: Any, back: Any) -> Any:
    """The complete native 10:1 knife envelope and ridge-round detail."""
    return _detail_view(
        adapter,
        back,
        centre_mm=(0.0, 0.0, -PLATE_L / 2.0 - HEX_DEPTH),
        radius_m=DETAIL_RADIUS_MM / 1000.0,
        at_xy=DETAIL_CENTER,
        scale=DETAIL_SCALE,
        letter=DETAIL_LETTER,
        label_xy=DETAIL_LABEL_XY,
        letter_offset=DETAIL_LETTER_OFFSET,
        label="knife detail",
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
    """Prove Detail D's KnifeRidgeRadius prints the part's R MAX: radial,
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


def _assert_rib_root_radius(adapter: Any, annotations: list[Any]) -> None:
    """Read the native R1 MAX root/profile blend; never type its value."""
    found = [
        raw for raw in annotations
        if dimension_name(adapter, raw) == "RibRootRadius"
    ]
    if len(found) != 1:
        raise RuntimeError("expected one native RibRootRadius in VIEW G")
    annotation = _early_bound(found[0], "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        display.Diametric is not False
        or int(tolerance.Type) != RIB_BLEND_R_TOL_TYPE
        or not math.isclose(
            float(dimension.SystemValue), RIB_BLEND_R / 1000.0,
            rel_tol=0.0, abs_tol=1e-9,
        )
    ):
        raise RuntimeError("RibRootRadius lost its native radial value or MAX band")


# Datum A's box stands above the actual ridge round in Detail D.
RIDGE_DATUM_RISE = 0.001


def _ridge_datum(adapter: Any, detail: Any) -> Any:
    """Datum A on the knife-edge ridge itself, seen end-on in Detail D: the
    tag stands on the R0.1 round's arc at the vertex. In the plan, A hung
    on the -Z ridge's tangent line down the stub's middle, which machinist
    review r9 read as a flat face, leaving no basic from A to the 20 holes;
    end-on it can only be the ridge line, the knife-edge pivot axis that the
    39.85 basic and the web arcs' "AXIS A" both name."""
    z_mm = -PLATE_L / 2.0 - HEX_DEPTH
    half = math.radians(RIDGE_ANGLE_DEG) / 2.0
    centre_y = HEX_H / 2.0 - KNIFE_RIDGE_R / math.sin(half)
    edges = scan_view_edges(detail, label="knife detail datum")
    ridge_round = edges.circle_at(
        (0.0, centre_y, z_mm),
        KNIFE_RIDGE_R,
        axis=(0.0, 0.0, 1.0),
        label="-Z knife-edge ridge round",
    )
    crest, vertex = model_points_in_view(
        adapter,
        detail,
        [
            _metres((0.0, centre_y + KNIFE_RIDGE_R, z_mm)),
            _metres((0.0, HEX_H / 2.0, z_mm)),
        ],
        label="knife ridge datum",
        names=("crest", "vertex"),
    )
    return add_datum_feature(
        adapter,
        detail,
        edge_entity=ridge_round.edge,
        leader_attach_xy=crest,
        symbol_xy=(vertex[0], vertex[1] + RIDGE_DATUM_RISE),
        datum="A",
        label="knife-edge pivot axis",
        position_tolerance_m=0.003,
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


def _plate_thickness_check(
    adapter: Any, view: Any, annotations: list[Any],
) -> Callable[[], None]:
    """Preserve the imported free-end sketch thickness in VIEW F.

    The Front-plane slab profile authors this dimension on its X=PLATE_W
    vertical edge. Native witness origins, not a coincident seven-millimetre
    value, must still tie it to the visible top and bottom free-end edges.
    No synthetic witness move or value, tolerance, precision or gap edit.
    """
    label = "VIEW F PlateThickness"
    slop = 1e-8
    matches = [
        raw for raw in annotations
        if dimension_name(adapter, raw) == "PlateThickness"
    ]
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one imported thickness annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    view = _early_bound(view, "IView")

    def finite(value: Any) -> bool:
        return type(value) in (int, float) and math.isfinite(value)

    def same(first: Any, second: Any) -> bool:
        result = adapter.swApp.IsSame(first, second)
        return type(result) is int and result == 1

    def model_state() -> tuple[Any, Any, str, float, tuple[int, float, float]]:
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        if drawing.ActivateSheet(SHEET_NAMES[1]) is not True:
            raise RuntimeError(f"{label}: could not activate its receiver sheet")
        count = view.GetAnnotationCount()
        owned = view.GetAnnotations()
        if (
            type(count) is not int or count < 1
            or not isinstance(owned, (tuple, list)) or len(owned) != count
        ):
            raise RuntimeError(f"{label}: invalid native view annotation inventory")
        kind, owner_type = annotation.GetType(), annotation.OwnerType
        if (
            type(kind) is not int or kind != 4
            or type(owner_type) is not int or owner_type != 0
            or annotation.IsDangling() is not False
            or sum(same(raw, annotation) for raw in owned) != 1
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
            or name.split("@")[:2] != ["PlateThickness", "PlateProfile"]
            or not finite(value)
            or abs(value - COEFFICIENT_T / 1000.0) > 1e-12
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

    def geometry() -> tuple[tuple[float, float], tuple[float, float]]:
        z_mm = -PLATE_L / 2.0
        edges = scan_view_edges(view, label="coefficient plate free end")
        points = []
        for face, y_mm in (
            ("bottom", COEFFICIENT_BOTTOM_Y), ("top", COEFFICIENT_TOP_Y),
        ):
            free_end = (PLATE_W, y_mm, z_mm)
            edge = edges.exact_line_through(
                (PLATE_W - 0.5, y_mm, z_mm), label=f"coefficient {face} edge",
            )
            if (
                min(math.dist(point, free_end) for point in edge.line) > 1e-6
                or any(
                    abs(point[1] - y_mm) > 1e-6 or abs(point[2] - z_mm) > 1e-6
                    for point in edge.line
                )
            ):
                raise RuntimeError(f"{label}: {face} edge does not reach the actual free end")
            points.append(model_point_in_view(
                adapter, view, _metres(free_end), label=f"{label} {face}",
            ))
        inset = model_point_in_view(
            adapter, view, _metres((PLATE_W - 1.0, COEFFICIENT_BOTTOM_Y, z_mm)),
            label=f"{label} inboard",
        )
        if any(
            len(point) != 2 or not all(finite(v) for v in point)
            for point in (*points, inset)
        ):
            raise RuntimeError(f"{label}: nonfinite projected plate geometry")
        bottom, top = points
        if (
            abs(top[0] - bottom[0]) > slop
            or abs(top[1] - bottom[1] - COEFFICIENT_T / 1000.0) > slop
            or abs(inset[0] - bottom[0] - 0.001) > slop
            or abs(inset[1] - bottom[1]) > slop
        ):
            raise RuntimeError(f"{label}: unexpected projected plate direction or scale")
        return bottom, top

    def ink(display: Any) -> tuple[Any, ...]:
        faces = geometry()
        gaps = []
        for index in (0, 1):
            ok, use_doc, value = display.GetWitnessLineGap(index, False, 0.0)
            if (
                ok is not True or type(use_doc) is not bool
                or not finite(value) or value < 0.0
            ):
                raise RuntimeError(f"{label}: invalid native witness gap {index}")
            gaps.append((use_doc, value))
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
        for face, tip, (_use_doc, gap) in zip(faces, tips, gaps):
            witnesses = [
                stroke for stroke in horizontal
                if all(abs(point[1] - face[1]) <= slop for point in stroke)
            ]
            if len(witnesses) != 1:
                raise RuntimeError(f"{label}: witness does not follow its plate face level")
            left, right = sorted(point[0] for point in witnesses[0])
            if (
                abs(tip[1] - face[1]) > slop
                or abs(right - (face[0] - gap)) > slop
                or not left < tip[0] < right
            ):
                raise RuntimeError(f"{label}: unexpected native witness endpoint or arrow")
            tails.append(left)
        if any(
            stroke not in horizontal
            and any(abs(point[0] - tips[0][0]) > slop for point in stroke)
            for stroke in segments
        ):
            raise RuntimeError(f"{label}: unexpected native dimension-line ink")
        return tuple(gaps), tuple(tips), tuple(tails)

    display, dimension, name, value, band = model_state()
    original_ink = ink(display)

    def check_thickness() -> None:
        current, owner, current_name, current_value, current_band = model_state()
        if (
            not same(current, display) or not same(owner, dimension)
            or (current_name, current_value, current_band) != (name, value, band)
        ):
            raise RuntimeError(f"{label}: native model identity, value or band changed")
        actual_gaps, actual_tips, actual_tails = ink(current)
        gaps, tips, tails = original_ink
        if (
            actual_gaps != gaps
            or any(math.dist(a, b) > slop for a, b in zip(actual_tips, tips))
            or any(abs(a - b) > slop for a, b in zip(actual_tails, tails))
        ):
            raise RuntimeError(f"{label}: native witness gaps, arrow tips or tails moved")

    return check_thickness


def _dimension_ownership_check(
    adapter: Any, views: Iterable[tuple[str, str, Any, Iterable[str]]],
) -> Callable[[], None]:
    """Keep every marked dimension on exactly its assigned manufacturing view."""
    owners = {
        name: feature for feature, names in DIMENSIONS_BY_FEATURE.items() for name in names
    }
    assignments = tuple(
        (sheet, label, raw, frozenset(wanted)) for sheet, label, raw, wanted in views
    )

    def check_ownership() -> None:
        ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
        active_sheet = None
        for sheet, label, raw_view, wanted in assignments:
            if sheet != active_sheet:
                if ddoc.ActivateSheet(sheet) is not True:
                    raise RuntimeError(f"{label}: cannot activate native owner sheet {sheet!r}")
                active_sheet = sheet
            view = _early_bound(raw_view, "IView")
            count = view.GetAnnotationCount()
            raw_annotations = view.GetAnnotations()
            if (
                type(count) is not int or count < 0
                or (raw_annotations is None and count != 0)
                or (raw_annotations is not None and (
                    not isinstance(raw_annotations, (tuple, list))
                    or len(raw_annotations) != count
                ))
            ):
                raise RuntimeError(f"{label}: invalid native annotation census")
            found = []
            for raw in raw_annotations or ():
                annotation = _early_bound(raw, "IAnnotation")
                kind = annotation.GetType()
                if type(kind) is not int:
                    raise RuntimeError(f"{label}: unreadable native annotation type")
                if kind != 4:  # swDisplayDimension
                    continue
                display = _early_bound(
                    annotation.GetSpecificAnnotation(), "IDisplayDimension",
                )
                raw_dimension = display.GetDimension2(0)
                if raw_dimension is None:
                    if display.IsHoleCallout() is True:
                        continue
                    raise RuntimeError(f"{label}: non-callout dimension has no model owner")
                dimension = _early_bound(raw_dimension, "IDimension")
                full_name = dimension.FullName
                if not isinstance(full_name, str) or not full_name:
                    raise RuntimeError(f"{label}: model dimension has no native name")
                parts = full_name.split("@")
                name = parts[0]
                if name not in owners:
                    continue
                if (
                    len(parts) < 2 or parts[1] != owners[name]
                    or type(annotation.OwnerType) is not int or annotation.OwnerType != 0
                    or type(annotation.Visible) is not int or annotation.Visible != 1
                    or annotation.IsDangling() is not False
                ):
                    raise RuntimeError(f"{label}: {full_name} lost its native feature/view ownership")
                found.append(name)
            if sorted(found) != sorted(wanted):
                raise RuntimeError(
                    f"{label}: marked-dimension ownership mismatch: "
                    f"expected {sorted(wanted)}, found {sorted(found)}"
                )

    return check_ownership


_SW_HIDDEN = 2  # swDisplayMode_e.swHIDDEN: hidden lines removed


def _hidden_lines_removed_without_greyed_pass(view: Any) -> None:
    """Set HLR directly before annotating, without the label-generating grey pass.

    #1591 observed view-dependent automatic receiver labels after the shared
    hidden-line regeneration. These newly placed views need no such pass.
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
    #1591 recorded view-dependent labels. The three authored native callouts,
    not automatic notes, define the holes.
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


# VIEW F's controlled ReceiverY0 locates the bracket row from the plate top.
# The coefficient top stays fixed above the pivot; both tap centres remain
# y=0. An owned centreline runs through the taps and hex centre, extending
# past the free-edge station and hex flats. The separate (2.54) reference
# repeated ReceiverY0's span and was struck by ReceiverX1's extension line.
RECEIVER_AXIS_STATION_MM = 37.5
RECEIVER_AXIS_OVERRUN_MM = 2.0


def _receiver_axis_centerline(adapter: Any, back: Any) -> Any:
    """Extend VIEW F's receiver-row centreline through the hex centre."""
    z_mm = -PLATE_L / 2.0
    station = RECEIVER_AXIS_STATION_MM
    return _owned_centerline(
        adapter,
        back,
        (
            (station + RECEIVER_AXIS_OVERRUN_MM, 0.0, z_mm),
            (-(HEX_W / 2.0 + RECEIVER_AXIS_OVERRUN_MM), 0.0, z_mm),
        ),
        label="receiver row centreline",
    )


# VIEW G carries the shared positive rib profile, its derived reach, and the
# bounded R1 root/profile blend. The counter web remains independently sized.
FRONT_KEEP = {
    "AnchorHeight": (0.183, 0.235),
    "WebThickness": (0.215, 0.247),
    "EdgeRibFrontArcR": (0.1948, 0.2120),
    "RibReach": (0.2443, 0.254),
    "RibRootRadius": (0.283, 0.225),
}
# Detail D at 10:1: the complete envelope fills a 120 mm crop on sheet 2.
# The ridge pair shares one line above the crop, with each whole callout
# outside its span. Datum A and R0.1 MAX stay between that line and the
# actual ridge; the angle sits in the open wedge right of the upper shoulder.
# The vertex height is left of the crop and the reference width below it.
DETAIL_KEEP = {
    "HexWidth": (0.203, 0.083),
    "HexHeight": (0.0342, DETAIL_CENTER[1]),
    "RidgeFromLeft": (0.044, 0.254),
    "RidgeFromRight": (0.201, 0.254),
    "FlankToSide": (0.207, 0.201),
    "KnifeRidgeRadius": (0.150, 0.224),
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
    # Receiver rib's inward depth, beside the -Z end of the plan.
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
    # Ordinary mid-rib thickness beside its end, clear of the spring callout.
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
# VIEW F at 1:1, model X reversed, in the lower-right field of sheet 2.
# The receiver stations are above the end profile; its uniform thickness
# stands left of the free end, below the separately controlled row height.
BACK_KEEP = {
    "PlateThickness": (0.228, 0.083),
    "ReceiverX0": (0.295, 0.1315),
    "ReceiverX1": (0.205, 0.1245),
    "ReceiverY0": (0.218, 0.1085),
}
# The view label is below the receiver profile, outside the thickness witnesses.
BACK_VIEW_NOTE_XY = (0.225, 0.050)
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
    _attach_radial_leaders(
        adapter, front_annotations, ("EdgeRibFrontArcR", "RibRootRadius"), label="front"
    )
    _attach_radial_leaders(
        adapter, top_annotations, ("SummationArcRadius",), label="top"
    )
    _shorten_radii(adapter, top_annotations, ("SummationArcRadius",), label="top")
    _assert_rib_root_radius(adapter, front_annotations)
    _apply_callouts(
        adapter, [*front_annotations, *top_annotations], label="lever geometry",
    )
    # The boss's Ø19.05 takes one arrow on its near rim, no line through the
    # centre: there it crossed the anchor tap callout's leader, which runs
    # through the tap's centre (machinist review r13, rule 14).
    [boss_dia] = [
        annotation
        for annotation in top_annotations
        if dimension_name(adapter, annotation) == "AnchorOuterDia"
    ]
    set_near_side_diameter(boss_dia, "boss diameter")

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

    # Datum A is the common knife-edge pivot ridge, tagged in Detail D on sheet 2.
    # One sweep of the plan's visible edges serves every
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
        (HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z_LAST),
        HOLE_DIA / 2.0,
        axis=(0.0, 1.0, 0.0),
        label="spring-hole seed rim",
    )
    second_rim = top_edges.circle_at(
        (HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z_LAST - CHANNEL_PITCH),
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
    # The 20X callout hangs on hole 7, with its complete process line in the
    # open field right of the column and clear of the mid-rib witnesses.
    callout_hole_z = HOLE_Z_LAST - (HOLE_COUNT // 2 - 3) * CHANNEL_PITCH
    callout_rim = top_edges.circle_at(
        (HOLE_X, COEFFICIENT_TOP_Y, callout_hole_z),
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
        (HOLE_X, COEFFICIENT_TOP_Y, HOLE_Z_FIRST),
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
    # The reference envelope is hidden in the saved part. Show it only while
    # creating/curating D; its native items select through their existing parent.
    with part_sketches_shown(
        adapter,
        source_model,
        KNIFE_SKETCHES,
        label="knife envelope",
        base_view=back,
    ):
        detail = _knife_detail(adapter, back)
        _hidden_lines_removed_without_greyed_pass(detail)
        detail_annotations = curate_hidden_dimensions(
            adapter,
            detail,
            keep=DETAIL_KEEP,
            view_label="knife detail",
            dimensions_by_feature=DIMENSIONS_BY_FEATURE,
        )
    _attach_radial_leaders(
        adapter, detail_annotations, ("KnifeRidgeRadius",), label="knife detail",
    )
    _assert_knife_ridge_radius(adapter, detail_annotations)
    _ridge_datum(adapter, detail)
    _apply_callouts(adapter, detail_annotations, label="knife detail")
    back_edges = scan_view_edges(back, label="bracket receiver face")
    mounting_rims = _mounting_rims(back_edges)
    # Below VIEW F, clear of the receiver stations and the detail's width.
    mounting_callout = add_native_hole_callout(
        adapter, back, edge=mounting_rims[0].edge,
        callout_xy=(0.292, 0.065), label="two blind bracket mounting taps",
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
    check_plate_thickness = _plate_thickness_check(adapter, back, back_annotations)
    _apply_callouts(adapter, back_annotations, label="bracket receiver")
    _receiver_axis_centerline(adapter, back)
    # Keep the removed-view identity below the actual end profile.
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
    check_dimension_ownership = _dimension_ownership_check(
        adapter,
        (
            (SHEET_NAMES[0], "VIEW G", front, FRONT_KEEP),
            (SHEET_NAMES[0], "top", top, TOP_KEEP),
            (SHEET_NAMES[0], "geometry isometric", iso, ()),
            (SHEET_NAMES[1], "knife detail D", detail, DETAIL_KEEP),
            (SHEET_NAMES[1], "VIEW F", back, BACK_KEEP),
            (SHEET_NAMES[1], "receiver isometric", receiver_iso, ()),
        ),
    )
    check_dimension_ownership()
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
            check_thread_annotations, check_plate_thickness, check_dimension_ownership,
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

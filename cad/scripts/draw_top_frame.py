r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only native model
dimensions, associative hole callouts, and the views of the casting; shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``. GEOMETRY defines the frame windows and T-rail section;
HOLES-SOCKETS defines the socket pattern, hanger/keeper holes, cap seats, and
cross-screw axes. HUB-SET-SCREW contains the hub location, true-axis side view,
enlarged native underside, and a cropped section through the set-screw pocket.
Projected top/front pairs stay aligned; removed and section views carry scales.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from solidworks_mcp.adapters.com_variant import double_array
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_edge_dimension,
    dimension_name,
    set_arc_endpoints_to_center,
    set_arc_endpoints_to_max,
    set_reference_dimension,
    set_dimension_precision,
    add_property_linked_note,
    create_section_view,
    create_blank_drawing_sheets,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    _select_view_entity,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    view_name,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    visible_view_entities,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from build_top_frame import (
    BAR_X0,
    BAR_X1,
    BORE_DIA,
    BORE_CHAMFER,
    CAP_RECESS_DIAMETER,
    BOSS_ABOVE,
    BOSS_BELOW,
    FLANGE,
    FLANGE_BOT_Y,
    EDGE_CHAMFER,
    ROOT_FILLET_R,
    OUTER_Z,
    RAIL_W_FR,
    RAIL_W_SIDE,
    INNER_X,
    INNER_Z,
    RING_HEIGHT,
    WEB_T,
    WEB_OUT_X,
    WEB_IN_Z,
    WEB_OUT_Z,
    REAR_COLUMN_Z,
    BOSS_DIA,
    COLUMN_X,
    FRONT_COLUMN_Z,
    GOOSENECK_BORE_DIA,
    GOOSENECK_X,
    GOOSENECK_Z,
    HALF_H,
    HUB_BOSS_DROP,
    HUB_RIB_W,
    HUB_GUSSET_T,
    HUB_GUSSET_HALF_IN,
    HUB_GUSSET_HALF_OUT,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_FRONT,
    OUTER_X,
    SET_POCKET_DEPTH,
    SET_POCKET,
    SPOTFACE_DIA,
    SET_TAP_SPEC,
    SIDE_TAP_DRILL_DIA,
    STUD_HOLE_DIA,
    STUD_Z_FRONT,
    TAP_DRILL_MM,
    TOP_SCREW_SEAT_Z,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["top_frame"]
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

SHEET_NAMES = ("GEOMETRY", "HOLES-SOCKETS", "HUB-SET-SCREW")
SHEET_SCALE = (1.0, 3.0)
GEOMETRY_VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
DETAIL_VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0
FRAME_ORIGIN_AXES = (
    ((-PLAN_HALF_X, 0.0, 0.0), (PLAN_HALF_X, 0.0, 0.0)),
    ((0.0, 0.0, -PLAN_HALF_Z), (0.0, 0.0, PLAN_HALF_Z)),
)
GEOMETRY_PLAN_HALF_W = PLAN_HALF_X * GEOMETRY_VIEW_SCALE / 1000.0
GEOMETRY_PLAN_HALF_D = PLAN_HALF_Z * GEOMETRY_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_W = PLAN_HALF_X * DETAIL_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_D = PLAN_HALF_Z * DETAIL_VIEW_SCALE / 1000.0


# Sheet 1: overall envelope and non-hole geometry.  Top/front remain
# horizontally projected; the isometric supplements those orthographic views.
GEOMETRY_TOP_CENTER = (0.145, 0.175)
GEOMETRY_FRONT_CENTER = (0.145, 0.090)
GEOMETRY_ISO_CENTER = (0.072, 0.052)
ISO_SCALE = (1, 5)

# Sheet 2: the aligned hole pattern/front group and corner section.
DETAIL_TOP_CENTER = (0.175, 0.190)
DETAIL_FRONT_CENTER = (0.175, 0.095)
DETAIL_SECTION_CENTER = (0.330, 0.130)

# Sheet 3: hub location, true-axis side view, and enlarged native underside.
HUB_TOP_CENTER = (0.145, 0.200)
HUB_LEFT_CENTER = (0.145, 0.095)
HUB_LEFT_SCALE = (1, 2)
HUB_BOTTOM_CENTER = (0.330, 0.220)
HUB_BOTTOM_SCALE = (1, 5)
HUB_DETAIL_CENTER = (0.325, 0.140)
HUB_DETAIL_SCALE = (1, 1)
HUB_SECTION_CENTER = (0.105, 0.050)
HUB_SECTION_SCALE = (1, 1)

GEOMETRY_TOP_NOTE_XY = (0.015, 0.245)
GEOMETRY_FRONT_NOTE_XY = (0.025, 0.120)
GEOMETRY_ISO_NOTE_XY = (0.042, 0.018)
DETAIL_TOP_NOTE_XY = (0.030, 0.120)
DETAIL_FRONT_NOTE_XY = (0.040, 0.065)

# The first sheet contains only the frame/window and T-rail definition.
GEOMETRY_TOP_KEEP = {
    "Width": (
        GEOMETRY_TOP_CENTER[0],
        0.250,
    ),
    "Depth": (0.046, GEOMETRY_TOP_CENTER[1]),
    "WinWidth": (
        GEOMETRY_TOP_CENTER[0],
        0.237,
    ),
    "WinDepth": (0.059, GEOMETRY_TOP_CENTER[1] - 0.012),
    "GussetRunE": (GEOMETRY_TOP_CENTER[0], 0.227),
}
GEOMETRY_FRONT_KEEP: dict[str, tuple[float, float]] = {}
GEOMETRY_CALLOUTS = {
    "Width": "RAIL FLANGE EXTENT",
    "Depth": "RAIL FLANGE EXTENT",
    "GussetRunE": "4X 45 DEG GUSSET",
}

# Imported station dimensions share the drawn model-origin axes.
DETAIL_TOP_KEEP = {
    "StudRearZ": (0.065, DETAIL_TOP_CENTER[1] - 0.030),
    "KeeperRearZ": (0.300, DETAIL_TOP_CENTER[1] - 0.028),
    "C0Dia": (0.045, 0.254),
    "B0Dia": (0.070, 0.244),
    "StudFrontX": (0.170, 0.245),
    "StudFrontZ": (0.055, DETAIL_TOP_CENTER[1] + 0.015),
    "KeeperFrontX": (0.285, 0.240),
    "KeeperFrontZ": (0.290, DETAIL_TOP_CENTER[1] + 0.012),
}
HUB_TOP_KEEP: dict[str, tuple[float, float]] = {}
HUB_LEFT_KEEP = {
    "PocketRise": (0.045, HUB_LEFT_CENTER[1]),
}
DETAIL_FRONT_KEEP: dict[str, tuple[float, float]] = {}
DETAIL_SECTION_KEEP = {
    "CapRecessDia": (
        DETAIL_SECTION_CENTER[0] - 0.040,
        DETAIL_SECTION_CENTER[1] + 0.020,
    ),
    "CapRecessDepth": (
        0.374,
        0.167,
    ),
}
DETAIL_CALLOUTS = {
    "C0Dia": "4X BOSS",
    "B0Dia": "4X SOCKET / REF\nMATCH-FIT ASSIGNED TUBE",
    "StudFrontX": "WEB / HANGER X",
    "StudFrontZ": "FRONT HANGER Z",
    "StudRearZ": "REAR HANGER Z",
    "KeeperFrontX": "KEEPER X",
    "KeeperFrontZ": "FRONT KEEPER Z",
    "KeeperRearZ": "REAR KEEPER Z",
}
SECTION_CALLOUTS = {
    "CapRecessDia": "4X CAP RECESS",
    "CapRecessDepth": "4X CAP SEAT",
}


def _add_view_centerlines(
    adapter: Any,
    view: Any,
    axes: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...],
) -> None:
    """Create only the owned axes, in the target view's actual sketch frame."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate drawing centreline view")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    for start, end in axes:
        points = []
        for xyz in (start, end):
            x, y = model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in xyz),
                label="drawing centreline endpoint",
            )
            point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
            points.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
        segment = manager.CreateCenterLine(*points[0], *points[1])
        if segment is None:
            raise RuntimeError("failed to create owned drawing centreline")
        segment = _early_bound(segment, "ISketchSegment")
        segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
        if int(segment.Color) != 0:
            raise RuntimeError("owned drawing centreline color did not persist")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


def _exact_linear_entities(
    view: Any, points: tuple[tuple[float, float, float], ...], *, label: str
) -> list[Any]:
    candidates = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None or not _early_bound(curve, "ICurve").IsLine():
            continue
        vertices = (edge.GetStartVertex(), edge.GetEndVertex())
        if any(vertex is None for vertex in vertices):
            continue
        ends = [
            tuple(float(value)*1000.0 for value in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in vertices
        ]
        candidates.append((edge, ends))
    selected = []
    for point in points:
        matches = []
        for edge, (start, end) in candidates:
            vector = tuple(b-a for a, b in zip(start, end))
            length_sq = sum(value*value for value in vector)
            if length_sq == 0.0:
                continue
            t = sum((p-a)*v for p, a, v in zip(point, start, vector))/length_sq
            if not -1e-6 <= t <= 1.0+1e-6:
                continue
            error = sum((p-a-t*v)**2 for p, a, v in zip(point, start, vector))
            matches.append((error, edge))
        if not matches or min(matches, key=lambda item: item[0])[0] > 1e-8:
            raise RuntimeError(f"{label}: no exact visible line through {point}")
        selected.append(min(matches, key=lambda item: item[0])[1])
    return selected


def _checked_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    text_xy: tuple[float, float],
    label: str,
    expected_mm: float,
    orientation: str,
    center: bool = False,
    maximum: bool = False,
    reference: bool = False,
    precision: int = 1,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    suffix: str = "",
    exact_linear: bool = False,
    exact_vertices: bool = False,
    entities: tuple[Any, Any] | None = None,
) -> Any:
    selected = list(entities) if entities is not None else None
    if exact_vertices:
        candidates = []
        for raw_edge in visible_view_entities(view, 1, label=label):
            edge = _early_bound(raw_edge, "IEdge")
            for raw_vertex in (edge.GetStartVertex(), edge.GetEndVertex()):
                if raw_vertex is None:
                    continue
                vertex = _early_bound(raw_vertex, "IVertex")
                point = tuple(float(value)*1000.0 for value in vertex.GetPoint())
                candidates.append((point, vertex))
        selected = []
        for point in (p0, p1):
            matches = [
                (sum((a-b)**2 for a, b in zip(point, candidate)), vertex)
                for candidate, vertex in candidates
            ]
            if not matches or min(matches, key=lambda item: item[0])[0] > 1e-8:
                raise RuntimeError(f"{label}: no exact visible vertex at {point}")
            selected.append(min(matches, key=lambda item: item[0])[1])
    elif exact_linear:
        selected = _exact_linear_entities(view, (p0, p1), label=label)
    points = [
        model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in point), label=label
        )
        for point in (p0, p1)
    ]
    display = add_edge_dimension(
        adapter, view, p0=points[0], p1=points[1], text_xy=text_xy,
        label=label, orientation=orientation,
        entity_types=("VERTEX", "VERTEX") if exact_vertices else entity_types,
        entities=tuple(selected) if selected is not None else None,
    )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    elif maximum:
        set_arc_endpoints_to_max(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    dimension_type = int(native.Type2)
    if dimension_type not in (2, 11, 12):  # linear, horizontal linear, vertical linear
        raise RuntimeError(f"{label}: expected linear dimension, received type {dimension_type}")
    measured = abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)) * 1000.0
    if abs(measured - expected_mm) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured:g}, expected {expected_mm:g} mm")
    annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
    set_dimension_precision(
        adapter, [annotation], {dimension_name(adapter, annotation): precision}
    )
    if suffix:
        set_dimension_callouts(adapter, [annotation], {dimension_name(adapter, annotation): suffix})
    if reference:
        set_reference_dimension(adapter, annotation, label=label)
    return native


def _orient_cut_section(
    adapter: Any, view: Any, horizontal_axis: tuple[float, float, float]
) -> None:
    """Show only the cut faces, with model Y up and the named axis right."""
    view = _early_bound(view, "IView")
    section = _early_bound(view.GetSection(), "IDrSection")
    section.SetDisplayOnlySurfaceCut(True)
    if not section.GetDisplayOnlySurfaceCut():
        raise RuntimeError("section retained geometry behind the cutting plane")
    def projected_axes() -> tuple[tuple[float, float], tuple[float, float]]:
        origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="section origin")
        points = [
            model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in axis),
                label="section orientation axis",
            )
            for axis in (horizontal_axis, (0.0, 1.0, 0.0))
        ]
        return tuple(tuple(point[i]-origin[i] for i in range(2)) for point in points)

    horizontal, vertical = projected_axes()
    if horizontal[0]*vertical[1]-horizontal[1]*vertical[0] < 0.0:
        reversed_cut = not bool(section.GetReversedCutDirection())
        section.SetReversedCutDirection(reversed_cut)
        adapter.currentModel.EditRebuild3()
        if bool(section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError("section cutting direction did not persist")
        horizontal, vertical = projected_axes()
    view.Angle = float(view.Angle)-math.atan2(horizontal[1], horizontal[0])
    adapter.currentModel.EditRebuild3()
    horizontal, vertical = projected_axes()
    if (
        horizontal[0] <= 0.0 or abs(horizontal[1]) > 1e-8
        or vertical[1] <= 0.0 or abs(vertical[0]) > 1e-8
    ):
        raise RuntimeError(
            f"section model-axis orientation did not persist: {horizontal=}, {vertical=}"
        )


def _hub_pocket_section(adapter: Any, parent_view: Any) -> Any:
    """Crop a native section at the bore/set-tap axis; no model is simplified."""
    line = [
        model_point_in_view(
            adapter, parent_view, (x/1000.0, 0.0, GOOSENECK_Z/1000.0),
            label="set-pocket section cutting line",
        )
        for x in (-INNER_X+5.0, -OUTER_X-5.0)
    ]
    view = create_section_view(
        adapter, parent_view, line_start=line[0], line_end=line[1],
        view_xy=HUB_SECTION_CENTER, section_label="D", scale=HUB_SECTION_SCALE,
        label="set-pocket manufacturing section",
    )
    _orient_cut_section(adapter, view, (1.0, 0.0, 0.0))
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate set-pocket section for cropping")
    draw.ClearSelection2(True)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    corners = []
    for xyz in (
        (-OUTER_X-5.0, -HALF_H-HUB_BOSS_DROP-3.0, GOOSENECK_Z),
        (-INNER_X+5.0, HALF_H+3.0, GOOSENECK_Z),
    ):
        x, y = model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in xyz),
            label="set-pocket section crop corner",
        )
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        corners.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCornerRectangle(*corners[0], *corners[1]) is None:
        raise RuntimeError("failed to create set-pocket section crop profile")
    crop_status = int(view.Crop2(True, False, 5))
    if crop_status != 1 or not view.IsCropped():  # swCropViewErrors_NoError
        raise RuntimeError(f"set-pocket section crop failed: {crop_status}")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in view.GetOutline())
    position = tuple(float(value) for value in view.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("cropped set-pocket section has invalid bounds")
    target = [
        position[axis]+HUB_SECTION_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position cropped set-pocket section")
    draw.EditRebuild3()
    outline = tuple(float(value) for value in view.GetOutline())
    center = tuple((outline[axis]+outline[axis+2])/2 for axis in range(2))
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if math.dist(center, HUB_SECTION_CENTER) > 0.0001:
        raise RuntimeError("cropped set-pocket section centre did not persist")
    if not math.isclose(ratio[0]/ratio[1], HUB_SECTION_SCALE[0]/HUB_SECTION_SCALE[1]):
        raise RuntimeError("cropped set-pocket section scale did not persist")
    _add_view_centerlines(
        adapter, view,
        (
            ((GOOSENECK_X, -HALF_H-HUB_BOSS_DROP-2.0, GOOSENECK_Z),
             (GOOSENECK_X, HALF_H+2.0, GOOSENECK_Z)),
            ((-OUTER_X-2.0, 0.0, GOOSENECK_Z), (-INNER_X+2.0, 0.0, GOOSENECK_Z)),
        ),
    )
    _checked_dimension(
        adapter, view,
        p0=(-OUTER_X, (SET_POCKET+SET_POCKET_DEPTH)/2, GOOSENECK_Z),
        p1=(-OUTER_X+SET_POCKET_DEPTH, (SET_POCKET-SET_POCKET_DEPTH)/2, GOOSENECK_Z),
        text_xy=(0.062, 0.055), label="set-pocket depth from outer rail face",
        expected_mm=SET_POCKET_DEPTH, orientation="horizontal", exact_linear=True,
        suffix="POCKET DEPTH\nFROM OUTER FACE",
    )
    return view

def _hub_underside_detail(adapter: Any, parent_view: Any) -> Any:
    """Enlarge the native underside; the circular fence is presentation only."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    parent = _early_bound(parent_view, "IView")
    if not drawing.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError("failed to activate underside detail parent")
    draw.ClearSelection2(True)
    center = model_point_in_view(
        adapter, parent_view,
        (GOOSENECK_X/1000.0, (-HALF_H-HUB_BOSS_DROP)/1000.0, GOOSENECK_Z/1000.0),
        label="underside detail centre",
    )
    radius = (HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP)*HUB_BOTTOM_SCALE[0]/HUB_BOTTOM_SCALE[1]/1000.0
    sketch = _early_bound(parent.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0]+radius, center[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        points.append(tuple(_early_bound(point.MultiplyTransform(transform), "IMathPoint").ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create native underside detail fence")
    detail = drawing.CreateDetailViewAt4(
        *HUB_DETAIL_CENTER, 0.0, 0, *HUB_DETAIL_SCALE, "C", 1, True, False, False, 5,
    )
    if detail is None:
        raise RuntimeError("failed to create native underside detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array([float(value) for value in HUB_DETAIL_SCALE])
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("native underside detail has invalid initial bounds")
    target = [
        position[axis]+HUB_DETAIL_CENTER[axis]-(outline[axis]+outline[axis+2])/2
        for axis in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position native underside detail")
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    ratio = tuple(float(value) for value in detail.ScaleRatio)
    if len(outline) != 4 or len(ratio) != 2:
        raise RuntimeError("native underside detail has invalid final bounds")
    center = tuple((outline[axis]+outline[axis+2])/2 for axis in range(2))
    if not math.isclose(ratio[0]/ratio[1], HUB_DETAIL_SCALE[0]/HUB_DETAIL_SCALE[1]):
        raise RuntimeError("native underside detail scale did not persist")
    if math.dist(center, HUB_DETAIL_CENTER) > 0.0001:
        raise RuntimeError(f"native underside detail centre did not persist: {center}")
    return detail




def _position_view_caption(
    adapter: Any, view: Any, target: tuple[float, float]
) -> None:
    """Move a native section/detail caption without replacing its linked fields."""
    view = _early_bound(view, "IView")
    if int(view.Type) not in (2, 3):  # swDrawingSectionView, swDrawingDetailView
        raise RuntimeError("caption target is not a native section or detail")
    candidates = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        # GetText is blank at this point; the native view-label fields persist.
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            candidates.append((note, linked_text))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one native linked view caption, found {len(candidates)}")
    note, linked_text = candidates[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    adapter.currentModel.EditRebuild3()
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


def _gusset_ramp_angle(adapter: Any, view: Any) -> None:
    """Define the exposed ramp, not the buried sketch flat inside the boss."""
    ramp_points = (
        (-WEB_OUT_X, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP),
        (GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H-HUB_BOSS_DROP/2,
         GOOSENECK_Z+(HUB_GUSSET_HALF_IN+HUB_GUSSET_HALF_OUT)/2),
    )
    edges = _exact_linear_entities(view, ramp_points, label="hub gusset ramp angle")
    sector = model_point_in_view(
        adapter, view,
        ((GOOSENECK_X-HUB_GUSSET_T/2)/1000.0,
         (-HALF_H-HUB_BOSS_DROP/8)/1000.0,
         (GOOSENECK_Z+HUB_GUSSET_HALF_OUT-HUB_BOSS_DROP)/1000.0),
        label="gusset acute angular sector",
    )
    points = [
        model_point_in_view(
            adapter, view, tuple(value/1000.0 for value in point),
            label="gusset angular pick",
        )
        for point in ramp_points
    ]
    display = add_edge_dimension(
        adapter, view, p0=points[0], p1=points[1], text_xy=sector,
        label="hub gusset ramp angle", orientation="smart", entities=tuple(edges),
    )
    draw = adapter.currentModel
    display = _early_bound(display, "IDisplayDimension")
    if int(display.Type2) != 3:
        raise RuntimeError("gusset ramp dimension is not angular")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    expected = math.atan2(HUB_BOSS_DROP, HUB_GUSSET_HALF_OUT-HUB_GUSSET_HALF_IN)
    if abs(float(dimension.SystemValue)-expected) > 1e-7:
        raise RuntimeError(f"gusset ramp angle measured {dimension.SystemValue} radians, expected {expected}")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    if not annotation.SetPosition2(0.175, 0.070, 0.0):
        raise RuntimeError("failed to position native gusset ramp angle")
    set_dimension_precision(adapter, [annotation], {dimension_name(adapter, annotation): 1})
    set_dimension_callouts(adapter, [annotation], {dimension_name(adapter, annotation): "2X GUSSET\nTO RAIL UNDERSIDE"})
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if abs(float(dimension.SystemValue)-expected) > 1e-7:
        raise RuntimeError("gusset ramp angle changed after text positioning")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")
    check("open top-frame source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="top-frame package")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Frame Ring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top frame; webbed gray iron ring casting; column bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    extension = _early_bound(drawing_model.Extension, "IModelDocExtension")
    if not extension.SetUserPreferenceInteger(542, 0, 0):
        raise RuntimeError("failed to set connected section cutting lines")
    if extension.GetUserPreferenceInteger(542, 0) != 0:
        raise RuntimeError("section cutting-line style did not persist")
    ddoc = _early_bound(drawing_model, "IDrawingDoc")

    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate top-frame geometry sheet")
    geometry_top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *GEOMETRY_TOP_CENTER,
        scale=SHEET_SCALE,
    )
    geometry_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *GEOMETRY_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    geometry_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *GEOMETRY_ISO_CENTER,
        scale=ISO_SCALE,
    )
    for view in (geometry_top, geometry_front):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_removed(adapter, geometry_iso)
    geometry_top_dimensions = curate_view_dimensions(
        adapter,
        geometry_top,
        keep=GEOMETRY_TOP_KEEP,
        view_label="geometry top",
    )
    geometry_front_dimensions = curate_view_dimensions(
        adapter,
        geometry_front,
        keep=GEOMETRY_FRONT_KEEP,
        view_label="geometry front",
    )
    geometry_annotations = [*geometry_top_dimensions, *geometry_front_dimensions]
    geometry_callouts = {
        name: "" for name in (*GEOMETRY_TOP_KEEP, *GEOMETRY_FRONT_KEEP)
    }
    geometry_callouts.update(GEOMETRY_CALLOUTS)
    set_dimension_callouts(adapter, geometry_annotations, geometry_callouts)
    set_dimension_precision(
        adapter, geometry_annotations,
        {name: 1 for name in (*GEOMETRY_TOP_KEEP, *GEOMETRY_FRONT_KEEP)},
    )
    _checked_dimension(
        adapter, geometry_top,
        p0=(-PLAN_HALF_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(PLAN_HALF_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        text_xy=(GEOMETRY_TOP_CENTER[0], 0.263), label="overall casting width",
        expected_mm=2*PLAN_HALF_X, orientation="horizontal", maximum=True,
        reference=True, suffix="OVERALL",
    )
    _checked_dimension(
        adapter, geometry_top,
        p0=(-COLUMN_X, HALF_H+BOSS_ABOVE, -PLAN_HALF_Z),
        p1=(-COLUMN_X, HALF_H+BOSS_ABOVE, PLAN_HALF_Z),
        text_xy=(0.022, 0.145), label="overall casting depth",
        expected_mm=2*PLAN_HALF_Z, orientation="vertical", maximum=True,
        reference=True,
    )
    _checked_dimension(
        adapter, geometry_top,
        p0=(INNER_X, HALF_H-EDGE_CHAMFER, 0.0),
        p1=(OUTER_X, HALF_H-EDGE_CHAMFER, 0.0),
        text_xy=(0.240, 0.120), label="side flange width",
        expected_mm=RAIL_W_SIDE, orientation="horizontal", exact_linear=True,
        suffix="SIDE FLANGE\nWIDTH",
    )
    for left_x, right_x, text_x, label in (
        (-INNER_X, BAR_X0, 0.105, "left window clear width"),
        (BAR_X1, INNER_X, 0.180, "right window clear width"),
    ):
        _checked_dimension(
            adapter, geometry_top,
            p0=(left_x, HALF_H - EDGE_CHAMFER, 0.0),
            p1=(right_x, HALF_H - EDGE_CHAMFER, 0.0),
            text_xy=(text_x, 0.125), label=label,
            expected_mm=right_x-left_x, orientation="horizontal", exact_linear=True,
        )
    _checked_dimension(
        adapter, geometry_top,
        p0=(BAR_X0, HALF_H-EDGE_CHAMFER, 0.0),
        p1=(BAR_X1, HALF_H-EDGE_CHAMFER, 0.0),
        text_xy=(GEOMETRY_TOP_CENTER[0], 0.112), label="central web width",
        expected_mm=BAR_X1-BAR_X0, orientation="horizontal", exact_linear=True,
        suffix="CENTRAL WEB",
    )
    rail_cut_x = COLUMN_X / 2.0
    rail_cut = [
        model_point_in_view(
            adapter, geometry_top, (rail_cut_x/1000.0, 0.0, z/1000.0),
            label="front rear rail section station",
        )
        for z in (PLAN_HALF_Z+6.0, -PLAN_HALF_Z-6.0)
    ]
    rail_section = create_section_view(
        adapter, geometry_top,
        line_start=rail_cut[0],
        line_end=rail_cut[1],
        view_xy=(0.320, 0.205), section_label="B", scale=(1, 3),
        label="T rail manufacturing section",
    )
    _orient_cut_section(adapter, rail_section, (0.0, 0.0, 1.0))
    rail_edges = []
    for raw_edge in visible_view_entities(
        geometry_front, 1, label="front rail-height plane inventory"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None or not _early_bound(curve, "ICurve").IsLine():
            continue
        vertices = (edge.GetStartVertex(), edge.GetEndVertex())
        if any(vertex is None for vertex in vertices):
            continue
        start, end = [
            tuple(float(value)*1000.0 for value in _early_bound(vertex, "IVertex").GetPoint())
            for vertex in vertices
        ]
        if (
            abs(start[1]-end[1]) > 1e-6 or abs(start[2]-end[2]) > 1e-6
            or not min(start[0], end[0]) < rail_cut_x < max(start[0], end[0])
        ):
            continue
        rail_edges.append((edge, (rail_cut_x, start[1], start[2])))
    height_edges = []
    for plane_y in (HALF_H, -HALF_H):
        candidates = [
            item for item in rail_edges if abs(item[1][1]-plane_y) < 1e-6
        ]
        if not candidates:
            raise RuntimeError(
                f"front rail has no visible edge on Y={plane_y:g}; "
                f"native section-station edge points={[point for _, point in rail_edges]}"
            )
        # *Front looks from +Z: choose its actual frontmost edge, not a
        # constructed point on the hidden opposite rail/chamfer.
        height_edges.append(max(candidates, key=lambda item: item[1][2]))
    _checked_dimension(
        adapter, geometry_front,
        p0=height_edges[0][1], p1=height_edges[1][1],
        text_xy=(0.238, 0.091), label="front projection rail height",
        expected_mm=RING_HEIGHT, orientation="vertical",
        entities=(height_edges[0][0], height_edges[1][0]),
        reference=True, suffix="RAIL HEIGHT",
    )
    set_hidden_lines_visible(adapter, rail_section)
    for p0, p1, expected, xy, orientation, label, qualifier in (
        ((rail_cut_x, 0.0, WEB_IN_Z), (rail_cut_x, 0.0, WEB_OUT_Z),
         WEB_T, (0.355, 0.180), "horizontal", "rail web thickness", "WEB WIDTH"),
        ((rail_cut_x, (FLANGE_BOT_Y+HALF_H-EDGE_CHAMFER)/2, INNER_Z),
         (rail_cut_x, (FLANGE_BOT_Y+HALF_H-EDGE_CHAMFER)/2, OUTER_Z),
         RAIL_W_FR, (0.355, 0.230), "horizontal", "front rear flange width", "FLANGE WIDTH"),
        ((rail_cut_x, HALF_H, (INNER_Z+WEB_IN_Z)/2),
         (rail_cut_x, FLANGE_BOT_Y, (INNER_Z+WEB_IN_Z)/2),
         FLANGE, (0.371, 0.215), "vertical", "top flange thickness", "FLANGE THICKNESS"),
        ((rail_cut_x, HALF_H, abs(FRONT_COLUMN_Z)),
         (rail_cut_x, -HALF_H, abs(FRONT_COLUMN_Z)),
         RING_HEIGHT, (0.390, 0.195), "vertical", "rail total height", "RAIL HEIGHT"),
    ):
        _checked_dimension(
            adapter, rail_section, p0=p0, p1=p1, text_xy=xy,
            label=label, expected_mm=expected, orientation=orientation, exact_linear=True,
            suffix=qualifier,
        )
    _checked_dimension(
        adapter, rail_section,
        p0=(rail_cut_x, HALF_H, INNER_Z + EDGE_CHAMFER),
        p1=(rail_cut_x, HALF_H-EDGE_CHAMFER, INNER_Z),
        text_xy=(0.290, 0.250), label="top rim chamfer",
        expected_mm=EDGE_CHAMFER, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="X 45 DEG TOP RIMS",
    )
    root_arcs = []
    for raw_edge in visible_view_entities(rail_section, 1, label="T rail root fillets"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if curve.IsCircle() and abs(float(curve.CircleParams[6])*1000.0-ROOT_FILLET_R) < 1e-6:
            root_arcs.append(edge)
    if not root_arcs:
        raise RuntimeError("T rail section has no source root fillet")
    _select_view_entity(
        adapter, rail_section, "EDGE", None, label="T rail root radius",
        entity=root_arcs[0],
    )
    root_display = drawing_model.AddRadialDimension2(0.290, 0.235, 0.0)
    if root_display is None:
        raise RuntimeError("failed to dimension T rail root radius")
    root_display = _early_bound(root_display, "IDisplayDimension")
    root_value = float(_early_bound(root_display.GetDimension2(0), "IDimension").SystemValue)*1000.0
    if abs(root_value-ROOT_FILLET_R) > 1e-6:
        raise RuntimeError(f"T rail root radius measured {root_value:g}")
    root_annotation = _early_bound(root_display.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(adapter, [root_annotation], {dimension_name(adapter, root_annotation): "TYP WEB ROOT"})
    set_dimension_precision(adapter, [root_annotation], {dimension_name(adapter, root_annotation): 1})
    drawing_model.ClearSelection2(True)
    if add_note(
        adapter, "B-B: FRONT / REAR RAILS\nALL WEBS CENTRED UNDER TOP FLANGE",
        0.270, 0.145,
    ) is None:
        raise RuntimeError("failed to identify the cut rails and centred webs")
    geometry_top_note = add_note(
        adapter, "PLAN VIEW SCALE 1:3", *GEOMETRY_TOP_NOTE_XY
    )
    geometry_front_note = add_note(
        adapter, "FRONT VIEW SCALE 1:3", *GEOMETRY_FRONT_NOTE_XY
    )
    geometry_iso_note = add_note(
        adapter,
        f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}",
        *GEOMETRY_ISO_NOTE_XY,
    )
    if (
        geometry_top_note is None
        or geometry_front_note is None
        or geometry_iso_note is None
    ):
        raise RuntimeError("failed to label top-frame geometry sheet")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate top-frame holes/sockets sheet")
    detail_top = place_view(
        adapter,
        str(SOURCE),
        "*Top",
        *DETAIL_TOP_CENTER,
        scale=SHEET_SCALE,
    )
    detail_front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *DETAIL_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    cut_x = model_point_in_view(
        adapter,
        detail_front,
        (COLUMN_X / 1000.0, 0.0, 0.0),
        label="top-frame corner-section axis",
    )[0]
    detail_section = create_section_view(
        adapter,
        detail_front,
        line_start=(cut_x, DETAIL_FRONT_CENTER[1] - 0.020),
        line_end=(cut_x, DETAIL_FRONT_CENTER[1] + 0.030),
        view_xy=DETAIL_SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="top-frame corner section",
    )
    for view in (detail_top, detail_front):
        set_hidden_lines_visible(adapter, view)
    set_hidden_lines_visible(adapter, detail_section)
    _add_view_centerlines(
        adapter, detail_section,
        (((COLUMN_X, 0.0, -PLAN_HALF_Z), (COLUMN_X, 0.0, PLAN_HALF_Z)),),
    )

    detail_top_dimensions = curate_view_dimensions(
        adapter,
        detail_top,
        keep=DETAIL_TOP_KEEP,
        view_label="holes/sockets top",
    )
    detail_front_dimensions = curate_view_dimensions(
        adapter,
        detail_front,
        keep=DETAIL_FRONT_KEEP,
        view_label="holes/sockets front",
    )
    detail_section_dimensions = curate_view_dimensions(
        adapter,
        detail_section,
        keep=DETAIL_SECTION_KEEP,
        view_label="holes/sockets section A-A",
    )
    detail_annotations = [
        *detail_top_dimensions,
        *detail_front_dimensions,
        *detail_section_dimensions,
    ]
    detail_callouts = {
        name: ""
        for name in (
            *DETAIL_TOP_KEEP,
            *DETAIL_FRONT_KEEP,
            *DETAIL_SECTION_KEEP,
        )
    }
    detail_callouts.update(DETAIL_CALLOUTS)
    detail_callouts.update(SECTION_CALLOUTS)
    set_dimension_callouts(adapter, detail_annotations, detail_callouts)
    set_dimension_precision(
        adapter, detail_annotations,
        {"C0Dia": 1, "B0Dia": 1},
    )
    socket_annotations = [
        annotation for annotation in detail_top_dimensions
        if dimension_name(adapter, annotation) == "B0Dia"
    ]
    if len(socket_annotations) != 1:
        raise RuntimeError("expected one native socket nominal for reference display")
    socket_display = set_reference_dimension(
        adapter, socket_annotations[0], label="matched socket nominal", diameter=True,
    )
    socket_dimension = _early_bound(socket_display.GetDimension2(0), "IDimension")
    if int(socket_dimension.GetToleranceType()) != 0:  # swTolNONE
        raise RuntimeError("socket source still carries a fixed fit tolerance; rebuild the part")
    boss_pick_z = REAR_COLUMN_Z+(CAP_RECESS_DIAMETER+BOSS_DIA)/4
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, boss_pick_z),
        p1=(COLUMN_X, -HALF_H-BOSS_BELOW, boss_pick_z),
        text_xy=(0.372, 0.117), label="socket boss overall height",
        expected_mm=RING_HEIGHT+BOSS_ABOVE+BOSS_BELOW,
        orientation="vertical", exact_linear=True, suffix="4X BOSS\nOVERALL HEIGHT",
    )
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z+CAP_RECESS_DIAMETER/2+BORE_CHAMFER),
        p1=(COLUMN_X, HALF_H+BOSS_ABOVE-BORE_CHAMFER, REAR_COLUMN_Z+CAP_RECESS_DIAMETER/2),
        text_xy=(0.340, 0.190), label="top bore mouth chamfer",
        expected_mm=BORE_CHAMFER, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="X 45 DEG\nCAP / GOOSENECK TOP",
    )
    if not auto_center_marks(adapter, detail_top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top-frame hole pattern")
    _add_view_centerlines(adapter, detail_top, FRAME_ORIGIN_AXES)
    for label, xy in (
        ("X", (DETAIL_TOP_CENTER[0]+DETAIL_PLAN_HALF_W+0.005, DETAIL_TOP_CENTER[1]+0.002)),
        ("Z", (DETAIL_TOP_CENTER[0]+0.003, DETAIL_TOP_CENTER[1]-DETAIL_PLAN_HALF_D-0.006)),
    ):
        if add_note(adapter, label, *xy) is None:
            raise RuntimeError("failed to label frame-centre coordinate axes")
    _checked_dimension(
        adapter, detail_top,
        p0=(-COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2),
        p1=(COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2),
        text_xy=(DETAIL_TOP_CENTER[0], 0.132), label="socket horizontal pitch",
        expected_mm=2*COLUMN_X, orientation="horizontal", center=True, precision=2,
    )
    _checked_dimension(
        adapter, detail_top,
        p0=(COLUMN_X + BORE_DIA/2, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(COLUMN_X + BORE_DIA/2, HALF_H + BOSS_ABOVE, REAR_COLUMN_Z),
        text_xy=(0.080, DETAIL_TOP_CENTER[1]), label="socket vertical pitch",
        expected_mm=REAR_COLUMN_Z-FRONT_COLUMN_Z, orientation="vertical",
        center=True, precision=2,
    )

    front_tap_candidates: list[tuple[float, float, float, Any]] = []
    upper_boss_edge = None
    spotface_edge = None
    for raw_edge in visible_view_entities(
        detail_front, 1, label="front column cross-tap circles"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        raw_params = tuple(float(value) for value in curve.CircleParams)
        params = tuple(value * 1000.0 for value in raw_params)
        if (
            abs(params[0]-COLUMN_X) < 1e-4
            and abs(params[1]-(HALF_H+BOSS_ABOVE)) < 1e-4
            and abs(params[2]-REAR_COLUMN_Z) < 1e-4
            and abs(params[6]-BOSS_DIA/2) < 1e-4
            and abs(raw_params[3])+abs(abs(raw_params[4])-1.0)+abs(raw_params[5]) < 1e-6
        ):
            upper_boss_edge = edge
        radius_error = abs(params[6] - SIDE_TAP_DRILL_DIA / 2.0)
        center_error = (
            abs(params[0] - COLUMN_X)
            + abs(params[1])
            + abs(params[2] - TOP_SCREW_SEAT_Z)
        )
        normal_error = (
            abs(raw_params[3])
            + abs(raw_params[4])
            + abs(raw_params[5] - 1.0)
        )
        if (
            abs(params[6]-SPOTFACE_DIA/2) < 1e-4
            and center_error < 1e-4 and normal_error < 1e-6
        ):
            spotface_edge = edge
        front_tap_candidates.append(
            (radius_error, center_error, normal_error, edge)
        )
    if not front_tap_candidates:
        raise RuntimeError("front view has no column cross-tap circular edges")
    radius_error, center_error, normal_error, front_tap_edge = min(
        front_tap_candidates, key=lambda item: item[0] + item[1] + item[2]
    )
    if radius_error > 0.01 or center_error > 0.02 or normal_error > 0.02:
        raise RuntimeError(
            "front view has no exact column cross-tap edge at "
            f"({COLUMN_X:g}, 0, {TOP_SCREW_SEAT_Z:g}) mm"
        )
    if upper_boss_edge is None:
        raise RuntimeError("front view has no exact outer boss rim on the upper boss plane")
    if spotface_edge is None:
        raise RuntimeError("front view has no exact column cross-screw spotface rim")
    _select_view_entity(
        adapter, detail_front, "EDGE", None,
        label="column cross-screw spotface diameter", entity=spotface_edge,
    )
    spotface_dimension = drawing_model.AddDiameterDimension2(0.200, 0.078, 0.0)
    if spotface_dimension is None:
        raise RuntimeError("failed to dimension column cross-screw spotface")
    spotface_dimension = _early_bound(spotface_dimension, "IDisplayDimension")
    spotface_value = abs(float(
        _early_bound(spotface_dimension.GetDimension2(0), "IDimension").SystemValue
    ))*1000.0
    if abs(spotface_value-SPOTFACE_DIA) > 1e-6:
        raise RuntimeError(f"column cross-screw spotface measured {spotface_value:g}")
    spotface_annotation = _early_bound(spotface_dimension.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(
        adapter, [spotface_annotation],
        {dimension_name(adapter, spotface_annotation): "4X SPOTFACE"},
    )
    set_dimension_precision(
        adapter, [spotface_annotation], {dimension_name(adapter, spotface_annotation): 1},
    )
    drawing_model.ClearSelection2(True)
    _checked_dimension(
        adapter, detail_section,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z),
        p1=(COLUMN_X, 0.0, TOP_SCREW_SEAT_Z),
        text_xy=(0.360, 0.098), label="spotface plane from socket axis",
        expected_mm=TOP_SCREW_SEAT_Z-REAR_COLUMN_Z,
        orientation="horizontal", center=True, precision=2,
        suffix="SPOTFACE FROM\nSOCKET AXIS", entities=(upper_boss_edge, spotface_edge),
    )
    add_native_hole_callout(
        adapter,
        detail_front,
        edge=front_tap_edge,
        callout_xy=(
            DETAIL_FRONT_CENTER[0] + DETAIL_PLAN_HALF_W + 0.012,
            DETAIL_FRONT_CENTER[1] + 0.020,
        ),
        label="front/rear column-retention bottoming taps",
        process="DEPTHS FROM SPOTFACE\nBOTTOMING TAP",
    )
    _checked_dimension(
        adapter, detail_front,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z),
        p1=(COLUMN_X+SIDE_TAP_DRILL_DIA/2, 0.0, TOP_SCREW_SEAT_Z),
        text_xy=(0.270, 0.082), label="cross screw axis from boss top",
        expected_mm=HALF_H+BOSS_ABOVE, orientation="vertical", center=True, precision=2,
        suffix="4X: 2 FRONT + 2 REAR\nALONG Z AT SOCKET X CENTRES",
        entities=(upper_boss_edge, front_tap_edge),
    )
    stud_edge = model_point_in_view(
        adapter,
        detail_top,
        (
            ((BAR_X0 + BAR_X1) / 2.0) / 1000.0,
            HALF_H / 1000.0,
            (STUD_Z_FRONT + STUD_HOLE_DIA / 2.0) / 1000.0,
        ),
        label="top-frame hanger-stud hole edge",
    )
    add_native_hole_callout(
        adapter,
        detail_top,
        edge_xy=stud_edge,
        callout_xy=(0.190, 0.258),
        label="2X hanger-stud clearance holes",
        process="HANGER DRILL",
    )
    keeper_edge = model_point_in_view(
        adapter,
        detail_top,
        (
            KEEPER_TAP_X / 1000.0,
            HALF_H / 1000.0,
            (KEEPER_TAP_Z_FRONT + TAP_DRILL_MM[KEEPER_TAP_SPEC.size] / 2.0)
            / 1000.0,
        ),
        label="top-frame fulcrum-keeper tap edge",
    )
    add_native_hole_callout(
        adapter,
        detail_top,
        edge_xy=keeper_edge,
        callout_xy=(0.345, 0.225),
        label="2X fulcrum-keeper blind taps",
        process="KEEPER TAP",
    )
    detail_top_note = add_note(
        adapter,
        "HOLE LOCATIONS FROM FRAME CENTRE (X,Z) / SCALE 1:3",
        *DETAIL_TOP_NOTE_XY,
    )
    detail_front_note = add_note(
        adapter,
        "FRONT CROSS-TAP VIEW SCALE 1:3",
        *DETAIL_FRONT_NOTE_XY,
    )
    cap_fit_note = add_note(
        adapter,
        "CAP RECESSES FOR MHA-133 / 9275K141",
        0.040,
        0.055,
    )
    if add_note(adapter, "A-A: THREAD BOTH CASTING WALLS IN PHASE FOR MHA-132", 0.040, 0.025) is None:
        raise RuntimeError("failed to identify section cross-screw relation")
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.040, 0.045, char_height=0.0035,
    )
    if not ddoc.ActivateSheet(SHEET_NAMES[2]):
        raise RuntimeError("failed to activate top-frame hub sheet")
    hub_top = place_view(
        adapter, str(SOURCE), "*Top", *HUB_TOP_CENTER, scale=SHEET_SCALE,
    )
    detail_left = place_view(
        adapter, str(SOURCE), "*Left", *HUB_LEFT_CENTER, scale=HUB_LEFT_SCALE,
    )
    for view in (hub_top, detail_left):
        set_hidden_lines_visible(adapter, view)
    hub_top_dimensions = curate_view_dimensions(
        adapter, hub_top, keep=HUB_TOP_KEEP, view_label="hub location",
    )
    hub_left_dimensions = curate_view_dimensions(
        adapter, detail_left, keep=HUB_LEFT_KEEP, view_label="hub side",
    )
    set_dimension_callouts(
        adapter, [*hub_top_dimensions, *hub_left_dimensions],
        {name: "" for name in (*HUB_TOP_KEEP, *HUB_LEFT_KEEP)},
    )
    set_dimension_callouts(
        adapter, hub_left_dimensions,
        {"PocketRise": "SQ POCKET\nOUTER LEFT FACE\nCENTRED ON SET TAP"},
    )
    set_dimension_precision(
        adapter, hub_left_dimensions, {name: 1 for name in HUB_LEFT_KEEP},
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(-OUTER_X, 0.0, GOOSENECK_Z-HUB_RIB_W/2),
        p1=(-OUTER_X, 0.0, GOOSENECK_Z+HUB_RIB_W/2),
        text_xy=(HUB_LEFT_CENTER[0], 0.141), label="full-height hub rail pad",
        expected_mm=HUB_RIB_W, orientation="horizontal", exact_linear=True,
        suffix="FULL-HEIGHT PAD\nCENTRED ON BORE",
    )
    _add_view_centerlines(
        adapter, hub_top,
        (
            ((-COLUMN_X, 0.0, -PLAN_HALF_Z), (-COLUMN_X, 0.0, PLAN_HALF_Z)),
            ((-PLAN_HALF_X, 0.0, FRONT_COLUMN_Z), (PLAN_HALF_X, 0.0, FRONT_COLUMN_Z)),
        ),
    )
    if add_note(adapter, "HUB LOCATION SCALE 1:3", 0.030, 0.260) is None:
        raise RuntimeError("failed to label hub location view")
    hub_bottom_parent = place_view(
        adapter, str(SOURCE), "*Bottom", *HUB_BOTTOM_CENTER, scale=HUB_BOTTOM_SCALE,
    )
    set_hidden_lines_visible(adapter, hub_bottom_parent)
    geometry_bottom = _hub_underside_detail(adapter, hub_bottom_parent)
    set_hidden_lines_visible(adapter, geometry_bottom)
    curate_view_dimensions(
        adapter, hub_bottom_parent, keep={},
        view_label="underside locator",
    )
    bottom_dimensions = curate_view_dimensions(
        adapter, geometry_bottom,
        keep={"HubDia": (0.265, 0.150)},
        view_label="enlarged underside geometry",
    )
    set_dimension_callouts(adapter, bottom_dimensions, {"HubDia": "CYLINDRICAL BOSS"})
    set_dimension_precision(adapter, bottom_dimensions, {"HubDia": 1})
    if add_note(adapter, "UNDERSIDE LOCATOR SCALE 1:5", 0.270, 0.255) is None:
        raise RuntimeError("failed to label underside locator")
    gusset_z = GOOSENECK_Z + (HUB_GUSSET_HALF_IN+HUB_GUSSET_HALF_OUT)/2
    gusset_y = -HALF_H-HUB_BOSS_DROP/2
    _checked_dimension(
        adapter, geometry_bottom,
        p0=(GOOSENECK_X-HUB_GUSSET_T/2, gusset_y, gusset_z),
        p1=(GOOSENECK_X+HUB_GUSSET_T/2, gusset_y, gusset_z),
        text_xy=(0.390, 0.185), label="underside gusset thickness",
        expected_mm=HUB_GUSSET_T, orientation="horizontal", exact_linear=True,
        suffix="2X GUSSET\nCENTRED ON BORE",
    )
    _checked_dimension(
        adapter, geometry_bottom,
        p0=(GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H, GOOSENECK_Z-HUB_GUSSET_HALF_OUT),
        p1=(GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT),
        text_xy=(0.390, 0.140), label="underside gusset overall span",
        expected_mm=2*HUB_GUSSET_HALF_OUT, orientation="vertical",
        entity_types=("VERTEX", "VERTEX"), exact_vertices=True,
        suffix="UNDERSIDE\nGUSSET SPAN",
    )
    bore_candidates: list[tuple[float, float, Any]] = []
    left_socket_edge = None
    for raw_edge in visible_view_entities(
        hub_top, 1, label="top gooseneck clearance-bore circles"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        raw_params = tuple(float(value) for value in curve.CircleParams)
        params = tuple(value*1000.0 for value in raw_params)
        if (
            abs(params[0]+COLUMN_X) < 1e-4
            and abs(params[2]-FRONT_COLUMN_Z) < 1e-4
            and abs(params[6]-BORE_DIA/2) < 1e-4
            and abs(raw_params[3])+abs(abs(raw_params[4])-1.0)+abs(raw_params[5]) < 1e-6
        ):
            left_socket_edge = edge
        radius_error = abs(params[6] - GOOSENECK_BORE_DIA / 2.0)
        center_error = abs(params[0] - GOOSENECK_X) + abs(
            params[2] - GOOSENECK_Z
        )
        bore_candidates.append((radius_error, center_error, edge))
    if not bore_candidates:
        raise RuntimeError("top view has no gooseneck clearance-bore circles")
    bore_error, center_error, gooseneck_edge = min(
        bore_candidates, key=lambda item: item[0] + item[1]
    )
    if bore_error > 0.01 or center_error > 0.02:
        raise RuntimeError(
            "top view has no gooseneck clearance-bore circle at "
            f"({GOOSENECK_X:g}, {GOOSENECK_Z:g}) mm with "
            f"{GOOSENECK_BORE_DIA / 2.0:g} mm radius"
        )
    if left_socket_edge is None:
        raise RuntimeError("hub view has no exact left front socket circle")
    _select_view_entity(
        adapter,
        hub_top,
        "EDGE",
        None,
        label="gooseneck clearance-bore diameter",
        entity=gooseneck_edge,
    )
    diameter_xy = (
        0.040,
        HUB_TOP_CENTER[1] - 0.015,
    )
    draw = adapter.currentModel
    display = draw.AddDiameterDimension2(diameter_xy[0], diameter_xy[1], 0.0)
    if display is None:
        raise RuntimeError("failed to add gooseneck clearance-bore diameter")
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue)) * 1000.0
    if abs(measured_mm - GOOSENECK_BORE_DIA) > 1e-6:
        raise RuntimeError(
            "gooseneck clearance-bore diameter readback "
            f"{measured_mm:g} mm != {GOOSENECK_BORE_DIA:g} mm"
        )
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_dimension_callouts(
        adapter, [annotation],
        {dimension_name(adapter, annotation): "DRILL THRU\nSAME X AS\nLEFT SOCKETS"},
    )
    set_dimension_precision(adapter, [annotation], {dimension_name(adapter, annotation): 2})
    if not annotation.SetPosition2(diameter_xy[0], diameter_xy[1], 0.0):
        raise RuntimeError("failed to position gooseneck clearance-bore diameter")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    _checked_dimension(
        adapter, hub_top,
        p0=(-COLUMN_X, HALF_H+BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(GOOSENECK_X, HALF_H, GOOSENECK_Z),
        text_xy=(0.040, 0.225), label="hub from left front socket",
        expected_mm=GOOSENECK_Z-FRONT_COLUMN_Z, orientation="vertical",
        center=True, precision=2, entities=(left_socket_edge, gooseneck_edge),
    )
    set_hidden_lines_visible(adapter, detail_left)
    tap_candidates: list[tuple[float, float, float, Any]] = []
    tap_x = -(OUTER_X - SET_POCKET_DEPTH)
    tap_radius = TAP_DRILL_MM[SET_TAP_SPEC.size] / 2.0
    rail_top_edge = None
    for raw_edge in visible_view_entities(
        detail_left, 1, label="left gooseneck set-tap circles"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if curve.IsLine():
            vertices = (edge.GetStartVertex(), edge.GetEndVertex())
            if all(vertex is not None for vertex in vertices):
                start, end = [
                    tuple(float(value)*1000.0 for value in _early_bound(vertex, "IVertex").GetPoint())
                    for vertex in vertices
                ]
                if (
                    max(
                        abs(start[0]+OUTER_X-EDGE_CHAMFER),
                        abs(end[0]+OUTER_X-EDGE_CHAMFER),
                        abs(start[1]-HALF_H),
                        abs(end[1]-HALF_H),
                    ) < 1e-4
                    and min(start[2], end[2]) < GOOSENECK_Z < max(start[2], end[2])
                ):
                    rail_top_edge = edge
        if not curve.IsCircle():
            continue
        raw_params = tuple(float(value) for value in curve.CircleParams)
        params = tuple(value * 1000.0 for value in raw_params)
        radius_error = abs(params[6] - tap_radius)
        center_error = (
            abs(params[0] - tap_x)
            + abs(params[1])
            + abs(params[2] - GOOSENECK_Z)
        )
        normal_error = (
            abs(raw_params[3] + 1.0)
            + abs(raw_params[4])
            + abs(raw_params[5])
        )
        tap_candidates.append((radius_error, center_error, normal_error, edge))
    if not tap_candidates:
        raise RuntimeError("left view has no set-tap circular edges")
    radius_error, center_error, normal_error, set_tap_edge = min(
        tap_candidates, key=lambda item: item[0] + item[1] + item[2]
    )
    if radius_error > 0.01 or center_error > 0.02 or normal_error > 0.02:
        raise RuntimeError(
            "left view has no exact set-tap edge at "
            f"({tap_x:g}, 0, {GOOSENECK_Z:g}) mm"
        )
    if rail_top_edge is None:
        raise RuntimeError("left view has no exact upper rail edge at the gooseneck station")
    add_native_hole_callout(
        adapter,
        detail_left,
        edge=set_tap_edge,
        callout_xy=(
            HUB_LEFT_CENTER[0] - 0.075,
            HUB_LEFT_CENTER[1] + 0.030,
        ),
        label="gooseneck set-screw through-to-bore tap",
        process="TAP",
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(-OUTER_X, HALF_H, GOOSENECK_Z),
        p1=(tap_x, 0.0, GOOSENECK_Z+tap_radius),
        text_xy=(0.230, 0.108), label="set screw axis from rail top",
        expected_mm=HALF_H, orientation="vertical", center=True, precision=2,
        suffix="FROM RAIL TOP\nON BORE CENTRE",
        entities=(rail_top_edge, set_tap_edge),
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(-WEB_OUT_X, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP),
        p1=(GOOSENECK_X, -HALF_H-HUB_BOSS_DROP, GOOSENECK_Z),
        text_xy=(0.225, 0.083), label="hub boss underside drop",
        expected_mm=HUB_BOSS_DROP, orientation="vertical",
        suffix="BELOW RAIL\nUNDERSIDE",
    )
    _gusset_ramp_angle(adapter, detail_left)
    set_hidden_lines_visible(adapter, detail_left)
    left_note = add_note(
        adapter, "HUB SIDE / REMOVED VIEW SCALE 1:2",
        0.080, 0.078,
    )
    if (
        detail_top_note is None
        or detail_front_note is None
        or cap_fit_note is None
        or left_note is None
    ):
        raise RuntimeError("failed to label top-frame holes/sockets sheet")
    hub_section = _hub_pocket_section(adapter, hub_top)
    _position_view_caption(adapter, hub_section, (0.170, 0.050))
    _position_view_caption(adapter, geometry_bottom, (HUB_DETAIL_CENTER[0], 0.086))
    for sheet_index, sheet_name in enumerate(SHEET_NAMES, start=1):
        if not ddoc.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to label drawing sheet {sheet_name}")
        if add_note(adapter, f"SHEET {sheet_index} OF {len(SHEET_NAMES)}", 0.350, 0.263) is None:
            raise RuntimeError(f"failed to stamp sheet count on {sheet_name}")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        # Separate hub location/side and underside imports add automatic Hole
        # Wizard notes. This three-sheet composition has six across all sheets;
        # the associative feature callouts replace them, and the total stays gated.
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=6,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

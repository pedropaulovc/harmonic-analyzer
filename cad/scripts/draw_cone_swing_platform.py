r"""Create the curated machinist drawing for the cone swing platform.

The SLDPRT remains authoritative.  The plan imports the plate outline,
post-mount pattern, lock notch and corner radii; the native Hole Wizard callout
defines the pivot clearance hole; section A-A exposes the shallow pivot-head
relief and plate thickness in solid lines.  Display precision comes from the
model.

The platform is an asymmetric steel wedge with a 1/4-in close-clearance pivot
hole over the stock screw shoulder, paired 1/4-20 post-mount taps, an open
west-edge lock notch, four rounded plan corners and the counterbored slot
for the tip block's hidden hold-down screw (U30).  The three plan views run
1:2 and pivot section A-A 2:1.  Slot detail B enlarges a 12 mm radius
around the pivot-to-slot region at 2:1, hidden lines dashed, at sheet
(88, 44) mm; section C-C (1:1) cuts along the slot for the counterbore
depth.  The isometric runs 1:3.

Run with SolidWorks open::

    uv run python cad\scripts\draw_cone_swing_platform.py cone-swing-platform
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    rebuild_drawing,
    new_project_drawing,
    model_point_in_view,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_dimension_callouts,
    set_reference_dimension,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
)
from _hole_spec import blind_cut_dia_mm
from _surface_finish import surface_finish_by_key
from cone_swing_platform_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIVOT_HOLE_DIA,
    PLATE_STOCK_CALLOUT,
    PLATE_THICKNESS,
    POST_MOUNT_SPEC,
    SURFACE_FINISHES,
    TIP_CBORE_W,
    TIP_SCREW_LOCAL_Z,
    TIP_SLOT_W,
)
from diagnostics.drawing_layout_audit import collect_document, describe_sheet


SPEC = DRAWINGS_BY_NAME["cone_swing_platform"]
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

SHEET_SCALE = (1.0, 2.0)  # title block states the principal (plan) scale; iso and section carry their own

# Sheet layout (meters).  Three 1:2 plan views separate the profile, hole
# pattern and lock-notch definitions instead of routing unrelated leaders
# through one narrow 224-mm wedge.  The section and pictorial occupy the
# right-hand field.
PROFILE_CENTER = (0.075, 0.190)
FEATURE_CENTER = (0.180, 0.190)
NOTCH_CENTER = (0.260, 0.190)
ISO_CENTER = (0.355, 0.205)
# The section group sits up and right in the open field below the isometric,
# clear of the lock-notch caption; every section annotation shares this shift.
SECTION_SHIFT = (0.020, 0.015)


def _shifted(x: float, y: float) -> tuple[float, float]:
    return (x + SECTION_SHIFT[0], y + SECTION_SHIFT[1])


SECTION_CENTER = _shifted(0.335, 0.105)

PROFILE_KEEP = {
    "PlateLenDim": (0.025, PROFILE_CENTER[1]),
    "NorthEastX": (0.045, 0.105),
    "NorthWestX": (0.100, 0.115),
    "SouthWestX": (0.104, 0.258),
    "SouthEastX": (0.045, 0.259),
    # Radial rays must meet actual trimmed corners, not circle extensions.
    # CornerNE/R10 is left and CornerNW/R8 is right in this view.  R10 and
    # R12 shelves sit just above horizontal enough to land inside their arcs
    # while clearing the 223.4 witness lines.
    "CornerNER": (0.045, 0.139),
    "CornerNWR": (0.135, 0.118),
    "CornerSWR": (0.110, 0.249),
    "CornerSER": (0.040, 0.2435),
}
FEATURE_KEEP = {
    "PivotBearingReliefDia": (0.150, 0.155),
    "PostMountWestX": (0.150, 0.185),
    "PostMountWestZ": (0.225, 0.175),
    "PostMountEastX": (0.205, 0.185),
    "PostMountEastZ": (0.130, 0.175),
}
NOTCH_KEEP = {
    # Pivot-to-north-edge lives here, sharing the 205.81 pivot witness: in the
    # profile the R8 corner ray has no path that clears this dimension.
    "NorthEdgeZ": (0.270, 0.150),
    # Text between its witnesses: outside, it read as spanning from the corner.
    "CapECx": (0.2652, 0.258),
    "CapECz": (0.305, 0.180),
    "CapEDia": (0.285, 0.259),
}
SECTION_KEEP = {
    "PlateThk": _shifted(0.300, 0.120),
    "PivotBearingReliefDepth": _shifted(0.365, 0.115),
}

# U30 tip-block hold-down slot: too small to dimension at 1:2, so DETAIL B
# enlarges the pivot-to-slot region of the hole-location plan to 2:1, with
# hidden lines shown so the underside counterbored slot reads dashed.  At
# 1:1 (run 7959e994) five dimensions and two cutter callouts crowded a 24 mm
# circle, texts over the outline and each other; 2:1 gives them the room.
# The counterbore depth is section C-C's imported dimension.
#
# The free band is x 0.0127..0.216 under the plan captions (y <= 0.0805)
# and above the bottom border (y >= 0.0127).  Run e86bf319 put the detail in
# its right half, where the title block (x >= 0.216, y <= 0.066) boxed its
# callouts in and its native label fell 8.9 mm through the bottom border.
# So the relief-fit note moves to the band's lower right and the detail to
# its left half: the wide callouts get the open field right of the circle.
# A vertical dimension's text hangs outward from its dimension line (the
# e86bf319 extents: left of a left-side line, right of a right-side one).
# Sheet +x is model +x (west) and sheet +y is model -z (south) in these plans.
DETAIL_MODEL_Z = -6.0  # detail circle centre, between the pivot and the slot
DETAIL_RADIUS_MM = 12.0
DETAIL_SCALE = (2, 1)
_DETAIL_S = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0
DETAIL_CENTER = (0.088, 0.044)
DETAIL_SHEET_RADIUS = DETAIL_RADIUS_MM * _DETAIL_S
_PIVOT_Y = DETAIL_CENTER[1] + DETAIL_MODEL_Z * _DETAIL_S
_SLOT_Y = DETAIL_CENTER[1] + (DETAIL_MODEL_Z - TIP_SCREW_LOCAL_Z) * _DETAIL_S
DETAIL_KEEP = {
    # Right, nearest the circle: pivot to slot, its text between the relief
    # note's top (0.034) and the counterbore's lower extension line (0.046).
    "TipSlotZ": (DETAIL_CENTER[0] + 0.030, 0.0435),
    # Above the circle, each 2.00 outside its own extension lines and under
    # the plan caption row (y >= 0.0805).
    "TipSlotEastCx": (
        DETAIL_CENTER[0] - 0.020,
        DETAIL_CENTER[1] + DETAIL_SHEET_RADIUS + 0.005,
    ),
    "TipSlotWestCx": (
        DETAIL_CENTER[0] + 0.020,
        DETAIL_CENTER[1] + DETAIL_SHEET_RADIUS + 0.005,
    ),
    # Left: the through slot and its cutter, text hanging left to the border.
    "TipSlotW": (DETAIL_CENTER[0] - 0.032, _SLOT_Y),
    # Right, outboard of TipSlotZ: the counterbored slot and its cutter,
    # text hanging right above the relief note.
    "TipCboreW": (DETAIL_CENTER[0] + 0.048, _SLOT_Y),
}
# The native "DETAIL B / SCALE 2:1" label, moved by its measured extent:
# lower left of its box, in the band's lower-left corner under the slot text.
DETAIL_LABEL_LOWER_LEFT = (0.016, 0.015)
# The pivot relief-fit note (2.5 mm text, ~0.095 x 0.018): anchored by its
# upper-left corner, lower right of the free band, left of the title block.
RELIEF_NOTE_XY = (0.119, 0.034)
# SECTION C-C cuts across the plate along the slot (sheet-horizontal through
# its centre in detail B), so the counterbore's depth is an imported model
# dimension (drawing-simplicity rule 2: a typed "4.20 DEEP" was not).  The
# 1:1 strip, plate edge-on, sits in the free pocket between the notch plan
# (x <= 0.2806, y >= 0.1286), its caption row (y <= 0.0853), the relief
# dimension RD1 (x <= 0.246) and section A-A's finish symbol (x >= 0.316).
SLOT_SECTION_HALF_SPAN_MM = 9.0
SLOT_SECTION_CENTER = (0.296, 0.096)
SLOT_SECTION_KEEP = {
    "TipCboreDepth": (SLOT_SECTION_CENTER[0] - 0.015, SLOT_SECTION_CENTER[1]),
}
# Its native label, above the strip and left of the finish symbol.
SLOT_SECTION_LABEL_LOWER_LEFT = (0.258, 0.106)




_COSMETIC_THREAD_LAYER = "COSMETIC-THREADS-HIDDEN"


def _hide_profile_cosmetic_threads(adapter: Any, view: Any) -> None:
    """Hide the redundant model cosmetic-thread callout in the profile view."""
    draw = adapter.currentModel
    manager = _early_bound(draw.GetLayerManager(), "ILayerMgr")
    layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    if layer is None:
        if (
            int(
                manager.AddLayer(
                    _COSMETIC_THREAD_LAYER,
                    "cosmetic thread ink hidden in profile view",
                    0,
                    0,
                    0,
                )
            )
            != 1
        ):
            raise RuntimeError("failed to add hidden cosmetic-thread layer")
        layer = manager.GetLayer(_COSMETIC_THREAD_LAYER)
    layer = _early_bound(layer, "ILayer")
    layer.Visible = False
    if bool(layer.Visible) or bool(layer.Printable):
        raise RuntimeError("cosmetic-thread layer did not remain hidden")

    hidden = 0
    hidden_callouts = 0
    for raw_annotation in _early_bound(view, "IView").GetAnnotations() or ():
        annotation = _early_bound(raw_annotation, "IAnnotation")
        if int(annotation.GetType()) != 1:  # swCosmeticThread
            continue
        annotation.Layer = _COSMETIC_THREAD_LAYER
        if str(annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
            raise RuntimeError("profile cosmetic thread refused the hidden layer")
        thread = _early_bound(annotation.GetSpecificAnnotation(), "ICThread")
        raw_callout = _read_member(thread, "ThreadCallout")
        if raw_callout is not None:
            callout = _early_bound(raw_callout, "INote")
            callout_annotation = _early_bound(
                _read_member(callout, "GetAnnotation"), "IAnnotation"
            )
            callout_annotation.Layer = _COSMETIC_THREAD_LAYER
            if str(callout_annotation.Layer or "") != _COSMETIC_THREAD_LAYER:
                raise RuntimeError("profile thread callout refused the hidden layer")
            hidden_callouts += 1
        hidden += 1
    if not hidden:
        raise RuntimeError("profile view has no cosmetic thread to hide")
    if not hidden_callouts:
        raise RuntimeError("profile cosmetic threads have no callout note to hide")
    rebuild_drawing(adapter, label="hide profile cosmetic threads")


def _position_section_label(adapter: Any, section: Any) -> None:
    """Keep the native section caption below, rather than inside, the section."""
    notes = tuple(_read_member(section, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native section label, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    target = (*_shifted(0.335, 0.085), 0.0)
    if not annotation.SetPosition2(*target):
        raise RuntimeError("failed to position native section label")
    adapter.currentModel.EditRebuild3()
    actual = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    if max(abs(actual[i] - target[i]) for i in range(3)) > 1e-8:
        raise RuntimeError(
            f"native section label position did not persist: {actual}; "
            f"requested={target}"
        )


def _position_view_label(
    adapter: Any, view: Any, lower_left: tuple[float, float], *, label: str
) -> None:
    """Move a view's native label so its box's lower-left lands at ``lower_left``.

    The label's anchor is not its box corner, so the move is measured: read
    ``INote.GetExtent``, shift the anchor by the corner's error, read back.
    The sheet scale is pinned first; finalization re-applying it must not
    move a dynamic label after this readback.
    """
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError(f"cannot pin sheet scale before {label} placement")
    notes = tuple(_read_member(view, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"expected one native {label}, found {len(notes)}")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    for _attempt in range(2):
        extent = tuple(float(v) for v in note.GetExtent())
        error = (lower_left[0] - extent[0], lower_left[1] - extent[1])
        if max(abs(error[0]), abs(error[1])) < 0.0002:
            break
        anchor = tuple(float(v) for v in _read_member(annotation, "GetPosition"))
        moved = (anchor[0] + error[0], anchor[1] + error[1], 0.0)
        if not annotation.SetPosition2(*moved):
            raise RuntimeError(f"failed to position native {label}")
        adapter.currentModel.EditRebuild3()
    extent = tuple(float(v) for v in note.GetExtent())
    print(f"{label}: requested lower-left={lower_left} extent={extent}")
    if max(abs(lower_left[0] - extent[0]), abs(lower_left[1] - extent[1])) > 0.0005:
        raise RuntimeError(
            f"native {label} landed at {extent[:2]}, requested {lower_left}"
        )


def _create_detail_view(
    adapter: Any,
    parent_view: Any,
    *,
    model_center_mm: tuple[float, float, float],
    radius_mm: float,
    view_xy: tuple[float, float],
    detail_label: str,
    scale: tuple[int, int],
    label: str,
) -> Any:
    """Create a circular detail view around one model point of ``parent_view``.

    The circle is sketched in the parent view's own sketch space: the model
    point is projected to the sheet, then through the sketch transform, the same
    path ``create_section_view`` uses for its cutting line.
    """
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    if not ddoc.ActivateView(view_name(adapter, parent_view)):
        raise RuntimeError(f"failed to activate detail parent view ({label})")
    draw.ClearSelection2(True)
    center_m = tuple(value / 1000.0 for value in model_center_mm)
    rim_m = (center_m[0] + radius_mm / 1000.0, center_m[1], center_m[2])
    sheet = [
        model_point_in_view(adapter, parent_view, point, label=f"{label} {name}")
        for name, point in (("centre", center_m), ("rim", rim_m))
    ]
    sketch = _early_bound(_early_bound(parent_view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    math_utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet:
        point = _early_bound(
            math_utility.CreatePoint(double_array([float(x), float(y), 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    previous_add_to_db = bool(sketch_manager.AddToDB)
    sketch_manager.AddToDB = True
    try:
        circle = sketch_manager.CreateCircle(*points[0], *points[1])
    finally:
        sketch_manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the detail circle ({label})")
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    selection_data = selection_manager.CreateSelectData()
    selection_data.View = parent_view
    selectable = _sw_type_info.early_bound_or_flag(circle, "ISketchSegment", "Select4")
    if not selectable.Select4(False, selection_data):
        raise RuntimeError(f"failed to select the detail circle ({label})")
    detail = ddoc.CreateDetailViewAt4(
        float(view_xy[0]),
        float(view_xy[1]),
        0.0,
        0,  # swDetViewSTANDARD
        float(scale[0]),
        float(scale[1]),
        detail_label,
        1,  # swDetCircleCIRCLE
        True,  # FullOutline
        False,  # JaggedOutline
        False,  # NoOutline
        5,
    )
    draw.ClearSelection2(True)
    if detail is None:
        raise RuntimeError(f"CreateDetailViewAt4 returned no view ({label})")
    detail = _sw_type_info.early_bound_or_flag(
        detail, "IView", "SetViewPosition", "Position"
    )
    rebuild_drawing(adapter, label=f"create detail view {detail_label}")
    # A detail view's Position is its model-origin anchor, not the circle
    # centre (run 2b643c17 placed the circle 99 mm below the request).  Move
    # the anchor until the circle's model centre lands on ``view_xy``.
    for attempt in range(2):
        landed = model_point_in_view(
            adapter, detail, center_m, label=f"{label} centre, pass {attempt}"
        )
        anchor = tuple(float(v) for v in detail.Position)
        if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) < 0.0002:
            break
        moved = (
            anchor[0] + view_xy[0] - landed[0],
            anchor[1] + view_xy[1] - landed[1],
        )
        if not detail.SetViewPosition(double_array(list(moved)), False):
            raise RuntimeError(f"failed to position the detail view ({label})")
        rebuild_drawing(adapter, label=f"place detail view {detail_label}")
    landed = model_point_in_view(adapter, detail, center_m, label=f"{label} centre")
    print(
        f"detail {detail_label}: parent_sheet_centre={sheet[0]} "
        f"sketch_centre={points[0]} requested={view_xy} landed={landed} "
        f"outline={tuple(float(v) for v in detail.GetOutline())}"
    )
    if max(abs(landed[0] - view_xy[0]), abs(landed[1] - view_xy[1])) > 0.0005:
        raise RuntimeError(
            f"detail {detail_label} centre landed at {landed}, requested {view_xy}"
        )
    return detail


def _visible_plan_controls(adapter: Any, view: Any) -> tuple[Any, Any]:
    """Return the pivot and post-mount rims from the plan view.

    The north-end and long-straight-side edges were dropped with the GD&T that
    referenced them (see ``build``) -- nothing else on this sheet attaches to
    them.
    """
    expected_radius_m = PIVOT_HOLE_DIA / 2000.0
    expected_mount_radius_m = blind_cut_dia_mm(POST_MOUNT_SPEC) / 2000.0
    pivot_edges: list[Any] = []
    mount_edges: list[Any] = []
    components = adapter._attempt(lambda: view.GetVisibleComponents(), default=()) or ()
    for component in components:
        edges = (
            adapter._attempt(
                lambda c=component: view.GetVisibleEntities2(c, 1), default=()
            )
            or ()
        )
        for raw_edge in edges:
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            values = tuple(float(value) for value in curve.CircleParams)
            if abs(values[6] - expected_radius_m) <= 1e-6:
                pivot_edges.append(edge)
            if abs(values[6] - expected_mount_radius_m) <= 1e-6:
                mount_edges.append(edge)
    if not pivot_edges or len(mount_edges) < 2:
        raise RuntimeError("cone-platform plan view is missing pivot/mount controls")
    return pivot_edges[0], mount_edges[0]


def _horizontal_section_edge(
    view: Any, y_mm: float, *, label: str, prefer_right: bool = False
) -> Any:
    """Return a horizontal section edge on one broad-face station."""
    candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} section edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - y_mm) <= 0.01 and abs(p1[1] - y_mm) <= 0.01:
            candidates.append((abs(p1[0] - p0[0]), 0.5 * (p0[0] + p1[0]), edge))
    if not candidates:
        raise RuntimeError(f"pivot section has no {label} edge at y={y_mm:.3f} mm")
    key_index = 1 if prefer_right else 0
    return max(candidates, key=lambda item: item[key_index])[2]


def _add_section_hole_axis(adapter: Any, section: Any) -> None:
    """Draw the pivot-hole axis between the two cut slices of section A-A.

    The cut-face-only section shows the hole as a bare gap; without its axis a
    reader takes the right slice for an unrelated fragment.
    """
    radius_mm = PIVOT_HOLE_DIA / 2.0
    walls: dict[int, Any] = {}
    for raw_edge in visible_view_entities(section, 1, label="pivot hole wall edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1] - p1[1]) < 1.0:
            continue
        for side in (-1, 1):
            if all(abs(p[0] - side * radius_mm) <= 0.01 for p in (p0, p1)):
                walls[side] = edge
                print(f"pivot hole wall {side:+d}: {p0} -> {p1}")
    if set(walls) != {-1, 1}:
        raise RuntimeError(f"section A-A shows {len(walls)} pivot hole walls, expected 2")
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, section)):
        raise RuntimeError("failed to activate section A-A for the hole axis")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for index, side in enumerate((-1, 1)):
        data = selection_manager.CreateSelectData()
        data.View = section
        if not _early_bound(walls[side], "IEntity").Select4(index > 0, data):
            raise RuntimeError(f"failed to select pivot hole wall {side:+d}")
    if int(selection_manager.GetSelectedObjectCount2(-1)) != 2:
        raise RuntimeError("pivot hole axis needs exactly the two wall edges selected")
    centerline = ddoc.InsertCenterLine2()
    draw.ClearSelection2(True)
    if centerline is None:
        raise RuntimeError("failed to insert the pivot hole axis in section A-A")
    rebuild_drawing(adapter, label="section A-A pivot hole axis")
    lines = tuple(_read_member(section, "GetCenterLines") or ())
    if not lines:
        raise RuntimeError("section A-A lost its pivot hole axis")
    print(f"section A-A centerlines: {len(lines)}")


def _section_edge_midpoint(
    adapter: Any, view: Any, edge: Any, *, label: str
) -> tuple[float, float]:
    """Return the sheet point at the middle of one broad-face section edge."""
    points = [
        tuple(float(value) for value in _early_bound(vertex, "IVertex").GetPoint())
        for vertex in (edge.GetStartVertex(), edge.GetEndVertex())
    ]
    middle = tuple(0.5 * (points[0][i] + points[1][i]) for i in range(3))
    if abs(middle[0]) * 1000.0 <= PIVOT_HOLE_DIA / 2.0 + 0.5:
        raise RuntimeError(f"{label} edge midpoint falls in the pivot hole: {middle}")
    sheet = model_point_in_view(adapter, view, middle, label=f"{label} edge midpoint")
    print(
        f"{label} finish attach: edge_model_m={points} middle_model_m={middle} "
        f"sheet_m=({sheet[0]:.5f},{sheet[1]:.5f})"
    )
    return (sheet[0], sheet[1])


def _assert_corner_radius_attachment(
    adapter: Any, view: Any, annotations: list[Any], *,
    name: str, feature_name: str, radius_m: float, station_xy: tuple[float, float],
) -> None:
    """Prove a native radius dimension's arrow lies on its owned visible arc."""
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one native {name} radius annotation")
    annotation = _early_bound(matches[0], "IAnnotation")
    # Imported fillet dimensions can return unsupported/null annotation entities.
    # Record that API honestly; model-dimension ownership below is authoritative.
    entities = annotation.GetAttachedEntities3()
    entity_types = annotation.GetAttachedEntityTypes()
    print(
        f"{name} annotation entities_none={entities is None} "
        f"entity_nulls={tuple(item is None for item in (entities or ()))} types={entity_types!r}"
    )
    dangling = annotation.IsDangling()
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    owner = _early_bound(dimension.GetFeatureOwner(), "IFeature")
    print(f"{name} native model dimension owner={owner.Name!r} dangling={dangling!r}")
    if dangling is not False or str(owner.Name) != feature_name:
        raise RuntimeError(f"{name} is dangling or is not owned by native {feature_name}")
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    arrows = [
        tuple(float(value) for value in data.GetArrowHeadAtIndex2(index))
        for index in range(int(data.GetArrowHeadCount()))
    ]
    if len(arrows) != 1 or len(arrows[0]) < 3:
        raise RuntimeError(f"expected one {name} arrow tip, found {arrows}")
    arrow = arrows[0]
    visible = visible_view_entities(view, 1, label=f"{name} visible corner edges")
    candidates = []
    for raw_face in owner.GetFaces() or ():
        face = _early_bound(raw_face, "IFace2")
        if str(_early_bound(face.GetFeature(), "IFeature").Name) != feature_name:
            continue
        for raw_edge in face.GetEdges() or ():
            edge = _early_bound(raw_edge, "IEdge")
            if not any(int(adapter.swApp.IsSame(edge, item)) == 1 for item in visible):
                continue
            if any(int(adapter.swApp.IsSame(edge, item[0])) == 1 for item in candidates):
                continue
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(circle[6] - radius_m) > 1e-8:
                continue
            center = model_point_in_view(adapter, view, circle[:3], label=f"{name} owned circle")
            if all(abs(center[i] - station_xy[i]) <= 0.001 for i in (0, 1)):
                candidates.append((edge, circle, center))
    # W18 (5db29554, run d9711228): the open pivot relief crosses the NW
    # fillet, so its plan arc is two physical edges on one circle -- one on
    # the 6.35 top, one on the 6.10 relief floor.  Every owned visible arc
    # must share the plan centre and radius; the arrow must land on one.
    if not candidates:
        raise RuntimeError(f"no {feature_name}-owned visible {name} edge at corner station")
    plan = [(circle[0], circle[2], circle[6]) for _edge, circle, _center in candidates]
    if any(math.dist(item, plan[0]) > 1e-8 for item in plan[1:]):
        raise RuntimeError(f"{name} owned arcs do not share one plan circle: {plan!r}")
    distances = []
    for edge, circle, center in candidates:
        # Invert the measured plan-view X/Z basis at this owned edge's model Y.
        px = model_point_in_view(adapter, view, (circle[0] + 0.001, circle[1], circle[2]), label=f"{name} X basis")
        pz = model_point_in_view(adapter, view, (circle[0], circle[1], circle[2] + 0.001), label=f"{name} Z basis")
        xx, xy = px[0] - center[0], px[1] - center[1]
        zx, zy = pz[0] - center[0], pz[1] - center[1]
        det = xx * zy - zx * xy
        if abs(det) < 1e-12:
            raise RuntimeError(f"{name} plan projection is singular")
        dx, dy = arrow[0] - center[0], arrow[1] - center[1]
        model_tip = (
            circle[0] + 0.001 * (dx * zy - zx * dy) / det,
            circle[1],
            circle[2] + 0.001 * (xx * dy - dx * xy) / det,
        )
        # IEdge, not ICurve: the closest point is on the trimmed physical edge.
        closest = tuple(float(value) for value in edge.GetClosestPointOn(*model_tip))
        trim = _early_bound(edge.GetCurveParams3(), "ICurveParamData")
        distance = math.dist(model_tip, closest[:3])
        distances.append(distance)
        print(
            f"{name} owned visible trimmed edge: arrow_sheet_m={arrow[:3]} radius_m={circle[6]} "
            f"center_model_m={circle[:3]} trim_u=({trim.UMinValue},{trim.UMaxValue}) "
            f"closest_u={closest[3]} arrow_model_m={model_tip} "
            f"closest_model_m={closest[:3]} distance_m={distance}"
        )
    if not min(distances) <= 0.00002:  # 0.01 mm on this 1:2 sheet; unchanged physical-edge bound.
        raise RuntimeError(f"{name} arrow does not land on its owned physical corner arc")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-swing-platform source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Profile View Note",
            "Feature View Note",
            "Notch View Note",
            "Isometric View Note",
            "Pivot Relief Fit",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Swing Platform Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone swing platform; wedge plate; pivot; lock notch",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    profile = place_view(
        adapter, str(SOURCE), "*Top", *PROFILE_CENTER, scale=(1, 2)
    )
    feature = place_view(
        adapter, str(SOURCE), "*Top", *FEATURE_CENTER, scale=(1, 2)
    )
    notch = place_view(adapter, str(SOURCE), "*Top", *NOTCH_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 3))
    for view in (profile, feature, notch, iso):
        set_hidden_lines_removed(adapter, view)

    pivot_xy = model_point_in_view(
        adapter, feature, (0.0, 0.0, 0.0), label="pivot section station"
    )
    feature_outline = tuple(float(value) for value in feature.GetOutline())
    section = create_section_view(
        adapter,
        feature,
        line_start=(feature_outline[0] - 0.002, pivot_xy[1]),
        line_end=(feature_outline[2] + 0.002, pivot_xy[1]),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=(2, 1),
        label="pivot bearing section",
    )
    cut = _early_bound(section.GetSection(), "IDrSection")
    cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="pivot section cut faces only")
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section retained geometry beyond the cutting plane")
    _position_section_label(adapter, section)
    set_hidden_lines_removed(adapter, section)
    _add_section_hole_axis(adapter, section)

    detail = _create_detail_view(
        adapter,
        feature,
        model_center_mm=(0.0, PLATE_THICKNESS, DETAIL_MODEL_Z),
        radius_mm=DETAIL_RADIUS_MM,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="tip screw slot detail",
    )
    # Hidden edges dashed, so the underside counterbored slot reads.
    set_hidden_lines_visible(adapter, detail)
    slot_ends = [
        model_point_in_view(
            adapter,
            detail,
            (x / 1000.0, PLATE_THICKNESS / 1000.0, TIP_SCREW_LOCAL_Z / 1000.0),
            label=f"slot section end {index}",
        )
        for index, x in enumerate(
            (-SLOT_SECTION_HALF_SPAN_MM, SLOT_SECTION_HALF_SPAN_MM)
        )
    ]
    slot_section = create_section_view(
        adapter,
        detail,
        line_start=slot_ends[0],
        line_end=slot_ends[1],
        view_xy=SLOT_SECTION_CENTER,
        section_label="C",
        scale=(1, 1),
        partial=True,
        label="tip screw slot section",
    )
    slot_cut = _early_bound(slot_section.GetSection(), "IDrSection")
    slot_cut.SetDisplayOnlySurfaceCut(True)
    rebuild_drawing(adapter, label="slot section cut faces only")
    set_hidden_lines_removed(adapter, slot_section)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    _hide_profile_cosmetic_threads(adapter, profile)
    feature_annotations = curate_view_dimensions(
        adapter,
        feature,
        keep=FEATURE_KEEP,
        view_label="feature plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Name the relief so the reader ties the width to the fit note; it is
    # open through the north edge (rule-12 W18), round-ended at the pivot.
    set_dimension_callouts(
        adapter,
        feature_annotations,
        {"PivotBearingReliefDia": "TOP RELIEF\nOPEN TO NORTH EDGE"},
    )
    notch_annotations = curate_view_dimensions(
        adapter,
        notch,
        keep=NOTCH_KEEP,
        view_label="notch plan",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    section_annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="pivot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for annotation in section_annotations:
        if dimension_name(adapter, annotation) == "PlateThk":
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            for witness_index in (0, 1):
                ok, _use_doc, old_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True:
                    raise RuntimeError("plate thickness witness gap could not be read")
                # Measured native witness origin is x415; the actual cut edge
                # is x310.2. Leave a visible 1.2 mm gap at x309, without
                # changing the model dimension or hiding either witness.
                gap = float(old_gap) + 0.106
                if display.SetWitnessLineGap(witness_index, False, gap) is not True:
                    raise RuntimeError("plate thickness witness gap was refused")
                ok, use_doc, actual_gap = display.GetWitnessLineGap(witness_index, False, 0.0)
                if ok is not True or use_doc or abs(float(actual_gap) - gap) > 1e-8:
                    raise RuntimeError("plate thickness witness gap did not persist")
                print(f"PlateThk witness {witness_index}: old_gap_m={old_gap} gap_m={actual_gap}")
            rebuild_drawing(adapter, label="plate thickness cut-edge witness gaps")
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="tip screw slot detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(
        adapter,
        detail_annotations,
        # The +0.10/0 width band is the cutter's own size: name the cutter.
        {
            "TipSlotW": f"<MOD-DIAM>{TIP_SLOT_W:g} END MILL\nSLOT THRU",
            "TipCboreW": (
                f"<MOD-DIAM>{TIP_CBORE_W:g} END MILL\nC'BORE SLOT\nFROM UNDERSIDE"
            ),
        },
    )
    # U41: the thickness is the stock's, a reference with no band.
    thickness_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PlateThk"
    ]
    if len(thickness_annotations) != 1:
        raise RuntimeError("expected one native plate thickness")
    thickness_reference = set_reference_dimension(
        adapter, thickness_annotations[0], label="stock plate thickness reference"
    )
    set_dimension_callouts(
        adapter, thickness_annotations, {"PlateThk": PLATE_STOCK_CALLOUT}
    )
    slot_section_annotations = curate_view_dimensions(
        adapter,
        slot_section,
        keep=SLOT_SECTION_KEEP,
        view_label="tip screw slot section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    relief_annotations = [
        item for item in section_annotations
        if dimension_name(adapter, item) == "PivotBearingReliefDepth"
    ]
    if len(relief_annotations) != 1:
        raise RuntimeError("expected one native pivot relief depth")
    relief_reference = set_reference_dimension(
        adapter, relief_annotations[0], label="matched pivot relief reference depth"
    )
    annotations = [
        *profile_annotations,
        *feature_annotations,
        *notch_annotations,
        *section_annotations,
        *detail_annotations,
        *slot_section_annotations,
    ]
    if not auto_center_marks(adapter, feature, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to feature plan")

    pivot_edge, mount_edge = _visible_plan_controls(adapter, feature)
    # Below the section line, between the A arrows: right of the plate the
    # 189.26 dimension line crosses any callout wider than ~40 mm.
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.215, 0.107),
        label="pivot close-clearance hole",
        edge=pivot_edge,
        process="DRILL",
    )
    add_native_hole_callout(
        adapter,
        feature,
        callout_xy=(0.200, 0.258),
        label="v2 post-mount tapped holes",
        edge=mount_edge,
    )
    # The section shows the top seat at the bottom.  Arrows land mid-face so
    # neither symbol reads as controlling a corner, hole wall or outer edge.
    seat_edge = _horizontal_section_edge(section, 6.35, label="top seat")
    add_surface_finish(
        adapter,
        section,
        symbol_xy=_shifted(0.291, 0.087),
        control=surface_finish_by_key(SURFACE_FINISHES, "post_seat"),
        label="post and tip-block seat finish",
        char_height=0.0025,
        entity=seat_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, seat_edge, label="top seat"),
    )
    slide_edge = _horizontal_section_edge(
        section, 0.0, label="base slide", prefer_right=True
    )
    add_surface_finish(
        adapter,
        section,
        # The layout audit boxes an Ra symbol 39 mm right of its anchor.
        symbol_xy=_shifted(0.355, 0.120),
        control=surface_finish_by_key(SURFACE_FINISHES, "base_slide"),
        label="base sliding-face finish",
        char_height=0.0025,
        entity=slide_edge,
        leader_attach_xy=_section_edge_midpoint(adapter, section, slide_edge, label="base slide"),
    )

    add_property_linked_note(adapter, "Profile View Note", 0.045, 0.085)
    add_property_linked_note(adapter, "Feature View Note", 0.150, 0.085)
    add_property_linked_note(adapter, "Notch View Note", 0.245, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", 0.315, 0.158)
    add_property_linked_note(
        adapter, "Pivot Relief Fit", *RELIEF_NOTE_XY, char_height=0.0025
    )

    # Annotation insertion can invalidate the exported display geometry.
    for view in (profile, feature, notch, section, slot_section, iso):
        set_hidden_lines_removed(adapter, view)
    # Re-assert after the dimensions attach: the shared helper passes through
    # HLR, so the dashed edge set is regenerated, not a same-mode no-op.
    set_hidden_lines_visible(adapter, detail)
    # Last, after every annotation and display-mode regen could re-lay it.
    _position_view_label(
        adapter, detail, DETAIL_LABEL_LOWER_LEFT, label="detail B label"
    )
    _position_view_label(
        adapter,
        slot_section,
        SLOT_SECTION_LABEL_LOWER_LEFT,
        label="section C-C label",
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if (str(relief_reference.GetText(1)), str(relief_reference.GetText(2))) != ("(", ")"):
        raise RuntimeError("pivot relief reference state did not persist")
    if (
        str(thickness_reference.GetText(1)),
        str(thickness_reference.GetText(2)),
    ) != ("(", ")"):
        raise RuntimeError("stock plate thickness reference state did not persist")
    for name, feature_name, radius_m, station_xy in (
        ("CornerSWR", "CornerSW", 0.005, (0.0875, 0.2433)),
        ("CornerNWR", "CornerNW", 0.008, (0.0723, 0.1382)),
        ("CornerNER", "CornerNE", 0.010, (0.0686, 0.1392)),
        ("CornerSER", "CornerSE", 0.012, (0.0660, 0.2398)),
    ):
        _assert_corner_radius_attachment(
            adapter, profile, profile_annotations,
            name=name, feature_name=feature_name, radius_m=radius_m, station_xy=station_xy,
        )
    if cut.GetDisplayOnlySurfaceCut() is not True:
        raise RuntimeError("pivot section lost its cut-only display after annotation")
    for face_name, model_y in (
        ("post_seat", PLATE_THICKNESS / 1000.0),
        ("base_slide", 0.0),
    ):
        projected = model_point_in_view(
            adapter, section, (0.0, model_y, 0.0), label=f"{face_name} projection"
        )
        print(
            f"section face {face_name}: model_y_mm={model_y * 1000:.3f} "
            f"sheet_xy_mm=({projected[0] * 1000:.3f},{projected[1] * 1000:.3f})"
        )
    for sheet_geometry in collect_document(adapter):
        print(describe_sheet(sheet_geometry))
        thickness_geometry = [
            item for item in sheet_geometry.annotations if item.label == "PlateThk"
        ]
        if len(thickness_geometry) != 1:
            raise RuntimeError("expected one measured plate thickness annotation")
        witnesses = [
            segment for segment in thickness_geometry[0].segments
            if abs(segment.y0 - segment.y1) < 1e-8
            and any(
                abs(segment.y0 - SECTION_SHIFT[1] - level) < 0.0001
                for level in (0.09865, 0.11135)
            )
        ]
        if len(witnesses) != 2 or any(
            abs(max(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.309) > 0.0005
            or abs(min(segment.x0, segment.x1) - SECTION_SHIFT[0] - 0.299) > 0.0005
            for segment in witnesses
        ):
            raise RuntimeError(f"plate thickness witnesses did not shorten to the cut edge: {witnesses}")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Swing Platform Manufacturing Drawing",
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

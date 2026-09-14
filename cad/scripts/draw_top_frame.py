r"""Create the curated machinist drawing for the green-painted top-frame casting.

The SLDPRT remains authoritative.  This recipe supplies only native model
dimensions, associative hole callouts, and the views of the casting; shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.  The top view carries the ring, web, boss, socket, and
crossbar dimensions.  Section A-A carries the recessed cap-seat dimensions and
the cross-tap callout.

The package uses two landscape sheets: GEOMETRY owns the projected envelope
and pictorial view; HOLES-SOCKETS owns socket/station/cap details, sections, and
the set-screw detail. Each sheet keeps its projected top/front pair aligned.

Run with SolidWorks open::

    uv run python cad\scripts\draw_top_frame.py top-frame
"""

from __future__ import annotations

import argparse
import sys
from typing import Any


import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_edge_dimension,
    dimension_name,
    set_arc_endpoints_to_center,
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
    BOSS_ABOVE,
    BOSS_BELOW,
    FLANGE,
    FLANGE_BOT_Y,
    GUSSET,
    EDGE_CHAMFER,
    ROOT_FILLET_R,
    OUTER_Z,
    RAIL_W_FR,
    INNER_X,
    INNER_Z,
    RING_HEIGHT,
    WEB_T,
    WEB_IN_X,
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
    HUB_BOSS_DIA,
    HUB_BOSS_DROP,
    HUB_GUSSET_T,
    HUB_GUSSET_HALF_IN,
    HUB_GUSSET_HALF_OUT,
    KEEPER_TAP_SPEC,
    KEEPER_TAP_X,
    KEEPER_TAP_Z_FRONT,
    OUTER_X,
    SET_POCKET_DEPTH,
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

SHEET_NAMES = ("GEOMETRY", "HOLES-SOCKETS")
SHEET_SCALE = (1.0, 3.0)
GEOMETRY_VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]
DETAIL_VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]

# Plan extents including the proud corner bosses (the straight rails alone
# stop at x +/-214.1 / z +/-131.0): x +/-223.1 -> 446.2 and z +/-138.1 ->
# 276.2 envelope; the boss stack is 47.3 tall around the 36.5 rail band.
PLAN_HALF_X = COLUMN_X + BOSS_DIA / 2.0
PLAN_HALF_Z = abs(FRONT_COLUMN_Z) + BOSS_DIA / 2.0
GEOMETRY_PLAN_HALF_W = PLAN_HALF_X * GEOMETRY_VIEW_SCALE / 1000.0
GEOMETRY_PLAN_HALF_D = PLAN_HALF_Z * GEOMETRY_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_W = PLAN_HALF_X * DETAIL_VIEW_SCALE / 1000.0
DETAIL_PLAN_HALF_D = PLAN_HALF_Z * DETAIL_VIEW_SCALE / 1000.0

# The title block begins at x=.216 and y=.066 on the landscape template.
# Every detail-sheet feature stays to its left or above its top edge.
NOTE_COLUMN_X = 0.308
NOTE_CHAR_HEIGHT = 0.002

# Sheet 1: overall envelope and non-hole geometry.  Top/front remain
# horizontally projected; the isometric supplements those orthographic views.
GEOMETRY_TOP_CENTER = (0.145, 0.185)
GEOMETRY_FRONT_CENTER = (0.145, 0.090)
GEOMETRY_ISO_CENTER = (0.072, 0.052)
ISO_SCALE = (1, 5)

# Sheet 2: socket, station, cap, and tap information at a larger view scale.
DETAIL_TOP_CENTER = (0.145, 0.185)
DETAIL_FRONT_CENTER = (0.145, 0.095)
DETAIL_SECTION_CENTER = (0.320, 0.130)
DETAIL_LEFT_CENTER = (0.145, 0.040)
DETAIL_LEFT_SCALE = (1, 4)

GEOMETRY_TOP_NOTE_XY = (0.015, 0.245)
GEOMETRY_FRONT_NOTE_XY = (0.025, 0.120)
GEOMETRY_ISO_NOTE_XY = (0.042, 0.018)
DETAIL_TOP_NOTE_XY = (0.030, 0.265)
DETAIL_FRONT_NOTE_XY = (0.030, 0.075)
MANUFACTURING_NOTES_XY = (NOTE_COLUMN_X, 0.263)

# Sheet 1 retains only the outside/web and crossbar geometry.  Hole, socket,
# cap, and set-screw stations are controlled once on sheet 2.
GEOMETRY_TOP_KEEP = {
    "Width": (
        GEOMETRY_TOP_CENTER[0],
        GEOMETRY_TOP_CENTER[1] + GEOMETRY_PLAN_HALF_D + 0.006,
    ),
    "Depth": (0.025, GEOMETRY_TOP_CENTER[1]),
    "WinWidth": (
        GEOMETRY_TOP_CENTER[0],
        GEOMETRY_TOP_CENTER[1] + GEOMETRY_PLAN_HALF_D + 0.001,
    ),
    "WinDepth": (0.025, GEOMETRY_TOP_CENTER[1] + 0.030),
    "BarAnchorX": (0.255, GEOMETRY_TOP_CENTER[1] - 0.065),
    "RibWidth": (0.255, GEOMETRY_TOP_CENTER[1] + 0.012),
    "PocketRun": (0.255, GEOMETRY_TOP_CENTER[1]),
    "SetTapZ": (0.255, GEOMETRY_TOP_CENTER[1] - 0.012),
    "BarFootSpan": (0.255, GEOMETRY_TOP_CENTER[1] - 0.030),
    "GussetRunE": (0.255, GEOMETRY_TOP_CENTER[1] - 0.042),
    "BarSideE": (0.255, GEOMETRY_TOP_CENTER[1] - 0.054),
}
GEOMETRY_FRONT_KEEP = {
    "PocketRise": (
        GEOMETRY_FRONT_CENTER[0] + GEOMETRY_PLAN_HALF_W + 0.010,
        GEOMETRY_FRONT_CENTER[1],
    ),
}
GEOMETRY_CALLOUTS = {
    "GussetRunE": "4X 45 DEG GUSSET",
}

# sit outside the 1:3 plan silhouette; the cap-seat dimensions live in A-A.
DETAIL_TOP_KEEP = {
    "StudRearZ": (0.040, DETAIL_TOP_CENTER[1] - 0.065),
    "KeeperRearZ": (0.280, DETAIL_TOP_CENTER[1] - 0.065),
    "C0Dia": (0.275, DETAIL_TOP_CENTER[1] + 0.021),
    "B0Dia": (0.275, DETAIL_TOP_CENTER[1] + 0.009),
    "StudFrontX": (0.018, DETAIL_TOP_CENTER[1] + 0.045),
    "StudFrontZ": (0.018, DETAIL_TOP_CENTER[1] + 0.033),
    "KeeperFrontX": (0.275, DETAIL_TOP_CENTER[1] - 0.015),
    "KeeperFrontZ": (0.275, DETAIL_TOP_CENTER[1] - 0.027),
    "GnX": (0.018, DETAIL_TOP_CENTER[1] - 0.003),
    "GnZ": (0.018, DETAIL_TOP_CENTER[1] - 0.015),
}
DETAIL_FRONT_KEEP: dict[str, tuple[float, float]] = {}
DETAIL_SECTION_KEEP = {
    "BossTopExtent": (
        DETAIL_SECTION_CENTER[0] + 0.060,
        DETAIL_SECTION_CENTER[1] + 0.032,
    ),
    "BossBottomExtent": (
        DETAIL_SECTION_CENTER[0] + 0.060,
        DETAIL_SECTION_CENTER[1] - 0.032,
    ),
    "RingHeight": (
        DETAIL_SECTION_CENTER[0] + 0.040,
        DETAIL_SECTION_CENTER[1] - 0.012,
    ),
    "CapRecessDia": (
        DETAIL_SECTION_CENTER[0] - 0.040,
        DETAIL_SECTION_CENTER[1] + 0.020,
    ),
    "CapRecessDepth": (
        DETAIL_SECTION_CENTER[0] + 0.040,
        DETAIL_SECTION_CENTER[1] + 0.010,
    ),
}
DETAIL_CALLOUTS = {
    "C0Dia": "4X",
    "B0Dia": "4X SOCKET; FIT MHA-083 TUBE; SLIP BY HAND",
}
SECTION_CALLOUTS = {
    "BossTopExtent": "4X",
    "BossBottomExtent": "4X",
    "CapRecessDia": "4X CAP RECESS",
    "CapRecessDepth": "4X CAP SEAT",
}


def _add_ring_midline(adapter: Any, view: Any) -> None:
    """Expose the common model origin for the coordinate dimensions."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    drawing.EditSheet()
    sketch_manager = _early_bound(draw.SketchManager, "ISketchManager")
    for start, end in (
        ((-PLAN_HALF_X, 0.0, 0.0), (PLAN_HALF_X, 0.0, 0.0)),
        ((0.0, 0.0, -PLAN_HALF_Z), (0.0, 0.0, PLAN_HALF_Z)),
    ):
        points = [
            model_point_in_view(
                adapter, view, tuple(value/1000.0 for value in point),
                label="frame origin centerline",
            )
            for point in (start, end)
        ]
        if sketch_manager.CreateCenterLine(*points[0], 0.0, *points[1], 0.0) is None:
            raise RuntimeError("failed to create frame origin centerline")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


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
    precision: int = 1,
    entity_types: tuple[str, str] = ("EDGE", "EDGE"),
    suffix: str = "",
    exact_linear: bool = False,
) -> Any:
    points = [
        model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in point), label=label
        )
        for point in (p0, p1)
    ]
    if exact_linear:
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
        for point in (p0, p1):
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
        _select_view_entity(adapter, view, "EDGE", None, label=label, entity=selected[0])
        if not view.SelectEntity(selected[1], True):
            raise RuntimeError(f"{label}: failed to append second exact edge")
        draw = adapter.currentModel
        display = (
            draw.AddHorizontalDimension2(*text_xy, 0.0)
            if orientation == "horizontal"
            else draw.AddVerticalDimension2(*text_xy, 0.0)
        )
        draw.ClearSelection2(True)
        draw.EditRebuild3()
        if display is None:
            raise RuntimeError(f"{label}: exact-edge dimension failed")
    else:
        display = add_edge_dimension(
            adapter, view, p0=points[0], p1=points[1], text_xy=text_xy,
            label=label, orientation=orientation, entity_types=entity_types,
        )
    if center:
        set_arc_endpoints_to_center(adapter, display, label=label)
    native = _early_bound(display, "IDisplayDimension")
    measured = abs(float(_early_bound(native.GetDimension2(0), "IDimension").SystemValue)) * 1000.0
    if abs(measured - expected_mm) > 1e-5:
        raise RuntimeError(f"{label}: measured {measured:g}, expected {expected_mm:g} mm")
    annotation = _early_bound(native.GetAnnotation(), "IAnnotation")
    set_dimension_precision(
        adapter, [annotation], {dimension_name(adapter, annotation): precision}
    )
    if suffix:
        set_dimension_callouts(adapter, [annotation], {dimension_name(adapter, annotation): suffix})
    return native

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
    if not extension.SetUserPreferenceInteger(542, 0, 1):
        raise RuntimeError("failed to set end-only section cutting line")
    if extension.GetUserPreferenceInteger(542, 0) != 1:
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
    geometry_bottom = place_view(
        adapter, str(SOURCE), "*Bottom", 0.320, 0.125, scale=(1, 5),
    )
    set_hidden_lines_visible(adapter, geometry_bottom)
    bottom_dimensions = curate_view_dimensions(
        adapter, geometry_bottom, keep={"HubDia": (0.265, 0.135)},
        view_label="removed underside geometry",
    )
    set_dimension_callouts(adapter, bottom_dimensions, {"HubDia": "BOSS OD"})
    set_dimension_precision(adapter, bottom_dimensions, {"HubDia": 1})
    if add_note(adapter, "UNDERSIDE / REMOVED VIEW SCALE 1:5", 0.265, 0.083) is None:
        raise RuntimeError("failed to label removed underside view")
    gusset_z = GOOSENECK_Z + (HUB_GUSSET_HALF_IN+HUB_GUSSET_HALF_OUT)/2
    gusset_y = -HALF_H-HUB_BOSS_DROP/2
    _checked_dimension(
        adapter, geometry_bottom,
        p0=(GOOSENECK_X-HUB_GUSSET_T/2, gusset_y, gusset_z),
        p1=(GOOSENECK_X+HUB_GUSSET_T/2, gusset_y, gusset_z),
        text_xy=(0.275, 0.105), label="underside gusset thickness",
        expected_mm=HUB_GUSSET_T, orientation="horizontal", exact_linear=True,
        suffix="2X GUSSET CENTRED ON BORE",
    )
    _checked_dimension(
        adapter, geometry_bottom,
        p0=(GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H, GOOSENECK_Z-HUB_GUSSET_HALF_OUT),
        p1=(GOOSENECK_X-HUB_GUSSET_T/2, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT),
        text_xy=(0.265, 0.125), label="underside gusset overall span",
        expected_mm=2*HUB_GUSSET_HALF_OUT, orientation="vertical",
        entity_types=("VERTEX", "VERTEX"),
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
    rail_cut_x = COLUMN_X / 2.0
    rail_cut = model_point_in_view(
        adapter, geometry_front, (rail_cut_x / 1000.0, 0.0, 0.0),
        label="front rear rail section station",
    )[0]
    rail_section = create_section_view(
        adapter, geometry_front,
        line_start=(rail_cut, GEOMETRY_FRONT_CENTER[1] - 0.020),
        line_end=(rail_cut, GEOMETRY_FRONT_CENTER[1] + 0.020),
        view_xy=(0.320, 0.205), section_label="B", scale=(1, 3),
        label="T rail manufacturing section",
    )
    set_hidden_lines_visible(adapter, rail_section)
    for p0, p1, expected, xy, orientation, label in (
        ((rail_cut_x, 0.0, WEB_IN_Z), (rail_cut_x, 0.0, WEB_OUT_Z),
         WEB_T, (0.355, 0.180), "horizontal", "rail web thickness"),
        ((rail_cut_x, (FLANGE_BOT_Y+HALF_H-EDGE_CHAMFER)/2, INNER_Z),
         (rail_cut_x, (FLANGE_BOT_Y+HALF_H-EDGE_CHAMFER)/2, OUTER_Z),
         RAIL_W_FR, (0.355, 0.230), "horizontal", "front rear flange width"),
        ((rail_cut_x, HALF_H, (INNER_Z+WEB_IN_Z)/2),
         (rail_cut_x, FLANGE_BOT_Y, (INNER_Z+WEB_IN_Z)/2),
         FLANGE, (0.385, 0.215), "vertical", "top flange thickness"),
        ((rail_cut_x, HALF_H, abs(FRONT_COLUMN_Z)),
         (rail_cut_x, -HALF_H, abs(FRONT_COLUMN_Z)),
         RING_HEIGHT, (0.390, 0.195), "vertical", "rail total height"),
    ):
        _checked_dimension(
            adapter, rail_section, p0=p0, p1=p1, text_xy=xy,
            label=label, expected_mm=expected, orientation=orientation, exact_linear=True,
        )
    _checked_dimension(
        adapter, rail_section,
        p0=(rail_cut_x, HALF_H, INNER_Z + EDGE_CHAMFER),
        p1=(rail_cut_x, HALF_H-EDGE_CHAMFER, INNER_Z),
        text_xy=(0.290, 0.250), label="top rim chamfer",
        expected_mm=EDGE_CHAMFER, orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"), suffix="X 45 DEG TOP RIMS",
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
    add_property_linked_note(
        adapter,
        "Manufacturing Notes",
        *MANUFACTURING_NOTES_XY,
        char_height=NOTE_CHAR_HEIGHT,
    )
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
        line_start=(cut_x, DETAIL_FRONT_CENTER[1] - 0.030),
        line_end=(cut_x, DETAIL_FRONT_CENTER[1] + 0.030),
        view_xy=DETAIL_SECTION_CENTER,
        section_label="A",
        scale=(1, 4),
        label="top-frame corner section",
    )
    detail_left = place_view(
        adapter,
        str(SOURCE),
        "*Left",
        *DETAIL_LEFT_CENTER,
        scale=DETAIL_LEFT_SCALE,
    )
    for view in (detail_top, detail_front):
        set_hidden_lines_visible(adapter, view)
    for view in (detail_section, detail_left):
        set_hidden_lines_removed(adapter, view)

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
    if not auto_center_marks(adapter, detail_top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top-frame hole pattern")
    _add_ring_midline(adapter, detail_top)
    _checked_dimension(
        adapter, detail_top,
        p0=(-COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2),
        p1=(COLUMN_X, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z + BORE_DIA/2),
        text_xy=(DETAIL_TOP_CENTER[0], 0.245), label="socket horizontal pitch",
        expected_mm=2*COLUMN_X, orientation="horizontal", center=True, precision=2,
    )
    _checked_dimension(
        adapter, detail_top,
        p0=(COLUMN_X + BORE_DIA/2, HALF_H + BOSS_ABOVE, FRONT_COLUMN_Z),
        p1=(COLUMN_X + BORE_DIA/2, HALF_H + BOSS_ABOVE, REAR_COLUMN_Z),
        text_xy=(0.255, DETAIL_TOP_CENTER[1]), label="socket vertical pitch",
        expected_mm=REAR_COLUMN_Z-FRONT_COLUMN_Z, orientation="vertical",
        center=True, precision=2,
    )

    front_tap_candidates: list[tuple[float, float, float, Any]] = []
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
    add_native_hole_callout(
        adapter,
        detail_front,
        edge=front_tap_edge,
        callout_xy=(
            DETAIL_FRONT_CENTER[0] + DETAIL_PLAN_HALF_W + 0.012,
            DETAIL_FRONT_CENTER[1] + 0.020,
        ),
        label="front/rear column-retention bottoming taps",
        process="CROSS-SCREW TAP EACH END",
    )
    _checked_dimension(
        adapter, detail_front,
        p0=(COLUMN_X, HALF_H+BOSS_ABOVE, REAR_COLUMN_Z),
        p1=(COLUMN_X+SIDE_TAP_DRILL_DIA/2, 0.0, TOP_SCREW_SEAT_Z),
        text_xy=(0.225, 0.090), label="cross screw axis from boss top",
        expected_mm=HALF_H+BOSS_ABOVE, orientation="vertical", center=True,
        suffix="4X ON SOCKET AXES",
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
        callout_xy=(DETAIL_TOP_CENTER[0] - 0.040, DETAIL_TOP_CENTER[1] + 0.075),
        label="2X hanger-stud clearance holes",
        process="DRILL",
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
        callout_xy=(DETAIL_TOP_CENTER[0] + 0.100, DETAIL_TOP_CENTER[1] - 0.048),
        label="2X fulcrum-keeper blind taps",
        process="TAP",
    )
    bore_candidates: list[tuple[float, float, Any]] = []
    for raw_edge in visible_view_entities(
        detail_top, 1, label="top gooseneck clearance-bore circles"
    ):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
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
    _select_view_entity(
        adapter,
        detail_top,
        "EDGE",
        None,
        label="gooseneck clearance-bore diameter",
        entity=gooseneck_edge,
    )
    diameter_xy = (
        DETAIL_TOP_CENTER[0] - 0.095,
        DETAIL_TOP_CENTER[1] + 0.008,
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
    set_dimension_callouts(adapter, [annotation], {dimension_name(adapter, annotation): "DRILL THRU"})
    set_dimension_precision(adapter, [annotation], {dimension_name(adapter, annotation): 2})
    if not annotation.SetPosition2(diameter_xy[0], diameter_xy[1], 0.0):
        raise RuntimeError("failed to position gooseneck clearance-bore diameter")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    set_hidden_lines_visible(adapter, detail_left)
    tap_candidates: list[tuple[float, float, float, Any]] = []
    tap_x = -(OUTER_X - SET_POCKET_DEPTH)
    tap_radius = TAP_DRILL_MM[SET_TAP_SPEC.size] / 2.0
    for raw_edge in visible_view_entities(
        detail_left, 1, label="left gooseneck set-tap circles"
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
    add_native_hole_callout(
        adapter,
        detail_left,
        edge=set_tap_edge,
        callout_xy=(
            DETAIL_LEFT_CENTER[0] - 0.060,
            DETAIL_LEFT_CENTER[1] + 0.022,
        ),
        label="gooseneck set-screw blind tap",
        process="TAP",
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(-OUTER_X, HALF_H, GOOSENECK_Z),
        p1=(tap_x, 0.0, GOOSENECK_Z+tap_radius),
        text_xy=(0.195, 0.045), label="set screw axis from rail top",
        expected_mm=HALF_H, orientation="vertical", center=True,
        suffix="ON GOOSENECK BORE CENTRE",
    )
    _checked_dimension(
        adapter, detail_left,
        p0=(-WEB_OUT_X, -HALF_H, GOOSENECK_Z+HUB_GUSSET_HALF_OUT+HUB_BOSS_DROP),
        p1=(GOOSENECK_X, -HALF_H-HUB_BOSS_DROP, GOOSENECK_Z),
        text_xy=(0.205, 0.030), label="hub boss underside drop",
        expected_mm=HUB_BOSS_DROP, orientation="vertical",
    )
    set_hidden_lines_visible(adapter, detail_left)
    detail_top_note = add_note(
        adapter,
        "HOLE / SOCKET VIEWS SCALE 1:3",
        *DETAIL_TOP_NOTE_XY,
    )
    detail_front_note = add_note(
        adapter,
        "FRONT CROSS-TAP VIEW SCALE 1:3",
        *DETAIL_FRONT_NOTE_XY,
    )
    cap_fit_note = add_note(
        adapter,
        "CAP RECESS FIT MHA-133 / 9275K141; SLIP BY HAND",
        0.245,
        0.075,
    )
    left_note = add_note(
        adapter,
        "SET-SCREW DETAIL / REMOVED VIEW (SCALE 1:4)",
        DETAIL_LEFT_CENTER[0] - 0.034,
        DETAIL_LEFT_CENTER[1] - 0.016,
    )
    if (
        detail_top_note is None
        or detail_front_note is None
        or cap_fit_note is None
        or left_note is None
    ):
        raise RuntimeError("failed to label top-frame holes/sockets sheet")
    for view in (detail_top, detail_front):
        set_hidden_lines_visible(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Frame Ring Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts={name: SPEC.layout for name in SHEET_NAMES},
        redundant_note_substrings=("Tapped Hole",),
        expected_redundant_notes=2,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

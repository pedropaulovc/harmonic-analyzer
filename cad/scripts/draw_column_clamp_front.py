r"""Create the curated machinist drawing for the column clamp, front arc.

The SLDPRT remains authoritative.  This recipe supplies only the front-arc
views, dimension layout, hole callouts, and manufacturing notes; every shared
sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The sheet runs at 2:1 (the arc is 48 mm ear tip to ear tip); the isometric
carries an explicit 1:1 override so it stays clear of the title block.  Third
angle: the top view (the 17.9 x 48 plan carrying the column-relief arc) sits
above the front view; the right view (the 48 x 16 bar face carrying the two
ear holes) sits to its right.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
clamp casting carries no datums, no feature-control frames, no roughness
symbols and no basic dimensions -- the slip-fit relief carries its band on
the model dimension, the title block governs the rest, and the relief is
finished as a pair with its back arc.  The bore and the ear-hole pattern are
located from the block's own faces by entity-selected dimensions; the bar
face is flagged from the view.

Run with SolidWorks open::

    uv run python cad\scripts\draw_column_clamp_front.py column-clamp-front
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    view_name,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from column_clamp_front_spec import (
    ARC_DEPTH,
    ARC_HEIGHT,
    ARC_WIDTH,
    BAR_FACE_FLAG,
    BORE_RADIUS,
    EAR_HOLE_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["column_clamp_front"]
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

SHEET_SCALE = (2.0, 1.0)

# Sheet layout (meters).  The model bbox runs 0..17.9 in X (depth), +/-8 in Y
# (height) and +/-24 in Z (width); at 2:1 the front view is 35.8 x 32 mm, the
# top view 35.8 x 96 mm, the right view 96 x 32 mm.
FRONT_CENTER = (0.105, 0.125)
TOP_CENTER = (0.105, 0.205)
RIGHT_CENTER = (0.250, 0.125)
ISO_CENTER = (0.355, 0.205)

_M = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters


# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  All three live on the top view (their sketches lie on the part's
# Top plane): the depth chain above the view, the width chain to its left, the
# bore diameter leadered off the relief arc.
TOP_KEEP = {
    "Depth": (0.105, 0.261),
    "Width": (0.058, 0.205),
    "BoreDia": (0.158, 0.243),
}
FRONT_KEEP = {}
RIGHT_KEEP = {}
DIMENSION_CALLOUTS = {
    "BoreDia": "BORE THRU\nSLIP FIT ON <MOD-DIAM>25.4 COLUMN",
}
# The relief is the one fitted feature (slip-fit band on the model dimension,
# build_column_clamp_front): three decimals say "hold it".
DIMENSION_PRECISION = {"BoreDia": 3}
# Bore axis along the 48 width, LEFT of the plan between the view and the
# 48 width chain (on the right it sat under the bore-diameter leader, which
# crossed it); ear-hole pattern origin (one hole from its end, both from the
# bottom face) on the right view; the ear-hole callout parked under the
# right view, clear of the bar-face flag.
BORE_STATION_TEXT_X = TOP_CENTER[0] - ARC_DEPTH / 2.0 * _M - 0.014
EAR_END_OFFSET_TEXT_Y = RIGHT_CENTER[1] + ARC_HEIGHT / 2.0 * _M + 0.013
EAR_PITCH_TEXT_Y = RIGHT_CENTER[1] + ARC_HEIGHT / 2.0 * _M + 0.020
EAR_HEIGHT_TEXT_X = RIGHT_CENTER[0] + ARC_WIDTH / 2.0 * _M + 0.010
EAR_CALLOUT_XY = (0.180, 0.088)


def _edge_points(edge: Any) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    start = edge.GetStartVertex()
    end = edge.GetEndVertex()
    if start is None or end is None:
        return None
    p0 = tuple(float(v) * 1000.0 for v in _early_bound(start, "IVertex").GetPoint())
    p1 = tuple(float(v) * 1000.0 for v in _early_bound(end, "IVertex").GetPoint())
    return p0, p1


def _straight_edge(
    adapter: Any,
    view: Any,
    *,
    fixed: dict[int, float],
    span_axis: int,
    label: str,
) -> Any:
    """Longest visible straight edge whose vertices sit at ``fixed`` {axis: mm}."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} edges"):
        edge = _early_bound(raw_edge, "IEdge")
        points = _edge_points(edge)
        if points is None:
            continue
        if any(
            abs(p[axis] - value) > 0.01 for p in points for axis, value in fixed.items()
        ):
            continue
        candidates.append((abs(points[1][span_axis] - points[0][span_axis]), edge))
    if not candidates:
        raise RuntimeError(f"{label}: no straight edge at {fixed!r}")
    return max(candidates, key=lambda item: item[0])[1]


def _circles(
    adapter: Any, view: Any, *, radius_mm: float, label: str
) -> list[tuple[tuple[float, float, float], Any]]:
    """Visible circular edges of one radius: (centre mm, edge)."""
    found: list[tuple[tuple[float, float, float], Any]] = []
    for raw_edge in visible_view_entities(view, 1, label=f"{label} circles"):
        edge = _early_bound(raw_edge, "IEdge")
        curve = edge.GetCurve()
        if curve is None:
            continue
        curve = _early_bound(curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = tuple(float(value) * 1000.0 for value in curve.CircleParams)
        if abs(params[6] - radius_mm) > 0.01:
            continue
        found.append(((params[0], params[1], params[2]), edge))
    if not found:
        raise RuntimeError(f"{label}: no circular edge of radius {radius_mm:.3f} mm")
    return found


@_telemetry.traced("drawing.entity_dimension", label_param="label")
def _entity_dimension(
    adapter: Any,
    view: Any,
    base_entity: Any,
    circle_entity: Any,
    *,
    orientation: str,
    position: tuple[float, float],
    label: str,
) -> Any:
    """Entity-selected edge-to-circle-centre dimension (the arbor recipe)."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    if not drawing.ActivateView(view_name(adapter, view)):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, base_entity), (True, circle_entity)):
        selection_data = selection_manager.CreateSelectData()
        selection_data.View = view
        entity = _early_bound(raw_entity, "IEntity")
        if not entity.Select4(append, selection_data):
            raise RuntimeError(f"failed to select {label} entity")
    if orientation == "horizontal":
        display = draw.AddHorizontalDimension2(*position, 0.0)
    elif orientation == "vertical":
        display = draw.AddVerticalDimension2(*position, 0.0)
    else:
        raise ValueError(f"unsupported dimension orientation: {orientation}")
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to create {label} dimension")
    set_arc_endpoints_to_center(adapter, display, label=label)
    return display


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open column-clamp-front source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Column Clamp Front Arc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "column clamp; front arc; gray iron casting; manufacturing drawing",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (policy rule 7): the
    # front view shows the ear drills edge-on, the top view the hidden
    # ear-hole rectangles beside the open arc.
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)

    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*top_annotations, *front_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    set_dimension_precision(
        adapter,
        [*top_annotations, *front_annotations, *right_annotations],
        DIMENSION_PRECISION,
    )

    # Bore axis along the 48 width: from one end face (z = +24 on the top
    # face) to the relief arc's centre.
    top_end = _straight_edge(
        adapter,
        top,
        fixed={1: ARC_HEIGHT / 2.0, 2: ARC_WIDTH / 2.0},
        span_axis=0,
        label="top-face end edge",
    )
    relief = _circles(adapter, top, radius_mm=BORE_RADIUS, label="relief arc")
    relief_arc = max(relief, key=lambda item: item[0][1])[1]  # the top-face arc
    end_xy = model_point_in_view(
        adapter, top, (0.0, ARC_HEIGHT / 2000.0, ARC_WIDTH / 2000.0), label="top end"
    )
    _entity_dimension(
        adapter,
        top,
        top_end,
        relief_arc,
        orientation="vertical",
        position=(BORE_STATION_TEXT_X, (end_xy[1] + TOP_CENTER[1]) / 2.0),
        label="bore axis station",
    )

    # The bar face (the flat x = ARC_DEPTH face the platen bar's back sits on,
    # masked from the paint): flagged from its corner edge on the front view,
    # with the collar-height dimension on the opposite side of the view.
    bar_edge = _straight_edge(
        adapter,
        front,
        fixed={0: ARC_DEPTH, 2: ARC_WIDTH / 2.0},
        span_axis=1,
        label="bar-face corner edge",
    )
    bar_xy = model_point_in_view(
        adapter, front, (ARC_DEPTH / 1000.0, 0.0, ARC_WIDTH / 2000.0), label="bar face"
    )
    bar_on_right = bar_xy[0] > FRONT_CENTER[0]
    collar_text_x = FRONT_CENTER[0] + (-0.033 if bar_on_right else 0.033)
    add_edge_dimension(
        adapter,
        front,
        p0=(FRONT_CENTER[0], FRONT_CENTER[1] - ARC_HEIGHT / 2.0 * _M),
        p1=(FRONT_CENTER[0], FRONT_CENTER[1] + ARC_HEIGHT / 2.0 * _M),
        text_xy=(collar_text_x, FRONT_CENTER[1]),
        label="collar-height overall",
    )
    flag_x = bar_xy[0] + 0.012 if bar_on_right else bar_xy[0] - 0.030
    add_attached_note(
        adapter,
        front,
        text=BAR_FACE_FLAG,
        entity=bar_edge,
        note_xy=(flag_x, FRONT_CENTER[1] - ARC_HEIGHT / 2.0 * _M - 0.011),
        label="bar face flag",
    )

    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the right view")

    # Ear-hole pattern on the right view (the bar face): the pitch between
    # the two rims, one hole from its own end face, and the pair's height
    # from the bottom face -- all entity-selected to the rim centres.
    rims = [
        (model_point_in_view(adapter, right, tuple(v / 1000.0 for v in center), label="ear rim")[0], center, edge)
        for center, edge in _circles(adapter, right, radius_mm=EAR_HOLE_DIA / 2.0, label="ear rims")
        if abs(center[0] - ARC_DEPTH) <= 0.01
    ]
    if len(rims) != 2:
        raise RuntimeError(f"right view shows {len(rims)} ear rims on the bar face, expected 2")
    rims.sort(key=lambda item: item[0])
    left_rim_x, left_center, left_rim = rims[0]
    right_rim_x, _right_center, right_rim = rims[-1]
    _entity_dimension(
        adapter,
        right,
        left_rim,
        right_rim,
        orientation="horizontal",
        position=(RIGHT_CENTER[0], EAR_PITCH_TEXT_Y),
        label="ear-hole spacing",
    )
    end_sign = 1.0 if left_center[2] > 0.0 else -1.0
    near_end = _straight_edge(
        adapter,
        right,
        fixed={0: ARC_DEPTH, 2: end_sign * ARC_WIDTH / 2.0},
        span_axis=1,
        label="bar-face end edge",
    )
    end_x = model_point_in_view(
        adapter,
        right,
        (ARC_DEPTH / 1000.0, 0.0, end_sign * ARC_WIDTH / 2000.0),
        label="bar-face end",
    )[0]
    _entity_dimension(
        adapter,
        right,
        near_end,
        left_rim,
        orientation="horizontal",
        position=((end_x + left_rim_x) / 2.0, EAR_END_OFFSET_TEXT_Y),
        label="ear-hole end offset",
    )
    bottom = _straight_edge(
        adapter,
        right,
        fixed={0: ARC_DEPTH, 1: -ARC_HEIGHT / 2.0},
        span_axis=2,
        label="bar-face bottom edge",
    )
    _entity_dimension(
        adapter,
        right,
        bottom,
        right_rim,
        orientation="vertical",
        position=(EAR_HEIGHT_TEXT_X, RIGHT_CENTER[1] - ARC_HEIGHT / 4.0 * _M),
        label="ear-hole height",
    )
    add_native_hole_callout(
        adapter,
        right,
        callout_xy=EAR_CALLOUT_XY,
        label="ear holes",
        edge=left_rim,
        process="#9 DRILL",
    )

    # 0.020: the note is left-aligned ON its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred border rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.060)
    add_property_linked_note(adapter, "Isometric View Note", 0.330, 0.168)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Column Clamp Front Arc Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

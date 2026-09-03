r"""Create the curated machinist drawing for the cone tip block.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
small clamp block carries no datums, no feature-control frames, no
roughness symbols and no basic dimensions -- the title block's general
tolerances govern everything.  The adjuster tap carries its own native
callout on the face it is tapped from; the pinch cross-hole is flagged from
the drawn +X face with a leader note; every hole axis is located from an
edge of the view it is drilled in.
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
    add_native_hole_callout,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_arc_endpoints_to_center,
    view_name,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import TAP_DRILL_MM
from cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_THREAD,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    PINCH_HOLE_NOTE,
    SHAFT_PASSAGE_DIA,
    SLIT_DEPTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
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

SHEET_SCALE = (2.0, 1.0)  # small 14x55 block -- 2:1 keeps the tall elevation legible
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Third-angle: the 14x12 plan sits ABOVE the front elevation (which carries the
# block height and clamp slit); the isometric is off to the right.
FRONT_CENTER = (0.100, 0.160)
TOP_CENTER = (0.100, 0.245)
RIGHT_CENTER = (0.205, 0.160)
ISO_CENTER = (0.330, 0.160)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot at model y=0)."""
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


# Front elevation carries the standing block width, height, shaft passage, top
# clamp slit depth and the adjuster tap; the plan carries the 12 depth and the
# slit width; the right view (the +X face) carries the pinch hole.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.014),
    "BlockHt": (FRONT_CENTER[0] - 0.028, FRONT_CENTER[1]),
    # Leadered from below-right so it stays under the slit-depth dimension.
    "PassageDiaDim": (FRONT_CENTER[0] + 0.048, _front_y(ADJUSTER_AXIS_HEIGHT) - 0.014),
    "PassageZ": (FRONT_CENTER[0] - 0.050, _front_y(ADJUSTER_AXIS_HEIGHT / 2.0)),
    # The slit is open to the front face, so its depth is a visible edge
    # dimension here (never to a hidden line).
    "SlitDepth": (FRONT_CENTER[0] + 0.030, _front_y(BLOCK_HEIGHT - SLIT_DEPTH / 2.0)),
}
TOP_KEEP = {
    # Text east of the plan so the arrows sit clear of the view.
    "Depth": (TOP_CENTER[0] + 0.052, TOP_CENTER[1]),
    # Below the plan, clear of the view outline (its text used to sit on the
    # slot's projected lines).
    "SlitW": (TOP_CENTER[0], 0.221),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "PassageDiaDim": "DRILL THRU",
}
# Nothing on this block is fitted: every dimension prints two places under the
# title-block tolerance.
DIMENSION_PRECISION = {"PassageZ": 2, "BlockHt": 2}

# Tap callout (front view = the north face the tap enters) and pinch flag note
# (right view = the +X face the pinch is drilled from).
TAP_CALLOUT_XY = (0.150, 0.215)
PINCH_NOTE_XY = (0.228, 0.205)
# Hole-axis locations: the pinch from a depth face in the right view, the
# passage/slit axis from a side face in the front view, both above the block.
AXIS_LOCATION_Y = 0.212


def _circle_entity(
    adapter: Any,
    view: Any,
    *,
    radius_mm: float,
    center_y_mm: float,
    label: str,
) -> Any:
    """Return a real circular model edge by size and vertical station."""
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
            f"height {center_y_mm:.3f} mm"
        )
    return edge


def _edge_vertices(edge: Any) -> tuple[tuple[float, ...], tuple[float, ...]] | None:
    start = edge.GetStartVertex()
    end = edge.GetEndVertex()
    if start is None or end is None:
        return None
    start = _early_bound(start, "IVertex")
    end = _early_bound(end, "IVertex")
    p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
    p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
    return p0, p1


def _foot_edge(adapter: Any, view: Any, *, min_span_mm: float = 13.9) -> Any:
    """Return the real bottom edge of the block's foot seat in ``view``.

    ``min_span_mm`` guards against picking a sliver edge: the foot spans
    BLOCK_X (14.0) in the front view and BLOCK_Z (12.0) in the right view.
    """
    candidates: list[tuple[float, float, Any]] = []
    for edge in visible_view_entities(view, 1, label="tip-block foot edges"):
        edge = _early_bound(edge, "IEdge")
        points = _edge_vertices(edge)
        if points is None:
            continue
        p0, p1 = points
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        # The foot's bottom edges run along model X in the front view and
        # along model Z in the right view — take the larger in-plane span.
        span_x = max(abs(p1[0] - p0[0]), abs(p1[2] - p0[2]))
        candidates.append((span_x, min(p0[2], p1[2]), edge))
    if not candidates:
        raise RuntimeError("front view has no model edge on the foot-seat plane")
    span_x, _z, edge = max(candidates, key=lambda item: item[0])
    if span_x < min_span_mm:
        raise RuntimeError(f"foot-seat edge span is only {span_x:.3f} mm")
    return edge


def _vertical_side_edge(
    adapter: Any, view: Any, *, x_mm: float, z_mm: float, label: str
) -> Any:
    """Return the tallest vertical block edge at plan station (x, z)."""
    candidates: list[tuple[float, Any]] = []
    for edge in visible_view_entities(view, 1, label=f"{label} side edges"):
        edge = _early_bound(edge, "IEdge")
        points = _edge_vertices(edge)
        if points is None:
            continue
        p0, p1 = points
        if any(abs(p[0] - x_mm) > 0.01 or abs(p[2] - z_mm) > 0.01 for p in (p0, p1)):
            continue
        candidates.append((abs(p1[1] - p0[1]), edge))
    if not candidates:
        raise RuntimeError(f"{label}: no vertical edge at x={x_mm:g}, z={z_mm:g}")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < BLOCK_HEIGHT - 0.1:
        raise RuntimeError(f"{label}: side edge spans only {span:.3f} mm")
    return edge


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
    """Entity-selected edge-to-circle-centre dimension (the arbor recipe).

    A sheet-picked dimension re-anchored to a circle centre was found to
    DANGLE on this sheet (rendered gray on the eye pass); entity selection
    does not.
    """
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

    check("open cone-tip-block source", await adapter.open_model(str(SOURCE)))
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip block; steel adjuster carrier; end-play thread lock",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (policy rule 7): the
    # elevation shows the passage as a hidden circle and the slit, the plan
    # the footprint with the bore and holes crossing it, the right view the
    # pinch bore into the slit.
    for view in (front, top, right):
        set_hidden_lines_visible(adapter, view)
    # SolidWorks auto-inserts a generic "<thread> Tapped Hole" note per Hole
    # Wizard tap normal to a placed view; the native callouts replace them
    # (draw_top_frame idiom).
    removed_tap_notes = remove_notes_matching(adapter, "Tapped Hole")
    _telemetry.info(
        f"removed {removed_tap_notes} redundant automatic tapped-hole note(s)"
    )

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(
        adapter,
        [*front_annotations, *top_annotations, *right_annotations],
        DIMENSION_CALLOUTS,
    )
    set_dimension_precision(
        adapter, [*front_annotations, *right_annotations], DIMENSION_PRECISION
    )
    for label, view in (("front", front), ("plan", top), ("right", right)):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center mark to the {label} view")

    # Adjuster tap: the native Hole Wizard callout (thread, thread depth and
    # tap-drill depth) on the tap rim in the front view -- the north face the
    # tap enters is the face toward the front camera.
    tap_entity = _circle_entity(
        adapter,
        front,
        radius_mm=TAP_DRILL_MM[ADJUSTER_THREAD] / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="adjuster tap",
    )
    add_native_hole_callout(
        adapter,
        front,
        callout_xy=TAP_CALLOUT_XY,
        label="adjuster tapped hole",
        edge=tap_entity,
    )
    # Slit / adjuster axis across the 14 width: from the drawn -X side face.
    passage_entity = _circle_entity(
        adapter,
        front,
        radius_mm=SHAFT_PASSAGE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="shaft passage",
    )
    front_side = _vertical_side_edge(
        adapter, front, x_mm=-BLOCK_X / 2.0, z_mm=BLOCK_Z / 2.0, label="front side"
    )
    side_xy = model_point_in_view(
        adapter, front, (-BLOCK_X / 2000.0, 0.0, BLOCK_Z / 2000.0), label="front side"
    )
    axis_xy = model_point_in_view(
        adapter, front, (0.0, ADJUSTER_AXIS_HEIGHT / 1000.0, 0.0), label="adjuster axis"
    )
    _entity_dimension(
        adapter,
        front,
        front_side,
        passage_entity,
        orientation="horizontal",
        position=((side_xy[0] + axis_xy[0]) / 2.0, AXIS_LOCATION_Y),
        label="adjuster-axis lateral location",
    )

    pinch_entity = _circle_entity(
        adapter,
        right,
        radius_mm=PINCH_CLEARANCE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch clearance",
    )
    # Pinch-axis height from the foot seat and its station across the 12
    # depth, both from a face drawn in the right view.
    base_edge = _foot_edge(adapter, right, min_span_mm=11.9)
    _entity_dimension(
        adapter,
        right,
        base_edge,
        pinch_entity,
        orientation="vertical",
        position=(RIGHT_CENTER[0] - 0.036, _front_y(PINCH_HEIGHT / 2.0)),
        label="pinch-axis height",
    )
    depth_face = _vertical_side_edge(
        adapter, right, x_mm=BLOCK_X / 2.0, z_mm=-BLOCK_Z / 2.0, label="right side"
    )
    depth_xy = model_point_in_view(
        adapter, right, (BLOCK_X / 2000.0, 0.0, -BLOCK_Z / 2000.0), label="depth face"
    )
    pinch_xy = model_point_in_view(
        adapter, right, (BLOCK_X / 2000.0, PINCH_HEIGHT / 1000.0, 0.0), label="pinch axis"
    )
    _entity_dimension(
        adapter,
        right,
        depth_face,
        pinch_entity,
        orientation="horizontal",
        position=((depth_xy[0] + pinch_xy[0]) / 2.0, AXIS_LOCATION_Y),
        label="pinch-axis depth station",
    )
    # The entry face is the drawn face: flag the pinch process from its rim.
    add_attached_note(
        adapter,
        right,
        text=PINCH_HOLE_NOTE,
        entity=pinch_entity,
        note_xy=PINCH_NOTE_XY,
        label="pinch hole",
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.088, char_height=0.0025
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Block Manufacturing Drawing",
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

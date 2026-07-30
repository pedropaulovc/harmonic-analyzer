r"""Create the curated machinist drawing for the cone tip block."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_arc_endpoints_to_center,
    set_basic_dimension,
    view_name,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    SHAFT_PASSAGE_DIA,
    SLIT_W,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    dimension_name,
    place_view,
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


# Front elevation carries the standing block width, height, shaft passage, and
# top clamp slit. The plan carries the 12 depth.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.014),
    "BlockHt": (FRONT_CENTER[0] - 0.028, FRONT_CENTER[1]),
    "PassageDiaDim": (FRONT_CENTER[0] + 0.048, _front_y(ADJUSTER_AXIS_HEIGHT)),
    "PassageZ": (FRONT_CENTER[0] - 0.050, _front_y(ADJUSTER_AXIS_HEIGHT / 2.0)),
    # Keep the slit width directly above the slot; the native 5/16-18 thread
    # callout routes rightward below it.
    "SlitW": (FRONT_CENTER[0], 0.232),
}
TOP_KEEP = {
    # Text far enough east that the dimension's arrows and the dim-attached
    # datum-D tag (which SolidWorks snaps to the text) sit clear of the view
    # and of each other (eye-pass catch: box/arrow through the 12.00 digits).
    "Depth": (TOP_CENTER[0] + 0.052, TOP_CENTER[1]),
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {
    "PassageDiaDim": "THRU - CLEARANCE PASSAGE",
}
DIMENSION_PRECISION = {"PassageZ": 2}


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
        key=lambda item: abs(item[0] - radius_mm)
        + abs(item[1] - center_y_mm),
    )
    if abs(radius - radius_mm) > 0.01 or abs(center_y - center_y_mm) > 0.01:
        raise RuntimeError(
            f"no {label} circle matches radius {radius_mm:.3f} mm at "
            f"height {center_y_mm:.3f} mm"
        )
    return edge


def _foot_edge(adapter: Any, view: Any, *, min_span_mm: float = 13.9) -> Any:
    """Return the real bottom edge of the block's foot seat in ``view``.

    ``min_span_mm`` guards against picking a sliver edge: the foot spans
    BLOCK_X (14.0) in the front view and BLOCK_Z (12.0) in the right view.
    """
    candidates: list[tuple[float, float, Any]] = []
    for edge in visible_view_entities(view, 1, label="tip-block foot edges"):
        edge = _early_bound(edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        start = _early_bound(start, "IVertex")
        end = _early_bound(end, "IVertex")
        p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
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
    for view in (right, iso):
        set_hidden_lines_removed(adapter, view)
    # The elevation carries the journal as a hidden circle and the adjuster/slit
    # detail; the plan shows the footprint with the bore and holes crossing it.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

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
    by_name = {
        dimension_name(adapter, annotation): annotation
        for annotation in front_annotations
    }
    for name, label in (("PassageZ", "adjuster common-axis height"),):
        display = adapter._attempt(lambda n=name: by_name[n].GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"{name} has no display dimension to box")
        set_basic_dimension(adapter, display, label=label)
    for label, view in (("front", front), ("plan", top), ("right", right)):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center mark to the {label} view")

    # Datum A = the foot seat face (the platform-seat datum the adjuster and
    # pinch-axis heights measure from).
    # Attach datum A to the RIGHT of the foot-bottom edge so its symbol clears
    # the centred 14.00 Width dimension (which sits at x=FRONT_CENTER[0]).
    foot_entity = _foot_edge(adapter, front)
    add_datum_feature(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.024, _front_y(0.0) - 0.010),
        datum="A",
        label="foot seat face",
        entity=foot_entity,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=FRONT_KEEP["Width"],
        symbol_xy=(FRONT_CENTER[0], _front_y(0.0) + 0.024),
        datum="B",
        label="block-width median plane",
        entity_type="DIMENSION",
        position_tolerance_m=0.001,
    )
    add_datum_feature(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + BLOCK_X / 2.0 * _S, _front_y(20.0)),
        symbol_xy=(FRONT_CENTER[0] + BLOCK_X / 2.0 * _S + 0.018, _front_y(20.0)),
        datum="E",
        label="positive-X pinch-entry face",
        # The tag is offset 18 mm off the +X edge (symbol_xy) to clear the
        # crowded lane; keep the accepted placement error well below that gap so
        # a SolidWorks snap-back onto the edge is caught rather than silently
        # passing (a 20 mm tolerance admitted the full 18 mm collapse).
        position_tolerance_m=0.010,
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=(TOP_CENTER[0], TOP_CENTER[1] + BLOCK_Z / 2.0 * _S),
        symbol_xy=(0.065, TOP_CENTER[1] + BLOCK_Z / 2.0 * _S),
        datum="C",
        label="adjuster entry face",
    )
    add_datum_feature(
        adapter,
        top,
        edge_xy=TOP_KEEP["Depth"],
        symbol_xy=TOP_KEEP["Depth"],
        datum="D",
        label="block-depth median plane",
        entity_type="DIMENSION",
        shoulder=True,
        position_tolerance_m=0.001,
    )
    passage_entity = _circle_entity(
        adapter,
        front,
        radius_mm=SHAFT_PASSAGE_DIA / 2.0,
        center_y_mm=ADJUSTER_AXIS_HEIGHT,
        label="adjuster passage",
    )
    add_feature_control_frame(
        adapter,
        front,
        frame_xy=(0.245, _front_y(ADJUSTER_AXIS_HEIGHT) - 0.058),
        characteristic="position",
        tolerance="0.05",
        datums=("A", "B", "C"),
        diameter=True,
        quantity="2 COAXIAL FEATURES; SIM REQT",
        label="adjuster common-axis true position",
        entity=passage_entity,
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(
            FRONT_CENTER[0] + SLIT_W / 2.0 * _S,
            _front_y(BLOCK_HEIGHT - 4.0),
        ),
        # Below the y=0.245 row so the leader down to the slit edge never
        # crosses the datum-D tag leader east of the plan-view depth text.
        frame_xy=(0.170, 0.239),
        characteristic="position",
        tolerance="0.10",
        datums=("B",),
        quantity="SLOT MEDIAN PLANE; BASIC 0 TO B",
        label="slot median-plane position",
    )
    pinch_entity = _circle_entity(
        adapter,
        right,
        radius_mm=PINCH_CLEARANCE_DIA / 2.0,
        center_y_mm=PINCH_HEIGHT,
        label="pinch clearance",
    )
    # Entity-selected vertical dimension (the sheet-pick + arc-center recipe
    # left the dimension DANGLING after the re-anchor — it rendered gray on the
    # eye-pass; the arbor sheet's entity-selected circle basics do not).
    with _telemetry.span("drawing.pinch_axis_height"):
        base_edge = _foot_edge(adapter, right, min_span_mm=11.9)
        draw = adapter.currentModel
        drawing = _early_bound(draw, "IDrawingDoc")
        if not drawing.ActivateView(view_name(adapter, right)):
            raise RuntimeError("failed to activate right view for pinch-axis height")
        draw.ClearSelection2(True)
        selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
        for append, raw_entity in ((False, base_edge), (True, pinch_entity)):
            selection_data = selection_manager.CreateSelectData()
            selection_data.View = right
            entity = _early_bound(raw_entity, "IEntity")
            if not entity.Select4(append, selection_data):
                raise RuntimeError("failed to select pinch-axis height entity")
        pinch_height = draw.AddVerticalDimension2(
            RIGHT_CENTER[0] - 0.036, _front_y(PINCH_HEIGHT / 2.0), 0.0
        )
        draw.ClearSelection2(True)
        if pinch_height is None:
            raise RuntimeError("failed to create pinch-axis height dimension")
        set_arc_endpoints_to_center(adapter, pinch_height, label="pinch-axis height")
        set_basic_dimension(adapter, pinch_height, label="pinch-axis height")
    add_feature_control_frame(
        adapter,
        right,
        frame_xy=(0.245, _front_y(PINCH_HEIGHT) - 0.030),
        characteristic="position",
        tolerance="0.05",
        datums=("A", "D", "E"),
        diameter=True,
        quantity="2 COAXIAL FEATURES; SIM REQT",
        label="pinch common-axis true position",
        entity=pinch_entity,
    )
    entry_face_label = add_note(adapter, "PINCH ENTRY FACE E (+X)", 0.180, 0.225)
    if entry_face_label is None:
        raise RuntimeError("failed to add datum-E pinch-entry face label")
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

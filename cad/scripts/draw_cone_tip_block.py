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
    add_property_linked_note,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cone_tip_block_spec import BLOCK_HEIGHT
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
ISO_CENTER = (0.330, 0.160)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot at model y=0)."""
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


# Front elevation carries the standing block width, height, shaft passage, and
# top clamp slit. The plan carries the 12 depth.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.014),
    "BlockHt": (FRONT_CENTER[0] - 0.028, FRONT_CENTER[1]),
    "PassageDiaDim": (FRONT_CENTER[0] + 0.048, _front_y(47.65)),
    "SlitW": (FRONT_CENTER[0] + 0.044, _front_y(BLOCK_HEIGHT)),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + 0.036, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {"PassageDiaDim": "THRU - CLEARANCE PASSAGE"}
DIMENSION_PRECISION: dict[str, int] = {}


def _foot_edge(adapter: Any, view: Any) -> Any:
    """Return the real front-view bottom edge of the block's foot seat."""
    drawing_view = _early_bound(view, "IView")
    candidates: list[tuple[float, float, Any]] = []
    for component in drawing_view.GetVisibleComponents() or []:
        for edge in drawing_view.GetVisibleEntities2(component, 1) or []:
            edge = _early_bound(edge, "IEdge", "GetStartVertex", "GetEndVertex")
            start = edge.GetStartVertex()
            end = edge.GetEndVertex()
            if start is None or end is None:
                continue
            start = _early_bound(start, "IVertex", "GetPoint")
            end = _early_bound(end, "IVertex", "GetPoint")
            p0 = tuple(float(value) * 1000.0 for value in start.GetPoint())
            p1 = tuple(float(value) * 1000.0 for value in end.GetPoint())
            if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
                continue
            span_x = abs(p1[0] - p0[0])
            candidates.append((span_x, min(p0[2], p1[2]), edge))
    if not candidates:
        raise RuntimeError("front view has no model edge on the foot-seat plane")
    span_x, _z, edge = max(candidates, key=lambda item: item[0])
    if span_x < 13.9:
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
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
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
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the plan view")

    # Datum A = the foot seat face (the platform-seat datum the adjuster and
    # pinch-axis heights measure from).
    # Attach datum A to the RIGHT of the foot-bottom edge so its symbol clears
    # the centred 14.00 Width dimension (which sits at x=FRONT_CENTER[0]).
    foot_edge = (FRONT_CENTER[0] + 0.005, _front_y(0.0))
    foot_entity = _foot_edge(adapter, front)
    add_datum_feature(
        adapter,
        front,
        edge_xy=foot_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.024, _front_y(0.0) - 0.010),
        datum="A",
        label="foot seat face",
        entity=foot_entity,
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.075, char_height=0.0025
    )
    removed = remove_notes_matching(adapter, "Tapped Hole")
    if removed != 2:
        raise RuntimeError(f"expected 2 auto tapped-hole notes, removed {removed}")

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

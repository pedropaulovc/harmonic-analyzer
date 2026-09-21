r"""Create the simplicity-policy machinist drawing for the cone tip block."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from cone_tip_block_spec import (
    ADJUSTER_AXIS_HEIGHT,
    ADJUSTER_BORE_DIA,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    DRAWING_PRECISION_BY_NAME,
    PINCH_BORE_DIA,
    PINCH_CLEARANCE_DIA,
    PINCH_HEIGHT,
    SHAFT_PASSAGE_DIA,
    SLIT_W,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view


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

SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0
FRONT_CENTER = (0.072, 0.129)
TOP_CENTER = (FRONT_CENTER[0], 0.225)
RIGHT_CENTER = (0.166, FRONT_CENTER[1])
LEFT_CENTER = (0.238, FRONT_CENTER[1])
BACK_CENTER = (0.310, FRONT_CENTER[1])
SECTION_CENTER = (0.190, 0.225)
ISO_CENTER = (0.330, 0.225)


def _elevation_y(model_y: float, center: tuple[float, float]) -> float:
    return center[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _elevation_y(0.0, FRONT_CENTER) - 0.012),
    "BlockHt": (FRONT_CENTER[0] - 0.033, FRONT_CENTER[1]),
    "PassageDiaDim": (
        FRONT_CENTER[0] + 0.038,
        _elevation_y(ADJUSTER_AXIS_HEIGHT, FRONT_CENTER),
    ),
    "PassageZ": (
        FRONT_CENTER[0] - 0.045,
        _elevation_y(ADJUSTER_AXIS_HEIGHT / 2.0, FRONT_CENTER),
    ),
    "SlitW": (FRONT_CENTER[0], _elevation_y(BLOCK_HEIGHT, FRONT_CENTER) + 0.014),
}
TOP_KEEP = {"Depth": (TOP_CENTER[0] - 0.035, TOP_CENTER[1])}
SECTION_KEEP = {
    "PinchZ": (
        SECTION_CENTER[0] - 0.036,
        _elevation_y(PINCH_HEIGHT / 2.0, SECTION_CENTER),
    )
}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
LEFT_KEEP: dict[str, tuple[float, float]] = {}
BACK_KEEP: dict[str, tuple[float, float]] = {}
DIMENSION_CALLOUTS = {"PassageDiaDim": "THRU - CLEARANCE PASSAGE"}


def _foot_edge(adapter: Any, view: Any, *, min_span_mm: float = 13.9) -> Any:
    """Return the longest real edge on the block's locating foot plane."""
    candidates: list[tuple[float, Any]] = []
    for raw_edge in visible_view_entities(view, 1, label="tip-block foot edges"):
        edge = _early_bound(raw_edge, "IEdge")
        start = edge.GetStartVertex()
        end = edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = tuple(float(value) * 1000.0 for value in _early_bound(start, "IVertex").GetPoint())
        p1 = tuple(float(value) * 1000.0 for value in _early_bound(end, "IVertex").GetPoint())
        if abs(p0[1]) > 0.01 or abs(p1[1]) > 0.01:
            continue
        span = max(abs(p1[0] - p0[0]), abs(p1[2] - p0[2]))
        candidates.append((span, edge))
    if not candidates:
        raise RuntimeError("front view has no real edge on the locating foot plane")
    span, edge = max(candidates, key=lambda item: item[0])
    if span < min_span_mm:
        raise RuntimeError(f"locating-foot edge span is only {span:.3f} mm")
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
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Tip Block Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip block; adjuster carrier; split pinch clamp",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=SHEET_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=SHEET_SCALE)
    left = place_view(adapter, str(SOURCE), "*Left", *LEFT_CENTER, scale=SHEET_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    for view in (front, top, right, left, back, iso):
        set_hidden_lines_removed(adapter, view)

    # The top-view cutting plane passes through both orthogonal bore axes.  The
    # resulting solid-line section shows the blind adjuster thread, clearance
    # passage, split jaws and pinch bore relationship without dashed inference.
    section = create_section_view(
        adapter,
        top,
        line_start=(TOP_CENTER[0], TOP_CENTER[1] - BLOCK_Z * _S / 2.0 - 0.004),
        line_end=(TOP_CENTER[0], TOP_CENTER[1] + BLOCK_Z * _S / 2.0 + 0.004),
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=SHEET_SCALE,
        label="adjuster and pinch-bore centre section",
    )
    set_hidden_lines_removed(adapter, section)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="passage entry elevation"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="plan"
    )
    section_annotations = curate_view_dimensions(
        adapter, section, keep=SECTION_KEEP, view_label="bore centre section"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="pinch clearance entry"
    )
    left_annotations = curate_view_dimensions(
        adapter, left, keep=LEFT_KEEP, view_label="pinch threaded entry"
    )
    back_annotations = curate_view_dimensions(
        adapter, back, keep=BACK_KEEP, view_label="adjuster threaded entry"
    )
    annotations = [
        *front_annotations,
        *top_annotations,
        *section_annotations,
        *right_annotations,
        *left_annotations,
        *back_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)

    for view, label in (
        (front, "shaft-passage entry"),
        (right, "pinch clearance entry"),
        (left, "pinch threaded entry"),
        (back, "adjuster threaded entry"),
    ):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add centre marks to {label} view")

    add_native_hole_callout(
        adapter,
        back,
        edge_xy=(
            BACK_CENTER[0] + ADJUSTER_BORE_DIA * _S / 2.0,
            _elevation_y(ADJUSTER_AXIS_HEIGHT, BACK_CENTER),
        ),
        callout_xy=(0.356, _elevation_y(ADJUSTER_AXIS_HEIGHT, BACK_CENTER) + 0.012),
        label="blind adjuster thread",
    )
    add_native_hole_callout(
        adapter,
        right,
        edge_xy=(
            RIGHT_CENTER[0],
            _elevation_y(PINCH_HEIGHT, RIGHT_CENTER) + PINCH_CLEARANCE_DIA * _S / 2.0,
        ),
        callout_xy=(0.182, 0.181),
        label="pinch entry-jaw clearance",
        process="DRILL",
    )
    add_native_hole_callout(
        adapter,
        left,
        edge_xy=(
            LEFT_CENTER[0],
            _elevation_y(PINCH_HEIGHT, LEFT_CENTER) + PINCH_BORE_DIA * _S / 2.0,
        ),
        callout_xy=(0.254, 0.181),
        label="pinch opposite-jaw thread",
    )

    foot_edge = _foot_edge(adapter, front)
    add_surface_finish(
        adapter,
        front,
        edge_entity=foot_edge,
        symbol_xy=(FRONT_CENTER[0] + 0.028, _elevation_y(0.0, FRONT_CENTER) - 0.006),
        control=surface_finish_by_key(SURFACE_FINISHES, "foot_seat"),
        label="swing-platform locating foot seat",
    )
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.020, 0.060, char_height=0.0025
    )

    # Annotation insertion can regenerate a view with inherited display state;
    # every manufacturing view is explicitly HLR at export.
    for view in (front, top, right, left, back, section):
        set_hidden_lines_removed(adapter, view)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Block Manufacturing Drawing",
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

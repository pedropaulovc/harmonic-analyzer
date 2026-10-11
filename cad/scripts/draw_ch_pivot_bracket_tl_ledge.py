r"""Create the drawing for the pivot bracket's angle-plate ledge (MHA-CH-008-TL-01).

A 22.6 x 27.7 x 6 block: the face view (front) carries the width, the
milled height and both screw-hole stations, each from the left end or the bottom
face (no chains); the edge view (right) carries the thickness; the iso
rides top-right at 2:1. No datums (policy rule 3).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_pivot_bracket_tl_ledge.py ch-pivot-bracket-tl-ledge
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import drill_process
from ch_pivot_bracket_tl_ledge_spec import (
    CLEARANCE_SPEC,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    HOLE_DIA,
    HOLE_X,
    HOLE_Y,
    LEDGE_HEIGHT,
    LEDGE_WIDTH,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["ch_pivot_bracket_tl_ledge"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (2, 1)
# Front: the 22.6 x 27.7 face at 4:1 is 90.4 x 110.8 mm, x 0.090..0.180 and
# y 0.110..0.220, above the stacked widths. Third angle: the edge view stands
# right of it, past the hole callout; the iso rides top-right.
FRONT_CENTER = (0.135, 0.165)
RIGHT_CENTER = (0.290, 0.165)
ISO_CENTER = (0.370, 0.205)
ISO_NOTE_XY = (0.340, 0.250)
NOTES_XY = (0.020, 0.070)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - LEDGE_WIDTH / 2.0) * SHEET_SCALE[0] / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (4:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - LEDGE_HEIGHT / 2.0) * SHEET_SCALE[0] / 1000.0


HOLE_R_SHEET = HOLE_DIA * SHEET_SCALE[0] / 2000.0
HOLE_Y_SHEET = _sheet_y(HOLE_Y)
HOLE_2_X_SHEET = _sheet_x(HOLE_X[1])

# Width and both hole X stations stack below the face from its left end;
# the height and the shared hole Y stand left of it from the bottom face;
# the thickness rides above the edge view.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], 0.088),
    "Hole2X": (_sheet_x(HOLE_X[1] / 2.0), 0.097),
    "Hole1X": (_sheet_x(HOLE_X[0] / 2.0), 0.106),
    "Height": (0.058, FRONT_CENTER[1]),
    "Hole1Y": (0.075, _sheet_y(HOLE_Y / 2.0)),
}
RIGHT_KEEP = {"Thick": (RIGHT_CENTER[0], 0.226)}
# Both holes stand on the one Y station the part prints (Hole1Y).
DIMENSION_PREFIXES = {"Hole1Y": "2X "}
HOLE_CALLOUT_XY = (0.200, 0.200)
HOLE_CALLOUT_PROCESS = drill_process(CLEARANCE_SPEC)


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open ledge source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pivot Bracket Angle-Plate Ledge Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot bracket angle-plate ledge; 1018 flat; MHA-CH-008-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, right):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="ledge face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="ledge edge",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places are authored on the part; the sheet only proves the import kept
    # them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)

    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the ledge face")
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=(
            HOLE_2_X_SHEET + 0.6 * HOLE_R_SHEET,
            HOLE_Y_SHEET + 0.8 * HOLE_R_SHEET,
        ),
        callout_xy=HOLE_CALLOUT_XY,
        label="ledge screw holes",
        process=HOLE_CALLOUT_PROCESS,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Bracket Angle-Plate Ledge Drawing",
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

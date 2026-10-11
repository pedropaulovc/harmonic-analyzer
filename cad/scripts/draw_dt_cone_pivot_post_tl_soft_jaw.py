r"""Create the drawing for the cone pivot post's tall vise soft jaw (MHA-DT-005-TL-04).

A flat plate needs only the gripping-face view (front, which shows the
counterbores as circles), the plan above it (third angle: the thickness)
and the shaded isometric. The plate's length, height and both bolt stations
print from its bottom-left corner; the counterbored holes ship as the native
wizard callout. No frames and no datums (fixtures are off the rule-3
allowlist).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from dt_cone_pivot_post_tl_soft_jaw_spec import (
    BOLT_HEIGHT,
    BOLT_LEFT_X,
    BOLT_RIGHT_X,
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PLATE_HEIGHT,
    PLATE_LENGTH,
)
from solidworks_mcp.adapters.solidworks.drawing import auto_center_marks, place_view

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_soft_jaw"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 158.67 x 63.5 x 19.05 plate: 1:1 fits the face view and its plan on the
# B sheet; the isometric runs at 1:2 to clear the title block.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
FRONT_CENTER = (0.150, 0.150)
TOP_CENTER = (0.150, 0.215)
ISO_CENTER = (0.360, 0.190)
ISO_NOTE_XY = (0.315, 0.245)
NOTES_XY = (0.020, 0.070)


def _sheet_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the face view (1:1, bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - PLATE_LENGTH / 2.0) / 1000.0


def _sheet_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the face view (1:1, bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) / 1000.0


# Every station measures from the bottom-left corner: the three horizontal
# sizes stack under the face view (shortest nearest), the two heights stand
# left of it (the shorter inboard); the thickness rides right of the plan.
FRONT_KEEP = {
    "BoltLeftX": (_sheet_x(BOLT_LEFT_X / 2.0), 0.106),
    "BoltRightX": (_sheet_x(BOLT_RIGHT_X / 2.0), 0.096),
    "PlateLength": (FRONT_CENTER[0], 0.086),
    "BoltY": (0.054, _sheet_y(BOLT_HEIGHT / 2.0)),
    "PlateHeight": (0.033, FRONT_CENTER[1]),
}
TOP_KEEP = {"PlateThick": (0.250, TOP_CENTER[1])}
# The leader leaves the right counterbore from its upper-right quadrant and the
# text stands right of the plate's upper half, above the length's extension
# line and below the plan's thickness, short of the isometric.
_CBORE_R = CBORE_DIA / 2.0
HOLE_CALLOUT_EDGE_XY = (
    _sheet_x(BOLT_RIGHT_X + 0.6 * _CBORE_R),
    _sheet_y(BOLT_HEIGHT + 0.8 * _CBORE_R),
)
HOLE_CALLOUT_XY = (0.272, 0.168)
HOLE_CALLOUT_PROCESS = "7/16 DRILL"


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open soft-jaw source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Post Vise Soft Jaw Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post vise soft jaw; 6061 plate; MHA-DT-005-TL-04",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The counterbores show as true circles on the face and are sized by
    # their callout; the plan needs no hidden bores.
    for view in (front, top):
        set_hidden_lines_removed(adapter, view)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="gripping face",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            top,
            keep=TOP_KEEP,
            view_label="plan",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add the center marks to the soft-jaw face view")
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=HOLE_CALLOUT_EDGE_XY,
        callout_xy=HOLE_CALLOUT_XY,
        label="soft-jaw bolt counterbores",
        process=HOLE_CALLOUT_PROCESS,
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Vise Soft Jaw Drawing",
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

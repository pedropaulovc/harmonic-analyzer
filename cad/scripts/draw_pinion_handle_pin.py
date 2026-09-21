r"""Create the curated manufacturing drawing for the pinion-handle pin.

The plain straight pin is shown as an end view and a turned side view.  Both
``PinDia`` and ``PinLen`` are native model dimensions on the Right-plane
revolve, so the side view imports the complete manufacturing definition.  The
assembly note identifies the pin as the match-ream gauge and requires both
installed ends to finish flush.  No fit band, GD&T, roughness symbol, or
invented stock dimension is added.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_handle_pin.py pinion-handle-pin
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_handle_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
    PIN_LEN,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_handle_pin"]
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

SHEET_SCALE = (8.0, 1.0)
VIEW_SCALE = (8, 1)
FRONT_CENTER = (0.100, 0.150)  # end view: the one circle
RIGHT_CENTER = (0.230, 0.150)  # side view: the length and diameter
ISO_CENTER = (0.360, 0.150)

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0
HALF_LEN = PIN_LEN * VIEW_SCALE[0] / 2000.0

# A *Right view lays model +Z to the left.  The pin has no preferred end, so
# the diameter sits above the side view and the overall length below it.
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + HALF_DIA + 0.016),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.016),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-handle-pin source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Handle Retention Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion handle retention pin; straight match-ream gauge; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # A solid pin has no internal feature: hidden lines are removed everywhere.
    # finalize_drawing styles the standard isometric Shaded With Edges at
    # precision quality after all annotations are complete.
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, right_annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin end view")
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="pinion handle pin axis centerline",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.082)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Handle Retention Pin Manufacturing Drawing",
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

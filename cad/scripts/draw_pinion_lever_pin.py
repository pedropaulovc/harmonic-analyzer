r"""Create the curated machinist drawing for the pinion lever retention pin.

A plain 1/16 in drill-rod pin (MHA-135), cut overlength, then trimmed and
peened flush with the lever hub at assembly.  The side view carries the cut length, the projected
end view the stock diameter, and a 4:1 isometric sits clear of the title block.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_lever_pin.py pinion-lever-pin
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
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_lever_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lever_pin"]
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

# The 13 x 1.6 pin reads at arm's length at 8:1: a 104 mm side view.
SHEET_SCALE = (8.0, 1.0)
# Third-angle: the end view projects to the RIGHT of the side view and shares
# its Y station.
FRONT_CENTER = (0.110, 0.175)
RIGHT_CENTER = (0.235, FRONT_CENTER[1])
ISO_CENTER = (0.345, 0.195)

# Printed half-diameter in sheet metres, which the diameter is placed clear of.
HALF_DIA = PIN_DIA * SHEET_SCALE[0] / 2000.0
# Rule 7 (turned parts): both dimensions sit on the side view, the diameter
# above it -- its dimension line left of centre so the axis-centerline pick at
# the view's middle lands on bare face -- and the cut length below.  The end
# view is a bare circle with its center mark (machinist review of 7f7fc1717).
FRONT_KEEP = {
    "PinDia": (FRONT_CENTER[0] - 0.030, FRONT_CENTER[1] + HALF_DIA + 0.016),
    "PinLen": (FRONT_CENTER[0], 0.140),
}
DIMENSION_CALLOUTS = {
    "PinLen": "CUT LENGTH",
    "PinDia": "1/16 DRILL ROD",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lever-pin source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Lever Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion lever retention pin; 1/16 drill rod; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(8, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(8, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="pin side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to pin end view")
    add_view_centerline(
        adapter,
        front,
        face_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + PIN_DIA * SHEET_SCALE[0] / 4000.0),
        label="pinion lever pin axis centerline",
    )

    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.160)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lever Pin Manufacturing Drawing",
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

r"""Create the curated machinist drawing for the connecting-rod clevis pin.

The pin is only 5.5 mm overall, so all three views run at 12:1.  The head-end
view carries the head diameter; the side view carries shank diameter, grip, and
head thickness.
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
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["clevis_pin"]
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

SHEET_SCALE = (12.0, 1.0)
END_CENTER = (0.070, 0.190)
SIDE_CENTER = (0.180, 0.190)
ISO_CENTER = (0.310, 0.190)

END_KEEP = {
    "HeadDia": (END_CENTER[0], END_CENTER[1] + 0.045),
}
SIDE_KEEP = {
    "GripLength": (SIDE_CENTER[0], SIDE_CENTER[1] - 0.045),
    "HeadThickness": (SIDE_CENTER[0] - 0.040, SIDE_CENTER[1] + 0.040),
    "ShankDia": (SIDE_CENTER[0] + 0.050, SIDE_CENTER[1] + 0.015),
}
DIMENSION_CALLOUTS = {
    "GripLength": "GRIP LENGTH",
    "HeadThickness": "HEAD THICKNESS",
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open clevis-pin source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Clevis Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "connecting-rod clevis pin; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=(12, 1))
    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=(12, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(12, 1))
    for view in (side, end, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="head-end"
    )
    side_annotations = curate_view_dimensions(
        adapter, side, keep=SIDE_KEEP, view_label="side"
    )
    set_dimension_callouts(
        adapter,
        [*end_annotations, *side_annotations],
        DIMENSION_CALLOUTS,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.110)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.225)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Clevis Pin Manufacturing Drawing",
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

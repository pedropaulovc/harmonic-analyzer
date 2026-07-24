r"""Create the curated machinist drawing for the pen frame (stirrup yoke).

The SLDPRT remains authoritative.  This recipe supplies only the frame's views,
the outer + window dimensions, and machining notes; every shared sheet/template,
import, curation, and export behavior lives in ``_drawing_common``.

The pen frame is a brass yoke: a flat 22 x 40 rectangular ring, 10 thick, with a
window (4-wide side rails, 5-wide end rails), the platen-side edge trimmed back
0.75, and a #4-40 set-screw tapped up through the bottom rail.  It is small, so
the sheet runs 2:1; the isometric stays 1:1.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_frame.py pen-frame
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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["pen_frame"]
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

SHEET_SCALE = (2.0, 1.0)   # 2:1 whole sheet (small 22 x 40 ring)
VIEW_SCALE = SHEET_SCALE[0] / SHEET_SCALE[1]  # 2.0 sheet-mm per model-mm

# Sheet layout (meters).  The front ring face is the main view; the isometric
# (1:1) sits to its right.  The outer envelope dims frame the view (width above,
# height left) and the window opening dims sit right/below, all keyed off the
# real envelope so they clear the sheet border and the lower-left note block.
FRONT_CENTER = (0.115, 0.165)
ISO_CENTER = (0.325, 0.175)
RIGHT_CENTER = (0.220, 0.165)

FRONT_KEEP = frozenset({"OuterHeightDim", "OuterSpanX"})


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-frame source", await adapter.open_model(str(SOURCE)))
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
            "Front View Note",
            "Right View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
            "Right View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Frame Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen frame; brass stirrup yoke; set-screw rail",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(2, 1))
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.090)
    add_property_linked_note(adapter, "Front View Note", 0.040, 0.036)
    add_property_linked_note(adapter, "Right View Note", 0.184, 0.105)
    add_property_linked_note(adapter, "Isometric View Note", 0.288, 0.096)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Frame Manufacturing Drawing",
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

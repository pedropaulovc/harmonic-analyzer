r"""Create the curated machinist drawing for the pen amplification wire.

The SLDPRT remains authoritative.  This recipe supplies only the wire's
elevation view, its run-length dimension, and the amplification notes; every
shared sheet/template, import, curation, and export behavior lives in
``_drawing_common``.

The wire is a hair-thin Ø0.8 steel run (WIRE 2 of the amplification chain),
modelled as the straight rest-pose length only.  The sheet magnifies to 2:1 so
the run is legible; the isometric matches.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pen_wire.py pen-wire
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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["pen_wire"]
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

SHEET_SCALE = (2.0, 1.0)   # 2:1 whole sheet (hair-thin 62.7 mm wire)

# Sheet layout (meters).  The elevation (front) is the sole ortho view -- the
# vertical wire -- with the run length to its left; the isometric sits mid-right;
# the notes fill the lower-left.
FRONT_CENTER = (0.110, 0.155)
ISO_CENTER = (0.300, 0.170)

# Per-view survivor of the marked-dimension import: the run length only (the
# Ø0.8 diameter is a note -- a 0.8 mm circle is below the view's ink width).
FRONT_KEEP = {
    "Depth": (0.078, 0.155),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pen-wire source", await adapter.open_model(str(SOURCE)))
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
            "Elevation View Note",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Elevation View Note",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        category=SPEC.category,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pen Wire Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen wire; amplification wire 2; straight steel run",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.086)
    add_property_linked_note(adapter, "Elevation View Note", 0.040, 0.036)
    add_property_linked_note(adapter, "Isometric View Note", 0.270, 0.100)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Wire Manufacturing Drawing",
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

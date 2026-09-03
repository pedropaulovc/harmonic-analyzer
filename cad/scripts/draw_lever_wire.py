r"""Create the curated machinist drawing for the lever wire (WIRE 1).

The lever wire is a Ø0.8 drawn-steel cylinder ~353 long -- a hair-thin
silhouette with no flat face, no pickable end and no selectable silhouette edge,
so the print is note-based: nothing is a marked dimension, and the diameter +
straight rest-run length ride the notes (the build stamps the computed length).
That chord is not a developed cut length: the source model does not define the
formed hook or hub wrap, so the note has the maker form them at assembly.
The print is plain (cad/docs/drawing-simplicity-policy.md): no datum, frame,
roughness or basic dimension.
The wire axis is local +Y, so the FRONT view is the straight run reduced to fit
(1:5) and the isometric confirms it is a plain straight rod.

Run with SolidWorks open::

    uv run python cad\scripts\draw_lever_wire.py lever-wire
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
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["lever_wire"]
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

SHEET_SCALE = (1.0, 1.0)
WIRE_SCALE = (1, 5)  # ~353 long reduced to ~71 mm on the sheet
FRONT_CENTER = (0.135, 0.150)
ISO_CENTER = (0.320, 0.160)

# Note-based: the wire carries no marked model dimension, so every view keeps
# nothing (the front view is curated with an empty keep to delete any stray
# auto-import; the offline test asserts union(marks) == union(keeps) == {}).
FRONT_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-wire source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Front View Note",
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
            0: "Lever Wire (WIRE 1) Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever wire; drawn steel wire; amplification chain",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=WIRE_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=WIRE_SCALE)
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines ON in the orthographic view (policy rule 7).
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)
    add_property_linked_note(adapter, "Front View Note", 0.100, 0.100)
    add_property_linked_note(adapter, "Isometric View Note", 0.300, 0.100)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Wire (WIRE 1) Manufacturing Drawing",
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

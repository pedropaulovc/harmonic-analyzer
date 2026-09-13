"""Create the purchased-reference sheet for the installed 1330K524 spring.

The supplier-native part stays in its vendor frame.  Its +X spring axis is
shown horizontally in the Front view, with the +Z double-loop axes normal to
the sheet.  The part is ordered by SKU; the view is reference geometry and
carries no fabrication dimensions.

Run with SolidWorks open::

    uv run python cad\\scripts\\draw_counter_spring.py counter-spring
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


SPEC = DRAWINGS_BY_NAME["counter_spring"]
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

SHEET_SCALE = (1.0, 2.0)
FRONT_CENTER = (0.110, 0.165)
ISO_CENTER = (0.110, 0.090)

FRONT_KEEP: dict[str, tuple[float, float]] = {}
RIGHT_KEEP: dict[str, tuple[float, float]] = {}
TOP_KEEP: dict[str, tuple[float, float]] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open counter-spring source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Stock Name",
            "Supplier",
            "Supplier SKUs",
            "Manufacturing Notes",
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
            0: "Purchased Counter Spring Reference Sheet",
            1: "McMaster-Carr 1330K524; order by supplier SKU",
            2: "Harmonic Analyzer Project",
            3: "counter spring; 1330K524; purchased reference part",
            4: "Vendor-frame Front and Isometric views; no fabrication dimensions",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 2))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 4))
    set_hidden_lines_removed(adapter, iso)
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")

    add_property_linked_note(adapter, "Manufacturing Notes", 0.275, 0.245)
    add_property_linked_note(adapter, "Isometric View Note", 0.065, 0.050)
    set_hidden_lines_visible(adapter, front)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Purchased Counter Spring Reference Sheet",
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

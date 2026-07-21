r"""Create the curated assembly drawing for the magnifier subassembly.

Front / right / isometric views of ``cad/out/sldasm/magnifier.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_magnifier_assembly.py`` stamps on the assembly.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons,
    finalize_drawing,
    insert_bom_table,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["magnifier_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

# The magnifier spans the wheel-bar from the west column (machine x ~-197) out
# past the wheel (~+192) -- a ~390 mm width -- and ~230 mm tall around the
# wheel-bar height (y ~575). 1:4 shrinks the width to a ~98 mm on-sheet view
# (pen's size), so three views + the BOM + the 13-balloon cloud clear the
# borders and the title block; refined against the render.
SHEET_SCALE = (1.0, 4.0)
VIEW_SCALE = (1, 4)

# One BOM row per UNIQUE top-level component of build_magnifier_assembly.py.
# The two column-clamp arcs are separate parts; the clamp-screw is a native
# pattern (QTY 2); the rest are placed once. Descriptions fill the template's
# DESCRIPTION column.
BOM_COMPONENTS = {
    "wheel-bar": "MAGNIFYING-WHEEL SUPPORT BAR",
    "column-clamp-front": "WHEEL-BAR COLUMN CLAMP, FRONT",
    "column-clamp-back": "WHEEL-BAR COLUMN CLAMP, BACK",
    "clamp-screw": "COLUMN-CLAMP SCREW",
    "magnifying-lever": "MAGNIFYING LEVER",
    "magnifying-bracket": "LEVER-ROD BRACKET",
    "magnifying-clamp": "MAGNIFICATION-SET CLAMP",
    "thumb-screw": "CLAMP THUMB SCREW",
    "magnifying-vertical-rod": "MAGNIFICATION VERTICAL ROD",
    "output-fixture": "WIRE-1 OUTPUT FIXTURE",
    "wheel-axle": "MAGNIFYING-WHEEL AXLE",
    "magnifying-wheel": "MAGNIFYING WHEEL",
    "lever-wire": "AMPLIFICATION WIRE 1",
}

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. SEAT MAGNIFYING LEVER ON THE SUMMING-LEVER KNIFE EDGE.",
        "2. ROUTE LEVER WIRE FROM OUTPUT FIXTURE TO WHEEL HUB GROOVE.",
        "3. VERIFY LEVER ROCKS AND MAGNIFYING WHEEL TURNS FREELY.",
    )
)

# Pen's proven three-view + BOM layout, valid at the pen-sized 1:4 views.
FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.225, 0.140)
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open magnifier assembly source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    drawing_model, _sheet = new_project_drawing(adapter, scale=SHEET_SCALE)
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifier Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifier; lever, wheel, amplification wire 1; parts list",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE
    )
    right = place_view(
        adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE
    )
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    insert_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        expected_components=tuple(BOM_COMPONENTS),
        descriptions=BOM_COMPONENTS,
        label="magnifier assembly",
    )
    # Balloon the ISOMETRIC view: the pictorial keeps every component visible,
    # while the orthographic views stack the clamped lever chain under HLR.
    add_auto_balloons(
        adapter, iso, expected=len(BOM_COMPONENTS),
        label="magnifier assembly balloons",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.070) is None:
        raise RuntimeError("failed to add magnifier assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifier Assembly Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

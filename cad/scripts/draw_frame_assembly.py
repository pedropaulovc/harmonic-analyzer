r"""Create the curated assembly drawing for the frame subassembly.

Front / right / isometric views of ``cad/out/sldasm/frame.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_frame_assembly.py`` stamps on the assembly.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _assembly_drawing_bom import (
    configured_part_numbers,
    insert_identified_bom_table,
)
from _common import _early_bound, run_build
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons,
    create_blank_drawing_sheets,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["frame_assembly"]
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

# The frame is the whole structural tower: cast base at machine y ~0-51, four
# smooth columns rising to the top-frame ring at y ~1000-1041 -- a ~1040 mm
# span, ~460 wide x ~280 deep. The live 1:5 projections were 219-241 mm tall,
# leaving no truthful single-sheet arrangement clear of the ASME-B zones and
# title block. At 1:6 the two orthographic views remain about 183 mm tall and
# readable on the general sheet; the large pictorial, parts list and balloons
# get their own sheet.
SHEET_SCALE = (1.0, 6.0)
VIEW_SCALE = (1, 6)
SHEET_NAMES = ("GENERAL ASSEMBLY", "PARTS LIST AND ITEM IDENTIFICATION")

# One BOM row per UNIQUE top-level component of build_frame_assembly.py. The
# four corner columns (tube-frame) and four hold-down lag-screws are native
# component patterns, so each collapses to one QTY-4 BOM row; the base, support,
# ring and nameplate are placed once. Descriptions fill the template's
# DESCRIPTION column.
BOM_COMPONENTS = {
    "harmonic-base": "TWO-PLATE CAST BASE",
    "tube-frame": "CORNER COLUMN",
    "rocker-arm-support": "ROCKER-PIVOT SUPPORT",
    "lag-screw": "SUPPORT HOLD-DOWN LAG SCREW",
    "top-frame": "TOP-FRAME RING",
    "nameplate": "MAKER'S NAMEPLATE",
}
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. INSTALL FOUR LAG SCREWS FROM THE BASE UNDERSIDE",
        "   INTO THE SUPPORT.",
        "2. SEAT TOP-FRAME RING ON ALL FOUR",
        "   COLUMNS AS SHOWN.",
        "3. VERIFY FRAME IS SQUARE BEFORE FINAL",
        "   TIGHTENING.",
    )
)

GENERAL_FRONT_CENTER = (0.065, 0.155)
GENERAL_RIGHT_CENTER = (0.150, 0.155)
ID_ISO_CENTER = (0.115, 0.145)
# Top-left BOM anchor, bounded above by the sheet ZONE band (0.2667) and kept
# left of the title-block keep-out; refined against the first render.
BOM_ANCHOR = (0.250, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    drawing_model, _sheet = new_project_drawing(
        adapter, category=SPEC.category, scale=SHEET_SCALE
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="frame drawing")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Frame Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "structural frame; base, columns, top ring; parts list",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate frame general assembly sheet")
    general_front = place_view(
        adapter, str(SOURCE), "*Front", *GENERAL_FRONT_CENTER, scale=VIEW_SCALE
    )
    read_required_view_properties(
        adapter,
        general_front,
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
    general_right = place_view(
        adapter, str(SOURCE), "*Right", *GENERAL_RIGHT_CENTER, scale=VIEW_SCALE
    )
    for view in (general_front, general_right):
        set_hidden_lines_removed(adapter, view)
    if add_note(adapter, "SHEET 1 OF 2 — GENERAL ASSEMBLY", 0.018, 0.255) is None:
        raise RuntimeError("failed to add frame general assembly heading")
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.045) is None:
        raise RuntimeError("failed to add frame assembly notes")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate frame parts-list sheet")
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ID_ISO_CENTER, scale=VIEW_SCALE
    )
    set_hidden_lines_removed(adapter, iso)
    insert_identified_bom_table(
        adapter,
        iso,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        label="frame assembly",
    )
    # Balloon the ISOMETRIC view: the pictorial keeps every component visible,
    # while the tall orthographic views stack the base/columns/ring vertically.
    add_auto_balloons(
        adapter, iso, expected=len(BOM_COMPONENTS),
        label="frame assembly balloons",
    )
    if add_note(adapter, "SHEET 2 OF 2\nITEM IDENTIFICATION", 0.018, 0.255) is None:
        raise RuntimeError("failed to add frame identification heading")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Frame Assembly Drawing",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

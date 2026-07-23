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
from _assembly_drawing_bom import (
    configured_part_numbers,
    insert_identified_bom_table,
)
from _common import _early_bound, run_build
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons_across_views,
    create_blank_drawing_sheets,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
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
SHEET_NAMES = ("GENERAL ASSEMBLY", "PARTS LIST AND ITEM IDENTIFICATION")

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
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

# TODO(https://github.com/pedropaulovc/harmonic-analyzer/issues/374):
# Replace these release holds after the wire terminations, grooved hub, and
# installable wheel retention are modeled and released on the part drawings.
ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. SEAT MAGNIFYING LEVER ON THE SUMMING-LEVER KNIFE EDGE.",
        "2. RELEASE HOLD - LEVER-WIRE TERMINATIONS AND DEVELOPED LENGTH NOT DEFINED.",
        "3. RELEASE HOLD - WHEEL HUB/RIM GROOVES AND RETENTION NOT DEFINED.",
        "4. VERIFY LEVER ROCKS AND MAGNIFYING WHEEL TURNS FREELY.",
    )
)

# The general sheet retains the proven three-view arrangement. The item sheet
# moves the pictorial and the one orthographic needed to expose the concealed
# clamp screw into the left field, leaving the full-height BOM alone at right.
GENERAL_FRONT_CENTER = (0.070, 0.150)
GENERAL_RIGHT_CENTER = (0.150, 0.150)
GENERAL_ISO_CENTER = (0.225, 0.140)
ID_ISO_CENTER = (0.085, 0.140)
ID_FRONT_CENTER = (0.190, 0.140)
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    drawing_model, _sheet = new_project_drawing(
        adapter, category=SPEC.category, scale=SHEET_SCALE
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="magnifier drawing")
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

    ddoc = _early_bound(drawing_model, "IDrawingDoc")
    if not ddoc.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate magnifier general assembly sheet")
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
    general_iso = place_view(
        adapter, str(SOURCE), "*Isometric", *GENERAL_ISO_CENTER, scale=VIEW_SCALE
    )
    for view in (general_front, general_right, general_iso):
        set_hidden_lines_removed(adapter, view)
    if add_note(adapter, "SHEET 1 OF 2 — GENERAL ASSEMBLY", 0.018, 0.255) is None:
        raise RuntimeError("failed to add magnifier general assembly heading")
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.040) is None:
        raise RuntimeError("failed to add magnifier assembly notes")

    if not ddoc.ActivateSheet(SHEET_NAMES[1]):
        raise RuntimeError("failed to activate magnifier parts-list sheet")
    iso = place_view(
        adapter, str(SOURCE), "*Isometric", *ID_ISO_CENTER, scale=VIEW_SCALE
    )
    front = place_view(
        adapter, str(SOURCE), "*Front", *ID_FRONT_CENTER, scale=VIEW_SCALE
    )
    for view in (iso, front):
        set_hidden_lines_removed(adapter, view)
    insert_identified_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        label="magnifier assembly",
    )
    # The pictorial exposes almost the whole mechanism, but the live HLR view
    # can conceal one of the two column-clamp halves. Complete and validate the
    # BOM identity set across the orthographic views instead of weakening the
    # required 13-item coverage.
    add_auto_balloons_across_views(
        adapter, (iso, front), expected=len(BOM_COMPONENTS),
        label="magnifier assembly balloons",
    )
    if add_note(adapter, "SHEET 2 OF 2\nITEM IDENTIFICATION", 0.018, 0.255) is None:
        raise RuntimeError("failed to add magnifier identification heading")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifier Assembly Drawing",
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

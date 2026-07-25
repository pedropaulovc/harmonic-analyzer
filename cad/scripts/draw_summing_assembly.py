r"""Create the curated assembly drawing for the summing subassembly.

Front / right / isometric views of ``cad/out/sldasm/summing.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_summing_assembly.py`` stamps on the assembly
(Number, Revision, component-drawing material/finish, and the TOL_* cells
``finalize_drawing`` requires).
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
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_auto_balloons,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["summing_assembly"]
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

# The summing head is tall: the knife-mount / lever / crossbar cluster sits at
# machine y ~990-1050, and the counter-spring chain (boss-hook -> spring ->
# gooseneck) hangs from the east column up to ~1225, with the gooseneck leg
# reaching down toward the top frame -- a ~470 mm span. 1:5 shrinks that to a
# ~94 mm on-sheet view (pen's size), so three views + the BOM + the balloon
# cloud all clear the borders and the title block (1:3 overflowed the balloons
# past the bottom border and across the right view).
SHEET_SCALE = (1.0, 5.0)
VIEW_SCALE = (1, 5)

# One BOM row per UNIQUE top-level component of build_summing_assembly.py. The
# two knife-mount bearing supports collapse to one row (QTY 2) under the
# standard BOM's IgnoreMultiple; the other six are placed once. Descriptions
# fill the template's DESCRIPTION column (the parts carry no Description custom
# property, and a blank column reads as an unreleased sheet).
BOM_COMPONENTS = {
    "knife-mount": "KNIFE-EDGE BEARING SUPPORT",
    "summing-lever": "SUMMING LEVER",
    "boss-hook": "COUNTER-SPRING LEVER HOOK",
    "counter-spring": "COUNTER-BALANCE SPRING",
    "gooseneck": "COUNTER-SPRING SUPPORT POST",
    "gooseneck-screw": "GOOSENECK PINCH SCREW",
}
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

# TODO(https://github.com/pedropaulovc/harmonic-analyzer/issues/373):
# Replace these release holds after the knife seats and crossbar fasteners are
# modeled, added to the BOM, and released on the affected part drawings.
ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. POSITION BOTH KNIFE MOUNTS ABOUT THE SUMMING-LEVER TRUNNIONS.",
        "2. HOOK COUNTER-SPRING BETWEEN BOSS HOOK AND GOOSENECK.",
        "3. VERIFY LEVER ROCKS FREELY AFTER ASSEMBLY.",
        "4. RELEASE HOLD - HARDENED KNIFE SEATS ARE NOT DEFINED.",
        "5. RELEASE HOLD - MOUNT-TO-CROSSBAR FASTENERS ARE NOT DEFINED.",
    )
)

# Three views left-shifted from pen's centers to open the right-view/iso gap:
# the iso balloons spread ~0.05 left of the iso outline, so the right view is
# pulled left to 0.130 to clear them (at pen's 0.150 they overlapped by 2-5 mm),
# while the iso stays at 0.225 -- right balloons clear of the title-block
# keep-out (x >= 0.264) and above the bottom border.
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)
# Top-left BOM anchor, top-right of the sheet above the title block, bounded by
# the sheet ZONE band (0.2667); refined against the render.
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open summing assembly source", await adapter.open_model(str(SOURCE)))
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
            0: "Summing Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "summing head; knife-edge lever; counter-spring; parts list",
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

    insert_identified_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        label="summing assembly",
    )
    # Balloon the ISOMETRIC view: the pictorial keeps every component visible,
    # while the orthographic projections stack the counter-spring chain over the
    # lever under hidden-lines-removed.
    add_auto_balloons(
        adapter, iso, expected=len(BOM_COMPONENTS),
        label="summing assembly balloons",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.070) is None:
        raise RuntimeError("failed to add summing assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Summing Assembly Drawing",
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

r"""Create the curated assembly drawing for the complete machine (top level).

Front / right / isometric views of ``cad/out/sldasm/harmonic-analyzer.SLDASM``
plus a TOP-LEVEL parts BOM (the seven subassemblies + the loose measuring
stick) and item-number balloons on the isometric, on the shared ASME B
template. Top-level-only BOM is the shipped pen precedent: the subassemblies
each carry their own assembly drawing (MHA-A0x), so the machine sheet lists
them as single line items rather than exploding every part.
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


SPEC = DRAWINGS_BY_NAME["harmonic_analyzer_assembly"]
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

# The whole machine: cast base at machine y ~0 up through the top-frame ring
# and the summing head / counter-spring chain to ~1400 mm, ~460 wide x ~280
# deep. 1:8 keeps the tall front + right + iso views and the 8-row BOM on
# ASME B; refined against the first render.
SHEET_SCALE = (1.0, 8.0)
VIEW_SCALE = (1, 8)

# One BOM row per top-level component. TOP-LEVEL-ONLY: the seven subassemblies
# (each inserted whole and fixed) plus the loose measuring stick. The BOM PART
# NUMBER column shows each component's document stem; descriptions fill the
# DESCRIPTION column.
BOM_COMPONENTS = {
    "frame": "STRUCTURAL FRAME SUBASSEMBLY",
    "drive-train": "DRIVE-TRAIN SUBASSEMBLY",
    "channel": "CHANNEL / SPRING-BANK SUBASSEMBLY",
    "summing": "SUMMING-HEAD SUBASSEMBLY",
    "magnifier": "MAGNIFIER SUBASSEMBLY",
    "pen": "PEN / OUTPUT SUBASSEMBLY",
    "paper-drive": "PAPER-DRIVE SUBASSEMBLY",
    "measuring-stick": "LOOSE MEASURING STICK",
}
BOM_PART_NUMBERS = {
    "frame": "MHA-A04",
    "drive-train": "MHA-A03",
    "channel": "MHA-A02",
    "summing": "MHA-A07",
    "magnifier": "MHA-A05",
    "pen": "MHA-A01",
    "paper-drive": "MHA-A06",
    **configured_part_numbers(("measuring-stick",)),
}

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. BUILD SUBASSEMBLIES PER MHA-A01 THROUGH MHA-A07.",
        "2. INSTALL ALL SUBASSEMBLIES ON THE COMMON MACHINE DATUMS AS SHOWN.",
        "3. VERIFY ALL SAVED OPERATIONAL DEGREES OF FREEDOM MOVE WITHOUT BINDING.",
    )
)

# Three views left-shifted so the iso's balloon cloud clears the right view and
# the title-block keep-out (the summing slice's proven arrangement).
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open harmonic-analyzer assembly source", await adapter.open_model(str(SOURCE)))
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
            0: "Harmonic Analyzer Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "complete machine; seven subassemblies; parts list",
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
        label="harmonic-analyzer assembly",
    )
    add_auto_balloons(
        adapter, iso, expected=len(BOM_COMPONENTS),
        label="harmonic-analyzer assembly balloons",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.070) is None:
        raise RuntimeError("failed to add harmonic-analyzer assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Harmonic Analyzer Assembly Drawing",
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

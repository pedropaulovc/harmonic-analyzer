r"""Create the curated assembly drawing for the channel subassembly.

Front / right / isometric views of ``cad/out/sldasm/channel.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_channel_assembly.py`` stamps on the assembly
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
    add_auto_balloons_across_views,
    finalize_drawing,
    new_project_drawing,
    position_bom_balloon,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view


SPEC = DRAWINGS_BY_NAME["channel_assembly"]
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

# The channel bank is the machine's tallest subassembly: the rocker bank sits at
# machine y ~254 and the whole motion chain runs UP the 812.8 mm amplitude bars
# to the lever fulcrum at y ~1066, a ~840 mm span in Y that governs BOTH ortho
# views (Front = XY, Right = ZY). The pitch-station Z spread (~220 mm, ball
# mounts at |z| ~111) and the X spread (ring centre -55 to fulcrum 200, ~255 mm)
# are both far smaller, so Y drives the on-sheet size. 1:7 shrinks the 840 mm
# tower to a ~120 mm on-sheet view -- in the 100-130 mm target band -- so three
# views + the BOM + the balloon cloud all clear the borders and the title block.
# (summing's 1:5 fits its shorter ~470 mm head; the taller channel tower needs
# the extra reduction. 1:4/1:5 would render ~170-210 mm and overflow the sheet.)
SHEET_SCALE = (1.0, 7.0)
VIEW_SCALE = (1, 7)

# One BOM row per UNIQUE top-level component of build_channel_assembly.py. Most
# components repeat down the 20-channel spine (rocker/rod/bar/lever/spring/hook
# x20, the two bushings x19, ball mount x4); the standard BOM collapses each
# family to one row (QTY N) under IgnoreMultiple, so the UNIQUE placed set -- not
# the raw call count -- fills the list. Descriptions fill the template's
# DESCRIPTION column (the parts carry no Description custom property, and a blank
# column reads as an unreleased sheet).
BOM_COMPONENTS = {
    "pivot-shaft": "ROCKER PIVOT SHAFT",
    "fulcrum-shaft": "LEVER FULCRUM SHAFT",
    "pivot-ball-mount": "BALL PIVOT MOUNT",
    "pivot-bushing": "ROCKER SHAFT SPACER BUSHING",
    "lever-bushing": "FULCRUM SHAFT SPACER BUSHING",
    "rocker-arm": "ROCKER SEESAW ARM",
    "connecting-rod": "CAM CONNECTING ROD",
    "amplitude-bar": "AMPLITUDE BAR",
    "channel-lever": "CHANNEL OUTPUT LEVER",
    "channel-spring-installed": "CHANNEL RETURN SPRING",
    "spring-hook": "SPRING-HOOK FASTENER",
}
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. INSTALL 20 CHANNEL CHAINS AT 7.06 PITCH AS SHOWN.",
        "2. SEAT EACH SPRING HOOK IN THE SUMMING-LEVER PLATE AT FINAL ASSEMBLY.",
        "3. VERIFY EACH ROCKER / ROD / BAR / LEVER CHAIN MOVES FREELY.",
    )
)

# Three views on the validated summing layout (left-shifted centers open the
# right-view/iso gap; the iso balloons spread ~0.05 left of the iso outline, so
# the right view is pulled left to 0.130 to clear them, while the iso stays at
# 0.225 -- right balloons clear of the title-block keep-out (x >= 0.264) and
# above the bottom border).
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)
# Top-left BOM anchor, top-right of the sheet above the title block, bounded by
# the sheet ZONE band (0.2667); refined against the render.
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open channel assembly source", await adapter.open_model(str(SOURCE)))
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
            0: "Channel Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "channel motion chain; rocker/rod/bar/lever bank; parts list",
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
        label="channel assembly",
    )
    # No single view exposes all eleven component families in the dense bank.
    # Cover the BOM across the three projections and validate every item number.
    balloons = add_auto_balloons_across_views(
        adapter, (front, right, iso), expected=len(BOM_COMPONENTS),
        label="channel assembly balloons",
    )
    # Item 4 and item 7 attach at nearly the same X in the right view. Keep
    # their balloon centres in that same left-to-right order so their leaders
    # cannot exchange sides on the way to the component.
    position_bom_balloon(
        adapter,
        balloons,
        item_number="4",
        position_xy=(0.150, 0.066),
        label="channel item 4 crossing correction",
    )
    # A rebuilt source assembly can change which generated DetailItem name
    # carries each BOM identity. Item 2 currently auto-lands inside the table;
    # route it by its stable item number into the open field below the table.
    position_bom_balloon(
        adapter,
        balloons,
        item_number="2",
        position_xy=(0.255, 0.105),
        label="channel item 2 table-overlap correction",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.052) is None:
        raise RuntimeError("failed to add channel assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Assembly Drawing",
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

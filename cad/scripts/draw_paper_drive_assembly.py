r"""Create the curated assembly drawing for the paper-drive subassembly.

Front / right / isometric views of ``cad/out/sldasm/paper-drive.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_paper_drive_assembly.py`` stamps on the assembly
(Number, Revision, SEE PARTS LIST material/finish, and the TOL_* cells
``finalize_drawing`` requires).
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


SPEC = DRAWINGS_BY_NAME["paper_drive_assembly"]
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

# The paper-drive is a WIDE, FLAT mechanism: the 452 mm support bar (centred at
# machine x=0, spanning +-226) dominates the front view, while the platen +
# guide rails + transgear cluster stack at machine y ~260-350 and the spare T18
# gear rests low on the base (~y 53) -- a ~452 mm width x ~320 mm height span,
# only ~45 mm deep. 1:4 shrinks the 452 mm width to a ~113 mm on-sheet front
# view (in the 100-130 mm target); the shallow depth keeps the right view ~11 mm
# wide so the front (right edge ~117 mm) and right (centre 130 mm) views clear.
# 1:3 (front ~151 mm) would overrun the right view and the left border.
SHEET_SCALE = (1.0, 4.0)
VIEW_SCALE = (1, 4)

# One BOM row per UNIQUE top-level component of build_paper_drive_assembly.py.
# The clamp-/fillister-/bracket-screw seeds and BOTH roller-chain link stems
# (chain-inner-link, chain-outer-link) are native component patterns, so each
# collapses to one QTY-N BOM row (proven by the frame assembly's column/lag-screw
# pattern rows); transgear-removable is ONE stem placed in three configurations
# (T24 knob wheel, T12 crank wheel, T18 spare) and collapses to one row.
# Descriptions fill the template's DESCRIPTION column (the parts carry no
# Description custom property, and a blank column reads as an unreleased sheet).
BOM_COMPONENTS = {
    "support-bar": "PLATEN SUPPORT BAR",
    "column-clamp-front": "COLUMN CLAMP (FRONT ARC)",
    "column-clamp-back": "COLUMN CLAMP (BACK ARC)",
    "clamp-screw": "COLUMN CLAMP SCREW",
    "platen": "RECORDING PAPER PLATEN",
    "platen-rack": "PLATEN FEED RACK",
    "platen-guide": "PLATEN GUIDE RAIL",
    "guide-lock": "PLATEN GUIDE LOCK PLATE",
    "platen-clip": "PLATEN PAPER EDGE CLIP",
    "platen-paper": "RECORDING PAPER SHEET",
    "fillister-screw": "FILLISTER-HEAD SCREW",
    "transgear-bracket": "TRANSGEAR MOUNT BRACKET",
    "bracket-screw": "TRANSGEAR BRACKET SCREW",
    "transgear-stub": "TRANSGEAR STEPPED STUD",
    "transgear-latch": "TRANSGEAR LATCH ARM",
    "rack-pinion": "120T REDUCER DISC",
    "transgear-feed-pinion": "12T FEED PINION",
    "transgear-knob-shaft": "KNOB SHAFT",
    "transgear-pinion": "12T THIRD GEAR",
    "transgear-removable": "REMOVABLE CHAIN SPROCKET",
    "chain-inner-link": "ROLLER CHAIN INNER LINK",
    "chain-outer-link": "ROLLER CHAIN OUTER LINK",
}

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. HANG PLATEN GUIDE RAILS ON SUPPORT BAR; VERIFY FREE X TRAVEL.",
        "2. LOCK 120T DISC COAXIAL WITH 12T FEED PINION ON THE STUD.",
        "3. ROUTE ALTERNATING 56-LINK CHAIN AROUND T24 AND T12 SPROCKETS.",
        "4. VERIFY CRANK ROTATION FEEDS THE PLATEN WITHOUT BINDING.",
    )
)

# Three views kept on summing's centres: the front view opens on the wide bar,
# the right view pulled to 0.130 to clear the iso balloons (which spread ~0.05
# left of the iso outline), while the iso stays at 0.225 -- right balloons clear
# of the title-block keep-out (x >= 0.264) and above the bottom border.
FRONT_CENTER = (0.060, 0.150)
RIGHT_CENTER = (0.130, 0.150)
ISO_CENTER = (0.225, 0.140)
# Top-left BOM anchor, top-right of the sheet above the title block, bounded by
# the sheet ZONE band (0.2667); refined against the render.
BOM_ANCHOR = (0.248, 0.265)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open paper-drive assembly source", await adapter.open_model(str(SOURCE)))
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
            0: "Paper-Drive Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen time-base; roller chain; transgear train; parts list",
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
        label="paper-drive assembly",
    )
    # Balloon the ISOMETRIC view: the pictorial keeps every component visible,
    # while the orthographic projections stack the transgear cluster and chain
    # over the platen under hidden-lines-removed.
    add_auto_balloons(
        adapter, iso, expected=len(BOM_COMPONENTS),
        label="paper-drive assembly balloons",
    )
    if add_note(adapter, ASSEMBLY_NOTES, 0.018, 0.070) is None:
        raise RuntimeError("failed to add paper-drive assembly notes")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Paper-Drive Assembly Drawing",
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

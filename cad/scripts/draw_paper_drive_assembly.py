r"""Create the curated assembly drawing for the paper-drive subassembly.

Front / right / isometric views of ``cad/out/sldasm/paper-drive.SLDASM`` plus a
top-level parts BOM and auto-inserted item-number balloons, on the same
hand-made ASME B template every part print uses. The title block resolves from
the custom properties ``build_paper_drive_assembly.py`` stamps on the assembly
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
    isolate_drawing_view_components,
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
# only ~45 mm deep. Live drawing bounds include projected component extents
# beyond the nominal support-bar span: at 1:4 the front crossed the left zone
# by 11.8 mm and overlapped the right view by 18.1 mm. 1:5 keeps both main
# orthographic views inside their own fields while remaining readable.
SHEET_SCALE = (1.0, 5.0)
VIEW_SCALE = (1, 5)

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
    "transgear-removable": "CHAIN SPROCKET, T12/T18/T24; 1 EACH",
    "chain-inner-link": "ROLLER CHAIN INNER LINK",
    "chain-outer-link": "ROLLER CHAIN OUTER LINK",
}
BOM_PART_NUMBERS = configured_part_numbers(tuple(BOM_COMPONENTS))

ASSEMBLY_NOTES = "\n".join(
    (
        "ASSEMBLY NOTES",
        "1. HANG PLATEN GUIDE RAILS ON SUPPORT BAR;",
        "   VERIFY FREE X TRAVEL.",
        "2. LOCK 120T DISC AND 12T FEED PINION COAXIAL",
        "   ON THE STUD.",
        "3. ROUTE ALTERNATING 56-LINK CHAIN AROUND",
        "   T24 AND T12 SPROCKETS.",
        "4. VERIFY CRANK ROTATION FEEDS THE PLATEN",
        "   WITHOUT BINDING.",
    )
)

# The 1:5 orthographic fields retain 80 mm between centres; the isometric stays
# in the right field above the title-block keep-out.
FRONT_CENTER = (0.070, 0.145)
RIGHT_CENTER = (0.170, 0.170)
ISO_CENTER = (0.180, 0.080)
ISO_VIEW_SCALE = (1, 7)
BRACKET_DETAIL_CENTER = (0.100, 0.230)
BRACKET_DETAIL_SCALE = (1, 4)
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
        adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_VIEW_SCALE
    )
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)
    bracket_detail = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *BRACKET_DETAIL_CENTER,
        scale=BRACKET_DETAIL_SCALE,
    )
    set_hidden_lines_removed(adapter, bracket_detail)
    isolate_drawing_view_components(
        adapter,
        bracket_detail,
        visible_stems=frozenset(
            {
                "transgear-bracket",
                "bracket-screw",
                "transgear-latch",
            }
        ),
        label="paper-drive transgear detail",
    )

    insert_identified_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        descriptions=BOM_COMPONENTS,
        part_numbers=BOM_PART_NUMBERS,
        configuration_grouping="same-part",
        label="paper-drive assembly",
    )
    # The pictorial exposes most component families, but its transgear cluster
    # still hides eight BOM items. The isolated transgear detail exposes the
    # bracket/screw pair and removes latch item 15 from the right view before
    # its leader can cross item 19 there.
    add_auto_balloons_across_views(
        adapter, (iso, front, bracket_detail, right), expected=len(BOM_COMPONENTS),
        label="paper-drive assembly balloons",
    )
    if add_note(adapter, "TRANSGEAR DETAIL", 0.020, 0.260) is None:
        raise RuntimeError("failed to label paper-drive transgear detail")
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

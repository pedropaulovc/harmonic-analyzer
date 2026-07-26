r"""Create a simple three-view diagram of the channel subassembly.

The sheet intentionally contains only front, right, and isometric views of
``cad/out/sldasm/channel.SLDASM``.  It is an arrangement diagram for a
mechanism that is still changing, not a parts-identification or manufacturing
drawing.

The curated version -- top-level parts BOM plus auto-inserted item-number
balloons -- was removed 2026-07-25 and will be recreated later.  It could not
be kept in the meantime: ``AutoBalloon5`` places item 4 (pivot-bushing) and
item 7 (connecting-rod) in a tight vertical cluster in the right view, and its
ring layout does not preserve their attachment order, so their leaders cross
and the layout audit fails.  An earlier revision pinned those two balloons by
hand for exactly this reason; ``f375557a`` replaced the pins with SolidWorks'
native circular layout (``layout=2``) on the premise that "their order follows
the view ring", which does not hold for this pair -- the ring fills the same
two slots with the items swapped.  ``AutoBalloon5`` is also nondeterministic in
which view it balloons a given BOM item from run to run (measured: item 2
landed in view 3 on one run and view 1 on the next against an identical
``.SLDASM``), so which pairs end up adjacent is luck.  Whatever replaces this
needs a deterministic placement, not a tuned auto-layout.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import check, run_build
from _drawing_common import (
    DrawingOutputs,
    create_blank_drawing_sheets,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


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
# views clear the borders and the title block.
# (summing's 1:5 fits its shorter ~470 mm head; the taller channel tower needs
# the extra reduction. 1:4/1:5 would render ~170-210 mm and overflow the sheet.)
SHEET_SCALE = (1.0, 7.0)
VIEW_SCALE = (1, 7)
SHEET_NAMES = ("THREE-VIEW DIAGRAM",)

# The curated sheet squeezed all three views into the left half so the BOM
# (anchored 0.248) and the iso balloon cloud (~0.05 left of the iso outline) had
# room. With both gone that crowding buys nothing, so the views spread across
# the drawable width. The iso is the widest (~50 mm on sheet) and sits above the
# title block, whose keep-out is x >= 0.261, y <= 0.069; at y 0.150 its lower
# edge lands ~0.094, clearing that corner.
FRONT_CENTER = (0.100, 0.150)
RIGHT_CENTER = (0.200, 0.150)
ISO_CENTER = (0.310, 0.150)


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
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="channel diagram")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Channel Three-View Diagram",
            1: "Harmonic Analyzer arrangement diagram",
            2: "Harmonic Analyzer Project",
            3: "channel motion chain; front; right; isometric",
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

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Channel Three-View Diagram",
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

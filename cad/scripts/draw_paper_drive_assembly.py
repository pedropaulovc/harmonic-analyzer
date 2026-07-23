r"""Create a simple three-view diagram of the paper-drive assembly.

The sheet intentionally contains only front, right, and isometric views of
``cad/out/sldasm/paper-drive.SLDASM``.  It is an arrangement diagram for a
mechanism that is still changing, not a parts-identification or manufacturing
drawing.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import run_build
from _drawing_common import (
    DrawingOutputs,
    create_blank_drawing_sheets,
    finalize_drawing,
    new_project_drawing,
    read_required_view_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import place_view


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

# The paper drive is wide and flat.  At 1:5 its three views fit the ASME B
# drawable area while retaining enough separation to read the mechanism.
SHEET_SCALE = (1.0, 5.0)
VIEW_SCALE = (1, 5)
SHEET_NAMES = ("THREE-VIEW DIAGRAM",)
FRONT_CENTER = (0.080, 0.150)
RIGHT_CENTER = (0.200, 0.150)
ISO_CENTER = (0.320, 0.145)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    drawing_model, _sheet = new_project_drawing(
        adapter, category=SPEC.category, scale=SHEET_SCALE
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="paper-drive diagram")
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Paper-Drive Three-View Diagram",
            1: "Harmonic Analyzer arrangement diagram",
            2: "Harmonic Analyzer Project",
            3: "paper drive; front; right; isometric",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(
        adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE
    )
    read_required_view_properties(
        adapter,
        front,
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
        pdf_title="Paper-Drive Three-View Diagram",
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

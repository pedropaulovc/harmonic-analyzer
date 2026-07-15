r"""Create the curated assembly drawing for the pen subassembly.

The first ASSEMBLY drawing (source_kind="assembly" in the registry): front /
right / isometric views of ``cad/out/sldasm/pen.SLDASM`` plus a top-level
parts BOM and auto-inserted item-number balloons, on the same hand-made ASME B
template every part print uses. The title block resolves from the custom
properties ``build_pen_assembly.py`` stamps on the assembly (Number, Revision,
SEE PARTS LIST material/finish, and the TOL_* cells ``finalize_drawing``
requires).
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
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["pen_assembly"]
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

# The pen sub spans ~44 x 197 x 34 mm (machine x/y/z), so the whole sheet runs
# 1:2 -- the front view is ~99 mm tall and three views + BOM fit ASME B.
SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)

# One BOM row per top-level component of build_pen_assembly.py (each part is
# placed exactly once, so IgnoreMultiple collapses nothing).
BOM_COMPONENTS = (
    "pen-hanger",
    "pen-v-block",
    "pen-rod",
    "pen-marker",
    "pen-wire",
    "pen-frame",
    "pen-set-screw",
    "hanger-screw",
)

FRONT_CENTER = (0.070, 0.150)
RIGHT_CENTER = (0.150, 0.150)
ISO_CENTER = (0.225, 0.150)
BOM_ANCHOR = (0.240, 0.272)  # top-left corner, clear of the views and border


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open pen assembly source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
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
            0: "Pen Assembly Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pen assembly; output transducer; parts list",
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
        expected_components=BOM_COMPONENTS,
        label="pen assembly",
    )
    add_auto_balloons(
        adapter, front, expected=len(BOM_COMPONENTS), label="pen assembly balloons"
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pen Assembly Drawing",
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

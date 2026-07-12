r"""Create the curated machinist drawing for the cast-iron top crossbar."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)
from top_crossbar_spec import (
    BAR_HEIGHT,
    BAR_LENGTH,
    BAR_WIDTH,
    STUD_HOLE_DIA,
    STUD_HOLE_FIT,
    STUD_HOLE_SIZE,
)


SPEC = DRAWINGS_BY_NAME["top_crossbar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (1.0, 1.0)
TOP_CENTER = (0.165, 0.210)
FRONT_CENTER = (0.165, 0.135)
ISO_CENTER = (0.355, 0.200)

TOP_KEEP = {
    "Depth": (TOP_CENTER[0], TOP_CENTER[1] + 0.028),
}
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.034),
    "Height": (FRONT_CENTER[0] - 0.035, FRONT_CENTER[1]),
}

_NOTES = (
    "UNLESS OTHERWISE SPECIFIED:",
    "1. DIMENSIONS ARE IN MILLIMETRES. INTERPRET PER ASME Y14.5.",
    (
        "2. GRAY-IRON CASTING: AS-CAST +/-0.8; MACHINED\n"
        "   +/-0.25; HOLE AXIS LOCATION +/-0.10."
    ),
    "3. REMOVE BURRS AND BREAK SHARP EDGES 0.3 MAX.",
    (
        f"4. CENTRE HOLE: {STUD_HOLE_SIZE} IN {STUD_HOLE_FIT.upper()}-FIT\n"
        f"   CLEARANCE (O{STUD_HOLE_DIA:.3f}) THRU; REAM IF NEEDED.\n"
        f"   AXIS CENTRED ON THE {BAR_WIDTH:.0f} X {BAR_LENGTH:.0f} BAR PLAN."
    ),
    (
        f"5. MACHINE THE {BAR_WIDTH:.0f} X {BAR_HEIGHT:.0f} END SEATS SQUARE TO THE\n"
        "   LONG AXIS WITHIN 0.10; END FACES PARALLEL 0.10."
    ),
    (
        "6. MACHINE HOLE AND END SEATS Ra 3.2. OTHER SURFACES\n"
        "   MAY REMAIN AS-CAST. ALL Ra VALUES IN MICROMETRES."
    ),
    (
        "7. FINISH: MACHINE GREEN ENAMEL. MASK HOLE AND\n"
        "   MACHINED END SEATS."
    ),
    "8. MAY BE MACHINED FROM SOLID CLASS 30 BAR; NO DRAFT MODELLED.",
)


def _manufacturing_notes() -> str:
    return "\n".join(_NOTES)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open top-crossbar source", await adapter.open_model(str(SOURCE)))
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
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Top Crossbar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "top crossbar; cast iron; clearance hole",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (top, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, front)

    curate_view_dimensions(adapter, top, keep=TOP_KEEP, view_label="top")
    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to top-view stud hole")

    add_note(adapter, "\n".join(_NOTES[:4]), 0.014, 0.090)
    add_note(adapter, "\n".join(_NOTES[4:7]), 0.145, 0.088)
    add_note(adapter, "\n".join(_NOTES[7:]), 0.145, 0.055)
    add_note(adapter, "ISOMETRIC VIEW SCALE 1:2", 0.330, 0.155)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Top Crossbar Manufacturing Drawing",
        scale=SHEET_SCALE,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

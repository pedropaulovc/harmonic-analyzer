r"""Create the curated machinist drawing for the lever-bank spacer bushing."""

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
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from lever_bushing_spec import BORE_DIA, LENGTH, OUTER_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["lever_bushing"]
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

SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.080, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + (OUTER_DIA + LENGTH) * SHEET_SCALE[0] / 1000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.315, 0.205)

FRONT_KEEP = {
    "OuterDia": (
        FRONT_CENTER[0] - 0.035,
        FRONT_CENTER[1] + 0.010,
    ),
    "BoreDia": (
        FRONT_CENTER[0] + OUTER_DIA * SHEET_SCALE[0] / 1000.0 + 0.020,
        FRONT_CENTER[1] - 0.010,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.040),
}
DIMENSION_CALLOUTS = {"BoreDia": "THRU (NOTE 5)"}

_NOTES = (
    "UNLESS OTHERWISE SPECIFIED:",
    "1. DIMENSIONS ARE IN MILLIMETRES. INTERPRET PER ASME Y14.5.",
    (
        "2. TOLERANCES: LINEAR +/-0.10; DIAMETERS +/-0.05;\n"
        "   BORE O6.50 +0.03/-0.00."
    ),
    "3. REMOVE BURRS AND BREAK SHARP EDGES 0.15 MAX.",
    (
        "4. TURN OD AND BOTH END FACES IN ONE SETUP WHERE PRACTICAL.\n"
        "   END FACES PARALLEL WITHIN 0.03; TOTAL LENGTH +/-0.03."
    ),
    (
        "5. DRILL UNDERSIZE AND REAM O6.50 THRU; Ra 1.6.\n"
        "   FREE RUNNING FIT ON O6.35 FULCRUM SHAFT."
    ),
    (
        "6. CONCENTRICITY OF OD TO BORE: 0.05 TIR.\n"
        "   OD AND END FACES Ra 3.2. ALL Ra VALUES IN MICROMETRES."
    ),
    (
        "7. MAKE 19 IDENTICAL PIECES.\n"
        "   DEBURR BORE EDGES;\n"
        "   AVOID BELL-MOUTH."
    ),
)


def _manufacturing_notes() -> str:
    return "\n".join(_NOTES)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-bushing source", await adapter.open_model(str(SOURCE)))
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
            0: "Lever Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    add_note(adapter, "\n".join(_NOTES[:4]), 0.014, 0.112)
    add_note(adapter, "\n".join(_NOTES[4:]), 0.170, 0.105)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Bushing Manufacturing Drawing",
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

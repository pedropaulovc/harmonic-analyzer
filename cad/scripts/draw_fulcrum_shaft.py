r"""Create the curated machinist drawing for the lever fulcrum shaft."""

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
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from fulcrum_shaft_spec import SHAFT_DIA, SHAFT_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_shaft"]
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
END_VIEW_SCALE = 2.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)

FRONT_KEEP = {
    "ShaftDia": (
        FRONT_CENTER[0] - SHAFT_DIA * END_VIEW_SCALE / 1000.0 - 0.025,
        FRONT_CENTER[1] + 0.008,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {"ShaftDia": "+0.00/-0.02"}

_NOTES = (
    "UNLESS OTHERWISE SPECIFIED:",
    "1. DIMENSIONS ARE IN MILLIMETRES. INTERPRET PER ASME Y14.5.",
    (
        "2. LENGTH +/-0.25. SHAFT DIAMETER TOLERANCE\n"
        "   IS SHOWN DIRECTLY ON THE END VIEW."
    ),
    (
        "3. REMOVE BURRS AND BREAK END EDGES 0.15 MAX.\n"
        "   CENTER-DRILL MARKS PERMITTED, 1.0 DEEP MAX."
    ),
    (
        "4. TURN OR CENTRELESS-GRIND THE FULL BEARING LENGTH.\n"
        "   NO LOCAL FLATS, STEPS, OR TOOL ROLLOVER."
    ),
    (
        "5. CYLINDRICITY 0.03 OVER FULL LENGTH. BOTH END\n"
        "   FACES SQUARE TO AXIS WITHIN 0.05."
    ),
    (
        "6. BEARING SURFACE Ra 1.6; END FACES Ra 3.2.\n"
        "   ALL Ra VALUES IN MICROMETRES."
    ),
    (
        "7. MATING O6.50 BUSHINGS GIVE 0.15-0.20\n"
        "   DIAMETRAL CLEARANCE. LIGHTLY OIL."
    ),
)


def _manufacturing_notes() -> str:
    return "\n".join(_NOTES)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-shaft source", await adapter.open_model(str(SOURCE)))
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
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    curate_view_dimensions(adapter, right, keep=RIGHT_KEEP, view_label="right")
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    add_note(adapter, "\n".join(_NOTES[:4]), 0.014, 0.108)
    add_note(adapter, "\n".join(_NOTES[4:]), 0.175, 0.105)
    add_note(adapter, "END VIEW SCALE 2:1", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
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

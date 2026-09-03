r"""Create the curated manufacturing drawing for the crank-drive gear (64T).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). The helical
crossed-axis accommodation is stated in the GEAR DATA note (helix angle and
hand, thinned tooth, over-pins acceptance, mating pinion). SECTION A-A (cut
face only, through the axis) replaces the projected side view -- 64 helical
teeth projected edge-on were a black band -- and carries the 8.00 face width.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
gear is not on the GD&T allowlist and this one is keyed to the cone shaft, so
it carries no datums, no feature-control frames and no roughness symbols --
the title block's general tolerances govern everything but the reamed bore,
whose fit band rides the model dimension.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    create_section_view,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import show_only_cut_face
from crank_drive_gear_spec import FACE_WIDTH, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_drive_gear"]
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
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.225, 0.175)
ISO_CENTER = (0.375, 0.205)
GEAR_DATA_POS = (0.025, 0.262)

# SECTION A-A: vertical cut through the axis, cut face only, where the side
# view used to sit; a plain adjacent note states the face width without
# relying on an imported edge dimension.
SECTION_HALF_LINE = OUTSIDE_DIA / 2000.0 + 0.008
SECTION_LINE = (
    (FRONT_CENTER[0], FRONT_CENTER[1] - SECTION_HALF_LINE),
    (FRONT_CENTER[0], FRONT_CENTER[1] + SECTION_HALF_LINE),
)
SECTION_CENTER = (0.300, 0.175)
SECTION_NOTE = f"SECTION A-A\nFACE WIDTH {FACE_WIDTH:.2f}"
SECTION_NOTE_XY = (
    SECTION_CENTER[0],
    SECTION_CENTER[1] + OUTSIDE_DIA / 2000.0 + 0.009,
)

FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] - 0.030),
}
# A nominal 3/8 in reamer is inside the 9.525 +0.05/0.00 model band
# (build_crank_drive_gear); the callout names the process and three decimals
# say "hold it".
DIMENSION_CALLOUTS = {"BoreDia": "REAM THRU"}
DIMENSION_PRECISION = {"BoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-drive-gear source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Gear Data",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank-Drive Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank-drive gear; steel; 64T helical",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in the orthographic view (policy rule 7).
    set_hidden_lines_visible(adapter, front)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to gear bore")

    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="gear blank",
    )
    show_only_cut_face(adapter, section, label="gear blank")
    if add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY) is None:
        raise RuntimeError("failed to add crank-drive section geometry note")

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS, char_height=0.0025)
    add_property_linked_note(
        adapter, "Manufacturing Notes", 0.018, 0.102, char_height=0.0025
    )
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank-Drive Gear Manufacturing Drawing",
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

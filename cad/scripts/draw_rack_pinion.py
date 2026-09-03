r"""Create the curated manufacturing drawing for the rack-pinion reduction disc.

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). Drawn 1:1;
the 120T disc is large and thin. SECTION A-A (cut face only, through the axis)
replaces the projected side view -- 120 teeth projected edge-on were a black
band hiding the bore -- and carries the 3.00 face width.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
gear is not on the GD&T allowlist, so it carries no datums and no
feature-control frames. The one roughness symbol is on the bore, which RUNS
free on the transgear stud; its fit band rides the model dimension.
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
    add_surface_finish,
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
from _gear_drawing_entities import show_only_cut_face, visible_circle_edge
from _surface_finish import surface_finish_by_key
from rack_pinion_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA, SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["rack_pinion"]
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
FRONT_CENTER = (0.220, 0.175)
ISO_CENTER = (0.383, 0.210)  # 0.388 clipped the zone border right by 1.4 mm

# SECTION A-A: vertical cut through the axis, cut face only, where the side
# view used to sit.  The explicit scale and "axial disc profile" wording make
# clear that the two hatched lands are the bore-interrupted edge profile, not
# an incomplete tooth-form detail.
SECTION_HALF_LINE = OUTSIDE_DIA / 2000.0 + 0.008
SECTION_LINE = (
    (FRONT_CENTER[0], FRONT_CENTER[1] - SECTION_HALF_LINE),
    (FRONT_CENTER[0], FRONT_CENTER[1] + SECTION_HALF_LINE),
)
SECTION_CENTER = (0.320, 0.175)
SECTION_NOTE = (
    f"SECTION A-A SCALE {VIEW_SCALE[0]}:{VIEW_SCALE[1]}\n"
    f"AXIAL DISC PROFILE - FACE WIDTH {FACE_WIDTH:.2f}"
)
SECTION_NOTE_XY = (
    SECTION_CENTER[0] - 0.045,
    SECTION_CENTER[1] + OUTSIDE_DIA / 2000.0 + 0.009,
)

# The bore callout sits upper-left and the roughness symbol lower-left, so
# each leader lands radially on its own side of the bore and neither runs
# through the centre mark (machinist review 2026-09-02).
FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.062, FRONT_CENTER[1] + 0.045),
}
BORE_FINISH_SYMBOL = (FRONT_CENTER[0] - 0.036, FRONT_CENTER[1] - 0.066)
# Reamed slip fit on the stud's Ø5 seat; the band is on the model dimension
# (build_rack_pinion), so the callout only names the process and three
# decimals say "hold it".
DIMENSION_CALLOUTS = {"BoreDia": "REAM THRU"}
DIMENSION_PRECISION = {"BoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open rack-pinion source", await adapter.open_model(str(SOURCE)))
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
            0: "Rack-Pinion Disc Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "rack pinion; reduction disc; brass; 120T",
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
        raise RuntimeError("failed to add ASME center mark to disc bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_surface_finish(
        adapter,
        front,
        symbol_xy=BORE_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="rack pinion bore finish",
        entity=bore_edge,
    )

    section = create_section_view(
        adapter,
        front,
        line_start=SECTION_LINE[0],
        line_end=SECTION_LINE[1],
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="disc blank",
    )
    show_only_cut_face(adapter, section, label="disc blank")
    if add_note(adapter, SECTION_NOTE, *SECTION_NOTE_XY) is None:
        raise RuntimeError("failed to add rack-pinion section geometry note")

    add_property_linked_note(adapter, "Gear Data", 0.018, 0.262)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rack-Pinion Disc Manufacturing Drawing",
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

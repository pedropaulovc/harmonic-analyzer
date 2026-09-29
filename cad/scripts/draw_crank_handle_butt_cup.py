r"""Create the curated machinist drawing for MHA-153, the crank handle butt cup.

A flanged steel cup (user ruling 2026-09-29, ch11 p.14/p.15).  The end view
carries only its centre mark and the cutting plane; the longitudinal section
A-A is the cup's length view (policy rule 7) and takes every dimension, so
the pocket and the floor hole read on cut edges rather than hidden lines (the
MHA-153 machinist review).  The body diameter is the one band; the pocket is
bored to suit the MHA-139 head (a reference size, the note says how), and
the floor hole carries its drill callout.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle_butt_cup.py crank-handle-butt-cup
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
    assert_imported_precision,
    check_drawing_layout,
    create_section_view,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _section_axis import create_section_axis_centerline, position_section_caption
from crank_handle_butt_cup_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_DIA,
    FLANGE_THICKNESS,
    FLOOR_HOLE_CALLOUT,
    OVERALL_LENGTH,
    REFERENCE_DIMENSIONS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_handle_butt_cup"]
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

# Ø13.5 x 7.3 at 5:1 reads 68 x 37 on the sheet.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
ISO_SCALE = (4, 1)
END_CENTER = (0.080, 0.165)
SECTION_CENTER = (0.215, 0.165)
ISO_CENTER = (0.368, 0.215)
CAPTION_XY = (0.195, 0.100)
MANUFACTURING_NOTES_POS = (0.022, 0.085)
ISO_NOTE_POS = (0.335, 0.170)

_S = VIEW_SCALE[0] / 1000.0
FLANGE_R = FLANGE_DIA * _S / 2.0  # 0.03375
HALF_LENGTH = OVERALL_LENGTH * _S / 2.0  # 0.01825
# The section lays the part's +X to the right (the draw_crank_pinion
# convention), so the flange face is the right edge and the floor the left.
FLANGE_RIGHT_X = SECTION_CENTER[0] + HALF_LENGTH
FLANGE_SEAT_X = FLANGE_RIGHT_X - FLANGE_THICKNESS * _S

# Diameters that open at the flange face stand right of the section, the body
# and the floor hole left of it; the axial sizes stack above (from the flange
# face) and below (the floor).
SECTION_KEEP = {
    "FlangeDia": (FLANGE_RIGHT_X + 0.020, SECTION_CENTER[1]),
    "PocketDia": (FLANGE_RIGHT_X + 0.040, SECTION_CENTER[1]),
    "BodyDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.020, SECTION_CENTER[1]),
    "FloorHoleDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.042, SECTION_CENTER[1]),
    "FlangeThickness": ((FLANGE_RIGHT_X + FLANGE_SEAT_X) / 2.0, SECTION_CENTER[1] + FLANGE_R + 0.009),
    "OverallLength": (SECTION_CENTER[0], SECTION_CENTER[1] + FLANGE_R + 0.021),
    "FloorThickness": (SECTION_CENTER[0] - HALF_LENGTH, SECTION_CENTER[1] - FLANGE_R - 0.010),
}
DIMENSION_CALLOUTS = {"FloorHoleDia": FLOOR_HOLE_CALLOUT}
CUT_START = (END_CENTER[0], END_CENTER[1] - FLANGE_R - 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] + FLANGE_R + 0.006)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-butt-cup source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Crank Handle Butt Cup Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle butt cup; turned steel flanged cup",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="butt cup longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="butt cup")
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (end, section, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        section,
        keep=SECTION_KEEP,
        view_label="longitudinal section",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in sorted(REFERENCE_DIMENSIONS):
        set_reference_dimension(
            adapter, by_name[name], label=f"MHA-153 {name}", diameter=True
        )
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the cup end view")
    create_section_axis_centerline(
        adapter, section, length_mm=OVERALL_LENGTH, label="butt cup axis"
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="crank-handle-butt-cup layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Butt Cup Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

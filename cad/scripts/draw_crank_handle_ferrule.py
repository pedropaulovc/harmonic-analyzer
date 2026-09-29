r"""Create the curated machinist drawing for MHA-150, the crank handle ferrule.

A plain brass ring (user ruling 2026-09-29, ch11 p.14/p.15): OD, bore and
length.  The end view carries only its centre mark and the cutting plane; the
longitudinal section A-A is the ring's length view (policy rule 7) and takes
every dimension, so the bore reads on cut edges rather than hidden lines (the
MHA-150 machinist review).  Every size is routine (.X): the oak tenon is
turned to suit this bore.

Run with SolidWorks open::

    uv run python cad\scripts\draw_crank_handle_ferrule.py crank-handle-ferrule
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
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _section_axis import create_section_axis_centerline, position_section_caption
from crank_handle_ferrule_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OUTER_DIA,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["crank_handle_ferrule"]
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

# Ø15 x 7 at 4:1 reads 60 x 28 on the sheet.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (2, 1)
END_CENTER = (0.085, 0.165)
SECTION_CENTER = (0.215, 0.165)
ISO_CENTER = (0.365, 0.205)
CAPTION_XY = (0.195, 0.113)
MANUFACTURING_NOTES_POS = (0.022, 0.090)
ISO_NOTE_POS = (0.335, 0.160)

OUTER_R = OUTER_DIA * VIEW_SCALE[0] / 2000.0  # 0.030
HALF_LENGTH = LENGTH * VIEW_SCALE[0] / 2000.0  # 0.014

# The OD stands left of the section and the bore right of it; the length
# above.  The cutting line runs vertically through the end view's centre.
SECTION_KEEP = {
    "OuterDia": (SECTION_CENTER[0] - HALF_LENGTH - 0.022, SECTION_CENTER[1]),
    "BoreDia": (SECTION_CENTER[0] + HALF_LENGTH + 0.022, SECTION_CENTER[1]),
    "Length": (SECTION_CENTER[0], SECTION_CENTER[1] + OUTER_R + 0.012),
}
CUT_START = (END_CENTER[0], END_CENTER[1] - OUTER_R - 0.006)
CUT_END = (END_CENTER[0], END_CENTER[1] + OUTER_R + 0.006)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-handle-ferrule source", await adapter.open_model(str(SOURCE)))
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
            0: "Crank Handle Ferrule Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank handle ferrule; turned brass ring",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # The ring revolves about local +X: *Right is the end view, and a vertical
    # cut through it is the longitudinal section on the profile's Front plane.
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    section = create_section_view(
        adapter,
        end,
        line_start=CUT_START,
        line_end=CUT_END,
        view_xy=SECTION_CENTER,
        section_label="A",
        scale=VIEW_SCALE,
        label="ferrule longitudinal section",
    )
    position_section_caption(adapter, section, CAPTION_XY, label="ferrule")
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
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the ferrule end view")
    create_section_axis_centerline(
        adapter, section, length_mm=LENGTH, label="ferrule axis"
    )

    add_property_linked_note(adapter, "Manufacturing Notes", *MANUFACTURING_NOTES_POS)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_POS)
    rebuild_drawing(adapter, label="crank-handle-ferrule layout audit")
    check_drawing_layout(adapter, layout=SPEC.layout, stem=PART_STEM)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Handle Ferrule Manufacturing Drawing",
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

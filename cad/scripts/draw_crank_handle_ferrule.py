r"""Create the curated machinist drawing for MHA-150, the crank handle ferrule.

A plain brass ring (user ruling 2026-09-29, ch11 p.14/p.15): OD, bore and
length, all on the side view (policy rule 7, turned parts: diameters on the
side view), with hidden lines shown so the bore reads.  The end view carries
only centre marks.  The bore and length print their bands from the model
(``crank_handle_ferrule_spec``); one note names the mating tenon.

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
    add_view_centerline,
    assert_imported_precision,
    check_drawing_layout,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
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
SIDE_CENTER = (0.130, 0.160)
END_CENTER = (0.260, 0.160)
ISO_CENTER = (0.365, 0.205)
MANUFACTURING_NOTES_POS = (0.022, 0.095)
ISO_NOTE_POS = (0.335, 0.165)

OUTER_R = OUTER_DIA * VIEW_SCALE[0] / 2000.0  # 0.030
HALF_LENGTH = LENGTH * VIEW_SCALE[0] / 2000.0  # 0.014

# The OD and the bore stand either side of the side view; the length above it.
SIDE_KEEP = {
    "OuterDia": (SIDE_CENTER[0] - HALF_LENGTH - 0.022, SIDE_CENTER[1]),
    "BoreDia": (SIDE_CENTER[0] + HALF_LENGTH + 0.022, SIDE_CENTER[1]),
    "Length": (SIDE_CENTER[0], SIDE_CENTER[1] + OUTER_R + 0.012),
}


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
    # The ring revolves about local +X: *Front is the side view (axis
    # horizontal), *Right the end view.
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Right", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_visible(adapter, side)
    for view in (end, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the ferrule end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0], SIDE_CENTER[1] + 0.8 * OUTER_R),
        label="ferrule side-view axis centerline",
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

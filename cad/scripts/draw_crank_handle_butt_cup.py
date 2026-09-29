r"""Create the curated machinist drawing for MHA-153, the crank handle butt cup.

A flanged steel cup (user ruling 2026-09-29, ch11 p.14/p.15): flange, body,
pocket and floor hole, all on the side view (policy rule 7, turned parts:
diameters on the side view), with hidden lines shown so the pocket and the
floor hole read.  The end view carries only centre marks.  The stack, fit and
clearance sizes print their bands from the model
(``crank_handle_butt_cup_spec``); one note names the mating counterbore.

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
from crank_handle_butt_cup_spec import (
    BODY_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_DIA,
    OVERALL_LENGTH,
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

# Ø10.8 x 4.6 at 8:1 reads 86 x 37 on the sheet: room for seven dimensions.
SHEET_SCALE = (8.0, 1.0)
VIEW_SCALE = (8, 1)
ISO_SCALE = (4, 1)
SIDE_CENTER = (0.140, 0.160)
END_CENTER = (0.290, 0.160)
ISO_CENTER = (0.370, 0.225)
MANUFACTURING_NOTES_POS = (0.022, 0.075)
ISO_NOTE_POS = (0.335, 0.185)

_S = VIEW_SCALE[0] / 1000.0
FLANGE_R = FLANGE_DIA * _S / 2.0  # 0.0432
BODY_R = BODY_DIA * _S / 2.0
HALF_LENGTH = OVERALL_LENGTH * _S / 2.0  # 0.0184

# *Front: local +X to the right, so the flange face (x=0) is the view's right
# end and the body runs left.  Diameters that open at the flange face stand
# right of the view, the body and floor-hole diameters left of it; the axial
# sizes stack above (from the flange face) and below (the pocket).
SIDE_KEEP = {
    "FlangeDia": (SIDE_CENTER[0] + HALF_LENGTH + 0.016, SIDE_CENTER[1]),
    "PocketDia": (SIDE_CENTER[0] + HALF_LENGTH + 0.032, SIDE_CENTER[1]),
    "BodyDia": (SIDE_CENTER[0] - HALF_LENGTH - 0.016, SIDE_CENTER[1]),
    "FloorHoleDia": (SIDE_CENTER[0] - HALF_LENGTH - 0.032, SIDE_CENTER[1]),
    "FlangeThickness": (SIDE_CENTER[0] + HALF_LENGTH, SIDE_CENTER[1] + FLANGE_R + 0.010),
    "OverallLength": (SIDE_CENTER[0], SIDE_CENTER[1] + FLANGE_R + 0.022),
    "PocketDepth": (SIDE_CENTER[0] + 0.004, SIDE_CENTER[1] - FLANGE_R - 0.012),
}


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
        raise RuntimeError("failed to add ASME center marks to the cup end view")
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0] - HALF_LENGTH / 2.0, SIDE_CENTER[1] + 0.9 * BODY_R),
        label="cup side-view axis centerline",
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

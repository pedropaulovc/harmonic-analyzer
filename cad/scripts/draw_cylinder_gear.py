r"""Create the curated manufacturing drawing for the cylinder gear (+ cam).

Sets the batch gear-drawing pattern: two orthographic views (toothed face +
edge profile) dimension the machinable BLANK (bore Ø, face width), while the
GEAR DATA note specifies the involute tooth system (an involute OD is a
scalloped outline with no single circular edge to dimension). The eccentric
cam and alignment notch are carried by the manufacturing notes.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_edge_dimension,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from cylinder_gear_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cylinder_gear"]
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

# 1:1 whole sheet: OD 62.2 mm reads roomily and leaves the left column for the
# gear-data and manufacturing-notes blocks. The gear axis is Z, so *Front shows
# the toothed face and *Right the disc thickness (face 3 + cam) edge-on.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.225, 0.175)
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.375, 0.205)
GEAR_DATA_POS = (0.040, 0.262)

BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0  # bore radius on the sheet (m)

FRONT_KEEP = {
    "BoreDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] - 0.030),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear source", await adapter.open_model(str(SOURCE)))
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
            0: "Cylinder Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear; integral eccentric cam; brass; 120T",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    curate_view_dimensions(adapter, front, keep=FRONT_KEEP, view_label="front")
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to gear bore")

    # Datum A: the bore axis (front view, 12 o'clock pick with the symbol above,
    # the draw_pivot_bushing spelling so the standoff is honoured).
    bore_top = (FRONT_CENTER[0], FRONT_CENTER[1] + BORE_R)
    add_datum_feature(
        adapter,
        front,
        edge_xy=bore_top,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.028),
        datum="A",
        label="cylinder gear bore axis",
    )
    # Gear face perpendicular to the bore axis (datum A), attached to the front
    # face (z=0) silhouette in the profile view. The gear disc runs +z from the
    # front face; the cam boss is on the far face, so the near (left) face edge
    # is a clean full-height silhouette.
    half_od = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
    # z=0 front face: the profile is bbox-centred, so it sits half the full
    # stack (gear 3 + cam 3.5) left of RIGHT_CENTER.
    front_face_x = RIGHT_CENTER[0] - (FACE_WIDTH + 3.5) * VIEW_SCALE[0] / 2000.0
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(front_face_x, RIGHT_CENTER[1] + half_od * 0.55),
        frame_xy=(front_face_x - 0.034, RIGHT_CENTER[1] + half_od + 0.010),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="gear face squareness to bore",
    )
    # Bore finish: pick at 6 o'clock, symbol below (always-clean routing).
    bore_bottom = (FRONT_CENTER[0], FRONT_CENTER[1] - BORE_R)
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_bottom,
        symbol_xy=(FRONT_CENTER[0] + 0.015, FRONT_CENTER[1] - 0.052),
        roughness_ra="1.6",
        label="cylinder gear bore finish",
    )

    add_property_linked_note(adapter, "Gear Data", *GEAR_DATA_POS)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Manufacturing Drawing",
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

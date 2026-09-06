r"""Create the curated manufacturing drawing for the cone gear (T120 shown).

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``): the bore is
the marked model dimension; the GEAR DATA note carries the tooth system; the
cone gear is a 20-member configured family, documented here at its fundamental
T120 configuration with a family note.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from cone_gear_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_datum_feature,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_entities import CircleEdge, EdgeAdjacentFace, FaceBoundary, FeatureFace, ModelEntities
from _gtol_spec import CylinderFace, PlanarFace
from _surface_finish import surface_finish_by_key
from cone_gear_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA, SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_gear"]
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
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.375, 0.205)

BORE_R = BORE_DIA * VIEW_SCALE[0] / 2000.0
HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
FRONT_FACE_X = RIGHT_CENTER[0] - FACE_WIDTH * VIEW_SCALE[0] / 2000.0

FRONT_KEEP = {
    "BoreCutDia": (FRONT_CENTER[0] - 0.055, FRONT_CENTER[1] - 0.030),
}
# The generated gear has hundreds of tooth faces. Follow explicit ownership
# from its named bore cut to the front rim and its neighbouring blank face.
# This bounds entity discovery independently of tooth count.
BORE_FACE = FeatureFace("BoreCut", CylinderFace(BORE_DIA))
BORE_RIM = FaceBoundary(BORE_FACE, CircleEdge(BORE_DIA / 2.0, (0, 0, 0), (0, 0, 1)))
ENTITY_ROLES = {
    "bore": BORE_RIM,
    "front_face": EdgeAdjacentFace(BORE_RIM, PlanarFace((0, 0, -1), 0.0)),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-gear source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Gear Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone gear; brass; T120 of the 20-gear cone set",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    # 3 decimals so the displayed bore matches the family rows' 9.525 (a
    # 2-decimal 9.53 reads as a conflicting definition).
    set_dimension_precision(adapter, front_annotations, {"BoreCutDia": 3})
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to gear bore")
    entities = ModelEntities(front.ReferencedDocument).resolve(ENTITY_ROLES)
    bore_edge = entities["bore"]

    add_datum_feature(
        adapter,
        front,
        entity=bore_edge,
        selection_point_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + BORE_R),
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.028),
        datum="A",
        label="cone gear bore axis",
        shoulder=True,
        position_tolerance_m=0.0001,
    )
    add_feature_control_frame(
        adapter,
        right,
        entity=entities["front_face"],
        entity_type="FACE",
        frame_xy=(FRONT_FACE_X - 0.034, RIGHT_CENTER[1] + HALF_OD + 0.010),
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["gear face squareness to bore"],
        datums=("A",),
        label="gear face squareness to bore",
    )
    add_surface_finish(
        adapter,
        front,
        symbol_xy=(FRONT_CENTER[0] + 0.015, FRONT_CENTER[1] - 0.052),
        control=surface_finish_by_key(SURFACE_FINISHES, "cone_gear_bore"),
        label="cone gear bore finish",
        entity=bore_edge,
    )

    add_property_linked_note(adapter, "Gear Data", 0.018, 0.262)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.018, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Gear Manufacturing Drawing",
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

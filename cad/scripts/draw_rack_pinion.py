r"""Create the curated manufacturing drawing for the rack-pinion reduction disc.

Follows the batch gear-drawing pattern (see ``draw_cylinder_gear``). Drawn 1:1;
the 120T disc is large and thin.
"""

from __future__ import annotations

import argparse
from rack_pinion_spec import DIMENSION_CALLOUTS
import sys
from typing import Any

from rack_pinion_spec import GEOMETRIC_TOLERANCES_MM

import _telemetry
from _common import CAD_ROOT, _early_bound, check
from _drawing_build import ProjectDrawingFactory, TemplateSpec, run_drawing_build
from _drawing_common import (
    DrawingOutputs,
    add_feature_control_frame,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    read_required_properties,
    verify_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _native_axis_datum import add_native_axis_datum
from _surface_finish import surface_finish_by_key
from rack_pinion_spec import BORE_DIA, FACE_WIDTH, OUTSIDE_DIA, SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
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
TEMPLATE_SPEC = TemplateSpec(scale=SHEET_SCALE, decimals=2)
VIEW_SCALE = (1, 1)
FRONT_CENTER = (0.220, 0.175)
RIGHT_CENTER = (0.320, 0.175)
ISO_CENTER = (0.383, 0.210)  # 0.388 clipped the zone border right by 1.4 mm
BORE_FINISH_POSITION = (FRONT_CENTER[0] + 0.058, FRONT_CENTER[1] - 0.062)

HALF_OD = OUTSIDE_DIA * VIEW_SCALE[0] / 2000.0
FRONT_FACE_X = RIGHT_CENTER[0] - FACE_WIDTH * VIEW_SCALE[0] / 2000.0

FRONT_KEEP = {
    # Approach from upper-left, clear of native datum A below-left.
    "BoreDia": (FRONT_CENTER[0] - 0.062, FRONT_CENTER[1] + 0.038),
}

DIMENSION_PRECISION = {"BoreDia": 2}


async def build(
    adapter: Any, *, drawing_factory: ProjectDrawingFactory
) -> dict[str, str]:
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
    callout_source_model = adapter.currentModel
    drawing_model, _sheet = drawing_factory(
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
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    verify_dimension_callouts(
        adapter,
        front_annotations,
        DIMENSION_CALLOUTS,
        feature_name="BoreProfile",
        view=front,
        source_model=callout_source_model,
    )
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to disc bore")
    bore_edge = visible_circle_edge(adapter, front, BORE_DIA)

    add_native_axis_datum(
        adapter,
        front,
        entity=bore_edge,
        source_path=SOURCE,
        radius_m=BORE_DIA / 2000.0,
        datum="A",
        label="rack pinion bore axis",
        shoulder=True,
        stability_tolerance_m=0.0001,
    )
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=(FRONT_FACE_X, RIGHT_CENTER[1] + HALF_OD * 0.55),
        frame_xy=(FRONT_FACE_X - 0.034, RIGHT_CENTER[1] + HALF_OD + 0.010),
        characteristic="perpendicularity",
        tolerance=GEOMETRIC_TOLERANCES_MM["disc face squareness to bore"],
        datums=("A",),
        label="disc face squareness to bore",
    )
    # Keep the finish text outside the enlarged view and approach the opposite
    # side of the bore from datum A. The pick remains the semantic bore edge;
    # this projected point controls the leader attachment, not entity selection.
    finish = add_surface_finish(
        adapter,
        front,
        symbol_xy=BORE_FINISH_POSITION,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="rack pinion bore finish",
        entity=bore_edge,
        leader_attach_xy=model_point_in_view(
            adapter, front, (BORE_DIA / 2000.0, 0.0, FACE_WIDTH / 1000.0),
            label="rack bore finish rim point",
        ),
    )
    finish_annotation = _early_bound(finish.GetAnnotation(), "IAnnotation")
    finish_entities = tuple(finish_annotation.GetAttachedEntities3() or ())
    if (
        tuple(finish_annotation.GetAttachedEntityTypes() or ()) != (1,)
        or len(finish_entities) != 1 or finish_entities[0] is None
        or int(adapter.swApp.IsSame(finish_entities[0], bore_edge)) != 1
        or finish_annotation.IsDangling()
    ):
        raise RuntimeError("rack bore finish lost its semantic edge attachment")

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
    sys.exit(run_drawing_build(build, spec=TEMPLATE_SPEC))

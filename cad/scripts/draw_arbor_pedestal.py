r"""Create the curated machinist drawing for the cylinder-arbor pedestal."""

from __future__ import annotations

import argparse
import sys
from typing import Any

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
    set_dimension_callouts,
    set_dimension_precision,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from arbor_pedestal_spec import BORE_DIA, BORE_HEIGHT, FOOT_HEIGHT
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    remove_notes_matching,
)


SPEC = DRAWINGS_BY_NAME["arbor_pedestal"]
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

SHEET_SCALE = (2.0, 1.0)  # 64 mm tall casting -- 2:1 keeps the strap/bore legible
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# The casting spans model y 0 (foot seat) .. 64 (dome top); centre the front
# elevation on that midpoint. Third-angle: the 24x16 foot plan sits ABOVE the
# elevation, the isometric off to the right.
_PART_MID_Y = (BORE_HEIGHT + 10.0) / 2.0  # foot 0 .. dome top (bore + dome radius)
FRONT_CENTER = (0.100, 0.145)
TOP_CENTER = (0.100, 0.250)
ISO_CENTER = (0.335, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (foot seat at model y=0)."""
    return FRONT_CENTER[1] + (model_y - _PART_MID_Y) * _S


# Front elevation carries the foot width + flange height, the arbor-bore station
# and diameter, and the dome diameter; the plan carries the 16 foot depth.
FRONT_KEEP = {
    "Width": (FRONT_CENTER[0], _front_y(0.0) - 0.014),
    "FootHt": (FRONT_CENTER[0] - 0.030, _front_y(FOOT_HEIGHT / 2.0)),
    "BoreHeight": (FRONT_CENTER[0] - 0.048, _front_y(BORE_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.050, _front_y(BORE_HEIGHT)),
    "DomeDia": (FRONT_CENTER[0] + 0.048, _front_y(BORE_HEIGHT + 6.0)),
}
TOP_KEEP = {
    "Depth": (TOP_CENTER[0] + 0.040, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {"BoreDia": "THRU, ARBOR CLAMP FIT"}
# 3/8 in = 9.525 exactly; show 3 places so the view matches the note (else the
# 2-decimal sheet default prints 9.53 against the DIA 9.525 the note cites).
DIMENSION_PRECISION = {"BoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open arbor-pedestal source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
            0: "Cylinder-Arbor Pedestal Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "arbor pedestal; gray-iron casting; arbor clamp bore",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    set_hidden_lines_removed(adapter, iso)
    # The elevation carries the arbor bore as a hidden circle and the flange
    # hold-down hole; the plan shows the foot with the bore + screw crossing it.
    for view in (front, top):
        set_hidden_lines_visible(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    top_annotations = curate_view_dimensions(
        adapter, top, keep=TOP_KEEP, view_label="top"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *top_annotations], DIMENSION_CALLOUTS
    )
    set_dimension_precision(adapter, front_annotations, DIMENSION_PRECISION)
    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the plan view")

    # Datum A = the foot seat face (the base-seat datum the bore/dome heights
    # measure from). The arbor bore is toleranced parallel to it and carries the
    # clamp-fit finish.
    _bore_r = BORE_DIA / 2.0 * _S
    foot_edge = (FRONT_CENTER[0] + 0.006, _front_y(0.0))
    add_datum_feature(
        adapter,
        front,
        edge_xy=foot_edge,
        symbol_xy=(foot_edge[0], _front_y(0.0) - 0.012),
        datum="A",
        label="foot seat face",
    )
    # The arbor bore is seen end-on (a circle); its axis runs horizontal (along
    # Z), so it is PARALLEL to the horizontal foot seat (datum A) -- parallelism
    # holds the arbor axis at a constant height off the seat.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_HEIGHT) + _bore_r),  # bore top
        frame_xy=(0.155, _front_y(BORE_HEIGHT) + 0.030),
        characteristic="parallelism",
        tolerance="0.05",
        datums=("A",),
        label="arbor bore parallelism",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BORE_HEIGHT)),  # bore right
        symbol_xy=(0.157, _front_y(BORE_HEIGHT) - 0.026),
        roughness_ra="1.6",
        label="arbor bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.070)

    # The #4 flange hold-down is a native Hole Wizard clearance feature, so the
    # model-item import may bring SolidWorks' descriptive callout note for it;
    # it duplicates the prose note, so drop it if present (best-effort -- a
    # clearance hole does not always carry one).
    remove_notes_matching(adapter, "Clearance")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder-Arbor Pedestal Manufacturing Drawing",
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

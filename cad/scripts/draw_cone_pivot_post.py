r"""Create the curated machinist drawing for the cone pivot post."""

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
from cone_pivot_post_spec import (
    BLOCK_HEIGHT,
    BORE_DIA,
    BORE_HEIGHT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["cone_pivot_post"]
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
_S = SHEET_SCALE[0] / 1000.0  # sheet meters per model mm

# Third-angle: the round Ø24 plan sits ABOVE the front elevation (which carries
# the column height + both bore stations); the isometric is off to the right.
FRONT_CENTER = (0.100, 0.150)
TOP_CENTER = (0.100, 0.235)
ISO_CENTER = (0.330, 0.150)


def _front_y(model_y: float) -> float:
    """Sheet Y of a model-Y point in the front view (1:1, foot at model y=0)."""
    return FRONT_CENTER[1] + (model_y - BLOCK_HEIGHT / 2.0) * _S


# Front elevation carries the column height, the journal-bore station and the
# journal bore diameter; the plan carries the round Ø24.
FRONT_KEEP = {
    "BlockHt": (FRONT_CENTER[0] - 0.045, FRONT_CENTER[1]),
    "BoreZ": (FRONT_CENTER[0] - 0.030, _front_y(BORE_HEIGHT / 2.0)),
    "BoreDia": (FRONT_CENTER[0] + 0.040, _front_y(BORE_HEIGHT)),
}
TOP_KEEP = {
    "BlockDia": (TOP_CENTER[0] + 0.040, TOP_CENTER[1]),
}
DIMENSION_CALLOUTS = {"BoreDia": "THRU, CLOSE RUNNING FIT"}
# 3/8 in = 9.525 exactly; the sheet default of 2 decimals prints 9.53, a false
# contradiction of the DIA 9.525 the note and the mating cone shaft are built on.
DIMENSION_PRECISION = {"BoreDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cone-pivot-post source", await adapter.open_model(str(SOURCE)))
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
            0: "Cone Pivot Post Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post; cast iron column; journal + crank bores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # The elevation carries both bores as hidden circles; the plan shows them
    # crossing the round column.
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

    # Datum A = the foot seat face (the platform-seat datum the bore heights
    # measure from). The journal bore is toleranced perpendicular to it and
    # carries the running-fit finish.
    _bore_r = BORE_DIA / 2.0 * _S
    foot_edge = (FRONT_CENTER[0] + 0.005, _front_y(0.0))
    add_datum_feature(
        adapter,
        front,
        edge_xy=foot_edge,
        symbol_xy=(foot_edge[0], _front_y(0.0) - 0.010),
        datum="A",
        label="foot seat face",
    )
    # Journal bore is seen end-on (a circle); its axis runs horizontal (along Z),
    # so it is PARALLEL to the horizontal foot seat (datum A) -- parallelism, not
    # perpendicularity, keeps the shaft axis at a constant height off the seat.
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0], _front_y(BORE_HEIGHT) + _bore_r),  # bore top
        frame_xy=(0.145, _front_y(BORE_HEIGHT) + 0.028),
        characteristic="parallelism",
        tolerance="0.05",
        datums=("A",),
        label="journal bore parallelism",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=(FRONT_CENTER[0] + _bore_r, _front_y(BORE_HEIGHT)),  # bore right
        symbol_xy=(0.150, _front_y(BORE_HEIGHT) - 0.024),
        roughness_ra="1.6",
        label="journal bore finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.075)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Pivot Post Manufacturing Drawing",
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

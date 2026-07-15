r"""Create the curated machinist drawing for the pinion lift rod."""

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
    set_hidden_lines_removed,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_lift_rod_spec import CAP_SAG, ROD_DIA, ROD_LEN
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_lift_rod"]
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
END_VIEW_SCALE = 2.0
# The crown adds CAP_SAG past the nominal length, so the side view's bounding
# box (and its centre) span ROD_LEN + CAP_SAG.
HALF_SPAN = (ROD_LEN + CAP_SAG) / 2000.0
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + HALF_SPAN * SHEET_SCALE[0] + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)

FRONT_KEEP = {
    # Offset kept tight (-0.010, not the fulcrum -0.025): the toleranced text
    # is wide and a further-left anchor runs it across the sheet border.
    "RodDia": (
        FRONT_CENTER[0] - ROD_DIA * END_VIEW_SCALE / 1000.0 - 0.010,
        FRONT_CENTER[1] + 0.008,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
DIMENSION_CALLOUTS = {"RodDia": "+0.00/-0.02"}
# The length tolerance rides its own dimension (codex machinist review: a
# detached "LENGTH +/-0.25" UOS note is ambiguous about which length it bounds).
RIGHT_CALLOUTS = {"Depth": "+/-0.25"}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-lift-rod source", await adapter.open_model(str(SOURCE)))
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
            "End View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Lift Rod Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion lift rod; eccentric cam rod; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, right_annotations, RIGHT_CALLOUTS)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to rod end view")

    end_circle = (
        FRONT_CENTER[0] + ROD_DIA * END_VIEW_SCALE / 2000.0,
        FRONT_CENTER[1],
    )
    # In the *Right view the part's +Z (crowned back end) points screen-left,
    # so the flat front end (z=0) is the RIGHT silhouette edge.
    flat_end = (RIGHT_CENTER[0] + HALF_SPAN, RIGHT_CENTER[1])
    add_datum_feature(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.024),
        datum="A",
        label="lift rod axis",
    )
    add_feature_control_frame(
        adapter,
        front,
        edge_xy=end_circle,
        frame_xy=(RIGHT_CENTER[0], 0.232),
        characteristic="cylindricity",
        tolerance="0.01",
        label="lift rod bearing cylindricity",
    )
    # Only the flat front end gets a perpendicularity control -- the back end
    # is the SR4.8 crown (a note), where a face-orientation callout is
    # meaningless.
    add_feature_control_frame(
        adapter,
        right,
        edge_xy=flat_end,
        frame_xy=(flat_end[0] + 0.014, 0.180),
        characteristic="perpendicularity",
        tolerance="0.05",
        datums=("A",),
        label="front end perpendicularity",
    )
    add_surface_finish(
        adapter,
        front,
        edge_xy=end_circle,
        symbol_xy=(RIGHT_CENTER[0], 0.245),
        roughness_ra="1.6",
        label="lift rod bearing finish",
    )
    add_surface_finish(
        adapter,
        right,
        edge_xy=flat_end,
        symbol_xy=(flat_end[0] + 0.020, 0.218),
        roughness_ra="3.2",
        label="front end finish",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.014, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Lift Rod Manufacturing Drawing",
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

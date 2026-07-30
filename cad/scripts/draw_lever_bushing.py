r"""Create the curated machinist drawing for the lever-bank spacer bushing."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from lever_bushing_spec import (
    BORE_DIA,
    GEOMETRIC_CONTROLS,
    LENGTH,
    OUTER_DIA,
    PART_DATUMS,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["lever_bushing"]
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

SHEET_SCALE = (4.0, 1.0)
FRONT_CENTER = (0.080, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + (OUTER_DIA + LENGTH) * SHEET_SCALE[0] / 1000.0 + 0.045,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.315, 0.205)

FRONT_KEEP = {
    "OuterDia": (
        FRONT_CENTER[0] - 0.035,
        FRONT_CENTER[1] + 0.010,
    ),
    "BoreDia": (
        FRONT_CENTER[0] + OUTER_DIA * SHEET_SCALE[0] / 1000.0 + 0.005,
        FRONT_CENTER[1] - 0.010,
    ),
}
RIGHT_KEEP = {
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.040),
}
# Bore and length tolerances live on the source model; the linked note carries
# the drill-under/ream-through manufacturing instruction.
DIMENSION_CALLOUTS: dict[str, str] = {}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open lever-bushing source", await adapter.open_model(str(SOURCE)))
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
            0: "Lever Bushing Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "lever bushing; turned spacer; brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(4, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(4, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    set_hidden_lines_visible(adapter, right)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP, view_label="front"
    )
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    annotations = [*front_annotations, *right_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to front view")

    bore_edge = (
        FRONT_CENTER[0] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
        FRONT_CENTER[1],
    )
    bore_top = (
        FRONT_CENTER[0],
        FRONT_CENTER[1] + BORE_DIA * SHEET_SCALE[0] / 2000.0,
    )
    outer_radius = OUTER_DIA * SHEET_SCALE[0] / 2000.0
    outer_runout = (
        FRONT_CENTER[0] + outer_radius * math.cos(math.radians(45.0)),
        FRONT_CENTER[1] + outer_radius * math.sin(math.radians(45.0)),
    )
    half_depth = LENGTH * SHEET_SCALE[0] / 2000.0
    left_end = (RIGHT_CENTER[0] - half_depth, RIGHT_CENTER[1])
    right_end = (RIGHT_CENTER[0] + half_depth, RIGHT_CENTER[1])
    # GD&T is model PMI (lever_bushing_spec.PART_DATUMS/GEOMETRIC_CONTROLS,
    # authored by build_lever_bushing) — project it and place it where the
    # hand-authored symbols used to sit. Which VIEW receives each annotation
    # depends on its attachment (a datum tag only lands in a view aligned
    # with its face), and the projection fails loud on any mismatch.
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=front,
                position=(FRONT_CENTER[0], FRONT_CENTER[1] + 0.037),
                attachment_xy=bore_top,
                position_tolerance_m=0.0001,
            ),
            "datum:B": PmiDrawingPlacement(
                view=right,
                position=(left_end[0] - 0.018, RIGHT_CENTER[1]),
                attachment_xy=left_end,
            ),
            "od_runout": PmiDrawingPlacement(
                view=front, position=(0.115, 0.255), attachment_xy=outer_runout
            ),
            "end_face_parallelism": PmiDrawingPlacement(
                view=right,
                position=(right_end[0] + 0.014, 0.180),
                attachment_xy=right_end,
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="lever bushing PMI",
    )
    # Sits just right of the front view, level with the bore. From (0.160, 0.225)
    # the leader ran ~70 mm diagonally back across the whole ring to reach the
    # bore, tangling with the Ø12.00 and Ø6.50 dimension lines that already meet
    # at the centre. The symbol draws UP and RIGHT of its anchor (roughly
    # x+0.039, y+0.019) and the leader leaves the anchor itself, so anchoring
    # just above/right of the bore keeps the leader short and the body in the
    # empty band between the views: clear of the Ø6.50 callout below (it ends at
    # y=0.205) and the runout frame above (y=0.251).
    #
    # NOTE this reasoning bounds the symbol BODY only. If this symbol moves,
    # re-check its LEADER's path back to bore_edge, not just where the body
    # lands — a leader once crossed the runout frame's sheet-authored arrowhead
    # at (0.1041, 0.2079) even though the body itself was clear.
    add_surface_finish(
        adapter,
        front,
        edge_xy=bore_edge,
        symbol_xy=(0.120, 0.212),
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="bushing bore finish",
    )

    # x=0.020: the anchor is the text's left edge, so the ink starts here. The
    # sheet's 0.0127 zone margin and the re-centred border rule (~0.0126) now
    # agree, so 0.020 clears the rule and the audit enforces the same bound.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.095)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Lever Bushing Manufacturing Drawing",
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

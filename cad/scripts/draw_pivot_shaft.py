r"""Create the curated machinist drawing for the rocker pivot shaft.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
plain bearing shaft carries no datums and no feature-control frames -- its
running fit is the band on the model diameter, plus one roughness symbol on
the OD the rocker arms swing on. The diameter and the length both read on
the side view (policy rule 7: a turned part is dimensioned as it sits in the
lathe); the end view carries only its centre mark.
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
from _surface_finish import surface_finish_by_key
from pivot_shaft_spec import SHAFT_DIA, SHAFT_LENGTH, SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pivot_shaft"]
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
FRONT_CENTER = (0.055, 0.205)
# 0.060 between the end circle and the side view's left end (was 0.045): the
# diameter callout now stands at that end, ~25 mm wide, and needs the room.
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.060,
    FRONT_CENTER[1],
)
# NOT the fulcrum-shaft spot (0.355, 0.205): the shaft's isometric silhouette
# reaches ~0.072 m each side of center, so up there it ran past the right
# border line. The empty band between the notes block and the title block
# fits it whole (its low tip stays above the title block's 0.064 top rule).
ISO_CENTER = (0.320, 0.120)

# Side-view landmarks: the shaft's left end and its top flank (a 6.35-dia
# cylinder at 1:1, so the top silhouette runs ~3.2 mm above the view centre).
LEFT_END_X = RIGHT_CENTER[0] - SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0
SHAFT_FLANK_Y = RIGHT_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0

# Every marked dimension reads on the side view: the diameter as a linear
# diameter between the flank silhouettes at the left end, the length below.
# The end view keeps nothing -- SolidWorks inserts each marked model
# dimension into ONE view, so the side view is curated first and the end
# view is never asked (draw_pinion_bracket, 2026-09-02 seat build).
FRONT_KEEP: dict[str, tuple[float, float]] = {}
RIGHT_KEEP = {
    "ShaftDia": (LEFT_END_X - 0.024, RIGHT_CENTER[1]),
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.025),
}
# Size tolerances live on the source-model dimensions; the sheet renders them natively.
DIMENSION_CALLOUTS: dict[str, str] = {}
# The diameter is the one fitted feature (SHAFT_H band on the model
# dimension): three decimals say "hold it".
DIMENSION_PRECISION = {"ShaftDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            0: "Pivot Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot shaft; rocker bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    set_hidden_lines_removed(adapter, iso)
    # Hidden lines stay ON in every orthographic view (Harvey #30 / Lipton).
    for view in (front, right):
        set_hidden_lines_visible(adapter, view)

    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, right_annotations, DIMENSION_PRECISION)
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to shaft end view")

    # The bearing OD is the one running surface (the rocker arms swing on it),
    # so it alone carries a roughness symbol. It anchors to the shaft's flank
    # in the side view, which shows the cylindrical face edge-on. A cylinder
    # carries no model edge along its side, so the pick is a SILHOUETTE entity
    # (as in draw_transgear_stub). The Ra text renders ABOVE the arm (ASME
    # Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.045, SHAFT_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.045, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bearing"),
        label="pivot bearing finish",
        entity_type="SILHOUETTE",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred border rule
    # now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Shaft Manufacturing Drawing",
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

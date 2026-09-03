r"""Create the curated machinist drawing for the lever fulcrum shaft.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
plain bearing shaft carries no datums and no feature-control frames -- its
running fit is the band on the model diameter, plus one roughness symbol on
the OD the channel levers rock on. The diameter, the length and the Ra all
read on the side view (policy rule 7: a turned part is dimensioned as it sits
in the lathe); the end view carries only its centre mark.
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
from fulcrum_shaft_spec import SHAFT_DIA, SHAFT_LENGTH, SURFACE_FINISHES
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["fulcrum_shaft"]
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
# The side view's right end lands at x~0.297, 24 mm short of the 1:2 iso.
RIGHT_CENTER = (
    FRONT_CENTER[0] + SHAFT_LENGTH * SHEET_SCALE[0] / 2000.0 + 0.060,
    FRONT_CENTER[1],
)
ISO_CENTER = (0.355, 0.205)
# 1:2, like the near-identical 187 arbor on MHA-028: at 1:1 the 182 shaft's
# isometric is a ~136 mm diagonal bar whose outline ran x=0.287..0.423 -- over
# the right zone border (0.4191).  At 1:2 the outline is ~x=0.321..0.389,
# inside the border.
ISO_SCALE = (1, 2)

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
# The shaft fit lives on the source-model dimension.
DIMENSION_CALLOUTS: dict[str, str] = {}
# The diameter is the one fitted feature (SHAFT_H band on the model
# dimension): three decimals say "hold it".
DIMENSION_PRECISION = {"ShaftDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open fulcrum-shaft source", await adapter.open_model(str(SOURCE)))
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
            "Iso View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "End View Note",
            "Iso View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Fulcrum Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "fulcrum shaft; bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
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

    # The bearing OD is the one running surface (the channel levers rock on
    # it), so it alone carries a roughness symbol, anchored on the shaft's
    # flank in the side view (a SILHOUETTE pick: a cylinder carries no model
    # edge along its side, as in draw_pivot_shaft). The Ra text renders ABOVE
    # the arm (ASME Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.045, SHAFT_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.045, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="fulcrum bearing finish",
        entity_type="SILHOUETTE",
    )

    # 0.020: the note is left-aligned on its anchor, so the ink starts here. The
    # left bound is the 12.7 mm zone margin (~0.0127), which the re-centred frame
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.170)
    # The iso renders at 1:2 while the title block reads 1:1, so the pictorial
    # needs its own scale callout or the sheet misstates it. Placed at the same
    # offset from ISO_CENTER that cylinder-gear-shaft uses for its identical 1:2
    # iso (dx -0.030, dy -0.048), so the two sibling shafts read alike.
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.157)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Fulcrum Shaft Manufacturing Drawing",
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

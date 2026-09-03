r"""Create the curated machinist drawing for the pinion lift rod.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
plain bearing rod carries no datums and no feature-control frames -- its
running fit is the band on the model diameter, plus one roughness symbol on
the OD that spins in the pivot-block bores. The diameter, the shank length
and the Ra all read on the side view (policy rule 7: a turned part is
dimensioned as it sits in the lathe); the crown is a note leadered to the
crowned end, and the true overall length is a conspicuous reference below
the shank length (machinist review 2026-09-02: the 202.00 read as the
overall and the crown note said "back end" from the block).
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
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
from pinion_lift_rod_spec import (
    CAP_SAG,
    CROWN_NOTE,
    OVERALL_LEN,
    ROD_DIA,
    ROD_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
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
HALF_SPAN = OVERALL_LEN / 2000.0
FRONT_CENTER = (0.055, 0.205)
# 0.060 between the end circle and the side view's left end (was 0.045): the
# crown note now sits above that end and needs the room.
RIGHT_CENTER = (
    FRONT_CENTER[0] + HALF_SPAN * SHEET_SCALE[0] + 0.060,
    FRONT_CENTER[1],
)
# NOT (0.355, 0.205): up there the iso crowded the side view's right end. The
# empty band below the side view and right of the notes block takes it whole,
# clear of the length dimensions above it.
ISO_CENTER = (0.345, 0.145)

# Side-view landmarks (sheet meters): crown apex at the LEFT end, flat front
# end at the RIGHT (the exact apex / rim points are projected from the model
# at build time). The rod's top flank is a 6.35-dia cylinder at 1:1, so its
# silhouette runs ~3.2 mm above the view centre.
LEFT_END_X = RIGHT_CENTER[0] - HALF_SPAN * SHEET_SCALE[0]
RIGHT_END_X = RIGHT_CENTER[0] + HALF_SPAN * SHEET_SCALE[0]
ROD_FLANK_Y = RIGHT_CENTER[1] + ROD_DIA * SHEET_SCALE[0] / 2000.0

# Every marked dimension reads on the side view: the diameter as a linear
# diameter between the flank silhouettes at the flat right end, the shank
# length below. The end view keeps nothing -- SolidWorks inserts each marked
# model dimension into ONE view, so the side view is curated first and the
# end view is never asked (draw_pinion_bracket, 2026-09-02 seat build).
FRONT_KEEP: dict[str, tuple[float, float]] = {}
RIGHT_KEEP = {
    "RodDia": (RIGHT_END_X + 0.024, RIGHT_CENTER[1]),
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.020),
}
# The shank length says where it stops (the crown root, not the apex); the
# diameter and length bands ride their model dimensions.
DIMENSION_CALLOUTS = {"Depth": "TO CROWN ROOT"}
# The diameter is the one fitted feature (SHAFT_H band on the model
# dimension): three decimals say "hold it".
DIMENSION_PRECISION = {"RodDia": 3}
# The crown note stands above-left of the crowned end, its leader down to the
# apex; the Ra (x~0.26) and the end view (x<=0.068) both stay clear.
CROWN_NOTE_XY = (LEFT_END_X - 0.012, 0.236)
OVERALL_NOTE = f"({OVERALL_LEN:.2f}) OVERALL REF"
OVERALL_NOTE_XY = (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.035)


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
        raise RuntimeError("failed to add ASME center mark to rod end view")

    # The crown apex is projected from the MODEL for the attached process
    # callout below; the overall reference note itself selects no geometry.
    apex = model_point_in_view(
        adapter, right, (0.0, 0.0, OVERALL_LEN / 1000.0), label="crown apex"
    )
    # The true overall is reference information derived from the same geometry
    # contract as the model.  A view-adjacent note is deliberate: the shallow
    # revolved crown apex is not a stable selectable drawing vertex across
    # SolidWorks seats.
    if add_note(adapter, OVERALL_NOTE, *OVERALL_NOTE_XY) is None:
        raise RuntimeError("failed to add pinion lift rod overall reference note")
    # The crown, called out FROM the crowned end (its sketch dims live on the
    # Top plane, outside every placed view).
    add_attached_note(
        adapter,
        right,
        text=CROWN_NOTE,
        entity_xy=apex,
        note_xy=CROWN_NOTE_XY,
        label="crown callout",
        entity_type="VERTEX",
    )

    # The rod OD is the one running surface (the rod spins in the pivot-block
    # bores as the cam input), so it alone carries a roughness symbol,
    # anchored on the rod's flank in the side view (a SILHOUETTE pick: a
    # cylinder carries no model edge along its side, as in
    # draw_transgear_stub). The Ra text renders ABOVE the arm (ASME Y14.36),
    # reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.045, ROD_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.045, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="lift rod bearing finish",
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

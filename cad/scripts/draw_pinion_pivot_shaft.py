r"""Create the curated machinist drawing for the pinion strap torque shaft.

A plain Ø6.35 turned steel shaft with a shallow spherical crown at each end.
Modelled on the fulcrum-shaft slice: a 4:1 end view carries the centre mark,
the 1:1 side view carries the diameter, the body length between the crown
roots, the (194.40) overall reference and the crown callout, and a 1:2
isometric stays clear of the title block.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
plain shaft carries no datums or frames; the size band rides the model
diameter and the one roughness symbol sits on the journal the two swing
straps rock on. Diameter, length and Ra all read on the side view (policy
rule 7: a turned part is dimensioned as it sits in the lathe).

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_pivot_shaft.py pinion-pivot-shaft
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_attached_note,
    add_edge_dimension,
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
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pinion_pivot_shaft_spec import (
    CAP_SAG,
    CROWN_NOTE,
    OVERALL_LEN,
    SHAFT_DIA as SHAFT_DIA,
    SHAFT_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_pivot_shaft"]
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
END_VIEW_SCALE = 4.0
# Both crowns add CAP_SAG past the body, so the side view's bounding box (and
# its centre) span the full OVERALL_LEN.
HALF_SPAN = OVERALL_LEN / 2000.0
FRONT_CENTER = (0.055, 0.205)
# 0.060 between the end circle and the side view's left end (was 0.045): the
# crown note now sits above that end and needs the room.
RIGHT_CENTER = (
    FRONT_CENTER[0] + HALF_SPAN * SHEET_SCALE[0] + 0.060,
    FRONT_CENTER[1],
)
# NOT (0.355, 0.205): the diameter callout now stands at the side view's right
# end (x~0.333) where a 1:2 iso spanning x=0.321..0.389 sat. The empty band
# between the notes block and the title block takes it whole (its low edge
# stays above the title block's 0.064 top rule).
ISO_CENTER = (0.355, 0.120)
# 1:2, like fulcrum-shaft's identical long turned shaft: at 1:1 a 194 mm
# isometric bar runs over the right zone border, so the pictorial is halved and
# a scale callout keeps the title block honest.
ISO_SCALE = (1, 2)

# Side-view landmarks (sheet meters): crown apexes at BOTH ends (the exact
# apex points are projected from the model at build time). The body's top
# flank is a 6.35-dia cylinder at 1:1, so its silhouette runs ~3.2 mm above
# the view centre.
LEFT_END_X = RIGHT_CENTER[0] - HALF_SPAN * SHEET_SCALE[0]
RIGHT_END_X = RIGHT_CENTER[0] + HALF_SPAN * SHEET_SCALE[0]
SHAFT_FLANK_Y = RIGHT_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0

# Every marked dimension reads on the side view: the diameter as a linear
# diameter between the flank silhouettes at the right end, the body length
# below. The end view keeps nothing -- SolidWorks inserts each marked model
# dimension into ONE view, so the side view is curated first and the end
# view is never asked (draw_pinion_bracket, 2026-09-02 seat build).
FRONT_KEEP: dict[str, tuple[float, float]] = {}
RIGHT_KEEP = {
    "ShaftDia": (RIGHT_END_X + 0.024, RIGHT_CENTER[1]),
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.020),
}
DIMENSION_CALLOUTS = {
    "Depth": "BETWEEN CROWN ROOT CIRCLES",
}
# The diameter is the one fitted feature (SHAFT_H band on the model
# dimension): three decimals say "hold it".
DIMENSION_PRECISION = {"ShaftDia": 3}
# The crown note stands above-left of the left crown, its leader down to that
# apex; the Ra (x~0.26) and the end view (x<=0.068) both stay clear.
CROWN_NOTE_XY = (LEFT_END_X - 0.012, 0.238)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Torque Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion torque shaft; pivot shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(4, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    set_hidden_lines_removed(adapter, iso)
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

    # Both crown apexes projected from the MODEL (a revolve apex is a VERTEX):
    # the front cap reaches z=-CAP_SAG, the back cap z=SHAFT_LEN+CAP_SAG.
    front_apex = model_point_in_view(
        adapter, right, (0.0, 0.0, -CAP_SAG / 1000.0), label="front crown apex"
    )
    back_apex = model_point_in_view(
        adapter,
        right,
        (0.0, 0.0, (SHAFT_LEN + CAP_SAG) / 1000.0),
        label="back crown apex",
    )
    # The true overall (apex to apex), as a conspicuous reference below the
    # body length so nobody saws the stock short (Harvey #25) -- review
    # 2026-09-02: the overall had to be derived from both crowns.
    overall = add_edge_dimension(
        adapter,
        right,
        p0=front_apex,
        p1=back_apex,
        text_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.040),
        label="overall length reference",
        orientation="horizontal",
        entity_types=("VERTEX", "VERTEX"),
    )
    set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="overall length reference",
    )
    # The crowns, called out FROM the left crown (whichever apex projects
    # left) rather than from the remote note block.
    left_apex = min((front_apex, back_apex), key=lambda point: point[0])
    add_attached_note(
        adapter,
        right,
        text=CROWN_NOTE,
        entity_xy=left_apex,
        note_xy=CROWN_NOTE_XY,
        label="crown callout",
        entity_type="VERTEX",
    )

    # The body is the journal both swing straps rock on (rule 5), so it alone
    # carries a roughness symbol, anchored on the body's flank in the side
    # view (a SILHOUETTE pick: a cylinder carries no model edge along its
    # side, as in draw_pivot_shaft). The Ra text renders ABOVE the arm (ASME
    # Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.045, SHAFT_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.045, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="pinion pivot bearing finish",
        entity_type="SILHOUETTE",
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.108)
    add_property_linked_note(adapter, "End View Note", 0.020, 0.140)
    # The iso's own scale label rides under it, above the title block's top
    # rule (0.064).
    add_property_linked_note(adapter, "Iso View Note", 0.325, 0.082)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Torque Shaft Manufacturing Drawing",
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

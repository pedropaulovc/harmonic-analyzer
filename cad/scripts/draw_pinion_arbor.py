r"""Create the curated machinist drawing for the alignment-pinion arbor.

The print is deliberately plain (cad/docs/drawing-simplicity-policy.md): a
plain bearing arbor carries no datums and no feature-control frames -- its
running fit is the band on the model diameter, plus one roughness symbol on
the OD that turns in the strap bores. The diameter, the shank length and the
Ra all read on the side view (policy rule 7: a turned part is dimensioned as
it sits in the lathe); the crowned back end is enlarged in DETAIL B, with a
compact adjacent note stating its spec-derived sagitta and spherical radius.
The true overall length is a conspicuous reference below the shank length
(machinist review 2026-09-02: the 226.25 read as the overall).
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
    create_detail_view,
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
from pinion_arbor_spec import (
    CAP_R,
    CAP_SAG,
    OVERALL_LEN,
    SHAFT_DIA,
    SHAFT_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_arbor"]
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
# The part spans z 0..OVERALL_LEN (shaft + crown), so the side view is
# OVERALL_LEN wide on the 1:1 sheet and its outline centre is the mid-span.
# The end circle and the side view retain enough room for the detail source
# circle around the crowned left end.
FRONT_CENTER = (0.055, 0.205)
RIGHT_CENTER = (
    FRONT_CENTER[0] + OVERALL_LEN * SHEET_SCALE[0] / 2000.0 + 0.060,
    FRONT_CENTER[1],
)
# 226-long arbor: a 1:1 isometric would run off the ASME B sheet, so 1:2.
# The empty band below the side view and right of the notes block takes it
# whole, clear of the length dimensions above it.
ISO_CENTER = (0.345, 0.145)

# Side-view landmark (sheet meters): the flat front end is at the RIGHT. The
# shaft's top flank is an 8-dia cylinder at 1:1, so its silhouette runs 4 mm
# above the view centre.
RIGHT_END_X = RIGHT_CENTER[0] + OVERALL_LEN * SHEET_SCALE[0] / 2000.0
SHAFT_FLANK_Y = RIGHT_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0

# DETAIL B (4:1): the crown, circled on the side view around its root and
# enlarged below-left.  At 4:1 the 8-dia crown is 32 mm tall and the 1.2
# sagitta reads as 4.8 mm.  The note sits beyond the 64 mm detail boundary
# rather than occupying the view's upper-right quadrant.
DETAIL_CENTER = (0.145, 0.130)
DETAIL_RADIUS = 0.008
DETAIL_SCALE = (4, 1)

# Marked dimensions by view. The crown's sketch dimension is unavailable from
# the derived detail, so DETAIL B carries a spec-derived geometry note instead
# of asking SolidWorks to import it. The end view keeps nothing and is never
# asked for model annotations.
RIGHT_KEEP = {
    "ShaftDia": (RIGHT_END_X + 0.024, RIGHT_CENTER[1]),
    "Depth": (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.020),
}
DIMENSION_CALLOUTS = {"Depth": "TO CROWN ROOT"}
CROWN_GEOMETRY_NOTE = f"DETAIL B CROWN\nSR{CAP_R:.2f}; {CAP_SAG:.2f} HIGH"
CROWN_GEOMETRY_NOTE_XY = (
    DETAIL_CENTER[0] + 0.045,
    DETAIL_CENTER[1] + 0.015,
)
OVERALL_NOTE = f"({OVERALL_LEN:.2f}) OVERALL REF"
OVERALL_NOTE_XY = (RIGHT_CENTER[0], RIGHT_CENTER[1] - 0.035)
# The diameter is the one fitted feature (SHAFT_H band on the model
# dimension): three decimals say "hold it".
DIMENSION_PRECISION = {"ShaftDia": 3}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-arbor source", await adapter.open_model(str(SOURCE)))
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
            0: "Pinion Arbor Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion arbor; zeroing-drum shaft; turned steel",
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

    # DETAIL B is centred on the actual projected crown root.  The common
    # detail helper converts this sheet point into parent-view sketch space;
    # pre-compensating that conversion shifted the detail's sampled model
    # region into the plain shaft and produced an empty detail.
    crown_root = model_point_in_view(
        adapter, right, (0.0, 0.0, SHAFT_LEN / 1000.0), label="crown root"
    )
    detail = create_detail_view(
        adapter,
        right,
        center=crown_root,
        radius=DETAIL_RADIUS,
        view_xy=DETAIL_CENTER,
        detail_label="B",
        scale=DETAIL_SCALE,
        label="crown detail",
    )
    set_hidden_lines_visible(adapter, detail)
    right_annotations = curate_view_dimensions(
        adapter, right, keep=RIGHT_KEEP, view_label="right"
    )
    set_dimension_callouts(adapter, right_annotations, DIMENSION_CALLOUTS)
    set_dimension_precision(adapter, right_annotations, DIMENSION_PRECISION)
    if add_note(adapter, CROWN_GEOMETRY_NOTE, *CROWN_GEOMETRY_NOTE_XY) is None:
        raise RuntimeError("failed to add crown geometry note")
    # SolidWorks classifies a solid circular end silhouette under the same
    # AutoInsertCenterMarks2 "hole" bit as a bored circle; disabling that bit
    # makes the API a guaranteed no-op even though the end view is circular.
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to arbor end view")

    # The true overall is reference information derived from the same
    # authoritative geometry contract as the model. A compact view-adjacent
    # note is deliberate: the shallow revolved crown apex is not a stable
    # selectable drawing vertex across SolidWorks seats.
    if add_note(adapter, OVERALL_NOTE, *OVERALL_NOTE_XY) is None:
        raise RuntimeError("failed to add pinion arbor overall reference note")

    # The bearing OD is the one running surface (the arbor turns in the strap
    # bores under the zeroing crank), so it alone carries a roughness symbol,
    # anchored on the shaft's flank in the side view (a SILHOUETTE pick: a
    # cylinder carries no model edge along its side). The Ra text renders
    # ABOVE the arm (ASME Y14.36), reaching y~0.236.
    add_surface_finish(
        adapter,
        right,
        edge_xy=(RIGHT_CENTER[0] + 0.050, SHAFT_FLANK_Y),
        symbol_xy=(RIGHT_CENTER[0] + 0.050, 0.222),
        control=surface_finish_by_key(SURFACE_FINISHES, "bearing"),
        label="arbor bearing finish",
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
        pdf_title="Pinion Arbor Manufacturing Drawing",
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

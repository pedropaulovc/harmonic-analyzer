r"""Create the drawing for MHA-DT-03-TL-08, the round arbor's backing collar.

Shop tooling (issue #2356; owner ruling 2026-11-20, Option 2). The keyed
arbor collar's member sheet (``draw_dt_cone_gear_tl_arbor_collar``) for one
collar, at 4:1 like the retired hub washer's sheet
(``a40cbf6124:cad/scripts/draw_ch_rocker_strap_tl_hub_washer.py``):
the END VIEW (``*Front``) keeps the drilled bore's callout; the outside
diameter (stock), which imports there too, moves onto the SIDE VIEW
(``*Right``) right of the collar, where a turned part's diameter reads beside
its length (rule 11); the length stands under the side view. The isometric
at 2:1 with its scale note.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_gear_tl_round_arbor_collar.py dt-cone-gear-tl-round-arbor-collar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
import dt_cone_gear_tl_round_arbor_collar_spec as spec
from _check import check
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_round_arbor_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)

SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = spec.ISOMETRIC_VIEW_SCALE
if tuple(ISO_SCALE) == VIEW_SCALE:
    raise AssertionError("the isometric's label would repeat the sheet scale")
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
END_CENTER = (0.070, 0.175)
SIDE_CENTER = (0.170, 0.175)
ISO_CENTER = (0.320, 0.175)
ISO_NOTE_XY = (0.290, 0.130)
HALF_OD = spec.OUTER_DIA / 2.0 * _S
HALF_LENGTH = spec.LENGTH / 2.0 * _S

# The bore keeps the end view, its callout up and right of the circles; the
# outside diameter is a donor there, parked below until it moves.
END_KEEP = {
    "BoreDia": (END_CENTER[0] + HALF_OD + 0.010, END_CENTER[1] + HALF_OD + 0.010),
    "OuterDia": (END_CENTER[0], END_CENTER[1] - HALF_OD - 0.012),
}
SIDE_KEEP = {
    "Length": (SIDE_CENTER[0], SIDE_CENTER[1] - HALF_OD - 0.014),
}
OD_ON_SIDE = (SIDE_CENTER[0] + HALF_LENGTH + 0.020, SIDE_CENTER[1])
if set(END_KEEP) | set(SIDE_KEEP) != set().union(*spec.DRAWING_DIMENSIONS.values()):
    raise AssertionError("the collar sheet does not place every marked dimension")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open round arbor collar source", adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity")
    read_required_properties(
        adapter.currentModel,
        ("Revision", "Title", *required, "Isometric View Note"),
        required=(*required, "Isometric View Note"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Round Cutting Arbor Collar Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: f"round arbor backing collar; low-carbon steel; {spec.PART_NUMBER}",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    end = place_view(adapter, str(SOURCE), "*Front", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Right", *SIDE_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A turned part needs no hidden lines (drawing-guidelines.md rule 9).
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="end",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="side",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    od_donors = [a for a in end_annotations if dimension_name(adapter, a) == "OuterDia"]
    if len(od_donors) != 1:
        raise RuntimeError("expected one OuterDia donor dimension on the end view")
    moved_od = move_model_dimension(
        adapter, od_donors[0], side, OD_ON_SIDE, source_view=end
    )
    annotations = [
        *(a for a in end_annotations if dimension_name(adapter, a) != "OuterDia"),
        *side_annotations,
        moved_od,
    ]
    assert_imported_precision(adapter, annotations, spec.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, dict(spec.CALLOUTS_BELOW))
    add_view_centerline(
        adapter,
        side,
        face_xy=(SIDE_CENTER[0], SIDE_CENTER[1] + HALF_OD / 2.0),
        label="round arbor collar axis centerline",
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Round Cutting Arbor Collar Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

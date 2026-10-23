r"""Create the manufacturing drawing for the magnifying-wheel drum (MHA-MG-10).

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_wheel_drum.py mg-wheel-drum
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _check import check
from _paths import CAD_ROOT
from _session import run_build
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
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from solidworks_mcp.adapters.solidworks.drawing import dimension_name
from _drawing_registry import DRAWINGS_BY_NAME
from mg_wheel_drum_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    DRUM_LEN,
    PRESS_CALLOUT,
    RECESS_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["mg_wheel_drum"]
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

# A Ø18.9 x 9 ring at 3:1: the face view, the side view and the isometric
# sit on one row midway between the top border and the title block (top at
# about 65 mm), with no general note left to anchor (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
FRONT_CENTER = (0.100, 0.155)
RIGHT_CENTER = (0.230, 0.155)
ISO_CENTER = (0.345, 0.155)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0

DRAWING_PRECISION_BY_NAME = {
    name: digits
    for names in DRAWING_PRECISION.values()
    for name, digits in names.items()
}

# Both diameters import on the face view, where every diameter line runs
# through the centre: two would cross there. The bore keeps the face view;
# the O.D. is a donor there and moves onto the side view, right of the ring.
# The bore's four-line callout stands up and right of the face view; the
# length's two-line callout hangs under the side view, above the title
# block, so the two text blocks never share a row.  The length's block is
# wider than the ring (run 14: its widest line printed 66.0 mm, centred on
# its point), so it stands LEFT of the side view's extension lines, which
# ran through it when it was centred between them.
_RECESS_BLOCK_HALF = 0.034
FRONT_KEEP = {
    "DrumOd": (0.060, 0.090),
    "DrumBore": (0.150, 0.228),
}
RIGHT_KEEP = {
    "DrumLen": (
        RIGHT_CENTER[0] - DRUM_LEN / 2.0 * _S - 0.004 - _RECESS_BLOCK_HALF,
        0.112,
    ),
}
OD_ON_SIDE = (RIGHT_CENTER[0] + DRUM_LEN / 2.0 * _S + 0.030, RIGHT_CENTER[1])
# Each band's need prints on its own callout (drawing-guidelines.md rule 7 (notes: few, flagged, never a method)).
DIMENSION_CALLOUTS = {
    "DrumBore": f"REAM THRU\n{PRESS_CALLOUT}",
    "DrumLen": RECESS_CALLOUT,
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-drum source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Magnifying Wheel Drum Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "magnifying wheel drum; turned brass",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="front",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    od_donors = [a for a in front_annotations if dimension_name(adapter, a) == "DrumOd"]
    if len(od_donors) != 1:
        raise RuntimeError("expected one drum O.D. donor dimension")
    moved_od = move_model_dimension(
        adapter, od_donors[0], right, OD_ON_SIDE, source_view=front
    )
    annotations = [
        *(a for a in front_annotations if dimension_name(adapter, a) != "DrumOd"),
        *right_annotations,
        moved_od,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    # The template centre-marks the bore as the view is placed; run 11's
    # explicit AutoInsertCenterMarks2 printed a second, identical mark (the
    # layout audit's duplicate-annotation finding).  The pressed bore takes
    # no roughness symbol (drawing-guidelines.md rule 6): it neither runs nor
    # slides, and the ream and the stated interference control the fit.

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Magnifying Wheel Drum Manufacturing Drawing",
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

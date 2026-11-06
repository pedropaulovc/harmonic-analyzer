r"""Create the manufacturing drawing for the oblique-trammel hub sleeve (MHA-CH-06-TL-34).

The face view carries the .4000 reamed bore with its REAM callout and mate;
the O.D. moves onto the side view with the matched length and its
acceptance (drawing-guidelines.md rules 4, 11 and 12).  Places and the
bore's band are authored on the part
(``ch_rocker_arm_tl_oblique_hub_sleeve_spec``).

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_rocker_arm_tl_oblique_hub_sleeve.py ch-rocker-arm-tl-oblique-hub-sleeve
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

import _telemetry
from _check import check
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
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from ch_rocker_arm_tl_oblique_hub_sleeve_spec import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH,
    OD,
    STEM,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_sleeve"]
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

# A Ø.580 x .24 sleeve at 3:1 (44 mm across, 18 mm long): the face view, the
# side view and the isometric on one row midway between the top border and
# the title block (the mg-wheel-axle-spacer sheet's layout), no general note.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
FRONT_CENTER = (0.090, 0.160)
RIGHT_CENTER = (0.215, 0.160)
ISO_CENTER = (0.340, 0.160)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0

# Both diameters import on the face view, where every diameter line runs
# through the centre: two would cross there.  The bore keeps the face view,
# its three-row callout up and right of it; the O.D. is a donor there and
# moves onto the side view, right of the sleeve.  The length and its
# two-row matched-fit callout hang under the side view.
FRONT_KEEP = {
    "SleeveOd": (0.050, 0.100),
    "SleeveBore": (0.135, 0.220),
}
RIGHT_KEEP = {
    "SleeveLength": (RIGHT_CENTER[0], RIGHT_CENTER[1] - OD / 2.0 * _S - 0.018),
}
OD_ON_SIDE = (RIGHT_CENTER[0] + LENGTH / 2.0 * _S + 0.030, RIGHT_CENTER[1])


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open hub sleeve source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Material Specification", "Finish", "Quantity"),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Oblique Trammel Hub Sleeve Manufacturing Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "hub sleeve; turned steel; reamed bore; matched length",
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
    od_donors = [a for a in front_annotations if dimension_name(adapter, a) == "SleeveOd"]
    if len(od_donors) != 1:
        raise RuntimeError("expected one hub sleeve O.D. donor dimension")
    moved_od = move_model_dimension(
        adapter, od_donors[0], right, OD_ON_SIDE, source_view=front
    )
    annotations = [
        *(a for a in front_annotations if dimension_name(adapter, a) != "SleeveOd"),
        *right_annotations,
        moved_od,
    ]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Oblique Trammel Hub Sleeve Manufacturing Drawing",
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

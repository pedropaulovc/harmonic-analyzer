r"""Create the curated manufacturing drawing for the crank pinion retention pin.

Recreated under ``cad/docs/drawing-guidelines.md``: a plain straight
pin is two native model dimensions -- its diameter and its length, both on
the side view where a turned part's diameter sits beside its axial extent
(drawing-guidelines.md rule 11 (turned parts read like the lathe)) -- an axis centerline, a bare end view, the isometric, and one note
saying where the stock may come from. No datums, no frames, no roughness
symbol, no band: the match-drilled hole it is driven into (crank_pinion_spec)
is the fit.
The decimal places are the PART's (``crank_pinion_pin_spec.DRAWING_PRECISION``,
applied natively by ``build_crank_pinion_pin``); this script only reads them
back off the sheet.

Drawn 8:1 -- a 1/8 x .56 pin is a matchstick on a B sheet at anything less.
The sheet prints decimal inch (the part's ``drawing_unit: in``); the rod's
diameter is its as-bought fraction, a reference.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
)

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
from _drawing_dimensions import assert_imported_precision
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _supplier_dimensions import supplier_reference_dimension
import _telemetry
from dt_crank_pinion_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
    PIN_DIA_CALLOUT,
    PIN_DIA_FRACTION_DENOMINATOR,
    PIN_LEN,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_crank_pinion_pin"]
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

SHEET_SCALE = (8.0, 1.0)
VIEW_SCALE = (8, 1)
FRONT_CENTER = (0.100, 0.150)  # end view: the one circle
RIGHT_CENTER = (0.230, 0.150)  # side view: the length, lying as it is cut
ISO_CENTER = (0.360, 0.150)

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0  # 0.0127
HALF_LEN = PIN_LEN * VIEW_SCALE[0] / 2000.0  # 0.054

# Side view (a *Right view lays model +Z to the left; a plain pin has no end
# to prefer): the diameter above the view, its dimension line left of centre
# so the axis-centerline pick at the view's middle lands on bare face; the
# length below. The diameter's two callout lines hang under its value, so the
# value stands a line higher than the length's offset.
RIGHT_KEEP = {
    "PinDia": (RIGHT_CENTER[0] - 0.030, RIGHT_CENTER[1] + HALF_DIA + 0.022),
    "PinLen": (RIGHT_CENTER[0], RIGHT_CENTER[1] - HALF_DIA - 0.016),
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open crank-pinion-pin source", await adapter.open_model(str(SOURCE)))
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
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
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
            0: "Crank Pinion Retention Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "crank pinion retention pin; straight pin; steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # A solid pin has nothing inside: hidden lines off everywhere (drawing-guidelines.md rule 9 (show internal shape in solid lines)).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The end view is a bare circle with its center mark: both of the pin's
    # dimensions live on the revolve's half-profile and import into the side
    # view only.
    right_annotations = curate_view_dimensions(
        adapter,
        right,
        keep=RIGHT_KEEP,
        view_label="right",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, right_annotations, DRAWING_PRECISION_BY_NAME)
    # The rod's as-bought diameter: a fraction reference, supplier tolerance.
    (pin_dia,) = (
        annotation
        for annotation in right_annotations
        if dimension_name(adapter, annotation) == "PinDia"
    )
    supplier_reference_dimension(
        adapter,
        pin_dia.GetSpecificAnnotation(),
        label="crank pinion pin rod diameter",
        units="in",
        precision=DRAWING_PRECISION_BY_NAME["PinDia"],
        expected_mm=PIN_DIA,
        presentation="diameter",
        fraction_denominator=PIN_DIA_FRACTION_DENOMINATOR,
        callout=PIN_DIA_CALLOUT,
    )
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin end view")
    # The side view is a rectangle: its axis centerline says which pair of
    # edges is the faced ends (drawing-guidelines.md rule 11 (turned parts read like the lathe), turned parts).
    add_view_centerline(
        adapter,
        right,
        face_xy=(RIGHT_CENTER[0], RIGHT_CENTER[1] + 0.004),
        label="crank pinion pin axis centerline",
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Crank Pinion Retention Pin Manufacturing Drawing",
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

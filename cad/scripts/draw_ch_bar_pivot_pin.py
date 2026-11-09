r"""Create the curated manufacturing drawing for the bar pivot pin (MHA-CH-11).

Under ``cad/docs/drawing-guidelines.md``: the pin the shop makes -- a 5/64
drill-rod cylinder cut to length, the part's default configuration (the
channel assembly places its INSTALLED configuration, pressed in and dressed
flush, and its step says so) -- on two native model dimensions, both on the
side view where a turned part's diameter sits beside its length
(drawing-guidelines.md rule 11 (turned parts read like the lathe)): the Ø as
the 5/64 stock fraction's REFERENCE (the drill rod's grind governs), its
callout naming both mates, and the cut length under the title block's band.
An axis centerline, a bare end view with its one center mark and the
isometric. No notes, no datums, no frames, no roughness symbol.
The decimal places are the PART's
(``ch_bar_pivot_pin_notes.DRAWING_PRECISION``, applied natively by
``build_ch_bar_pivot_pin``); this script reads them back off the sheet and
dresses the diameter as its stock fraction. Decimal-inch sheet (#290).

Drawn 10:1 -- a 5/64 x .30 pin is a speck on a B sheet at anything less.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_bar_pivot_pin.py ch-bar-pivot-pin
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
from _com import _early_bound
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
import _telemetry
from _supplier_dimensions import supplier_reference_dimension
from ch_bar_pivot_pin_notes import (
    DIAMETER_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA_FRACTION_DENOMINATOR,
)
from ch_bar_pivot_pin_spec import PIN_BLANK_LENGTH, PIN_DIA


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_bar_pivot_pin"]
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

SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
# Third-angle: the end view projects to the RIGHT of the side view and shares
# its Y station.
FRONT_CENTER = (0.110, 0.170)  # side view: the pin along its axis
RIGHT_CENTER = (0.220, FRONT_CENTER[1])  # end view: a bare circle
ISO_CENTER = (0.330, 0.170)

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0  # 0.0099
HALF_LEN = PIN_BLANK_LENGTH * VIEW_SCALE[0] / 2000.0  # 0.0381

# Side view: the diameter above the view, its text left of centre so the
# axis-centerline pick at the view's middle lands on bare face, high enough
# that its two-line callout hangs clear of the pin; the length below.
FRONT_KEEP = {
    "PinDia": (FRONT_CENTER[0] - 0.020, FRONT_CENTER[1] + HALF_DIA + 0.028),
    "PinLen": (FRONT_CENTER[0], FRONT_CENTER[1] - HALF_DIA - 0.018),
}
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


def _center_mark_count(view: Any) -> int:
    """The view's centre-mark annotations (a bare view answers None)."""
    return len(
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open bar-pivot-pin source", await adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit("ch-bar-pivot-pin"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Bar Pivot Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "bar pivot pin; cut drill rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # A solid pin has nothing inside: hidden lines off everywhere (drawing-guidelines.md rule 9 (show internal shape in solid lines)).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The diameter and the length live on the revolve's half-profile: the side
    # view carries both. The end view is a bare circle with its center mark.
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="pin side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    # The diameter is the as-bought drill rod: its native value prints as the
    # 5/64 stock fraction's REFERENCE (#290: supplier tolerance governs), both
    # mates below it (rule 4).
    diameters = [a for a in front_annotations if dimension_name(adapter, a) == "PinDia"]
    if len(diameters) != 1:
        raise RuntimeError("expected one pin PinDia dimension")
    supplier_reference_dimension(
        adapter,
        _early_bound(
            _early_bound(diameters[0], "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        ),
        label="pin PinDia",
        units="in",
        precision=DRAWING_PRECISION_BY_NAME["PinDia"],
        expected_mm=PIN_DIA,
        presentation="diameter",
        fraction_denominator=PIN_DIA_FRACTION_DENOMINATOR,
        callout=DIAMETER_CALLOUT,
    )
    # The template may centre-mark the circle as the view is placed: farm run
    # 20261023T185703445Z's layout audit found two identical marks on it
    # (duplicate-annotation, fleet issue #913) after the explicit call.  Mark
    # only a bare view, then prove the end carries exactly one.
    if _center_mark_count(right) == 0 and not auto_center_marks(
        adapter, right, holes=True, size=0.0025
    ):
        raise RuntimeError("failed to add ASME center mark to the pin end view")
    if (found := _center_mark_count(right)) != 1:
        raise RuntimeError(f"pin end view carries {found} centre marks, not one")
    add_view_centerline(
        adapter,
        front,
        face_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + HALF_DIA / 2.0),
        label="bar pivot pin axis centerline",
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Bar Pivot Pin Manufacturing Drawing",
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

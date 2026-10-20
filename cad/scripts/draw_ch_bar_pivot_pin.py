r"""Create the curated manufacturing drawing for the bar pivot pin (MHA-CH-11).

Under ``cad/docs/drawing-guidelines.md``: the INSTALLED pin -- a 5/64
drill-rod cylinder pressed into the amplitude bar's reamed top pin hole and
dressed flush with the bar's faces -- on three native model dimensions, all
on the side view where a turned part's diameter sits beside its length
(drawing-guidelines.md rule 11 (turned parts read like the lathe)): the Ø
with the drill rod's own grind band, its callout naming the stock and both
mates; the installed length as REFERENCE (the bar's width; the MHA-CH-01
stock owns it); and the blank's cut length with its band from the part's
blanked ``BlankReference`` sketch. An axis centerline, a bare end view with
its center mark, the isometric, and the one property-linked note. No datums,
no frames, no roughness symbol.
The decimal places and the band are the PART's
(``ch_bar_pivot_pin_notes.DRAWING_PRECISION``, applied natively by
``build_ch_bar_pivot_pin``); this script only reads them back off the sheet.

Drawn 10:1 -- a Ø1.98 x 6.35 pin is a speck on a B sheet at anything less.

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
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
import _drawing_hidden_sketches as hidden_sketches
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from ch_bar_pivot_pin_notes import (
    DIMENSION_CALLOUTS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    REFERENCE_DIMENSIONS,
)
from ch_bar_pivot_pin_spec import PIN_DIA, PIN_INSTALLED_LENGTH


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
NOTES_XY = (0.020, 0.085)  # left of the title block, below the views

# Printed half-sizes in sheet metres, which every dimension is placed clear of.
HALF_DIA = PIN_DIA * VIEW_SCALE[0] / 2000.0  # 0.0099
HALF_LEN = PIN_INSTALLED_LENGTH * VIEW_SCALE[0] / 2000.0  # 0.0318

# Side view: the diameter above the view, its text left of centre so the
# axis-centerline pick at the view's middle lands on bare face, high enough
# that its three-line callout hangs clear of the pin; the installed length
# below with its one-line callout, and the blank's cut length below that.
FRONT_KEEP = {
    "PinDia": (FRONT_CENTER[0] - 0.020, FRONT_CENTER[1] + HALF_DIA + 0.032),
    "PinLen": (FRONT_CENTER[0], FRONT_CENTER[1] - HALF_DIA - 0.016),
    "BlankLen": (FRONT_CENTER[0], FRONT_CENTER[1] - HALF_DIA - 0.036),
}
# The installed length's arrows stand inside its span (swDimensionArrowsSide_e
# swDimArrowsInside, read back as draw_mg_magnifying_wheel does): left to the
# document's smart arrows, r2 drew them outside, across the blank's extension
# lines 3.25 mm beyond each pin end.
ARROWS_INSIDE = ("PinLen",)
_DIM_ARROWS_INSIDE = 0


def _set_arrows_inside(adapter: Any, annotations: list[Any]) -> None:
    remaining = set(ARROWS_INSIDE)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        remaining.discard(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"pin {name} did not keep its arrows inside")
    if remaining:
        raise RuntimeError(
            f"no pin dimension to set arrows inside: {sorted(remaining)}"
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
            "Manufacturing Notes",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Bar Pivot Pin Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "bar pivot pin; installed state; pressed drill rod",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    # A solid pin has nothing inside: hidden lines off everywhere (drawing-guidelines.md rule 9 (show internal shape in solid lines)).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # The diameter and installed length live on the revolve's half-profile and
    # the blank length on a reference sketch the part saves hidden, all on the
    # Front plane: the side view curates through _drawing_hidden_sketches,
    # which shows that sketch in this view only. The end view is a bare
    # circle with its center mark.
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="pin side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    # Descriptive text only; every value and band is the model's.
    set_dimension_callouts(adapter, front_annotations, DIMENSION_CALLOUTS)
    # The installed length is the bar's width: a LINEAR reference. The plural
    # set_reference_dimensions forces a diameter glyph, printing "(Ø6.35)".
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in front_annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one pin {name} reference dimension")
        set_reference_dimension(adapter, matches[0], label=f"pin {name}")
    _set_arrows_inside(adapter, front_annotations)
    if not auto_center_marks(adapter, right, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center mark to the pin end view")
    add_view_centerline(
        adapter,
        front,
        face_xy=(FRONT_CENTER[0], FRONT_CENTER[1] + HALF_DIA / 2.0),
        label="bar pivot pin axis centerline",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

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

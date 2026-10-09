r"""Create the curated manufacturing drawing for the bar pivot pin (MHA-CH-011).

Under ``cad/docs/drawing-simplicity-policy.md``: the INSTALLED pin -- a 5/64
drill-rod cylinder pressed into the amplitude bar's reamed top pin hole and
dressed flush with the bar's faces -- on two native model dimensions, both on
the side view where a turned part's diameter sits beside its length (rule 7):
the Ø with the drill rod's own grind band, and the installed length as
REFERENCE (the bar's width; the MHA-CH-001 stock owns it). An axis
centerline, a bare end view with its center mark, the isometric, and the
property-linked notes (the blank's cut length, the press, the flush ends, the
running fit). No datums, no frames, no roughness symbol.
The decimal places and the band are the PART's
(``ch_bar_pivot_pin_spec.DRAWING_PRECISION``, applied natively by
``build_ch_bar_pivot_pin``); this script only reads them back off the sheet.

Drawn 10:1 -- a Ø1.98 x 6.35 pin is a speck on a B sheet at anything less.

Run with SolidWorks open::

    uv run python cad\scripts\draw_ch_bar_pivot_pin.py ch-bar-pivot-pin
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
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_hidden_lines_removed,
    set_reference_dimensions,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from ch_bar_pivot_pin_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    PIN_DIA,
    PIN_INSTALLED_LENGTH,
    REFERENCE_DIMENSIONS,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


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
# axis-centerline pick at the view's middle lands on bare face; the installed
# length below.
FRONT_KEEP = {
    "PinDia": (FRONT_CENTER[0] - 0.020, FRONT_CENTER[1] + HALF_DIA + 0.016),
    "PinLen": (FRONT_CENTER[0], FRONT_CENTER[1] - HALF_DIA - 0.016),
}


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
    # A solid pin has nothing inside: hidden lines off everywhere (rule 7).
    for view in (front, right, iso):
        set_hidden_lines_removed(adapter, view)

    # Both dimensions live on the revolve's half-profile and import into the
    # side view only; the end view is a bare circle with its center mark.
    front_annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="pin side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, front_annotations, DRAWING_PRECISION_BY_NAME)
    # The installed length is the bar's width: REFERENCE, keyed by name.
    set_reference_dimensions(adapter, front_annotations, REFERENCE_DIMENSIONS)
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

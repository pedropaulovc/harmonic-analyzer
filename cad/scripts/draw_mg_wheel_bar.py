r"""Create the curated machinist drawing for the magnifying-wheel bar.

A 10 x 9 steel bar, 234 long, carrying the wheel axle and the pen-hanger strap.
Four bores run along the depth (front-back), so the FRONT view (looking down the
bore axis) shows them as circles: the reamed axle bore, 2x #8 clamp-screw
clearance holes flanking the column and 1x #8 pen-hanger hole at the free end.
The bar length + section and the axle bore's Ø + station from the left end ride
the imported model marks; the depth is added across the right-view section;
the screw holes' sizes and stations ride the notes.

Run with SolidWorks open::

    uv run python cad\scripts\draw_mg_wheel_bar.py mg-wheel-bar
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

from _check import check
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from mg_wheel_bar_spec import (
    AXLE_BORE_X,
    BAR_DEPTH,
    BAR_LENGTH,
    BAR_SIDE,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
)
from mg_wheel_group import BACK_END_PROUD_MAX, BACK_END_SUNK_MAX, BAR_PRESS


SPEC = DRAWINGS_BY_NAME["mg_wheel_bar"]
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
FRONT_CENTER = (0.155, 0.175)
# The end view stands far enough right that the height's callout runs
# between it and the bar end.
RIGHT_CENTER = (0.340, 0.175)
ISO_CENTER = (0.320, 0.095)

_HALF_LEN = BAR_LENGTH * SHEET_SCALE[0] / 2000.0
LEFT_END = FRONT_CENTER[0] - _HALF_LEN
RIGHT_END = FRONT_CENTER[0] + _HALF_LEN
AXLE_BORE_SHEET_X = FRONT_CENTER[0] + AXLE_BORE_X * SHEET_SCALE[0] / 1000.0

FRONT_KEEP = {
    "Length": (FRONT_CENTER[0], FRONT_CENTER[1] - 0.030),
    # The bar height off the right end, in the open sheet between the bar and
    # the end view: off the left end its text sat on the border's zone
    # letter and frame line. The model dimension sits on the left end, so its
    # extension lines run the bar's whole length; the text stands above the
    # top one rather than between them.
    "Side": (RIGHT_END + 0.026, FRONT_CENTER[1] + 0.015),
    # The axle bore's station from the left end, above the bar; its reamed Ø
    # up and right of the bore, far enough right that the leader drops onto
    # the bore past the station's dimension line, the press lines standing
    # clear of the bar.
    "AxleBoreStation": ((LEFT_END + AXLE_BORE_SHEET_X) / 2.0, FRONT_CENTER[1] + 0.018),
    "AxleBoreDia": (AXLE_BORE_SHEET_X + 0.035, FRONT_CENTER[1] + 0.042),
}
# The bar depth (the extrude's banded model dimension) under the end view,
# its text right of the extension lines: the callout is wider than the 9.
RIGHT_KEEP = {
    "BarDepth": (
        RIGHT_CENTER[0] + BAR_DEPTH / 2000.0 + 0.034,
        RIGHT_CENTER[1] - BAR_SIDE / 2000.0 - 0.014,
    ),
}
# Each band states its need: the bore holds the pressed axle, the depth sets
# where the axle's back end lands, the height's top limit clears the tie wire.
DIMENSION_CALLOUTS = {
    "AxleBoreDia": (
        "REAM THRU\nPRESS FIT MG-WHEEL-AXLE\n"
        f"{BAR_PRESS[0]:.3f}-{BAR_PRESS[1]:.3f} INTERFERENCE"
    ),
    "BarDepth": (
        "MG-WHEEL-AXLE BACK END\n"
        f"{BACK_END_PROUD_MAX:.2f} PROUD TO {BACK_END_SUNK_MAX:.2f} SUNK"
    ),
    "Side": "CLEARS WHEEL TIE",
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-bar source", await adapter.open_model(str(SOURCE)))
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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Wheel Bar Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel bar; steel support bar; reamed axle bore; clearance holes",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(1, 1))
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 2))
    set_hidden_lines_removed(adapter, iso)
    # Front carries the hole circles; the end view's hidden bores only repeat
    # the THRU callouts, so it is drawn hidden-lines-removed.
    set_hidden_lines_visible(adapter, front)
    set_hidden_lines_removed(adapter, right)

    annotations = [
        *curate_view_dimensions(
            adapter,
            front,
            keep=FRONT_KEEP,
            view_label="front",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            right,
            keep=RIGHT_KEEP,
            view_label="right",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to wheel-bar bores")

    # The reamed axle bore carries its Ø and station from the left end
    # (FRONT_KEEP). The three screw bores show as circles with the ASME centre
    # marks above; their small clearance diameters + X-stations from the left
    # end are not dependable associative-callout picks at this 1:1 scale, so
    # they ride the notes (spec DRAWING_NOTES lists the sizes + stations).

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.125)
    # x <= 0.235 keeps the ~55 mm label fully left of the title-block keep-out
    # (x >= 0.264) -- the first run landed it 25.6 x 4.5 mm into the block.
    add_property_linked_note(adapter, "Isometric View Note", 0.180, 0.070)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Wheel Bar Manufacturing Drawing",
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

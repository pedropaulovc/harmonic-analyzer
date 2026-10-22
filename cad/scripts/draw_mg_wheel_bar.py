r"""Create the curated machinist drawing for the magnifying-wheel bar.

A 10 x 9 steel bar, 234 long, carrying the wheel axle and the pen-hanger strap.
Four bores run along the depth (front-back), so the FRONT view (looking down the
bore axis) shows them as circles: the reamed axle bore, 2x #8 clamp-screw
clearance holes flanking the column and 1x #8 pen-hanger hole at the free end.
The bar length + section, the axle bore's Ø + station from the left end, the
screw holes' stations from the left end and the bore row's height from the
bottom face ride the imported model marks (the row and its stations on the
part-hidden BoreRowReference sketch, shown in the front view); the depth is
added across the right-view section; the screw holes' sizes ride native
Hole Wizard callouts.

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
from _drawing_edges import scan_view_edges
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout
from _drawing_leader_notes import add_attached_note
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _column_clamp_interface import BAR_DEPTH
from mg_wheel_bar_spec import (
    AXLE_BORE_X,
    AXLE_ORIENTATION_CALLOUT,
    BAR_LENGTH,
    BAR_SIDE,
    BORE_MIN_WALL,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PEN_HANGER_HOLE_DIA,
    PEN_HANGER_MIN_END_WALL,
    SCREW_HOLE_X,
)
from mg_wheel_axle_spec import BACK_END_PROUD_MAX, BACK_END_SUNK_MAX
from mg_wheel_group import BAR_PRESS


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
# Label the actual +Z back-face edge in the Right view, clear of the front
# view's height callout. Keep orientation separate from the axle fit block.
AXLE_ORIENTATION_NOTE_XY = (RIGHT_CENTER[0] + 0.015, RIGHT_CENTER[1] + 0.055)

_HALF_LEN = BAR_LENGTH * SHEET_SCALE[0] / 2000.0
LEFT_END = FRONT_CENTER[0] - _HALF_LEN
RIGHT_END = FRONT_CENTER[0] + _HALF_LEN
AXLE_BORE_SHEET_X = FRONT_CENTER[0] + AXLE_BORE_X * SHEET_SCALE[0] / 1000.0
_BAR_BOTTOM = FRONT_CENTER[1] - BAR_SIDE * SHEET_SCALE[1] / 2000.0


def _sheet_x(model_x: float) -> float:
    return FRONT_CENTER[0] + model_x * SHEET_SCALE[0] / 1000.0


# Every station is a baseline dimension from the left end, stacked under the
# bar shortest first (8 mm rows, text y), the overall length outermost, so no
# dimension line crosses another's extension line. The rows stay below the bar
# because the hole callouts' leaders come down from above. The hanger's wall
# line prints under its value, so the next row stands 20 mm below it.
FRONT_KEEP = {
    # The hanger's 5 mm span is too short for its text: the value and its
    # wall need sit right of the hole's extension line, ending short of the
    # axle bore's extension line.
    "HangerStation": (LEFT_END + 0.030, _BAR_BOTTOM - 0.010),
    "AxleBoreStation": ((LEFT_END + AXLE_BORE_SHEET_X) / 2.0, _BAR_BOTTOM - 0.030),
    "ClampStation1": (LEFT_END + 0.082, _BAR_BOTTOM - 0.038),
    "ClampStation2": (LEFT_END + 0.152, _BAR_BOTTOM - 0.046),
    "Length": (FRONT_CENTER[0], _BAR_BOTTOM - 0.054),
    # The bar height off the right end, in the open sheet between the bar and
    # the end view: off the left end its text sat on the border's zone
    # letter and frame line. The model dimension sits on the left end, so its
    # extension lines run the bar's whole length; the text stands above the
    # top one rather than between them.
    # The row's height from the bottom face (its rise is on the right end)
    # pairs with it as a baseline: the shorter one nearer the bar, its text
    # dropped under the shared bottom line and 21 mm off the bar end, so its
    # block stays off the length's extension line; the height's line stands
    # outside the row's extension line.
    "Side": (RIGHT_END + 0.040, FRONT_CENTER[1] + 0.020),
    "BoreRowHeight": (RIGHT_END + 0.021, FRONT_CENTER[1] - 0.019),
    # The reamed Ø up and right of the bore. The two added mate/fit rows grow
    # upward at the native 5.6 mm pitch, retaining the old leader shoulder.
    "AxleBoreDia": (
        AXLE_BORE_SHEET_X + 0.035,
        FRONT_CENTER[1] + 0.042 + 0.0056,
    ),
}
# The bar depth (the extrude's banded model dimension) under the end view,
# its text right of the extension lines: the callout is wider than the 9.
RIGHT_KEEP = {
    "BarDepth": (
        RIGHT_CENTER[0] + BAR_DEPTH / 2000.0 + 0.034,
        RIGHT_CENTER[1] - BAR_SIDE / 2000.0 - 0.014,
    ),
}
# The native Hole Wizard callouts stand above the bar, the hanger's left of
# the reamed bore's Ø, the clamps' between that and the height's text.
HANGER_CALLOUT_XY = (_sheet_x(SCREW_HOLE_X) + 0.025, FRONT_CENTER[1] + 0.035)
CLAMP_CALLOUT_XY = (_sheet_x(CLAMP_HOLE_X[0]) + 0.010, FRONT_CENTER[1] + 0.035)
# Each band states its need: the bore holds the pressed axle, the depth sets
# where the axle's back end lands, the height's top limit clears the tie wire
# and its bottom limit, with the row's band, holds the bore walls; the hanger
# station's .XX holds its end wall.
DIMENSION_CALLOUTS = {
    "AxleBoreDia": (
        "REAM THRU\nPRESS FIT MG-WHEEL-AXLE\nMHA-MG-07\n"
        f"{BAR_PRESS[0]:.3f}-{BAR_PRESS[1]:.3f} DIAMETRAL\nINTERFERENCE"
    ),
    "BarDepth": (
        "MG-WHEEL-AXLE BACK END\n"
        f"{BACK_END_PROUD_MAX:.2f} PROUD TO {BACK_END_SUNK_MAX:.2f} SUNK"
    ),
    "Side": f"CLEARS WHEEL TIE\nFOR {BORE_MIN_WALL:.1f} BORE WALLS",
    "BoreRowHeight": f"ALL BORES\nFOR {BORE_MIN_WALL:.1f} WALLS",
    "HangerStation": f"FOR {PEN_HANGER_MIN_END_WALL:.1f} END WALL",
}
DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _hole_rims(front: Any) -> list[Any]:
    """The hanger hole's and the first clamp hole's rims, picked as entities:
    the front view looks onto the model's +Z (back) face."""
    edges = scan_view_edges(front, label="wheel-bar front")
    return [
        edges.circle_at(
            (x, 0.0, BAR_DEPTH / 2.0),
            dia / 2.0,
            axis=(0.0, 0.0, 1.0),
            label=label,
            radius_tol_mm=0.025,
        ).edge
        for x, dia, label in (
            (SCREW_HOLE_X, PEN_HANGER_HOLE_DIA, "pen-hanger hole rim"),
            (CLAMP_HOLE_X[0], CLAMP_HOLE_DIA, "first clamp hole rim"),
        )
    ]


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

    # The front view shows the part-hidden BoreRowReference sketch that owns
    # the row height and the screw-hole stations (_drawing_hidden_sketches).
    annotations = [
        *hidden_sketches.curate_view_dimensions(
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

    hanger_rim, clamp_rim = _hole_rims(front)
    for edge, callout_xy, label in (
        (hanger_rim, HANGER_CALLOUT_XY, "pen-hanger clearance hole"),
        (clamp_rim, CLAMP_CALLOUT_XY, "column-clamp clearance holes"),
    ):
        add_native_hole_callout(
            adapter,
            front,
            edge=edge,
            callout_xy=callout_xy,
            label=label,
            process="DRILL",
        )

    back_face_point_mm = (BAR_LENGTH / 2.0, 0.0, BAR_DEPTH / 2.0)
    back_face_edge = scan_view_edges(
        right, label="wheel-bar back-face edge"
    ).exact_line_through(
        back_face_point_mm, label="bar +Z back-face edge"
    ).edge
    add_attached_note(
        adapter,
        right,
        text=AXLE_ORIENTATION_CALLOUT,
        entity=back_face_edge,
        leader_attach_xy=model_point_in_view(
            adapter,
            right,
            tuple(value / 1000.0 for value in back_face_point_mm),
            label="bar +Z back-face edge",
        ),
        note_xy=AXLE_ORIENTATION_NOTE_XY,
        label="axle squareness to the bar back face",
    )

    # Under the length row, which sits 54 mm below the bar.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.105)
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

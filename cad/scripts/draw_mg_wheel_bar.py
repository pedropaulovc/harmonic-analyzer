r"""Create the curated machinist drawing for the magnifying-wheel bar.

A 10 x 9 steel bar, 234 long, carrying the wheel axle and the pen-hanger strap.
Four bores run along the depth (front-back), so the FRONT view (looking down the
bore axis) shows them as circles: the reamed axle bore, 2x #8 clamp-screw
clearance holes flanking the column and 1x #8 pen-hanger hole at the free end.
The bar length + section, the axle bore's Ø + station from the left end, the
screw holes' stations from the left end and the bore row's distance from the
top face ride the imported model marks (the row and its stations on the
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
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_edges import scan_view_edges
import _drawing_hidden_sketches as hidden_sketches
from _drawing_hole_callout import add_native_hole_callout
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from _column_clamp_interface import BAR_DEPTH
import mg_wheel_bar_callouts as callouts
from mg_wheel_bar_spec import (
    AXLE_BORE_X,
    BAR_LENGTH,
    BAR_SIDE,
    CLAMP_HOLE_DIA,
    CLAMP_HOLE_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    PEN_HANGER_HOLE_DIA,
    SCREW_HOLE_X,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


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
# The front view stands far enough right that the hanger row's drop, off the
# bar's left end, clears the frame.
FRONT_CENTER = (0.161, 0.175)
# The end view stands far enough right that the height's callout runs
# between it and the bar end.
RIGHT_CENTER = (0.340, 0.175)
ISO_CENTER = (0.320, 0.095)

_HALF_LEN = BAR_LENGTH * SHEET_SCALE[0] / 2000.0
LEFT_END = FRONT_CENTER[0] - _HALF_LEN
RIGHT_END = FRONT_CENTER[0] + _HALF_LEN
AXLE_BORE_SHEET_X = FRONT_CENTER[0] + AXLE_BORE_X * SHEET_SCALE[0] / 1000.0
# The view centres the bar's outline.
_BAR_BOTTOM = FRONT_CENTER[1] - BAR_SIDE * SHEET_SCALE[1] / 2000.0
_BAR_TOP = FRONT_CENTER[1] + BAR_SIDE * SHEET_SCALE[1] / 2000.0


def _sheet_x(model_x: float) -> float:
    return FRONT_CENTER[0] + model_x * SHEET_SCALE[0] / 1000.0


# Every station is a baseline dimension from the left end, stacked under the
# bar shortest first (8 mm rows, text y), the overall length outermost, so no
# dimension line crosses another's extension line. The rows stay below the bar
# because the hole callouts' leaders come down from above.
FRONT_KEEP = {
    # The hanger's 5 mm span is too short for its text: the value sits right
    # of the hole's extension line, ending short of the axle bore's extension
    # line.
    "HangerStation": (LEFT_END + 0.030, _BAR_BOTTOM - 0.010),
    "AxleBoreStation": ((LEFT_END + AXLE_BORE_SHEET_X) / 2.0, _BAR_BOTTOM - 0.030),
    "ClampStation1": (LEFT_END + 0.082, _BAR_BOTTOM - 0.038),
    "ClampStation2": (LEFT_END + 0.152, _BAR_BOTTOM - 0.046),
    "Length": (FRONT_CENTER[0], _BAR_BOTTOM - 0.054),
    # The bar height and the clamp row's drop from the top face off the right
    # end, in the open sheet between the bar and the end view: off the left
    # end the height's text sat on the border's zone letter and frame line.
    # Both share the top face's extension line: the shorter row nearer the
    # bar, its text (the band and its mate) above the top face; the height's
    # line outside it, its text under the bottom face.
    "Side": (RIGHT_END + 0.040, _BAR_BOTTOM - 0.014),
    "ClampRowFromTop": (RIGHT_END + 0.021, _BAR_TOP + 0.015),
    # The hanger and axle row's drop off the left end, its text above the top
    # face and left of the bar, clear of the hanger callout's leader.
    "BoreRowFromTop": (LEFT_END - 0.018, _BAR_TOP + 0.008),
    # The reamed Ø up and right of the bore, the press lines standing clear
    # of the bar.
    "AxleBoreDia": (AXLE_BORE_SHEET_X + 0.035, FRONT_CENTER[1] + 0.042),
}
# The bar depth (the extrude's banded model dimension) under the end view,
# its text right of the extension lines: the callout is wider than the 9.5.
RIGHT_KEEP = {
    "BarDepth": (
        RIGHT_CENTER[0] + BAR_DEPTH / 2000.0 + 0.034,
        RIGHT_CENTER[1] - BAR_SIDE / 2000.0 - 0.014,
    ),
}
# The native Hole Wizard callouts stand above the bar, the hanger's left of
# the reamed bore's Ø, the clamps' between that and the row's text.
HANGER_CALLOUT_XY = (_sheet_x(SCREW_HOLE_X) + 0.025, FRONT_CENTER[1] + 0.035)
CLAMP_CALLOUT_XY = (_sheet_x(CLAMP_HOLE_X[0]) + 0.010, FRONT_CENTER[1] + 0.035)
# Each band's mate prints under its value, authored on the part's dimension
# (mg_wheel_bar_callouts): the bore's press fit on the axle, the depth's
# axle back end, the row's MHA-SH-02 taps.
DRAWING_PRECISION_BY_NAME = {
    name: places
    for names in DRAWING_PRECISION.values()
    for name, places in names.items()
}


def _assert_part_authored_text(adapter: Any, annotations: list[Any]) -> None:
    """Every imported dimension prints the text lanes its part authored.

    The mates print nowhere else on the sheet, so a lost lane must fail the
    drawing.  Read-only: text set from the sheet would write through to the
    source part (#1942).
    """
    wanted = callouts.authored_by_name()
    displays: dict[str, list[Any]] = {name: [] for name in wanted}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in displays:
            displays[name].append(
                _early_bound(
                    _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                    "IDisplayDimension",
                )
            )
    counts = {name: len(found) for name, found in displays.items() if len(found) != 1}
    if counts:
        raise RuntimeError(f"authored dimensions not printed exactly once: {counts!r}")
    printed = {
        (name, lane): str(displays[name][0].GetText(lane) or "")
        for name, lanes in wanted.items()
        for lane in lanes
    }
    wrong = {
        key: text
        for key, text in printed.items()
        if callouts.callout_rows(text) != callouts.callout_rows(wanted[key[0]][key[1]])
    }
    if wrong:
        raise RuntimeError(
            f"imported dimension text differs from the part's: {wrong!r}"
        )


def _name_clamp_taps(display: Any) -> None:
    """Hang the back-arc taps the clamp holes locate to under their native
    callout (a drawing annotation, not an imported model dimension)."""
    display = _early_bound(display, "IDisplayDimension")
    display.SetText(callouts.CALLOUT_BELOW, callouts.CLAMP_HOLE_CALLOUT)
    applied = str(display.GetText(callouts.CALLOUT_BELOW) or "")
    if callouts.callout_rows(applied) != callouts.callout_rows(
        callouts.CLAMP_HOLE_CALLOUT
    ):
        raise RuntimeError(f"clamp-hole callout's taps did not persist: {applied!r}")


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
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
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
    # the row's drop from the top face and the screw-hole stations
    # (_drawing_hidden_sketches).
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
    _assert_part_authored_text(adapter, annotations)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to wheel-bar bores")

    hanger_rim, clamp_rim = _hole_rims(front)
    add_native_hole_callout(
        adapter,
        front,
        edge=hanger_rim,
        callout_xy=HANGER_CALLOUT_XY,
        label="pen-hanger clearance hole",
        process="DRILL",
    )
    _name_clamp_taps(
        add_native_hole_callout(
            adapter,
            front,
            edge=clamp_rim,
            callout_xy=CLAMP_CALLOUT_XY,
            label="column-clamp clearance holes",
            process="DRILL",
        )
    )

    # Beside the isometric, over its lower-right run (the view falls from
    # its upper-left end): clear of the title block below and of the depth's
    # callout above.
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.118)

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

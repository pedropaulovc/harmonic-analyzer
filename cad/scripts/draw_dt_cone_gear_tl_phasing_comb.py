r"""Manufacturing drawing of the cone tip gears' phasing comb (MHA-DT-03-TL-02).

One sheet. The front view draws the brass sheet's stepped edge as it lies
parallel to the cone's radial plane, south (T030) left, the gears' axis
below: every step's start from the sheet's south end, every blade's depth
from the T030 blade's edge (the seat line), all at the title block's bands.
The bottom view shows the stock's thickness; note 1 names the gear each blade
serves. A shaded isometric gives the picture.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_gear_tl_phasing_comb.py dt-cone-gear-tl-phasing-comb
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
)

import _telemetry
import dt_cone_gear_tl_phasing_comb_spec as part
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_phasing_comb"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 1.42 x .49 sheet whose shallowest step is .048: 5:1 keeps every step and
# the .020 stock legible.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
ISO_SCALE = (1, 1)
# The model origin (the sheet's south end on the seat line) on the sheet;
# the bottom view projects straight below.
FRONT_ORIGIN = (0.035, 0.215)
BOTTOM_CENTER_Y = 0.118
# The isometric and its label in the free upper right; the notes left of the
# title block.
ISO_CENTER = (0.372, 0.246)
ISO_NOTE_XY = (0.325, 0.227)
NOTES_XY = (0.020, 0.036)


def front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) on the front view."""
    return FRONT_ORIGIN[0] + x_mm * RATIO / 1000.0, FRONT_ORIGIN[
        1
    ] + y_mm * RATIO / 1000.0


_POINTS = part.profile_points_mm()
_SOUTH_X, _NORTH_X = _POINTS[0][0], _POINTS[-1][0]
_TOP_Y = part.SHEET_HEIGHT
_LOW_Y = min(y for _, y in _POINTS)
SHEET_BOX = (*front_xy(_SOUTH_X, _LOW_Y), *front_xy(_NORTH_X, _TOP_Y))

# --- Measured text (layout audit) ----------------------------------------------
# A dimension whose text stands outside its extension lines prints the text
# on one side of its dimension line, with the line at the text's edge: the
# depths and the thickness to the right of the line. Widths (sheet m): a
# three-place value 10 mm, a two-place value 7.6 mm; a capital 2.7 mm. A line
# of dimension text stands 5 mm in a block, which is centred on its keep
# point.
TEXT_GAP = 0.004
DEPTH_TEXT_WIDTH = 0.010
TWO_PLACE_TEXT_WIDTH = 0.0076
CHAR_WIDTH = 0.0027
LINE_HEIGHT = 0.005

# --- Front view dimension text (sheet m) ---------------------------------------
# The sheet's length over it; the step starts below it, one row each, from
# the south end, the shortest nearest. The heights stand in one baseline row
# right of the north end, shallowest first: the sheet's height has its text
# in its span, every depth below the seat has its text in one row under the
# sheet's deepest blade, each line TEXT_GAP right of the text before it, so
# no line runs through a text.
BASELINE_X0 = SHEET_BOX[2] + 0.008
DEPTH_TEXT_Y = SHEET_BOX[1] - 0.014
START_ROW_Y0 = SHEET_BOX[1] - 0.010
START_ROW_PITCH = 0.008


def front_keep() -> dict[str, tuple[float, float]]:
    keep: dict[str, tuple[float, float]] = {
        "SheetLength": ((SHEET_BOX[0] + SHEET_BOX[2]) / 2.0, SHEET_BOX[3] + 0.010),
        "SheetHeight": (BASELINE_X0, front_xy(0.0, part.SHEET_HEIGHT / 2.0)[1]),
    }
    for row, teeth in enumerate(part.BONDED_TEETH):
        south, _north = part.blade_x_mm(teeth)
        keep[part.blade_start_name(teeth)] = (
            front_xy((_SOUTH_X + south) / 2.0, 0.0)[0],
            START_ROW_Y0 - row * START_ROW_PITCH,
        )
    x = BASELINE_X0 + TEXT_GAP
    for teeth in part.BONDED_TEETH:
        keep[part.blade_depth_name(teeth)] = (x, DEPTH_TEXT_Y)
        x += DEPTH_TEXT_WIDTH + TEXT_GAP
    return keep


FRONT_KEEP = front_keep()

# --- Bottom view ---------------------------------------------------------------
# The stock's thickness across the edge view, right of the sheet's north end,
# its value and SHEET STOCK under it.
SHEET_THICK_X = SHEET_BOX[2] + 0.020
BOTTOM_KEEP = {"SheetThick": (SHEET_THICK_X, BOTTOM_CENTER_Y)}


def text_blocks() -> dict[str, tuple[float, float, float, float]]:
    """(left, bottom, right, top) of each dimension's text: its value's line
    and its callout's lines, a depth's or the thickness's run right of its
    line, the rest centred on it."""
    blocks = {}
    for name, (x, y) in (FRONT_KEEP | BOTTOM_KEEP).items():
        callout = part.CALLOUTS_BELOW.get(name, "").splitlines()
        places = part.DRAWING_PRECISION_BY_NAME[name]
        value = DEPTH_TEXT_WIDTH if places == 3 else TWO_PLACE_TEXT_WIDTH
        width = max([value, *(len(line) * CHAR_WIDTH for line in callout)])
        right_of_line = name in BOTTOM_KEEP or name.startswith("BladeDepth")
        left = x if right_of_line else x - width / 2.0
        half = (1 + len(callout)) * LINE_HEIGHT / 2.0
        blocks[name] = (left, y - half, left + width, y + half)
    return blocks


def sheet_dimension_names() -> set[str]:
    return set().union(*part.DRAWING_DIMENSIONS.values())


def _place_point(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    point = tuple(value / 1000.0 for value in point_mm)
    here = model_point_in_view(adapter, view, point, label=label)
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_point_in_view(adapter, view, point, label=label)
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: point sits at {here!r}, not {target!r}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source phasing comb missing: {SOURCE}")
    check("open phasing comb", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part.UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing,
        {
            0: "Cone Tip Gear Phasing Comb Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip gear phasing comb; brass sheet, one blade each, T030-T006; MHA-DT-03-TL-02",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_ORIGIN, scale=VIEW_SCALE)
    bottom = place_view(
        adapter,
        str(SOURCE),
        "*Bottom",
        FRONT_ORIGIN[0],
        BOTTOM_CENTER_Y,
        scale=VIEW_SCALE,
    )
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _place_point(adapter, front, (0.0, 0.0, 0.0), FRONT_ORIGIN, label="front view")
    # Projection-aligned below the front view, the sheet's mid-thickness on
    # BOTTOM_CENTER_Y.
    _place_point(
        adapter,
        bottom,
        (0.0, 0.0, part.SHEET_THICK / 2.0),
        (FRONT_ORIGIN[0], BOTTOM_CENTER_Y),
        label="bottom view",
    )
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    annotations: list[Any] = []
    for view, keep, label in (
        (front, FRONT_KEEP, "front view"),
        (bottom, BOTTOM_KEEP, "bottom view"),
    ):
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=part.DRAWING_DIMENSIONS,
        )
    printed = {dimension_name(adapter, annotation) for annotation in annotations}
    if printed != sheet_dimension_names():
        raise RuntimeError(
            f"sheet prints {sorted(printed)}, the part marks {sorted(sheet_dimension_names())}"
        )
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_BELOW)
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    drawing.ClearSelection2(True)
    _early_bound(drawing, "IDrawingDoc").EditSheet()
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    if add_note(adapter, part.SHEET_NOTES, *NOTES_XY) is None:
        raise RuntimeError("failed to add the phasing comb's numbered notes")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Gear Phasing Comb Drawing",
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

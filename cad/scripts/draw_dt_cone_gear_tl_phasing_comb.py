r"""Manufacturing drawing of the cone tip gears' phasing comb (MHA-DT-03-TL-02).

One sheet. The front view draws the plate's stepped edge as it lies in the
cone's radial plane, south (T030) left, the gears' axis below: every length
from the plate's south end, every height from the seat line, the T030 fork's
slot bottom (hidden lines show each slot running up to the seat line). The
bottom view shows each fork's slot, its width banded at the shop's slot row
with the gear it fits named at it (note 1), and the five slots' common
location from the plate's back face at the shop's milled-step row (5X). A
shaded isometric gives the picture.

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
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
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

# A 1.33 x .51 plate whose smallest slot is .034: 5:1 keeps the slots and
# the .010 T030 fork tip legible. Measured on the farm sheet (layout audit):
# dimension text is 3.5 mm high, about 2.6 mm a capital, a banded value with
# its stacked limits 25 mm wide centred on its dimension line.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
ISO_SCALE = (2, 1)
# The model origin (the T030 fork's north end on the seat line) on the
# sheet; the bottom view projects straight below. The T030 slot's callout
# block ends at the origin and runs 53 mm left: it stays 5 mm inside the
# border.
FRONT_ORIGIN = (0.072, 0.215)
BOTTOM_CENTER_Y = 0.105
# The isometric and its label in the free lower right, between the height
# texts and the title block; the notes under the bottom view's callouts, left
# of the title block.
ISO_CENTER = (0.345, 0.122)
ISO_NOTE_XY = (0.305, 0.096)
NOTES_XY = (0.020, 0.070)


def front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) on the front view."""
    return FRONT_ORIGIN[0] + x_mm * RATIO / 1000.0, FRONT_ORIGIN[
        1
    ] + y_mm * RATIO / 1000.0


_POINTS = part.profile_points_mm()
_SOUTH_X, _NORTH_X = _POINTS[0][0], _POINTS[-1][0]
_TOP_Y = part.PLATE_HEIGHT
_LOW_Y = min(y for _, y in _POINTS)
PLATE_BOX = (*front_xy(_SOUTH_X, _LOW_Y), *front_xy(_NORTH_X, _TOP_Y))

# --- Front view dimension text (sheet m) ---------------------------------------
# The plate's length over it; the fork starts below it, one row each, from
# the south end. The heights stand in one baseline row right of the north
# end, shallowest first; the plate's height has its text in its span, every
# depth below the seat has its text in one row under the plate's lowest
# fork, so no extension line runs through a text. Neighbouring texts stand
# their half-widths plus TEXT_GAP apart.
TEXT_GAP = 0.003
BANDED_HALF_WIDTH = 0.0125  # value and stacked limits, or SEE NOTE 1 under it
PLAIN_HALF_WIDTH = 0.0046  # a two-place value
BASELINE_X0 = PLATE_BOX[2] + 0.008
DEPTH_TEXT_Y = PLATE_BOX[1] - 0.014
START_ROW_Y0 = PLATE_BOX[1] - 0.010
START_ROW_PITCH = 0.008


def _heights() -> list[tuple[str, float]]:
    """(dimension, depth below the seat, mm; negative above) right of the
    plate: the plate's height first, then the depths shallowest first."""
    rows = [(f"Fork{part.gear_tag(t)}", part.FORK_TIP_DEPTH_MM[t]) for t in part.GEARS]
    rows += [
        (f"Step{part.gear_tag(t)}", part.STEP_DEPTH_MM[t])
        for t in part.BONDED_TEETH[:-1]
    ]
    return [("PlateHeight", -part.PLATE_HEIGHT), *sorted(rows, key=lambda row: row[1])]


def _half_width(name: str) -> float:
    return BANDED_HALF_WIDTH if name.startswith("Fork") else PLAIN_HALF_WIDTH


def front_keep() -> dict[str, tuple[float, float]]:
    keep: dict[str, tuple[float, float]] = {
        "PlateLength": ((PLATE_BOX[0] + PLATE_BOX[2]) / 2.0, PLATE_BOX[3] + 0.010),
        "FingerLength": (
            front_xy(_SOUTH_X / 2.0, 0.0)[0],
            front_xy(0.0, -part.FORK_TIP_DEPTH_MM[part.GEARS[0]])[1] - 0.008,
        ),
    }
    for row, teeth in enumerate(part.BONDED_TEETH):
        south, _north = part.finger_x_mm(teeth)
        keep[f"Start{part.gear_tag(teeth)}"] = (
            front_xy((_SOUTH_X + south) / 2.0, 0.0)[0],
            START_ROW_Y0 - row * START_ROW_PITCH,
        )
    x, previous = BASELINE_X0, None
    for name, depth in _heights():
        if previous is not None:
            x += _half_width(previous) + TEXT_GAP + _half_width(name)
        y = front_xy(0.0, -depth / 2.0)[1] if depth < 0.0 else DEPTH_TEXT_Y
        keep[name] = (x, y)
        previous = name
    return keep


FRONT_KEEP = front_keep()

# --- Bottom view ---------------------------------------------------------------
# A narrow vertical dimension prints its text left of its dimension line,
# ending there, on a leader shelf (farm layout audit). Each slot's width has
# its line just inside its fork's north end, its block in one of two rows,
# over and under the plate's edge view, so blocks in a row stand a fork apart
# and no leader crosses another block. The slots' common location (5X) prints
# over the edge view right of the plate, the thickness under it farther right.
SLOT_LINE_INSET = 0.002
ROW_OFFSET = 0.0185
OVER_Y = BOTTOM_CENTER_Y + ROW_OFFSET
UNDER_Y = BOTTOM_CENTER_Y - ROW_OFFSET
SLOT_FACE_X = PLATE_BOX[2] + 0.018
PLATE_THICK_X = PLATE_BOX[2] + 0.053


def bottom_keep() -> dict[str, tuple[float, float]]:
    keep = {
        part.SLOT_FACE_PRINTED: (SLOT_FACE_X, OVER_Y),
        "PlateThick": (PLATE_THICK_X, UNDER_Y),
    }
    for index, teeth in enumerate(part.GEARS):
        _south, north = part.finger_x_mm(teeth)
        keep[part.slot_width_name(teeth)] = (
            front_xy(north, 0.0)[0] - SLOT_LINE_INSET,
            UNDER_Y if index % 2 == 0 else OVER_Y,
        )
    return keep


BOTTOM_KEEP = bottom_keep()


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
            3: "cone tip gear phasing comb; T030-T006 forks; MHA-DT-03-TL-02",
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
    # Projection-aligned below the front view, the plate's mid-thickness on
    # BOTTOM_CENTER_Y.
    _place_point(
        adapter,
        bottom,
        (0.0, 0.0, part.THICKNESS / 2.0),
        (FRONT_ORIGIN[0], BOTTOM_CENTER_Y),
        label="bottom view",
    )
    # The slots' bottoms are hidden in the front view; it shows them dashed.
    set_hidden_lines_visible(adapter, front)
    for view in (bottom, iso):
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
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_BELOW)
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    set_hidden_lines_visible(adapter, front)
    for view in (bottom, iso):
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

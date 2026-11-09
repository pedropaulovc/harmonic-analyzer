r"""Manufacturing drawing of the cone tip gears' phasing comb (MHA-DT-03-TL-02).

One sheet. The front view draws the plate's stepped edge as it lies in the
cone's radial plane, south (T030) left, the gears' axis below: every length
from the plate's south end, every height from the seat line, the T030 fork's
slot bottom (hidden lines show each slot's bottom; T030..T012's run on at
their step). The bottom view shows each fork's slot, its width banded at
the shop's slot row with the gear it fits named at it (note 1), and the four
bonded slots' centre planes located to T030's (datum A) at the shop's
milled-step row. A shaded isometric gives the picture.

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
from dt_cone_gear_tl_phasing_comb_spec import GEOMETRIC_TOLERANCES_IN
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
from _drawing_gdt import add_datum_feature, add_feature_control_frame
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

# A 1.33 x .50 plate whose smallest slot is .034: 5:1 keeps the slots and
# the .010 T030 fork tip legible and the plate inside the left half.
SHEET_SCALE = (5.0, 1.0)
VIEW_SCALE = (5, 1)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
ISO_SCALE = (1, 1)
# The model origin (the T030 fork's north end on the seat line) on the
# sheet; the bottom view projects straight below.
FRONT_ORIGIN = (0.075, 0.200)
BOTTOM_CENTER_Y = 0.095
ISO_CENTER = (0.390, 0.232)
ISO_NOTE_XY = (0.365, 0.205)
NOTES_XY = (0.235, 0.122)


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
# the south end; the heights in one baseline row right of the north end,
# shallowest first, each text at its span's middle.
BASELINE_X0 = PLATE_BOX[2] + 0.014
BASELINE_PITCH = 0.013
START_ROW_Y0 = PLATE_BOX[1] - 0.010
START_ROW_PITCH = 0.008


def _heights() -> list[tuple[str, float]]:
    """(dimension, depth below the seat, mm; negative above) right of the plate."""
    rows = [("PlateHeight", -part.PLATE_HEIGHT)]
    rows += [(f"Fork{part.gear_tag(t)}", part.FORK_TIP_DEPTH_MM[t]) for t in part.GEARS]
    rows += [
        (f"Step{part.gear_tag(t)}", part.STEP_DEPTH_MM[t])
        for t in part.BONDED_TEETH[:-1]
    ]
    rows.append(("SlotBottomT006", part.SLOT_BOTTOM_DEPTH_MM[6]))
    return sorted(rows, key=lambda row: abs(row[1]))


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
    for column, (name, depth) in enumerate(_heights()):
        keep[name] = (
            BASELINE_X0 + column * BASELINE_PITCH,
            front_xy(0.0, -depth / 2.0)[1],
        )
    return keep


FRONT_KEEP = front_keep()

# --- Bottom view ---------------------------------------------------------------
# Each slot's banded width under its fork, the callouts in two rows so the
# neighbours' blocks stand apart; the plate's thickness off its north end.
SLOT_ROW_Y = (BOTTOM_CENTER_Y - 0.020, BOTTOM_CENTER_Y - 0.045)


def bottom_keep() -> dict[str, tuple[float, float]]:
    keep = {"PlateThick": (PLATE_BOX[2] + 0.014, BOTTOM_CENTER_Y)}
    for index, teeth in enumerate(part.GEARS):
        south, north = part.finger_x_mm(teeth)
        keep[part.slot_width_name(teeth)] = (
            front_xy((south + north) / 2.0, 0.0)[0],
            SLOT_ROW_Y[index % 2],
        )
    return keep


BOTTOM_KEEP = bottom_keep()
# Datum A on T030's slot; the bonded slots' frame over the bottom view, left
# of the title block.
DATUM_XY = (PLATE_BOX[0] - 0.012, BOTTOM_CENTER_Y + 0.018)
POSITION_FRAME_XY = (front_xy(part.finger_x_mm(24)[0], 0.0)[0], BOTTOM_CENTER_Y + 0.020)


def sheet_dimension_names() -> set[str]:
    return set().union(*part.DRAWING_DIMENSIONS.values())


def _place_origin(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move ``view`` so the model origin lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - origin[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    origin = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=label)
    if math.dist(origin, target) > 1e-4:
        raise RuntimeError(f"{label}: origin sits at {origin!r}, not {target!r}")


def _slot_edge_xy(adapter: Any, view: Any, teeth: int) -> tuple[float, float]:
    """Sheet point on ``teeth``'s slot's +Z wall where the bottom view shows it
    (the fork's mid-length, on its tip face)."""
    south, north = part.finger_x_mm(teeth)
    return model_point_in_view(
        adapter,
        view,
        (
            (south + north) / 2000.0,
            -part.FORK_TIP_DEPTH_MM[teeth] / 1000.0,
            part.SLOT_WIDTH_MM[teeth] / 2000.0,
        ),
        label=f"{part.gear_tag(teeth)} slot wall",
    )


@_telemetry.traced("drawing.phasing_comb_slot_position")
def _position_slots(adapter: Any, view: Any) -> None:
    """Datum A on T030's slot; the bonded slots' centre planes to it."""
    add_datum_feature(
        adapter,
        view,
        edge_xy=_slot_edge_xy(adapter, view, part.REFERENCE_TEETH),
        symbol_xy=DATUM_XY,
        datum=part.SLOT_DATUM,
        label="T030 slot datum",
    )
    add_feature_control_frame(
        adapter,
        view,
        edge_xy=_slot_edge_xy(adapter, view, part.BONDED_TEETH[0]),
        frame_xy=POSITION_FRAME_XY,
        characteristic="position",
        tolerance=GEOMETRIC_TOLERANCES_IN["slot position"],
        datums=(part.SLOT_DATUM,),
        quantity=f"{len(part.BONDED_TEETH)}X",
        label="bonded slot position",
    )


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
    _place_origin(adapter, front, FRONT_ORIGIN, label="front view")
    # Projection-aligned below the front view.
    bottom_origin = model_point_in_view(
        adapter, bottom, (0.0, 0.0, 0.0), label="bottom view"
    )
    _place_origin(
        adapter, bottom, (FRONT_ORIGIN[0], bottom_origin[1]), label="bottom view"
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
    _position_slots(adapter, bottom)
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

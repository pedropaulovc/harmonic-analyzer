r"""Manufacturing drawing of the DT6-FORM1 fly-cutter bit (MHA-DT-37-TL-01).

Issue #2358: the T006 form tool drawn as a tool.  One sheet at 10:1: the face
(top) view with MHA-DT-37 sheet 2's envelope widths as references, the front
view with the rod, its length, the flat to centre and the front clearance, the
end (right) view with the side clearance, and the isometric.  The form itself
is MHA-DT-37 sheet 2's table (note 1); every number here is the part's own
(``dt_cone_tip_gear_tl_form_cutter_spec``), imported from the model.
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
import dt_cone_tip_gear_tl_form_cutter_spec as part
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
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _session import run_build

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_tip_gear_tl_form_cutter"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A Ø.125 x .45 rod whose tip is .011 wide: 10:1 prints the tip 2.9 mm and
# the whole bit 114 mm long.
SHEET_SCALE = (10.0, 1.0)
VIEW_SCALE = (10, 1)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
ISO_SCALE = (5, 1)
# P1 (the model origin) on each orthographic view: the front view right of
# centre with its 114 mm run to the left, the face view projected above it,
# the end view projected right of it; the isometric and the notes in the free
# left column, the notes above the title block's left edge.
FRONT_P1 = (0.300, 0.150)
TOP_P1 = (FRONT_P1[0], 0.215)
RIGHT_AXIS = (0.360, FRONT_P1[1])
ISO_CENTER = (0.095, 0.220)
ISO_NOTE_XY = (0.060, 0.185)
NOTES_XY = (0.020, 0.060)

_R = part.BIT_RADIUS
_S = RATIO / 1000.0


def front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) on the front view."""
    return FRONT_P1[0] + x_mm * _S, FRONT_P1[1] + y_mm * _S


def top_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, z) on the face (top) view, +Z down."""
    return TOP_P1[0] + x_mm * _S, TOP_P1[1] - z_mm * _S


# --- Front view: the rod's length under it; its Ø far enough left of the
# shank end that the three-line callout stays clear of the outline; the flat's
# length with its text left of both extension lines (between them the lines
# ran up through FLAT TO CENTER LINE, farm run 20261113T012650242Z); the front
# clearance low and right of the plumb line, under the end view's side
# clearance arc, whose extension line crossed it at 3.5 mm.
FRONT_KEEP = {
    "BitLength": front_xy(-part.BIT_LENGTH / 2.0, -_R - 1.2),
    "BitDia": front_xy(-part.BIT_LENGTH - 4.5, 0.0),
    "FlatLength": front_xy(-part.FLAT_LENGTH - 2.8, _R + 1.2),
    "FrontClearance": front_xy(3.0, -_R - 4.5),
}
# --- Face view: the three widths right of the tip, one column each a
# reference's text width apart (at 1 mm pitch the same run printed them over
# one another).  The tip width's text hangs below the form's widest extension
# line (between its own lines, 2.9 mm apart on the sheet, they struck it).
# The two stations from P1 stand above the view, one row each, their texts
# right of P1 outside every extension line (the longer one's lines cross the
# shorter one's row left of P1).
WIDTH_PITCH_MM = 2.5
_DEPTH_TEXT_X = 1.2
TOP_KEEP = {
    "TipWidth": top_xy(WIDTH_PITCH_MM, part.FORM_WIDTH / 2.0 + 0.6),
    "JunctionWidth": top_xy(2.0 * WIDTH_PITCH_MM, 0.0),
    "FormWidth": top_xy(3.0 * WIDTH_PITCH_MM, 0.0),
    "JunctionDepth": top_xy(_DEPTH_TEXT_X, -_R - 0.9),
    "FormDepth": top_xy(_DEPTH_TEXT_X, -_R - 2.0),
}
# --- End view: the side clearance right of and below the rod, its text clear
# of the circle (the run printed SIDE touching it).
RIGHT_KEEP = {
    "SideClearance": (
        RIGHT_AXIS[0] + (_R + 1.6) * _S,
        RIGHT_AXIS[1] - (_R + 0.3) * _S,
    ),
}


def sheet_dimension_names() -> set[str]:
    return set().union(*part.DRAWING_DIMENSIONS.values())


if {*FRONT_KEEP, *TOP_KEEP, *RIGHT_KEEP} != sheet_dimension_names():
    raise AssertionError("every marked bit dimension prints once, in one view")


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
        raise FileNotFoundError(f"source fly-cutter bit missing: {SOURCE}")
    check("open fly-cutter bit", await adapter.open_model(str(SOURCE)))
    required = ("Number", "Material Specification", "Finish", "Quantity")
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
            0: "Cone Tip Gear Fly Cutter Bit Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "DT6-FORM1 single-point form bit for the T006 tooth spaces; MHA-DT-37-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_P1, scale=VIEW_SCALE)
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_P1, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_AXIS, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    origin = (0.0, 0.0, 0.0)
    _place_point(adapter, front, origin, FRONT_P1, label="front view")
    _place_point(adapter, top, origin, TOP_P1, label="face view")
    _place_point(adapter, right, origin, RIGHT_AXIS, label="end view")
    for view in (front, top, right):
        set_hidden_lines_removed(adapter, view)

    annotations: list[Any] = []
    for view, keep, label in (
        (front, FRONT_KEEP, "front view"),
        (top, TOP_KEEP, "face view"),
        (right, RIGHT_KEEP, "end view"),
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
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, part.DIMENSION_CALLOUTS)
    # MHA-DT-37 sheet 2's table governs the form; its envelope prints here as
    # references only.
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in part.REFERENCE_DIMENSIONS:
            set_reference_dimension(adapter, annotation, label=f"form envelope {name}")
    for view in (front, top, right):
        set_hidden_lines_removed(adapter, view)

    drawing.ClearSelection2(True)
    _early_bound(drawing, "IDrawingDoc").EditSheet()
    for text, xy, label in (
        (part.SHEET_NOTES, NOTES_XY, "numbered notes"),
        (part.ISOMETRIC_VIEW_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        if add_note(adapter, text, *xy) is None:
            raise RuntimeError(f"failed to add the fly-cutter bit's {label}")
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Gear Fly Cutter Bit Drawing",
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

r"""Create the curated machinist drawing for the platen plate (MHA-PD-002).

The platen is a 269.64 x 134.82 brass plate, 3.85 thick, with four Ø7 bosses
standing proud of its back face round the #2-56 clip-screw through taps and
ten counterbored #4 loose through holes for the guide screws.  The sheet runs
at 1:2: the front view carries the outline and every hole coordinate from the
plate's bottom-left corner, a back view the bosses, an enlarged 1:1 right view
the thickness and the boss height, and a 1:4 isometric the form.

Every printed dimension is an associative model dimension whose places the
part authors (``pd_platen_spec.DRAWING_PRECISION``); the hole sizes ship as
native Hole Wizard callouts.

Run (SolidWorks already open)::

    uv run python cad\scripts\draw_pd_platen.py pd-platen
"""

from __future__ import annotations

import argparse
import math
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
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _hole_spec import blind_cut_dia_mm
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from pd_platen_spec import (
    CBORE_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    GUIDE_CALLOUT_PRECISION,
    GUIDE_HOLE_X,
    GUIDE_HOLE_Y,
    PLATE_HEIGHT,
    PLATE_THICKNESS,
    PLATE_WIDTH,
    SOCKET_BOSS_H,
    SOCKET_SPEC,
    SOCKET_XY,
)


SPEC = DRAWINGS_BY_NAME["pd_platen"]
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

SHEET_SCALE = (1.0, 2.0)
VIEW_SCALE = (1, 2)
RIGHT_SCALE = (1, 1)
ISO_SCALE = (1, 4)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet m per model mm, 1:2
_RIGHT_S = 1.0 / 1000.0  # enlarged right view, 1:1

# Sheet layout (meters; the B-size field is x 0.0127..0.4191, y 0.0127..0.2667
# and the title block holds x >= 0.216, y <= 0.066).  The front view's hole
# coordinates stack below it (smallest nearest) and at its sides; the back
# view sits below that stack, left of the title block; the enlarged right view
# and the isometric stand right of the front view.
FRONT_CENTER = (0.140, 0.190)
BACK_CENTER = (0.140, 0.058)
RIGHT_CENTER = (0.300, 0.175)
ISO_CENTER = (0.370, 0.190)
ISO_NOTE_XY = (0.338, 0.150)
RIGHT_NOTE_XY = (0.262, 0.100)
BACK_NOTE_XY = (0.020, 0.064)
# The right view's bbox spans the plate and the bosses behind it (model Z).
_DEPTH_SPAN = PLATE_THICKNESS + SOCKET_BOSS_H


def _front_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the front view (bbox-centred)."""
    return FRONT_CENTER[0] + (model_x_mm - PLATE_WIDTH / 2.0) * _S


def _front_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the front view (bbox-centred)."""
    return FRONT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _S


def _back_x(model_x_mm: float) -> float:
    """Sheet X of a model-X point in the back view (seen from -Z: mirrored)."""
    return BACK_CENTER[0] - (model_x_mm - PLATE_WIDTH / 2.0) * _S


def _back_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the back view."""
    return BACK_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _S


def _right_x(model_z_mm: float) -> float:
    """Sheet X of a model-Z point in the right view (seen from +X: -Z right)."""
    return RIGHT_CENTER[0] - (model_z_mm - _DEPTH_SPAN / 2.0) * _RIGHT_S


def _right_y(model_y_mm: float) -> float:
    """Sheet Y of a model-Y point in the enlarged right view."""
    return RIGHT_CENTER[1] + (model_y_mm - PLATE_HEIGHT / 2.0) * _RIGHT_S


LEFT_EDGE_X = _front_x(0.0)
RIGHT_EDGE_X = _front_x(PLATE_WIDTH)
BOTTOM_EDGE_Y = _front_y(0.0)
TOP_EDGE_Y = _front_y(PLATE_HEIGHT)
_SOCKET_LEFT_X, _SOCKET_RIGHT_X = sorted({x for x, _ in SOCKET_XY})
_SOCKET_LOW_Y, _SOCKET_HIGH_Y = sorted({y for _, y in SOCKET_XY})

# Per-view survivors of the marked-dimension import: parametric name -> sheet
# position.  Below the front view the X coordinates stack from the corner,
# smallest nearest: the left sockets' 5.393 and the first guide hole's 26.964
# print outboard of the plate's left edge (their spans are narrower than the
# text), the rest mid-span, the overall width outermost.  The guide rows' Y
# coordinates stand left of the plate, each value on its own line clear of the
# other's; the sockets' Y coordinates and the height stand right of it.  The
# enlarged right view carries the plate's thickness above it and the boss
# height beside the upper boss; the back view the boss Ø.
FRONT_KEEP = {
    "Socket3X": (0.058, 0.150),
    "Guide1X": (0.058, 0.143),
    "Guide2X": (_front_x(GUIDE_HOLE_X[1] / 2.0), 0.136),
    "Guide3X": (_front_x(GUIDE_HOLE_X[2] / 2.0), 0.129),
    "Guide4X": (_front_x(GUIDE_HOLE_X[3] / 2.0), 0.122),
    "Guide5X": (_front_x(GUIDE_HOLE_X[4] / 2.0), 0.115),
    "Socket1X": (_front_x(_SOCKET_RIGHT_X / 2.0), 0.108),
    "Width": (FRONT_CENTER[0], 0.101),
    "Guide1Y": (0.058, _front_y(GUIDE_HOLE_Y[0] / 2.0)),
    "Guide6Y": (0.030, _front_y(GUIDE_HOLE_Y[1] / 2.0)),
    "Socket1Y": (0.222, _front_y(_SOCKET_LOW_Y / 2.0)),
    "Socket2Y": (0.250, _front_y(_SOCKET_HIGH_Y * 0.68)),
    "Height": (0.272, FRONT_CENTER[1]),
}
RIGHT_KEEP = {
    "Depth": (_right_x(PLATE_THICKNESS / 2.0), 0.251),
    "BossH": (0.284, _right_y(_SOCKET_HIGH_Y)),
}
BACK_KEEP = {"Boss1Dia": (0.240, 0.082)}
# One printed coordinate stands for every hole on its station: 5X per guide
# row and column pair, 2X per socket station.  A custom prefix replaces
# SolidWorks' own diameter symbol, so the boss's carries it.
DIMENSION_PREFIXES = {
    "Socket1X": "2X ",
    "Socket3X": "2X ",
    "Socket1Y": "2X ",
    "Socket2Y": "2X ",
    "Guide1X": "2X ",
    "Guide2X": "2X ",
    "Guide3X": "2X ",
    "Guide4X": "2X ",
    "Guide5X": "2X ",
    "Guide1Y": "5X ",
    "Guide6Y": "5X ",
    "Boss1Dia": "4X Ø",
}

# The guide-hole callout rides the top row's first hole, its leader up-left
# over the plate's left edge to text above the plate's top-left corner; the
# socket callout rides the upper right socket, its leader up-right to text
# above the plate's top-right corner.  Each pick lies on the hole's own rim
# (counterbore Ø, tap drill Ø) on the side the leader leaves.
_GUIDE_PICK_HOLE = (GUIDE_HOLE_X[0], GUIDE_HOLE_Y[1])
_DIAG = math.sqrt(0.5)
GUIDE_EDGE_XY = (
    _front_x(_GUIDE_PICK_HOLE[0]) - CBORE_DIA / 2.0 * _S * _DIAG,
    _front_y(_GUIDE_PICK_HOLE[1]) + CBORE_DIA / 2.0 * _S * _DIAG,
)
GUIDE_CALLOUT_XY = (0.060, 0.245)
GUIDE_CALLOUT_PROCESS = "DRILL"
SOCKET_DRILL_R_SHEET = blind_cut_dia_mm(SOCKET_SPEC) / 2.0 * _S
SOCKET_EDGE_XY = (
    _front_x(_SOCKET_RIGHT_X) + SOCKET_DRILL_R_SHEET * _DIAG,
    _front_y(_SOCKET_HIGH_Y) + SOCKET_DRILL_R_SHEET * _DIAG,
)
SOCKET_CALLOUT_XY = (0.250, 0.252)
SOCKET_CALLOUT_PROCESS = "TAP"

_VIEW_KEEPS = {"front": FRONT_KEEP, "right": RIGHT_KEEP, "back": BACK_KEEP}
if set().union(*_VIEW_KEEPS.values()) != set().union(*DRAWING_DIMENSIONS.values()):
    raise AssertionError("the platen views must keep exactly the marked dimensions")


def _set_dimension_prefixes(
    adapter: Any, annotations: list[Any], prefixes: dict[str, str]
) -> None:
    """Write a native prefix on named imported dimensions and read it back."""
    remaining = dict(prefixes)
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        prefix = remaining.pop(dimension_name(adapter, annotation), None)
        if prefix is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.SetText(1, prefix)  # swDimensionTextPrefix
        if str(display.GetText(1) or "") != prefix:
            raise RuntimeError(f"dimension prefix {prefix!r} did not persist")
    if remaining:
        raise RuntimeError(f"dimension prefixes not applied: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open platen source", await adapter.open_model(str(SOURCE)))
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
            "Right View Note",
            "Back View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Isometric View Note",
            "Right View Note",
            "Back View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Platen Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "platen; manufacturing drawing; #2-56 taps; #4 counterbores",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    # Explicit per-view scale: a view placed without one can silently
    # auto-scale, which shifts every coordinate-based pick on it.
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    back = place_view(adapter, str(SOURCE), "*Back", *BACK_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=RIGHT_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # The holes are fully defined by their callouts; no view needs hidden lines.
    for view in (front, back, right, iso):
        set_hidden_lines_removed(adapter, view)

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
        *curate_view_dimensions(
            adapter,
            back,
            keep=BACK_KEEP,
            view_label="back",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _set_dimension_prefixes(adapter, annotations, DIMENSION_PREFIXES)

    for view, label in ((front, "front"), (back, "back")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(f"failed to add ASME center marks to {label} view")

    guide_callout = add_native_hole_callout(
        adapter,
        front,
        edge_xy=GUIDE_EDGE_XY,
        callout_xy=GUIDE_CALLOUT_XY,
        label="guide-screw counterbored holes",
        process=GUIDE_CALLOUT_PROCESS,
    )
    set_hole_callout_precision(
        guide_callout, GUIDE_CALLOUT_PRECISION, label="guide-screw counterbored holes"
    )
    add_native_hole_callout(
        adapter,
        front,
        edge_xy=SOCKET_EDGE_XY,
        callout_xy=SOCKET_CALLOUT_XY,
        label="clip-screw through taps",
        process=SOCKET_CALLOUT_PROCESS,
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    add_property_linked_note(adapter, "Right View Note", *RIGHT_NOTE_XY)
    add_property_linked_note(adapter, "Back View Note", *BACK_NOTE_XY)
    _telemetry.info("platen sheet: views, dimensions and callouts placed")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Platen Manufacturing Drawing",
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

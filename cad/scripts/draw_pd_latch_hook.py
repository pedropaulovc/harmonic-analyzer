r"""Create the manufacturing drawing for the latch hook (MHA-PD-014).

One formed spring-steel part, all orthographic views at 3:2 (each pinned so
the part origin -- the ear's outer face, the base's underside and its low-Y
edge -- lands where the layout puts it):

* ``*Front`` (looking -Z, X right, Y up; hidden lines shown so the pin hole
  reads through the edge-on strip): the screw holes on the base, located
  from the ear's outer face and the low-Y edge; the arm's formed profile --
  the roll's start below the ear, its inside radius (shortened leader: the
  centre is 80 off), the straight's length, the inside tab radius, the tab
  end's X -- and the far face where the pin crosses it, in X and Y from the
  origin; the pin hole's size, match-drilled at assembly;
* ``*Right`` (looking -X, Z running left): the width, the arm's front-edge
  heights above and below the taper, the root relief and the full round;
  left of it the formed overall height, a reference from the ear's top edge
  to the full round's tip; beside it the flat pattern, the part's hidden
  ``FlatBlank`` reference sketch shown in this view only (a thin outline):
  the blank across the bend and the arm's developed stations of the taper
  and the round's centre;
* ``*Bottom`` (looking +Y, X right, Z up), out of projection beside the side
  view and so labelled: the base length, the ear height and the inside bend.

The process and the heat treatment ride the part's Manufacturing Notes and
the title block's FINISH cell.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_imported_precision,
    dimension_name,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from build_pd_latch_hook import FAR_FACE_POINT, FLAT_GAP
from pd_latch_hook_geometry import (
    ARM_N,
    ARM_U,
    BASE_LENGTH,
    BBOX_X,
    BBOX_Y,
    BBOX_Z,
    DEV_TAPER,
    EAR_HEIGHT,
    FLAT_LENGTH,
    OUTER_ROLL_END,
    OUTER_ROLL_START,
    OUTER_TAB_END,
    PART_ORIGIN_MACHINE,
    PIN_HOLE_L,
    ROUND_C_L,
    ROUND_R,
    SCREW_HOLE_X,
    SCREW_HOLE_Y,
    TAB_C_L,
    WIDTH,
)
from pd_latch_hook_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLAT_ROUND_CALLOUT,
    OVERALL_HEIGHT,
    PAIR_CALLOUT,
    PIN_HOLE_CALLOUT,
    ROUND_CALLOUT,
    SCREW_HOLE_CALLOUT,
)
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["pd_latch_hook"]
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

# A 30 x 97 x 16 formed part: 3:2 keeps the arm's 97 drop and its dimensions
# between the border and the title block, and the 0.8 strip legible.
SHEET_SCALE = (3.0, 2.0)
VIEW_SCALE = (3, 2)
ISO_SCALE = (1, 2)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
_PIN_TOL_M = 1e-4  # how close a pinned view's origin must land

# The part's local bounding box (mm): X and Y on the front view, Z the band.
_LOCAL_X = tuple(x - PART_ORIGIN_MACHINE[0] for x in BBOX_X)
_LOCAL_Y = tuple(y - PART_ORIGIN_MACHINE[1] for y in BBOX_Y)
_LOCAL_Z = tuple(z - PART_ORIGIN_MACHINE[2] for z in BBOX_Z)
_MID_X = sum(_LOCAL_X) / 2.0
_MID_Y = sum(_LOCAL_Y) / 2.0
_MID_Z = sum(_LOCAL_Z) / 2.0

# View centres (the part's bounding box centre on the sheet): the front view
# at the left, the side view and its flat pattern level with it, the bottom
# view and the isometric at the right above the title block (top 0.066).
FRONT_CENTER = (0.072, 0.170)
RIGHT_CENTER = (0.205, FRONT_CENTER[1])
BOTTOM_CENTER = (0.365, 0.230)
ISO_CENTER = (0.372, 0.135)
NOTES_XY = (0.020, 0.062)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.035)
BOTTOM_NOTE_XY = (BOTTOM_CENTER[0] - 0.013, 0.258)
NOTE_HEIGHT = 0.003  # the notes' characters (top-left anchored)

# Where each view puts the part origin.
FRONT_ORIGIN = (FRONT_CENTER[0] - _MID_X * _S, FRONT_CENTER[1] - _MID_Y * _S)
RIGHT_ORIGIN = (RIGHT_CENTER[0] + _MID_Z * _S, FRONT_ORIGIN[1])
BOTTOM_ORIGIN = (BOTTOM_CENTER[0] - _MID_X * _S, BOTTOM_CENTER[1] - _MID_Z * _S)


def _front(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a local (X, Y) on the front view."""
    return (FRONT_ORIGIN[0] + x_mm * _S, FRONT_ORIGIN[1] + y_mm * _S)


def _right(z_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of a local (Z, Y) on the side view (Z runs left)."""
    return (RIGHT_ORIGIN[0] - z_mm * _S, RIGHT_ORIGIN[1] + y_mm * _S)


def _flat(u_mm: float, v_mm: float) -> tuple[float, float]:
    """Sheet point of a FlatBlank sketch point (Right-plane sketch x, y)."""
    return (RIGHT_ORIGIN[0] + u_mm * _S, RIGHT_ORIGIN[1] + v_mm * _S)


def _bottom(x_mm: float, z_mm: float) -> tuple[float, float]:
    """Sheet point of a local (X, Z) on the bottom view."""
    return (BOTTOM_ORIGIN[0] + x_mm * _S, BOTTOM_ORIGIN[1] + z_mm * _S)


def _on(point: tuple[float, float], u: float, n: float = 0.0) -> tuple[float, float]:
    """``point`` moved ``u`` along ARM_U and ``n`` along ARM_N (local mm)."""
    return (
        point[0] + u * ARM_U[0] + n * ARM_N[0],
        point[1] + u * ARM_U[1] + n * ARM_N[1],
    )


# Per-view survivors of the marked-dimension import: name -> sheet position.
# Front: the screw X pair stacked above the base, their Y and size left of
# it; the roll start and the far face's Y right of the arm; the far face's X
# and the tab end's X stacked below it; the straight's length on the arm's
# -U side (its extension set clear of the far face's X, which drops from the
# far face); the pin hole's size up its +N side past the straight's roll-end
# extension line, under the roll radius, its callout above so the dimension
# line meets the value and never the callout; the inside roll radius in the
# roll's concave side, the tab radius outside the tab.
FRONT_KEEP = {
    "ScrewX2": _front(SCREW_HOLE_X[1] / 2.0, 12.5),
    "ScrewX1": _front(SCREW_HOLE_X[0] / 2.0, 17.5),
    "ScrewY": _front(-32.0, SCREW_HOLE_Y / 2.0),
    "ScrewDia": _front(-24.0, -8.0),
    "RollStart": _front(20.0, OUTER_ROLL_START[1] / 2.0),
    "FaceY": _front(30.0, FAR_FACE_POINT[1] / 2.0),
    "FaceX": _front(FAR_FACE_POINT[0] / 2.0, -96.0),
    "TabEndX": _front(OUTER_TAB_END[0] / 2.0, -103.0),
    "StraightLen": _front(*_on(OUTER_ROLL_END, -28.0, -4.0)),
    "PinHoleDia": _front(*_on(PIN_HOLE_L, -12.3, 21.2)),
    "RollR": _front(-20.0, -35.0),
    "TabR": _front(
        TAB_C_L[0] + 21.0 * math.cos(math.radians(175.0)),
        TAB_C_L[1] + 21.0 * math.sin(math.radians(175.0)),
    ),
}
# Side view: the width left of the ear, the two front-edge heights stacked
# above it, the root relief right of its corner, the round under the tip;
# the flat's length above it and its developed stations stacked to its right.
RIGHT_KEEP = {
    "Width": _right(26.0, 4.0),
    "ArmFrontZ": _right(3.0, 13.0),
    "ArmLowZ": _right(2.25, 19.0),
    "RootR": _right(-4.0, -8.0),
    "RoundR": _right(-6.0, -95.0),
    "FlatLength": _flat(FLAT_GAP + FLAT_LENGTH / 2.0, 14.0),
    "DevTaper1": _flat(58.0, -DEV_TAPER[0] / 2.0),
    "DevTaper2": _flat(66.0, -DEV_TAPER[1] / 2.0),
    "DevRoundC": _flat(74.0, -45.0),
}
# Bottom view: the base length under the base, the ear height right of the
# ear, the inside bend's leader from below-right through the corner.
BOTTOM_KEEP = {
    "BaseLength": _bottom(-BASE_LENGTH / 2.0, -6.0),
    "EarHeight": _bottom(6.0, EAR_HEIGHT / 2.0),
    "InsideBendR": _bottom(11.0, -12.0),
}
CALLOUTS_ABOVE = {
    "ScrewDia": PAIR_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "DevRoundC": FLAT_ROUND_CALLOUT,
}
CALLOUTS_BELOW = {"ScrewDia": SCREW_HOLE_CALLOUT, "RoundR": ROUND_CALLOUT}
# The roll's centre sits 80 left of the vertical: off the sheet at 3:2.
SHORTENED_RADII = ("RollR",)
# The formed overall height (rule 7), a reference left of the side view: its
# dimension line passes left of the width's text, its text below the front
# view's 70.4 level and clear right of it; picked on the ear's top edge and
# on the full round, re-anchored to the round's far extreme (its tip).
_ROUND_PICK_DEG = -120.0  # on the round, clear of its tip and the RoundR leader
OVERALL_PICKS = (
    _right(12.0, WIDTH),
    _right(
        ROUND_C_L[1] + ROUND_R * math.cos(math.radians(_ROUND_PICK_DEG)),
        ROUND_C_L[0] + ROUND_R * math.sin(math.radians(_ROUND_PICK_DEG)),
    ),
)
OVERALL_TEXT_XY = _right(38.0, -55.0)


def _pin_origin(
    adapter: Any, view: Any, target: tuple[float, float], *, label: str
) -> None:
    """Move ``view`` so the part origin lands on ``target`` (sheet m), and
    read the projection back.  The view's annotations move with it."""
    view = _early_bound(view, "IView")
    at = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    if math.dist(at, target) <= _PIN_TOL_M:
        return
    position = tuple(float(value) for value in view.Position)
    moved = [position[axis] + target[axis] - at[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label} onto its sheet position")
    adapter.currentModel.EditRebuild3()
    at = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label=f"{label} origin")
    if math.dist(at, target) > _PIN_TOL_M:
        raise RuntimeError(f"{label}: part origin sits at {at!r}, not {target!r}")


def _shorten_radii(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Foreshorten the named radius dimensions and read each one back.

    ``IDisplayDimension::ShortenedRadius`` draws the radius line toward the
    centre but stops it short of it -- the jogged radius for a centre beyond
    the sheet.  A property put that SolidWorks ignores still returns, so the
    flag is read back.
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = True
        if not bool(display.ShortenedRadius):
            raise RuntimeError(f"radius {name!r} did not keep its shortened leader")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"radii not shortened: {sorted(remaining)}")


def _overall_reference(adapter: Any, right: Any) -> None:
    """The (96.5) formed overall height, ear top edge to the round's tip."""
    label = "latch-hook overall height reference"
    display = add_edge_dimension(
        adapter,
        right,
        p0=OVERALL_PICKS[0],
        p1=OVERALL_PICKS[1],
        text_xy=OVERALL_TEXT_XY,
        label=label,
        orientation="vertical",
    )
    set_arc_endpoints_to_max(adapter, display, label=label)
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - OVERALL_HEIGHT) > 1e-4:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {OVERALL_HEIGHT:g}"
        )
    set_reference_dimension(adapter, display.GetAnnotation(), label=label)
    display.SetPrecision3(DRAWING_REFERENCE_PRECISION, -1, -1, -1)
    if int(display.GetPrimaryPrecision2()) != DRAWING_REFERENCE_PRECISION:
        raise RuntimeError(f"{label} precision did not persist")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open latch-hook source", await adapter.open_model(str(SOURCE)))
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
            "Bottom View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Bottom View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Latch Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "latch hook; formed spring-steel sheet",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    right = place_view(adapter, str(SOURCE), "*Right", *RIGHT_CENTER, scale=VIEW_SCALE)
    bottom = place_view(
        adapter, str(SOURCE), "*Bottom", *BOTTOM_CENTER, scale=VIEW_SCALE
    )
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (right, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    for view, origin, label in (
        (front, FRONT_ORIGIN, "front view"),
        (right, RIGHT_ORIGIN, "side view"),
        (bottom, BOTTOM_ORIGIN, "bottom view"),
    ):
        _pin_origin(adapter, view, origin, label=label)

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
            view_label="side",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
        *curate_view_dimensions(
            adapter,
            bottom,
            keep=BOTTOM_KEEP,
            view_label="bottom",
            dimensions_by_feature=DRAWING_DIMENSIONS,
        ),
    ]
    # Showing the FlatBlank sketch may grow the side view's box; put its
    # origin back (its dimensions travel with it).
    _pin_origin(adapter, right, RIGHT_ORIGIN, label="side view with flat pattern")
    # Places (and so each dimension's title-block row) and every band are
    # authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _shorten_radii(adapter, annotations, SHORTENED_RADII)
    _overall_reference(adapter, right)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the screw holes")
    # Re-asserted after annotating: the toggle regenerates the dashed edges.
    set_hidden_lines_visible(adapter, front)
    for name, xy in (
        ("Manufacturing Notes", NOTES_XY),
        ("Isometric View Note", ISO_NOTE_XY),
        ("Bottom View Note", BOTTOM_NOTE_XY),
    ):
        add_property_linked_note(adapter, name, *xy, char_height=NOTE_HEIGHT)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Latch Hook Manufacturing Drawing",
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

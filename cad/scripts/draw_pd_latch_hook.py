r"""Create the manufacturing drawing for the latch hook (MHA-PD-14).

One formed spring-steel part, printed in decimal inch (the row's
``drawing_unit: in``), all orthographic views at 3:2 (each pinned so
the part origin -- the ear's outer face, the base's underside and its low-Y
edge -- lands where the layout puts it):

* ``*Front`` (looking -Z, X right, Y up; hidden lines shown so the pin hole
  reads through the edge-on strip): the screw holes on the base, located
  from the ear's outer face and the low-Y edge; the arm's formed profile --
  the roll's start below the ear, its inside radius (shortened leader: the
  centre is off the sheet), the straight's length, the inside tab radius, the tab
  end's X -- and the far face where the pin crosses it, in X and Y from the
  origin as references, the Y flagged as the pin's axis at that face; the
  pin hole's size, match-drilled at assembly (note 2 names the pin);
* ``*Right`` (looking -X, Z running left): the width, the root relief and
  the full round; left of it the formed overall height, a reference from
  the ear's top edge to the full round's tip; beside it the flat pattern,
  the part's hidden ``FlatBlank`` reference sketch shown in this view only
  (labelled FLAT PATTERN; its outline black at the visible-edge weight, its
  bend centrelines black chain lines): the blank across the bend, the arm's
  two strip widths (its controlling widths), its developed stations of the
  taper and the round's centre, and the bend centrelines' references;
* ``*Bottom`` (looking +Y, X right, Z up), projected under the front view
  (third angle, so unlabelled): the base length, the ear height and the
  inside bend.

The heat treatment rides the title block's FINISH cell; the fit-up and
heat-treat sequence is the assembly's (the registry row's process).
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    dimension_name,
    place_view,
    view_name,
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
from _drawing_dimensions import (
    assert_imported_precision,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_edge_dimensions import add_edge_dimension
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed, set_hidden_lines_visible
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
from build_pd_latch_hook import FAR_FACE_POINT, FLAT_GAP
from pd_latch_hook_geometry import (
    ARM_N,
    ARM_U,
    BASE_LENGTH,
    BBOX_X,
    BBOX_Y,
    BBOX_Z,
    DEV_ROLL_C,
    DEV_TAPER,
    DEV_TIP,
    EAR_HEIGHT,
    FLAT_BEND_C,
    FLAT_LENGTH,
    OUTER_ROLL_END,
    OUTER_ROLL_START,
    OUTER_TAB_END,
    PART_ORIGIN_MACHINE,
    PIN_HOLE_L,
    ROUND_C_L,
    ROUND_R,
    SCREW_HOLE_Y,
    TAB_C_L,
    WIDTH,
)
from pd_latch_hook_spec import (
    BEND_LINE_DIMENSIONS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    FLAT_ROUND_CALLOUT,
    FLAT_SKETCH,
    OVERALL_HEIGHT,
    PAIR_CALLOUT,
    PIN_HOLE_CALLOUT,
    PIN_STATION_CALLOUT,
    REFERENCE_DIMENSIONS,
    ROUND_CALLOUT,
    SCREW_HOLE_CALLOUT,
    SCREW_HOLE_MATE,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

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

# A 30 x 97 x 16 mm formed part: 3:2 keeps the arm's drop and its dimensions
# between the border and the title block, and the .032 strip legible.
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
# view projected under the front view (its top clear under the front view's
# lowest text), the isometric at the right above the title block (top
# 0.066), the notes in the free top-right corner.
FRONT_CENTER = (0.072, 0.170)
RIGHT_CENTER = (0.205, FRONT_CENTER[1])
BOTTOM_CENTER = (FRONT_CENTER[0], 0.0544)
ISO_CENTER = (0.380, 0.135)
NOTES_XY = (0.316, 0.262)
ISO_NOTE_XY = (ISO_CENTER[0] - 0.030, ISO_CENTER[1] - 0.035)
FLAT_NOTE_XY = (0.245, 0.083)
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
# Front: the screw X pair stacked above the base, their texts right of the
# ear's outer face (its extension line crossed them between the arrows,
# review 4), their Y and size left of it; the roll start and the far face's
# Y right of the arm, the roll start inside so its text clears the far
# face's dimension line; the far face's X
# and the tab end's X stacked below it; the straight's length on the arm's
# -U side (its extension set clear of the far face's X, which drops from the
# far face); the pin hole's size up its +N side past the straight's roll-end
# extension line, under the roll radius, its callout above so the dimension
# line meets the value and never the callout;
# the inside roll radius in the roll's concave side, the tab radius outside
# the tab, its leader radial through the middle of the tab's 35 deg arc
# (147-182 deg about its centre), clear of the end face and its X.
_TAB_LEADER_DEG = 165.0
FRONT_KEEP = {
    "ScrewX2": _front(11.0, 12.5),
    "ScrewX1": _front(11.0, 17.5),
    "ScrewY": _front(-32.0, SCREW_HOLE_Y / 2.0),
    "ScrewDia": _front(-25.0, -8.0),  # its mate line clear of the arm
    "RollStart": _front(14.0, OUTER_ROLL_START[1] / 2.0),
    "FaceY": _front(24.0, FAR_FACE_POINT[1] / 2.0),
    "FaceX": _front(FAR_FACE_POINT[0] / 2.0, -96.0),
    "TabEndX": _front(OUTER_TAB_END[0] / 2.0, -103.0),
    "StraightLen": _front(*_on(OUTER_ROLL_END, -28.0, -5.0)),
    "PinHoleDia": _front(*_on(PIN_HOLE_L, -12.3, 21.2)),
    "RollR": _front(-20.0, -35.0),
    "TabR": _front(
        TAB_C_L[0] + 26.0 * math.cos(math.radians(_TAB_LEADER_DEG)),
        TAB_C_L[1] + 26.0 * math.sin(math.radians(_TAB_LEADER_DEG)),
    ),
}
# Side view: the width left of the ear, the root relief right of its corner,
# the round under the tip; the flat's length above it over the ear bend's
# centreline; its two strip widths (the arm's controlling widths) left of
# it, between the views; its developed stations stacked to its right, the
# longer outside (the roll's centreline among them, its text clear below
# the taper's), the tab's centreline chained under the round's centre, its
# text below the blank's tip.
RIGHT_KEEP = {
    "Width": _right(26.0, 4.0),
    "RootR": _right(-4.0, -8.0),
    "RoundR": _right(-6.0, -95.0),
    "FlatBendC": _flat(FLAT_GAP + FLAT_BEND_C / 2.0, 14.0),
    "FlatLength": _flat(FLAT_GAP + FLAT_LENGTH / 2.0, 19.5),
    "FlatArmW": _flat(10.0, -12.0),
    "FlatLowW": _flat(10.0, -40.0),
    "DevTaper1": _flat(58.0, -DEV_TAPER[0] / 2.0),
    "DevTaper2": _flat(66.0, -DEV_TAPER[1] / 2.0),
    "FlatRollC": _flat(74.0, -DEV_ROLL_C / 2.0),
    "DevRoundC": _flat(82.0, -50.0),
    "FlatTabC": _flat(82.0, -(DEV_TIP + 4.0)),
}
# Bottom view: the base length well under the base, the ear height right of
# the ear, and the inside bend's text between the two, right of the ear: its
# radial leader leaves the bend at 45 deg, through the corner gap between
# the two dimensions' extension lines, and crosses no dimension line (review
# 4: from below, it cut the base length's).  SolidWorks lands that leader on
# an underline under the text.
BOTTOM_KEEP = {
    "BaseLength": _bottom(-BASE_LENGTH / 2.0, -11.0),
    "EarHeight": _bottom(6.0, EAR_HEIGHT / 2.0),
    "InsideBendR": _bottom(13.0, -2.0),
}
CALLOUTS_ABOVE = {
    "ScrewDia": PAIR_CALLOUT,
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "DevRoundC": FLAT_ROUND_CALLOUT,
}
CALLOUTS_BELOW = {
    "ScrewDia": f"{SCREW_HOLE_CALLOUT}\n{SCREW_HOLE_MATE}",
    "FaceY": PIN_STATION_CALLOUT,
    "RoundR": ROUND_CALLOUT,
}
# The roll's centre sits ~80 mm left of the vertical: off the sheet at 3:2.
SHORTENED_RADII = ("RollR",)
# The formed overall height (drawing-guidelines.md rule 10 (dimension from a real feature)), a reference left of the side view: its
# dimension line passes left of the width's text, its text below the front
# view's far-face Y level and clear right of it; picked on the ear's top edge and
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
    """The (3.80) formed overall height, ear top edge to the round's tip."""
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


# A model sketch shown in a view draws thin and grey (review 3: the flat
# pattern read unlike the views).  Its outline takes the visible edges'
# black and weight; its bend centrelines (construction, the chain font)
# black, thin.
FLAT_LINE_COLOR = 0  # COLORREF black, the outline's colour
_SW_LW_THICK = 2  # swLineWeights_e.swLW_THICK, the visible-edge weight
_FLAT_SEGMENTS = {False: 9, True: 3}  # outline / bend centrelines


def _flat_pattern_lines(adapter: Any, right: Any) -> None:
    """Draw the flat pattern's outline as visible edges, its bend lines black."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    native = _early_bound(right, "IView")
    if not drawing.ActivateView(view_name(adapter, right)):
        raise RuntimeError("cannot activate the side view for the flat pattern")
    model = native.ReferencedDocument
    feature = (
        None
        if model is None
        else _early_bound(model, "IPartDoc").FeatureByName(FLAT_SKETCH)
    )
    if feature is None:
        raise RuntimeError(f"the side view's model has no {FLAT_SKETCH} sketch")
    sketch = _early_bound(
        _early_bound(feature, "IFeature").GetSpecificFeature2(), "ISketch"
    )
    segments = [
        _early_bound(raw, "ISketchSegment") for raw in sketch.GetSketchSegments() or ()
    ]
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for construction, count in _FLAT_SEGMENTS.items():
        picked = [s for s in segments if bool(s.ConstructionGeometry) is construction]
        label = "bend centrelines" if construction else "outline"
        if len(picked) != count:
            raise RuntimeError(
                f"flat pattern {label}: {len(picked)} segments, want {count}"
            )
        draw.ClearSelection2(True)
        for index, segment in enumerate(picked):
            in_view = native.GetCorresponding(segment)
            if in_view is None:
                raise RuntimeError(f"flat pattern {label}: a segment has no instance")
            data = selection.CreateSelectData()
            data.View = right
            if not _early_bound(in_view, "ISketchSegment").Select4(index > 0, data):
                raise RuntimeError(f"cannot select the flat pattern {label}")
        if int(selection.GetSelectedObjectCount2(-1)) != count:
            raise RuntimeError(f"flat pattern {label}: the selection lost segments")
        drawing.SetLineColor(FLAT_LINE_COLOR)
        if not construction:
            drawing.SetLineWidth(_SW_LW_THICK)
        _telemetry.info(f"latch-hook: flat pattern {label} drawn black ({count})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()


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
            "Flat Pattern Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
            "Flat Pattern Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
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
    _flat_pattern_lines(adapter, right)
    # Places (and so each dimension's title-block row) and every band are
    # authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    set_dimension_callouts(adapter, annotations, CALLOUTS_BELOW)
    _shorten_radii(adapter, annotations, SHORTENED_RADII)
    # The far face at the pin (located at fit-up on the pin's axis) and the
    # flat pattern's bend centrelines print as references.
    by_name = {dimension_name(adapter, a): a for a in annotations}
    for name in sorted(REFERENCE_DIMENSIONS | BEND_LINE_DIMENSIONS):
        set_reference_dimension(adapter, by_name[name], label=f"MHA-PD-14 {name}")
    _overall_reference(adapter, right)
    if not auto_center_marks(adapter, front, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to the screw holes")
    # Re-asserted after annotating: the toggle regenerates the dashed edges.
    set_hidden_lines_visible(adapter, front)
    for name, xy in (
        ("Manufacturing Notes", NOTES_XY),
        ("Isometric View Note", ISO_NOTE_XY),
        ("Flat Pattern Note", FLAT_NOTE_XY),
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

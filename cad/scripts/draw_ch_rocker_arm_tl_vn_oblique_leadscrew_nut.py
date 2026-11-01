"""Create the four-view purchased-reference sheet for ZYLtech HW-SC-T8x2-NUT, Tr8x2 brass flange nut.

Identification and supplier-native nominal size references, with its stock,
ordering SKU and fitting note; no fabrication controls. The orthographic
views are 1:1 in the ``tall_top`` cells (see the spec's lane budget).
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable, Mapping
from functools import partial
from math import isfinite
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import view_name

import _telemetry
from _com import _early_bound
from _session import run_build
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_leaders import set_near_side_diameter
from _drawing_projection import model_point_in_view, model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_audit import display_box
from _machinist_review_mode import MachinistReviewMode
from _drawing_view_display import _SW_HLR
from _purchased_part_drawing import build_purchased_part_drawing
from _purchased_title_fit import fit_purchased_title_block
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
from _supplier_screw_dimensions import (
    _assert_supplier_top_stations,
    _supplier_top_record,
    annotate_supplier_screw,
)
from _supplier_screw_layout import supplier_screw_margins, supplier_top_text_geometry
from _transgear_zone_line import (
    CENTER_LINE_STYLE,
    CENTER_LINE_WEIGHT,
    dimension_input_suppressed,
    sheet_to_sketch,
)
import ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec as supplier


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_leadscrew_nut"]
PART_STEM = SPEC.artifact_stem
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "TR8X2 BRASS FLANGE NUT"
# The 41-character Name and the DWG. NO. overran their title cells (machinist
# review, b344192): fit the linked notes inside their ruled cells.
TITLE_BLOCK_SETUP = partial(fit_purchased_title_block, spec=SPEC)
# No supplier-data footer: its two lines raised the bottom view row 12.5 mm,
# which the 1:1 Front row cannot spare (spec lane budget).
VIEW_LAYOUT = "tall_top"
# Every chord's horizontal text is wider than its span or crosses its own
# vertical dimension line, so centred text sat across its own witness or
# dimension lines (layout audit, farm run 20261023T173603916Z). Each text
# slides sideways in offset-text mode, just past all of its own line ink on
# its free side; the native tips, witnesses and dimension lines stay put.
TEXT_SHELVES = {
    "SupplierLength": "right",
    "SupplierFlangeThickness": "left",
    "SupplierSpigotLength": "right",
    "SupplierBodyDiameter": "right",
    "SupplierFlangeDiameter": "right",
    "SupplierMountingHoleDiameter": "right",
}
_HORIZONTAL = {
    name: orientation == "horizontal"
    for name, _, orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS
}
# The 1.5 mm spigot is shorter than its text, which at mid-span crossed the
# overall length's line one lane out; its shelf drops below the spigot's end
# witness instead, and the overall length keeps its arrows inside its span
# (left smart, its lower tail ran down past the spigot).
LOWERED = "SupplierSpigotLength"
ARROWS_INSIDE = ("SupplierLength",)
_DIM_ARROWS_INSIDE = 0  # swDimensionArrowsSide_e.swDimArrowsInside
# The bolt pattern: a centreline circle through the four hole centres in the
# end view, its diameter a reference on that circle (machinist review: a
# floating linear (Ø16 mm) between empty extension lines read as nothing).
# The leader reaches the circle at 160°, between the 135° hole and the
# horizontal centreline, and the text stands left of the flange.
PITCH_CIRCLE = "SupplierHolePitchDiameter"
PITCH_CIRCLE_FORMAT = (0, "diameter", None, "PCD")
PITCH_LEADER_DEG = 160.0
PITCH_TEXT_RADIUS_M = 0.032
# swDimensionType_e.swDiameterDimension: the end view's one diameter-type
# display (its imported sizes are linear chords).
_DIAMETER_DIMENSION = 6


def projection_margins(
    margins: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    """Refuse lane reserves that would move a view off its projection axis.

    The builder centres each view in its cell less its reserves. Front shares
    its vertical axis with Top and its horizontal axis with the unannotated
    (cell-centred) Right, so Front's reserves must match left/right and
    bottom/top, and Top's left/right. Widening the smaller bottom/top would
    cost the 1:1 Front row (spec lane budget), so only the 180 mm-wide
    columns are balanced (``balanced_columns``); this refuses anything else.
    """
    pairs = {"*Front": ((0, 2), (1, 3)), "*Top": ((0, 2),)}
    for name, lanes in margins.items():
        for a, b in pairs.get(name, ()):
            if abs(lanes[a] - lanes[b]) > 1e-12:
                raise ValueError(
                    f"{name}: supplier lane reserves {lanes!r} leave the projection axis"
                )
    return dict(margins)


def balanced_columns(
    margins: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    """Widen each view's smaller left/right reserve to its larger one.

    Front's right carries two lanes (the spigot inside the overall length)
    and Top's left the pitch circle's text, which no lane reserves.
    """
    balanced = {}
    for name, (left, bottom, right, top) in margins.items():
        side = max(left, right)
        balanced[name] = (side, bottom, side, top)
    return balanced


def _measure(adapter: Any, display: Any, name: str) -> dict[str, Any]:
    return supplier_top_text_geometry(
        _supplier_top_record(adapter, display), horizontal=_HORIZONTAL[name]
    )


def _shelf_gap(name: str, actual: Mapping[str, Any]) -> float:
    text = actual["text"]
    if TEXT_SHELVES[name] == "left":
        return actual["left"] - text.xmax
    return text.xmin - actual["right"]


def _shelf_text(adapter: Any, displays: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Move text only, after formatting; return the measured native line stations.

    The sequence is ``_supplier_screw_dimensions._shelf_supplier_top_text``'s,
    with this sheet's own shelves and sides.
    """
    rebuild_drawing(adapter, label="nut supplier formatting and native lanes settled")
    before, positions, anchors = {}, {}, {}
    for name in TEXT_SHELVES:
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        position = tuple(float(value) for value in annotation.GetPosition())
        if len(position) != 3 or not all(map(isfinite, position)):
            raise RuntimeError(f"{name}: nut supplier text has no native position")
        actual = _measure(adapter, display, name)
        before[name], positions[name] = actual, position
        # OffsetText makes the old annotation anchor the physical line station:
        # seed it on the measured arrow tips first.
        normal = 1 if _HORIZONTAL[name] else 0
        anchor = list(position[:2])
        anchor[normal] = sum(tip[normal] for tip in actual["tips"]) / 2.0
        anchors[name] = tuple(anchor)
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: failed to prepare nut supplier offset anchor")
    rebuild_drawing(adapter, label="nut supplier measured pre-offset anchors")
    for name, anchor in anchors.items():
        display = _early_bound(displays[name], "IDisplayDimension")
        display.OffsetText = True
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        if not annotation.SetPosition2(*anchor, 0.0):
            raise RuntimeError(f"{name}: failed to enable nut supplier text offset")
    rebuild_drawing(adapter, label="nut supplier native offset-text mode")
    for name in TEXT_SHELVES:
        display = _early_bound(displays[name], "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        actual = _measure(adapter, display, name)
        _assert_supplier_top_stations(name, before[name], actual)
        dx = CLEAR_GAP_M + PLACE_SETTLE_M - _shelf_gap(name, actual)
        if TEXT_SHELVES[name] == "left":
            dx = -dx
        current = tuple(float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(current[0] + dx, positions[name][1], 0.0):
            raise RuntimeError(f"{name}: failed to place nut supplier text shelf")
    rebuild_drawing(adapter, label="nut supplier text shelves settled")
    _assert_text_shelves(adapter, displays, before)
    return before


def _assert_text_shelves(
    adapter: Any,
    displays: Mapping[str, Any],
    stations: Mapping[str, Mapping[str, Any]],
) -> None:
    for name in TEXT_SHELVES:
        display = _early_bound(displays[name], "IDisplayDimension")
        actual = _measure(adapter, display, name)
        if display.OffsetText is not True or _shelf_gap(name, actual) < CLEAR_GAP_M:
            raise RuntimeError(f"{name}: nut supplier text shelf is not clear")
        _assert_supplier_top_stations(name, stations[name], actual)


def _set_arrows_inside(displays: Mapping[str, Any]) -> None:
    for name in ARROWS_INSIDE:
        display = _early_bound(displays[name], "IDisplayDimension")
        display.ArrowSide = _DIM_ARROWS_INSIDE
        if int(display.ArrowSide) != _DIM_ARROWS_INSIDE:
            raise RuntimeError(f"{name} did not keep its arrows inside")


def _drop_clearance(actual: Mapping[str, Any]) -> float:
    """The spigot text's top below its lower witness (its lower arrow tip)."""
    return min(tip[1] for tip in actual["tips"]) - actual["text"].ymax


def _lower_spigot_text(adapter: Any, displays: Mapping[str, Any]) -> None:
    display = _early_bound(displays[LOWERED], "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    dy = CLEAR_GAP_M + PLACE_SETTLE_M - _drop_clearance(_measure(adapter, display, LOWERED))
    x, y, _z = (float(value) for value in annotation.GetPosition())
    if not annotation.SetPosition2(x, y - max(dy, 0.0), 0.0):
        raise RuntimeError(f"{LOWERED}: failed to lower its text below the spigot")
    rebuild_drawing(adapter, label="nut spigot text lowered")


def _assert_front_layout(adapter: Any, displays: Mapping[str, Any]) -> None:
    for name in ARROWS_INSIDE:
        if int(_early_bound(displays[name], "IDisplayDimension").ArrowSide) != (
            _DIM_ARROWS_INSIDE
        ):
            raise RuntimeError(f"{name}: arrows left the span")
    display = _early_bound(displays[LOWERED], "IDisplayDimension")
    if _drop_clearance(_measure(adapter, display, LOWERED)) < CLEAR_GAP_M:
        raise RuntimeError(f"{LOWERED}: text is not clear below the spigot")


def _pitch_circle_sheet(adapter: Any, view: Any) -> tuple[tuple[float, float], float]:
    """The bolt circle's sheet centre and radius, through every hole centre."""
    view = _early_bound(view, "IView")
    centre = model_point_in_view(adapter, view, (0.0, 0.0, 0.0), label="nut axis")
    radius = supplier.HOLE_PCD / 2000.0 * float(view.ScaleDecimal)
    holes = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, z / 1000.0) for x, z in supplier.HOLE_CENTRES],
        label="nut flange hole centres",
    )
    for hole in holes:
        if abs(math.dist(hole, centre) - radius) > 1e-7:
            raise RuntimeError(f"nut hole centre {hole!r} is off the pitch circle")
    return centre, radius


def _add_pitch_circle(adapter: Any, view: Any) -> Any:
    """A black thin centreline circle in the end view's sketch; its segment."""
    centre, radius = _pitch_circle_sheet(adapter, view)
    model = adapter.currentModel
    if not _early_bound(model, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("failed to activate the nut end view for its pitch circle")
    model.ClearSelection2(True)
    mapped = sheet_to_sketch(adapter, view, [centre, (centre[0] + radius, centre[1])])
    manager = _early_bound(model.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        circle = manager.CreateCircle(*mapped[0], *mapped[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError("failed to sketch the nut pitch circle")
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0
    segment.Style = CENTER_LINE_STYLE
    segment.Width = CENTER_LINE_WEIGHT
    model.ClearSelection2(True)
    return segment


def _pitch_text_box(adapter: Any, display: Any) -> Any:
    texts = (_supplier_top_record(adapter, display).get("display") or {}).get("texts")
    box = display_box({"texts": texts or ()})
    if box is None:
        raise RuntimeError(f"{PITCH_CIRCLE}: no measured text")
    return box


def _pitch_text_clearance(adapter: Any, view: Any, display: Any) -> float:
    """Gap from the PCD text's right edge to the flange's left rim."""
    centre, _radius = _pitch_circle_sheet(adapter, view)
    rim = centre[0] - supplier.FLANGE_DIA / 2000.0 * float(
        _early_bound(view, "IView").ScaleDecimal
    )
    return rim - _pitch_text_box(adapter, display).xmax


def _reference_settings() -> dict[str, Any]:
    precision, presentation, fraction, callout = PITCH_CIRCLE_FORMAT
    return {
        "label": PITCH_CIRCLE,
        "units": "mm",
        "precision": precision,
        "expected_mm": supplier.HOLE_PCD,
        "presentation": presentation,
        "fraction_denominator": fraction,
        "callout": callout,
    }


def _dimension_pitch_circle(adapter: Any, view: Any, segment: Any) -> Any:
    """(Ø16 mm) PCD on the circle: one arrow at the leader's rim, text left."""
    centre, _radius = _pitch_circle_sheet(adapter, view)
    angle = math.radians(PITCH_LEADER_DEG)
    at = (
        centre[0] + PITCH_TEXT_RADIUS_M * math.cos(angle),
        centre[1] + PITCH_TEXT_RADIUS_M * math.sin(angle),
    )
    model = adapter.currentModel
    with dimension_input_suppressed(adapter):
        if not _early_bound(model, "IDrawingDoc").ActivateView(view_name(adapter, view)):
            raise RuntimeError("failed to activate the nut end view to dimension its PCD")
        selection = _early_bound(model.SelectionManager, "ISelectionMgr").CreateSelectData()
        selection.View = view
        if not segment.Select4(False, selection):
            raise RuntimeError("failed to select the nut pitch circle")
        display = model.AddDiameterDimension2(*at, 0.0)
        model.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to dimension the nut pitch circle")
    display = _early_bound(display, "IDisplayDimension")
    set_near_side_diameter(display.GetAnnotation(), PITCH_CIRCLE)
    display = supplier_reference_dimension(adapter, display, **_reference_settings())
    rebuild_drawing(adapter, label="nut pitch circle dimensioned")
    # Keep the text a clear gap left of the flange whatever its native width.
    shift = CLEAR_GAP_M + PLACE_SETTLE_M - _pitch_text_clearance(adapter, view, display)
    if shift > 0.0:
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        x, y, _z = (float(value) for value in annotation.GetPosition())
        if not annotation.SetPosition2(x - shift, y, 0.0):
            raise RuntimeError(f"{PITCH_CIRCLE}: failed to move its text off the flange")
        rebuild_drawing(adapter, label="nut pitch circle text clear of the flange")
    return display


def _settled_pitch_dimension(view: Any) -> Any:
    """Reacquire the end view's one diameter-type dimension: the PCD."""
    found = []
    display = _early_bound(view, "IView").GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        if int(display.Type2) == _DIAMETER_DIMENSION:
            found.append(display)
        display = display.GetNext5()
    if len(found) != 1:
        raise RuntimeError(f"{PITCH_CIRCLE}: end view must carry one diameter dimension")
    return found[0]


def _assert_pitch_circle(adapter: Any, view: Any, segment: Any) -> None:
    font = (int(segment.Color), int(segment.Style), int(segment.Width))
    if font != (0, CENTER_LINE_STYLE, CENTER_LINE_WEIGHT):
        raise RuntimeError(f"nut pitch circle font reads {font!r}, not a black centreline")
    display = _settled_pitch_dimension(view)
    assert_supplier_reference_dimension(adapter, display, **_reference_settings())
    if _pitch_text_clearance(adapter, view, display) < CLEAR_GAP_M:
        raise RuntimeError(f"{PITCH_CIRCLE}: text is not clear of the flange")


def _assert_hidden_lines_removed(views: Mapping[str, Any]) -> None:
    """The orthographic views print no hidden edges after the final rebuild.

    The reference chords show in their views as construction lines; they lie
    on the axis or on visible edges, never as dashed edges across a face.
    """
    for name in ("*Front", "*Top", "*Right"):
        mode = int(_early_bound(views[name], "IView").GetDisplayMode2())
        if mode != _SW_HLR:
            raise RuntimeError(f"{name}: nut view is not hidden-lines-removed ({mode})")


def _annotate(
    adapter: Any, views: dict[str, Any], *, checks: list[Callable[[], None]]
) -> None:
    reference_checks: list[Callable[[], Any]] = []
    displays = annotate_supplier_screw(
        adapter,
        views,
        dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        formats=supplier.SUPPLIER_REFERENCE_FORMATS,
        starts=supplier.SUPPLIER_REFERENCE_STARTS,
        planes=supplier.SUPPLIER_REFERENCE_PLANES,
        sides=supplier.SUPPLIER_REFERENCE_SIDES,
        units=supplier.SUPPLIER_REFERENCE_UNITS,
        settled_checks=reference_checks,
    )
    _set_arrows_inside(displays)
    stations = _shelf_text(adapter, displays)
    _lower_spigot_text(adapter, displays)
    _assert_text_shelves(adapter, displays, stations)
    _assert_front_layout(adapter, displays)
    end = views["*Top"]
    circle = _add_pitch_circle(adapter, end)
    _dimension_pitch_circle(adapter, end, circle)
    _assert_pitch_circle(adapter, end, circle)
    [reference_check] = reference_checks

    # The final check reacquires every native reference, then re-proves the
    # shelves on those settled displays against the stations measured here.
    def assert_references() -> None:
        settled = reference_check()
        _assert_text_shelves(adapter, settled, stations)
        _assert_front_layout(adapter, settled)
        _assert_pitch_circle(adapter, end, circle)

    checks.append(assert_references)
    checks.append(partial(_assert_hidden_lines_removed, dict(views)))


async def build(adapter: Any) -> dict[str, str]:
    checks: list[Callable[[], None]] = []
    return await build_purchased_part_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=partial(_annotate, checks=checks),
        supplier_margins=projection_margins(
            balanced_columns(
                supplier_screw_margins(
                    supplier.SUPPLIER_REFERENCE_DIMENSIONS,
                    planes=supplier.SUPPLIER_REFERENCE_PLANES,
                    sides=supplier.SUPPLIER_REFERENCE_SIDES,
                )
            )
        ),
        settled_checks=checks,
        title_block_setup=TITLE_BLOCK_SETUP,
        view_layout=VIEW_LAYOUT,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

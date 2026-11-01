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
from dataclasses import dataclass
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
from _supplier_screw_dimensions import _supplier_top_record, annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins, supplier_top_text_geometry
# Tips and witnesses exact, the dimension line on its station: the overall
# length's inside arrows let its centred text break the line in two, and the
# shelved text leaves one run (the screw family's exact-run check refused it).
from _supplier_text_shelf import _assert_stations
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


@dataclass(frozen=True)
class DiameterLeader:
    """A reference Ø on its circle: format, value, leader and text placement.

    The leader leaves its circle's centre at ``leader_deg`` (sheet, CCW from
    +X); the text anchor stands ``text_radius_m`` out along it, on ``side``
    of the flange.
    """

    format: tuple[int, str, int | None, str | None]
    expected_mm: float
    leader_deg: float
    text_radius_m: float
    side: str


# The end view's two diameters print on their circles (machinist review):
# - the bolt pattern on a centreline circle through the four hole centres
#   (a floating linear (Ø16 mm) between empty extension lines read as
#   nothing); its leader meets the circle at 160°, between the 135° hole and
#   the horizontal centreline, the text left of the flange;
# - the 4X hole on the lower-right hole's own rim (a vertical linear between
#   tangent extension lines read as indirect), its leader out at -20°, the
#   text right of the flange and above the Ø10.2 shelf.
PITCH_CIRCLE = "SupplierHolePitchDiameter"
HOLE = "SupplierMountingHoleDiameter"
DIAMETER_LEADERS = {
    PITCH_CIRCLE: DiameterLeader(
        (0, "diameter", None, "PCD"), supplier.HOLE_PCD, 160.0, 0.032, "left"
    ),
    HOLE: DiameterLeader(
        (1, "diameter", None, "4X"), supplier.HOLE_DIA, -20.0, 0.020, "right"
    ),
}
_DIAMETER_TYPES = (6, 15)  # swDimensionType_e diameter displays
_SEL_EDGES = 1  # swSelectType_e.swSelEDGES


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
    and its left one, so the left widens to match.
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
        _assert_stations(name, _HORIZONTAL[name], before[name], actual)
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
        _assert_stations(name, _HORIZONTAL[name], stations[name], actual)


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


def _text_box(adapter: Any, display: Any, label: str) -> Any:
    texts = (_supplier_top_record(adapter, display).get("display") or {}).get("texts")
    box = display_box({"texts": texts or ()})
    if box is None:
        raise RuntimeError(f"{label}: no measured text")
    return box


def _flange_clearance(adapter: Any, view: Any, display: Any, name: str) -> float:
    """Gap from a leader's text to the flange rim on its side of the view."""
    centre, _radius = _pitch_circle_sheet(adapter, view)
    rim = supplier.FLANGE_DIA / 2000.0 * float(_early_bound(view, "IView").ScaleDecimal)
    box = _text_box(adapter, display, name)
    if DIAMETER_LEADERS[name].side == "left":
        return centre[0] - rim - box.xmax
    return box.xmin - (centre[0] + rim)


def _reference_settings(name: str) -> dict[str, Any]:
    leader = DIAMETER_LEADERS[name]
    precision, presentation, fraction, callout = leader.format
    return {
        "label": name,
        "units": "mm",
        "precision": precision,
        "expected_mm": leader.expected_mm,
        "presentation": presentation,
        "fraction_denominator": fraction,
        "callout": callout,
    }


def _leader_hole_sheet(adapter: Any, view: Any) -> tuple[float, float]:
    """The hole the 4X leader lands on: the end view's lower-right one."""
    holes = model_points_in_view(
        adapter,
        view,
        [(x / 1000.0, 0.0, z / 1000.0) for x, z in supplier.HOLE_CENTRES],
        label="nut flange hole centres",
    )
    return max(holes, key=lambda hole: hole[0] - hole[1])


def _select_pitch_circle(adapter: Any, view: Any, segment: Any) -> None:
    selection = _early_bound(
        adapter.currentModel.SelectionManager, "ISelectionMgr"
    ).CreateSelectData()
    selection.View = view
    if not segment.Select4(False, selection):
        raise RuntimeError("failed to select the nut pitch circle")


def _select_hole_edge(adapter: Any, view: Any) -> None:
    """Pick the lower-right hole's own edge on its leader side; prove it."""
    centre = _leader_hole_sheet(adapter, view)
    radius = supplier.HOLE_DIA / 2000.0 * float(_early_bound(view, "IView").ScaleDecimal)
    angle = math.radians(DIAMETER_LEADERS[HOLE].leader_deg)
    pick = (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))
    model = adapter.currentModel
    extension = _early_bound(model.Extension, "IModelDocExtension")
    if not extension.SelectByID2("", "EDGE", *pick, 0.0, False, 0, None, 0):
        raise RuntimeError(f"{HOLE}: no edge at the hole rim {pick!r}")
    manager = _early_bound(model.SelectionManager, "ISelectionMgr")
    if int(manager.GetSelectedObjectType3(1, -1)) != _SEL_EDGES:
        raise RuntimeError(f"{HOLE}: the rim pick is not an edge")
    curve = _early_bound(
        _early_bound(manager.GetSelectedObject6(1, -1), "IEdge").GetCurve(), "ICurve"
    )
    if not curve.IsCircle() or not math.isclose(
        float(curve.CircleParams[6]) * 2000.0, supplier.HOLE_DIA, abs_tol=1e-6
    ):
        raise RuntimeError(f"{HOLE}: the rim pick is not a Ø{supplier.HOLE_DIA} hole edge")


def _dimension_diameter(adapter: Any, view: Any, name: str, select: Any) -> Any:
    """A reference Ø on its circle: one arrow at the rim, text off the flange."""
    leader = DIAMETER_LEADERS[name]
    origin = (
        _pitch_circle_sheet(adapter, view)[0]
        if name == PITCH_CIRCLE
        else _leader_hole_sheet(adapter, view)
    )
    angle = math.radians(leader.leader_deg)
    at = (
        origin[0] + leader.text_radius_m * math.cos(angle),
        origin[1] + leader.text_radius_m * math.sin(angle),
    )
    model = adapter.currentModel
    with dimension_input_suppressed(adapter):
        if not _early_bound(model, "IDrawingDoc").ActivateView(view_name(adapter, view)):
            raise RuntimeError(f"failed to activate the nut end view to dimension {name}")
        model.ClearSelection2(True)
        select()
        display = model.AddDiameterDimension2(*at, 0.0)
        model.ClearSelection2(True)
    if display is None:
        raise RuntimeError(f"failed to dimension {name}")
    display = _early_bound(display, "IDisplayDimension")
    set_near_side_diameter(display.GetAnnotation(), name)
    display = supplier_reference_dimension(adapter, display, **_reference_settings(name))
    rebuild_drawing(adapter, label=f"nut {name} dimensioned")
    # Keep the text a clear gap off the flange whatever its native width.
    shift = CLEAR_GAP_M + PLACE_SETTLE_M - _flange_clearance(adapter, view, display, name)
    if shift > 0.0:
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        x, y, _z = (float(value) for value in annotation.GetPosition())
        dx = -shift if leader.side == "left" else shift
        if not annotation.SetPosition2(x + dx, y, 0.0):
            raise RuntimeError(f"{name}: failed to move its text off the flange")
        rebuild_drawing(adapter, label=f"nut {name} text clear of the flange")
    return display


def _settled_diameter(view: Any, name: str) -> Any:
    """Reacquire the end view's one diameter-type dimension of this size."""
    expected = DIAMETER_LEADERS[name].expected_mm
    found = []
    display = _early_bound(view, "IView").GetFirstDisplayDimension6()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        if int(display.Type2) in _DIAMETER_TYPES:
            native = _early_bound(display.GetDimension2(0), "IDimension")
            if math.isclose(abs(float(native.SystemValue)) * 1000.0, expected, abs_tol=1e-5):
                found.append(display)
        display = display.GetNext5()
    if len(found) != 1:
        raise RuntimeError(f"{name}: end view must carry one Ø{expected} diameter")
    return found[0]


def _assert_diameters(adapter: Any, view: Any, segment: Any) -> None:
    font = (int(segment.Color), int(segment.Style), int(segment.Width))
    if font != (0, CENTER_LINE_STYLE, CENTER_LINE_WEIGHT):
        raise RuntimeError(f"nut pitch circle font reads {font!r}, not a black centreline")
    for name in DIAMETER_LEADERS:
        display = _settled_diameter(view, name)
        assert_supplier_reference_dimension(adapter, display, **_reference_settings(name))
        if _flange_clearance(adapter, view, display, name) < CLEAR_GAP_M:
            raise RuntimeError(f"{name}: text is not clear of the flange")


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
    _dimension_diameter(
        adapter, end, PITCH_CIRCLE, partial(_select_pitch_circle, adapter, end, circle)
    )
    _dimension_diameter(adapter, end, HOLE, partial(_select_hole_edge, adapter, end))
    _assert_diameters(adapter, end, circle)
    [reference_check] = reference_checks

    # The final check reacquires every native reference, then re-proves the
    # shelves on those settled displays against the stations measured here.
    def assert_references() -> None:
        settled = reference_check()
        _assert_text_shelves(adapter, settled, stations)
        _assert_front_layout(adapter, settled)
        _assert_diameters(adapter, end, circle)

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

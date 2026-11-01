"""Create the four-view purchased-reference sheet for ZYLtech HW-SC-T8x2-NUT, Tr8x2 brass flange nut.

Identification and supplier-native nominal size references, with its stock,
ordering SKU and fitting note; no fabrication controls. The orthographic
views are 1:1 in the ``tall_top`` cells (see the spec's lane budget).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping
from functools import partial
from math import isfinite
from typing import Any

import _telemetry
from _com import _early_bound
from _session import run_build
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _drawing_view_display import _SW_HLR
from _purchased_part_drawing import build_purchased_part_drawing
from _purchased_title_fit import fit_purchased_title_block
from _supplier_screw_dimensions import (
    _assert_supplier_top_stations,
    _supplier_top_record,
    annotate_supplier_screw,
)
from _supplier_screw_layout import supplier_screw_margins, supplier_top_text_geometry
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
    "SupplierBodyDiameter": "right",
    "SupplierFlangeDiameter": "right",
    "SupplierMountingHoleDiameter": "right",
    "SupplierHolePitchDiameter": "left",
}
_HORIZONTAL = {
    name: orientation == "horizontal"
    for name, _, orientation in supplier.SUPPLIER_REFERENCE_DIMENSIONS
}


def projection_margins(
    margins: Mapping[str, tuple[float, float, float, float]],
) -> dict[str, tuple[float, float, float, float]]:
    """Refuse lane reserves that would move a view off its projection axis.

    The builder centres each view in its cell less its reserves. Front shares
    its vertical axis with Top and its horizontal axis with the unannotated
    (cell-centred) Right, so Front's reserves must match left/right and
    bottom/top, and Top's left/right. The riser screw widens the smaller side
    instead (``_aligned_margins``); here that would cost the 1:1 Front row
    (spec lane budget), so the spec authors balanced lanes and this refuses
    any other arrangement.
    """
    pairs = {"*Front": ((0, 2), (1, 3)), "*Top": ((0, 2),)}
    for name, lanes in margins.items():
        for a, b in pairs.get(name, ()):
            if abs(lanes[a] - lanes[b]) > 1e-12:
                raise ValueError(
                    f"{name}: supplier lane reserves {lanes!r} leave the projection axis"
                )
    return dict(margins)


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
    stations = _shelf_text(adapter, displays)
    [reference_check] = reference_checks
    # The final check reacquires every native reference, then re-proves the
    # shelves on those settled displays against the stations measured here.
    checks.append(
        lambda: _assert_text_shelves(adapter, reference_check(), stations)
    )
    checks.append(partial(_assert_hidden_lines_removed, dict(views)))


async def build(adapter: Any) -> dict[str, str]:
    checks: list[Callable[[], None]] = []
    return await build_purchased_part_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=partial(_annotate, checks=checks),
        supplier_margins=projection_margins(
            supplier_screw_margins(
                supplier.SUPPLIER_REFERENCE_DIMENSIONS,
                planes=supplier.SUPPLIER_REFERENCE_PLANES,
                sides=supplier.SUPPLIER_REFERENCE_SIDES,
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

"""Create the purchased reference drawing for the transgear disc screw."""

from __future__ import annotations

import argparse
from math import isfinite
import sys
from typing import Any

import _telemetry
from _com import _early_bound
from _drawing_annotation_extent import CLEAR_GAP_M, PLACE_SETTLE_M
from _drawing_common import rebuild_drawing
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_reference_text import (
    assert_reference_text_stations,
    measure_reference_text,
)
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _mcmaster_91794a055 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_FORMATS,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_disc_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#0-80 x 1/4 FILLISTER HEAD SLOTTED SCREW"

# The stock length's text and its "AS-SUPPLIED STOCK LENGTH" qualifier
# stand wholly right of its dimension line, in the open field right of the
# Front view (machinist review r5, all runs: centred on the line, the
# qualifier ran across the threaded shank, the thread lines through "SUPP"
# and the extension line through "AS").  The qualifier stays: the screw is
# cut at assembly, so the stock length is not the installed one.
STOCK_LENGTH = "SupplierStockLength"
_VERTICAL = 1  # measure_reference_text's axis for a vertical dimension


def _position(annotation: Any) -> tuple[float, float, float]:
    position = tuple(float(value) for value in annotation.GetPosition())
    if len(position) != 3 or not all(map(isfinite, position)):
        raise RuntimeError(f"{STOCK_LENGTH}: unreadable native text position")
    return position


def _clear_x(geometry: dict[str, Any]) -> float:
    """The dimension line's station or its extension lines' far ends,
    whichever stands farther right."""
    line_x = geometry["tips"][0][0]
    return max(line_x, *(far for _station, _near, far in geometry["witnesses"]))


def _shelve_stock_length_text(
    adapter: Any, front: Any, display: Any
) -> Any:
    """Offset the stock length's text off its line to the right; the arrow
    tips and extension lines stay where SolidWorks put them.  Returns the
    read-only settled proof."""
    display = _early_bound(display, "IDisplayDimension")
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    rebuild_drawing(adapter, label="disc screw stock length measured")
    before = measure_reference_text(
        adapter, display, axis=_VERTICAL, label=STOCK_LENGTH
    )
    outline = tuple(float(value) for value in _early_bound(front, "IView").GetOutline())
    line_x = before["tips"][0][0]
    if len(outline) != 4 or not line_x > outline[2]:
        raise RuntimeError(
            f"{STOCK_LENGTH}: its dimension line no longer stands right of the "
            f"Front view ({line_x!r} vs outline {outline!r})"
        )
    position = _position(annotation)
    anchor = (line_x, position[1], position[2])
    if display.OffsetText is not False or not annotation.SetPosition2(*anchor):
        raise RuntimeError(f"{STOCK_LENGTH}: cannot seed its offset text anchor")
    rebuild_drawing(adapter, label="disc screw stock length offset anchor")
    display.OffsetText = True
    if not annotation.SetPosition2(*anchor):
        raise RuntimeError(f"{STOCK_LENGTH}: cannot enable its offset text")
    rebuild_drawing(adapter, label="disc screw stock length offset mode")
    if display.OffsetText is not True:
        raise RuntimeError(f"{STOCK_LENGTH}: offset text mode did not persist")
    offset = measure_reference_text(
        adapter, display, axis=_VERTICAL, label=STOCK_LENGTH
    )
    assert_reference_text_stations(before, offset, label=STOCK_LENGTH)
    current = _position(annotation)
    dx = _clear_x(offset) + CLEAR_GAP_M + PLACE_SETTLE_M - offset["text"].xmin
    if not annotation.SetPosition2(current[0] + dx, position[1], 0.0):
        raise RuntimeError(f"{STOCK_LENGTH}: cannot shelf its text right of its line")
    rebuild_drawing(adapter, label="disc screw stock length text right of its line")

    def settled() -> None:
        actual = measure_reference_text(
            adapter, display, axis=_VERTICAL, label=STOCK_LENGTH
        )
        assert_reference_text_stations(before, actual, label=STOCK_LENGTH)
        if (
            display.OffsetText is not True
            or actual["text"].xmin < _clear_x(actual) + CLEAR_GAP_M
        ):
            raise RuntimeError(
                f"{STOCK_LENGTH}: its text crowds its dimension or extension lines"
            )

    settled()
    return settled


async def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    shelf_checks = []
    callback_count = 0
    settled = False

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        displays = annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )
        shelf_checks.append(
            _shelve_stock_length_text(
                adapter, views_by_orientation["*Front"], displays[STOCK_LENGTH]
            )
        )

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if (
            settled
            or callback_count != 1
            or len(supplier_checks) != 1
            or len(shelf_checks) != 1
        ):
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        supplier_checks[0]()
        shelf_checks[0]()
        settled = True

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=True,
        supplier_margins=supplier_screw_margins(
            SUPPLIER_REFERENCE_DIMENSIONS, planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        ),
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        unit=part_drawing_unit("pd-vn-transgear-disc-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

"""Create the purchased reference drawing for the pen set screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_annotation_extent import CLEAR_GAP_M
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import _supplier_top_record, annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins, supplier_top_text_geometry
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _mcmaster_99607a213 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_FORMATS,
    TS_MAJOR_R,
    TS_SH_R,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_vn_pen_set_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 5/8 KNURLED-HEAD THUMB SCREW, FLARED COLLAR"
# The thread and collar diameters share FRONT's right side, nested; centred on
# the axis their texts overprinted and the collar's line crossed the thread's
# text (dabcd16 review). Each text moves along its own dimension line, outside
# the collar's witnesses: thread below, collar above. A start only places the
# text (its height is start y + half the diameter); the model chords are the
# catalogue's. 2.5 mm past the collar radius is 10 mm on the 4:1 sheet, room
# for the two-line thread text clear of the collar's witnesses.
_TEXT_HEIGHT_MM = TS_SH_R + 2.5
STARTS = {
    **SUPPLIER_REFERENCE_STARTS,
    "SupplierThreadDiameter": (
        SUPPLIER_REFERENCE_STARTS["SupplierThreadDiameter"][0],
        -_TEXT_HEIGHT_MM - TS_MAJOR_R,
    ),
    "SupplierCollarDiameter": (
        SUPPLIER_REFERENCE_STARTS["SupplierCollarDiameter"][0],
        _TEXT_HEIGHT_MM - TS_SH_R,
    ),
}
# The .125 in head and collar heights print wider than their spans: shelve
# them past their own witnesses, right, into free sheet. Centred on its line,
# the head diameter's closing paren crowded the knurl outline (6988bc2
# review): its text shelves left, away from the head, at its own height.
SHELVES = {
    "SupplierHeadHeight": (True, "right"),
    "SupplierCollarHeight": (True, "right"),
    "SupplierHeadDiameter": (False, "left"),
}


def _assert_diameter_texts_clear(adapter: Any, displays: dict[str, Any]) -> None:
    """Thread text below and collar text above the collar's witnesses."""
    thread, collar = (
        supplier_top_text_geometry(
            _supplier_top_record(adapter, displays[name]), horizontal=False
        )
        for name in ("SupplierThreadDiameter", "SupplierCollarDiameter")
    )
    low, high = (tip[1] for tip in collar["tips"])
    if (
        thread["text"].ymax > low - CLEAR_GAP_M
        or collar["text"].ymin < high + CLEAR_GAP_M
    ):
        raise RuntimeError("pen set screw diameter texts are not clear of the collar")


async def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False
    stations = {}

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
            starts=STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )
        stations.update(shelve_supplier_text(adapter, displays, SHELVES))
        _assert_diameter_texts_clear(adapter, displays)

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        displays = supplier_checks[0]()
        assert_supplier_shelves(adapter, displays, SHELVES, stations)
        _assert_diameter_texts_clear(adapter, displays)
        settled = True

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM,
        supplier_margins=supplier_screw_margins(
            SUPPLIER_REFERENCE_DIMENSIONS, planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        ),
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        unit=part_drawing_unit("pn-vn-pen-set-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

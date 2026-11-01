"""Create the purchased reference drawing for the pen-rod set screw (MHA-PN-VN-52, McMaster 91375A105)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
from _mcmaster_91375a105 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_FORMATS,
)


MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pn_vn_pen_rod_set_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 3/16 SOCKET SET SCREW, CUP POINT"
# The diameter and drive texts are as wide as their spans: shelve them past
# their own witnesses. The 3/16 length keeps its centred text.
SHELVES = {
    "SupplierThreadDiameter": (True, "right"),
    "SupplierDriveWidth": (True, "right"),
}


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
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )
        stations.update(shelve_supplier_text(adapter, displays, SHELVES))

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        assert_supplier_shelves(adapter, supplier_checks[0](), SHELVES, stations)
        settled = True

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM,
        supplier_margins=supplier_screw_margins(
            SUPPLIER_REFERENCE_DIMENSIONS, planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
        ),
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        unit=part_drawing_unit("pn-vn-pen-rod-set-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

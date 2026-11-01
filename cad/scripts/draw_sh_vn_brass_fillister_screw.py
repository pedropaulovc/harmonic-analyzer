"""Create the shared purchased reference sheet for McMaster 90114A511."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from _supplier_text_shelf import assert_supplier_shelves, shelve_supplier_text
import sh_vn_brass_fillister_screw_spec as supplier
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_brass_fillister_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 1/4 FILLISTER HEAD SLOTTED SCREW"
# Each of these spans is shorter than its text, so the witnesses ran through
# it: shelve the text past its outer witness. The thread text goes left, away
# from the shelved Length text and its arrow tail on the right.
SHELVES = {
    "SupplierLength": (False, "right"),
    "SupplierHeadHeight": (False, "left"),
    "SupplierThreadDiameter": (True, "left"),
    "SupplierHeadDiameter": (True, "right"),
}


async def build(adapter: Any) -> dict[str, str]:
    checks = []

    def supplier_dimensions(adapter, views_by_orientation):
        if checks:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        supplier_checks = []
        displays = annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            formats=supplier.SUPPLIER_REFERENCE_FORMATS,
            starts=supplier.SUPPLIER_REFERENCE_STARTS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )
        stations = shelve_supplier_text(adapter, displays, SHELVES)
        checks.append(
            lambda: assert_supplier_shelves(
                adapter, supplier_checks[0](), SHELVES, stations
            )
        )

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=checks,
        unit=part_drawing_unit("sh-vn-brass-fillister-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

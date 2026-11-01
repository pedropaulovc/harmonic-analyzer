"""Create the purchased reference drawing for the transgear disc screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
# The supplier's references less its stock length: the views show the screw
# as cut, and the ITEM row names the 1/4 stock.
from pd_vn_transgear_disc_screw_spec import (
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


async def build(adapter: Any) -> dict[str, str]:
    supplier_checks = []
    callback_count = 0
    settled = False

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            sides=SUPPLIER_REFERENCE_SIDES,
            settled_checks=supplier_checks,
        )

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        supplier_checks[0]()
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

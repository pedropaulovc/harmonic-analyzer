"""Create the purchased reference drawing for the transgear arm-plate screw."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from _machinist_review_mode import MachinistReviewMode
import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
from pd_vn_transgear_arm_plate_screw_spec import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_SIDES,
    SUPPLIER_REFERENCE_FORMATS,
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_arm_plate_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#8-32 x 1 OVAL HEAD SLOTTED SCREW"
# Only the sizes a replacement and the cut need beyond ITEM: the head
# diameter, the plate countersink's fit, and the as-cut length under the head
# the views show (machinist review round 6), a reference the MHA-PD-00 cut
# step governs. ITEM already names the #8-32 thread and 1 in stock, and the
# installed screw is cut shorter, so a stock length ended in empty space.
# The standard oval head's 82 deg angle and .052 REF crown are not replacement
# criteria. The part's reference sketch still authors the unprinted rows by
# design; FRONT imports only the cut length.
PRINTED_REFERENCES = ("SupplierHeadDiameter", "SupplierCutLength")


def _printed_rows() -> tuple[tuple[str, float, str], ...]:
    rows = {row[0]: row for row in SUPPLIER_REFERENCE_DIMENSIONS}
    missing = [name for name in PRINTED_REFERENCES if name not in rows]
    if missing:
        raise ValueError(f"printed supplier references are not authored: {missing}")
    return tuple(rows[name] for name in PRINTED_REFERENCES)


def _printed(settings: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in settings.items() if name in PRINTED_REFERENCES}


async def build(adapter: Any) -> dict[str, str]:
    # At the standard layout's short Top cell the Top view only fits at 1:2.
    # The taller supplier Top cell fits 1:1 and shelves the head diameter's
    # text beside its arrows.
    view_layout = "supplier_top"
    supplier_checks = []
    callback_count = 0
    settled = False
    dimensions = _printed_rows()
    planes = _printed(SUPPLIER_REFERENCE_PLANES)
    sides = _printed(SUPPLIER_REFERENCE_SIDES)

    def supplier_dimensions(adapter, views_by_orientation):
        nonlocal callback_count
        callback_count += 1
        if callback_count != 1:
            raise RuntimeError("supplier dimensions callback must run exactly once")
        annotate_supplier_screw(
            adapter,
            views_by_orientation,
            dimensions=dimensions,
            formats=_printed(SUPPLIER_REFERENCE_FORMATS),
            starts=_printed(SUPPLIER_REFERENCE_STARTS),
            planes=planes,
            sides=sides,
            settled_checks=supplier_checks,
            layout=view_layout,
        )

    def assert_supplier_dimensions_settled():
        nonlocal settled
        if settled or callback_count != 1 or len(supplier_checks) != 1:
            raise RuntimeError("supplier dimensions require exactly one settled proof")
        supplier_checks[0]()
        settled = True

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, cut_to_suit=True, view_layout=view_layout,
        supplier_margins=supplier_screw_margins(dimensions, planes=planes, sides=sides),
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions_settled,),
        unit=part_drawing_unit(SPEC.artifact_stem),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

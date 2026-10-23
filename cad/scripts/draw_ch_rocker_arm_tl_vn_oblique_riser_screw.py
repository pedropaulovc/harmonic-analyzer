"""Create the purchased reference drawing for the oblique-trammel riser screw."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import NumberFit, build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _supplier_screw_layout import supplier_screw_margins
import ch_rocker_arm_tl_vn_oblique_riser_screw_spec as supplier


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_riser_screw"]
# The footer's ITEM row: the fastener table's callout for the bought screw.
ITEM = "#4-40 X 5/8 B18.6.3 FLAT HEAD"
# Only the sizes needed to buy a replacement: length, head diameter (the
# riser countersink's fit) and thread. The 82 deg head angle and head height
# follow from the B18.6.3 flat head in ITEM. The part's reference sketch still
# authors the unprinted rows by design; the targeted import deletes them.
PRINTED_REFERENCES = ("SupplierLength", "SupplierHeadDiameter", "SupplierThreadDiameter")


def _printed_rows() -> tuple[tuple[str, float, str], ...]:
    rows = {row[0]: row for row in supplier.SUPPLIER_REFERENCE_DIMENSIONS}
    missing = [name for name in PRINTED_REFERENCES if name not in rows]
    if missing:
        raise ValueError(f"printed supplier references are not authored: {missing}")
    return tuple(rows[name] for name in PRINTED_REFERENCES)


def _printed(settings: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in settings.items() if name in PRINTED_REFERENCES}


async def build(adapter: Any) -> dict[str, str]:
    checks = []
    dimensions = _printed_rows()
    planes = _printed(supplier.SUPPLIER_REFERENCE_PLANES)
    sides = _printed(supplier.SUPPLIER_REFERENCE_SIDES)
    # The 18-character registry number overruns the template's DWG. NO.
    # cell into REV; fit it there, measured.
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        number_fit=NumberFit.SHRINK_TO_CELL,
        supplier_dimensions=partial(
            annotate_supplier_screw,
            dimensions=dimensions,
            formats=_printed(supplier.SUPPLIER_REFERENCE_FORMATS),
            starts=_printed(supplier.SUPPLIER_REFERENCE_STARTS),
            planes=planes,
            sides=sides,
            settled_checks=checks,
        ),
        supplier_margins=supplier_screw_margins(dimensions, planes=planes, sides=sides),
        settled_checks=checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

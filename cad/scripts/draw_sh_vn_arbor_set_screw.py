"""Create the shared MHA-SH-VN-54 reference sheet for McMaster 91375A106."""

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
import sh_vn_arbor_set_screw_spec as supplier
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_arbor_set_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 x 1/4 SOCKET SET SCREW, CUP POINT"
# The Top view carries lanes above and below; in the standard 64 mm Top cell
# that left 12 mm, so the 1/4 in screw fit only at 1:4. The taller supplier
# Top cell leaves 18 mm and fits 2:1.
VIEW_LAYOUT = "supplier_top"
# Each span is shorter than its text, so the witnesses ran through it: shelve
# the text past its outer witness. The thread diameter's two-line text (with
# 4-40 below) sits on the Top's upper lane, the hex socket on its lower one.
SHELVES = {
    "SupplierLength": (False, "right"),
    "SupplierThreadDiameter": (True, "right"),
    "SupplierDriveWidth": (True, "right"),
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
        view_layout=VIEW_LAYOUT,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=supplier_screw_margins(
            supplier.SUPPLIER_REFERENCE_DIMENSIONS,
            planes=supplier.SUPPLIER_REFERENCE_PLANES,
            sides=supplier.SUPPLIER_REFERENCE_SIDES,
        ),
        settled_checks=checks,
        unit=part_drawing_unit("sh-vn-arbor-set-screw"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

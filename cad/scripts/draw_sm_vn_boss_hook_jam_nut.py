"""Create the purchased reference drawing for the counter-anchor jam nut (MHA-SM-VN-55, McMaster 90760A140)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_nut_drawing import add_supplier_nut_dimensions
from _supplier_screw_layout import supplier_screw_margins
import sm_vn_boss_hook_jam_nut_spec as supplier


SPEC = DRAWINGS_BY_NAME["sm_vn_boss_hook_jam_nut"]
ITEM = "#10-24 NARROW-PROFILE HEX NUT"
# Shared Front budget includes the bottom nominal-major/thread callout; its
# 20 mm top reservation also covers the physical AF fraction 8 mm above Front.
# Tuple order is (left, bottom, right, top), in sheet metres.
SUPPLIER_MARGINS = supplier_screw_margins(
    supplier.SUPPLIER_REFERENCE_DIMENSIONS,
    sides={"ThreadNominalMajor": "bottom"},
)
SUPPLIER_MARGINS["*Right"] = (0.007, 0.018, 0.007, 0.0)


def _supplier_dimensions(
    adapter: Any, views_by_orientation: dict[str, Any]
) -> Callable[[], None]:
    return add_supplier_nut_dimensions(
        adapter,
        views_by_orientation,
        across_flats_mm=supplier.ACROSS_FLATS,
        thickness_mm=supplier.THICKNESS,
        bore_diameter_mm=supplier.BORE_DIA,
        thread=supplier.THREAD,
        precision=supplier.DRAWING_REFERENCE_PRECISION,
        fraction_denominator=supplier.SUPPLIER_FRACTION_DENOMINATOR,
        reference_dimensions=supplier.SUPPLIER_REFERENCE_DIMENSIONS,
        reference_starts=supplier.SUPPLIER_REFERENCE_STARTS,
    )


async def build(adapter: Any) -> dict[str, str]:
    authored_checks: list[Callable[[], None]] = []

    def supplier_dimensions(target: Any, views: dict[str, Any]) -> None:
        authored_checks.append(_supplier_dimensions(target, views))

    def assert_settled() -> None:
        if len(authored_checks) != 1:
            raise RuntimeError("supplier nut annotations must be authored exactly once")
        authored_checks[0]()

    # Every purchased view is hidden-lines-removed (rule 9), which also clears
    # the dashed bore the r6/r7 reviews flagged in the TOP/RIGHT views.
    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_settled,),
        unit=part_drawing_unit("sm-vn-boss-hook-jam-nut"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

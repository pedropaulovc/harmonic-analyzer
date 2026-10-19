"""Create the purchased reference drawing for the wheel axle nut (MHA-VN-025, McMaster 92671A005)."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_nut_drawing import add_supplier_nut_dimensions
import vn_wheel_axle_nut_spec as supplier


SPEC = DRAWINGS_BY_NAME["vn_wheel_axle_nut"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4-40 HEX NUT"
# Sheet metres, (left, bottom, right, top). Reserve the AF fraction above
# Front and its 13-character thread note 8 mm beyond the right outline.
# Right's centred height text also needs lateral room outside its short span.
SUPPLIER_MARGINS = {
    "*Front": (0.0, 0.0, 0.041, 0.018),
    "*Right": (0.008, 0.018, 0.008, 0.0),
}


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
    )


async def build(adapter: Any) -> dict[str, str]:
    authored_checks: list[Callable[[], None]] = []

    def supplier_dimensions(target: Any, views: dict[str, Any]) -> None:
        authored_checks.append(_supplier_dimensions(target, views))

    def assert_settled() -> None:
        if len(authored_checks) != 1:
            raise RuntimeError("supplier nut annotations must be authored exactly once")
        authored_checks[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

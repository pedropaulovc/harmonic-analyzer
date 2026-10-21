"""Purchased reference drawing for MHA-PD-VN-64 McMaster 93600A189."""
from __future__ import annotations

import argparse
import sys
from typing import Any
from collections.abc import Callable

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_drawing import DOWEL_SUPPLIER_MARGINS, add_supplier_dowel_dimensions
from pd_vn_transgear_arm_plate_locating_pin_spec import SUPPLIER_REFERENCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_arm_plate_locating_pin"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "DOWEL PIN, ISO 2338 m6"


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        proofs.append(add_supplier_dowel_dimensions(adapter, views_by_orientation, SUPPLIER_REFERENCE))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("arm-plate locating pin supplier callback must run exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=DOWEL_SUPPLIER_MARGINS,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem], nargs="?", default=SPEC.artifact_stem)
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

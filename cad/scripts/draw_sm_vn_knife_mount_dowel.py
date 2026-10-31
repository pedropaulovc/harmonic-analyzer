"""Create the purchased reference drawing for the knife-mount dowel."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from collections.abc import Callable

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_pin_drawing import DOWEL_SUPPLIER_MARGINS, add_supplier_dowel_dimensions
from sm_vn_knife_mount_dowel_spec import SUPPLIER_REFERENCE


SPEC = DRAWINGS_BY_NAME["sm_vn_knife_mount_dowel"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø1/8 x 3/4 DOWEL PIN"


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        proofs.append(add_supplier_dowel_dimensions(adapter, views_by_orientation, SUPPLIER_REFERENCE))

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("knife-mount dowel supplier callback must run exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=DOWEL_SUPPLIER_MARGINS,
        unit=part_drawing_unit("sm-vn-knife-mount-dowel"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

"""Create the purchased reference drawing for the MHA-DT-12-TL-VN-50 cam fixture stub."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_pin_drawing import DOWEL_SUPPLIER_MARGINS, add_supplier_dowel_dimensions
from dt_cylinder_gear_tl_vn_cam_stub_spec import SUPPLIER_REFERENCE

SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_vn_cam_stub"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "Ø3/8 x 3/4 PULL-OUT DOWEL PIN, 10-32 TAPPED"


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def supplier_dimensions(adapter: Any, views_by_orientation: dict[str, Any]) -> None:
        proofs.append(
            add_supplier_dowel_dimensions(
                adapter, views_by_orientation, SUPPLIER_REFERENCE
            )
        )

    def assert_supplier_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError(
                "cam fixture stub supplier callback must run exactly once"
            )
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=supplier_dimensions,
        settled_checks=(assert_supplier_dimensions,),
        supplier_margins=DOWEL_SUPPLIER_MARGINS,
        unit=part_drawing_unit("dt-cylinder-gear-tl-vn-cam-stub"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

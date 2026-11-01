"""Create the purchased reference drawing for the wheel axle front washer (MHA-MG-VN-55, McMaster 92916A250)."""

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
from _supplier_washer_drawing import supplier_washer_dimensions
import mg_vn_wheel_axle_front_washer_spec as part


SPEC = DRAWINGS_BY_NAME["mg_vn_wheel_axle_front_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#4 FLAT WASHER"
# Sheet-metre reserves: 12 mm face picks plus the supplier screw callout,
# and a 14 mm Top thickness pick plus native stacked-limit ink.
SUPPLIER_MARGINS = {
    "*Front": (0.0, 0.008, 0.040, 0.006),
    "*Top": (0.0, 0.008, 0.035, 0.008),
}


def _supplier_dimensions(
    adapter: Any, views: dict[str, Any]
) -> Callable[[], None]:
    return supplier_washer_dimensions(
        adapter,
        views,
        axis="z",
        bore_mm=part.ID,
        outer_mm=part.OD,
        thickness_mm=part.MODEL_THICKNESS,
        units=part.SUPPLIER_UNITS,
        precision=part.DRAWING_REFERENCE_PRECISION,
        bands=part.SUPPLIER_TOLERANCES,
        bore_callout=part.SUPPLIER_BORE_CALLOUT,
    )


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[Callable[[], None]] = []

    def dimensions(adapter: Any, views: dict[str, Any]) -> None:
        proofs.append(_supplier_dimensions(adapter, views))

    def assert_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("supplier washer dimensions must be authored exactly once")
        proofs[0]()

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_dimensions,),
        unit=part_drawing_unit("mg-vn-wheel-axle-front-washer"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

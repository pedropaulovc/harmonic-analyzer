"""Create the purchased reference sheet for MHA-SM-VN-54 knife-hanger washer."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_washer_drawing import supplier_washer_dimensions
import sm_vn_knife_hanger_washer_spec as part

SPEC = DRAWINGS_BY_NAME["sm_vn_knife_hanger_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#10 SAE FLAT WASHER"
# Sheet-metre ink reserves: face picks are 12 mm right plus the supplier
# diameter/callout width; the 14 mm thickness pick carries stacked limits.
SUPPLIER_MARGINS = {
    "*Top": (0.0, 0.008, 0.040, 0.006),
    "*Front": (0.0, 0.008, 0.035, 0.008),
}


def _supplier_dimensions(
    adapter: Any, views: dict[str, Any]
) -> Callable[[], None]:
    return supplier_washer_dimensions(
        adapter,
        views,
        axis="y",
        bore_mm=part.ID,
        outer_mm=part.OD,
        thickness_mm=part.THICKNESS,
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
        unit=part_drawing_unit("sm-vn-knife-hanger-washer"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

"""Create the purchased reference sheet for MHA-VN-060 knife-hanger washer."""

from __future__ import annotations

import argparse
from collections.abc import Callable
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_washer_drawing import supplier_washer_dimensions
import vn_knife_hanger_washer_spec as part

SPEC = DRAWINGS_BY_NAME["vn_knife_hanger_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#10 SAE FLAT WASHER"


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
        settled_checks=(assert_dimensions,),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

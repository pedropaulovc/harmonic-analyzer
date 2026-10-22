"""Create the purchased reference sheet for MHA-PD-VN-67 transgear pivot shim."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build
from _supplier_washer_drawing import SupplierWasherProof, supplier_washer_dimensions
import pd_vn_transgear_pivot_shim_spec as part

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_shim"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "DIN 988 SHIM RING"
# Sheet-metre reserves include the 12 mm diameter picks and two-line
# unilateral bands; the 14 mm thickness pick has its own band ink reserve.
SUPPLIER_MARGINS = {
    "*Top": (0.0, 0.008, 0.040, 0.008),
    "*Front": (0.0, 0.006, 0.035, 0.006),
}


def _supplier_dimensions(
    adapter: Any, views: dict[str, Any]
) -> SupplierWasherProof:
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
    )


async def build(adapter: Any) -> dict[str, str]:
    proofs: list[SupplierWasherProof] = []

    def dimensions(adapter: Any, views: dict[str, Any]) -> None:
        proofs.append(_supplier_dimensions(adapter, views))

    def assert_dimensions() -> None:
        if len(proofs) != 1:
            raise RuntimeError("supplier washer dimensions must be authored exactly once")
        proofs[0]()

    def saved_dimensions(adapter: Any, path: Path) -> None:
        if len(proofs) != 1:
            raise RuntimeError("supplier washer dimensions must be authored exactly once before saved proof")
        saved = proofs[0].saved_check
        proofs.clear()
        saved(adapter, path)

    return await build_purchased_fastener_drawing(
        adapter,
        SPEC,
        item=ITEM,
        supplier_dimensions=dimensions,
        supplier_margins=SUPPLIER_MARGINS,
        settled_checks=(assert_dimensions,),
        saved_check=saved_dimensions,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

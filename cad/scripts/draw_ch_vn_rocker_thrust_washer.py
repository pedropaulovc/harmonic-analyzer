"""Create the purchased reference sheet for MHA-CH-VN-56 rocker thrust washer."""

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
import ch_vn_rocker_thrust_washer_spec as part

SPEC = DRAWINGS_BY_NAME["ch_vn_rocker_thrust_washer"]
# The final +Z face is Front; Top is parallel to its thickness witness.
# Reserve 12 mm face/14 mm side picks plus supplier band/limit ink widths.
# Front/Top share outer X bounds, so both need the face's 40 mm right reserve.
# Front's equal bottom/top reserves already align Y with the uninset Right.
SUPPLIER_MARGINS = {
    "*Front": (0.0, 0.008, 0.040, 0.008),
    "*Top": (0.0, 0.006, 0.040, 0.006),
}


def _supplier_dimensions(
    adapter: Any, views: dict[str, Any]
) -> SupplierWasherProof:
    return supplier_washer_dimensions(
        adapter,
        views,
        axis="z",
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
        item="RING SHIM",
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

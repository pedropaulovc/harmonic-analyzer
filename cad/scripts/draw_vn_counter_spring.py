"""Supplier free/max reference dimensions beside the installed 1330K524 spring.

Both supplier states retain the source's two touching bodies. The installed
pictorial, calibration notes, material and source identity stay unchanged.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_spring_drawing import build_supplier_spring_drawing
from _supplier_extension_spring import extension_spring_dimensions
import vn_counter_spring_spec as supplier


SPEC = DRAWINGS_BY_NAME["vn_counter_spring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "EXTENSION SPRING, DOUBLE-LOOP ENDS, 1/2 OD x 0.063 WIRE"
PART_STEM = SPEC.artifact_stem


def _supplier_dimensions(adapter: Any, views: dict[str, Any]) -> tuple[Callable[[], None], ...]:
    return extension_spring_dimensions(
        adapter, views, free_length_mm=supplier.FREE_LENGTH_MM,
        max_length_mm=supplier.MAX_LENGTH_MM, coil_od_mm=supplier.SUPPLIER_COIL_OD_MM,
        wire_dia_mm=supplier.SUPPLIER_WIRE_DIA_MM, precision=supplier.SUPPLIER_PRECISION,
    )


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM, dimensions=_supplier_dimensions, maximum=True,
        spring_metadata=True,
        supplier_margins={
            "free_front": (0.0, 0.0, 0.0, 0.018),
            "free_right": (0.0, 0.018, 0.045, 0.018),
            "max_front": (0.0, 0.0, 0.0, 0.018),
        },
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

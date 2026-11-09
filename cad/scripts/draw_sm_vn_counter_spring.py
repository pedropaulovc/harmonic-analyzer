"""The installed 1330K524 counter spring, with its catalogue sizes as REF data.

Only the installed state is drawn: the source's two touching solid bodies.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _part_properties import part_drawing_unit
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _supplier_spring_drawing import build_supplier_spring_drawing, extension_spring_data
import sm_vn_counter_spring_spec as supplier

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_vn_counter_spring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "EXTENSION SPRING, DOUBLE-LOOP ENDS"
PART_STEM = SPEC.artifact_stem
SUPPLIER_DATA = extension_spring_data(
    free_length_mm=supplier.FREE_LENGTH_MM,
    max_length_mm=supplier.MAX_LENGTH_MM,
    coil_od_mm=supplier.SUPPLIER_COIL_OD_MM,
    wire_dia_mm=supplier.SUPPLIER_WIRE_DIA_MM,
    precision=supplier.SUPPLIER_PRECISION,
    ends="LOOPS",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM, installed_front=True, spring_metadata=True,
        supplier_data=SUPPLIER_DATA, installed_caption="ISOMETRIC",
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

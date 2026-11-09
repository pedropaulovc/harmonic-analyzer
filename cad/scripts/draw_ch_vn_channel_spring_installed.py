"""The installed 9432K31 channel spring, with its catalogue sizes as REF data.

Only the installed state is drawn; the supplier free/maximum lengths and
sections are footer reference data, never physical spring states.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _supplier_spring_drawing import build_supplier_spring_drawing, extension_spring_data
import ch_vn_channel_spring_installed_spec as supplier


SPEC = DRAWINGS_BY_NAME["ch_vn_channel_spring_installed"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "EXTENSION SPRING, HOOK ENDS"
PART_STEM = SPEC.artifact_stem
SUPPLIER_DATA = extension_spring_data(
    free_length_mm=supplier.FREE_LENGTH_MM,
    max_length_mm=supplier.MAX_LENGTH_MM,
    coil_od_mm=supplier.SUPPLIER_COIL_OD_MM,
    wire_dia_mm=supplier.SUPPLIER_WIRE_DIA_MM,
    precision=supplier.SUPPLIER_PRECISION,
    ends="HOOKS",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM, installed_front=True, spring_metadata=True,
        supplier_data=SUPPLIER_DATA, installed_caption="ISOMETRIC",
        unit=part_drawing_unit("ch-vn-channel-spring-installed"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

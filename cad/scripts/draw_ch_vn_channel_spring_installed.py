"""The installed 9432K31 channel spring: a tier-2 specification-control sheet.

Only the installed state is drawn. The footer prints the supplier's catalogue
tolerances on rate, initial tension and coil OD as acceptance limits; the
free/maximum lengths and wire, which it states no tolerance on, print as REF
and are never physical spring states (#2886, owner ruling 2026-11-17).
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
from _supplier_spring_drawing import (
    SPEC_CONTROL_HEADING,
    build_supplier_spring_drawing,
    extension_spring_spec_control_data,
)
import ch_vn_channel_spring_installed_spec as supplier


SPEC = DRAWINGS_BY_NAME["ch_vn_channel_spring_installed"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "EXTENSION SPRING, HOOK ENDS"
PART_STEM = SPEC.artifact_stem
SUPPLIER_DATA = extension_spring_spec_control_data(
    free_length_mm=supplier.FREE_LENGTH_MM,
    max_length_mm=supplier.MAX_LENGTH_MM,
    coil_od_mm=supplier.SUPPLIER_COIL_OD_MM,
    coil_od_tolerance_mm=supplier.SUPPLIER_COIL_OD_TOLERANCE_MM,
    wire_dia_mm=supplier.SUPPLIER_WIRE_DIA_MM,
    rate_n_per_mm=supplier.SPRING_RATE_N_PER_MM,
    rate_tolerance_fraction=supplier.SPRING_RATE_TOLERANCE_FRACTION,
    initial_tension_n=supplier.INITIAL_TENSION_N,
    initial_tension_tolerance_n=supplier.INITIAL_TENSION_TOLERANCE_N,
    precision=supplier.SUPPLIER_PRECISION,
    ends="HOOKS",
)


def build(adapter: Any) -> dict[str, str]:
    return build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM, installed_front=True, spring_metadata=True,
        supplier_data=SUPPLIER_DATA, supplier_data_heading=SPEC_CONTROL_HEADING,
        installed_caption="ISOMETRIC",
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

"""Supplier nominal dimension diagrams beside the unchanged installed 9714K24 envelope."""

from __future__ import annotations

import argparse
from functools import partial
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _supplier_disc_spring_drawing import (
    prepare_supplier_disc_diagram,
    supplier_disc_reference_features,
    supplier_disc_spring_dimensions,
)
from _supplier_spring_drawing import build_supplier_spring_drawing
from _supplier_spring_reference import SUPPLIER_DIAGRAM_CONFIGURATION
import ch_vn_rocker_bank_spring_spec as supplier_spec


SPEC = DRAWINGS_BY_NAME["ch_vn_rocker_bank_spring"]
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "WAVE DISC SPRING"


async def build(adapter: Any) -> dict[str, str]:
    settled_checks = []
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM,
        stock_configuration=SUPPLIER_DIAGRAM_CONFIGURATION,
        prepare_views=partial(prepare_supplier_disc_diagram, spec=supplier_spec),
        supplier_reference_features=supplier_disc_reference_features(supplier_spec),
        include_right=False,
        stock_caption="SUPPLIER NOMINAL DIMENSION DIAGRAM — NOT PART SHAPE",
        supplier_margins={
            "free_front": (0.035, 0.0, 0.035, 0.0),
            "free_top": (0.040, 0.0, 0.040, 0.0),
        },
        supplier_dimensions=partial(
            supplier_disc_spring_dimensions, spec=supplier_spec, settled_checks=settled_checks,
        ),
        installed_caption="INSTALLED ENVELOPE",
        settled_checks=settled_checks,
        unit=part_drawing_unit("ch-vn-rocker-bank-spring"),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

"""Supplier nominal diagrams beside the unchanged installed 9715K43 cone.

The sheet prints only replacement sizes: ID, OD, free height and strip
thickness. The part keeps its catalogue application gauges (compressed
height and the 0.190 shaft circle), which this sheet neither shows nor
dimensions (``SHEET_SPEC``), as MHA-DT-VN-62's sheet does. The 8:1 gauge view
was a prose-named view no parent bounded, and 'FOR SHAFT' named its mate by a
noun (machinist review, fan-out 2026-11-07); the pivot stack's installed
room is MHA-PD-00's, from MHA-PD-VN-57 and the MHA-PD-18 spot face.
"""

from __future__ import annotations

import argparse
from functools import partial
import sys
from types import SimpleNamespace
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
import pd_vn_transgear_pivot_spring_spec as supplier_spec

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_spring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "CURVED DISC SPRING"
# The drawing's view of the spec: identical except for no application gauges.
SHEET_SPEC = SimpleNamespace(
    **{**vars(supplier_spec), "SUPPLIER_APPLICATION_DIMENSIONS": ()}
)


async def build(adapter: Any) -> dict[str, str]:
    settled_checks = []
    return await build_supplier_spring_drawing(
        adapter, SPEC, item=ITEM,
        stock_configuration=SUPPLIER_DIAGRAM_CONFIGURATION,
        prepare_views=partial(prepare_supplier_disc_diagram, spec=SHEET_SPEC),
        supplier_reference_features=supplier_disc_reference_features(SHEET_SPEC),
        include_right=False,
        stock_caption="SUPPLIER NOMINAL DIMENSION DIAGRAM — NOT PART SHAPE",
        supplier_margins={
            "free_front": (0.035, 0.0, 0.035, 0.0),
            "free_top": (0.040, 0.0, 0.040, 0.0),
        },
        supplier_dimensions=partial(
            supplier_disc_spring_dimensions, spec=SHEET_SPEC, settled_checks=settled_checks,
        ),
        installed_caption="INSTALLED CONICAL REPRESENTATION",
        settled_checks=settled_checks,
        unit=part_drawing_unit(SPEC.artifact_stem),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

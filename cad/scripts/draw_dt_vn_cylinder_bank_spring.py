"""Supplier nominal dimension diagrams beside the installed 9714K392 envelope.

The sheet prints only replacement sizes: ID, OD, free height and thickness.
The part keeps its catalogue load-point gauge sketch (compressed height and
deflection at 1.5 lb), which is rating data rather than a replacement size;
the 0.95 mm set gap governs the installed preload.
"""

from __future__ import annotations

import argparse
from functools import partial
from types import SimpleNamespace
import sys
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _supplier_disc_spring_drawing import (
    prepare_supplier_disc_diagram,
    supplier_disc_reference_features,
    supplier_disc_spring_dimensions,
)
from _supplier_spring_drawing import build_supplier_spring_drawing
from _supplier_spring_reference import SUPPLIER_DIAGRAM_CONFIGURATION
import dt_vn_cylinder_bank_spring_spec as supplier_spec


SPEC = DRAWINGS_BY_NAME["dt_vn_cylinder_bank_spring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "WAVE DISC SPRING"
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
        installed_caption="INSTALLED ENVELOPE",
        settled_checks=settled_checks,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

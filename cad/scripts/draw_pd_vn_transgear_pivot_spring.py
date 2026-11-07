"""The installed 9715K43 curved disc spring, with its catalogue sizes as REF data.

The sheet draws the installed cone as projected views and an isometric.
The supplier's ID, OD, free height and strip thickness print as footer
reference data, not as dimension diagrams. The free-state diagrams read as
lines over no spring under prose captions (machinist review, fan-out
2026-11-07, rules 9/26), as the extension springs' gauge views did
(cb2c145caf). The catalogue application gauges (working height, 0.190 shaft)
are not printed. The pivot stack's installed room belongs to MHA-PD-00, from
MHA-PD-VN-57 and the MHA-PD-18 spot face.
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
from _purchased_fastener_drawing import build_purchased_fastener_drawing
import pd_vn_transgear_pivot_spring_spec as supplier_spec

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["pd_vn_transgear_pivot_spring"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "CURVED DISC SPRING"


def _inch(value_mm: float) -> str:
    text = f"{value_mm / supplier_spec.MM_PER_IN:.3f}"
    return text[1:] if text.startswith("0.") else text


# The catalogue sizes, inch REF at the catalogue's three places.
SUPPLIER_DATA = (
    f"ID (Ø{_inch(supplier_spec.ID)}), OD (Ø{_inch(supplier_spec.OD)}).",
    f"FREE HEIGHT ({_inch(supplier_spec.FREE_HEIGHT)}), "
    f"THICKNESS ({_inch(supplier_spec.THICKNESS)}).",
)


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM, supplier_data=SUPPLIER_DATA,
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

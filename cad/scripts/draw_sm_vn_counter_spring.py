"""The installed 1330K524 counter spring, with its catalogue data as REF text.

Only the installed state is drawn: the source's two touching solid bodies.
The ITEM designation, the one note line and the one supplier-data row are
composed in ``sm_vn_counter_spring_notes``.
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
from _supplier_spring_drawing import build_supplier_spring_drawing
from sm_vn_counter_spring_notes import ITEM, SUPPLIER_DATA

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_vn_counter_spring"]
PART_STEM = SPEC.artifact_stem


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

"""Purchased reference sheet for MHA-CH-06-TL-VN-75."""
from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_part_drawing import build_purchased_part_drawing
from _purchased_title_fit import fit_purchased_title_block
from ch_rocker_arm_tl_vn_oblique_pivot_cotter_spec import CALLOUT

SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_vn_oblique_pivot_cotter"]
ITEM = CALLOUT


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_part_drawing(
        adapter,
        SPEC,
        item=ITEM,
        title_block_setup=partial(fit_purchased_title_block, spec=SPEC),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

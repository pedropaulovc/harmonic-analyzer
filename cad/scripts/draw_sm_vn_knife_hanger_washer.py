"""Create the purchased reference sheet for MHA-SM-VN-54 knife-hanger washer."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build

SPEC = DRAWINGS_BY_NAME["sm_vn_knife_hanger_washer"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#10 SAE FLAT WASHER, ID 5.56 x OD 12.70"


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

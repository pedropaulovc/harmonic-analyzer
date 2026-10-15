"""Create the purchased reference sheet for MHA-VN-071 crank seat shim pack."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _session import run_build

SPEC = DRAWINGS_BY_NAME["vn_crank_seat_shim"]


async def build(adapter: Any) -> dict[str, str]:
    # Plain bore: the edge views' dashed bore adds nothing to the solid top view.
    return await build_purchased_fastener_drawing(
        adapter, SPEC, hidden_lines_removed=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[SPEC.artifact_stem])
    parser.parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))

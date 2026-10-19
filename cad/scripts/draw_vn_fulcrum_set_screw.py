"""Create the purchased reference drawing for the fulcrum-shaft set screw (MHA-VN-055, McMaster 91375A942)."""

from __future__ import annotations

import argparse
import sys
from functools import partial
from typing import Any

import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _purchased_fastener_drawing import build_purchased_fastener_drawing
from _supplier_screw_dimensions import annotate_supplier_screw
from _mcmaster_91375a942 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_FORMATS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
)


SPEC = DRAWINGS_BY_NAME["vn_fulcrum_set_screw"]
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "#1-72 x 5/32 SOCKET SET SCREW, CUP POINT"


async def build(adapter: Any) -> dict[str, str]:
    settled_checks = []
    return await build_purchased_fastener_drawing(
        adapter, SPEC, item=ITEM,
        supplier_dimensions=partial(
            annotate_supplier_screw,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            formats=SUPPLIER_REFERENCE_FORMATS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
            settled_checks=settled_checks,
        ),
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

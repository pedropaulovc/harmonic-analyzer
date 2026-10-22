"""Build the gooseneck set screw from McMaster 91410A540."""

from __future__ import annotations

import sys
from functools import partial

from _appearance import PANEL_BLACK
from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_91410a540 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_PLANES,
    SUPPLIER_REFERENCE_STARTS,
)
from diagnostics.diag_build_91410A540 import build_91410A540

PART_NAME = "fr-vn-gooseneck-set-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material



async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(StockComponent("91410A540", build_91410A540),),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
        color=PANEL_BLACK,
    )


if __name__ == "__main__":
    sys.exit(run_build(build))

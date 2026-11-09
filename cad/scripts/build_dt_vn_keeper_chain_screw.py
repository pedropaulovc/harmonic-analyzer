r"""Purchased MHA-DT-VN-70 keeper-chain screw: McMaster 92443A077 in the assembly frame.

The brass #2-56 x 1/4 slotted binding head lands as the MHA-PD-VN-65 pan head
does: head toward -Z, under-head plane at z=0, shank along +Z.  In the crank
frame (``dt_vn_keeper_chain_spec``) the head sits outboard of the MHA-DT-06
arm face and clamps the jack chain's end link through its eye.
"""

from __future__ import annotations

import sys
from functools import partial
from math import pi

from _session import run_build
from _fastener_catalog import fastener
from _stock_fastener import RigidTransform, StockComponent, build_stock_fastener
from _supplier_screw_save import save_supplier_reference_part
from _mcmaster_92443a077 import (
    SUPPLIER_REFERENCE_DIMENSIONS,
    SUPPLIER_REFERENCE_STARTS,
    SUPPLIER_REFERENCE_PLANES,
)
from diagnostics.diag_build_92443A077 import build_92443A077
from dt_vn_keeper_chain_screw_spec import PART_NO

PART_NAME = "dt-vn-keeper-chain-screw"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material


async def build(adapter) -> dict[str, str]:
    return await build_stock_fastener(
        adapter,
        part_name=PART_NAME,
        components=(
            StockComponent(
                sku=PART_NO,
                author=build_92443A077,
                transform=RigidTransform(rotation_radians=(-pi / 2.0, 0.0, 0.0)),
            ),
        ),
        material=MATERIAL,
        save_threaded_part=partial(
            save_supplier_reference_part,
            dimensions=SUPPLIER_REFERENCE_DIMENSIONS,
            starts=SUPPLIER_REFERENCE_STARTS,
            planes=SUPPLIER_REFERENCE_PLANES,
        ),
    )


if __name__ == "__main__":
    sys.exit(run_build(build))

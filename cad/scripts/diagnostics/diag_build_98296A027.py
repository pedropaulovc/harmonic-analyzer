r"""McMaster 98296A027 -- 1050-1095 spring steel slotted spring pin, 1/16 x 1/2.

Catalog page read live on September 25, 2026: 1/16 in diameter, 1/2 in long,
0.012 in wall, for a 0.062-0.065 in hole, ASME B18.8.2, chamfered ends.  No
vendor SLDPRT has been harvested, so there is no native tree to replay.

The recipe models the pin as installed in its 1/16 hole: a tube of the
nominal diameter and the catalog wall, axis along model X, centred on the
origin.  The slot and end chamfers are left out because the catalog gives no
size for either.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_98296A027.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    check,
    define_circle,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import replica_main  # noqa: E402
from pinion_strap_pin_spec import PIN_DIA, PIN_LEN, WALL_T  # noqa: E402

PIN_OD = PIN_DIA
PIN_ID = PIN_DIA - 2.0 * WALL_T
V_PIN = math.pi * (PIN_OD**2 - PIN_ID**2) / 4.0 * PIN_LEN


async def build_98296A027(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_sketch pin section", await adapter.create_sketch("Right"))
    await define_circle(adapter, 0.0, 0.0, PIN_OD / 2.0, "pin OD")
    await define_circle(adapter, 0.0, 0.0, PIN_ID / 2.0, "pin bore")
    check("exit_sketch pin section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinSection")
    check(
        "extrude pin",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PIN_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinBody")
    await volume_check(adapter, "spring pin tube", V_PIN, 0.005 * V_PIN)


if __name__ == "__main__":
    sys.exit(replica_main("98296A027", build_98296A027))

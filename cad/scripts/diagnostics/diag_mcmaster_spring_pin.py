r"""Shared recipe for the McMaster 98296A* slotted spring pins.

Catalogue: each size's own McMaster product page, read live (98296A027 on
2026-09-25, 98296A026 on 2026-09-30; dt-logs transgear-evidence
mcmaster-skus.md): 1050-1095 spring steel, unplated, ASME B18.8.2, chamfered
ends, 0.012 in wall, for a 0.062-0.065 in hole; no diameter tolerance
stated.  No vendor SLDPRT has been harvested for either size, so there is no
native tree to replay.

The recipe models the pin as installed in its hole: a tube of the nominal
diameter and the catalogue wall, axis along model X, centred on the origin.
The slot and end chamfers are left out because the catalogue gives no size
for either.

The size table is pure data: module import pulls in no SolidWorks helper,
so the pin specs read it.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

MM_PER_IN = 25.4

SPRING_PIN_SIZES = {
    # part:        (nominal dia, length), mm
    "98296A027": (MM_PER_IN / 16.0, MM_PER_IN / 2.0),  # 1/16 x 1/2
    "98296A026": (MM_PER_IN / 16.0, 9.0 * MM_PER_IN / 16.0),  # 1/16 x 9/16
}
# Catalogue wall (every size above).
WALL_T = 0.012 * MM_PER_IN


def spring_pin_bore(part_no: str) -> float:
    """The tube's bore, mm: the nominal diameter less the catalogue wall."""
    return SPRING_PIN_SIZES[part_no][0] - 2.0 * WALL_T


def spring_pin_volume(part_no: str) -> float:
    """The recipe's solid volume, mm^3: the nominal tube."""
    dia, length = SPRING_PIN_SIZES[part_no]
    return math.pi * (dia**2 - spring_pin_bore(part_no) ** 2) / 4.0 * length


async def build_spring_pin(adapter, part_no: str) -> None:
    from _common import check, define_circle, name_last_feature, volume_check
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dia, length = SPRING_PIN_SIZES[part_no]
    check("create_sketch pin section", await adapter.create_sketch("Right"))
    await define_circle(adapter, 0.0, 0.0, dia / 2.0, "pin OD")
    await define_circle(adapter, 0.0, 0.0, spring_pin_bore(part_no) / 2.0, "pin bore")
    check("exit_sketch pin section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinSection")
    check(
        "extrude pin",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=length, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinBody")
    volume = spring_pin_volume(part_no)
    await volume_check(adapter, "spring pin tube", volume, 0.005 * volume)

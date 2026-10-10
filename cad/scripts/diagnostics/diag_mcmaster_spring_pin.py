r"""Shared recipe for the McMaster 98296A* slotted spring pins.

Catalogue: each size's own McMaster product page, read live (98296A027 on
2026-09-25, 98296A026 on 2026-09-30, 98296A031 on 2026-10-02; dt-logs
transgear-evidence mcmaster-skus.md): 1050-1095 spring steel, unplated,
ASME B18.8.2, chamfered ends, 0.012 in wall, for a 0.062-0.065 in hole; no
diameter tolerance stated.  No vendor SLDPRT has been harvested for any
size, so there is no native tree to replay.

The recipe models the pin as installed in its hole: a tube of the nominal
diameter and the catalogue wall, axis along model X, centred on the origin.
The slot and end chamfers are left out because the catalogue gives no size
for either.

The per-SKU size modules are pure data, so the pin specs read them without
folding this recipe machinery into their cache inputs.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))



def spring_pin_bore(size: tuple[float, float], wall_t: float) -> float:
    """The tube's bore, mm: the nominal diameter less the catalogue wall."""
    return size[0] - 2.0 * wall_t


def spring_pin_volume(size: tuple[float, float], wall_t: float) -> float:
    """The recipe's solid volume, mm^3: the nominal tube."""
    dia, length = size
    return math.pi * (dia**2 - spring_pin_bore(size, wall_t) ** 2) / 4.0 * length


async def build_spring_pin(adapter, size: tuple[float, float], wall_t: float) -> None:
    from _common import check, define_circle, name_last_feature, volume_check
    from solidworks_mcp.adapters.base import ExtrusionParameters

    dia, length = size
    check("create_sketch pin section", await adapter.create_sketch("Right"))
    await define_circle(adapter, 0.0, 0.0, dia / 2.0, "pin OD")
    await define_circle(adapter, 0.0, 0.0, spring_pin_bore(size, wall_t) / 2.0, "pin bore")
    check("exit_sketch pin section", await adapter.exit_sketch())
    name_last_feature(adapter, "PinSection")
    check(
        "extrude pin",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=length, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinBody")
    volume = spring_pin_volume(size, wall_t)
    await volume_check(adapter, "spring pin tube", volume, 0.005 * volume)

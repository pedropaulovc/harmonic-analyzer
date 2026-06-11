r"""Reproduction script: knife stay (book ch. 18, pp. 42-43).

The thin anchor rod + strap that steady the knife mount against the
spring pull: a O3 rod running along X above the top frame (from the west
column line past the machine centre) and a flat strap hooked over it,
descending diagonally to the knife block's face. Modeled as ONE part
(rod + strap merged where the strap's upper end overlaps the rod --
the p.43 hooked end collapsed; documented simplification).

Layout: origin on the rod axis at machine x 0 (machine (0, 1086, 0)),
rod along X (local -197..+20), strap from (x -40, rod) down to the
knife-mount stud's west flank at local (10, -36) = machine (10, 1050),
stopping 0.4 short of the stud face (M6.4 reroute: the original drop to
the knife block at (5, 990) crossed the summing-lever plate band, and any
rod hook west of x -40 sends the strap through the channel-lever bank).
Dimensions: cad/DIMENSIONS.md ch. 18 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_knife_stay.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "knife-stay"
MATERIAL = "Plain Carbon Steel"

ROD_DIA = 3.0  # DIMENSIONS.md ch18: thin anchor rod (low)
ROD_X = (-197.0, 20.0)  # west column line -> past centre (low)
STRAP_TOP = (-40.0, 0.0)  # strap hooks the rod here (derived: any hook west
# of -40 sends the strap through the channel-lever bank at y 1063..1069)
STRAP_BOT = (10.0, -36.0)  # knife-mount stud west flank at machine y 1050,
# 0.4 shy of the stud face (derived: a drop to the knife block itself would
# cross the summing-lever plate band x -45..+5 at y 992.9..998)
STRAP_HALF_W = 4.0  # strap 8 wide (z), 2 thick (low)
STRAP_HALF_T = 1.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # 1. Rod along X (revolved rectangle -- no Right-plane mapping risk).
    check("create_sketch rod", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "rod centerline",
        await adapter.add_centerline(ROD_X[0], 0.0, ROD_X[1], 0.0),
    )
    profile = await add_line_chain(
        adapter,
        [
            (ROD_X[0], 0.0),
            (ROD_X[1], 0.0),
            (ROD_X[1], ROD_DIA / 2.0),
            (ROD_X[0], ROD_DIA / 2.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "rod sketch", fix_entities=[centerline, *profile])
    check("exit_sketch rod", await adapter.exit_sketch())
    check("revolve rod", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    rod_len = ROD_X[1] - ROD_X[0]
    expected = math.pi * (ROD_DIA / 2.0) ** 2 * rod_len
    vol = await _volume(adapter)
    print(f"  volume after rod: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"rod volume {vol:.1f} != {expected:.1f}")

    # 2. Diagonal strap (Front sketch quad, mid-plane along Z).
    dx = STRAP_BOT[0] - STRAP_TOP[0]
    dy = STRAP_BOT[1] - STRAP_TOP[1]
    length = math.hypot(dx, dy)
    px, py = -dy / length * STRAP_HALF_T, dx / length * STRAP_HALF_T
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    strap = await add_line_chain(
        adapter,
        [
            (STRAP_TOP[0] - px, STRAP_TOP[1] - py),
            (STRAP_TOP[0] + px, STRAP_TOP[1] + py),
            (STRAP_BOT[0] + px, STRAP_BOT[1] + py),
            (STRAP_BOT[0] - px, STRAP_BOT[1] - py),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "strap sketch", fix_entities=strap)
    check("exit_sketch strap", await adapter.exit_sketch())
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * STRAP_HALF_W, both_directions=True)
        ),
    )
    v_strap = length * 2.0 * STRAP_HALF_T * 2.0 * STRAP_HALF_W
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after strap: {vol:.1f} mm^3 (+{added:.1f}, solid {v_strap:.1f})")
    if not (0.9 * v_strap <= added <= 1.01 * v_strap):
        raise RuntimeError(f"strap: added {added:.1f}, expected ~{v_strap:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

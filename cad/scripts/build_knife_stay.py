r"""Reproduction script: knife stay (book ch. 18, pp. 42-43).

The thin anchor rod + strap that steady the knife mount against the
spring pull: a O3 rod running along X above the top frame (from the west
column line past the machine centre) and a flat strap hooked over it,
descending diagonally to the knife block's face. Modeled as ONE part
(rod + strap merged where the strap's upper end overlaps the rod --
the p.43 hooked end collapsed; documented simplification).

Layout: origin on the rod axis at machine x 0 (machine (0, 1086, 0)),
rod along X (local -197..+20), strap from (x -10, rod) down to the
knife-mount stud's west flank at local (9.7, -33) = machine (9.7, 1053),
its end corner 0.44 short of the stud face and its low corner 1.5 above
the raised top crossbar (top 1051) (M6.4 reroute: the original drop to
the knife block at (5, 990) crossed the summing-lever plate band; M6.5
reroute: the lever spring tabs overhang to x -14.1 / y ~1070.1, so the
hook moved from -40 to -10 to keep the whole strap east of the tab tips).
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
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "knife-stay"
MATERIAL = "Plain Carbon Steel"

ROD_DIA = 3.0  # DIMENSIONS.md ch18: thin anchor rod (low)
ROD_X = (-197.0, 20.0)  # west column line -> past centre (low)
STRAP_TOP = (-10.0, 0.0)  # strap hooks the rod here (M6.5: the levers'
# spring tabs OVERHANG 8 past the hole line to x -14.1 with tab tops at
# y ~1070.1 -- the former -40 hook sent the strap's lower edge through
# the two tab overhangs nearest z 0 (6.03/2.75 mm^3); the whole strap now
# stays east of x -10.9 > -14.1)
STRAP_BOT = (9.7, -33.0)  # knife-mount stud west flank at machine y 1053:
# the strap END CORNER (endpoint + half-thickness perpendicular, the
# steeper M6.5 run puts it at x 10.56) stays 0.44 clear of the stud's
# west tangent plane (x 11) and the strap's low corner (y 1052.5) stays
# 1.5 above the raised crossbar top 1051 (derived: a drop to the knife
# block itself would cross the summing-lever plate band x -45..+5 at
# y 992.9..998)
STRAP_HALF_W = 4.0  # strap 8 wide (z), 2 thick (low)
STRAP_HALF_T = 1.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # 1. Rod along X: an extruded circle, NOT a revolved rectangle -- a
    # 360-degree revolve of an on-axis profile leaves a degenerate axis
    # edge in the b-rep, and every boolean that crosses that axis (the
    # strap below) fails (probed live: extrude+merge and revolve-second
    # both refuse; the extruded rod merges fine). The circle sits on the
    # part origin, so the Right-plane axis-mapping ambiguity is moot.
    check("create_sketch rod", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, 0.0, 0.0, ROD_DIA / 2.0, "rod circle")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    rod_len = ROD_X[1] - ROD_X[0]
    extrude_at_offset(adapter, rod_len, ROD_X[0])
    expected = math.pi * (ROD_DIA / 2.0) ** 2 * rod_len
    vol = await _volume(adapter)
    print(f"  volume after rod: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"rod volume {vol:.1f} != {expected:.1f}")
    res = await adapter.get_mass_properties()
    com_x = float(res.data.center_of_mass[0])
    rod_mid = (ROD_X[0] + ROD_X[1]) / 2.0
    if abs(com_x - rod_mid) > 0.5:
        raise RuntimeError(
            f"rod extruded the wrong way: COM x {com_x:.1f}, expected {rod_mid:.1f}"
        )

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
    # Raw-COM start-offset extrude: the adapter's mid-plane extrusion fails
    # on this direct-db quad ("Failed to create extrusion feature"), while
    # the offset path is the proven recipe for direct-db sketches.
    extrude_at_offset(adapter, 2.0 * STRAP_HALF_W, -STRAP_HALF_W)
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

r"""Reproduction script: transgear latch arm (book ch. 23, pp. 56-59).

The tapered link that carries the knob shaft and swings its fine 24T
pinion into mesh with the rack-pinion disc (engineerguy v4_transgear_008:
latch arm with a hole, pivoting on the rack-pinion stud): a big hub
riding the stud, a small hub carrying the knob shaft, joined by a
tapered web. C2C 66.05 is the ch30 REST (disengaged) state -- the plates
show the knob shaft parked at post-mirror (-65, ~242), its mounted
removable's tips overlapping the disc rim only in XY projection (the
chain plane sits ~56 north of the disc). The ENGAGED state (24T DP30
pinion on the disc, c2c (81.28 + 20.32 + 0.4)/2 = 51.0) is NOT modeled;
how the original single arm serves both centre distances is the open
kinematic riddle of DIMENSIONS.md Appendix C #8.

Layout: big hub on the origin (stud axis along Z), small hub at
(+66.05, 0) -- the assembly rotates the c2c line to the photo direction.
4.5 thick along Z. Dimensions: cad/DIMENSIONS.md ch. 23 (M6.8, derived).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_transgear_latch.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "transgear-latch"
MATERIAL = "Plain Carbon Steel"

BIG_HUB_DIA = 22.0  # rides the rack-pinion stud (low)
SMALL_HUB_DIA = 16.0  # carries the knob shaft (low)
BORE_DIA = 9.6  # both bores ride O9.5 shafts (derived)
C2C = 66.0482  # ch30 rest-state centre distance: stud (0, 253.5) to the
# parked knob shaft (pre-mirror +65.0, 241.78) = hypot(65, 11.72) (scaled)
THICKNESS = 4.5  # along Z (low)
WEB_HALF_AT_BIG = 9.0  # tapered web half-widths (derived: inside hub ODs)
WEB_HALF_AT_SMALL = 6.5


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # 1. Big hub disc.
    check("create_sketch big hub", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, BIG_HUB_DIA / 2.0, "big hub")
    await ensure_fully_defined(adapter, "big hub sketch")
    check("exit_sketch big hub", await adapter.exit_sketch())
    check(
        "extrude big hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    expected = math.pi * (BIG_HUB_DIA / 2.0) ** 2 * THICKNESS
    vol = await _volume(adapter)
    print(f"  volume after big hub: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"big hub volume {vol:.1f} != {expected:.1f}")

    # 2. Small hub disc.
    check("create_sketch small hub", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, C2C, 0.0, SMALL_HUB_DIA / 2.0, "small hub")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "small hub sketch")
    check("exit_sketch small hub", await adapter.exit_sketch())
    check(
        "extrude small hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    expected += math.pi * (SMALL_HUB_DIA / 2.0) ** 2 * THICKNESS
    vol = await _volume(adapter)
    print(f"  volume after small hub: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"small hub volume {vol:.1f} != {expected:.1f}")

    # 3. Tapered web joining the hubs.
    check("create_sketch web", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    web_pts = [
        (0.0, -WEB_HALF_AT_BIG),
        (C2C, -WEB_HALF_AT_SMALL),
        (C2C, WEB_HALF_AT_SMALL),
        (0.0, WEB_HALF_AT_BIG),
    ]
    web = await add_line_chain(adapter, web_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, web, web_pts, label="web")
    await ensure_fully_defined(adapter, "web sketch")
    check("exit_sketch web", await adapter.exit_sketch())
    check(
        "extrude web",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    v_web = (WEB_HALF_AT_BIG + WEB_HALF_AT_SMALL) * C2C * THICKNESS
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after web: {vol:.1f} mm^3 (+{added:.1f}, solid {v_web:.1f})")
    if not (0.5 * v_web <= added <= 1.0 * v_web):
        raise RuntimeError(f"web: added {added:.1f}, expected 50-100% of {v_web:.1f}")
    expected = vol

    # 4. The two bores.
    check("create_sketch bores", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, 0.0, 0.0, BORE_DIA / 2.0, "big bore")
    await define_circle(adapter, C2C, 0.0, BORE_DIA / 2.0, "small bore")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * THICKNESS, both_directions=True)
        ),
    )
    expected -= 2.0 * math.pi * (BORE_DIA / 2.0) ** 2 * THICKNESS
    vol = await _volume(adapter)
    print(f"  volume after bores: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"bores volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: knife mount (book ch. 18, pp. 42-43).

The brass hanger that suspends the summing lever's knife edge from the
top crossbar: an 8 x 8 hardened bar set diamond-wise (edge up) -- the
lever's tube bore rides this top edge -- seated in a brass block, with a
O8 stud rising through the lever tube's central slot and the crossbar's
hole to a nut above. The p.42/43 square-head bolt + stirrup strap detail
is collapsed into block + stud merged with the bar (the stud visually
passes over the bar's mid-section -- documented simplification). The bar
rides entirely inside the lever tube's slot tunnel (z +-15.9 vs slot
+-16): contact bands outside the slot are geometrically impossible --
the diamond's lower flanks would clash with the tube's lower wall -- so
the knife-edge contact is conceptual (M6.4).

Layout: origin ON the knife edge line (machine (15, 990, 0)), edge along
Z. Diamond bar z +-15.9, block below, stud +Y to y +75 (machine 1065).
Dimensions: cad/DIMENSIONS.md ch. 18 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_knife_mount.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    apply_color,
    PANEL_BLACK,
    check,
    define_circle,
    define_polygon_chain,
    define_rectilinear_chain,
    ensure_fully_defined,
    extrude_at_offset,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "knife-mount"
MATERIAL = "Brass"

BAR_SIDE = 8.0  # hardened knife bar, square section set diamond-wise (low)
BAR_LENGTH = 31.8  # inside the lever tube slot (+-16) with 0.1 ends (derived)
BLOCK_HALF_X = 12.0  # brass block 24 x 28 x 24 (low)
BLOCK_TOP_Y = -8.0  # bar's lower half seats 3.3 into the block
BLOCK_HEIGHT = 28.0
BLOCK_HALF_Z = 12.0
STUD_DIA = 8.0  # rises through the slot and crossbar hole (low)
STUD_TOP_Y = 75.0  # machine 1065: nut seat above the crossbar (low)

HALF_DIAG = BAR_SIDE * math.sqrt(2.0) / 2.0  # 5.657


def _stud_bar_overlap() -> float:
    """Stud cylinder (axis Y, r 4) inside the diamond prism, numerically."""
    r = STUD_DIA / 2.0
    n = 200
    total = 0.0
    y0, y1 = -BLOCK_TOP_Y, 0.0  # diamond band the stud crosses: y -8..0
    for i in range(n):
        y = -y0 + (i + 0.5) * (y1 + y0) / n
        w = HALF_DIAG - abs(y + HALF_DIAG)  # diamond half-width at this y
        if w <= 0.0:
            continue
        area = 0.0
        m = 100
        for k in range(m):
            z = -r + (k + 0.5) * 2.0 * r / m
            x_lim = math.sqrt(max(r * r - z * z, 0.0))
            area += 2.0 * min(w, x_lim) * 2.0 * r / m
        total += area * (y1 + y0) / n
    return total


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # 1. Diamond knife bar (Front sketch, mid-plane along Z).
    check("create_sketch bar", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    diamond_pts = [
        (0.0, 0.0),
        (HALF_DIAG, -HALF_DIAG),
        (0.0, -2.0 * HALF_DIAG),
        (-HALF_DIAG, -HALF_DIAG),
    ]
    diamond = await add_line_chain(adapter, diamond_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, diamond, diamond_pts, label="diamond")
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_LENGTH, both_directions=True)
        ),
    )
    expected = BAR_SIDE**2 * BAR_LENGTH
    vol = await _volume(adapter)
    print(f"  volume after bar: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"bar volume {vol:.1f} != {expected:.1f}")

    # 2. Block; the bar's lower vee sinks into its top (merged).
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_HALF_X, BLOCK_TOP_Y - BLOCK_HEIGHT),
        (BLOCK_HALF_X, BLOCK_TOP_Y - BLOCK_HEIGHT),
        (BLOCK_HALF_X, BLOCK_TOP_Y),
        (-BLOCK_HALF_X, BLOCK_TOP_Y),
    ]
    block = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(adapter, block, block_rect, label="block")
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * BLOCK_HALF_Z, both_directions=True)
        ),
    )
    # Overlap: the diamond's tip below BLOCK_TOP_Y is a right-angle vee of
    # depth (2*HALF_DIAG + BLOCK_TOP_Y); its area is depth^2.
    vee_depth = 2.0 * HALF_DIAG + BLOCK_TOP_Y  # 3.314
    v_block = (
        2.0 * BLOCK_HALF_X * BLOCK_HEIGHT * 2.0 * BLOCK_HALF_Z
        - vee_depth**2 * 2.0 * BLOCK_HALF_Z
    )
    expected += v_block
    vol = await _volume(adapter)
    print(f"  volume after block: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"block volume {vol:.1f} != {expected:.1f}")

    # 3. Stud from the block top through the bar band up to the nut seat.
    check("create_sketch stud", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, STUD_DIA / 2.0, "stud")
    await ensure_fully_defined(adapter, "stud sketch")
    check("exit_sketch stud", await adapter.exit_sketch())
    extrude_at_offset(adapter, STUD_TOP_Y - BLOCK_TOP_Y, BLOCK_TOP_Y)
    v_stud = math.pi * (STUD_DIA / 2.0) ** 2 * (STUD_TOP_Y - BLOCK_TOP_Y)
    v_net = v_stud - _stud_bar_overlap()
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after stud: {vol:.1f} mm^3 (+{added:.1f}, net {v_net:.1f})")
    if abs(added - v_net) > 0.02 * v_net:
        raise RuntimeError(f"stud: added {added:.1f}, expected {v_net:.1f}")

    # Named axis = local Z through the origin = the diamond knife edge line,
    # which the summing lever's bore-bottom rocks on (M6 mated-DOF revolute).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "knife axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

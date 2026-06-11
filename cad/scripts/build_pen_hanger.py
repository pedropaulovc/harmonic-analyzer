r"""Reproduction script: pen hanger (book ch. 24, pp. 60-63).

The black tapered strap bolted to the wheel support bar that hangs the
pen rod's upper guide: a flat strap (3 thick) tapering 16 -> 10 wide,
lying on the bar's front face and descending to a deep guide block with
a 5.4 square hole the 5-square pen rod slides in. The block reaches
forward (-Z in the machine) so the pen rod hangs clear of the platen
paper plane while the strap stays flush on the bar. The mounting bolt is
omitted (simplification).

Layout: origin at the guide block centre (machine (-3, 505, -151.5));
block z -4..+12.6 (back face flush with the bar front at machine
z -138.9), strap in the z = 9.6..12.6 band rising +Y to the bar band
(machine y 560..570). Dimensions: cad/DIMENSIONS.md ch. 24 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pen_hanger.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "pen-hanger"
MATERIAL = "Plain Carbon Steel"  # black hardware

BLOCK_HALF = 6.0  # guide block 12 x 12 (low)
BLOCK_Z = (-4.0, 12.6)  # deep block: back face on the bar front (derived)
GUIDE_HOLE_HALF = 2.7  # 5.4 square: the 5-square pen rod slides (derived)
STRAP_Z = (9.6, 12.6)  # strap 3 thick, flush with the block back (derived)
STRAP_TOP_Y = 65.0  # machine 570: support bar top (derived)
STRAP_TOP_X = (0.0, 16.0)  # 16 wide at the bar (low)
STRAP_BOT_X = (-5.0, 5.0)  # 10 wide at the block (low)


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # 1. Guide block with the square rod hole (nested contours).
    check("create_sketch block", await adapter.create_sketch("Front"))
    outline = await add_line_chain(
        adapter,
        [
            (-BLOCK_HALF, -BLOCK_HALF),
            (BLOCK_HALF, -BLOCK_HALF),
            (BLOCK_HALF, BLOCK_HALF),
            (-BLOCK_HALF, BLOCK_HALF),
        ],
    )
    hole = await add_line_chain(
        adapter,
        [
            (-GUIDE_HOLE_HALF, -GUIDE_HOLE_HALF),
            (GUIDE_HOLE_HALF, -GUIDE_HOLE_HALF),
            (GUIDE_HOLE_HALF, GUIDE_HOLE_HALF),
            (-GUIDE_HOLE_HALF, GUIDE_HOLE_HALF),
        ],
    )
    await ensure_fully_defined(adapter, "block sketch", fix_entities=[*outline, *hole])
    check("exit_sketch block", await adapter.exit_sketch())
    extrude_at_offset(adapter, BLOCK_Z[1] - BLOCK_Z[0], BLOCK_Z[0])
    expected = (
        (2.0 * BLOCK_HALF) ** 2 - (2.0 * GUIDE_HOLE_HALF) ** 2
    ) * (BLOCK_Z[1] - BLOCK_Z[0])
    vol = await _volume(adapter)
    print(f"  volume after block: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"block volume {vol:.1f} != {expected:.1f}")

    # 2. Tapered strap rising to the support bar.
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    strap = await add_line_chain(
        adapter,
        [
            (STRAP_BOT_X[0], BLOCK_HALF),
            (STRAP_BOT_X[1], BLOCK_HALF),
            (STRAP_TOP_X[1], STRAP_TOP_Y),
            (STRAP_TOP_X[0], STRAP_TOP_Y),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "strap sketch", fix_entities=strap)
    check("exit_sketch strap", await adapter.exit_sketch())
    extrude_at_offset(adapter, STRAP_Z[1] - STRAP_Z[0], STRAP_Z[0])
    bot_w = STRAP_BOT_X[1] - STRAP_BOT_X[0]
    top_w = STRAP_TOP_X[1] - STRAP_TOP_X[0]
    v_strap = (
        (bot_w + top_w) / 2.0 * (STRAP_TOP_Y - BLOCK_HALF) * (STRAP_Z[1] - STRAP_Z[0])
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after strap: {vol:.1f} mm^3 (+{added:.1f}, solid {v_strap:.1f})")
    if abs(added - v_strap) > 0.02 * v_strap:
        raise RuntimeError(f"strap: added {added:.1f}, expected {v_strap:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

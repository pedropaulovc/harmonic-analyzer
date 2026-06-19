r"""Reproduction script: pen hanger (book ch. 24, pp. 60-63).

The black tapered strap bolted to the wheel support bar that hangs the
pen rod's upper guide: a flat strap (3 thick) tapering 16 -> 10 wide,
lying on the bar's front face and descending to a deep guide block with
a 5.4 square channel the 5-square pen rod slides in -- the rod is
VERTICAL, so the channel is cut along Y through the block (an M6.4 fix:
the first build wrongly tunnelled it along Z). The block reaches
forward (-Z in the machine) so the pen rod hangs clear of the platen
paper plane while the strap stays flush on the bar. M6.10 fasteners
pass: an O3.6 through-hole near the strap top (local (-8.5, 60) =
machine (-5.5, 565): the "x0" placement mirrors the ORIGIN to +3 and
keeps locals as-authored) takes the hanger-screw shank coming through
the bar FROM BEHIND (the magnifying wheel's rim back face passes 1.0 in
front of the strap, so no front-side head fits); the tip sits 0.5
behind the strap front face.

Layout: origin at the guide block centre (machine (+3, 505, -151.5));
block z -4..+12.6 (back face flush with the bar front at machine
z -138.9), strap in the z = 9.6..12.6 band rising +Y to the bar band
(machine y 560..570). M6.8: the strap's sideways lean is the part's only
x-asymmetric feature, so the machine mirror is authored here
(STRAP_TOP_X negated) and the assembly places the part with MIRROR_PLANE
'x0'. Dimensions: cad/DIMENSIONS.md ch. 24 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pen_hanger.py
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
    define_rectilinear_chain,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "pen-hanger"
MATERIAL = "Plain Carbon Steel"  # black hardware

BLOCK_HALF = 6.0  # guide block 12 x 12 (low)
BLOCK_Z = (-4.0, 12.6)  # deep block: back face on the bar front (derived)
GUIDE_HOLE_HALF = 2.7  # 5.4 square: the 5-square pen rod slides (derived)
STRAP_Z = (9.6, 12.6)  # strap 3 thick, flush with the block back (derived)
STRAP_TOP_Y = 65.0  # machine 570: support bar top (derived)
STRAP_TOP_X = (-16.0, 0.0)  # 16 wide at the bar (low; M6.8-mirrored lean)
STRAP_BOT_X = (-5.0, 5.0)  # 10 wide at the block (low)
SCREW_HOLE_DIA = 3.6  # M6.10: hanger-screw hole near the strap top
SCREW_HOLE_XY = (-8.5, 60.0)  # machine (-5.5, 565) = block centre +3 + local:
# within the 5-wide strap/bar overlap east of the bar's free end (machine
# -8); strap band at y 60 is local -15.1..0.4, so the hole sits 4.8/7.1
# from the strap edges


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # 1. Solid guide block.
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_HALF, -BLOCK_HALF),
        (BLOCK_HALF, -BLOCK_HALF),
        (BLOCK_HALF, BLOCK_HALF),
        (-BLOCK_HALF, BLOCK_HALF),
    ]
    outline = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(adapter, outline, block_rect, label="block")
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    extrude_at_offset(adapter, BLOCK_Z[1] - BLOCK_Z[0], BLOCK_Z[0])
    expected = (2.0 * BLOCK_HALF) ** 2 * (BLOCK_Z[1] - BLOCK_Z[0])
    vol = await _volume(adapter)
    print(f"  volume after block: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"block volume {vol:.1f} != {expected:.1f}")

    # 1b. Square rod channel cut along Y (the pen rod hangs vertically).
    # The +-2.7 footprint stays inside the block's z -4..12.6 band and well
    # clear of the strap's z 9.6..12.6 band, so a through cut is safe.
    check("create_sketch channel", await adapter.create_sketch("Top"))
    channel_rect = [
        (-GUIDE_HOLE_HALF, -GUIDE_HOLE_HALF),
        (GUIDE_HOLE_HALF, -GUIDE_HOLE_HALF),
        (GUIDE_HOLE_HALF, GUIDE_HOLE_HALF),
        (-GUIDE_HOLE_HALF, GUIDE_HOLE_HALF),
    ]
    channel = await add_line_chain(adapter, channel_rect)
    await define_rectilinear_chain(adapter, channel, channel_rect, label="channel")
    await ensure_fully_defined(adapter, "channel sketch")
    check("exit_sketch channel", await adapter.exit_sketch())
    check(
        "cut channel",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * BLOCK_HALF, both_directions=True)
        ),
    )
    expected -= (2.0 * GUIDE_HOLE_HALF) ** 2 * 2.0 * BLOCK_HALF
    vol = await _volume(adapter)
    print(f"  volume after channel: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"channel volume {vol:.1f} != {expected:.1f}")

    # 2. Tapered strap rising to the support bar.
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    strap_pts = [
        (STRAP_BOT_X[0], BLOCK_HALF),
        (STRAP_BOT_X[1], BLOCK_HALF),
        (STRAP_TOP_X[1], STRAP_TOP_Y),
        (STRAP_TOP_X[0], STRAP_TOP_Y),
    ]
    strap = await add_line_chain(adapter, strap_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(adapter, strap, strap_pts, label="strap")
    await ensure_fully_defined(adapter, "strap sketch")
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
    expected = vol

    # 3. Hanger-screw hole through the strap (mid-plane cut along Z: at
    # local y 60 only the strap band 9.6..12.6 is material).
    check("create_sketch screw hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, SCREW_HOLE_XY[0], SCREW_HOLE_XY[1], SCREW_HOLE_DIA / 2.0, "screw hole"
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw hole", await adapter.exit_sketch())
    check(
        "cut screw hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * STRAP_Z[1], both_directions=True)
        ),
    )
    expected -= math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * (STRAP_Z[1] - STRAP_Z[0])
    vol = await _volume(adapter)
    print(f"  volume after screw hole: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 1.0:
        raise RuntimeError(f"screw hole volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

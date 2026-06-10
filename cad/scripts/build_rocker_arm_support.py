r"""Reproduction script: rocker arm support A-frame (legacy part, 3 used).

Cast-iron A-frame carrying the rocker-arm shaft: isosceles-trapezoid side
profile (2.50 in base tapering to 2/3 in at the top, 7.00 in tall) extruded
mid-plane to 7.25 in wide, with a 5.00 in square window (0.625 in corner
radii, 1.25 in bottom rail / 0.75 in top rail) cut through and two 5/16 in
mounting holes in the bottom flange. Re-authors RockerArmSupport.cs; the
M1 audit found no book numerics for this part, so the legacy dims stand
(photo-scale sanity: 7 in = 17.8 cm against the 46 cm base reads right in
the ch. 5-6 overview photos).

Deferred: legacy 0.125 in cast-look external fillets (cosmetic, M4 pass).

Dimensions: cad/DIMENSIONS.md "Legacy part audit" - legacy (med).

Layout: legacy orientation - profile on the Right plane (trapezoid depth
along Z, height +Y), frame width extruded mid-plane along X, window cut
from the Front plane. Profile is symmetric in sketch x, so the Right-plane
axis handedness does not matter.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_rocker_arm_support.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "rocker-arm-support"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

IN = 25.4
TOTAL_HEIGHT = 7.00 * IN  # legacy RockerArmSupport.cs (no book numerics)
FRAME_WIDTH = 7.25 * IN  # front-view width, mid-plane extrusion
BASE_DEPTH = 2.50 * IN  # trapezoid base (side view)
TOP_DEPTH = (2.0 / 3.0) * IN  # trapezoid top
WINDOW_SIZE = 5.00 * IN  # square window
WINDOW_CORNER_RADIUS = 0.625 * IN
WINDOW_BOTTOM_RAIL = 1.25 * IN  # material below window (0.75 in above)
MOUNTING_HOLE_DIA = 0.3125 * IN  # 5/16 in clearance
MOUNTING_HOLE_SPACING = 2.5 * IN  # legacy hole pitch across X
HOLE_CUT_DEPTH = 80.0  # mid-plane total; > bottom rail, < window top


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # A-frame trapezoid profile, extruded mid-plane to the frame width.
    check("create_sketch profile", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(
        adapter,
        [
            (-BASE_DEPTH / 2.0, 0.0),
            (BASE_DEPTH / 2.0, 0.0),
            (TOP_DEPTH / 2.0, TOTAL_HEIGHT),
            (-TOP_DEPTH / 2.0, TOTAL_HEIGHT),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "profile sketch", fix_entities=lines)
    check("exit_sketch profile", await adapter.exit_sketch())
    check(
        "extrude A-frame",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=FRAME_WIDTH, both_directions=True)
        ),
    )
    print(f"  volume after A-frame: {await _volume(adapter):.1f} mm^3")
    # expected: (2.5 + 2/3)/2 * 7 * 7.25 in^3 = 80.354 in^3 = 1,316,776 mm^3

    # Window with rounded corners, cut through the trapezoid (along Z).
    check("create_sketch window", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    half = WINDOW_SIZE / 2.0
    bottom = WINDOW_BOTTOM_RAIL
    top = bottom + WINDOW_SIZE
    r = WINDOW_CORNER_RADIUS
    entities = [
        check(
            "window bottom edge",
            await adapter.add_line(-half + r, bottom, half - r, bottom),
        ),
        check(
            "window BR corner",
            await adapter.add_arc(
                half - r, bottom + r, half - r, bottom, half, bottom + r
            ),
        ),
        check(
            "window right edge",
            await adapter.add_line(half, bottom + r, half, top - r),
        ),
        check(
            "window TR corner",
            await adapter.add_arc(half - r, top - r, half, top - r, half - r, top),
        ),
        check(
            "window top edge",
            await adapter.add_line(half - r, top, -half + r, top),
        ),
        check(
            "window TL corner",
            await adapter.add_arc(
                -half + r, top - r, -half + r, top, -half, top - r
            ),
        ),
        check(
            "window left edge",
            await adapter.add_line(-half, top - r, -half, bottom + r),
        ),
        check(
            "window BL corner",
            await adapter.add_arc(
                -half + r, bottom + r, -half, bottom + r, -half + r, bottom
            ),
        ),
    ]
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "window sketch", fix_entities=entities)
    check("exit_sketch window", await adapter.exit_sketch())
    check(
        "cut window",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BASE_DEPTH * 2.5, both_directions=True)
        ),
    )
    print(f"  volume after window: {await _volume(adapter):.1f} mm^3")
    # expected: ~42.92 in^3 = ~703,250 mm^3 (taper-weighted window volume)

    # Mounting holes through the bottom flange.
    check("create_sketch holes", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        -MOUNTING_HOLE_SPACING / 2.0,
        0.0,
        MOUNTING_HOLE_DIA / 2.0,
        "mounting hole left",
    )
    await define_circle(
        adapter,
        MOUNTING_HOLE_SPACING / 2.0,
        0.0,
        MOUNTING_HOLE_DIA / 2.0,
        "mounting hole right",
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    check(
        "cut mounting holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HOLE_CUT_DEPTH, both_directions=True)
        ),
    )
    print(f"  volume after holes: {await _volume(adapter):.1f} mm^3")
    # expected: -2 * pi * (5/32)^2 * 1.25 in^3 = -3,142 mm^3 -> ~700,110 mm^3

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

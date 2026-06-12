r"""Reproduction script: channel (top) lever (book ch. 17, pp. 38-41).

One of the 20 cast third-class levers at the top of the machine: fulcrum
pivot at one end (Ø6.5 hole riding the common Ø6.35 fulcrum shaft - the
p.40 ball clevis is the shaft's END mount, mirroring the rocker-pivot
design), channel-spring pull from a narrow end tab (Ø4 hook hole at
177.8 = 7"), driven in between by its amplitude bar pinned Ø2 at 127
(5"). Section 9.5 tall x 3.0 thick: 20 levers at the 7.0565 channel
pitch cap the thickness (the M2 12.5 "width" violated the pitch), and
3.0 lets the bar's 3.2 top slot straddle the lever at the pin.

The earlier 254 (10", "clean 2:1") length is REFUTED by the calibrated
ch. 30 front view: the lever bank ends at x ~ -30 (not +54), the
summing-lever plate (44.45 wide, pivot bolt read at x ~ +13..17) sits
directly under the tab line, and the 32 mm channel springs can only
bridge lever tab -> plate if the tab holes are at x ~ -22 - i.e.
c2c = 177.8 from the -199.9 fulcrum (motion ratio 177.8/127 = 1.4).
The p.39 close-up also shows the bar pin only ~4-5 bar-heights from the
tip (50.8/9.5 = 5.3 fits; 127/9.5 = 13 does not). The tab itself is the
narrow stepped end visible on p.39/p.41: bar height 9.5 steps to a 6.0
centred tab carrying the spring hole, rounded tip.

Dimensions: cad/DIMENSIONS.md "Chapter 17" - lengths/section derived in
M6.3/M6.4 (med), hole diameters low.

Layout: lever length along +X from the pivot axis at the origin, bar
height in Y, thickness extruded mid-plane in Z. Through-holes use
mid-plane blind cuts (MCP issue #38 workaround).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_channel_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "channel-lever"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

LEVER_SPRING_X = 177.8  # DIMENSIONS.md ch17: fulcrum->spring-hole c2c, 7" (derived,
# M6.4: supersedes the 254 "2:1" guess - see docstring)
BAR_TALL = 9.5  # DIMENSIONS.md ch17: bar height, p.39 vs spring OD (low)
LEVER_THICKNESS = 3.0  # DIMENSIONS.md ch17: fits 7.06 pitch + 3.2 bar slot (derived)
PIVOT_HOLE_DIA = 6.5  # DIMENSIONS.md ch17: rides the 6.35 fulcrum shaft (derived)
BAR_PIN_HOLE_DIA = 2.0  # DIMENSIONS.md ch17: amplitude-bar top pin (derived)
BAR_PIN_X = 127.0  # 5" from the fulcrum (bar line -72.9, fulcrum -199.9)
SPRING_HOLE_DIA = 4.0  # DIMENSIONS.md ch17: sized so the spring's O5.5-mean
# O1-wire eye threads the tab with ~0.3 margins; the O3 photo read (low)
# is infeasible (best margins ~0.05) - see build_channel_assembly.py
# _assert_spring_threading
TAB_START_X = 169.0  # bar steps down to the end tab (p.39/p.41, low)
TAB_HALF = 3.0  # tab 6.0 tall, centred on the bar axis
TIP_RADIUS = 3.0  # rounded tab tip; tip overhang = 182.8 + 3 - 177.8 = 8
TIP_ARC_CX = LEVER_SPRING_X + 5.0  # 182.8

HALF_BAR = BAR_TALL / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > extrude width


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Side profile: round fulcrum nose, flat bar, stepped end tab with a
    # rounded tip (two arcs + 6-line chain).
    check("create_sketch outline", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    nose = check(
        "add_arc fulcrum nose",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_BAR, 0.0, -HALF_BAR),
    )
    lower = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_BAR),
            (TAB_START_X, -HALF_BAR),
            (TAB_START_X, -TAB_HALF),
            (TIP_ARC_CX, -TAB_HALF),
        ],
        close=False,
    )
    tip = check(
        "add_arc tab tip",
        await adapter.add_arc(
            TIP_ARC_CX, 0.0, TIP_ARC_CX, -TAB_HALF, TIP_ARC_CX, TAB_HALF
        ),
    )
    upper = await add_line_chain(
        adapter,
        [
            (TIP_ARC_CX, TAB_HALF),
            (TAB_START_X, TAB_HALF),
            (TAB_START_X, HALF_BAR),
            (0.0, HALF_BAR),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    # Semantic scheme: bar/tab edges horizontal, steps vertical; the nose
    # semicircle is pinned by centre-at-origin + radius + both ends on the
    # Y axis; the tip arc by its centre on the X axis at TIP_ARC_CX +
    # radius + both ends vertically aligned with its centre. One alignment
    # ties the lower step to the upper, one dim carries the bar length.
    lower_bar, lower_step, tab_bottom = lower
    tab_top, upper_step, upper_bar = upper
    for edge in (lower_bar, tab_bottom, tab_top, upper_bar):
        check(f"horizontal {edge}", await adapter.add_sketch_constraint(edge, None, "horizontal"))
    for edge in (lower_step, upper_step):
        check(f"vertical {edge}", await adapter.add_sketch_constraint(edge, None, "vertical"))
    check(
        "nose centre -> origin",
        await adapter.add_sketch_constraint(f"{nose}.center", "origin", "coincident"),
    )
    check("nose radius", await adapter.add_sketch_dimension(nose, None, "radial", HALF_BAR))
    for point in (f"{nose}.start", f"{nose}.end"):
        check(
            f"{point} on Y axis",
            await adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    await anchor_point_to_origin(adapter, f"{tip}.center", TIP_ARC_CX, 0.0, "tip centre")
    check("tip radius", await adapter.add_sketch_dimension(tip, None, "radial", TIP_RADIUS))
    for point in (f"{tip}.start", f"{tip}.end"):
        check(
            f"{point} above/below tip centre",
            await adapter.add_sketch_constraint(point, f"{tip}.center", "vertical_points"),
        )
    check(
        "tab steps aligned",
        await adapter.add_sketch_constraint(
            f"{lower_step}.start", f"{upper_step}.start", "vertical_points"
        ),
    )
    await dimension_between(
        adapter, f"{lower_bar}.start", f"{lower_bar}.end",
        "horizontal_distance", TAB_START_X, "bar length",
    )
    await ensure_fully_defined(adapter, "lever outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude lever",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=LEVER_THICKNESS, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    area = (
        TAB_START_X * BAR_TALL
        + math.pi * HALF_BAR**2 / 2.0
        + (TIP_ARC_CX - TAB_START_X) * 2.0 * TAB_HALF
        + math.pi * TIP_RADIUS**2 / 2.0
    )
    expected = area * LEVER_THICKNESS
    print(f"  volume after extrude: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(
            f"outline volume {vol:.1f} != analytic {expected:.1f} - an arc"
            " bulged the wrong way or the chain snapped"
        )

    # Fulcrum hole + bar-pin hole + spring-hook hole, one mid-plane cut.
    check("create_sketch holes", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, PIVOT_HOLE_DIA / 2.0, "fulcrum hole")
    await define_circle(adapter, BAR_PIN_X, 0.0, BAR_PIN_HOLE_DIA / 2.0, "bar pin hole")
    await define_circle(
        adapter, LEVER_SPRING_X, 0.0, SPRING_HOLE_DIA / 2.0, "spring hole"
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    v_holes = (
        math.pi
        * (
            (PIVOT_HOLE_DIA / 2.0) ** 2
            + (BAR_PIN_HOLE_DIA / 2.0) ** 2
            + (SPRING_HOLE_DIA / 2.0) ** 2
        )
        * LEVER_THICKNESS
    )
    expected -= v_holes
    print(f"  volume after holes: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(
            f"hole-cut volume {vol:.1f} != analytic {expected:.1f}"
        )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

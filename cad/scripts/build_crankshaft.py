r"""Reproduction script: crankshaft (book ch. 11, pp. 12-15).

Short Ø3/8 in steel shaft in the green pedestal bearing at the base
corner: crank arm on the outboard end (affixed by a removable tapered
pin so the crankshaft gear can be changed), chain sprocket and the 4:1
drive pinion inboard. Modeled as the plain shaft with the tapered-pin
cross-hole; the crank arm/pin/handle and the gears are separate parts
(`build_crank_arm.py` etc., gears in M4).

Dimensions: cad/DIMENSIONS.md "Chapter 11" - dia legacy (med), length
derived from eight-views 8/8 pedestal proportions (low).

Layout: shaft axis along +Y, outboard (crank) end at the origin;
tapered-pin cross-hole along Z at the crank-seat height.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crankshaft.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.375 * IN  # ch11: legacy ShaftDiameter, uncontradicted
SHAFT_LENGTH = 120.0  # ch11: derived (crank seat + pedestal bearing + seats)
PIN_HOLE_DIA = 5.0  # ch11: tapered-pin cross-hole, pin small end (photo)
PIN_HOLE_HEIGHT = 12.0  # crank hub centre above the outboard end
THROUGH_CUT_DEPTH = 30.0  # mid-plane total; > shaft dia


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft circle")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after shaft: {res.data.volume:.1f} mm^3")
    # expected: pi * 4.7625^2 * 120 = ~8,551 mm^3

    # Tapered-pin cross-hole through the crank seat (along Z).
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, PIN_HOLE_HEIGHT, PIN_HOLE_DIA / 2.0, "pin hole")
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after pin hole: {res.data.volume:.1f} mm^3")
    # expected: -178 (O5 cross-drill) -> ~8,373 mm^3

    # Named central axis (shaft axis = local +Y through the origin) so the
    # crankshaft mates concentric in the pedestal and the crank parts /
    # pinion / chain wheel lock to it (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

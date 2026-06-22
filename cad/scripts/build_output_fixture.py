r"""Reproduction script: output fixture collar (book ch. 20, p. 48).

The small fixture that slides up and down the vertical rod to set the
trace's vertical placement on the paper; the wire to the magnifying wheel
hooks onto it and a small reeded screw (separate thumb-screw part) locks
it. Modelled as a collar with the rod bore and one cross hole that serves
the clamp screw / wire hook.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — photo-scaled, p.48 bottom
close-up (low).

Layout: collar axis along Y (extruded from a Top-plane sketch, which maps
(x, y) -> global (X, -Z)); cross hole along Z from a Front-plane sketch.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_output_fixture.py
"""

from __future__ import annotations

import sys

from _common import (
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "output-fixture"
MATERIAL = "Brass"  # see _common.apply_material docstring

COLLAR_DIA = 10.0  # DIMENSIONS.md ch20: p.48 bottom close-up (low)
COLLAR_HEIGHT = 8.0  # DIMENSIONS.md ch20 (low)
ROD_BORE_DIA = 5.2  # Ø5 vertical rod + clearance
CROSS_HOLE_DIA = 3.0  # clamp screw / wire hook
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent crossed


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, COLLAR_DIA / 2.0, "collar")
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    check(
        "extrude collar",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLLAR_HEIGHT)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    check("create_sketch rod bore", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, ROD_BORE_DIA / 2.0, "rod bore")
    await ensure_fully_defined(adapter, "rod bore sketch")
    check("exit_sketch rod bore", await adapter.exit_sketch())
    check(
        "cut rod bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after rod bore: {vol:.1f} mm^3")

    # Cross hole along Z at mid-height (collar grows +Y from the Top plane).
    check("create_sketch cross hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, COLLAR_HEIGHT / 2.0, CROSS_HOLE_DIA / 2.0, "cross hole")
    await ensure_fully_defined(adapter, "cross hole sketch")
    check("exit_sketch cross hole", await adapter.exit_sketch())
    check(
        "cut cross hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after cross hole: {vol:.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

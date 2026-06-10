r"""Reproduction script: crank arm (book ch. 11, pp. 12-15).

The metal crank arm that drives the machine: full-radius boss at the
crankshaft end (bored for the shaft and cross-drilled for the removable
tapered pin), straight arm, square end carrying the handle pivot, and a
fiducial dimple for alignment. The wooden handle and the tapered pin are
separate parts (build_crank_handle.py / build_crank_pin.py); the chain
eyelet (chain lost) is omitted.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — all photo-scaled (low) except
the legacy 3/8" crankshaft bore (med).

Layout: arm length along +X from the origin (shaft bore axis = global Z
through the origin), thickness extruded +Z (0..8). The cross-pin hole runs
along global Y at mid-thickness: probed live, a Top-plane sketch maps
(x, y) -> global (X, -Z), so the hole circle sits at sketch (0, -4).
Through-cuts use mid-plane blind cuts (depth > extent) because the
ThroughAll+both_directions combination fails live on SW 2026 (MCP issue
#38); the dimple uses a mid-plane cut of twice its depth so the cut
direction never matters.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_crank_arm.py
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
)

PART_NAME = "crank-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

ARM_C2C = 150.0  # DIMENSIONS.md ch11: shaft-to-handle-pivot centres (low)
ARM_WIDTH = 16.0  # DIMENSIONS.md ch11: arm width (low)
ARM_THICKNESS = 8.0  # DIMENSIONS.md ch11: ~half the arm width, p.12 photo (low)
SQUARE_END_OVERHANG = 10.0  # DIMENSIONS.md ch11: square end past the pivot (low)
SHAFT_BORE_DIA = 9.5  # DIMENSIONS.md ch11: legacy 3/8" crankshaft (med)
PIVOT_BORE_DIA = 6.0  # DIMENSIONS.md ch11: handle pivot screw (low)
DIMPLE_DIA = 8.0  # DIMENSIONS.md ch11: fiducial indentation (low)
DIMPLE_DEPTH = 0.5  # DIMENSIONS.md ch11: fiducial indentation (low)
DIMPLE_X = 30.0  # DIMENSIONS.md ch11: on the arm near the boss (low)
PIN_HOLE_DIA = 5.0  # DIMENSIONS.md ch11: tapered-pin cross-hole, small end (low)

ARM_END_X = ARM_C2C + SQUARE_END_OVERHANG
HALF_WIDTH = ARM_WIDTH / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent it crosses


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Arm outline: full-radius boss cap (arc about the origin) + 3 lines.
    check("create_sketch outline", await adapter.create_sketch("Front"))
    arc = check(
        "add_arc boss cap",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_WIDTH, 0.0, -HALF_WIDTH),
    )
    bottom, right, top = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_WIDTH),
            (ARM_END_X, -HALF_WIDTH),
            (ARM_END_X, HALF_WIDTH),
            (0.0, HALF_WIDTH),
        ],
        close=False,
    )
    check("constraint horizontal bottom", await adapter.add_sketch_constraint(bottom, None, "horizontal"))
    check("constraint vertical right", await adapter.add_sketch_constraint(right, None, "vertical"))
    check("constraint horizontal top", await adapter.add_sketch_constraint(top, None, "horizontal"))
    check(
        f"dimension arm length = {ARM_END_X:g}",
        await adapter.add_sketch_dimension(bottom, None, "linear", ARM_END_X),
    )
    # The dimensioned bottom line stays out of fix_entities: fixing already
    # dimensioned geometry over-defines the sketch.
    await ensure_fully_defined(adapter, "arm outline", fix_entities=[arc, top, right])
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude arm",
        await adapter.create_extrusion(ExtrusionParameters(depth=ARM_THICKNESS)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    # Shaft bore + handle pivot bore, one through-cut.
    check("create_sketch bores", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_BORE_DIA / 2.0, "shaft bore")
    await define_circle(adapter, ARM_C2C, 0.0, PIVOT_BORE_DIA / 2.0, "pivot bore")
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after bores: {vol:.1f} mm^3")

    # Fiducial dimple on the Z=0 face (which face carries it is arbitrary
    # until assembly). Mid-plane cut of 2x depth: only the +Z half removes
    # material, so the result is DIMPLE_DEPTH regardless of cut direction.
    check("create_sketch dimple", await adapter.create_sketch("Front"))
    await define_circle(adapter, DIMPLE_X, 0.0, DIMPLE_DIA / 2.0, "dimple")
    await ensure_fully_defined(adapter, "dimple sketch")
    check("exit_sketch dimple", await adapter.exit_sketch())
    check(
        "cut dimple",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * DIMPLE_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after dimple: {vol:.1f} mm^3")

    # Tapered-pin cross-hole along global Y through boss and shaft bore at
    # mid-thickness (global Z = ARM_THICKNESS/2 -> Top sketch y = -Z).
    check("create_sketch pin hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, -ARM_THICKNESS / 2.0, PIN_HOLE_DIA / 2.0, "pin hole"
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after pin hole: {vol:.1f} mm^3")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

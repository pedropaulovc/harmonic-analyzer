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

import math
import sys

from _common import (
    IN,
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
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

    # Editable knobs (Tools > Equations): the shaft diameter/length and the
    # cross-hole diameter/height. The mm suffix is load-bearing -- this is an
    # INCH document and the equation manager reads BARE numbers in document units
    # (an unsuffixed 120 = 120 in, blowing the part up 25.4x). SHAFT_DIA is
    # already mm (0.375 * IN), so it serialises as its mm value.
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "PinHoleHeight", f"{PIN_HOLE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Shaft: on-axis circle (centre at the origin), so define_circle emits only
    # the diameter dim -- the two centre slots are ignored.
    shaft = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft circle", dims=shaft,
        names=("ShaftCx", "ShaftCz", "ShaftDiaDim"),
        drives=(None, None, '"ShaftDia"'),
    )
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += shaft.apply(adapter, "ShaftProfile")
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    name_last_feature(adapter, "Shaft")
    v_shaft = math.pi * (SHAFT_DIA / 2.0) ** 2 * SHAFT_LENGTH
    await volume_check(adapter, "shaft", v_shaft, 0.005 * v_shaft)

    # Tapered-pin cross-hole through the crank seat (along Z). On the Front
    # plane the centre is off-axis in y (height) only, so define_circle emits a
    # z (height) dim then the diameter -- the x slot is ignored.
    pin = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, PIN_HOLE_HEIGHT, PIN_HOLE_DIA / 2.0, "pin hole", dims=pin,
        names=("PinCx", "PinHeight", "PinDiaDim"),
        drives=(None, '"PinHoleHeight"', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    # Cross-drill removal is the Ø5 cylinder clipped by the shaft surface
    # (no clean closed form); the as-built drop is ~178 mm^3 (script comment).
    v_final = v_shaft - 178.0
    await volume_check(adapter, "shaft + pin hole", v_final, 50.0)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven crankshaft (equations neutral)", v_final, 50.0)

    # Named central axis (shaft axis = local +Y through the origin) so the
    # crankshaft mates concentric in the pedestal and the crank parts /
    # pinion / chain wheel lock to it (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

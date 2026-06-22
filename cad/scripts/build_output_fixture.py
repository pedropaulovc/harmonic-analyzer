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

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "output-fixture"
MATERIAL = "Brass"  # see _common.apply_material docstring

COLLAR_DIA = 10.0  # DIMENSIONS.md ch20: p.48 bottom close-up (low)
COLLAR_HEIGHT = 8.0  # DIMENSIONS.md ch20 (low)
ROD_BORE_DIA = 5.2  # Ø5 vertical rod + clearance
CROSS_HOLE_DIA = 3.0  # clamp screw / wire hook
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent crossed


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): collar OD/height, rod bore and cross
    # hole diameters. The mm suffix is load-bearing -- this is an INCH document
    # and the equation manager reads BARE numbers in document units (an
    # unsuffixed 10 = 10 in, blowing the part up 25.4x).
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarHeight", f"{COLLAR_HEIGHT}mm")
    await set_global(adapter, "RodBoreDia", f"{ROD_BORE_DIA}mm")
    await set_global(adapter, "CrossHoleDia", f"{CROSS_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Collar: on-axis circle (centre at the origin), so define_circle emits only
    # the diameter dim -- the two centre slots are ignored.
    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, COLLAR_DIA / 2.0, "collar", dims=collar,
        names=("CollarCx", "CollarCz", "CollarDiaDim"),
        drives=(None, None, '"CollarDia"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "extrude collar",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLLAR_HEIGHT)),
    )
    name_last_feature(adapter, "Collar")
    # Drive the collar's extrude depth from CollarHeight too (D1 is the blind-
    # extrude depth dim). The cross hole is driven to CollarHeight/2, so the body
    # height must move with it or a GUI edit of CollarHeight leaves the hole
    # off-centre (or outside the collar). Evaluates to as-built -> neutral.
    drive_jobs.append(("D1@Collar", '"CollarHeight"'))
    v_collar = math.pi * (COLLAR_DIA / 2.0) ** 2 * COLLAR_HEIGHT
    await volume_check(adapter, "collar", v_collar, 0.005 * v_collar)

    # Rod bore: on-axis circle, diameter dim only.
    rod = SketchDims()
    check("create_sketch rod bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, ROD_BORE_DIA / 2.0, "rod bore", dims=rod,
        names=("RodCx", "RodCz", "RodBoreDiaDim"),
        drives=(None, None, '"RodBoreDia"'),
    )
    await ensure_fully_defined(adapter, "rod bore sketch")
    check("exit_sketch rod bore", await adapter.exit_sketch())
    name_last_feature(adapter, "RodBoreProfile")
    drive_jobs += rod.apply(adapter, "RodBoreProfile")
    check(
        "cut rod bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RodBore")
    v_bored = v_collar - math.pi * (ROD_BORE_DIA / 2.0) ** 2 * COLLAR_HEIGHT
    await volume_check(adapter, "rod bore", v_bored, 0.005 * v_collar)

    # Cross hole along Z at mid-height (collar grows +Y from the Top plane). On
    # the Front plane the centre is off-axis in y (height) only, so define_circle
    # emits a z (height) dim then the diameter -- the x slot is ignored.
    cross = SketchDims()
    check("create_sketch cross hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, COLLAR_HEIGHT / 2.0, CROSS_HOLE_DIA / 2.0, "cross hole",
        dims=cross,
        names=("CrossCx", "CrossHeight", "CrossHoleDiaDim"),
        drives=(None, '"CollarHeight" / 2', '"CrossHoleDia"'),
    )
    await ensure_fully_defined(adapter, "cross hole sketch")
    check("exit_sketch cross hole", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossHoleProfile")
    drive_jobs += cross.apply(adapter, "CrossHoleProfile")
    check(
        "cut cross hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "CrossHole")
    # The Ø3 cross hole removes only the two annular walls it pierces (the bore
    # already cleared the centre); no clean closed form, so a loose tol.
    wall_span = COLLAR_DIA - ROD_BORE_DIA  # 2 x wall thickness pierced
    v_final = v_bored - math.pi * (CROSS_HOLE_DIA / 2.0) ** 2 * wall_span
    await volume_check(adapter, "cross hole", v_final, 30.0)

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven output fixture (equations neutral)", v_final, 30.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

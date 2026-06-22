r"""Reproduction script: crank pedestal (book ch. 11 / eight-views).

Green cylindrical pedestal at the machine's front-right that carries the
crankshaft: a plain vertical cylinder standing on the base with a
horizontal through-bore (along the machine depth Z) at the drive height.
Front view (eight-views 1/8, `ch30_images/v1_0deg_drivetrain_grid.png`):
pedestal centre x = +123 +/- 3 (ratifies the +122 layout), diameter
~46 mm, top ~110 mm above the base top, crank pivot 76 mm above the base
top (~34 mm below the pedestal top).

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports" (photo-scaled, low/med).

Layout: pedestal axis = +Y from the origin (assembly: standing on the
base top face), bore along Z at y = BORE_HEIGHT.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pedestal.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    IN,
    SketchDims,
    apply_color,
    apply_material,
    name_bore_axis,
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

PART_NAME = "crank-pedestal"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

PEDESTAL_DIA = 46.0  # ch13 layout: front view, 278 px / 6.02 px/mm (scaled, low)
PEDESTAL_HEIGHT = 110.0  # ch13 layout: front view top at ~110 above base top (scaled, low)
BORE_DIA = 0.375 * IN  # 9.525: crankshaft diameter (ch. 11, legacy, med)
BORE_HEIGHT = 76.0  # ch13 layout: drive height above base top (med)

PEDESTAL_RADIUS = PEDESTAL_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): pedestal diameter + height, bore
    # diameter + drive height. The mm suffix is load-bearing -- this is an INCH
    # document and the equation manager reads BARE numbers in document units (an
    # unsuffixed 46 = 46 in, blowing the part up 25.4x). PEDESTAL_HEIGHT and the
    # cut depth are feature parameters (not sketch dims), so nothing drives them;
    # exposing PedestalHeight is still a useful knob and matches the exemplars.
    await set_global(adapter, "PedestalDia", f"{PEDESTAL_DIA}mm")
    await set_global(adapter, "PedestalHeight", f"{PEDESTAL_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    # Each sketch records its dim names + drive equations inline; the deferred
    # drive batch at the end runs once the whole model + a rebuild exists.
    drive_jobs: list[tuple[str, str]] = []

    # Pedestal cylinder. Origin circle: only the diameter is a dim.
    pedestal = SketchDims()
    check("create_sketch pedestal", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, PEDESTAL_RADIUS, "pedestal circle", dims=pedestal,
        names=("PedestalCx", "PedestalCz", "PedestalDia"),
        drives=(None, None, '"PedestalDia"'),
    )
    await ensure_fully_defined(adapter, "pedestal sketch")
    check("exit_sketch pedestal", await adapter.exit_sketch())
    name_last_feature(adapter, "PedestalProfile")
    drive_jobs += pedestal.apply(adapter, "PedestalProfile")
    check(
        "extrude pedestal",
        await adapter.create_extrusion(ExtrusionParameters(depth=PEDESTAL_HEIGHT)),
    )
    name_last_feature(adapter, "Pedestal")
    v_cyl = math.pi * PEDESTAL_RADIUS**2 * PEDESTAL_HEIGHT
    volume = await volume_check(adapter, "pedestal cylinder", v_cyl, 0.005 * v_cyl)

    # Crankshaft bore along Z at the drive height (Front-plane sketch,
    # symmetric cut clears the full pedestal depth). On-axis in X (x 0), so
    # define_circle emits only the Z centre dim + the diameter (the X slot is a
    # coincident relation, not a dim, and is ignored).
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreCx", "BoreHeight", "BoreDia"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PEDESTAL_DIA + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    # Bore length through the round pedestal: chord at x integrated over the
    # bore cross-section; bore radius << pedestal radius, so a midpoint
    # integral over x is plenty.
    n = 2000
    dx = BORE_DIA / n
    v_bore = 0.0
    for i in range(n):
        x = -BORE_RADIUS + (i + 0.5) * dx
        v_bore += 2.0 * math.sqrt(BORE_RADIUS**2 - x * x) * dx * 2.0 * math.sqrt(
            PEDESTAL_RADIUS**2 - x * x
        )
    v_final = volume - v_bore
    volume = await volume_check(adapter, "bore", v_final, 0.01 * v_bore)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pedestal (equations neutral)", v_final, 0.01 * v_bore
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 76.0, "Right Plane", 0.0, "bore axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: crank pedestal (book ch. 11 / eight-views, ch30 GT).

Green cylindrical pedestal at the machine's front-right that carries the
crankshaft. The ch30 quarter views (page003 315deg, page009 45deg) show
one round green column -- elliptical top face with a two-screw split
bearing cap, domed oiler button on the flank -- standing on the base.

It carries ONLY the crank: the cone-swing journal that briefly nested
inside it (the 2026-07-02 cylinder restore) lives on the cone swing
platform now (build_cone_swing_platform + build_cone_pivot_post) -- the
p.18 top-down shows the pivot post standing on the dark wedge plate,
NOT inside the pedestal, and the whole plate swings to dis/engage the
cone set. With the cavity and shaft windows gone the column returns to
a slender plain cylinder south of the platform's south edge.

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports" (photo-scaled + ch30 GT triangulation).

Layout: cylinder standing on the Top plane, axis through the origin,
crank through-bore along Z at y = BORE_HEIGHT.

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

PEDESTAL_DIA = 28.0  # ch30 quarter views: slender round column (photo-scaled;
# slimmed 30 -> 28 within photo tolerance so the swing plate's DISENGAGED pose
# clears the column -- asserted in the drive-train assembly)
PEDESTAL_HEIGHT = 110.0  # ch13 layout: front view top at ~110 above base top
BORE_DIA = 0.375 * IN  # 9.525: crankshaft diameter (ch. 11, legacy, med)
BORE_HEIGHT = 94.16  # ch30 GT: crank axle 144.96 machine = 94.16 above base top
# (must equal build_drive_train_assembly Y_CRANK - Y_BASE_TOP -- asserted there)

PEDESTAL_RADIUS = PEDESTAL_DIA / 2.0
BORE_RADIUS = BORE_DIA / 2.0


def _bore_removed() -> float:
    """Material removed by the crank through-bore: a z-cylinder r=BORE_RADIUS
    crossing the column -- z-chord 2*sqrt(R^2-x^2) integrated over the bore
    disc (Simpson)."""
    R, r = PEDESTAL_RADIUS, BORE_RADIUS
    n = 4000
    h = 2.0 * r / n

    def f(x: float) -> float:
        return 2.0 * math.sqrt(max(R * R - x * x, 0.0)) * 2.0 * math.sqrt(
            max(r * r - x * x, 0.0)
        )

    s = f(-r) + f(r)
    s += 4.0 * sum(f(-r + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-r + 2 * k * h) for k in range(1, n // 2))
    return s * h / 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 30 = 30 in, blowing the part up 25.4x).
    await set_global(adapter, "PedestalDia", f"{PEDESTAL_DIA}mm")
    await set_global(adapter, "PedestalHeight", f"{PEDESTAL_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred column. Origin circle: only the diameter is a dim.
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
    # symmetric cut clears the full column). On-axis in X (x 0), so
    # define_circle emits only the Z centre dim + the diameter.
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
    v_bore = _bore_removed()
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven pedestal (equations neutral)", volume, 0.01 * v_bore
    )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "bore axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

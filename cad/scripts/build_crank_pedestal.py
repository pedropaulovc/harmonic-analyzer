r"""Reproduction script: crank pedestal (book ch. 11 / eight-views, ch30 GT).

Green pedestal slab at the machine's front-right that carries the
crankshaft. The ch30 GT photogrammetry (2026-07-02) moved the crank axle
UP to 94.16 above the base top (the crank meshes the 64T from ABOVE, a
near-vertical mesh) and pinned the pedestal axis at machine x -122.8; the
front view still reads width ~46 and top ~110 above the base top. In the
side views the green casting is a SLAB, not a round column -- it runs
from the T12 chain-wheel corridor back toward the (green) cone swing
post, the cone shaft's front stub boss showing between the two (GT
cone_front). Modeled as a 46.2 x 20 slab, 110 tall, with the crankshaft
through-bore along Z at y = 94.16.

Dimensions: cad/DIMENSIONS.md ch. 13 "Drive-train layout" + "Drive
supports" (photo-scaled + ch30 GT triangulation).

Layout: slab standing on the Top plane, centred at the origin in plan
(X width x Z depth), bore along Z at y = BORE_HEIGHT.

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
    define_centered_rectangle,
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

PEDESTAL_WIDTH = 46.2  # X; ch13 layout: front view, 278 px / 6.02 px/mm (scaled)
PEDESTAL_DEPTH = 20.0  # Z; ch30 GT side views: slab band -145..-125 in machine z
PEDESTAL_HEIGHT = 110.0  # ch13 layout: front view top at ~110 above base top
BORE_DIA = 0.375 * IN  # 9.525: crankshaft diameter (ch. 11, legacy, med)
BORE_HEIGHT = 94.16  # ch30 GT: crank axle 144.96 machine = 94.16 above base top
# (must equal build_drive_train_assembly Y_CRANK - Y_BASE_TOP -- asserted there)

BORE_RADIUS = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the slab envelope + the bore. The mm
    # suffix is load-bearing -- this is an INCH document and the equation manager
    # reads BARE numbers in document units (an unsuffixed 46 = 46 in, blowing the
    # part up 25.4x). PEDESTAL_HEIGHT and the cut depth are feature parameters
    # (not sketch dims), so nothing drives them; exposing PedestalHeight is still
    # a useful knob and matches the exemplars.
    await set_global(adapter, "PedestalWidth", f"{PEDESTAL_WIDTH}mm")
    await set_global(adapter, "PedestalDepth", f"{PEDESTAL_DEPTH}mm")
    await set_global(adapter, "PedestalHeight", f"{PEDESTAL_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    # Each sketch records its dim names + drive equations inline; the deferred
    # drive batch at the end runs once the whole model + a rebuild exists.
    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred slab footprint: width along X, depth along Z.
    pedestal = SketchDims()
    check("create_sketch pedestal", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, PEDESTAL_WIDTH / 2.0, PEDESTAL_DEPTH / 2.0, "pedestal", dims=pedestal,
        name_width="Width", drive_width='"PedestalWidth"',
        name_depth="Depth", drive_depth='"PedestalDepth"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"PedestalWidth" / 2', '"PedestalDepth" / 2'),
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
    v_slab = PEDESTAL_WIDTH * PEDESTAL_DEPTH * PEDESTAL_HEIGHT
    volume = await volume_check(adapter, "pedestal slab", v_slab, 0.005 * v_slab)

    # Crankshaft bore along Z at the drive height (Front-plane sketch,
    # symmetric cut clears the full slab depth). On-axis in X (x 0), so
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
            ExtrusionParameters(depth=PEDESTAL_DEPTH + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * BORE_RADIUS**2 * PEDESTAL_DEPTH
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
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "bore axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

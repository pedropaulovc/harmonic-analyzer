r"""Reproduction script: platen guide rail (book ch. 22, pp. 54-55; 2 used).

One of the two black guide rails screwed across the FULL width of the platen
back, above and below the bright wear band where the support bar slides --
the platen HANGS on the bar by these. Each is fastened by a row of 5 screws
whose heads show on the platen front (ch22 front photo; counterbored flush so
the paper lies flat, shanks threading into the rail) and carries 2 lock
plates (build_guide_lock.py) that bridge behind the bar so the platen cannot
fall off. 10 deep so the lock plates clear the 9-deep bar.

Layout: length along +X, height along +Y from the origin corner, depth
extruded +Z (the assembly seats local z 0 on the platen back). The 4 lock
screw holes run through along Z at the two lock stations (x 60/240 +- 7).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_guide.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "platen-guide"
MATERIAL = "Plain Carbon Steel"

GUIDE_LENGTH = 300.0  # = platen width (ch22 back photo: full-width rails)
GUIDE_HEIGHT = 5.0
GUIDE_DEPTH = 10.0  # 1.0 past the 9-deep bar so the lock plates clear it
LOCK_STATION_X = (60.0, 240.0)  # lock-plate centres (2 per guide)
LOCK_SCREW_DX = 7.0  # 2 screws per lock flank its centre
HOLE_DIA = 3.0  # the fillister screws' O2.9 shanks thread in

HOLE_X = tuple(s + d for s in LOCK_STATION_X for d in (-LOCK_SCREW_DX, LOCK_SCREW_DX))

# Blind holes on the FRONT face (mid-height) where the row of 5 fastening
# screws threads in: the platen counterbores its heads (build_platen), so the
# O2.9 shanks reach 2.4 past the platen back into the rail. Stations = the
# platen's GUIDE_HOLE_X (pinned by an assert in the assembly module).
SCREW_STATION_X = (30.0, 90.0, 150.0, 210.0, 270.0)
SCREW_HOLE_DEPTH = 3.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "GuideLength", f"{GUIDE_LENGTH}mm")
    await set_global(adapter, "GuideHeight", f"{GUIDE_HEIGHT}mm")
    await set_global(adapter, "GuideDepth", f"{GUIDE_DEPTH}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rail outline: corner-at-origin rectangle, length along X, height along Y.
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (GUIDE_LENGTH, 0.0),
        (GUIDE_LENGTH, GUIDE_HEIGHT),
        (0.0, GUIDE_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="guide outline", dims=outline,
        names=["Length", "Height"],
        drives=['"GuideLength"', '"GuideHeight"'],
    )
    await ensure_fully_defined(adapter, "guide outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "GuideProfile")
    drive_jobs += outline.apply(adapter, "GuideProfile")
    check(
        "extrude guide",
        await adapter.create_extrusion(ExtrusionParameters(depth=GUIDE_DEPTH)),
    )
    name_last_feature(adapter, "Guide")
    v_rail = GUIDE_LENGTH * GUIDE_HEIGHT * GUIDE_DEPTH
    await volume_check(adapter, "guide rail", v_rail, 0.005 * v_rail)

    # Lock-screw holes: through along Z at the mid-height line (positions are
    # the lock layout, named but undriven -- only the diameter is driven).
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, x in enumerate(HOLE_X):
        await define_circle(
            adapter, x, GUIDE_HEIGHT / 2.0, HOLE_DIA / 2.0, f"lock hole x{x:.0f}",
            dims=holes,
            names=(f"H{n}X", f"H{n}Z", f"H{n}Dia"),
            drives=(None, None, '"HoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * GUIDE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LockHoles")
    v_holes = len(HOLE_X) * math.pi * (HOLE_DIA / 2.0) ** 2 * GUIDE_DEPTH
    await volume_check(adapter, "guide with holes", v_rail - v_holes, 0.02 * v_holes)

    # Blind screw holes on the front face (both-directions trick: 2x depth
    # about the z=0 sketch plane lands 0..SCREW_HOLE_DEPTH in material).
    screws = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, x in enumerate(SCREW_STATION_X):
        await define_circle(
            adapter, x, GUIDE_HEIGHT / 2.0, HOLE_DIA / 2.0, f"screw hole x{x:.0f}",
            dims=screws,
            names=(f"F{n}X", f"F{n}Z", f"F{n}Dia"),
            drives=(None, None, '"HoleDia"'),
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screw holes sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += screws.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * SCREW_HOLE_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    v_screws = (
        len(SCREW_STATION_X) * math.pi * (HOLE_DIA / 2.0) ** 2 * SCREW_HOLE_DEPTH
    )
    v_final = v_rail - v_holes - v_screws
    await volume_check(adapter, "guide with screw holes", v_final, 0.02 * v_screws)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven guide (equations neutral)", v_final, 0.02 * v_holes
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

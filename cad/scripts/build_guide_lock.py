r"""Reproduction script: platen guide lock plate (book ch. 22, pp. 54-55; 4 used).

One of the four small black plates screwed to the backs of the two platen
guide rails (2 per rail), bridging BEHIND the support bar so the hanging
platen cannot fall off it: the plate overlaps the guide on one long edge
(the 2 screw holes) and cantilevers past the bar's back face on the other.

Layout: width along +X, height along +Y from the origin corner, thickness
extruded +Z; the y = 0 edge is the guide-side edge (screw holes 2.5 above
it). Bottom-rail copies mount as authored and bridge UP across the open
channel onto the bar band; top-rail copies are flipped Rz180 by the assembly
and hang DOWN over the bar.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_guide_lock.py
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

PART_NAME = "guide-lock"
MATERIAL = "Plain Carbon Steel"

LOCK_WIDTH = 22.0
# Sized by the BOTTOM station: its rail sits 7 below the bar (open channel), so
# reaching a 7 overlap behind the bar band takes 5 (rail) + 7 (channel) + 7
# (bar) = 19. The top rail sits ON the bar, so the same plate overlaps the bar
# by 14 there -- and the two rows still clear each other by 1.0 in y
# (2026-07-07 field report: a 12-tall plate topped out AT the bar's bottom
# edge and retained nothing at the bottom stations).
LOCK_HEIGHT = 19.0
LOCK_THICK = 2.0
HOLE_DIA = 3.0  # the fillister screws' O2.9 shanks pass through
HOLE_XY = ((4.0, 2.5), (18.0, 2.5))  # on the guide band (guide holes x +-7)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "LockWidth", f"{LOCK_WIDTH}mm")
    await set_global(adapter, "LockHeight", f"{LOCK_HEIGHT}mm")
    await set_global(adapter, "LockThick", f"{LOCK_THICK}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    rect = [
        (0.0, 0.0),
        (LOCK_WIDTH, 0.0),
        (LOCK_WIDTH, LOCK_HEIGHT),
        (0.0, LOCK_HEIGHT),
    ]
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(
        adapter, lines, rect, label="lock outline", dims=outline,
        names=["Width", "Height"],
        drives=['"LockWidth"', '"LockHeight"'],
    )
    await ensure_fully_defined(adapter, "lock outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "LockProfile")
    drive_jobs += outline.apply(adapter, "LockProfile")
    check(
        "extrude lock",
        await adapter.create_extrusion(ExtrusionParameters(depth=LOCK_THICK)),
    )
    name_last_feature(adapter, "Lock")
    v_plate = LOCK_WIDTH * LOCK_HEIGHT * LOCK_THICK
    await volume_check(adapter, "lock plate", v_plate, 0.005 * v_plate)

    # Screw holes on the guide-side band (positions are the guide layout,
    # named but undriven -- only the diameter is driven).
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    for n, (x, y) in enumerate(HOLE_XY):
        await define_circle(
            adapter, x, y, HOLE_DIA / 2.0, f"screw hole ({x:.0f}, {y:.1f})",
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
            ExtrusionParameters(depth=2.0 * LOCK_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    v_holes = len(HOLE_XY) * math.pi * (HOLE_DIA / 2.0) ** 2 * LOCK_THICK
    v_final = v_plate - v_holes
    await volume_check(adapter, "lock with holes", v_final, 0.005 * v_plate)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven lock (equations neutral)", v_final, 0.005 * v_plate
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

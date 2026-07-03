r"""Reproduction script: cone tip block (book ch. 12, p. 18; video 4/4 stills).

The small clamp block at the thin end of the cone shaft. It stands on the
swing platform right beside the pivot and journals the shaft's 1/32" tip
stub, so the shaft is carried at BOTH ends -- big-end journal in the
pivot post, tip in this block -- and the whole set swings as one unit
about the platform's pivot axis (the block sits so close to the pivot
that its throw is millimetres).

Dimensions estimated from the p.18 top-down and the v4_t00393 still
(low). The bore height above the block base is BORE_HEIGHT; the platform
adds PLATE_T under the foot, and BORE_HEIGHT + PLATE_T must equal the
drive height above the base top (54) -- asserted module-level in
build_drive_train_assembly.

Layout: block standing on the Top plane, plan centred on the origin,
tip journal bore along Z at y = BORE_HEIGHT (the assembly rotates the
block about Y to align the bore with the cone axis). Named "journal
axis" for the view-independent coaxial mate to the shaft tip.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_block.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    PANEL_BLACK,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
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

PART_NAME = "cone-tip-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel, like the platform it rides

BLOCK_X = 14.0  # plan width across the shaft (low)
BLOCK_Z = 12.0  # plan depth along the shaft (low)
BLOCK_HEIGHT = 53.65  # bore at 47.65 + 6 of material above (low)
BORE_DIA = 0.03125 * IN  # 0.79375: the shaft's 1/32" tip stub (ch. 12 SECTIONS)
BORE_HEIGHT = 47.65  # + platform PLATE_T 6.35 = drive height 54 above base top

BORE_RADIUS = BORE_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 14 = 14 in). BoreDia carries the legacy
    # 1/32" value already reduced to mm.
    await set_global(adapter, "BlockX", f"{BLOCK_X}mm")
    await set_global(adapter, "BlockZ", f"{BLOCK_Z}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHeight", f"{BORE_HEIGHT}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred rectangular footprint on the Top plane.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BLOCK_X / 2.0, BLOCK_Z / 2.0, "block", dims=block,
        name_width="Width", drive_width='"BlockX"',
        name_depth="Depth", drive_depth='"BlockZ"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BlockX" / 2', '"BlockZ" / 2'),
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    v_block = BLOCK_X * BLOCK_Z * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Tip journal bore along Z at the drive height. On-axis in X (centre x 0,
    # a relation), so define_circle records only the centre-Z + diameter dims.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, BORE_HEIGHT, BORE_RADIUS, "bore", dims=bore,
        names=("BoreX", "BoreZ", "BoreDiaDim"),
        drives=(None, '"BoreHeight"', '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_Z + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "JournalBore")
    v_bore = math.pi * BORE_RADIUS**2 * BLOCK_Z
    volume = await volume_check(adapter, "bore", volume - v_bore, 0.5 * v_bore)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven block (equations neutral)", volume, 0.5 * v_bore)

    # Named bore axis for the view-independent coaxial mate: the shaft tip
    # positions this block (coaxial + axial distance), no face picks.
    await name_bore_axis(adapter, "Top Plane", BORE_HEIGHT, "Right Plane", 0.0, "journal axis")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

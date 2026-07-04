r"""Reproduction script: pinion pivot block (book ch. 25; 2 used).

The black base block that anchors one end of the pinion swing rig
(p. 68 close-ups): a plain rectangular block screwed to the base,
cross-bored TWICE for the two parallel Ø6.35 rods -- the strap torque
shaft (east bore) and the lever lift rod (west bore). The slotted screw
heads on the plates are simplified away.

Layout: block centred on the origin midway between the bores (at local
x +-BORE_HALF_SPACING), both bores along Z at y 0 (12 above the base
seat), block x -16.5..16.5, y -12..4, z 0..12.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_pivot_block.py
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
    volume_check,
)

PART_NAME = "pinion-pivot-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel block (p.68)

WIDTH = 36.0  # spans both bores + margin; widened 33 -> 36 (PR7) so the
# Ø8 screw heads at x +-13.5 seat fully on the block (edge 17.5 + 0.5 rim)
HEIGHT = 16.0  # photo-scaled (low); keeps the strap's r 11 bottom cap
# (PIVOT_Y - 11 = 51.8) swinging clear of the base top 50.8
DEPTH = 12.0  # photo-scaled (low)
BORE_UP = 12.0  # bore height above the base seat -- sets PIVOT_Y (derived)
BORE = 6.35  # rides the Ø6.35 torque shaft / lift rod (derived)
BORE_HALF_SPACING = 7.5  # half the pivot-to-lift rod spacing 15.0 -- the
# lift rod must clear BOTH the cone-pivot-post column (machine x -47.1)
# and the strap's swinging r 11 bottom cap (build_drive_train_assembly)
SCREW_HOLE_DIA = 4.2  # slotted-screw shank O4 (PR7: the p.69 close-up's two
# bright hold-down heads per block)
SCREW_HALF_SPACING = 13.5  # hole centres out past the bores: 0.6 web to the
# bore wall, 0.9 rim to the block end


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the block envelope, the two bores and
    # their spacing. The mm suffix is load-bearing -- this is an INCH document and
    # the equation manager reads BARE numbers in document units (an unsuffixed 33
    # = 33 in). Depth is the extrude feature parameter (built with the literal);
    # BlockDepth is declared so a GUI edit sees the knob.
    await set_global(adapter, "BlockWidth", f"{WIDTH}mm")
    await set_global(adapter, "BlockHeight", f"{HEIGHT}mm")
    await set_global(adapter, "BlockDepth", f"{DEPTH}mm")
    await set_global(adapter, "BoreUp", f"{BORE_UP}mm")
    await set_global(adapter, "Bore", f"{BORE}mm")
    await set_global(adapter, "BoreHalfSpacing", f"{BORE_HALF_SPACING}mm")
    await set_global(adapter, "ScrewHoleDia", f"{SCREW_HOLE_DIA}mm")
    await set_global(adapter, "ScrewHalfSpacing", f"{SCREW_HALF_SPACING}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Block outline + both bores in ONE sketch -> single extrude. add_line_chain
    # and define_circle both suppress sketch inference internally (the bores sit
    # on the sketch x axis, so an auto-relation would mis-snap them).
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-WIDTH / 2.0, -BORE_UP),
        (WIDTH / 2.0, -BORE_UP),
        (WIDTH / 2.0, HEIGHT - BORE_UP),
        (-WIDTH / 2.0, HEIGHT - BORE_UP),
    ]
    entities = await add_line_chain(adapter, block_rect)
    # Bores on the sketch x axis (y 0): x != 0 records ONE centre dim (an unsigned
    # distance to the origin, driven by the positive spacing global) + diameter.
    await define_circle(
        adapter, BORE_HALF_SPACING, 0.0, BORE / 2.0, "pivot bore", dims=block,
        names=("PivotBoreX", "PivotBoreCz", "PivotBoreDia"),
        drives=('"BoreHalfSpacing"', None, '"Bore"'),
    )
    await define_circle(
        adapter, -BORE_HALF_SPACING, 0.0, BORE / 2.0, "lift bore", dims=block,
        names=("LiftBoreX", "LiftBoreCz", "LiftBoreDia"),
        drives=('"BoreHalfSpacing"', None, '"Bore"'),
    )
    # Rectangle anchored at vertex 0 (-WIDTH/2, -BORE_UP): the width (X span) and
    # height (Y span) segment dims, then the two anchor dims (absolute distances
    # to the origin, so AnchorX = WIDTH/2 and AnchorZ = BORE_UP).
    await define_rectilinear_chain(
        adapter, entities, block_rect, label="block", dims=block,
        names=["BlockWidth", "BlockHeight", "AnchorX", "AnchorZ"],
        drives=['"BlockWidth"', '"BlockHeight"', '"BlockWidth" / 2', '"BoreUp"'],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=DEPTH)),
    )
    name_last_feature(adapter, "Block")
    area = WIDTH * HEIGHT - 2.0 * math.pi * (BORE / 2.0) ** 2
    expected = area * DEPTH
    await volume_check(adapter, "block", expected, 0.005 * expected)

    # Two vertical slotted-screw holes (PR7): O4.2 along Y through the block at
    # (x +-SCREW_HALF_SPACING, z mid-depth) -- the p.69 close-up's bright
    # hold-down pair. Top sketch (u, v) -> (X, -Z); mid-plane cut spans the
    # 16-tall block about the bore plane.
    holes = SketchDims()
    check("create_sketch screw holes", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, SCREW_HALF_SPACING, -DEPTH / 2.0, SCREW_HOLE_DIA / 2.0,
        "screw hole east", dims=holes,
        names=("ScrewEastX", "ScrewEastZ", "ScrewEastDia"),
        drives=('"ScrewHalfSpacing"', '"BlockDepth" / 2', '"ScrewHoleDia"'),
    )
    await define_circle(
        adapter, -SCREW_HALF_SPACING, -DEPTH / 2.0, SCREW_HOLE_DIA / 2.0,
        "screw hole west", dims=holes,
        names=("ScrewWestX", "ScrewWestZ", "ScrewWestDia"),
        drives=('"ScrewHalfSpacing"', '"BlockDepth" / 2', '"ScrewHoleDia"'),
    )
    await ensure_fully_defined(adapter, "screw holes sketch")
    check("exit_sketch screw holes", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHolesProfile")
    drive_jobs += holes.apply(adapter, "ScrewHolesProfile")
    check(
        "cut screw holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * HEIGHT, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHoles")
    v_holes = 2.0 * math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * HEIGHT
    expected -= v_holes
    await volume_check(adapter, "screw holes", expected, 0.02 * v_holes)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven block (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

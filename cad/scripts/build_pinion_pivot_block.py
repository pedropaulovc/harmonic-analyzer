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
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes

PART_NAME = "pinion-pivot-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel block (p.68)

WIDTH = 36.0  # spans both bores + margin; widened 33 -> 36 (PR7) so the
# Ø8 screw heads at x +-13.5 seat fully on the block (edge 17.5 + 0.5 rim)
HEIGHT = 16.0  # photo-scaled (low); keeps the strap's r 11 bottom cap
# (PIVOT_Y - 11 = 51.8) swinging clear of the base top 50.8
DEPTH = 12.0  # photo-scaled (low)
BORE_UP = 12.0  # pivot bore height above the base seat -- sets PIVOT_Y (derived)
BORE = 6.35  # rides the Ø6.35 torque shaft / lift rod (derived)
BORE_HALF_SPACING = 7.5  # half the pivot-to-lift rod spacing 15.0 -- the
# lift rod must clear BOTH the cone-pivot-post column (machine x -47.1)
# and the strap's swinging r 11 bottom cap (build_drive_train_assembly)
LIFT_BORE_DROP = 4.66  # the WEST (lift) bore sits this far BELOW the pivot
# bore (PR8, page001_img01: the rods ride at different heights so the
# eccentric cam collar's top meets the follower pin from below). Bore
# bottom at local -7.84 keeps a 4.2 web to the block bottom (-12). The
# 4.66 (not the photo-first 4.51) buys the 0.15 park AIR between pin and
# collar -- exact tangency tips the interference gate on FP noise.
# Slotted-screw shank pass-throughs (PR7: the p.69 close-up's two bright
# hold-down heads per block): #19 drill (Ø4.216) -- the wizard twin of the old
# Ø4.2, matching the base's own #19 slotted-screw seats (build_harmonic_base
# BlockScrewHoles) exactly.
SCREW_HOLE_SPEC = HoleSpec("drilled_number", "#19")
SCREW_HOLE_DIA = NUMBER_DRILL_MM[SCREW_HOLE_SPEC.size]  # 4.216; re-exposed for
# the drive-train assembly's block-screw clearance assert
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
    await set_global(adapter, "LiftBoreDrop", f"{LIFT_BORE_DROP}mm")
    # (The old ScrewHoleDia/ScrewHalfSpacing knobs are gone: the two hold-down
    # holes are now a native Hole Wizard #19 feature at literal stations.)

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
    # Pivot bore on the sketch x axis (y 0): x != 0 records ONE centre dim (an
    # unsigned distance to the origin, driven by the positive spacing global) +
    # diameter. The lift bore drops LIFT_BORE_DROP below it (PR8), adding its
    # own unsigned y dim.
    await define_circle(
        adapter, BORE_HALF_SPACING, 0.0, BORE / 2.0, "pivot bore", dims=block,
        names=("PivotBoreX", "PivotBoreCz", "PivotBoreDia"),
        drives=('"BoreHalfSpacing"', None, '"Bore"'),
    )
    await define_circle(
        adapter, -BORE_HALF_SPACING, -LIFT_BORE_DROP, BORE / 2.0, "lift bore",
        dims=block,
        names=("LiftBoreX", "LiftBoreCz", "LiftBoreDia"),
        drives=('"BoreHalfSpacing"', '"LiftBoreDrop"', '"Bore"'),
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

    # Two vertical slotted-screw hold-down holes (PR7): ONE native Hole Wizard
    # #19 feature (2 through-all instances) along Y at (x +-SCREW_HALF_SPACING,
    # z mid-depth), drilled from the block bottom (y = -BORE_UP) while the block
    # is still prismatic (the two Z-bores exit the front/back faces, leaving the
    # bottom face a clean rectangle). Top-sketch (u,v)->(X,-Z), so the sketch v
    # -DEPTH/2 is model z = +DEPTH/2 -- the mid-depth line.
    screw_dia = NUMBER_DRILL_MM[SCREW_HOLE_SPEC.size]
    wizard_holes(
        adapter, SCREW_HOLE_SPEC,
        [[SCREW_HALF_SPACING, -BORE_UP, DEPTH / 2.0],
         [-SCREW_HALF_SPACING, -BORE_UP, DEPTH / 2.0]],
        (0.0, -1.0, 0.0), "hold-down screw holes (#19)", name="ScrewHoles",
    )
    v_holes = 2.0 * math.pi * (screw_dia / 2.0) ** 2 * HEIGHT
    expected -= v_holes
    await volume_check(adapter, "screw holes", expected, 0.02 * v_holes)

    # Named lift-bore axis (Axis1): the lift rod's revolute mates coaxial to
    # this in the assembly (PR8 -- the rod spins to drive the cams).
    await name_bore_axis(
        adapter, "Right Plane", -BORE_HALF_SPACING, "Top Plane", -LIFT_BORE_DROP,
        "lift bore",
    )

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

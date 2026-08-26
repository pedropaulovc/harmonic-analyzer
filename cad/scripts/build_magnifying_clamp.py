r"""Reproduction script: magnifying-lever clamp block (book ch. 20, p. 48).

The square block that slides along the magnifying lever and carries the
vertical rod beside it; the reeded thumb screw clamps it from the top.
The two rod bores are skew (offset across the block) so the rods pass
without touching, as in the p.48 close-up.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — all photo-scaled vs the Ø6
lever rod (low). Bores get 0.2 mm clearance over their rods.

Layout: lever bore along Z (the extrude direction) through the block's
upper portion; vertical-rod bore along Y, offset in X; thumb-screw hole
along Y above the lever bore. Through-holes are mid-plane blind cuts
(MCP issue #38 workaround); the Top-plane sketch maps (x, y) ->
global (X, -Z).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_clamp.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
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
from _holes import TAP_DRILL_MM, HoleSpec, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from magnifying_clamp_geom import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    LEVER_BORE_DIA,
    LEVER_BORE_Y,
    ROD_BORE_DIA,
    ROD_BORE_X,
)
from magnifying_clamp_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    SURFACE_FINISHES,
)

PART_NAME = "magnifying-clamp"
MATERIAL = "Brass"  # see _common.apply_material docstring

# Nominal geometry lives in magnifying_clamp_geom (imported above): the two rod
# bores are engineered running/slip fits (0.2 mm clearance over their rods), NOT
# drilled fastener holes, so they stay plain dimensioned cuts. The thumb-screw
# hole threads IN, so it IS a native #4-40 tapped Hole Wizard hole matching
# the stock thumb screw's #4-40 external thread.

THROUGH_CUT_DEPTH = 80.0  # mid-plane total; > any extent crossed


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): block envelope plus the two rod-bore
    # diameters and their in-plane stations. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 20 = 20 in, blowing the part up 25.4x).
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "LeverBoreDia", f"{LEVER_BORE_DIA}mm")
    await set_global(adapter, "LeverBoreY", f"{LEVER_BORE_Y}mm")
    await set_global(adapter, "RodBoreDia", f"{ROD_BORE_DIA}mm")
    await set_global(adapter, "RodBoreX", f"{ROD_BORE_X}mm")
    # (The old ScrewHoleDia knob is gone: the thumb-screw hole is now a native
    # Hole Wizard #4-40 tapped feature placed by point.)

    drive_jobs: list[tuple[str, str]] = []

    # Block outline: rectangle with its bottom edge on the X axis, centred in X
    # (corner vertex at (-W/2, 0)). NOT origin-centred, so it stays a
    # define_rectilinear_chain. Emission order is width (bottom segment), height
    # (one side segment), then the anchor X (anchor vertex at x=-W/2, y=0 -> only
    # the X dim; y=0 emits no dim): three display dims.
    block = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_WIDTH / 2.0, 0.0),
        (BLOCK_WIDTH / 2.0, 0.0),
        (BLOCK_WIDTH / 2.0, BLOCK_HEIGHT),
        (-BLOCK_WIDTH / 2.0, BLOCK_HEIGHT),
    ]
    lines = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter, lines, block_rect, label="block", dims=block,
        names=["Width", "Height", "AnchorX"],
        drives=['"BlockWidth"', '"BlockHeight"', '"BlockWidth" / 2'],
    )
    await ensure_fully_defined(adapter, "block outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    name_last_feature(adapter, "Block")
    v_block = BLOCK_WIDTH * BLOCK_HEIGHT * BLOCK_DEPTH
    await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Lever bore along Z: a plain dimensioned slip cut (engineered 0.2 mm
    # running fit, not a drilled hole). On-axis in X (centre x=0), off-axis in y
    # (the bore height), so define_circle emits the Z/height dim then the
    # diameter -- the X slot is ignored.
    lever = SketchDims()
    check("create_sketch lever bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, LEVER_BORE_Y, LEVER_BORE_DIA / 2.0, "lever bore",
        dims=lever,
        names=("LeverCx", "LeverBoreYDim", "LeverBoreDiaDim"),
        drives=(None, '"LeverBoreY"', '"LeverBoreDia"'),
    )
    await ensure_fully_defined(adapter, "lever bore sketch")
    check("exit_sketch lever bore", await adapter.exit_sketch())
    name_last_feature(adapter, "LeverBoreProfile")
    drive_jobs += lever.apply(adapter, "LeverBoreProfile")
    check(
        "cut lever bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "LeverBore")
    v_lever = math.pi * (LEVER_BORE_DIA / 2.0) ** 2 * BLOCK_DEPTH
    await volume_check(adapter, "lever bore", v_block - v_lever, 0.005 * v_block)

    # Vertical-rod slip bore along Y from the Top plane (sketch y maps to global
    # -Z; the block spans Z 0..BLOCK_DEPTH). Also a plain dimensioned slip cut.
    # Off-axis in both x (skew station) and z (depth mid-plane), so define_circle
    # emits X, Z, then diameter.
    rod = SketchDims()
    check("create_sketch rod bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, ROD_BORE_X, -BLOCK_DEPTH / 2.0, ROD_BORE_DIA / 2.0, "rod bore",
        dims=rod,
        names=("RodBoreXDim", "RodBoreZ", "RodBoreDiaDim"),
        drives=('"RodBoreX"', '"BlockDepth" / 2', '"RodBoreDia"'),
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

    # Thumb-screw hole: ONE native Hole Wizard #4-40 tapped feature along Y
    # (through_all) from the top face (Y=BLOCK_HEIGHT, outward normal +Y).
    # The stock screw's matching #4-40 external thread enters on the X axis,
    # crossing the lever bore.
    screw_cut = wizard_holes(
        adapter,
        HoleSpec("tapped", "#4-40"),
        [[0.0, BLOCK_HEIGHT, BLOCK_DEPTH / 2.0]],
        (0.0, 1.0, 0.0),
        "thumb-screw tapped hole (#4-40)", name="ScrewHole",
        placement_dims=[((None, None), ("ScrewHoleZ", '"BlockDepth" / 2'))],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    # The two Y features run the full block height; the screw hole crosses the
    # lever bore on the X axis with no clean closed form, so a loose tol absorbs
    # the double-counted intersection while still catching a gross unit-blowup.
    v_rod = math.pi * (ROD_BORE_DIA / 2.0) ** 2 * BLOCK_HEIGHT
    v_screw = math.pi * (TAP_DRILL_MM["#4-40"] / 2.0) ** 2 * BLOCK_HEIGHT
    v_final = v_block - v_lever - v_rod - v_screw
    await volume_check(adapter, "y-bores", v_final, 80.0)

    # Named lever-bore axis (local Z through (0, LEVER_BORE_Y)) so the clamp
    # rides the magnifying rod as a concentric slider in the M6 assembly.
    await name_bore_axis(
        adapter, "Top Plane", LEVER_BORE_Y, "Right Plane", 0.0, "lever bore axis"
    )

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check neutrality (each equation evaluates to the as-built
    # value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven magnifying clamp (equations neutral)", v_final, 80.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

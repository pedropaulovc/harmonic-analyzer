r"""Reproduction script: pinion pivot block (book ch. 25; 2 used).

The black base block that anchors one end of the pinion swing rig
(p. 68 close-ups): a plain rectangular block screwed to the base,
cross-bored TWICE for the two parallel Ø6.35 rods -- the strap torque
shaft (east bore) and the lever lift rod (west bore). The slotted screw
heads on the plates are simplified away.

Layout: block centred on the origin midway between the bores (at local
x +-BORE_HALF_SPACING), both bores along Z at y 0 (12 above the base
seat), block x -16.5..16.5, y -12..4, z 0..12.

Dimensions: cad/DIMENSIONS.md "Chapter 25". The nominal geometry lives in
``pinion_pivot_block_spec`` -- the pure-data contract shared with the
manufacturing drawing (``draw_pinion_pivot_block.py``).

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
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes
from pinion_pivot_block_spec import (
    BLOCK_DEPTH,
    BLOCK_HEIGHT,
    BLOCK_WIDTH,
    BORE_DIA,
    BORE_HALF_SPACING,
    BORE_UP,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    ISOMETRIC_VIEW_NOTE,
    LIFT_BORE_DROP,
    SCREW_HALF_SPACING,
)

PART_NAME = "pinion-pivot-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel block (p.68)
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

# Slotted-screw shank pass-throughs (PR7: the p.69 close-up's two bright
# hold-down heads per block): #19 drill (Ø4.216) -- the wizard twin of the old
# Ø4.2, matching the base's own #19 slotted-screw seats (build_harmonic_base
# BlockScrewHoles) exactly.
SCREW_HOLE_SPEC = HoleSpec("drilled_number", "#19")
SCREW_HOLE_DIA = NUMBER_DRILL_MM[SCREW_HOLE_SPEC.size]  # 4.216; re-exposed for
# the drive-train assembly's block-screw clearance assert


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the block envelope, the two bores and
    # their spacing. The mm suffix is load-bearing -- this is an INCH document and
    # the equation manager reads BARE numbers in document units (an unsuffixed 33
    # = 33 in).
    await set_global(adapter, "BlockWidth", f"{BLOCK_WIDTH}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "BlockDepth", f"{BLOCK_DEPTH}mm")
    await set_global(adapter, "BoreUp", f"{BORE_UP}mm")
    await set_global(adapter, "Bore", f"{BORE_DIA}mm")
    await set_global(adapter, "BoreHalfSpacing", f"{BORE_HALF_SPACING}mm")
    await set_global(adapter, "LiftBoreDrop", f"{LIFT_BORE_DROP}mm")
    await set_global(adapter, "ScrewHalfSpacing", f"{SCREW_HALF_SPACING}mm")
    # (The old ScrewHoleDia/ScrewHalfSpacing knobs are gone: the two hold-down
    # holes are now a native Hole Wizard #19 feature at literal stations.)

    drive_jobs: list[tuple[str, str]] = []

    # Block outline + both bores in ONE sketch -> single extrude. add_line_chain
    # and define_circle both suppress sketch inference internally (the bores sit
    # on the sketch x axis, so an auto-relation would mis-snap them).
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLOCK_WIDTH / 2.0, -BORE_UP),
        (BLOCK_WIDTH / 2.0, -BORE_UP),
        (BLOCK_WIDTH / 2.0, BLOCK_HEIGHT - BORE_UP),
        (-BLOCK_WIDTH / 2.0, BLOCK_HEIGHT - BORE_UP),
    ]
    entities = await add_line_chain(adapter, block_rect)
    # Pivot bore on the sketch x axis (y 0): x != 0 records ONE centre dim (an
    # unsigned distance to the origin, driven by the positive spacing global) +
    # diameter. The lift bore drops LIFT_BORE_DROP below it (PR8), adding its
    # own unsigned y dim.
    await define_circle(
        adapter, BORE_HALF_SPACING, 0.0, BORE_DIA / 2.0, "pivot bore", dims=block,
        names=("PivotBoreX", "PivotBoreCz", "PivotBoreDia"),
        drives=('"BoreHalfSpacing"', None, '"Bore"'),
    )
    await define_circle(
        adapter, -BORE_HALF_SPACING, -LIFT_BORE_DROP, BORE_DIA / 2.0, "lift bore",
        dims=block,
        names=("LiftBoreX", "LiftBoreCz", "LiftBoreDia"),
        drives=('"BoreHalfSpacing"', '"LiftBoreDrop"', '"Bore"'),
    )
    # Rectangle anchored at vertex 0 (-BLOCK_WIDTH/2, -BORE_UP): the width (X
    # span) and height (Y span) segment dims, then the two anchor dims (absolute
    # distances to the origin, so AnchorX = BLOCK_WIDTH/2 and AnchorZ = BORE_UP).
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
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_DEPTH)),
    )
    name_last_feature(adapter, "Block")
    depth_dim = name_dimensions(adapter, "Block", ["Depth"])
    drive_jobs += [(depth_dim[0], '"BlockDepth"')]
    area = BLOCK_WIDTH * BLOCK_HEIGHT - 2.0 * math.pi * (BORE_DIA / 2.0) ** 2
    expected = area * BLOCK_DEPTH
    await volume_check(adapter, "block", expected, 0.005 * expected)

    # Two vertical slotted-screw hold-down holes (PR7): ONE native Hole Wizard
    # #19 feature (2 through-all instances) along Y at (x +-SCREW_HALF_SPACING,
    # z mid-depth), drilled from the block bottom (y = -BORE_UP) while the block
    # is still prismatic (the two Z-bores exit the front/back faces, leaving the
    # bottom face a clean rectangle). Top-sketch (u,v)->(X,-Z), so the sketch v
    # -BLOCK_DEPTH/2 is model z = +BLOCK_DEPTH/2 -- the mid-depth line.
    screw_dia = NUMBER_DRILL_MM[SCREW_HOLE_SPEC.size]
    screw_cut = wizard_holes(
        adapter, SCREW_HOLE_SPEC,
        [[SCREW_HALF_SPACING, -BORE_UP, BLOCK_DEPTH / 2.0],
         [-SCREW_HALF_SPACING, -BORE_UP, BLOCK_DEPTH / 2.0]],
        (0.0, -1.0, 0.0), "hold-down screw holes (#19)", name="ScrewHoles",
        placement_dims=[
            (("ScrewEastX", '"ScrewHalfSpacing"'),
             ("ScrewEastZ", '"BlockDepth" / 2')),
            (("ScrewWestX", '"ScrewHalfSpacing"'),
             ("ScrewWestZ", '"BlockDepth" / 2')),
        ],
    )
    drive_jobs += screw_cut.placement_drive_jobs
    v_holes = 2.0 * math.pi * (screw_dia / 2.0) ** 2 * BLOCK_HEIGHT
    expected -= v_holes
    await volume_check(adapter, "screw holes", expected, 0.02 * v_holes)

    # Named lift-bore axis (Axis1): the lift rod's revolute mates coaxial to
    # this in the assembly (PR8 -- the rod spins to drive the cams).
    lift_axis = await name_bore_axis(
        adapter, "Right Plane", -BORE_HALF_SPACING, "Top Plane", -LIFT_BORE_DROP,
        "lift bore",
    )
    _blank_ref_geometry(adapter, "Plane1", "PLANE")
    _blank_ref_geometry(adapter, "Plane2", "PLANE")
    _blank_ref_geometry(adapter, lift_axis, "AXIS")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven block (equations neutral)", expected, 0.005 * expected)

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    missing = [
        name for name in _SAVED_DRAWING_PROPERTIES
        if not str(adapter.currentModel.GetCustomInfoValue("", name) or "")
    ]
    if missing:
        raise RuntimeError(f"saved part drawing properties are missing: {missing}")
    return artefacts


def _blank_ref_geometry(adapter, name: str, kind: str) -> None:
    """Keep construction planes and axes out of saved renders."""
    from solidworks_mcp.adapters.pywin32_adapter import null_callout

    model = adapter.currentModel
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(
        name, kind, 0, 0, 0, False, 0, null_callout(), 0,
    ):
        raise RuntimeError(f"cannot select {name!r} to hide reference geometry")
    model.BlankRefGeom()
    model.ClearSelection2(True)


if __name__ == "__main__":
    sys.exit(run_build(build))

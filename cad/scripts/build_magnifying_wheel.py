r"""Reproduction script: magnifying wheel (book ch. 21, pp. 50-53).

Pulley of two coaxial wheels rotating together: the wire from the magnifying
lever wraps the 20 mm grooved brass hub, the wire to the pen mechanism leaves
the 100 mm outer rim -- magnifying the summing lever's motion 5x. Six straight
cast spokes (counted on the p. 51 full-page photo; black-painted casting with
a bright machined rim). The fine hub grooves and the hex axle nut are
cosmetic/assembly details, omitted here.

Dimensions: cad/DIMENSIONS.md "Chapter 21" -- hub and rim diameters are
book-annotated and self-validate against the stated 5x magnification; rim
ring section, spoke section, and bore are photo-scaled (low confidence).

Layout: wheel axis = Z through the origin; all features mid-plane symmetric
about the Front plane.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_magnifying_wheel.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    measure_check,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "magnifying-wheel"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

RIM_OUTER_DIA = 100.0  # DIMENSIONS.md ch21: annotated (high)
HUB_DIA = 20.0  # DIMENSIONS.md ch21: annotated (high)
SPOKE_COUNT = 6  # DIMENSIONS.md ch21: counted on p.51 (high)

RIM_RING_RADIAL = 6.0  # rim ring radial thickness, photo-scaled (low)
RIM_AXIAL = 8.0  # rim axial width, photo-scaled (low)
HUB_AXIAL = 10.0  # brass drum axial length, photo-scaled (low)
SPOKE_WIDTH = 5.0  # photo-scaled (low)
SPOKE_AXIAL = 4.0  # photo-scaled (low)
BORE_DIA = 5.0  # axle bore, photo-scaled (low)

RIM_INNER_DIA = RIM_OUTER_DIA - 2 * RIM_RING_RADIAL
SPOKE_OVERLAP = 1.0  # spokes bite into hub and rim so the bodies merge


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations) for every length constant; the rim inner
    # diameter, the spoke span and its corner height are equations of the
    # primitives. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 100 =
    # 100 in). SPOKE_COUNT is a pattern instance count, not a sketch length, so it
    # stays a Python constant (no global, nothing to drive).
    await set_global(adapter, "RimOuterDia", f"{RIM_OUTER_DIA}mm")
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "RimRingRadial", f"{RIM_RING_RADIAL}mm")
    await set_global(adapter, "RimAxial", f"{RIM_AXIAL}mm")
    await set_global(adapter, "HubAxial", f"{HUB_AXIAL}mm")
    await set_global(adapter, "SpokeWidth", f"{SPOKE_WIDTH}mm")
    await set_global(adapter, "SpokeAxial", f"{SPOKE_AXIAL}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "SpokeOverlap", f"{SPOKE_OVERLAP}mm")
    await set_global(adapter, "RimInnerDia", '"RimOuterDia" - 2 * "RimRingRadial"')
    # Spoke runs from y0 (hub OD, less overlap) to y1 (rim ID, plus overlap); its
    # length dim is the span, its corner anchor sits at (-SpokeWidth/2, y0).
    await set_global(adapter, "SpokeY0", '"HubDia" / 2 - "SpokeOverlap"')
    await set_global(
        adapter, "SpokeLength",
        '"RimInnerDia" / 2 - "HubDia" / 2 + 2 * "SpokeOverlap"',
    )

    drive_jobs: list[tuple[str, str]] = []

    # Rim ring (annulus, mid-plane symmetric). Two on-axis circles: each emits
    # only its diameter dim.
    rim_sd = SketchDims()
    check("create_sketch rim", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, RIM_OUTER_DIA / 2.0, "rim OD", dims=rim_sd,
        names=("RimOdCx", "RimOdCz", "RimOuterDiaDim"),
        drives=(None, None, '"RimOuterDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, RIM_INNER_DIA / 2.0, "rim ID", dims=rim_sd,
        names=("RimIdCx", "RimIdCz", "RimInnerDiaDim"),
        drives=(None, None, '"RimInnerDia"'),
    )
    await ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", await adapter.exit_sketch())
    name_last_feature(adapter, "RimProfile")
    drive_jobs += rim_sd.apply(adapter, "RimProfile")
    check(
        "extrude rim",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIM_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Rim")

    # Hub drum. On-axis circle: diameter only.
    hub_sd = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HUB_DIA / 2.0, "hub drum", dims=hub_sd,
        names=("HubCx", "HubCz", "HubDiaDim"),
        drives=(None, None, '"HubDia"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub_sd.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_AXIAL, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Hub")

    # Seed spoke along +Y from the hub into the rim ring. Manual constraints +
    # dims, so record each display dim into SketchDims in CREATION order: the
    # width dim, the length dim, then the corner anchor (x, then z) emitted by
    # anchor_point_to_origin for the off-axis corner (-half, y0).
    spoke_sd = SketchDims()
    check("create_sketch spoke", await adapter.create_sketch("Front"))
    half = SPOKE_WIDTH / 2.0
    y0 = HUB_DIA / 2.0 - SPOKE_OVERLAP
    y1 = RIM_INNER_DIA / 2.0 + SPOKE_OVERLAP
    spoke_lines = await add_line_chain(
        adapter, [(-half, y0), (half, y0), (half, y1), (-half, y1)]
    )
    bottom, right, top, left = spoke_lines
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right, "vertical"),
        (left, "vertical"),
    ):
        check(f"spoke constraint {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    check("spoke width dim", await adapter.add_sketch_dimension(bottom, None, "linear", SPOKE_WIDTH))
    spoke_sd.record("SpokeWidthDim", '"SpokeWidth"')
    check("spoke length dim", await adapter.add_sketch_dimension(right, None, "linear", y1 - y0))
    spoke_sd.record("SpokeLengthDim", '"SpokeLength"')
    await anchor_point_to_origin(adapter, f"{bottom}.start", -half, y0, "spoke corner")
    spoke_sd.record("SpokeCornerX", '"SpokeWidth" / 2')  # unsigned half-width
    spoke_sd.record("SpokeCornerZ", '"SpokeY0"')
    await ensure_fully_defined(adapter, "spoke sketch")
    check("exit_sketch spoke", await adapter.exit_sketch())
    name_last_feature(adapter, "SpokeProfile")
    drive_jobs += spoke_sd.apply(adapter, "SpokeProfile")
    spoke_feature = await adapter.create_extrusion(
        ExtrusionParameters(depth=SPOKE_AXIAL, both_directions=True)
    )
    check("extrude spoke", spoke_feature)
    name_last_feature(adapter, "Spoke")

    # Axle bore through everything. On-axis circle: diameter only.
    bore_sd = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore", dims=bore_sd,
        names=("BoreCx", "BoreCz", "BoreDiaDim"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore_sd.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HUB_AXIAL + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")

    # Pattern the spoke about the bore axis. The seed feature was renamed to
    # "Spoke" above, so the pattern must select it by the NEW name (the captured
    # auto-name went stale on rename).
    check(
        f"circular pattern {SPOKE_COUNT} spokes",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=[BORE_DIA / 2.0, 0.0, 0.0],
                features=["Spoke"],
                count=SPOKE_COUNT,
            )
        ),
    )
    name_last_feature(adapter, "SpokePattern")
    res = await adapter.get_mass_properties()
    v_built = float(res.data.volume)
    print(f"  volume after pattern: {v_built:.1f} mm^3")

    await apply_material(adapter, MATERIAL)

    # Verify the two annotated diameters (ch. 21: 100 mm rim, 20 mm hub
    # — they self-validate against the stated 5x magnification).
    await measure_check(
        adapter,
        "rim OD (annotated 100)",
        [{"entity_type": "EDGE", "point": [RIM_OUTER_DIA / 2.0, 0.0, RIM_AXIAL / 2.0]}],
        "diameter",
        RIM_OUTER_DIA,
    )
    await measure_check(
        adapter,
        "hub dia (annotated 20)",
        [{"entity_type": "EDGE", "point": [HUB_DIA / 2.0, 0.0, HUB_AXIAL / 2.0]}],
        "diameter",
        HUB_DIA,
    )

    # Named wheel axis (local Z through the origin = the central bore axis) so
    # the wheel revolves on the axle stud in the M6 mated-DOF assembly
    # (circular_pattern's axis_point does NOT create a persistent ref axis).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "wheel axis")

    # Apply the deferred drive equations after the whole model + a rebuild exists,
    # so every target resolves. Each equation evaluates to the as-built value (the
    # spoked wheel's volume has no tidy closed form, so the neutrality gate asserts
    # the post-drive volume equals the captured as-built value): geometry must not
    # move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven magnifying wheel (equations neutral)", v_built, 0.001 * v_built
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

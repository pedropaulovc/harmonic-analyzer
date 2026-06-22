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
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    measure_check,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
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

    # Rim ring (annulus, mid-plane symmetric).
    check("create_sketch rim", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, RIM_OUTER_DIA / 2.0, "rim OD")
    await define_circle(adapter, 0.0, 0.0, RIM_INNER_DIA / 2.0, "rim ID")
    await ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", await adapter.exit_sketch())
    check(
        "extrude rim",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RIM_AXIAL, both_directions=True)
        ),
    )

    # Hub drum.
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, HUB_DIA / 2.0, "hub drum")
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_AXIAL, both_directions=True)
        ),
    )

    # Seed spoke along +Y from the hub into the rim ring.
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
    check("spoke length dim", await adapter.add_sketch_dimension(right, None, "linear", y1 - y0))
    await anchor_point_to_origin(adapter, f"{bottom}.start", -half, y0, "spoke corner")
    await ensure_fully_defined(adapter, "spoke sketch")
    check("exit_sketch spoke", await adapter.exit_sketch())
    spoke_feature = await adapter.create_extrusion(
        ExtrusionParameters(depth=SPOKE_AXIAL, both_directions=True)
    )
    check("extrude spoke", spoke_feature)

    # Axle bore through everything.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, BORE_DIA / 2.0, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=HUB_AXIAL + 2.0, both_directions=True)
        ),
    )

    # Pattern the spoke about the bore axis.
    check(
        f"circular pattern {SPOKE_COUNT} spokes",
        await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=[BORE_DIA / 2.0, 0.0, 0.0],
                features=[spoke_feature.data.name],
                count=SPOKE_COUNT,
            )
        ),
    )

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

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

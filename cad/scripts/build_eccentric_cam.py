r"""Reproduction script: eccentric cam (book ch. 13, pp. 22-25).

One of the 20 eccentric cams integral to the cylinder gear set. Each cam
converts its gear's rotation into the near-sinusoidal reciprocation of a
connecting rod (displacement = ECCENTRICITY x sin(theta)).

Dimensions: cad/DIMENSIONS.md "Chapter 13" (legacy parameters.kcl values,
uncontradicted by the book; cam outline printed on book p. 25 -- flagged
there for a photo-scaling cross-check).

Layout: shaft bore on the part origin (= rotation axis); cam disc centre
offset -Y by the eccentricity; keyway pointing +Y (away from the cam lobe).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_eccentric_cam.py
"""

from __future__ import annotations

import sys

from _common import (
    IN,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "eccentric-cam"
MATERIAL = "Brass"  # see _common.apply_material docstring

CAM_DIAMETER = 30.6  # DIMENSIONS.md ch13: cam diameter, scaled 0.6022 with the gear OD (low)
CAM_THICKNESS = 0.4 * IN  # 10.16 DIMENSIONS.md ch13: cam thickness (legacy, med)
BORE_DIAMETER = 0.375 * IN  # 9.525 DIMENSIONS.md ch13: cam bore (legacy, med)
ECCENTRICITY = 3.06  # DIMENSIONS.md ch13: cam eccentricity, scaled 0.6022 (5.08 -> 3.06) (low)
KEYWAY_WIDTH = 0.125 * IN  # 3.175 DIMENSIONS.md ch13: keyway width (legacy, med)
KEYWAY_DEPTH = 0.06 * IN  # 1.524 DIMENSIONS.md ch13: keyway depth past bore (legacy, med)

BORE_RADIUS = BORE_DIAMETER / 2.0
KEYWAY_TOP_Y = BORE_RADIUS + KEYWAY_DEPTH
KEYWAY_BOTTOM_Y = BORE_RADIUS / 2.0  # inside the bore; exact value immaterial
KEYWAY_HALF_WIDTH = KEYWAY_WIDTH / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Cam disc blank: circle centred -Y of the bore axis by the eccentricity.
    check("create_sketch disc", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, -ECCENTRICITY, CAM_DIAMETER / 2.0, "cam disc")
    await ensure_fully_defined(adapter, "disc sketch")
    check("exit_sketch disc", await adapter.exit_sketch())
    check(
        "extrude cam disc",
        await adapter.create_extrusion(ExtrusionParameters(depth=CAM_THICKNESS)),
    )

    # Shaft bore through the part origin.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, BORE_RADIUS, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CAM_THICKNESS + 2.0)
        ),
    )

    # Keyway: rectangular slot overlapping the bore, pointing +Y.
    check("create_sketch keyway", await adapter.create_sketch("Front"))
    keyway = await add_line_chain(
        adapter,
        [
            (-KEYWAY_HALF_WIDTH, KEYWAY_BOTTOM_Y),
            (KEYWAY_HALF_WIDTH, KEYWAY_BOTTOM_Y),
            (KEYWAY_HALF_WIDTH, KEYWAY_TOP_Y),
            (-KEYWAY_HALF_WIDTH, KEYWAY_TOP_Y),
        ],
    )
    bottom, right, top, left = keyway
    for ent, relation in ((bottom, "horizontal"), (top, "horizontal"), (right, "vertical"), (left, "vertical")):
        check(
            f"constraint {relation}",
            await adapter.add_sketch_constraint(ent, None, relation),
        )
    check(
        "dimension keyway width",
        await adapter.add_sketch_dimension(bottom, None, "linear", KEYWAY_WIDTH),
    )
    check(
        "dimension keyway height",
        await adapter.add_sketch_dimension(
            right, None, "linear", KEYWAY_TOP_Y - KEYWAY_BOTTOM_Y
        ),
    )
    await anchor_point_to_origin(
        adapter, f"{bottom}.start", -KEYWAY_HALF_WIDTH, KEYWAY_BOTTOM_Y, "keyway corner"
    )
    await ensure_fully_defined(adapter, "keyway sketch")
    check("exit_sketch keyway", await adapter.exit_sketch())
    check(
        "cut keyway",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=CAM_THICKNESS + 2.0)
        ),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: platen paper clip strip (book ch. 22, p. 55).

One of the two thin brass strips (left/right on the platen front) the
recording paper slides under; each is held by a screw at either end.
Used twice in the assembly.

Dimensions: cad/DIMENSIONS.md "Chapter 22" — scaled from the p.55 front
photo vs the 140 mm height callout (low).

Layout: length along +X, width along +Y from the origin corner,
thickness extruded +Z; screw holes inset from the ends.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_platen_clip.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    apply_color,
    PANEL_BLACK,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
)

PART_NAME = "platen-clip"
MATERIAL = "Brass"  # see _common.apply_material docstring

CLIP_LENGTH = 125.0  # DIMENSIONS.md ch22: ~0.9x plate height, p.55 (low)
CLIP_WIDTH = 10.0  # DIMENSIONS.md ch22 (low)
CLIP_THICKNESS = 1.2  # DIMENSIONS.md ch22: thin spring strip (low)
HOLE_DIA = 3.0  # DIMENSIONS.md ch22: end screws (low)
HOLE_INSET = 8.0  # from each end
THROUGH_CUT_DEPTH = 10.0  # mid-plane total; > thickness


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    check("create_sketch outline", await adapter.create_sketch("Front"))
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (CLIP_LENGTH, 0.0),
            (CLIP_LENGTH, CLIP_WIDTH),
            (0.0, CLIP_WIDTH),
        ],
    )
    bottom, right_edge, top, left_edge = lines
    for ent, relation in (
        (bottom, "horizontal"),
        (top, "horizontal"),
        (right_edge, "vertical"),
        (left_edge, "vertical"),
    ):
        check(f"outline {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    await anchor_point_to_origin(adapter, f"{bottom}.start", 0.0, 0.0, "clip corner")
    for ent, value, label in (
        (bottom, CLIP_LENGTH, "clip length"),
        (right_edge, CLIP_WIDTH, "clip width"),
    ):
        check(
            f"dimension {label} = {value:g}",
            await adapter.add_sketch_dimension(ent, None, "linear", value),
        )
    await ensure_fully_defined(adapter, "clip outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude clip",
        await adapter.create_extrusion(ExtrusionParameters(depth=CLIP_THICKNESS)),
    )

    check("create_sketch holes", await adapter.create_sketch("Front"))
    await define_circle(adapter, HOLE_INSET, CLIP_WIDTH / 2.0, HOLE_DIA / 2.0, "left hole")
    await define_circle(
        adapter, CLIP_LENGTH - HOLE_INSET, CLIP_WIDTH / 2.0, HOLE_DIA / 2.0, "right hole"
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

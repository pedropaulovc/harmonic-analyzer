r"""Reproduction script: platen rack bar (book ch. 22, pp. 54-55).

The brass rack screwed along the platen's back bottom edge; its teeth
engage the translational gearing (ch. 23). Modelled as a smooth bar for
M2 -- the tooth profile depends on the machine's module, which is OPEN
until the M4 gear-pipeline prep resolves it (then the teeth become a cut
+ linear pattern along the bottom edge). Mounting holes deferred with it.

Dimensions: cad/DIMENSIONS.md "Chapter 22" — bar section scaled from the
p.55 back-side and edge-on photos (low); length = platen width.

Layout: length along +X, height along +Y from the origin corner,
thickness extruded +Z.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_platen_rack.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "platen-rack"
MATERIAL = "Brass"  # see _common.apply_material docstring

RACK_LENGTH = 300.0  # DIMENSIONS.md ch22: = platen width (low)
RACK_HEIGHT = 30.0  # DIMENSIONS.md ch22: back-side brass strip (low)
RACK_THICKNESS = 6.0  # DIMENSIONS.md ch22: edge-on photo (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    check("create_sketch outline", await adapter.create_sketch("Front"))
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (RACK_LENGTH, 0.0),
            (RACK_LENGTH, RACK_HEIGHT),
            (0.0, RACK_HEIGHT),
        ],
    )
    await ensure_fully_defined(adapter, "rack outline", fix_entities=lines)
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude rack",
        await adapter.create_extrusion(ExtrusionParameters(depth=RACK_THICKNESS)),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

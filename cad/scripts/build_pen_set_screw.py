r"""Reproduction script: pen set screw (book ch. 24, pp. 64-65).

The small screw with the black knurled knob that threads up through the
pen frame's bottom rail to set the pen-to-paper angle. Modelled smooth;
knurling and threads wait for the Phase 5 manufacturing tools.

Dimensions: cad/DIMENSIONS.md "Chapter 24" — photo-scaled (low).

Layout: axis along +X from the knob face, revolved about a centerline.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pen_set_screw.py
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
    set_sketch_direct_db,
)

PART_NAME = "pen-set-screw"
MATERIAL = "Brass"  # see _common.apply_material docstring

KNOB_DIA = 9.0  # DIMENSIONS.md ch24: black knurled knob (low)
KNOB_LENGTH = 5.0
SHANK_DIA = 3.0  # threads into the pen frame's Ø3 hole
SHANK_LENGTH = 15.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, KNOB_LENGTH + SHANK_LENGTH, 0.0),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, KNOB_DIA / 2.0),
            (KNOB_LENGTH, KNOB_DIA / 2.0),
            (KNOB_LENGTH, SHANK_DIA / 2.0),
            (KNOB_LENGTH + SHANK_LENGTH, SHANK_DIA / 2.0),
            (KNOB_LENGTH + SHANK_LENGTH, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "screw profile", fix_entities=[centerline, *lines]
    )
    check("exit_sketch profile", await adapter.exit_sketch())

    check(
        "revolve screw",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

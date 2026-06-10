r"""Reproduction script: reeded thumb screw (book ch. 20, p. 48).

The knurled ("reeded") thumb screw that locks the magnifying-lever clamp
block (a second identical one locks the output fixture). Modelled smooth:
knurling and threads wait for the Phase 5 manufacturing tools.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — photo-scaled vs the Ø6
lever rod (low).

Layout: screw axis along +X from the origin (head face at x=0), profile
revolved 360 deg about a centerline.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_thumb_screw.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "thumb-screw"

HEAD_DIA = 10.0  # DIMENSIONS.md ch20: knurled head, p.48 (low)
HEAD_LENGTH = 5.0  # DIMENSIONS.md ch20 (low)
SHANK_DIA = 3.0  # DIMENSIONS.md ch20: matches clamp screw hole (low)
SHANK_LENGTH = 12.0  # DIMENSIONS.md ch20 (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, HEAD_LENGTH + SHANK_LENGTH, 0.0),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, HEAD_DIA / 2.0),
            (HEAD_LENGTH, HEAD_DIA / 2.0),
            (HEAD_LENGTH, SHANK_DIA / 2.0),
            (HEAD_LENGTH + SHANK_LENGTH, SHANK_DIA / 2.0),
            (HEAD_LENGTH + SHANK_LENGTH, 0.0),
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

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

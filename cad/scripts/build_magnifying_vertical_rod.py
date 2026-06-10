r"""Reproduction script: magnifying-lever vertical rod (book ch. 20, pp. 46-49).

The smaller vertical brass rod that slides along the magnifying lever in
the clamp block; the output fixture rides on it and the wire to the
magnifying wheel hooks below. Plain rod with domed ends, like the lever.

Dimensions: cad/DIMENSIONS.md "Chapter 20" — Ø5 x ~150, photo-scaled
against the lever rod (low).

Layout: rod axis along +X from the origin, revolved about a centerline
(orient vertically at assembly).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_magnifying_vertical_rod.py
"""

from __future__ import annotations

import sys

from _common import (
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "magnifying-vertical-rod"

ROD_LENGTH = 150.0  # DIMENSIONS.md ch20: ~half the lever rod, p.46/48 (low)
ROD_DIA = 5.0  # DIMENSIONS.md ch20: thinner than the Ø6 lever (low)

R = ROD_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, ROD_LENGTH, 0.0),
    )
    top = check(
        "add_line top",
        await adapter.add_line(R, R, ROD_LENGTH - R, R),
    )
    cap_right = check(
        "add_arc right dome",
        await adapter.add_arc(ROD_LENGTH - R, 0.0, ROD_LENGTH, 0.0, ROD_LENGTH - R, R),
    )
    axis_line = check(
        "add_line axis",
        await adapter.add_line(ROD_LENGTH, 0.0, 0.0, 0.0),
    )
    cap_left = check(
        "add_arc left dome",
        await adapter.add_arc(R, 0.0, R, R, 0.0, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter,
        "rod profile",
        fix_entities=[centerline, top, cap_right, axis_line, cap_left],
    )
    check("exit_sketch profile", await adapter.exit_sketch())

    check(
        "revolve rod",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

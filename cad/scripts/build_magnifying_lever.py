r"""Reproduction script: magnifying lever rod (book ch. 20, pp. 46-49).

The round brass rod affixed to the summing lever that magnifies its sweep
up to 4x. Plain rod with domed (hemispherical) ends, clearly visible in
the p.47 close-up. The sliding clamp block, vertical rod, thumb screw and
output fixture are separate parts (build_magnifying_*.py).

Dimensions: cad/DIMENSIONS.md "Chapter 20" — Ø6 photo-scaled (low);
length from the 4x constraint: max magnification puts the vertical rod
~300 mm from the summing-lever pivot against its ~76 mm effective spring
arm (300/76 = 3.9), consistent with the p.46 inset proportions (low).

Layout: rod axis along +X from the origin (tip of the pivot-end dome at
x=0), profile revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_magnifying_lever.py
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

PART_NAME = "magnifying-lever"

ROD_LENGTH = 310.0  # DIMENSIONS.md ch20: 4x-ratio constraint + p.46 inset (low)
ROD_DIA = 6.0  # DIMENSIONS.md ch20: round brass rod (low)

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
    # Half-profile: top line, two quarter-arc dome caps, closing axis line.
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

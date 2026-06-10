r"""Reproduction script: crank handle (book ch. 11, pp. 12-15).

The pear-shaped wooden handle (stained black) that rotates on the crank-arm
pivot. The brass collar at the crank end is modelled as an integral
cylindrical section of the revolve profile (it gets its own appearance at
M3 material assignment); the slotted pivot screw is a separate part
(grouped with the plain shafts/pins). The pear silhouette is approximated
by straight profile segments — smooth circumferentially after the revolve,
faceted axially; good enough until Phase 3 tooling allows spline profiles.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — handle ~90 long x Ø22 max,
photo-scaled (low).

Layout: handle axis along +X from the origin (collar face at x=0), profile
revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_crank_handle.py
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

PART_NAME = "crank-handle"
MATERIAL = "Oak"  # see _common.apply_material docstring

HANDLE_LENGTH = 90.0  # DIMENSIONS.md ch11: handle length (low)
HANDLE_MAX_DIA = 22.0  # DIMENSIONS.md ch11: handle diameter (low)
COLLAR_LENGTH = 6.0  # DIMENSIONS.md ch11: brass collar, p.12 photo (low)
COLLAR_DIA = 11.0  # DIMENSIONS.md ch11: brass collar, p.12 photo (low)

# Pear silhouette as (x, radius) breakpoints: collar cylinder, wood neck,
# swell to the maximum near the free end, rounded-off butt.
PROFILE = [
    (0.0, 0.0),
    (0.0, COLLAR_DIA / 2.0),
    (COLLAR_LENGTH, COLLAR_DIA / 2.0),
    (COLLAR_LENGTH, 4.8),
    (20.0, 6.0),
    (45.0, 9.0),
    (62.0, HANDLE_MAX_DIA / 2.0),
    (80.0, 9.5),
    (HANDLE_LENGTH, 5.5),
    (HANDLE_LENGTH, 0.0),
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the shallow pear-silhouette
    # segments to auto horizontal relations (see crank pin lesson).
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, HANDLE_LENGTH, 0.0),
    )
    lines = await add_line_chain(adapter, PROFILE)
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "handle profile", fix_entities=[centerline, *lines]
    )
    check("exit_sketch profile", await adapter.exit_sketch())

    check(
        "revolve handle",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

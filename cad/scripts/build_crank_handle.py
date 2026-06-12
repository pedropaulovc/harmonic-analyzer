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
    anchor_point_to_point,
    apply_material,
    apply_color,
    STAINED_OAK,
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
    collar_face, collar_top, collar_step = lines[0], lines[1], lines[2]
    butt_face = lines[8]
    # 20-DOF profile: collar face on the origin; centerline (merged into
    # both axis ends) horizontal + length dim; h/v + linear dims on the
    # collar and butt edges; the four interior silhouette breakpoints
    # pinned by per-segment run/rise dims -- the (80, 9.5)->(90, 5.5)
    # segment is skipped, its ends defined by the neighbours (closure).
    check(
        "anchor collar face",
        await adapter.add_sketch_constraint(
            f"{collar_face}.start", "origin", "coincident"
        ),
    )
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    check(
        "handle length",
        await adapter.add_sketch_dimension(centerline, None, "linear", HANDLE_LENGTH),
    )
    for label, ent, relation, value in (
        ("collar face", collar_face, "vertical", COLLAR_DIA / 2.0),
        ("collar top", collar_top, "horizontal", COLLAR_LENGTH),
        ("collar step", collar_step, "vertical", COLLAR_DIA / 2.0 - PROFILE[3][1]),
        ("butt face", butt_face, "vertical", PROFILE[8][1]),
    ):
        check(
            f"{label} {relation}",
            await adapter.add_sketch_constraint(ent, None, relation),
        )
        check(
            f"{label} dim",
            await adapter.add_sketch_dimension(ent, None, "linear", value),
        )
    for i in (3, 4, 5, 6):
        x1, y1 = PROFILE[i]
        x2, y2 = PROFILE[i + 1]
        await anchor_point_to_point(
            adapter,
            f"{lines[i]}.start",
            f"{lines[i]}.end",
            x2 - x1,
            y2 - y1,
            f"silhouette segment {i}",
        )
    await ensure_fully_defined(adapter, "handle profile")
    check("exit_sketch profile", await adapter.exit_sketch())

    check(
        "revolve handle",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, STAINED_OAK)  # ch30 plates: see _common palette
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

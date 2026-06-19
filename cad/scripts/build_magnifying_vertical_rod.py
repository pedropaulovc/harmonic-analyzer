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
    anchor_point_to_origin,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "magnifying-vertical-rod"
MATERIAL = "Brass"  # see _common.apply_material docstring

ROD_LENGTH = 150.0  # DIMENSIONS.md ch20: ~half the lever rod, p.46/48 (low)
ROD_DIA = 5.0  # DIMENSIONS.md ch20: thinner than the Ø6 lever (low)

R = ROD_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
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
    # Same scheme as build_magnifying_lever: origin corner + dome centres
    # anchored, one radial dim (the left dome's radius is forced by its
    # anchored centre + the anchored origin end), top edge horizontal and
    # aligned over the left centre; merged centerline unconstrained.
    check(
        "anchor origin corner",
        await adapter.add_sketch_constraint(
            f"{axis_line}.end", "origin", "coincident"
        ),
    )
    check(
        "axis line horizontal",
        await adapter.add_sketch_constraint(axis_line, None, "horizontal"),
    )
    await anchor_point_to_origin(
        adapter, f"{cap_left}.center", R, 0.0, "left dome centre"
    )
    await anchor_point_to_origin(
        adapter, f"{cap_right}.center", ROD_LENGTH - R, 0.0, "right dome centre"
    )
    check(
        "right dome radius",
        await adapter.add_sketch_dimension(cap_right, None, "radial", R),
    )
    check(
        "top horizontal",
        await adapter.add_sketch_constraint(top, None, "horizontal"),
    )
    check(
        "top start over left centre",
        await adapter.add_sketch_constraint(
            f"{top}.start", f"{cap_left}.center", "vertical_points"
        ),
    )
    await ensure_fully_defined(adapter, "rod profile")
    check("exit_sketch profile", await adapter.exit_sketch())

    check(
        "revolve rod",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

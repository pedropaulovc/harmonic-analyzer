r"""Reproduction script: crank tapered pin (book ch. 11, pp. 14-15).

The removable tapered pin that affixes the crank arm to the crankshaft —
pulled to swap the crankshaft gear. Modelled as a plain conical frustum
(period taper pins run ~1:48; the photo-scaled ends here are a touch
steeper, both low confidence).

Dimensions: cad/DIMENSIONS.md "Chapter 11" — cross-hole ~Ø5 (small end);
big end and length scaled from the p.14 photo.

Layout: pin axis along +X from the origin (big end at x=0), profile
revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_crank_pin.py
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
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "crank-pin"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

PIN_LENGTH = 45.0  # DIMENSIONS.md ch11: p.14 photo (low)
BIG_END_DIA = 6.0  # DIMENSIONS.md ch11: p.14 photo (low)
SMALL_END_DIA = 5.0  # DIMENSIONS.md ch11: cross-hole dia, small end (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the ~0.6 deg taper line to an
    # auto "horizontal" relation, flattening the frustum into a cylinder.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, PIN_LENGTH, 0.0),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, BIG_END_DIA / 2.0),
            (PIN_LENGTH, SMALL_END_DIA / 2.0),
            (PIN_LENGTH, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    big_end, _taper, small_end, _axis_closure = lines
    # 8-DOF profile: the centerline merged into the (0, 0) /
    # (PIN_LENGTH, 0) chain ends, so horizontal + a length dim on it keep
    # the small end on the axis; the taper line rides its pinned
    # neighbours (no h/v on it -- that is the whole point of the frustum).
    check(
        "anchor big end",
        await adapter.add_sketch_constraint(f"{big_end}.start", "origin", "coincident"),
    )
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    check(
        "pin length",
        await adapter.add_sketch_dimension(centerline, None, "linear", PIN_LENGTH),
    )
    for label, ent, radius in (
        ("big end", big_end, BIG_END_DIA / 2.0),
        ("small end", small_end, SMALL_END_DIA / 2.0),
    ):
        check(
            f"{label} vertical",
            await adapter.add_sketch_constraint(ent, None, "vertical"),
        )
        check(
            f"{label} radius",
            await adapter.add_sketch_dimension(ent, None, "linear", radius),
        )
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch profile", await adapter.exit_sketch())

    check(
        "revolve pin",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

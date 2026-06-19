r"""Reproduction script: magnifying lever rod (book ch. 20, pp. 46-49).

The round brass rod affixed to the summing lever that magnifies its sweep
up to 4x. Plain rod with domed (hemispherical) ends, clearly visible in
the p.47 close-up. The sliding clamp block, vertical rod, thumb screw and
output fixture are separate parts (build_magnifying_*.py).

Dimensions: cad/DIMENSIONS.md "Chapter 20" — Ø6 photo-scaled (low).
M6.4 revision: the M2 "310 from the 4x constraint" length is REFUTED by
the calibrated ch. 30 front view (p1): the rod spans x ~ -200..-35 at
y ~982, i.e. ~165 long. Magnification comes from the ratio of the clamp
radius (vertical-rod position along this rod, measured from the bracket
collar near the summing-lever plate) to the summing lever's own ratio --
the p.46/p.48 insets show the CLAMP sliding, not a 310 rod.

Layout: rod axis along +X from the origin (tip of the pivot-end dome at
x=0), profile revolved 360 deg about a centerline on the axis.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_magnifying_lever.py
"""

from __future__ import annotations

import sys

from _common import (
    anchor_point_to_origin,
    apply_material,
    check,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "magnifying-lever"
MATERIAL = "Brass"  # see _common.apply_material docstring

ROD_LENGTH = 165.0  # DIMENSIONS.md ch20: calibrated p1, x -200..-35 (med,
# supersedes the 310 "4x" guess -- see docstring)
ROD_DIA = 6.0  # DIMENSIONS.md ch20: round brass rod (low)

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
    # 14-unknown half-profile: origin corner anchored, both dome centres
    # anchored on the axis, ONE radial dim (the left dome's radius is
    # already forced by its anchored centre + the anchored origin end --
    # dimensioning it too over-defines), the top edge horizontal with its
    # start vertically aligned over the left centre. The centerline
    # merged into the two axis corners, so it carries no constraints.
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

    # Named rod axis (local X through the origin = the revolve axis) so the rod
    # rides the bracket collar as a revolute in the M6 mated-DOF assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Top Plane", 0.0, "rod axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: pedestal dome cap screw (book ch. 13 pp. 23-25; 2 used).

The bright domed screw head on each arbor pedestal's outer face, centred on
the cylinder arbor (ch13 page002_img01 "back side", page002_img03 "front
side", ch25 page002_img03: a large round crown filling the pedestal's dome).
It caps the blind arbor bore -- the arbor's end stops inside the strap, and
this head closes the bore from outside.

Layout: revolved about +Y, the crown's base plane on the Top plane at y = 0
(this is the face that bears on the pedestal): spherical crown DOME_DIA
across rising DOME_H, a short STUB_DIA x STUB_LEN spigot below into the bore.
The assembly turns +Y to face outward (-Z on the south pedestal, +Z on the
north one).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_dome_cap_screw.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "dome-cap-screw"
MATERIAL = "Plain Carbon Steel"  # bright nickel-look head (p.23)

DOME_DIA = 10.0  # ch13 page002_img01: ~half the pedestal's 20 dome (photo-scaled, low)
DOME_H = 3.0  # crown height
STUB_DIA = 5.0  # spigot into the O9.525 arbor bore
STUB_LEN = 2.0  # stops 0.5 short of the arbor end (2.5 inside the strap)

DOME_R = DOME_DIA / 2.0
SPHERE_R = (DOME_R**2 + DOME_H**2) / (2.0 * DOME_H)  # 5.667
V_CAP = math.pi * DOME_H**2 * (3.0 * SPHERE_R - DOME_H) / 3.0
V_STUB = math.pi * (STUB_DIA / 2.0) ** 2 * STUB_LEN
V_TOTAL = V_CAP + V_STUB


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    await set_global(adapter, "DomeDia", f"{DOME_DIA}mm")
    await set_global(adapter, "DomeH", f"{DOME_H}mm")
    await set_global(adapter, "StubDia", f"{STUB_DIA}mm")
    await set_global(adapter, "StubLen", f"{STUB_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # One revolved profile in the Front plane (sketch x = radius, y = axis):
    # axis closure, stub, crown base rim, crown arc rim -> apex.
    prof = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "axis", await adapter.add_centerline(0.0, -STUB_LEN, 0.0, DOME_H)
    )
    stub_bottom = check("stub bottom", await adapter.add_line(0.0, -STUB_LEN, STUB_DIA / 2.0, -STUB_LEN))
    stub_wall = check("stub wall", await adapter.add_line(STUB_DIA / 2.0, -STUB_LEN, STUB_DIA / 2.0, 0.0))
    base = check("crown base", await adapter.add_line(STUB_DIA / 2.0, 0.0, DOME_R, 0.0))
    arc = check(
        "crown arc",
        await adapter.add_arc(0.0, DOME_H - SPHERE_R, DOME_R, 0.0, 0.0, DOME_H),
    )
    closing = check("axis closure", await adapter.add_line(0.0, DOME_H, 0.0, -STUB_LEN))
    set_sketch_direct_db(adapter, False)
    for label, a, b in (
        ("bottom-wall", f"{stub_bottom}.end", f"{stub_wall}.start"),
        ("wall-base", f"{stub_wall}.end", f"{base}.start"),
        ("base-arc", f"{base}.end", f"{arc}.start"),
        ("arc-closure", f"{arc}.end", f"{closing}.start"),
        ("closure-bottom", f"{closing}.end", f"{stub_bottom}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    for label, ent, relation in (
        ("stub bottom", stub_bottom, "horizontal"),
        ("stub wall", stub_wall, "vertical"),
        ("crown base", base, "horizontal"),
        ("axis closure", closing, "vertical"),
        ("axis", centerline, "vertical"),
    ):
        check(f"{label} {relation}", await adapter.add_sketch_constraint(ent, None, relation))
    # (The axis-side x of the profile comes from anchor_point_to_origin's own
    # vertical_points relation on the stub-bottom corner below; a second one
    # here would over-define.)
    # Direct-to-DB leaves the centreline's ends loose: tie them to the profile
    # corners on the axis (the ball-mount idiom, done explicitly here).
    for label, a, b in (
        ("axis start", f"{centerline}.start", f"{stub_bottom}.start"),
        ("axis end", f"{centerline}.end", f"{arc}.end"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    check("stub length", await adapter.add_sketch_dimension(stub_wall, None, "linear", STUB_LEN))
    prof.record("StubWall", '"StubLen"')
    await anchor_point_to_origin(adapter, f"{stub_bottom}.start", 0.0, -STUB_LEN, "stub bottom")
    prof.record("StubLen", '"StubLen"')
    check("stub radius", await adapter.add_sketch_dimension(stub_bottom, None, "linear", STUB_DIA / 2.0))
    prof.record("StubR", '"StubDia" / 2')
    check(
        "crown rim reach",
        await adapter.add_sketch_dimension(f"{base}.end", "origin", "horizontal_distance", DOME_R),
    )
    prof.record("DomeR", '"DomeDia" / 2')
    check(
        "crown height",
        await adapter.add_sketch_dimension(f"{arc}.end", "origin", "vertical_distance", DOME_H),
    )
    prof.record("DomeHeight", '"DomeH"')
    check("crown sphere radius", await adapter.add_sketch_dimension(arc, None, "radial", SPHERE_R))
    prof.record(
        "SphereR",
        '("DomeDia" / 2 * "DomeDia" / 2 + "DomeH" * "DomeH") / (2 * "DomeH")',
    )
    await ensure_fully_defined(adapter, "cap profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += prof.apply(adapter, "CapProfile")
    check("revolve cap", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Cap")
    await volume_check(adapter, "cap", V_TOTAL, 0.02 * V_TOTAL)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven cap (equations neutral)", V_TOTAL, 0.02 * V_TOTAL)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

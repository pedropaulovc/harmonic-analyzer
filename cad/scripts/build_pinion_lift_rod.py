r"""Reproduction script: pinion lift rod (book ch. 25).

The second Ø6.35 rod of the swing rig, running through the pivot
blocks' LOW west bores, parallel to (and 4.51 below) the strap torque
shaft. Turning it by the engage lever (build_pinion_lever.py, clamped
on its front end) spins the two eccentric cam collars pinned to it
(build_pinion_cam.py, PR8); their rising ODs lift the straps' follower
pins resting on them from above and swing the drum east into mesh
(page001_img01). PR5's integral radial cam pins are RETIRED -- the
photo shows plain rod + separate set-pinned collars, and the collar
mechanism replaced the crossed-pin lift.

Layout: rod axis Z, z 0..202, plain cylinder; crowned back end.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_lift_rod.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    apply_color,
    apply_material,
    check,
    define_circle,
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

PART_NAME = "pinion-lift-rod"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

ROD_DIA = 6.35  # rides the block bores, same stock as the torque shaft (derived)
ROD_LEN = 202.0  # machine z -114..+88 (PR7): back end FLUSH with the back
# block's outer face (+88, crowned below); the front end reaches just far
# enough south of the front block (-104) for the lever's clamp hub
CAP_SAG = 1.2  # back-end crown sagitta (the p.69 dome; the front end hides
# under the lever hub's own domed cap)

ROD_R = ROD_DIA / 2.0
CAP_R = (ROD_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 4.80 crown sphere radius
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 19.85

V_ROD = math.pi * ROD_R**2 * ROD_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rod diameter; RodLen feeds the
    # feature-parameter extrude length (built with the literal below) --
    # declared so a GUI edit sees the knob. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 6.35 = 6.35 in).
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Rod along +Z: on-axis circle (origin centre), only the diameter recorded.
    rod = SketchDims()
    check("create_sketch rod", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, ROD_R, "rod", dims=rod,
        names=("RodCx", "RodCz", "RodDia"),
        drives=(None, None, '"RodDia"'),
    )
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    name_last_feature(adapter, "RodProfile")
    drive_jobs += rod.apply(adapter, "RodProfile")
    check(
        "extrude rod",
        await adapter.create_extrusion(ExtrusionParameters(depth=ROD_LEN)),
    )
    name_last_feature(adapter, "Rod")
    volume = await volume_check(adapter, "rod", V_ROD, 0.005 * V_ROD)

    expected = volume

    # Back-end crown (PR7, item 13): shallow spherical cap proud of the flush
    # back end -- Top-plane rim->apex profile revolved about the axis, the
    # pivot-shaft cap idiom (apex -> rim is the minor CCW lobe at a +Z end).
    from solidworks_mcp.adapters.base import RevolveParameters

    v_base, v_apex = -ROD_LEN, -(ROD_LEN + CAP_SAG)
    v_centre = -(ROD_LEN + CAP_SAG - CAP_R)
    cap = SketchDims()
    check("create_sketch back cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check(
        "back cap centerline",
        await adapter.add_centerline(0.0, v_base, 0.0, v_apex),
    )
    base = check(
        "back cap base",
        await adapter.add_line(0.0, v_base, ROD_R, v_base),
    )
    arc = check(
        "back cap arc",
        await adapter.add_arc(0.0, v_centre, 0.0, v_apex, ROD_R, v_base),
    )
    close = check(
        "back cap close",
        await adapter.add_line(0.0, v_apex, 0.0, v_base),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "back cap base horizontal",
        await adapter.add_sketch_constraint(base, None, "horizontal"),
    )
    check(
        "back cap close vertical",
        await adapter.add_sketch_constraint(close, None, "vertical"),
    )
    check(
        "back cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "horizontal_distance", ROD_R
        ),
    )
    cap.record("CapRim", '"RodDia" / 2')
    check(
        "back cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "vertical_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "back cap on axis",
        await adapter.add_sketch_constraint(f"{base}.start", "origin", "vertical_points"),
    )
    check(
        "back cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "vertical_distance", ROD_LEN
        ),
    )
    cap.record("CapZ", '"RodLen"')
    check(
        "back cap radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    cap.record(
        "CapR",
        '("RodDia" / 2 * "RodDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "back cap sketch")
    check("exit_sketch back cap", await adapter.exit_sketch())
    name_last_feature(adapter, "BackCapProfile")
    drive_jobs += cap.apply(adapter, "BackCapProfile")
    check(
        "revolve back cap",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "BackCap")
    expected += V_CAP
    await volume_check(adapter, "back cap", expected, 0.03 * V_CAP)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven lift rod (equations neutral)", expected, 0.03 * V_CAP
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

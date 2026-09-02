r"""Reproduction script: transgear thumbnut (book ch. 23 pp. 58-59; 1 used).

The knurled brass thumbnut that retains the removable chain wheel on the
knob shaft (ch23 page002_img03: the reeded brass disc in front of the
sprocket, page002_img04: outermost on the shaft; engineerguy 4/4 "unscrew
the nut that holds the other gear in place"). It sits OUTERMOST on the knob
shaft, in front of the removable transgear: a short neck bears on the
wheel's front face and the knurled disc is what the fingers turn.

Simplifications, both noted on the print:
* the disc is a plain cylinder -- the knurl is NOT modelled (the repo's
  reeding recipe, ``_features.add_reeded_head_and_thread``, is +X-axis-only
  and adds a shank thread; a +Y variant is untested on the seat);
* the bore is thread-free -- a plain O9.6 slip bore over the O9.525 shaft
  stands in for the nut's internal thread.

The neck is O14, not the O10 the photo suggests: the modelled removable has
a O12 plain bore (build_transgear_removable.BORE_DIAMETER), so a O10 neck
would slip INTO the wheel and retain nothing; O14 gives a 1.0 shoulder
around the bore and still clears the r 9.5 drive-pin circle by 0.5.

Layout (part frame): axis +Y, origin at the neck's gear-side face; neck
O NECK_DIA from y 0..NECK_LEN, disc O DISC_DIA from y NECK_LEN..
NECK_LEN + DISC_LEN, O BORE_DIA through. The paper-drive assembly maps +Y to
machine -Z (Rx-90), so the disc faces the machine front.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_thumbnut.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

PART_NAME = "transgear-thumbnut"
MATERIAL = "Brass"

NECK_DIA = 14.0  # bears on the removable's front face; covers its O12 bore
NECK_LEN = 4.0  # stands the knurled disc off the wheel
DISC_DIA = 26.0  # knurled thumb disc (ch23 page002_img03, photo-scaled)
DISC_LEN = 7.0
BORE_DIA = 9.6  # slips the O9.525 knob shaft (modelled thread-free)

TOTAL_LEN = NECK_LEN + DISC_LEN  # 11
V_NECK = math.pi * (NECK_DIA / 2.0) ** 2 * NECK_LEN
V_DISC = math.pi * (DISC_DIA / 2.0) ** 2 * DISC_LEN
V_BORE = math.pi * (BORE_DIA / 2.0) ** 2 * TOTAL_LEN
V_TOTAL = V_NECK + V_DISC - V_BORE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 26 = 26 in).
    await set_global(adapter, "NeckDia", f"{NECK_DIA}mm")
    await set_global(adapter, "NeckLen", f"{NECK_LEN}mm")
    await set_global(adapter, "DiscDia", f"{DISC_DIA}mm")
    await set_global(adapter, "DiscLen", f"{DISC_LEN}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped blank: a Front-plane half-profile revolved about the Y axis (the
    # knob-shaft idiom): the centerline merges into the (0, 0)/(0, TOTAL_LEN)
    # profile corners at creation, so the closed chain's own constraints
    # define it too. Emission order (anchor vertex 0 at the origin -> 0 anchor
    # dims): L0 neck radius (H), L1 neck length (V), L2 disc step (H), L3 disc
    # length (V); the top edge and the axis closure come from closure.
    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check("axis centerline", await adapter.add_centerline(0.0, 0.0, 0.0, TOTAL_LEN))
    profile_pts = [
        (0.0, 0.0),
        (NECK_DIA / 2.0, 0.0),
        (NECK_DIA / 2.0, NECK_LEN),
        (DISC_DIA / 2.0, NECK_LEN),
        (DISC_DIA / 2.0, TOTAL_LEN),
        (0.0, TOTAL_LEN),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(
        adapter, profile_lines, profile_pts, label="nut", dims=profile,
        names=["NeckRadius", "NeckLength", "DiscStep", "DiscLength"],
        drives=[
            '"NeckDia" / 2',
            '"NeckLen"',
            '("DiscDia" - "NeckDia") / 2',
            '"DiscLen"',
        ],
    )
    await ensure_fully_defined(adapter, "nut profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "NutProfile")
    drive_jobs += profile.apply(adapter, "NutProfile")
    check("revolve nut", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Nut")
    expected = V_NECK + V_DISC
    await volume_check(adapter, "nut blank", expected, 0.005 * expected)

    # Shaft bore along the axis: Top-plane circle on the origin (on-axis, so
    # define_circle records only the diameter), cut both ways past the length.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "shaft bore",
        dims=bore, names=("BoreCx", "BoreCz", "ShaftBoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * TOTAL_LEN + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftBore")
    expected -= V_BORE
    await volume_check(adapter, "shaft bore", expected, 0.01 * V_BORE)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven nut (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

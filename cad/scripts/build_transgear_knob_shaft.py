r"""Reproduction script: transgear knob shaft (book ch. 23, pp. 56-59).

The shaft riding the latch arm's small hub: it carries the mounted
removable gear (chain-wrapped, ch. 23 -- the chain rides the removable's
teeth directly) at the machine-inboard end, the fine 24T pinion near the
outboard end, and ends in the large brass thumb knob (engineerguy
v4_transgear_008/020). The knob's reeding is omitted (simplification --
the reeding recipe needs an X-axis layout and this part's stack is sized
along its axis).

Layout: axis +Y from the chain-side (machine-inboard) end at the
origin; the assembly rotates +Y to -Z (machine front). The chain plane
sits inboard at machine z -81 (see build_drive_train_assembly.py), so
the shaft is long: removable gear near y 0, latch hub at ~y 45, fine
pinion at ~y 55, knob at the outboard end. Dimensions:
cad/DIMENSIONS.md ch. 23 (M6.4 dims; M6.8 ch23-topology stack).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_knob_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    SketchDims,
    add_line_chain,
    apply_material,
    check,
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

PART_NAME = "transgear-knob-shaft"
MATERIAL = "Brass"

SHAFT_DIA = 0.375 * IN  # 9.525 (low)
SHAFT_LEN = 58.0  # machine z -76.5 (chain end) .. -134.5 (knob face): room for
# the fine 24T pinion at z -134..-128 just behind the knob; the knob then ends
# at -141.0, level with the transgear-stub collar band (to -141.5). Crossing
# the disc band z is safe since M6.8: the latch C2C 66.05 holds the shaft
# 24.6 clear of the disc rim (r 41.49)
KNOB_DIA = 20.0  # large brass thumb knob (low)
KNOB_LEN = 6.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two diameters and the two axial
    # lengths. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 58 =
    # 58 in); SHAFT_DIA is already 0.375 in expressed in mm, so it goes in as
    # "9.525mm".
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLen", f"{SHAFT_LEN}mm")
    await set_global(adapter, "KnobDia", f"{KNOB_DIA}mm")
    await set_global(adapter, "KnobLen", f"{KNOB_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    y_tip = SHAFT_LEN + KNOB_LEN
    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, y_tip),
    )
    profile_pts = [
        (0.0, 0.0),
        (SHAFT_DIA / 2.0, 0.0),
        (SHAFT_DIA / 2.0, SHAFT_LEN),
        (KNOB_DIA / 2.0, SHAFT_LEN),
        (KNOB_DIA / 2.0, y_tip),
        (0.0, y_tip),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, 0)/(0, y_tip) profile corners at
    # creation, so the closed chain's own constraints define it too.
    # Emission order (anchor vertex 0 at the origin -> 0 anchor dims): the
    # per-segment distance dims skipping the last of each direction -- L0 shaft
    # radius (H), L1 shaft length (V), L2 knob step radius (H), L3 knob length
    # (V); L4 (knob radius) and L5 (full length) are the closure of their
    # directions. The step is the radius DIFFERENCE, driven as a derived expr.
    await define_rectilinear_chain(
        adapter, profile_lines, profile_pts, label="shaft", dims=profile,
        names=["ShaftRadius", "ShaftLength", "KnobStep", "KnobLength"],
        drives=[
            '"ShaftDia" / 2',
            '"ShaftLen"',
            '("KnobDia" - "ShaftDia") / 2',
            '"KnobLen"',
        ],
    )
    await ensure_fully_defined(adapter, "shaft profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += profile.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")

    expected = math.pi * (
        (SHAFT_DIA / 2.0) ** 2 * SHAFT_LEN + (KNOB_DIA / 2.0) ** 2 * KNOB_LEN
    )
    await volume_check(adapter, "shaft", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven shaft (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

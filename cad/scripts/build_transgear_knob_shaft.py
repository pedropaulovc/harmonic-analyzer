r"""Reproduction script: transgear knob shaft (book ch. 23, pp. 56-59).

The shaft riding the latch arm's small hub: it carries the mounted
removable gear (chain-wrapped, ch. 23 -- the chain rides the removable's
teeth directly) at the machine-front end, the 12T DP38 third gear
(build_transgear_pinion.py) on a turned-down O5 seat just behind it (at
DP 38 the 12T root sits below a 3/8" shaft's surface, so the seat steps
down), and ends in the large brass thumb knob (engineerguy
v4_transgear_008/020). The knob's reeding is omitted (simplification --
the reeding recipe needs an X-axis layout and this part's stack is sized
along its axis).

Layout: axis +Y, origin at the FRONT face of the removable seat; the
assembly rotates +Y to +Z (machine back). Front stub y -FRONT_STUB..0 (the
thread the thumbnut runs onto, modelled plain: machine z -167.0..-157.5),
front section y 0..9.1 (removable seat, machine z -157.5..-148.4), O5
pinion seat y 9.1..14.6, rear section y 14.6..27.5 (latch small hub near
the knob), knob y 27.5..34. The stub (2026-09-02, ch23 p.58/59) carries the
knurled thumbnut (build_transgear_thumbnut.py) that retains the removable;
its length is sized in the paper-drive assembly so the shaft end lands
inside the nut's disc (past its mid-depth, short of its front face).
Dimensions: memory/paper-drive-rework.md E7/E8.

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
FRONT_STUB = 9.5  # thumbnut thread stub in front of the removable seat
# (machine z -167.0..-157.5): the nut spans -156.45..-167.45, so the shaft
# end sits 0.45 inside the nut's front face and 3.05 past its disc mid-depth
# (paper-drive _assert_thumbnut_fit pins both).
FRONT_LEN = 9.1  # removable seat (machine z -157.5..-148.4)
SEAT_DIA = 5.0  # turned-down third-gear seat (12T DP38 root < 3/8" surface)
SEAT_LEN = 5.5  # third gear face 4 + 1.5 clearance (z -148.4..-142.9)
REAR_LEN = 12.9  # to the knob face; latch small hub rides z -132.75..-130.15
KNOB_DIA = 20.0  # large brass thumb knob (low)
KNOB_LEN = 6.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section diameters and axial
    # lengths. The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 12.5 =
    # 12.5 in); SHAFT_DIA is already 0.375 in expressed in mm, so it goes in as
    # "9.525mm".
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "FrontStub", f"{FRONT_STUB}mm")
    await set_global(adapter, "FrontLen", f"{FRONT_LEN}mm")
    await set_global(adapter, "SeatDia", f"{SEAT_DIA}mm")
    await set_global(adapter, "SeatLen", f"{SEAT_LEN}mm")
    await set_global(adapter, "RearLen", f"{REAR_LEN}mm")
    await set_global(adapter, "KnobDia", f"{KNOB_DIA}mm")
    await set_global(adapter, "KnobLen", f"{KNOB_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    y_seat = FRONT_LEN + SEAT_LEN
    y_knob = y_seat + REAR_LEN
    y_tip = y_knob + KNOB_LEN
    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, -FRONT_STUB, 0.0, y_tip),
    )
    profile_pts = [
        (0.0, -FRONT_STUB),
        (SHAFT_DIA / 2.0, -FRONT_STUB),
        (SHAFT_DIA / 2.0, FRONT_LEN),
        (SEAT_DIA / 2.0, FRONT_LEN),
        (SEAT_DIA / 2.0, y_seat),
        (SHAFT_DIA / 2.0, y_seat),
        (SHAFT_DIA / 2.0, y_knob),
        (KNOB_DIA / 2.0, y_knob),
        (KNOB_DIA / 2.0, y_tip),
        (0.0, y_tip),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, -FRONT_STUB)/(0, y_tip) profile
    # corners at creation, so the closed chain's own constraints define it too.
    # Emission order: the per-segment distance dims in line order, skipping the
    # last of each direction (the final horizontal top edge and the vertical
    # closure are supplied by closure) -- L0 shaft radius (H), L1 stub + front
    # length (V), L2 seat step down (H), L3 seat length (V), L4 seat step up
    # (H), L5 rear length (V), L6 knob step (H), L7 knob length (V); THEN the
    # anchor: vertex 0 sits on the axis at (0, -FRONT_STUB), so it emits ONE
    # vertical distance dim (the stub). Steps are radius DIFFERENCES, driven as
    # derived exprs.
    await define_rectilinear_chain(
        adapter, profile_lines, profile_pts, label="shaft", dims=profile,
        names=[
            "ShaftRadius", "FrontLength", "SeatStepDown", "SeatLength",
            "SeatStepUp", "RearLength", "KnobStep", "KnobLength", "FrontStub",
        ],
        drives=[
            '"ShaftDia" / 2',
            '"FrontStub" + "FrontLen"',
            '"ShaftDia" / 2 - "SeatDia" / 2',
            '"SeatLen"',
            '"ShaftDia" / 2 - "SeatDia" / 2',
            '"RearLen"',
            '("KnobDia" - "ShaftDia") / 2',
            '"KnobLen"',
            '"FrontStub"',
        ],
    )
    await ensure_fully_defined(adapter, "shaft profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs += profile.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")

    expected = math.pi * (
        (SHAFT_DIA / 2.0) ** 2 * (FRONT_STUB + FRONT_LEN + REAR_LEN)
        + (SEAT_DIA / 2.0) ** 2 * SEAT_LEN
        + (KNOB_DIA / 2.0) ** 2 * KNOB_LEN
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

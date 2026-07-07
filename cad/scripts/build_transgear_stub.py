r"""Reproduction script: transgear stud (book ch. 23, pp. 56-59, 62-63).

The stepped steel stud that plugs into the transgear bracket's bore
(build_transgear_bracket.py, on the support bar's back) and carries the
whole fixed-reduction stack: a 3/8" base section through the bracket and
the latch arm's big hub, then a turned-down O5 front seat for the 12T DP30
feed pinion + 120T disc (their bores cannot take 3/8" -- the 12T base
circle r 4.92 sits under the wall), ending in a retaining collar (the
photo's end hardware collapsed to a collar -- simplification).

Layout: axis +Y from the bracket-back end at the origin; the assembly
rotates +Y to -Z (machine front). Base y 0..9.1 (bracket + arm hub), seat
y 9.1..22.9 (feed pinion + disc), collar 22.9..26.9.
Dimensions: memory/paper-drive-rework.md E7/E8.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_stub.py
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

PART_NAME = "transgear-stub"
MATERIAL = "Plain Carbon Steel"

BASE_DIA = 0.375 * IN  # 9.525 machine-standard stock (low)
BASE_LEN = 9.1  # bracket plate (4) + gap + latch big hub (z -125.9..-135)
SEAT_DIA = 5.0  # turned-down gear seat (feed pinion + disc bores)
SEAT_LEN = 13.8  # feed pinion 9.5 + disc 3 + 0.9 slack (z -135..-148.8)
COLLAR_DIA = 14.0
COLLAR_LEN = 4.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section diameters and lengths.
    # The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (so the 3/8" base
    # is carried as its 9.525 mm value, not an unsuffixed 9.525 read as inches).
    await set_global(adapter, "BaseDia", f"{BASE_DIA}mm")
    await set_global(adapter, "BaseLen", f"{BASE_LEN}mm")
    await set_global(adapter, "SeatDia", f"{SEAT_DIA}mm")
    await set_global(adapter, "SeatLen", f"{SEAT_LEN}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarLen", f"{COLLAR_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    y_seat = BASE_LEN + SEAT_LEN
    y_tip = y_seat + COLLAR_LEN
    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, y_tip),
    )
    profile_pts = [
        (0.0, 0.0),
        (BASE_DIA / 2.0, 0.0),
        (BASE_DIA / 2.0, BASE_LEN),
        (SEAT_DIA / 2.0, BASE_LEN),
        (SEAT_DIA / 2.0, y_seat),
        (COLLAR_DIA / 2.0, y_seat),
        (COLLAR_DIA / 2.0, y_tip),
        (0.0, y_tip),
    ]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, 0)/(0, y_tip) profile corners at
    # creation, so the closed chain's own constraints define it too. Emission
    # order = the kept per-segment distance dims in line order (each direction's
    # last segment is closure-supplied and skipped): seg0 base radius, seg1 base
    # length, seg2 seat step (radius drop), seg3 seat length, seg4 collar step
    # (radius rise), seg5 collar length; the origin anchor at (0, 0) adds no dim.
    await define_rectilinear_chain(
        adapter, profile_lines, profile_pts, label="stub", dims=profile,
        names=[
            "BaseRadius", "BaseLength", "SeatStep",
            "SeatLength", "CollarStep", "CollarLength",
        ],
        drives=[
            '"BaseDia" / 2',
            '"BaseLen"',
            '"BaseDia" / 2 - "SeatDia" / 2',
            '"SeatLen"',
            '"CollarDia" / 2 - "SeatDia" / 2',
            '"CollarLen"',
        ],
    )
    await ensure_fully_defined(adapter, "stub profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "StubProfile")
    drive_jobs += profile.apply(adapter, "StubProfile")
    check("revolve stub", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Stub")

    expected = math.pi * (
        (BASE_DIA / 2.0) ** 2 * BASE_LEN
        + (SEAT_DIA / 2.0) ** 2 * SEAT_LEN
        + (COLLAR_DIA / 2.0) ** 2 * COLLAR_LEN
    )
    await volume_check(adapter, "stub", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven stub (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

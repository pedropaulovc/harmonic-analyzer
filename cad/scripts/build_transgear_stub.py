r"""Reproduction script: transgear stud (book ch. 23, pp. 56-59).

The plain 3/8" steel stud that plugs into the pinion bar's hole and
carries the rack pinion, the fixed transgear pinion and the latch arm's
big hub. A retaining collar at the outboard end keeps the stack on (the
photo's end hardware collapsed to a collar -- simplification).

Layout: axis +Y from the bar-side end at the origin; the assembly
rotates +Y to -Z (machine front). Shaft y 0..36, collar 36..40.
Dimensions: cad/DIMENSIONS.md ch. 23 (M6.4, low/derived).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_transgear_stub.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "transgear-stub"
MATERIAL = "Plain Carbon Steel"

SHAFT_DIA = 0.375 * IN  # 9.525 machine-standard stock (low)
SHAFT_LEN = 36.0  # bar (z -105..-117) through rack pinion (-137.5) (derived)
COLLAR_DIA = 14.0
COLLAR_LEN = 4.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    y_tip = SHAFT_LEN + COLLAR_LEN
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
        (COLLAR_DIA / 2.0, SHAFT_LEN),
        (COLLAR_DIA / 2.0, y_tip),
        (0.0, y_tip),
    ]
    profile = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, 0)/(0, y_tip) profile corners at
    # creation, so the closed chain's own constraints define it too.
    await define_rectilinear_chain(adapter, profile, profile_pts, label="stub")
    await ensure_fully_defined(adapter, "stub profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    check("revolve stub", await adapter.create_revolve(RevolveParameters(angle=360.0)))

    expected = math.pi * (
        (SHAFT_DIA / 2.0) ** 2 * SHAFT_LEN + (COLLAR_DIA / 2.0) ** 2 * COLLAR_LEN
    )
    res = await adapter.get_mass_properties()
    vol = float(res.data.volume) if res.is_success else float("nan")
    print(f"  volume: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"volume {vol:.1f} != analytic {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

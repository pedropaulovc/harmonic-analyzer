r"""Reproduction script: magnifying-wheel axle (book ch. 21, pp. 50-51).

The stud that mounts the magnifying wheel on its support bar: a flange
seated on the bar's front face, a O5 stud the wheel's bore rides, and a
retaining collar at the stud tip (the photo's washer + hex nut collapsed
to one round collar -- simplification).

Layout: axle axis +Y from the origin at the flange's bar-side face; the
assembly rotates it so +Y points -Z (machine front). Flange y 0..3,
stud 3..17, wheel hub rides 3..13, collar 13..17. Dimensions:
cad/DIMENSIONS.md ch. 21 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_wheel_axle.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "wheel-axle"
MATERIAL = "Plain Carbon Steel"

FLANGE_DIA = 35.0  # seats on the support bar face (low)
FLANGE_LEN = 3.0
STUD_DIA = 5.0  # wheel bore O5 rides this (med: wheel part)
STUD_LEN = 14.0  # flange face -> tip
COLLAR_DIA = 9.0  # washer + nut, collapsed (low)
COLLAR_LEN = 4.0  # at the stud tip


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Stepped revolve profile about the Y axis (Front sketch).
    y_tip = FLANGE_LEN + STUD_LEN
    y_collar = y_tip - COLLAR_LEN
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, y_tip),
    )
    profile_pts = [
        (0.0, 0.0),
        (FLANGE_DIA / 2.0, 0.0),
        (FLANGE_DIA / 2.0, FLANGE_LEN),
        (STUD_DIA / 2.0, FLANGE_LEN),
        (STUD_DIA / 2.0, y_collar),
        (COLLAR_DIA / 2.0, y_collar),
        (COLLAR_DIA / 2.0, y_tip),
        (0.0, y_tip),
    ]
    profile = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the (0, 0)/(0, y_tip) profile corners at
    # creation, so the closed chain's own constraints define it too.
    await define_rectilinear_chain(adapter, profile, profile_pts, label="axle")
    await ensure_fully_defined(adapter, "axle profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    check("revolve axle", await adapter.create_revolve(RevolveParameters(angle=360.0)))

    expected = math.pi * (
        (FLANGE_DIA / 2.0) ** 2 * FLANGE_LEN
        + (STUD_DIA / 2.0) ** 2 * (STUD_LEN - COLLAR_LEN)
        + (COLLAR_DIA / 2.0) ** 2 * COLLAR_LEN
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

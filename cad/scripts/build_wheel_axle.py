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

    uv run python cad\scripts\build_wheel_axle.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
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

    # Editable knobs (Tools > Equations): the four stepped diameters + the two
    # axial lengths. The mm suffix is load-bearing -- this is an INCH document and
    # the equation manager reads BARE numbers in document units (an unsuffixed 14
    # = 14 in). Each profile dim below is driven from these via the equation
    # strings declared at the define call.
    await set_global(adapter, "FlangeDia", f"{FLANGE_DIA}mm")
    await set_global(adapter, "FlangeLen", f"{FLANGE_LEN}mm")
    await set_global(adapter, "StudDia", f"{STUD_DIA}mm")
    await set_global(adapter, "StudLen", f"{STUD_LEN}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarLen", f"{COLLAR_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stepped revolve profile about the Y axis (Front sketch).
    y_tip = FLANGE_LEN + STUD_LEN
    y_collar = y_tip - COLLAR_LEN
    profile_dims = SketchDims()
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
    # Emission order = the per-segment distance dims in line order, skipping the
    # last segment of each direction (closure supplies it): flange-radius (H),
    # flange-length (V), flange->stud step (H), stud run (V), stud->collar step
    # (H), collar-length (V). Anchor vertex 0 is the origin -> no anchor dims.
    await define_rectilinear_chain(
        adapter, profile, profile_pts, label="axle", dims=profile_dims,
        names=["FlangeRadius", "FlangeLength", "FlangeStudStep",
               "StudRunLength", "StudCollarStep", "CollarLength"],
        drives=['"FlangeDia" / 2', '"FlangeLen"', '("FlangeDia" - "StudDia") / 2',
                '"StudLen" - "CollarLen"', '("CollarDia" - "StudDia") / 2',
                '"CollarLen"'],
    )
    await ensure_fully_defined(adapter, "axle profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "AxleProfile")
    drive_jobs += profile_dims.apply(adapter, "AxleProfile")
    check("revolve axle", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Axle")

    expected = math.pi * (
        (FLANGE_DIA / 2.0) ** 2 * FLANGE_LEN
        + (STUD_DIA / 2.0) ** 2 * (STUD_LEN - COLLAR_LEN)
        + (COLLAR_DIA / 2.0) ** 2 * COLLAR_LEN
    )
    await volume_check(adapter, "axle", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven axle (equations neutral)", expected, 0.005 * expected)

    # Named stud axis (local Y through the origin = the revolve axis) so the
    # magnifying wheel revolves on it in the M6 mated-DOF assembly.
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "stud axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

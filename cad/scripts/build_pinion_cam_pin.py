r"""Reproduction script: pinion cam-follower pin (book ch. 25; 2 used).

The small bright pin pressed through each swing strap's tail cross-bore
(build_pinion_bracket.py CAM_BORE/CAM_DROP), protruding west over the
lift rod (p. 69 close-up, the pin the rotation arrows lift). The lift
rod's radial cam pin (build_pinion_lift_rod.py) sweeps up beneath this
follower and lifts it, swinging the drum east into mesh; the return
spring (build_pinion_spring.py) parks it back disengaged.

Layout: pin axis Z, mid-plane at z 0 (z -8.75..+8.75) -- the exact
mid-plane symmetry the chirality mirror's ("z", 0.0) MIRROR_PLANE entry
declares (see _transforms.py). Placed rotated onto the strap's leaned
bore axis in the assembly; the west/east span split about the bore is
set by the axial mate there (build_drive_train SPAN comment).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_cam_pin.py
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
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "pinion-cam-pin"
MATERIAL = "Plain Carbon Steel"  # bright steel, like the rods it works with

PIN_DIA = 3.0  # press fit in the strap tail bore -- build_pinion_bracket
# CAM_BORE must match (photo-scaled vs the 6.35 shafts in p.69, low)
PIN_LEN = 17.5  # through the tail cap (~13 of material) + the west working
# protrusion over the lift rod's sweep band + a short east proud end; the
# exact split is the assembly's axial seat (build_drive_train cam asserts
# bound both ends: west end clear of the parked down-pin plane by >= 1,
# east end >= 0.25 off the return spring's blade)

PIN_R = PIN_DIA / 2.0
V_PIN = math.pi * PIN_R**2 * PIN_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 3 = 3 in). The extrude length is a feature
    # parameter (built with the literal below); PinLen is declared so a GUI
    # edit sees the knob.
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis pin (origin centre): define_circle emits only the diameter dim.
    # Mid-plane extrude (both_directions, depth = TOTAL) keeps the part's z=0
    # symmetry exact -- the MIRROR_PLANE ("z", 0.0) contract.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, PIN_R, "pin", dims=pin,
        names=("PinCx", "PinCz", "PinDia"),
        drives=(None, None, '"PinDia"'),
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += pin.apply(adapter, "PinProfile")
    check(
        "extrude pin",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PIN_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Pin")
    await volume_check(adapter, "pin", V_PIN, 0.005 * V_PIN)

    # Named central axis (Axis1): mates coaxial to the strap's cam-pin bore
    # axis in the assembly, riding the p2 swing group.
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", V_PIN, 0.005 * V_PIN)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

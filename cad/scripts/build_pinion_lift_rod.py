r"""Reproduction script: pinion lift rod with cam pins (book ch. 25).

The second Ø6.35 rod of the swing rig, running through the pivot
blocks' west bores parallel to the strap torque shaft. Turning it by
the engage lever (build_pinion_lever.py, rooted on its front end)
sweeps two short radial cam pins up beneath the straps' cam-follower
pins (build_pinion_cam_pin.py, pressed through the strap tails),
lifting the followers and swinging the alignment pinion east into mesh
(p. 68-69 close-ups + engineerguy 4/4 7:15). Parked the pins point
straight DOWN, clear of the followers (the disengaged rest state); the
cam contact band and clearances are asserted in build_drive_train's
cam block (PR5 -- supersedes the old "shortened, non-working pins"
simplification, DIMENSIONS.md Appendix C).

Layout: rod axis Z, z 0..210; pins along -Y at z 42.5 and 190.5, axis
to tip 11.175 (8 proud of the rod surface).

Volume gate: rod exact; each pin adds pi*r^2*L minus the numerically
integrated rod/pin overlap wedge (Simpson, deterministic).

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
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "pinion-lift-rod"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

ROD_DIA = 6.35  # rides the block bores, same stock as the torque shaft (derived)
ROD_LEN = 210.0  # machine z -120..+90: front end proud for the lever root
# (ahead of the forward front block), back end 2 proud of the back pivot
# block face (derived)
PIN_DIA = 3.0  # cam pin, photo-scaled vs the rod (low). Thinned 4.0 -> 3.0
# with the PR5 working cam: at Ø4 the parked shaft sat 0.05 off the strap's
# follower pin (build_drive_train's cam scan), under every design margin.
PIN_TIP = 11.175  # rod axis to pin tip -- tip at machine y 51.625 (derived)
PIN_STATIONS = (42.5, 190.5)  # machine z -77.5 / +70.5: inside each strap's
# z band (straps at -80.25..-75.25 and +68.45..+73.45)
PIN_END_INSIDE = 2.0  # pin extrusion ends 2.0 up inside the rod: above the
# deepest rod-surface sag across the pin's width (2.466 at x +-2), so the
# merge is a clean overlap, not a point tangency

ROD_R = ROD_DIA / 2.0
PIN_R = PIN_DIA / 2.0
PIN_LEN = PIN_TIP - PIN_END_INSIDE  # 9.175 extrusion length

V_ROD = math.pi * ROD_R**2 * ROD_LEN


def _pin_overlap() -> float:
    """Pin volume already inside the rod: integral over the pin cross-section
    of (rod surface depth - PIN_END_INSIDE), Simpson with 2000 panels."""
    n = 2000
    h = 2.0 * PIN_R / n

    def f(x: float) -> float:
        return (math.sqrt(ROD_R**2 - x**2) - PIN_END_INSIDE) * 2.0 * math.sqrt(
            max(PIN_R**2 - x**2, 0.0)
        )

    total = f(-PIN_R) + f(PIN_R)
    for i in range(1, n):
        total += (4.0 if i % 2 else 2.0) * f(-PIN_R + i * h)
    return total * h / 3.0


V_PIN_ADDED = math.pi * PIN_R**2 * PIN_LEN - _pin_overlap()


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the rod + pin diameters, the two pin
    # stations along the rod, and the pin reach. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 6.35 = 6.35 in). RodLen, PinTip and
    # PinEndInside feed feature-parameter extrude lengths (built with the literals
    # below) -- declared so a GUI edit sees the knobs.
    await set_global(adapter, "RodDia", f"{ROD_DIA}mm")
    await set_global(adapter, "RodLen", f"{ROD_LEN}mm")
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinTip", f"{PIN_TIP}mm")
    await set_global(adapter, "PinStationFront", f"{PIN_STATIONS[0]}mm")
    await set_global(adapter, "PinStationBack", f"{PIN_STATIONS[1]}mm")
    await set_global(adapter, "PinEndInside", f"{PIN_END_INSIDE}mm")

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

    # Both cam pins from one Top sketch (sketch (u, v) -> global (X, -Z),
    # probe-verified), extruded +Y from y -PIN_TIP up into the rod. Each pin
    # circle sits on the sketch v axis (x 0): one centre dim (the station, an
    # unsigned distance driven by the positive station global) + diameter.
    pins = SketchDims()
    check("create_sketch pins", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, -PIN_STATIONS[0], PIN_R, "pin front", dims=pins,
        names=("PinFrontCx", "PinFrontZ", "PinFrontDia"),
        drives=(None, '"PinStationFront"', '"PinDia"'),
    )
    await define_circle(
        adapter, 0.0, -PIN_STATIONS[1], PIN_R, "pin back", dims=pins,
        names=("PinBackCx", "PinBackZ", "PinBackDia"),
        drives=(None, '"PinStationBack"', '"PinDia"'),
    )
    await ensure_fully_defined(adapter, "pins sketch")
    check("exit_sketch pins", await adapter.exit_sketch())
    name_last_feature(adapter, "PinsProfile")
    drive_jobs += pins.apply(adapter, "PinsProfile")
    extrude_at_offset(adapter, PIN_LEN, -PIN_TIP)
    name_last_feature(adapter, "CamPins")
    expected = volume + 2.0 * V_PIN_ADDED
    await volume_check(adapter, "cam pins", expected, 0.02 * 2.0 * V_PIN_ADDED)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven lift rod (equations neutral)", expected, 0.02 * 2.0 * V_PIN_ADDED
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

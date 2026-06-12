r"""Reproduction script: pinion lift rod with cam pins (book ch. 25).

The second Ø6.35 rod of the swing rig, running through the pivot
blocks' west bores parallel to the strap torque shaft. Turning it by
the engage lever (build_pinion_lever.py, rooted on its front end)
rotates two short cam pins against the swing straps, lifting the
alignment pinion into mesh (p. 68 close-ups + engineerguy 4/4 7:15).
The real pins are longer and bear obliquely on the strap flanks; here
they are shortened and parked pointing straight DOWN (the disengaged
rest state) -- documented simplification, DIMENSIONS.md Appendix C.

Layout: rod axis Z, z 0..210; pins along -Y at z 42.5 and 190.5, axis
to tip 11.175 (8 proud of the rod surface).

Volume gate: rod exact; each pin adds pi*r^2*L minus the numerically
integrated rod/pin overlap wedge (Simpson, deterministic).

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_lift_rod.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    apply_color,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)

PART_NAME = "pinion-lift-rod"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.68)

ROD_DIA = 6.35  # rides the block bores, same stock as the torque shaft (derived)
ROD_LEN = 210.0  # machine z -120..+90: front end proud for the lever root
# (ahead of the forward front block), back end 2 proud of the back pivot
# block face (derived)
PIN_DIA = 4.0  # cam pin, photo-scaled vs the rod (low)
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

    # Rod along +Z.
    check("create_sketch rod", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, ROD_R, "rod")
    await ensure_fully_defined(adapter, "rod sketch")
    check("exit_sketch rod", await adapter.exit_sketch())
    check(
        "extrude rod",
        await adapter.create_extrusion(ExtrusionParameters(depth=ROD_LEN)),
    )
    volume = await volume_check(adapter, "rod", V_ROD, 0.005 * V_ROD)

    # Both cam pins from one Top sketch (sketch (u, v) -> global (X, -Z),
    # probe-verified), extruded +Y from y -PIN_TIP up into the rod.
    check("create_sketch pins", await adapter.create_sketch("Top"))
    for station in PIN_STATIONS:
        await define_circle(adapter, 0.0, -station, PIN_R, f"pin z{station:g}")
    await ensure_fully_defined(adapter, "pins sketch")
    check("exit_sketch pins", await adapter.exit_sketch())
    extrude_at_offset(adapter, PIN_LEN, -PIN_TIP)
    await volume_check(
        adapter,
        "cam pins",
        volume + 2.0 * V_PIN_ADDED,
        0.02 * 2.0 * V_PIN_ADDED,
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

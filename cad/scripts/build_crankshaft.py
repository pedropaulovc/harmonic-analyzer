r"""Reproduction script: crankshaft (book ch. 11, pp. 12-15).

Short Ø3/8 in steel shaft in the green pedestal bearing at the base
corner: crank arm on the outboard end (affixed by a removable tapered
pin so the crankshaft gear can be changed), chain sprocket and the 4:1
drive pinion inboard. Modeled as the plain shaft with the tapered-pin
cross-hole; the crank arm/pin/handle and the gears are separate parts
(`build_crank_arm.py` etc., gears in M4).

Dimensions: cad/DIMENSIONS.md "Chapter 11" - dia legacy (med), length
derived from eight-views 8/8 pedestal proportions (low).

Layout: shaft axis along +Y, outboard (crank) end at the origin;
tapered-pin cross-hole along Z at the crank-seat height.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_crankshaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    name_bore_axis,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "crankshaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

SHAFT_DIA = 0.375 * IN  # ch11: legacy ShaftDiameter, uncontradicted
SHAFT_LENGTH = 120.0  # ch11: derived (crank seat + pedestal bearing + seats)
PIN_HOLE_HEIGHT = 12.0  # crank hub centre above the outboard end

# Removable taper pin (build_crank_pin.py): Ø6 big -> Ø5 small over 45 mm. The
# cross-bore is reamed to MATCH it (a true cone + radial clearance) so the pin
# seats without solid interference. The pin's small end seats flush at the
# crank-arm's far boss wall, ARM_BOSS_HALF_WIDTH out from the shaft axis, which
# fixes the along-pin distance (s) of each cross-section -> the bore radius.
PIN_BIG_DIA = 6.0  # DIMENSIONS.md ch11: pin big end (low)
PIN_SMALL_DIA = 5.0  # DIMENSIONS.md ch11: pin small end / cross-hole (low)
PIN_LEN = 45.0
PIN_TAPER_SLOPE = (PIN_BIG_DIA - PIN_SMALL_DIA) / 2.0 / PIN_LEN  # bore-radius gain per mm
PIN_TAPER_DEG = math.degrees(math.atan(PIN_TAPER_SLOPE))  # ~0.637 deg half-angle
PIN_CLEAR = 0.2  # radial clearance (mid-pin section, generous)
ARM_BOSS_HALF_WIDTH = 8.0  # build_crank_arm.py HALF_WIDTH: where the pin seats flush
PIN_BIG_OFFSET = 6.0  # big-end sketch plane, this far to -Z of the shaft axis


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    check("create_sketch shaft", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_DIA / 2.0, "shaft circle")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LENGTH)),
    )
    res = await adapter.get_mass_properties()
    print(f"  volume after shaft: {res.data.volume:.1f} mm^3")
    # expected: pi * 4.7625^2 * 120 = ~8,551 mm^3

    # Tapered-pin cross-hole through the crank seat (along Z), a true CONE
    # matching the removable taper pin (build_crank_pin.py). The pin enters
    # from machine +X (big end); with the drive train's crankshaft re-spin the
    # part's local +Z maps to machine -X, so the bore is widest at local -Z and
    # tapers down toward +Z. A drafted cut narrows with depth, so sketch the big
    # end on an offset plane PIN_BIG_OFFSET to -Z and cut +Z through the shaft.
    pre = (await adapter.get_mass_properties()).data.volume
    s_big = ARM_BOSS_HALF_WIDTH + PIN_BIG_OFFSET  # along-pin distance from the seated end
    r_big = PIN_SMALL_DIA / 2.0 + s_big * PIN_TAPER_SLOPE + PIN_CLEAR
    plane = check(
        "create_plane pin big end",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Front Plane", offset=PIN_BIG_OFFSET, flip=True
            )
        ),
    )
    check("create_sketch pin hole", await adapter.create_sketch(plane.name))
    await define_circle(adapter, 0.0, PIN_HOLE_HEIGHT, r_big, "pin hole big end")
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * PIN_BIG_OFFSET, draft_angle=PIN_TAPER_DEG)
        ),
    )
    res = await adapter.get_mass_properties()
    removed = pre - res.data.volume
    print(f"  pin hole removed {removed:.1f} mm^3 (tapered Ø5 cross-drill) -> {res.data.volume:.1f}")
    if removed < 100.0:
        raise RuntimeError(
            f"pin hole removed only {removed:.1f} mm^3 -- offset plane on the wrong side?"
        )

    # Named central axis (shaft axis = local +Y through the origin) so the
    # crankshaft mates concentric in the pedestal and the crank parts /
    # pinion / chain wheel lock to it (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

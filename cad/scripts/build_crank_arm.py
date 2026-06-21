r"""Reproduction script: crank arm (book ch. 11, pp. 12-15).

The metal crank arm that drives the machine: full-radius boss at the
crankshaft end (bored for the shaft and cross-drilled for the removable
tapered pin), straight arm, square end carrying the handle pivot, and a
fiducial dimple for alignment. The wooden handle and the tapered pin are
separate parts (build_crank_handle.py / build_crank_pin.py); the chain
eyelet (chain lost) is omitted.

Dimensions: cad/DIMENSIONS.md "Chapter 11" — all photo-scaled (low) except
the legacy 3/8" crankshaft bore (med).

Layout: arm length along +X from the origin (shaft bore axis = global Z
through the origin), thickness extruded +Z (0..8). The cross-pin hole runs
along global Y at mid-thickness (global Z = 4 -> Top sketch y = -Z): it is a
true CONE matching the removable taper pin (build_crank_pin.py), reamed from
an offset big-end plane so the pin seats without interference (see the
pin-hole block below). The bore/pivot/dimple through-cuts use mid-plane blind
cuts (depth > extent) because the ThroughAll+both_directions combination fails
live on SW 2026 (MCP issue #38); the dimple uses a mid-plane cut of twice its
depth so the cut direction never matters.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_crank_arm.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    name_bore_axis,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "crank-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

ARM_C2C = 66.0  # DIMENSIONS.md ch11: shaft-to-handle-pivot centres -- REDERIVED
# from the ch30 eight-views (angle 90 side view, scaled to the 280 mm base depth):
# the crank hangs straight down, handle pivot 66 mm below the crankshaft axis,
# landing the handle ~10 mm above the base top. The former 150 (cone-axial scaled,
# low) was >2x too long -- a down-pointing 150 arm would drive the handle below
# the table (med).
ARM_WIDTH = 16.0  # DIMENSIONS.md ch11: arm width (low)
ARM_THICKNESS = 8.0  # DIMENSIONS.md ch11: ~half the arm width, p.12 photo (low)
SQUARE_END_OVERHANG = 10.0  # DIMENSIONS.md ch11: square end past the pivot (low)
SHAFT_BORE_DIA = 0.375 * IN  # 9.525: 3/8" crankshaft (med); the legacy 9.5
# rounding left the bore 0.025 smaller than the shaft (caught in M6.2)
PIVOT_BORE_DIA = 6.0  # DIMENSIONS.md ch11: handle pivot screw (low)
DIMPLE_DIA = 8.0  # DIMENSIONS.md ch11: fiducial indentation (low)
DIMPLE_DEPTH = 0.5  # DIMENSIONS.md ch11: fiducial indentation (low)
DIMPLE_X = 30.0  # DIMENSIONS.md ch11: on the arm near the boss (low)
# Removable taper pin (build_crank_pin.py): Ø6 big -> Ø5 small over 45 mm. The
# cross-bore is reamed to MATCH it (a true cone + radial clearance) so the pin
# seats without solid interference (the straight Ø5 bore it replaced forced the
# pin to be OMITTED from the drive train).
PIN_BIG_DIA = 6.0  # DIMENSIONS.md ch11: pin big end (low)
PIN_SMALL_DIA = 5.0  # DIMENSIONS.md ch11: pin small end / cross-hole (low)
PIN_LEN = 45.0
PIN_TAPER_SLOPE = (PIN_BIG_DIA - PIN_SMALL_DIA) / 2.0 / PIN_LEN  # bore-radius gain per mm
PIN_TAPER_DEG = math.degrees(math.atan(PIN_TAPER_SLOPE))  # ~0.637 deg half-angle
PIN_CLEAR = 0.15  # radial clearance so the pin seats without interference
PIN_BIG_OFFSET = 10.0  # big-end sketch plane, this far to -Y of the boss centre

ARM_END_X = ARM_C2C + SQUARE_END_OVERHANG
HALF_WIDTH = ARM_WIDTH / 2.0
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any extent it crosses


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Arm outline: full-radius boss cap (arc about the origin) + 3 lines.
    check("create_sketch outline", await adapter.create_sketch("Front"))
    arc = check(
        "add_arc boss cap",
        await adapter.add_arc(0.0, 0.0, 0.0, HALF_WIDTH, 0.0, -HALF_WIDTH),
    )
    bottom, right, top = await add_line_chain(
        adapter,
        [
            (0.0, -HALF_WIDTH),
            (ARM_END_X, -HALF_WIDTH),
            (ARM_END_X, HALF_WIDTH),
            (0.0, HALF_WIDTH),
        ],
        close=False,
    )
    check("constraint horizontal bottom", await adapter.add_sketch_constraint(bottom, None, "horizontal"))
    check("constraint vertical right", await adapter.add_sketch_constraint(right, None, "vertical"))
    check("constraint horizontal top", await adapter.add_sketch_constraint(top, None, "horizontal"))
    check(
        f"dimension arm length = {ARM_END_X:g}",
        await adapter.add_sketch_dimension(bottom, None, "linear", ARM_END_X),
    )
    # Boss cap: centre at the origin + radius + both ends on the Y axis
    # fully pin the semicircle; the merged chain follows.
    check(
        "boss centre -> origin",
        await adapter.add_sketch_constraint(f"{arc}.center", "origin", "coincident"),
    )
    check("boss radius", await adapter.add_sketch_dimension(arc, None, "radial", HALF_WIDTH))
    for point in (f"{arc}.start", f"{arc}.end"):
        check(
            f"{point} on Y axis",
            await adapter.add_sketch_constraint(point, "origin", "vertical_points"),
        )
    await ensure_fully_defined(adapter, "arm outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    check(
        "extrude arm",
        await adapter.create_extrusion(ExtrusionParameters(depth=ARM_THICKNESS)),
    )
    vol = await _volume(adapter)
    print(f"  volume after extrude: {vol:.1f} mm^3")

    # Shaft bore + handle pivot bore, one through-cut.
    check("create_sketch bores", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_BORE_DIA / 2.0, "shaft bore")
    await define_circle(adapter, ARM_C2C, 0.0, PIVOT_BORE_DIA / 2.0, "pivot bore")
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after bores: {vol:.1f} mm^3")

    # Fiducial dimple on the Z=0 face (which face carries it is arbitrary
    # until assembly). Mid-plane cut of 2x depth: only the +Z half removes
    # material, so the result is DIMPLE_DEPTH regardless of cut direction.
    check("create_sketch dimple", await adapter.create_sketch("Front"))
    await define_circle(adapter, DIMPLE_X, 0.0, DIMPLE_DIA / 2.0, "dimple")
    await ensure_fully_defined(adapter, "dimple sketch")
    check("exit_sketch dimple", await adapter.exit_sketch())
    check(
        "cut dimple",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * DIMPLE_DEPTH, both_directions=True)
        ),
    )
    vol = await _volume(adapter)
    print(f"  volume after dimple: {vol:.1f} mm^3")

    # Tapered-pin cross-hole along global Y through boss and shaft bore at
    # mid-thickness (global Z = ARM_THICKNESS/2 -> Top sketch y = -Z). The bore
    # is a true cone MATCHING build_crank_pin.py (Ø6 big -> Ø5 small over 45 mm,
    # half-angle ~0.637 deg) so the removable taper pin seats without solid
    # interference. In the drive train the pin enters from machine +X (big end,
    # the grab head) and its small end seats flush at the far boss wall; the
    # arm's local +Y maps to machine -X at rest, so the bore is widest at local
    # -Y and tapers down toward +Y. A drafted cut narrows with depth (the
    # adapter pins the draft inward), so sketch the big end on an offset plane
    # BIG_OFFSET to -Y of the boss and cut +Y through it.
    pre = await _volume(adapter)
    s_big = HALF_WIDTH + PIN_BIG_OFFSET  # along-pin distance from the seated (small) end
    r_big = PIN_SMALL_DIA / 2.0 + s_big * PIN_TAPER_SLOPE + PIN_CLEAR
    plane = check(
        "create_plane pin big end",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=PIN_BIG_OFFSET, flip=True
            )
        ),
    )
    check("create_sketch pin hole", await adapter.create_sketch(plane.name))
    await define_circle(adapter, 0.0, -ARM_THICKNESS / 2.0, r_big, "pin hole big end")
    await ensure_fully_defined(adapter, "pin hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * PIN_BIG_OFFSET, draft_angle=PIN_TAPER_DEG)
        ),
    )
    removed = pre - await _volume(adapter)
    print(f"  pin hole removed {removed:.1f} mm^3 (tapered Ø5 cross-drill)")
    if removed < 50.0:
        raise RuntimeError(
            f"pin hole removed only {removed:.1f} mm^3 -- offset plane on the wrong side?"
        )

    # Named bore/central axis for view-independent assembly mate
    # selection (M6 mated-DOF drive train).
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "shaft bore axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

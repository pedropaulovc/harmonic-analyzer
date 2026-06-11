r"""Reproduction script: summing lever (book ch. 18, pp. 42-43).

The cast-iron knife-edge lever that sums the pull of the 20 channel
springs. M6.4 FULL REWRITE: the legacy SummingLever.cs shape (solid pivot
cylinder + edge ribs + tapering summation tongue + anchor boss on the
plate side) is REFUTED by the p.42/43 close-ups and the calibrated ch. 30
views:

* The pivot is a TUBE (O25, O14 bore) riding a knife-edge bar: the bore
  bottom line IS the pivot line. A central slot (|z| <= 16) through the
  tube clears the knife-mount stud that hangs the knife bar from the
  top crossbar.
* The coefficients plate (20 spring holes at the channel-lever tab line)
  hangs off the tube on the -X side, top face 8 above the knife line.
* A twin-rib web arm runs +X from the tube to a round boss; the counter
  spring hangs from a J-hook (build_boss_hook.py) whose shank plants in
  a vertical O2.6 hole in the boss top (the p.43 black hook + chrome
  ring chain collapsed to one hook part -- simplification).

Part-local origin = the knife-edge line (machine (+15, 990, 0)); X +ve
toward the boss/counter spring, Y up, Z along the knife edge (channel
direction). Dimensions: cad/DIMENSIONS.md ch. 18 (M6.4 revision; med/low).

Volume audit: tube/bore/slot/plate/boss-hole are asserted analytically
(the plate-tube overlap by midpoint-rule integration); the web ribs and
boss merge into curved neighbours, so they get bounded-range checks.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_summing_lever.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "summing-lever"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# DIMENSIONS.md ch18 (M6.4 revision; calibrated p1/p3 + p.42-43 close-ups)
TUBE_OD = 25.0  # pivot tube OD (med)
TUBE_LENGTH = 114.0  # tube span along the knife edge, z +-57 (med)
BORE_DIA = 14.0  # knife bore; bore bottom = knife line (med)
TUBE_CY = BORE_DIA / 2.0  # tube/bore centre sits one bore radius up
SLOT_HALF_Z = 16.0  # central slot clears the knife-mount stud (low)
SLOT_HALF_X = 9.0  # slot stays inside the tube walls (derived)

PLATE_X_MIN = -60.0  # coefficients plate, machine x -45 (med)
PLATE_X_MAX = -10.0  # machine x +5: plate edge merges into the tube (med)
PLATE_TOP_Y = 8.0  # plate top = machine y 998 (med)
PLATE_THICKNESS = 5.1  # 0.2" plate (legacy, uncontradicted)
PLATE_HALF_Z = 76.2  # plate length 152.4 = 6" (legacy, uncontradicted)
HOLE_DIA = 4.5  # spring holes: the installed eye must thread 5.1 plate
# (sqrt(3.25^2 - 2.55^2) = 2.0 reach) -- see build_channel_assembly.py
HOLE_X = -37.10  # machine x -22.10 = channel-lever tab line (derived)
HOLE_COUNT = 20
CHANNEL_Z0 = -67.1  # frame channel j=0 (DIMENSIONS.md ch6)
CHANNEL_PITCH = 7.0565
HOLE_Z_OFFSET = 0.8 - 2.75  # the spring's bottom lead hangs one coil mean
# radius (2.75) off the spring axis (z_j + 0.8) on the helix-start side,
# which the assembly's Ry(+90) maps to -Z -- the hole sits under the LEAD
# (see build_channel_spring_installed.py)

WEB_Y_BOT = 2.0  # twin-rib web band above the knife line (low)
WEB_Y_TOP = 12.0
RIB_X0 = 9.0  # ribs spring from the tube wall at the slot edge (derived)
RIB_X1 = 80.0  # ribs merge into the boss (med)
RIB_HALF_WIDTH = 1.5  # ~3 wide cast ribs (low)
RIB_Z0 = 17.18  # |z| of the rib centreline at RIB_X0 (p.43 plan, low)
RIB_Z1 = 4.27  # |z| at the boss (low)

BOSS_X = 80.0  # machine x 95: counter-spring anchor (med)
BOSS_DIA = 14.0
BOSS_LENGTH = 12.0  # z +-6 (low)
HOOK_HOLE_DIA = 2.6  # boss-hook O3 shank taps in here (low)
HOOK_HOLE_X = 75.5  # machine x 90.5: hook rod tip reaches x 97 (derived)
HOOK_HOLE_DEPTH = 14.0  # half-depth of the mid-plane cut; clears the boss
# top at this x (y 12.36) and bottom (y 1.64)

TUBE_R = TUBE_OD / 2.0
BORE_R = BORE_DIA / 2.0
HOLE_Z = [
    CHANNEL_Z0 + CHANNEL_PITCH * j + HOLE_Z_OFFSET for j in range(HOLE_COUNT)
]


def _slot_removed_volume() -> float:
    """Annulus cross-section area within |x| <= SLOT_HALF_X, times slot span."""
    r, big, x = BORE_R, TUBE_R, SLOT_HALF_X
    a_outer = 2.0 * (x * math.sqrt(big * big - x * x) + big * big * math.asin(x / big))
    a_inner = math.pi * r * r  # bore disc lies fully inside |x| <= 9
    return (a_outer - a_inner) * 2.0 * SLOT_HALF_Z


def _plate_tube_overlap_volume() -> float:
    """Plate slab (y band) clipped to the tube outer disc, x -12.5..-10,
    prism along the full tube length (midpoint rule)."""
    n = 400
    x0, x1 = -TUBE_R, PLATE_X_MAX
    y_bot = PLATE_TOP_Y - PLATE_THICKNESS
    area = 0.0
    for i in range(n):
        x = x0 + (i + 0.5) * (x1 - x0) / n
        h = TUBE_R * TUBE_R - x * x
        if h <= 0.0:
            continue
        half = math.sqrt(h)
        lo = max(y_bot, TUBE_CY - half)
        hi = min(PLATE_TOP_Y, TUBE_CY + half)
        if hi > lo:
            area += (hi - lo) * (x1 - x0) / n
    return area * TUBE_LENGTH


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def _assert_volume(adapter, label: str, expected: float, rel_tol: float) -> float:
    vol = await _volume(adapter)
    print(f"  volume after {label}: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > rel_tol * expected:
        raise RuntimeError(
            f"{label}: volume {vol:.1f} != analytic {expected:.1f} "
            f"(tol {rel_tol * 100:.1f}%)"
        )
    return vol


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # 1. Pivot tube along Z (Front sketch -> mid-plane extrude).
    check("create_sketch tube", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, TUBE_CY, TUBE_R, "tube OD")
    await ensure_fully_defined(adapter, "tube sketch")
    check("exit_sketch tube", await adapter.exit_sketch())
    check(
        "extrude tube",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=TUBE_LENGTH, both_directions=True)
        ),
    )
    expected = math.pi * TUBE_R**2 * TUBE_LENGTH
    await _assert_volume(adapter, "tube", expected, 0.005)

    # 2. Knife bore: bore bottom = the part-local origin = knife line.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, TUBE_CY, BORE_R, "knife bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=TUBE_LENGTH + 6.0, both_directions=True)
        ),
    )
    expected -= math.pi * BORE_R**2 * TUBE_LENGTH
    await _assert_volume(adapter, "bore", expected, 0.005)

    # 3. Central slot for the knife-mount stud (Top sketch, sy = -z).
    check("create_sketch slot", await adapter.create_sketch("Top"))
    slot = await add_line_chain(
        adapter,
        [
            (-SLOT_HALF_X, -SLOT_HALF_Z),
            (SLOT_HALF_X, -SLOT_HALF_Z),
            (SLOT_HALF_X, SLOT_HALF_Z),
            (-SLOT_HALF_X, SLOT_HALF_Z),
        ],
    )
    await ensure_fully_defined(adapter, "slot sketch", fix_entities=slot)
    check("exit_sketch slot", await adapter.exit_sketch())
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=60.0, both_directions=True)
        ),
    )
    expected -= _slot_removed_volume()
    await _assert_volume(adapter, "slot", expected, 0.005)

    # 4. Coefficients plate with the 20 spring holes (nested contours),
    # extruded at a start offset so its top face lands at PLATE_TOP_Y.
    check("create_sketch plate", await adapter.create_sketch("Top"))
    outline = await add_line_chain(
        adapter,
        [
            (PLATE_X_MIN, -PLATE_HALF_Z),
            (PLATE_X_MAX, -PLATE_HALF_Z),
            (PLATE_X_MAX, PLATE_HALF_Z),
            (PLATE_X_MIN, PLATE_HALF_Z),
        ],
    )
    # Direct-to-DB: inference around the freshly dimensioned neighbour
    # makes CreateCircleByRadius fail from the second small hole on.
    set_sketch_direct_db(adapter, True)
    for j, hole_z in enumerate(HOLE_Z):
        await define_circle(adapter, HOLE_X, -hole_z, HOLE_DIA / 2.0, f"hole {j + 1}")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "plate sketch", fix_entities=outline)
    check("exit_sketch plate", await adapter.exit_sketch())
    extrude_at_offset(
        adapter, PLATE_THICKNESS, PLATE_TOP_Y - PLATE_THICKNESS
    )
    v_plate = (
        (PLATE_X_MAX - PLATE_X_MIN) * 2.0 * PLATE_HALF_Z * PLATE_THICKNESS
        - HOLE_COUNT * math.pi * (HOLE_DIA / 2.0) ** 2 * PLATE_THICKNESS
        - _plate_tube_overlap_volume()
    )
    expected += v_plate
    await _assert_volume(adapter, "plate", expected, 0.01)

    # 5. Twin-rib web arm, tube wall -> boss (Top sketch, both strips).
    check("create_sketch web ribs", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    rib_entities: list[str] = []
    for side in (1.0, -1.0):  # sy = -z: +1 strip is the z<0 rib
        rib_entities += await add_line_chain(
            adapter,
            [
                (RIB_X0, side * (RIB_Z0 - RIB_HALF_WIDTH)),
                (RIB_X0, side * (RIB_Z0 + RIB_HALF_WIDTH)),
                (RIB_X1, side * (RIB_Z1 + RIB_HALF_WIDTH)),
                (RIB_X1, side * (RIB_Z1 - RIB_HALF_WIDTH)),
            ],
        )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "web ribs sketch", fix_entities=rib_entities)
    check("exit_sketch web ribs", await adapter.exit_sketch())
    extrude_at_offset(adapter, WEB_Y_TOP - WEB_Y_BOT, WEB_Y_BOT)
    v_rib_solid = (
        2.0 * (RIB_X1 - RIB_X0) * 2.0 * RIB_HALF_WIDTH * (WEB_Y_TOP - WEB_Y_BOT)
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after web ribs: {vol:.1f} mm^3 (+{added:.1f}, solid {v_rib_solid:.1f})")
    if not (0.55 * v_rib_solid <= added <= 1.01 * v_rib_solid):
        raise RuntimeError(
            f"web ribs: added {added:.1f}, expected 55-100% of {v_rib_solid:.1f}"
        )
    expected = vol

    # 6. Counter-spring boss (cylinder along Z at the arm tip).
    check("create_sketch boss", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, BOSS_X, TUBE_CY, BOSS_DIA / 2.0, "boss")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "boss sketch")
    check("exit_sketch boss", await adapter.exit_sketch())
    check(
        "extrude boss",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BOSS_LENGTH, both_directions=True)
        ),
    )
    v_boss_solid = math.pi * (BOSS_DIA / 2.0) ** 2 * BOSS_LENGTH
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after boss: {vol:.1f} mm^3 (+{added:.1f}, solid {v_boss_solid:.1f})")
    if not (0.7 * v_boss_solid <= added <= 1.01 * v_boss_solid):
        raise RuntimeError(
            f"boss: added {added:.1f}, expected 70-100% of {v_boss_solid:.1f}"
        )
    expected = vol

    # 7. Vertical O2.6 hook-shank hole in the boss top (Top sketch).
    check("create_sketch hook hole", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, HOOK_HOLE_X, 0.0, HOOK_HOLE_DIA / 2.0, "hook hole")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "hook hole sketch")
    check("exit_sketch hook hole", await adapter.exit_sketch())
    check(
        "cut hook hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * HOOK_HOLE_DEPTH, both_directions=True)
        ),
    )
    # Boss chord height at the hole x (the hole passes top-to-bottom).
    chord = 2.0 * math.sqrt((BOSS_DIA / 2.0) ** 2 - (HOOK_HOLE_X - BOSS_X) ** 2)
    v_hole = math.pi * (HOOK_HOLE_DIA / 2.0) ** 2 * chord
    before = expected
    vol = await _volume(adapter)
    removed = before - vol
    print(f"  volume after hook hole: {vol:.1f} mm^3 (-{removed:.1f}, chord {v_hole:.1f})")
    if not (0.8 * v_hole <= removed <= 1.15 * v_hole):
        raise RuntimeError(
            f"hook hole: removed {removed:.1f}, expected ~{v_hole:.1f}"
        )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

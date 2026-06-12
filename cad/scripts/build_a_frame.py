r"""Reproduction script: A-frame (book ch. 23, pp. 56-59; ch. 30 front view).

The green cast A-shaped stand on the base's front-west corner. M6.5 photo
audit: the calibrated ch. 30 front view shows this casting's apex clevis
gripping the SOUTH PIVOT BALL at (-72.9, 253.8) - the A-frame doubles as
the front rocker-shaft support (there is no south frustum; see
build_rocker_arm_support.py). The pivot-ball-mount (channel.SLDASM)
seats on the saddle top at machine y 228.6 between the clevis ears; the
transgear pinion bar starts just east of the clevis (its west end is
carried by the ball-mount housing in the real machine - not modeled,
documented simplification). The casting's lightening cutouts are omitted
(simplification).

Layout: local x = machine x, local y 0 = base top (machine 50.8), local
z 0 = clevis mid-plane (machine z -111). Plate foot x -115..-45 tapering
to the apex x -87..-59 at the ball-mount seat y 177.8 (machine 228.6);
ears rise 20 above the seat, gap 16.2 flanking the mount's Ø16 base.
The Ø6.35 pivot shaft (bottom 250.65) clears the ear tops (248.6) by 2.
Dimensions: cad/DIMENSIONS.md ch. 23 + ch. 14 layout (M6.5, low/med).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_a_frame.py
"""

from __future__ import annotations

import sys

from _common import (
    CASTING_GREEN,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "a-frame"
MATERIAL = "Gray Cast Iron"  # green casting

FOOT_X = (-115.0, -45.0)  # foot span on the base top (med)
APEX_X = (-87.0, -59.0)  # 28-wide top centred near the pivot x -72.9 (med)
SEAT_Y = 177.8  # ball-mount seat: machine 228.6 = pivot 253.8 - ball rise 25.2
PLATE_HALF_T = 4.0  # plate thickness 8 along Z (low)
EAR_HALF_GAP = 8.1  # ears flank the ball mount's Ø16 base + 0.1 clearance
EAR_HALF_Z = 11.1  # ears 3 thick
EAR_HEIGHT = 20.0  # ear tops at 197.8 (machine 248.6): shaft clears by 2
SADDLE_Y0 = 158.0  # saddle block bridges plate (z +-4) to the wider ears


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Tapered plate (Front sketch trapezoid, mid-plane along Z).
    check("create_sketch plate", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    plate = await add_line_chain(
        adapter,
        [
            (FOOT_X[0], 0.0),
            (FOOT_X[1], 0.0),
            (APEX_X[1], SEAT_Y),
            (APEX_X[0], SEAT_Y),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "plate sketch", fix_entities=plate)
    check("exit_sketch plate", await adapter.exit_sketch())
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * PLATE_HALF_T, both_directions=True)
        ),
    )
    foot_w = FOOT_X[1] - FOOT_X[0]
    apex_w = APEX_X[1] - APEX_X[0]
    expected = (foot_w + apex_w) / 2.0 * SEAT_Y * 2.0 * PLATE_HALF_T
    vol = await _volume(adapter)
    print(f"  volume after plate: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"plate volume {vol:.1f} != {expected:.1f}")

    # Saddle block at the apex: full clevis width, bridging the thin
    # plate to the ears above (otherwise the ears would be detached).
    check("create_sketch saddle", await adapter.create_sketch("Top"))
    saddle = await add_line_chain(
        adapter,
        [
            (APEX_X[0], -EAR_HALF_Z),
            (APEX_X[1], -EAR_HALF_Z),
            (APEX_X[1], EAR_HALF_Z),
            (APEX_X[0], EAR_HALF_Z),
        ],
    )
    await ensure_fully_defined(adapter, "saddle sketch", fix_entities=saddle)
    check("exit_sketch saddle", await adapter.exit_sketch())
    extrude_at_offset(adapter, SEAT_Y - SADDLE_Y0, SADDLE_Y0)
    apex_w = APEX_X[1] - APEX_X[0]
    v_saddle = (
        apex_w * 2.0 * EAR_HALF_Z * (SEAT_Y - SADDLE_Y0)
        - apex_w * 2.0 * PLATE_HALF_T * (SEAT_Y - SADDLE_Y0)
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after saddle: {vol:.1f} mm^3 (+{added:.1f}, net {v_saddle:.1f})")
    if abs(added - v_saddle) > 0.02 * v_saddle:
        raise RuntimeError(f"saddle: added {added:.1f}, expected {v_saddle:.1f}")
    expected = vol

    # Clevis ears flanking the ball mount's base (Top sketch, offset extrude).
    check("create_sketch ears", await adapter.create_sketch("Top"))
    ears: list[str] = []
    for side in (1.0, -1.0):
        ears += await add_line_chain(
            adapter,
            [
                (APEX_X[0], side * EAR_HALF_GAP),
                (APEX_X[1], side * EAR_HALF_GAP),
                (APEX_X[1], side * EAR_HALF_Z),
                (APEX_X[0], side * EAR_HALF_Z),
            ],
        )
    await ensure_fully_defined(adapter, "ears sketch", fix_entities=ears)
    check("exit_sketch ears", await adapter.exit_sketch())
    extrude_at_offset(adapter, EAR_HEIGHT, SEAT_Y)
    v_ears = 2.0 * apex_w * (EAR_HALF_Z - EAR_HALF_GAP) * EAR_HEIGHT
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after ears: {vol:.1f} mm^3 (+{added:.1f}, solid {v_ears:.1f})")
    if abs(added - v_ears) > 0.02 * v_ears:
        raise RuntimeError(f"ears: added {added:.1f}, expected {v_ears:.1f}")

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

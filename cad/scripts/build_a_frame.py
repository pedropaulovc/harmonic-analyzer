r"""Reproduction script: A-frame (book ch. 23, pp. 56-59).

The green cast A-shaped stand on the base's front-west corner that holds
the west end of the transgear pinion bar: a tapered plate rising from
the base top to a clevis whose ears grip the 12-square bar. The casting's
lightening cutouts are omitted (simplification).

Layout: origin on the base top at the plate's mid-thickness plane
(machine (0 local = x of the apex? no -- local x matches machine x:
origin at machine (0, 50.8, -111) minus apex offset). Concretely: local
x = machine x, local y 0 = base top (machine 50.8), local z 0 = bar
centre plane (machine z -111). Plate foot x -115..-45, clevis at the
apex grips the bar at y 202.7 (machine 253.5). Dimensions:
cad/DIMENSIONS.md ch. 23 (M6.4, low/med).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_a_frame.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
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
APEX_X = (-89.0, -69.0)  # 20-wide top under the bar (low)
BAR_BOTTOM_Y = 196.7  # bar underside: machine 253.5 - 6 - 50.8 (derived)
PLATE_HALF_T = 4.0  # plate thickness 8 along Z (low)
EAR_HALF_GAP = 6.1  # ears flank the 12-square bar (derived)
EAR_HALF_Z = 9.1  # ears 3 thick
EAR_HEIGHT = 20.0
SADDLE_Y0 = 188.0  # saddle block bridges plate (z +-4) to the wider ears


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
            (APEX_X[1], BAR_BOTTOM_Y),
            (APEX_X[0], BAR_BOTTOM_Y),
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
    expected = (foot_w + apex_w) / 2.0 * BAR_BOTTOM_Y * 2.0 * PLATE_HALF_T
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
    extrude_at_offset(adapter, BAR_BOTTOM_Y - SADDLE_Y0, SADDLE_Y0)
    apex_w = APEX_X[1] - APEX_X[0]
    v_saddle = (
        apex_w * 2.0 * EAR_HALF_Z * (BAR_BOTTOM_Y - SADDLE_Y0)
        - apex_w * 2.0 * PLATE_HALF_T * (BAR_BOTTOM_Y - SADDLE_Y0)
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after saddle: {vol:.1f} mm^3 (+{added:.1f}, net {v_saddle:.1f})")
    if abs(added - v_saddle) > 0.02 * v_saddle:
        raise RuntimeError(f"saddle: added {added:.1f}, expected {v_saddle:.1f}")
    expected = vol

    # Clevis ears flanking the bar (Top sketch, offset extrude).
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
    extrude_at_offset(adapter, EAR_HEIGHT, BAR_BOTTOM_Y)
    v_ears = 2.0 * apex_w * (EAR_HALF_Z - EAR_HALF_GAP) * EAR_HEIGHT
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after ears: {vol:.1f} mm^3 (+{added:.1f}, solid {v_ears:.1f})")
    if abs(added - v_ears) > 0.02 * v_ears:
        raise RuntimeError(f"ears: added {added:.1f}, expected {v_ears:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

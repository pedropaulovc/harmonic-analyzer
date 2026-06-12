r"""Reproduction script: transgear knob shaft (book ch. 23, pp. 56-59).

The shaft riding the latch arm's small hub: it carries the mounted
removable gear (chain-wrapped, ch. 23 -- the chain rides the removable's
teeth directly) at the machine-inboard end, the fine 24T pinion near the
outboard end, and ends in the large brass thumb knob (engineerguy
v4_transgear_008/020). The knob's reeding is omitted (simplification --
the reeding recipe needs an X-axis layout and this part's stack is sized
along its axis).

Layout: axis +Y from the chain-side (machine-inboard) end at the
origin; the assembly rotates +Y to -Z (machine front). The chain plane
sits inboard at machine z -81 (see build_drive_train_assembly.py), so
the shaft is long: removable gear near y 0, latch hub at ~y 45, fine
pinion at ~y 55, knob at the outboard end. Dimensions:
cad/DIMENSIONS.md ch. 23 (M6.4 dims; M6.8 ch23-topology stack).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_transgear_knob_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "transgear-knob-shaft"
MATERIAL = "Brass"

SHAFT_DIA = 0.375 * IN  # 9.525 (low)
SHAFT_LEN = 58.0  # machine z -76.5 (chain end) .. -134.5 (knob face): room for
# the fine 24T pinion at z -134..-128 just behind the knob; the knob then ends
# at -141.0, level with the transgear-stub collar band (to -141.5). Crossing
# the disc band z is safe since M6.8: the latch C2C 66.05 holds the shaft
# 24.6 clear of the disc rim (r 41.49)
KNOB_DIA = 20.0  # large brass thumb knob (low)
KNOB_LEN = 6.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    y_tip = SHAFT_LEN + KNOB_LEN
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, y_tip),
    )
    profile = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (SHAFT_DIA / 2.0, 0.0),
            (SHAFT_DIA / 2.0, SHAFT_LEN),
            (KNOB_DIA / 2.0, SHAFT_LEN),
            (KNOB_DIA / 2.0, y_tip),
            (0.0, y_tip),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "shaft profile", fix_entities=[centerline, *profile]
    )
    check("exit_sketch profile", await adapter.exit_sketch())
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))

    expected = math.pi * (
        (SHAFT_DIA / 2.0) ** 2 * SHAFT_LEN + (KNOB_DIA / 2.0) ** 2 * KNOB_LEN
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

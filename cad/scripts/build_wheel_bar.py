r"""Reproduction script: magnifying-wheel bar (book ch. 21, pp. 50-51).

The short square bar carrying the magnifying-wheel axle and the
pen-hanger strap. M6.8 ch30 8-view pass (user-confirmed): unlike the two
full-width platen rails, this bar spans only ~HALF the frame width --
every plate shows it clamped at ONE column (post-mirror the right/+X
one) with a free end just past the pen hanger; there is no second clamp
on the far column at this height.

Square 10 section like the support-bar, 200 long. Placed in
build_output_assembly at centre x -92 (pre-mirror): clamped end -192
(in the west clamp's front channel, off the column cylinder -- same
clearance logic as build_support_bar.py), free end +8, covering the
wheel axle (-53) and the pen-hanger strap top (-19..-3) with margin.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_wheel_bar.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "wheel-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 10.0  # square section, same stock as support-bar (low)
BAR_LENGTH = 200.0  # half-width span: one clamp + free end (photo, med)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    half = BAR_SIDE / 2.0
    check("create_sketch bar", await adapter.create_sketch("Front"))
    outline = await add_line_chain(
        adapter,
        [
            (-BAR_LENGTH / 2.0, -half),
            (BAR_LENGTH / 2.0, -half),
            (BAR_LENGTH / 2.0, half),
            (-BAR_LENGTH / 2.0, half),
        ],
    )
    await ensure_fully_defined(adapter, "bar sketch", fix_entities=outline)
    check("exit_sketch bar", await adapter.exit_sketch())
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_SIDE, both_directions=True)
        ),
    )

    res = await adapter.get_mass_properties()
    vol = res.data.volume
    expected = BAR_LENGTH * BAR_SIDE * BAR_SIDE
    print(f"  volume: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"bar volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

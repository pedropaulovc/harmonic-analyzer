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

M6.10 fasteners pass: an O3.8 through-hole along Z at local (-97.5, 0)
(machine (-5.5, 565) -- the realized ("x", 0) mirror is machine =
local + 92) takes the pen-hanger screw from behind the bar. The hole
sits in the 5-wide strap/bar overlap at the free end (0.6 edge wall to
the end face -- thin but photo-consistent: the bar end runs "just past"
the hanger).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_wheel_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_isometric_view,
    set_sketch_direct_db,
)

PART_NAME = "wheel-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 10.0  # square section, same stock as support-bar (low)
BAR_LENGTH = 200.0  # half-width span: one clamp + free end (photo, med)
SCREW_HOLE_DIA = 3.8  # M6.10: pen-hanger screw hole (see docstring)
SCREW_HOLE_X = -97.5


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    half = BAR_SIDE / 2.0
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (-BAR_LENGTH / 2.0, -half),
        (BAR_LENGTH / 2.0, -half),
        (BAR_LENGTH / 2.0, half),
        (-BAR_LENGTH / 2.0, half),
    ]
    outline = await add_line_chain(adapter, bar_rect)
    await define_rectilinear_chain(adapter, outline, bar_rect, label="bar")
    await ensure_fully_defined(adapter, "bar sketch")
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

    # Pen-hanger screw hole (mid-plane cut along Z, bar is z-symmetric).
    check("create_sketch screw hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(adapter, SCREW_HOLE_X, 0.0, SCREW_HOLE_DIA / 2.0, "screw hole")
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw hole", await adapter.exit_sketch())
    check(
        "cut screw hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * BAR_SIDE, both_directions=True)
        ),
    )
    expected -= math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * BAR_SIDE
    res = await adapter.get_mass_properties()
    vol = res.data.volume
    print(f"  volume after screw hole: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 1.0:
        raise RuntimeError(f"screw hole volume {vol:.1f} != {expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: magnifying-wheel bar (book ch. 21, pp. 50-51).

The short square bar carrying the magnifying-wheel axle and the
pen-hanger strap. M6.8 ch30 8-view pass (user-confirmed): unlike the two
full-width platen rails, this bar spans only ~HALF the frame width --
every plate shows it clamped at ONE column (post-mirror the right/+X
one) with a free end just past the pen hanger; there is no second clamp
on the far column at this height.

Square 10 section like the support-bar, 200 long. Placed in
build_magnifier_assembly at centre x -92 (pre-mirror): clamped end -192
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

    uv run python cad\scripts\build_wheel_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
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

    # Editable knobs (Tools > Equations): the square section, the bar length, and
    # the pen-hanger screw hole (diameter + its X station). The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads BARE
    # numbers in document units (an unsuffixed 200 = 200 in). BAR_SIDE doubles as
    # the extrude DEPTH (a feature parameter, not a sketch dim), so it drives the
    # profile's depth dim only; the depth itself is static, matching the exemplars.
    await set_global(adapter, "BarSide", f"{BAR_SIDE}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")
    await set_global(adapter, "ScrewHoleDia", f"{SCREW_HOLE_DIA}mm")
    await set_global(adapter, "ScrewHoleX", f"{SCREW_HOLE_X}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Square bar profile: width along X = length, depth along Z = section,
    # origin-centred. The old add_line_chain + define_rectilinear_chain pair is
    # an origin-centred rectangle, so switch it to define_centered_rectangle
    # (cleaner; emits exactly width, depth, cornerX, cornerZ).
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_SIDE / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Side", drive_depth='"BarSide"',
        name_corner=("CornerX", "CornerZ"),
        drive_corner=('"BarLength" / 2', '"BarSide" / 2'),
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_SIDE, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")

    expected = BAR_LENGTH * BAR_SIDE * BAR_SIDE
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Pen-hanger screw hole (mid-plane cut along Z, bar is z-symmetric). On-axis
    # in Z (y 0): only X + diameter are dims, so define_circle records just those
    # two -- the "Z" slot is ignored.
    hole = SketchDims()
    check("create_sketch screw hole", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, SCREW_HOLE_X, 0.0, SCREW_HOLE_DIA / 2.0, "screw hole",
        dims=hole,
        names=("ScrewHoleCx", "ScrewHoleCz", "ScrewHoleDiaDim"),
        # The centre-X dim is an unsigned distance from the origin, so drive it
        # by the ABS value of the (negative) X station: -ScrewHoleX = +97.5.
        drives=('-"ScrewHoleX"', None, '"ScrewHoleDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "screw hole sketch")
    check("exit_sketch screw hole", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewHoleProfile")
    drive_jobs += hole.apply(adapter, "ScrewHoleProfile")
    check(
        "cut screw hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=3.0 * BAR_SIDE, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHole")
    expected -= math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * BAR_SIDE
    await volume_check(adapter, "bar with screw hole", expected, 1.0)

    # Deferred drive equations after the model + a rebuild exists, then re-check:
    # each equation evaluates to the as-built value, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven wheel bar (equations neutral)", expected, 1.0)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: output support bar (book ch. 21/22, pp. 50-55).

The square steel bar used three times on the output (front, -Z) side of
the machine, clamped between the front columns by column clamps
(build_column_clamp.py): the magnifying-wheel axle bar (y 565), the
platen top rail (y 460) and the platen bottom rail (y ~318). Square 10
section, 384 long: the ends stop at x +-192, seated in the clamps' front
channels. With the Ø25.4 columns (OD rederived from the 8-views, M6.11)
the column cylinders (z -99.3..-124.7) no longer reach the bar's z band
(-138.9..-128.9) - a 4.2 gap - so the ends clear with margin; 384 is held
by the clamp-channel seating, not the old column-corner trim (M6.5).

Layout: bar axis along X, origin at the bar centre. Dimensions:
cad/DIMENSIONS.md ch. 21/22 (M6.4, low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_support_bar.py
"""

from __future__ import annotations

import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_centered_rectangle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "support-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 10.0  # square section (low)
BAR_LENGTH = 384.0  # ends at x +-192: seated in the clamp channels (Ø25.4 columns clear)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the square section and the length. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 384 = 384 in).
    await set_global(adapter, "BarSide", f"{BAR_SIDE}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Square bar profile: width along X = length, depth along Z = section.
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

    expected = BAR_SIDE * BAR_SIDE * BAR_LENGTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

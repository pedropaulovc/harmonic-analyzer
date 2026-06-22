r"""Reproduction script: transgear pinion bar (book ch. 23, pp. 56-59).

The square steel bar that carries the translational-gearing stud: it
runs from just east of the A-frame clevis (machine x -58: the clevis ears
end at -59 and grip the south pivot ball mount, M6.5) to just short of
the east column (x +178: the Ø25.4 column's near tangent is 184.3, M6.11) at y 253.5
on the output side, with a O9.6 hole along Z at the rack-pinion stud
position (machine x 0). The stud (build_transgear_stub.py) plugs into
this hole; the rack pinion, fixed pinion and latch ride it. In the real
machine the west end is carried by the ball-mount housing (ch. 30 front
view) - both ends float in the model (fix-all assembly), documented
simplification.

Layout: bar axis along X, origin ON the stud hole axis at the bar's
section centre. Dimensions: cad/DIMENSIONS.md ch. 23 (M6.4, low/med).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_bar.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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

PART_NAME = "pinion-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 12.0  # square section (low)
BAR_X = (-58.0, 178.0)  # east of the clevis -> short of the east column (med)
HOLE_DIA = 9.6  # 3/8" stud bore: 9.525 stud + slip clearance (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the square section, the two end
    # stations, and the stud-bore diameter. The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 178 = 178 in). The bar is NOT origin-centred along X
    # (it spans BarXWest..BarXEast), so its length is a derived global of the two
    # station knobs and the rectilinear chain is kept (not switched to a centred
    # rectangle).
    await set_global(adapter, "BarSide", f"{BAR_SIDE}mm")
    await set_global(adapter, "BarXWest", f"{BAR_X[0]}mm")
    await set_global(adapter, "BarXEast", f"{BAR_X[1]}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")
    await set_global(adapter, "BarLength", '"BarXEast" - "BarXWest"')

    drive_jobs: list[tuple[str, str]] = []

    half = BAR_SIDE / 2.0
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (BAR_X[0], -half),
        (BAR_X[1], -half),
        (BAR_X[1], half),
        (BAR_X[0], half),
    ]
    outline = await add_line_chain(adapter, bar_rect)
    # Emission order (anchor vertex 0 at (BarXWest, -half)): the per-segment
    # distance dims skipping the last of each direction -- L0 length (X span),
    # L1 side (Z span) -- THEN the anchor dims (x then z, both non-zero). Anchor
    # dims are absolute distances to the origin, so AnchorX = -BarXWest (west is
    # negative) and AnchorZ = BarSide / 2.
    await define_rectilinear_chain(
        adapter, outline, bar_rect, label="bar", dims=bar,
        names=["Length", "Side", "AnchorX", "AnchorZ"],
        drives=['"BarLength"', '"BarSide"', '-"BarXWest"', '"BarSide" / 2'],
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

    # Stud hole on the bar axis (origin): an on-axis/origin circle records only
    # its diameter (the centre is a coincident relation, not a dim), so the
    # centre name slots are ignored.
    hole = SketchDims()
    check("create_sketch stud hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HOLE_DIA / 2.0, "stud hole", dims=hole,
        names=("HoleCx", "HoleCz", "HoleDia"),
        drives=(None, None, '"HoleDia"'),
    )
    await ensure_fully_defined(adapter, "stud hole sketch")
    check("exit_sketch stud hole", await adapter.exit_sketch())
    name_last_feature(adapter, "StudHoleProfile")
    drive_jobs += hole.apply(adapter, "StudHoleProfile")
    check(
        "cut stud hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_SIDE, both_directions=True)
        ),
    )
    name_last_feature(adapter, "StudHole")

    expected = (
        BAR_SIDE * BAR_SIDE * (BAR_X[1] - BAR_X[0])
        - math.pi * (HOLE_DIA / 2.0) ** 2 * BAR_SIDE
    )
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

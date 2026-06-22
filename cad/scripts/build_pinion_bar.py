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
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "pinion-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 12.0  # square section (low)
BAR_X = (-58.0, 178.0)  # east of the clevis -> short of the east column (med)
HOLE_DIA = 9.6  # 3/8" stud bore: 9.525 stud + slip clearance (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    half = BAR_SIDE / 2.0
    check("create_sketch bar", await adapter.create_sketch("Front"))
    bar_rect = [
        (BAR_X[0], -half),
        (BAR_X[1], -half),
        (BAR_X[1], half),
        (BAR_X[0], half),
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

    check("create_sketch stud hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, HOLE_DIA / 2.0, "stud hole")
    await ensure_fully_defined(adapter, "stud hole sketch")
    check("exit_sketch stud hole", await adapter.exit_sketch())
    check(
        "cut stud hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * BAR_SIDE, both_directions=True)
        ),
    )

    expected = (
        BAR_SIDE * BAR_SIDE * (BAR_X[1] - BAR_X[0])
        - math.pi * (HOLE_DIA / 2.0) ** 2 * BAR_SIDE
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

r"""Reproduction script: output support bar (book ch. 21/22, pp. 50-55).

The square steel bar used three times on the output (front, -Z) side of
the machine, clamped between the front columns by column clamps
(build_column_clamp.py): the magnifying-wheel axle bar (y 565), the
platen top rail (y 460) and the platen bottom rail (y ~318). Square 10
section, 400 long (column lines at x +-197 plus the clamp lugs).

Layout: bar axis along X, origin at the bar centre. Dimensions:
cad/DIMENSIONS.md ch. 21/22 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_support_bar.py
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

PART_NAME = "support-bar"
MATERIAL = "Plain Carbon Steel"

BAR_SIDE = 10.0  # square section (low)
BAR_LENGTH = 400.0  # spans the column lines at x +-197 (derived)


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

    expected = BAR_SIDE * BAR_SIDE * BAR_LENGTH
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

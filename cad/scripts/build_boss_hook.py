r"""Reproduction script: summing-lever boss hook (book ch. 18/19, pp. 43-45).

The black J-hook that hangs the counter spring from the summing-lever
boss: an O3 rod planted in the boss top, rising clear of the boss, then
bent 90 degrees into a horizontal arm pointing +X (toward the channels'
mid-line) that the counter spring's bottom ring encircles nail-through-
ring style. The p.43/p.45 photos show a hook + separate chrome link ring;
the chain is collapsed to this single hook with the spring's own loop as
the ring (simplification, see build_counter_spring.py).

Dimensions: cad/DIMENSIONS.md ch. 18/19 (M6.4, low). Geometry constraints
that size it (see build_output_assembly.py): shank at machine x 90.5
(boss hole), rod centreline at machine y 1015 so the spring ring (mean
r 5.35, wire 1.8) hanging at centre y 1012 touches the rod top; rod tip
at machine x 97 so the ring's wire band (x 94.1..95.9) sits mid-rod.

Layout: shank axis +Y from the origin (machine (90.5, 1000, 0)); path =
vertical line, 90-degree elbow (R 3), horizontal line +X. Single sweep
along equation-driven curves (the fixed-curve fully-defined recipe).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_boss_hook.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "boss-hook"
MATERIAL = "Plain Carbon Steel"  # black hardware

ROD_DIA = 3.0  # DIMENSIONS.md ch18: hook rod (low)
SHANK_RISE = 12.0  # straight rise before the elbow (derived)
ELBOW_R = 3.0  # centreline bend radius (low)
ARM_RUN = 3.5  # straight run after the elbow; tip at x 6.5 (derived)
# Rod centreline tops out at y = SHANK_RISE + ELBOW_R = 15 (machine 1015);
# tip at x = ELBOW_R + ARM_RUN = 6.5 (machine 97).


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreateEquationCurveParameters,
        SweepParameters,
    )

    def fmt(value_mm: float) -> str:
        return f"{value_mm / IN:.12g}"  # document units are inches

    async def _curve(label: str, x_expr: str, y_expr: str) -> str:
        res = await adapter.create_equation_driven_curve(
            CreateEquationCurveParameters(
                x_expression=x_expr,
                y_expression=y_expr,
                range_start="0",
                range_end="1",
            )
        )
        return check(f"curve {label}", res)

    check("create_part", await adapter.create_part())

    # Path in the Front plane: rise, quarter-arc elbow, horizontal arm.
    path_name = check("create_sketch hook path", await adapter.create_sketch("Front"))
    rise = await _curve("shank rise", "0 * t", f"{fmt(SHANK_RISE)} * t")
    elbow = await _curve(
        "elbow",
        f"{fmt(ELBOW_R)} - {fmt(ELBOW_R)} * cos({math.pi / 2.0:.12g} * t)",
        f"{fmt(SHANK_RISE)} + {fmt(ELBOW_R)} * sin({math.pi / 2.0:.12g} * t)",
    )
    arm = await _curve(
        "arm",
        f"{fmt(ELBOW_R)} + {fmt(ARM_RUN)} * t",
        f"{fmt(SHANK_RISE + ELBOW_R)} + 0 * t",
    )
    await ensure_fully_defined(adapter, "hook path", fix_entities=[rise, elbow, arm])
    check("exit_sketch hook path", await adapter.exit_sketch())

    # Wire profile at the path start (origin, Top plane).
    check("create_sketch wire profile", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, ROD_DIA / 2.0, "wire profile")
    await ensure_fully_defined(adapter, "wire profile sketch")
    check("exit_sketch wire profile", await adapter.exit_sketch())

    check(
        "sweep hook",
        await adapter.create_sweep(SweepParameters(path=path_name)),
    )

    # Pappus: planar path, volume = path length x wire area.
    path_len = SHANK_RISE + math.pi / 2.0 * ELBOW_R + ARM_RUN
    v_expected = path_len * math.pi * (ROD_DIA / 2.0) ** 2
    res = await adapter.get_mass_properties()
    vol = float(res.data.volume) if res.is_success else float("nan")
    print(f"  volume: {vol:.1f} mm^3 (Pappus {v_expected:.1f})")
    if abs(vol - v_expected) > 0.02 * v_expected:
        raise RuntimeError(f"hook volume {vol:.1f} != Pappus {v_expected:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

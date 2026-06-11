r"""Reproduction script: column clamp (book ch. 21/22, pp. 50-55).

The green cast collar that clamps each output support bar to a front
column: a ring sliding on the O35 column with a lug whose upward-open
square notch cradles the 10-square bar (six used: two per bar). The
book's pinch screws are omitted (simplification).

Layout: collar axis +Y (column vertical) through the origin at the bar's
centre height; the lug points +X (rotated per side in the assembly).
The notch floor sits at y -5.1 so the bar centres on y 0. Dimensions:
cad/DIMENSIONS.md ch. 21/22 (M6.4, low).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_column_clamp.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
)

PART_NAME = "column-clamp"
MATERIAL = "Gray Cast Iron"  # green casting

COLLAR_OD = 48.0  # DIMENSIONS.md ch21 (low)
COLLAR_BORE = 35.2  # slides on the O35 column (derived)
COLLAR_HALF_H = 8.0  # 16 tall
LUG_X = (20.0, 44.0)  # overlaps the collar wall, reaches past the bar
LUG_HALF_Z = 8.0
NOTCH_HALF = 5.1  # 10.2 square notch for the 10-square bar
LUG_FLOOR_Y = -COLLAR_HALF_H  # lug bottom flush with the collar


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Collar ring.
    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, COLLAR_OD / 2.0, "collar OD")
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    check(
        "extrude collar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * COLLAR_HALF_H, both_directions=True)
        ),
    )
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, COLLAR_BORE / 2.0, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=4.0 * COLLAR_HALF_H, both_directions=True)
        ),
    )
    expected = (
        math.pi
        * ((COLLAR_OD / 2.0) ** 2 - (COLLAR_BORE / 2.0) ** 2)
        * 2.0
        * COLLAR_HALF_H
    )
    vol = await _volume(adapter)
    print(f"  volume after collar: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"collar volume {vol:.1f} != {expected:.1f}")

    # Lug floor plate (below the notch).
    check("create_sketch lug floor", await adapter.create_sketch("Front"))
    floor = await add_line_chain(
        adapter,
        [
            (LUG_X[0], LUG_FLOOR_Y),
            (LUG_X[1], LUG_FLOOR_Y),
            (LUG_X[1], -NOTCH_HALF),
            (LUG_X[0], -NOTCH_HALF),
        ],
    )
    await ensure_fully_defined(adapter, "lug floor sketch", fix_entities=floor)
    check("exit_sketch lug floor", await adapter.exit_sketch())
    check(
        "extrude lug floor",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=2.0 * LUG_HALF_Z, both_directions=True)
        ),
    )
    v_floor = (
        (LUG_X[1] - LUG_X[0])
        * (COLLAR_HALF_H - NOTCH_HALF)
        * 2.0
        * LUG_HALF_Z
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after lug floor: {vol:.1f} mm^3 (+{added:.1f}, solid {v_floor:.1f})")
    if not (0.7 * v_floor <= added <= 1.01 * v_floor):
        raise RuntimeError(f"lug floor: added {added:.1f}, expected ~{v_floor:.1f}")
    expected = vol

    # Lug cheeks flanking the notch (Top sketch, offset extrude up from
    # the notch floor to the collar top).
    check("create_sketch lug cheeks", await adapter.create_sketch("Top"))
    cheeks: list[str] = []
    for side in (1.0, -1.0):
        cheeks += await add_line_chain(
            adapter,
            [
                (LUG_X[0], side * NOTCH_HALF),
                (LUG_X[1], side * NOTCH_HALF),
                (LUG_X[1], side * LUG_HALF_Z),
                (LUG_X[0], side * LUG_HALF_Z),
            ],
        )
    await ensure_fully_defined(adapter, "lug cheeks sketch", fix_entities=cheeks)
    check("exit_sketch lug cheeks", await adapter.exit_sketch())
    extrude_at_offset(adapter, COLLAR_HALF_H + NOTCH_HALF, -NOTCH_HALF)
    v_cheeks = (
        2.0
        * (LUG_X[1] - LUG_X[0])
        * (LUG_HALF_Z - NOTCH_HALF)
        * (COLLAR_HALF_H + NOTCH_HALF)
    )
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    print(f"  volume after cheeks: {vol:.1f} mm^3 (+{added:.1f}, solid {v_cheeks:.1f})")
    if not (0.7 * v_cheeks <= added <= 1.01 * v_cheeks):
        raise RuntimeError(f"cheeks: added {added:.1f}, expected ~{v_cheeks:.1f}")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

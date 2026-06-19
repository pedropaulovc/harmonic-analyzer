r"""Reproduction script: top frame ring (ch. 30 eight-views; NEW part, 1 used).

Green cast rectangular ring clamping the four brass columns just below
their tops: rails 22 wide x 41 tall, corner bosses Ø48 bored Ø25.5 around
the Ø25.4 columns (OD rederived from the ch30 8-views, M6.11) at (x, z) =
(+/-197, +/-112). In the machine it sits
at y 999.7..1040.7; its west rail carries the two ball mounts of the
top-lever fulcrum shaft (seat 1040.7 + ball rise 25.2 = axis 1065.9) and
the summing lever hangs below it (M6.4). Identified in M6.3 from the
eight views (green ring at y ~ 1010-1055 in every view, columns
continuing above to their caps); no book chapter covers it directly.

Dimensions: cad/DIMENSIONS.md "Channel & top-frame layout" (med; boss OD
scaled, low).

Layout: plan profile in XZ centred on the origin, ring mid-plane extruded
both ways in Y (y -20.5..+20.5) - the assembly lifts it to 1020.2. Build
order: outer slab, window cut, THEN corner bosses, then column bores -
bosses after the window so the full Ø48 cylinder survives at the window
corners (the window rectangle passes within 15.6 of the boss centres,
well inside the Ø48 boss). All Top-plane sketches are symmetric in both
axes, so the (x, y) -> (X, -Z) handedness never matters. Boss volume
contribution is verified against a grid-integrated plan area (the
boss/band/window overlaps have no tidy closed form).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_top_frame.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    add_line_chain,
    apply_color,
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
    volume_check,
)

PART_NAME = "top-frame"
MATERIAL = "Gray Cast Iron"  # green-painted casting like the base

COLUMN_X = 197.0  # column stations (frame.SLDASM, M6.1)
COLUMN_Z = 112.0
RAIL_WIDTH = 22.0  # DIMENSIONS.md top-frame row (photo, med)
RING_HEIGHT = 41.0  # DIMENSIONS.md top-frame row (photo, med)
BOSS_DIA = 48.0  # corner boss around the column (scaled, low)
BORE_DIA = 25.5  # clamps the Ø25.4 column (0.1 slip; OD rederived from 8-views)

OUTER_X = COLUMN_X + RAIL_WIDTH / 2.0  # 208
OUTER_Z = COLUMN_Z + RAIL_WIDTH / 2.0  # 123
INNER_X = COLUMN_X - RAIL_WIDTH / 2.0  # 186
INNER_Z = COLUMN_Z - RAIL_WIDTH / 2.0  # 101
THROUGH_CUT_DEPTH = 60.0  # mid-plane total; > ring height


def _boss_extra_area() -> float:
    """Plan area one boss adds beyond the rail band, grid-integrated.

    Inside the Ø48 circle but outside the band (outer rect minus window):
    the boss bulges past the outer corner AND into the window corner.
    """
    r = BOSS_DIA / 2.0
    step = 0.05
    n = int(2.0 * r / step)
    extra = 0.0
    for i in range(n):
        x = COLUMN_X - r + (i + 0.5) * step
        half_chord = r * r - (x - COLUMN_X) ** 2
        if half_chord <= 0.0:
            continue
        dz = math.sqrt(half_chord)
        z0, z1 = COLUMN_Z - dz, COLUMN_Z + dz
        for j in range(int((z1 - z0) / step) + 1):
            z = z0 + (j + 0.5) * step
            if z >= z1:
                break
            in_band = (abs(x) <= OUTER_X and abs(z) <= OUTER_Z) and not (
                abs(x) < INNER_X and abs(z) < INNER_Z
            )
            if not in_band:
                extra += step * step
    return extra


async def _rectangle(adapter, label: str, half_x: float, half_z: float) -> None:
    set_sketch_direct_db(adapter, True)
    rect = [
        (-half_x, -half_z),
        (half_x, -half_z),
        (half_x, half_z),
        (-half_x, half_z),
    ]
    lines = await add_line_chain(adapter, rect)
    set_sketch_direct_db(adapter, False)
    await define_rectilinear_chain(adapter, lines, rect, label=label)
    await ensure_fully_defined(adapter, label)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    set_isometric_view(adapter)

    # Outer slab.
    check("create_sketch outer", await adapter.create_sketch("Top"))
    await _rectangle(adapter, "outer rectangle", OUTER_X, OUTER_Z)
    check("exit_sketch outer", await adapter.exit_sketch())
    check(
        "extrude slab",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    v_slab = 4.0 * OUTER_X * OUTER_Z * RING_HEIGHT
    await volume_check(adapter, "slab", v_slab, 0.001 * v_slab)

    # Window, leaving the 22-wide rail band.
    check("create_sketch window", await adapter.create_sketch("Top"))
    await _rectangle(adapter, "window rectangle", INNER_X, INNER_Z)
    check("exit_sketch window", await adapter.exit_sketch())
    check(
        "cut window",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    v_ring = v_slab - 4.0 * INNER_X * INNER_Z * RING_HEIGHT
    await volume_check(adapter, "rail band", v_ring, 0.001 * v_ring)

    # Corner bosses (full Ø48 cylinders; restore the window corners).
    check("create_sketch bosses", await adapter.create_sketch("Top"))
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter,
                sx * COLUMN_X,
                sz * COLUMN_Z,
                BOSS_DIA / 2.0,
                f"boss ({sx:+.0f}, {sz:+.0f})",
            )
    await ensure_fully_defined(adapter, "bosses sketch")
    check("exit_sketch bosses", await adapter.exit_sketch())
    check(
        "extrude bosses",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=RING_HEIGHT, both_directions=True)
        ),
    )
    v_boss_extra = 4.0 * _boss_extra_area() * RING_HEIGHT
    v_bossed = v_ring + v_boss_extra
    await volume_check(adapter, "bosses", v_bossed, 0.005 * v_boss_extra + 50.0)

    # Column bores (entirely inside the bosses).
    check("create_sketch bores", await adapter.create_sketch("Top"))
    for sx in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            await define_circle(
                adapter,
                sx * COLUMN_X,
                sz * COLUMN_Z,
                BORE_DIA / 2.0,
                f"bore ({sx:+.0f}, {sz:+.0f})",
            )
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    v_bores = 4.0 * math.pi * (BORE_DIA / 2.0) ** 2 * RING_HEIGHT
    await volume_check(adapter, "bored ring", v_bossed - v_bores, 0.005 * v_boss_extra + 50.0)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

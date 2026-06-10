r"""Reproduction script: drive-chain sprocket (book ch. 23; 2 used).

The two roller-chain sprockets of the translational gearing (one at the
platen front, one on the crankshaft) -- modeled identical: 17 teeth
(counted on `v4_transgear_012` crops), ~3/8" chain pitch (scaled from the
sprocket OD), 4.5 mm tooth width, plain 3/8" bore.

The tooth form is SIMPLIFIED: a flaring trapezoid notch per roller (seat
width = roller diameter at the seat radius, opening to a pointed-ish tooth
at the OD) instead of the standard seat-arc + topping-curve profile. Good
enough for the visual/BOM purposes of this model; the chain itself is not
modeled (flexible element, out of scope).

Sprocket math (3/8" pitch, roller 0.200"): PD = p / sin(pi/N) = 51.84 mm,
OD = p (0.6 + cot(pi/N)) = 56.67 mm, seat radius = PD/2 - roller/2.

Layout: axis = Z through the origin, body z = 0..4.5 mm, seed gap on +X.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_chain_sprocket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)
from _gear import volume_check

PART_NAME = "chain-sprocket"
MATERIAL = "Plain Carbon Steel"  # ch. 23 photos: steel sprockets

TEETH = 17  # DIMENSIONS.md ch23: counted on v4_transgear_012 (low)
CHAIN_PITCH = 0.375 * IN  # 9.525 -- scaled from sprocket OD (low)
ROLLER_DIAMETER = 0.200 * IN  # 5.08 -- standard 3/8" roller chain (low)
FACE_WIDTH = 4.5  # mm -- 3/8" chain inner width budget (low)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- crankshaft stock (low)

PITCH_RADIUS = CHAIN_PITCH / (2.0 * math.sin(math.pi / TEETH))  # 25.92
OUTER_RADIUS = CHAIN_PITCH * (0.6 + 1.0 / math.tan(math.pi / TEETH)) / 2.0  # 28.34
SEAT_RADIUS = PITCH_RADIUS - ROLLER_DIAMETER / 2.0  # 23.38, notch floor
NOTCH_OUTER = OUTER_RADIUS + 1.2  # opens past the OD
SEAT_HALF_WIDTH = ROLLER_DIAMETER / 2.0  # 2.54 at the floor
TIP_HALF_WIDTH = 4.0  # flare at NOTCH_OUTER -> ~2.4 mm pointed tooth tip


def notch_area_in_disc(step: float = 0.004) -> float:
    """Area (mm^2) of the trapezoid notch inside the blank disc."""
    nx = max(2, round((NOTCH_OUTER - SEAT_RADIUS) / step))
    ny = max(2, round(2.0 * TIP_HALF_WIDTH / step))
    dx = (NOTCH_OUTER - SEAT_RADIUS) / nx
    dy = 2.0 * TIP_HALF_WIDTH / ny
    hits = 0
    for i in range(nx):
        x = SEAT_RADIUS + (i + 0.5) * dx
        half = SEAT_HALF_WIDTH + (TIP_HALF_WIDTH - SEAT_HALF_WIDTH) * (
            (x - SEAT_RADIUS) / (NOTCH_OUTER - SEAT_RADIUS)
        )
        for j in range(ny):
            y = -TIP_HALF_WIDTH + (j + 0.5) * dy
            if abs(y) <= half and math.hypot(x, y) <= OUTER_RADIUS:
                hits += 1
    return hits * dx * dy


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Blank disc at the OD.
    check("create_sketch blank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, OUTER_RADIUS, "sprocket blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=FACE_WIDTH)),
    )
    v_blank = math.pi * OUTER_RADIUS**2 * FACE_WIDTH
    volume = await volume_check(adapter, "blank", v_blank, 0.005 * v_blank)

    # One roller notch on +X (fix-only recipe, inference off near the OD).
    check("create_sketch notch", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    notch = await add_line_chain(
        adapter,
        [
            (SEAT_RADIUS, -SEAT_HALF_WIDTH),
            (NOTCH_OUTER, -TIP_HALF_WIDTH),
            (NOTCH_OUTER, TIP_HALF_WIDTH),
            (SEAT_RADIUS, SEAT_HALF_WIDTH),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "notch sketch", fix_entities=notch)
    check("exit_sketch notch", await adapter.exit_sketch())
    notch_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=FACE_WIDTH + 1.0)
    )
    check("cut roller notch", notch_cut)

    from _gear import pattern_about_z

    await pattern_about_z(
        adapter, notch_cut.data.name, TEETH, OUTER_RADIUS, FACE_WIDTH / 2.0
    )
    v_teeth = v_blank - TEETH * notch_area_in_disc() * FACE_WIDTH
    volume = await volume_check(adapter, "toothed sprocket", v_teeth, 0.01 * v_teeth)

    # Bore.
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore")
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
    await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

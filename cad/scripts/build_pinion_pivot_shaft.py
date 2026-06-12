r"""Reproduction script: pinion torque shaft with end ball + T-handle (book ch. 25).

The long Ø6.35 shaft the two pinion swing brackets pivot on, running
parallel under the alignment-pinion drum through both pivot blocks. Its
front end carries a Ø16 ball with a Ø6 vertical T-handle rod through it
(p. 67/68: the bright ball-and-rod tee standing at the front-side end).
Modeled as ONE part: shaft extrusion plus a single ball+handle solid of
revolution about the handle axis.

Layout: shaft axis Z, shaft z 0..173, ball centred at the ORIGIN (the
front half protrudes as the end knob), handle along Y from -9 to +61
(asymmetric: the short side stops above the machine base).

Volume gate (exact union, mm^3): shaft 5478.78 + ball 2144.66 + handle
1979.20 - ball/shaft half-pass 243.10 - ball/handle full-pass 436.10
(the handle/shaft Steinmetz region lies entirely inside the ball, so
its -V and +V inclusion-exclusion terms cancel) = 8923.44.

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_pivot_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-pivot-shaft"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)

SHAFT_DIA = 6.35  # rides the strap and block bores (derived)
SHAFT_LEN = 173.0  # front strap z -80 to 4 proud of the back strap (derived)
BALL_DIA = 16.0  # end ball, photo-scaled vs the 6 mm rod (low)
HANDLE_DIA = 6.0  # T-handle rod, p.68 "6 mm" annotation (high)
HANDLE_DOWN = 9.0  # below the ball centre -- stops 1.3 above the base (derived)
HANDLE_UP = 61.0  # above the ball centre (photo-scaled, low)

SHAFT_R = SHAFT_DIA / 2.0
BALL_R = BALL_DIA / 2.0
HANDLE_R = HANDLE_DIA / 2.0
# Handle rod meets the sphere at the chord of its piercing cylinder.
JUNCTION = math.sqrt(BALL_R**2 - HANDLE_R**2)  # 7.4162


def _cyl_sphere_full_pass(a: float, r: float) -> float:
    """Volume of an infinite cylinder (radius a) through a sphere (radius r)."""
    return (4.0 * math.pi / 3.0) * (r**3 - (r**2 - a**2) ** 1.5)


V_SHAFT = math.pi * SHAFT_R**2 * SHAFT_LEN
V_BALL = (4.0 * math.pi / 3.0) * BALL_R**3
V_HANDLE = math.pi * HANDLE_R**2 * (HANDLE_DOWN + HANDLE_UP)
V_BALL_SHAFT = _cyl_sphere_full_pass(SHAFT_R, BALL_R) / 2.0  # shaft only on z >= 0
V_BALL_HANDLE = _cyl_sphere_full_pass(HANDLE_R, BALL_R)
V_TOTAL = V_SHAFT + V_BALL + V_HANDLE - V_BALL_SHAFT - V_BALL_HANDLE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Shaft along +Z from the ball centre.
    check("create_sketch shaft", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, SHAFT_R, "shaft")
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    check(
        "extrude shaft",
        await adapter.create_extrusion(ExtrusionParameters(depth=SHAFT_LEN)),
    )
    await volume_check(adapter, "shaft", V_SHAFT, 0.005 * V_SHAFT)

    # Ball + handle as one revolved profile about +Y (revolve LAST: an
    # on-axis revolve breaks later booleans, see solidworks pitfalls).
    check("create_sketch ball+handle", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline handle axis",
        await adapter.add_centerline(0.0, -HANDLE_DOWN, 0.0, HANDLE_UP),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, -HANDLE_DOWN),
            (HANDLE_R, -HANDLE_DOWN),
            (HANDLE_R, -JUNCTION),
        ],
        close=False,
    )
    arc = check(
        "add_arc ball",
        await adapter.add_arc(
            0.0, 0.0, HANDLE_R, -JUNCTION, HANDLE_R, JUNCTION
        ),
    )
    tail = await add_line_chain(
        adapter,
        [
            (HANDLE_R, JUNCTION),
            (HANDLE_R, HANDLE_UP),
            (0.0, HANDLE_UP),
            (0.0, -HANDLE_DOWN),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "ball+handle profile", fix_entities=[centerline, *lines, arc, *tail]
    )
    check("exit_sketch ball+handle", await adapter.exit_sketch())
    check(
        "revolve ball+handle",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    await volume_check(adapter, "ball+handle union", V_TOTAL, 0.01 * (V_TOTAL - V_SHAFT))

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

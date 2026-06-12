r"""Reproduction script: pinion turning handle (book ch. 25).

The bright ball-and-cross-rod tee on the alignment pinion's front arbor
(p. 67/68; the ch25 close-ups are shot from the BACK, so it appears at
viewer-left there but front-centre in ch30 p002): the operator turns it
to rotate all 20 engaged cylinder gears as one. A short hub journals on
the drum's front arbor stub (build_alignment_pinion.py); the big ball
with its through-rod forms the grip. Modeled as ONE part: bored hub
extrusion plus a single ball+rod solid of revolution about the rod
axis (revolve LAST -- an on-axis revolve breaks later booleans, see
solidworks pitfalls; the merge inside the revolve itself is fine, same
recipe as the old pivot-shaft tee).

Layout: drum axis Z, ball centred at the ORIGIN; hub z 7..14 (the ball
solid reaches z 11.57 inside the bore, so the arbor stub seats z 12..14);
cross rod along Y, asymmetric arms -35..+68 (the short arm stops above
the machine base when the handle leans over).

Volume gate (exact union, mm^3): hub annulus + ball + rod
- ball/rod full pass - ball/hub cap integral (analytic, see V_TOTAL).

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_handle.py
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
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "pinion-handle"
MATERIAL = "Plain Carbon Steel"  # bright steel (p.67)

HUB_DIA = 12.0  # journal hub, photo-scaled vs the rod (low)
HUB_BORE = 6.35  # rides the drum's front arbor stub (derived)
HUB_Z = (7.0, 14.0)  # clear of the ball bulge, 1 clear of the strap face
BALL_DIA = 24.0  # grip ball, p002 photogrammetry (med)
ROD_DIA = 6.0  # cross rod, same stock as the lever (high)
ROD_DOWN = 35.0  # short arm -- stops above the base when leaned (derived)
ROD_UP = 68.0  # long arm, p002 photogrammetry (med)

HUB_R = HUB_DIA / 2.0
BORE_R = HUB_BORE / 2.0
BALL_R = BALL_DIA / 2.0
ROD_R = ROD_DIA / 2.0
JUNCTION = math.sqrt(BALL_R**2 - ROD_R**2)  # 11.6190

V_HUB = math.pi * (HUB_R**2 - BORE_R**2) * (HUB_Z[1] - HUB_Z[0])
V_BALL = (4.0 * math.pi / 3.0) * BALL_R**3
V_ROD = math.pi * ROD_R**2 * (ROD_DOWN + ROD_UP)
# Rod through the ball centre: full-pass cylinder/sphere intersection.
V_BALL_ROD = (4.0 * math.pi / 3.0) * (
    BALL_R**3 - (BALL_R**2 - ROD_R**2) ** 1.5
)
# Ball cap inside the hub annulus (the ball surface z = sqrt(R^2 - r^2)
# crosses the annulus between HUB_Z[0] and HUB_Z[1] for all r in it):
# integral over r in [BORE_R, HUB_R] of 2*pi*r*(sqrt(R^2-r^2) - HUB_Z[0]).
V_BALL_HUB = (2.0 * math.pi / 3.0) * (
    (BALL_R**2 - BORE_R**2) ** 1.5 - (BALL_R**2 - HUB_R**2) ** 1.5
) - math.pi * (HUB_R**2 - BORE_R**2) * HUB_Z[0]
V_TOTAL = V_HUB + V_BALL + V_ROD - V_BALL_ROD - V_BALL_HUB


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Bored hub first (annulus sketch -> offset extrude along +Z).
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, HUB_R, "hub OD")
    await define_circle(adapter, 0.0, 0.0, BORE_R, "hub bore")
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    extrude_at_offset(adapter, HUB_Z[1] - HUB_Z[0], HUB_Z[0])
    volume = await volume_check(adapter, "hub", V_HUB, 0.005 * V_HUB)

    # Ball + cross rod as one revolved profile about +Y (revolve LAST).
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_sketch ball+rod", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline rod axis",
        await adapter.add_centerline(0.0, -ROD_DOWN, 0.0, ROD_UP),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, -ROD_DOWN),
            (ROD_R, -ROD_DOWN),
            (ROD_R, -JUNCTION),
        ],
        close=False,
    )
    arc = check(
        "add_arc ball",
        await adapter.add_arc(
            0.0, 0.0, ROD_R, -JUNCTION, ROD_R, JUNCTION
        ),
    )
    tail = await add_line_chain(
        adapter,
        [
            (ROD_R, JUNCTION),
            (ROD_R, ROD_UP),
            (0.0, ROD_UP),
            (0.0, -ROD_DOWN),
        ],
        close=False,
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(
        adapter, "ball+rod profile", fix_entities=[centerline, *lines, arc, *tail]
    )
    check("exit_sketch ball+rod", await adapter.exit_sketch())
    check(
        "revolve ball+rod",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    await volume_check(
        adapter, "ball+rod union", V_TOTAL, 0.01 * (V_TOTAL - V_HUB)
    )

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: corner bracket (legacy part, frame hardware).

L-bracket joining the frame columns to the base: an upright plate with a
rounded-top lug (sides taper ~2 deg, drawn tangent from the base corners to
the R 0.5 in top arc), a Ø0.4 in lug hole on the arc centre, and a mounting
foot with a #9 (0.196 in) clearance hole. No book numerics exist for this
part; the M1 audit kept the legacy dims, so this re-author replicates the
legacy SLDPRT, whose geometry was interrogated live (GetBodyBox +
PlaneParams/CylinderParams face inventory) because no .cs/.kcl source
survives. Hand-calc volume from those faces: 13,038 mm^3 vs 13,035.0
measured -- the legacy model is fully accounted for.

Dimensions: cad/DIMENSIONS.md "Legacy part audit" - legacy (med).

Layout: profile on the Front plane (width X, height +Y), plate extruded
mid-plane in Z, foot extending +Z. The legacy file has height along Z and
foot along +Y; this script uses the natural upright orientation instead
(legacy y -> +Z, legacy z -> +Y). Tangent points of the tapered sides are
computed exactly, so the sketch is fix-only (no driving dims, see _common).

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_corner_bracket.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    add_line_chain,
    check,
    define_circle,
    ensure_fully_defined,
    extrude_at_offset,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "corner-bracket"

BASE_WIDTH = 1.125 * IN  # legacy: 28.575 across the base
TOTAL_HEIGHT = 2.3 * IN  # legacy: 58.42 to the lug crown
PLATE_THICKNESS = 0.3 * IN  # legacy: 7.62 upright plate
TOP_RADIUS = 0.5 * IN  # legacy: R12.7 lug crown, centre 45.72 up
FOOT_DEPTH = 0.75 * IN  # legacy: 19.05 total (incl. plate thickness)
FOOT_HEIGHT = 0.3 * IN  # legacy: 7.62 foot slab
LUG_HOLE_DIA = 0.4 * IN  # legacy: Ø10.16 on the arc centre
FOOT_HOLE_DIA = 0.196 * IN  # legacy: #9 drill clearance, Ø4.978
THROUGH_CUT_DEPTH = 40.0  # mid-plane total; > any local thickness

HALF_BASE = BASE_WIDTH / 2.0
ARC_CENTER_Y = TOTAL_HEIGHT - TOP_RADIUS  # 45.72
FOOT_FRONT_Z = FOOT_DEPTH - PLATE_THICKNESS / 2.0  # 15.24
FOOT_EXTENSION = FOOT_FRONT_Z - PLATE_THICKNESS / 2.0  # 11.43 beyond the plate
FOOT_HOLE_Z = (PLATE_THICKNESS / 2.0 + FOOT_FRONT_Z) / 2.0  # centred on the
# exposed foot top (legacy hole at y=9.525)


def _tangent_point() -> tuple[float, float]:
    """Tangent point of the line from (+HALF_BASE, 0) to the top arc."""
    px, py = HALF_BASE, 0.0
    cx, cy = 0.0, ARC_CENTER_Y
    dx, dy = cx - px, cy - py
    dist = math.hypot(dx, dy)
    reach = math.sqrt(dist * dist - TOP_RADIUS * TOP_RADIUS)
    angle = math.atan2(dy, dx) - math.asin(TOP_RADIUS / dist)
    return (px + reach * math.cos(angle), py + reach * math.sin(angle))


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    tx, ty = _tangent_point()  # (12.702, 46.159)
    side_slope = (HALF_BASE - tx) / ty  # ~0.0343 (per side, ~2 deg)

    # Upright plate: tombstone profile, extruded mid-plane in Z.
    check("create_sketch plate", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "plate bottom edge",
            await adapter.add_line(-HALF_BASE, 0.0, HALF_BASE, 0.0),
        ),
        check("plate right side", await adapter.add_line(HALF_BASE, 0.0, tx, ty)),
        check(
            "plate crown arc",
            await adapter.add_arc(0.0, ARC_CENTER_Y, tx, ty, -tx, ty),
        ),
        check("plate left side", await adapter.add_line(-tx, ty, -HALF_BASE, 0.0)),
    ]
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "plate sketch", fix_entities=entities)
    check("exit_sketch plate", await adapter.exit_sketch())
    check(
        "extrude plate",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PLATE_THICKNESS, both_directions=True)
        ),
    )
    print(f"  volume after plate: {await _volume(adapter):.1f} mm^3")
    # expected: (1245.8 trapezoid + 242.2 crown segment) * 7.62 = ~11,339 mm^3

    # Mounting foot: trapezoid (sides continue the plate taper), extruded
    # from the plate front face outward (+Z).
    foot_half_top = HALF_BASE - side_slope * FOOT_HEIGHT
    check("create_sketch foot", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    lines = await add_line_chain(
        adapter,
        [
            (-HALF_BASE, 0.0),
            (HALF_BASE, 0.0),
            (foot_half_top, FOOT_HEIGHT),
            (-foot_half_top, FOOT_HEIGHT),
        ],
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "foot sketch", fix_entities=lines)
    check("exit_sketch foot", await adapter.exit_sketch())
    extrude_at_offset(adapter, FOOT_EXTENSION, PLATE_THICKNESS / 2.0)
    print(f"  volume after foot: {await _volume(adapter):.1f} mm^3")
    # expected: +215.7 mm^2 * 11.43 = +2,466 -> ~13,805 mm^3

    # Lug hole through the plate, on the crown arc centre.
    check("create_sketch lug hole", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, ARC_CENTER_Y, LUG_HOLE_DIA / 2.0, "lug hole")
    await ensure_fully_defined(adapter, "lug hole sketch")
    check("exit_sketch lug hole", await adapter.exit_sketch())
    check(
        "cut lug hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )

    # Foot mounting hole, vertical through the exposed foot slab.
    # Top-plane sketch (x, y) maps to global (X, -Z).
    check("create_sketch foot hole", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, -FOOT_HOLE_Z, FOOT_HOLE_DIA / 2.0, "foot hole")
    await ensure_fully_defined(adapter, "foot hole sketch")
    check("exit_sketch foot hole", await adapter.exit_sketch())
    check(
        "cut foot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    print(f"  volume after holes: {await _volume(adapter):.1f} mm^3")
    # expected: -617.9 (lug) -148.3 (foot) -> ~13,038 mm^3 (legacy: 13,035.0)

    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

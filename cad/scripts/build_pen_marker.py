r"""Reproduction script: pen marker (book ch. 24, pp. 60-63).

The marking pen itself: a round barrel with a conical tip, held by the
pen rod's v-block at ~12 degrees so the tip rides the platen paper.
Modeled as a plain barrel + cone (the book pen's collar/ferrule detail
omitted -- simplification).

Layout: axis +Y from the tip at the origin; cone 12 tall, barrel to
y 60. Dimensions: cad/DIMENSIONS.md ch. 24 (M6.4, low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pen_marker.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    define_polygon_chain,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_sketch_direct_db,
)

PART_NAME = "pen-marker"
MATERIAL = "Brass"

BARREL_DIA = 8.0  # (low)
BARREL_TOP_Y = 60.0
CONE_H = 12.0  # tip cone (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    r = BARREL_DIA / 2.0
    check("create_sketch profile", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    check(
        "axis centerline",
        await adapter.add_centerline(0.0, 0.0, 0.0, BARREL_TOP_Y),
    )
    profile_pts = [
        (0.0, 0.0),
        (r, CONE_H),
        (r, BARREL_TOP_Y),
        (0.0, BARREL_TOP_Y),
    ]
    profile = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    # The centerline merged into the tip/top profile corners at creation,
    # so the closed chain's own constraints define it too.
    await define_polygon_chain(adapter, profile, profile_pts, label="marker")
    await ensure_fully_defined(adapter, "marker profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    check("revolve marker", await adapter.create_revolve(RevolveParameters(angle=360.0)))

    expected = math.pi * r * r * (CONE_H / 3.0 + (BARREL_TOP_Y - CONE_H))
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

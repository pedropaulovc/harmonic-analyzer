r"""Reproduction script: crank-pin keeper ring (book ch. 11, p. 14).

The small brass wire ring hanging from the crank taper pin's head
(page002_img01). The pin hole is straight and close-fitting, so the wire uses a
straight through-hole leg; two tangent semicircular bends and a parallel return
close the loop only outside the pin body. A torus cannot represent this hardware:
its centreline curves into the pin before clearing the hole.

Layout: the capsule path lies in local XZ with its through leg centred on the
origin along local Z and its return toward local +X. The drive-train maps local
+Y to machine +X, so the loop hangs toward machine -Y while the straight leg
threads the pin's machine-Z hole.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin_ring.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from crank_pin_spec import BIG_END_DIA, PIN_LENGTH, RING_HOLE_X, SMALL_END_DIA

PART_NAME = "crank-pin-ring"
MATERIAL = "Brass"

WIRE_DIA = 1.2  # brass wire (photo-scaled, low)
PIN_CLEARANCE = 0.25
PIN_DIA_AT_HOLE = BIG_END_DIA - (
    (BIG_END_DIA - SMALL_END_DIA) * RING_HOLE_X / PIN_LENGTH
)
# Both bends begin beyond the pin surface, and the parallel return clears its
# side by the same air gap. This keeps every curved segment outside the pin.
STRAIGHT_HALF = PIN_DIA_AT_HOLE / 2.0 + WIRE_DIA / 2.0 + PIN_CLEARANCE
LOOP_WIDTH = STRAIGHT_HALF
CAP_RADIUS = LOOP_WIDTH / 2.0
PATH_LENGTH = 4.0 * STRAIGHT_HALF + math.pi * LOOP_WIDTH
V_RING = PATH_LENGTH * math.pi * (WIRE_DIA / 2.0) ** 2


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import SweepParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "StraightHalf", f"{STRAIGHT_HALF}mm")
    await set_global(adapter, "LoopWidth", f"{LOOP_WIDTH}mm")
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    drive_jobs: list[tuple[str, str]] = []

    path = SketchDims()
    check("create_sketch keeper path", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    through_leg = check(
        "through-hole leg",
        await adapter.add_line(0.0, -STRAIGHT_HALF, 0.0, STRAIGHT_HALF),
    )
    upper_bend = check(
        "upper bend",
        await adapter.add_arc(
            CAP_RADIUS,
            STRAIGHT_HALF,
            LOOP_WIDTH,
            STRAIGHT_HALF,
            0.0,
            STRAIGHT_HALF,
        ),
    )
    return_leg = check(
        "return leg",
        await adapter.add_line(
            LOOP_WIDTH, STRAIGHT_HALF, LOOP_WIDTH, -STRAIGHT_HALF
        ),
    )
    lower_bend = check(
        "lower bend",
        await adapter.add_arc(
            CAP_RADIUS,
            -STRAIGHT_HALF,
            0.0,
            -STRAIGHT_HALF,
            LOOP_WIDTH,
            -STRAIGHT_HALF,
        ),
    )
    set_sketch_direct_db(adapter, False)

    check(
        "through leg vertical",
        await adapter.add_sketch_constraint(through_leg, None, "vertical"),
    )
    check(
        "return leg vertical",
        await adapter.add_sketch_constraint(return_leg, None, "vertical"),
    )
    for label, line, bend in (
        ("upper through", through_leg, upper_bend),
        ("upper return", return_leg, upper_bend),
        ("lower return", return_leg, lower_bend),
        ("lower through", through_leg, lower_bend),
    ):
        check(
            f"{label} tangent",
            await adapter.add_sketch_constraint(line, bend, "tangent"),
        )
    await anchor_point_to_origin(
        adapter,
        f"{through_leg}.start",
        0.0,
        -STRAIGHT_HALF,
        "through-leg start",
    )
    path.record("ThroughStartZ", '"StraightHalf"')
    check(
        "through leg span",
        await adapter.add_sketch_dimension(
            through_leg, None, "linear", 2.0 * STRAIGHT_HALF
        ),
    )
    path.record("ThroughSpan", '2 * "StraightHalf"')
    await dimension_between(
        adapter,
        f"{through_leg}.start",
        f"{return_leg}.end",
        "horizontal_distance",
        LOOP_WIDTH,
        "loop width",
    )
    path.record("LoopWidthDim", '"LoopWidth"')
    await ensure_fully_defined(adapter, "keeper path")
    check("exit_sketch keeper path", await adapter.exit_sketch())
    name_last_feature(adapter, "KeeperPath")
    drive_jobs += path.apply(adapter, "KeeperPath")

    profile = SketchDims()
    check("create_sketch wire profile", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        WIRE_DIA / 2.0,
        "wire profile",
        dims=profile,
        names=("WireCx", "WireCy", "WireDia"),
        drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "wire profile")
    check("exit_sketch wire profile", await adapter.exit_sketch())
    name_last_feature(adapter, "WireProfile")
    drive_jobs += profile.apply(adapter, "WireProfile")

    check(
        "sweep keeper ring",
        await adapter.create_sweep(SweepParameters(path="KeeperPath")),
    )
    name_last_feature(adapter, "Ring")
    await volume_check(adapter, "keeper ring", V_RING, 0.02 * V_RING)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven keeper ring (equations neutral)", V_RING, 0.02 * V_RING
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

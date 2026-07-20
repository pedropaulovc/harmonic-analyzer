r"""Reproduction script: crank chain eyelet (book ch. 11, pp. 12-15).

The small brass wire eyelet hanging on the keeper screw at the crank arm's
hub-side edge -- the anchor of the pin's small retaining chain ("small
chain eyelet (chain lost)", ch. 11 text; the chain itself is not modelled,
matching the surviving machine). A Ø1 wire loop with a short twisted tail
(``ch11_images/page002_img03``/``img04``).

Dimensions: photo-scaled (low).

Layout: loop axis along local Y through the origin (the loop lies in XZ,
wire-centre radius LOOP_MEAN_R); the tail drops along -Z from the loop's
low point, overlapping the wire slightly so the two merge into one solid.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_chain_eyelet.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "crank-chain-eyelet"
MATERIAL = "Brass"  # see _common.apply_material docstring

WIRE_DIA = 1.0
LOOP_MEAN_R = 3.0  # wire-centre radius: loop reads ~Ø7 over the wire
TAIL_LEN = 3.5  # twisted tail below the loop
TAIL_OVERLAP = 0.7  # tail start buried in the loop wire so the bodies merge


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "WireDia", f"{WIRE_DIA}mm")
    await set_global(adapter, "LoopMeanR", f"{LOOP_MEAN_R}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Loop: wire circle at (+LOOP_MEAN_R, 0) on Front (XY), revolved 360 about
    # a Y centerline through the origin.
    wire = SketchDims()
    check("create_sketch loop", await adapter.create_sketch("Front"))
    centerline = check(
        "add_centerline loop axis",
        await adapter.add_centerline(0.0, -LOOP_MEAN_R, 0.0, LOOP_MEAN_R),
    )
    check(
        "axis vertical",
        await adapter.add_sketch_constraint(centerline, None, "vertical"),
    )
    check(
        "axis through origin",
        await adapter.add_sketch_constraint(f"{centerline}.start", "origin", "vertical_points"),
    )
    await define_circle(
        adapter, LOOP_MEAN_R, 0.0, WIRE_DIA / 2.0, "loop wire", dims=wire,
        names=("LoopCx", "LoopCy", "LoopWireDia"),
        drives=('"LoopMeanR"', None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "loop sketch")
    check("exit_sketch loop", await adapter.exit_sketch())
    name_last_feature(adapter, "LoopProfile")
    drive_jobs += wire.apply(adapter, "LoopProfile")

    check("revolve loop", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Loop")

    v_loop = 2.0 * math.pi**2 * LOOP_MEAN_R * (WIRE_DIA / 2.0) ** 2
    await volume_check(adapter, "loop", v_loop, 0.01 * v_loop)

    # Tail: a Ø1 stub dropping along -Z from the loop's low wire point (the
    # loop lies in XZ, so its low point is at z = -LOOP_MEAN_R). Front-plane
    # circle at the origin extruded from beyond the wire toward -Z, starting
    # TAIL_OVERLAP inside the wire tube so the result is one solid.
    tail = SketchDims()
    check("create_sketch tail", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, WIRE_DIA / 2.0, "tail", dims=tail,
        names=("TailCx", "TailCy", "TailDia"),
        drives=(None, None, '"WireDia"'),
    )
    await ensure_fully_defined(adapter, "tail sketch")
    check("exit_sketch tail", await adapter.exit_sketch())
    name_last_feature(adapter, "TailProfile")
    drive_jobs += tail.apply(adapter, "TailProfile")
    tail_start = LOOP_MEAN_R + WIRE_DIA / 2.0 - TAIL_OVERLAP  # 2.8 from origin
    extrude_at_offset(adapter, TAIL_LEN + TAIL_OVERLAP, tail_start, flip=True)
    name_last_feature(adapter, "Tail")
    v_tail = math.pi * (WIRE_DIA / 2.0) ** 2 * (TAIL_LEN + TAIL_OVERLAP)
    # The overlap lens with the wire tube is sub-mm^3: check with an absolute band.
    expected = v_loop + v_tail
    await volume_check(adapter, "loop + tail", expected, 0.8)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven eyelet (equations neutral)", expected, 0.8)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

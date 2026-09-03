r"""Reproduction script: magnifying-wheel axle nut (book ch. 21, p. 51).

The small hex nut on the wheel axle's stud tip that, with the O9 washer
(the axle's own collar), retains the magnifying wheel: ch21 page002_img01
shows a hex nut at the hub, not a round collar. AF NUT_AF x NUT_H, bore
NUT_BORE_DIA over the O5 stud. Thread not modelled (bore at the stud's
running clearance, the repo convention).

Layout: hexagon on the Top plane about the origin, extruded +Y NUT_H; the
magnifier turns +Y to -Z like the axle. Vertices at exact (r/2, AF/2) so the
flats stay axis-parallel for the polygon anchoring scheme (build_hex_bolt).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_wheel_axle_nut.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
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
from wheel_axle_spec import NUT_AF, NUT_BORE_DIA, NUT_H

PART_NAME = "wheel-axle-nut"
MATERIAL = "Plain Carbon Steel"

_INV_SQRT3 = 1.0 / math.sqrt(3.0)
_HALF_INV_SQRT3 = 0.5 / math.sqrt(3.0)
V_HEX = math.sqrt(3.0) / 2.0 * NUT_AF**2 * NUT_H
V_BORE = math.pi * (NUT_BORE_DIA / 2.0) ** 2 * NUT_H
V_NUT = V_HEX - V_BORE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "NutAF", f"{NUT_AF}mm")
    await set_global(adapter, "NutH", f"{NUT_H}mm")
    await set_global(adapter, "NutBoreDia", f"{NUT_BORE_DIA}mm")
    drive_jobs: list[tuple[str, str]] = []

    radius = NUT_AF / math.sqrt(3.0)
    half_flat = NUT_AF / 2.0
    points = [
        (radius, 0.0),
        (radius / 2.0, half_flat),
        (-radius / 2.0, half_flat),
        (-radius, 0.0),
        (-radius / 2.0, -half_flat),
        (radius / 2.0, -half_flat),
    ]
    _rx = f'"NutAF" * {_INV_SQRT3!r}'
    _rx2 = f'"NutAF" * {_HALF_INV_SQRT3!r}'
    _hf = '"NutAF" / 2'
    hexd = SketchDims()
    check("create_sketch hex", await adapter.create_sketch("Top"))
    hexagon = await add_line_chain(adapter, points)
    await define_polygon_chain(
        adapter, hexagon, points, label="hex", dims=hexd,
        names=["HexV0X", "HexS0dx", "HexS0dy", "HexS1dx", "HexS2dx", "HexS2dy", "HexS3dx", "HexS3dy", "HexS4dx"],
        drives=[_rx, _rx2, _hf, _rx, _rx2, _hf, _rx2, _hf, _rx],
    )
    await ensure_fully_defined(adapter, "hex sketch")
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    drive_jobs += hexd.apply(adapter, "HexProfile")
    extrude_at_offset(adapter, NUT_H, 0.0)
    name_last_feature(adapter, "Hex")
    await volume_check(adapter, "hex", V_HEX, 0.005 * V_HEX)

    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, NUT_BORE_DIA / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "NutBoreDia"), drives=(None, None, '"NutBoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check("cut bore", await adapter.create_cut_extrude(ExtrusionParameters(depth=4.0 * NUT_H, both_directions=True)))
    name_last_feature(adapter, "Bore")
    await volume_check(adapter, "nut", V_NUT, 0.005 * V_HEX)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven nut (equations neutral)", V_NUT, 0.005 * V_HEX)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

r"""Reproduction script: broad brass crankshaft-end washer/cap.

The photo-proven cap covers the outboard face of the crank-arm hub.  Its OD
matches the boss envelope and its small centre clearance receives the separate
short slotted retaining screw.  Layout: Front-plane annulus at z = 0, extruded
+Z to seat directly against the arm face.
"""

from __future__ import annotations

import math
import sys

import _config

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from crank_end_retainer_spec import WASHER_ID, WASHER_OD, WASHER_THICK


PART_NAME = "crank-end-washer"
MATERIAL = str(_config.parts(PART_NAME)["material"])
V_WASHER = math.pi * ((WASHER_OD / 2.0) ** 2 - (WASHER_ID / 2.0) ** 2) * WASHER_THICK


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    await set_global(adapter, "WasherOD", f"{WASHER_OD}mm")
    await set_global(adapter, "WasherID", f"{WASHER_ID}mm")
    await set_global(adapter, "WasherThick", f"{WASHER_THICK}mm")

    profile = SketchDims()
    check("create_sketch washer", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        WASHER_OD / 2.0,
        "washer OD",
        dims=profile,
        names=("OdCx", "OdCy", "WasherOD"),
        drives=(None, None, '"WasherOD"'),
    )
    await define_circle(
        adapter,
        0.0,
        0.0,
        WASHER_ID / 2.0,
        "screw clearance",
        dims=profile,
        names=("IdCx", "IdCy", "WasherID"),
        drives=(None, None, '"WasherID"'),
    )
    await ensure_fully_defined(adapter, "washer sketch")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    drive_jobs = profile.apply(adapter, "WasherProfile")
    check(
        "extrude washer",
        await adapter.create_extrusion(ExtrusionParameters(depth=WASHER_THICK)),
    )
    name_last_feature(adapter, "Washer")
    drive_jobs.append(("D1@Washer", '"WasherThick"'))
    await volume_check(adapter, "crank-end washer", V_WASHER, 0.005 * V_WASHER)

    await force_rebuild(adapter)
    for dim_name, expression in drive_jobs:
        await drive_dimension(adapter, dim_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter,
        "driven crank-end washer (equations neutral)",
        V_WASHER,
        0.005 * V_WASHER,
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

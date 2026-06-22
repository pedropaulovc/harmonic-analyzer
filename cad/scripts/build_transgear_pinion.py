r"""Reproduction script: translational-gearing reduction pinion (book ch. 23).

The small fine-tooth steel pinion that rides coaxially with the 120T rack
pinion (edge-on views `v4_transgear_002/003/008`): estimated 24T DP 30
(measured OD ~ 21 mm; 24T -> 22.0 mm), ~6 mm face, plain 3/8" bore. What it
meshes is unresolved -- Appendix C #8; re-check the tooth count against the
platen-speed law when mating the drive train in M6.

Layout: gear axis = Z through the origin, disc z = 0..6 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_pinion.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
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
)
from _gear import build_fixed_gear, volume_check

PART_NAME = "transgear-pinion"
MATERIAL = "Plain Carbon Steel"  # ch. 23 photos: steel (unlike the brass wheels)

TEETH = 24  # DIMENSIONS.md ch23: est. from measured OD ~21 mm (low)
FACE_WIDTH = 6.0  # mm, edge-on view v4_transgear_002 (low)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- machine-standard shaft stock (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): face width and bore diameter carry the
    # load-bearing mm suffix (INCH document; the equation manager reads bare
    # numbers in document units, so an unsuffixed length blows the part up 25.4x).
    # FaceWidth is the cut-bore depth knob (a feature parameter, not a driven
    # sketch dim). TEETH stays a module constant -- the gear blank/gap/pattern is
    # built by build_fixed_gear with literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH)

    # On-axis bore (centre 0,0): define_circle emits only the diameter dim, so
    # only the "Dia" slot is recorded -- the X/Z names are ignored.
    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIAMETER / 2.0, "bore", dims=bore,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=FACE_WIDTH + 2.0)),
    )
    name_last_feature(adapter, "Bore")
    v_bore = math.pi * (BORE_DIAMETER / 2.0) ** 2 * FACE_WIDTH
    await volume_check(adapter, "bore", volume - v_bore, 0.01 * v_bore)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven transgear pinion (equations neutral)", volume - v_bore, 0.01 * v_bore
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

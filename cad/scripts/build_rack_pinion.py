r"""Reproduction script: translational-gearing rack pinion (book ch. 23).

The large thin brass gear that drives the platen rack: 96 teeth DP 30.
The M4c "120 teeth / OD 103.3" keyframe read is REFUTED by the calibrated
ch. 30 front view (p1, 6.02 px/mm): the gear OD spans ~83 mm centred on
the pinion-bar stud at (0, 253.5) -- 96T DP 30 gives PD 81.28 / OD 82.97.
~3 mm disc, plain 3/8" shaft bore (the latch/stud hardware is modeled in
build_paper_drive_assembly.py; Appendix C #8).

Layout: gear axis = Z through the origin, disc z = 0..3 mm.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rack_pinion.py
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

PART_NAME = "rack-pinion"
MATERIAL = "Brass"  # ch. 23 photos: brass

TEETH = 96  # DIMENSIONS.md ch23: calibrated p1 OD ~83 -> 96T DP30 (med,
# supersedes the 120T keyframe count -- see docstring)
FACE_WIDTH = 3.0  # mm, edge-on view v4_transgear_002 (low)
BORE_DIAMETER = 0.375 * IN  # 9.525 -- machine-standard shaft stock (low)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in document
    # units (an unsuffixed 9.525 would be read as 9.525 inches). FaceWidth is the
    # blank/bore extrude DEPTH (a feature parameter, not a sketch dim), so it is
    # an editable knob but nothing in drive_jobs drives it; BoreDia drives the
    # shaft-bore diameter. The toothed-disc geometry (teeth/DP) is authored by the
    # shared _gear helper with literal-numeric curve expressions, so it has no
    # sketch dim to drive here.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIAMETER}mm")

    drive_jobs: list[tuple[str, str]] = []

    volume = await build_fixed_gear(adapter, TEETH, FACE_WIDTH)

    # Shaft bore (on-axis circle at the origin: only the diameter is a dim, so
    # define_circle records just that -- the centre X/Z slots are ignored).
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
    expected = volume - v_bore
    await volume_check(adapter, "bore", expected, 0.01 * v_bore)

    # Apply the deferred drive equations after the whole model + a rebuild exist,
    # then re-check: each equation evaluates to the as-built value, so the
    # geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven rack pinion (equations neutral)", expected, 0.01 * v_bore)

    # Construction axis (Top x Right = the Z gear axis through the origin): gives the
    # disc an Axis1 the paper-drive assembly can rack-pinion-mate to the platen, so
    # the visible 96T disc turns WITH the paper feed instead of sitting static
    # (codex #189). A reference feature -- no volume, geometry unchanged.
    from solidworks_mcp.adapters.base import CreateAxisParameters  # noqa: E402
    check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])),
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

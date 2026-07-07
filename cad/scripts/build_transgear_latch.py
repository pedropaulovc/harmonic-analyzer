r"""Reproduction script: transgear latch arm (book ch. 23, pp. 56-59).

The tapered link joining the stud to the knob shaft (engineerguy
v4_transgear_008: latch arm with a hole, pivoting ON the stud): a big hub
riding the stud, a small hub carrying the knob shaft, joined by a tapered
web. Its C2C is the PERMANENT 12T:120T DP38 mesh distance -- 44.116
nominal + 0.65 centre extension = 44.766 (the extension clears the
_gear-recipe gap floor at the 12T base circle, the same checker-arbitrated
slack the drive-train meshes use). The arm pivoting on the stud is what
DISSOLVED the old Appendix C #8 riddle: unlatching tilts the whole cluster
away from the rack (v4_transgear 001 vs 011-013) while this c2c never
changes; the old 66.05 was a rest-state fit against the refuted
disc-meshes-rack topology.

Layout: big hub on the origin (stud axis along Z), small hub at
(+44.766, 0) -- the assembly rotates the c2c line to the photo direction.
4.5 thick along Z. Dimensions: memory/paper-drive-rework.md E7/E8.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_transgear_latch.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
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

import _telemetry

PART_NAME = "transgear-latch"
MATERIAL = "Plain Carbon Steel"

BIG_HUB_DIA = 22.0  # rides the rack-pinion stud (low)
SMALL_HUB_DIA = 16.0  # carries the knob shaft (low)
BORE_DIA = 9.6  # both bores ride O9.5 shafts (derived)
C2C = 44.766  # the permanent 12T:120T DP38 mesh: (12 + 120) / (2 * 38) in
# = 44.116 + 0.65 centre extension (gap-floor clearance, see docstring)
THICKNESS = 2.6  # along Z: the arm lives in the 3.0 slot between the rack's
# back face (-132.9) and the bar front / bracket plane (-129.9) -- its big
# hub (r 11) rises past the rack's tooth band in y, so it cannot share the
# rack's z band (derived)
WEB_HALF_AT_BIG = 9.0  # tapered web half-widths (derived: inside hub ODs)
WEB_HALF_AT_SMALL = 6.5


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two hub diameters, the bore, the
    # hub centre distance, and the two web half-widths. The mm suffix is
    # load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 66 = 66 in, 25.4x too big).
    await set_global(adapter, "BigHubDia", f"{BIG_HUB_DIA}mm")
    await set_global(adapter, "SmallHubDia", f"{SMALL_HUB_DIA}mm")
    await set_global(adapter, "BoreDia", f"{BORE_DIA}mm")
    await set_global(adapter, "C2C", f"{C2C}mm")
    await set_global(adapter, "WebHalfAtBig", f"{WEB_HALF_AT_BIG}mm")
    await set_global(adapter, "WebHalfAtSmall", f"{WEB_HALF_AT_SMALL}mm")

    # Each sketch records its dim names + drive equations as the define_* helper
    # emits them; the equations are collected here and applied in one deferred
    # batch at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Big hub disc (on-axis circle: only the diameter is a dim).
    big_hub = SketchDims()
    check("create_sketch big hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, BIG_HUB_DIA / 2.0, "big hub", dims=big_hub,
        names=("BigHubCx", "BigHubCz", "BigHubDia"),
        drives=(None, None, '"BigHubDia"'),
    )
    await ensure_fully_defined(adapter, "big hub sketch")
    check("exit_sketch big hub", await adapter.exit_sketch())
    name_last_feature(adapter, "BigHubProfile")
    drive_jobs += big_hub.apply(adapter, "BigHubProfile")
    check(
        "extrude big hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "BigHub")
    expected = math.pi * (BIG_HUB_DIA / 2.0) ** 2 * THICKNESS
    vol = await _volume(adapter)
    _telemetry.info(f"volume after big hub: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"big hub volume {vol:.1f} != {expected:.1f}")

    # 2. Small hub disc (off-axis on X: centre-X + diameter are the two dims).
    small_hub = SketchDims()
    check("create_sketch small hub", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, C2C, 0.0, SMALL_HUB_DIA / 2.0, "small hub", dims=small_hub,
        names=("SmallHubCx", "SmallHubCz", "SmallHubDia"),
        drives=('"C2C"', None, '"SmallHubDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "small hub sketch")
    check("exit_sketch small hub", await adapter.exit_sketch())
    name_last_feature(adapter, "SmallHubProfile")
    drive_jobs += small_hub.apply(adapter, "SmallHubProfile")
    check(
        "extrude small hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SmallHub")
    expected += math.pi * (SMALL_HUB_DIA / 2.0) ** 2 * THICKNESS
    vol = await _volume(adapter)
    _telemetry.info(f"volume after small hub: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"small hub volume {vol:.1f} != {expected:.1f}")

    # 3. Tapered web joining the hubs. General 4-vertex polygon, anchor vertex 0
    #    at (0, -WebHalfAtBig). Emission order (anchor on +/-Z axis = 1 dim, then
    #    kept segments 0..2 in line order; segment 3 closes): V0z, S0dx, S0dy,
    #    S1dy, S2dx, S2dy.
    web_dims = SketchDims()
    check("create_sketch web", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    web_pts = [
        (0.0, -WEB_HALF_AT_BIG),
        (C2C, -WEB_HALF_AT_SMALL),
        (C2C, WEB_HALF_AT_SMALL),
        (0.0, WEB_HALF_AT_BIG),
    ]
    web = await add_line_chain(adapter, web_pts)
    set_sketch_direct_db(adapter, False)
    await define_polygon_chain(
        adapter, web, web_pts, label="web", dims=web_dims,
        names=["WebV0z", "WebS0dx", "WebS0dy", "WebS1dy", "WebS2dx", "WebS2dy"],
        drives=[
            '"WebHalfAtBig"',
            '"C2C"',
            '"WebHalfAtBig" - "WebHalfAtSmall"',
            '2 * "WebHalfAtSmall"',
            '"C2C"',
            '"WebHalfAtBig" - "WebHalfAtSmall"',
        ],
    )
    await ensure_fully_defined(adapter, "web sketch")
    check("exit_sketch web", await adapter.exit_sketch())
    name_last_feature(adapter, "WebProfile")
    drive_jobs += web_dims.apply(adapter, "WebProfile")
    check(
        "extrude web",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Web")
    v_web = (WEB_HALF_AT_BIG + WEB_HALF_AT_SMALL) * C2C * THICKNESS
    before = expected
    vol = await _volume(adapter)
    added = vol - before
    _telemetry.info(f"volume after web: {vol:.1f} mm^3 (+{added:.1f}, solid {v_web:.1f})")
    if not (0.5 * v_web <= added <= 1.0 * v_web):
        raise RuntimeError(f"web: added {added:.1f}, expected 50-100% of {v_web:.1f}")
    expected = vol

    # 4. The two bores (big on-axis: 1 dim; small off-axis on X: 2 dims).
    bores = SketchDims()
    check("create_sketch bores", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    await define_circle(
        adapter, 0.0, 0.0, BORE_DIA / 2.0, "big bore", dims=bores,
        names=("BigBoreCx", "BigBoreCz", "BigBoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await define_circle(
        adapter, C2C, 0.0, BORE_DIA / 2.0, "small bore", dims=bores,
        names=("SmallBoreCx", "SmallBoreCz", "SmallBoreDia"),
        drives=('"C2C"', None, '"BoreDia"'),
    )
    set_sketch_direct_db(adapter, False)
    await ensure_fully_defined(adapter, "bores sketch")
    check("exit_sketch bores", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bores.apply(adapter, "BoreProfile")
    check(
        "cut bores",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bores")
    expected -= 2.0 * math.pi * (BORE_DIA / 2.0) ** 2 * THICKNESS
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bores: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"bores volume {vol:.1f} != {expected:.1f}")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven transgear latch (equations neutral)", expected, 0.005 * expected
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

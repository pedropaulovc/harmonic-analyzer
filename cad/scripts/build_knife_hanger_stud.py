r"""Reproduction script: knife-hanger stud (top.png stud crops; 2 used).

ONE merged part -- 1/2-13 stud with integral washer disc, hex nut, turned
collar, and center-drilled tip (tmp_measure/crops/top_stud1/2.png show the
big hex nut on a washer with the turned tip at both crossbar junctions).
The lower 12 threads into the knife-mount top's tapped 1/2-13 hole, the
plain shank crosses the 0.25 mount gap and rides the casting crossbar's
O13.49 close-clearance bore (999.7..1036.2), and the washer/hex/collar/tip
stack stands above the casting top face.  Two in summing.SLDASM at
(x -15, z -83.972 / +90.148), bottom at machine y 987.45 (top 1056.7).
Thread geometry not modeled; the engagement is a reduced O10.6 neck, just
under the mount's 10.716 tap drill (repo convention: modeled thread < tap
drill), so the assembly interference gate sees zero stud/mount overlap.

Layout: axis along Y, AUTHORED IN FINAL ORIENTATION (threaded end down):
origin at the BOTTOM of the shank.  Thread 0..12 (O10.6), plain shank
12..48.75 (O12.7), washer 48.75..51.25, hex 51.25..62.25, collar
62.25..65.25, tip 65.25..69.25 with the cosmetic center-drill cut in its
end face.  Symmetric about local x = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_knife_hanger_stud.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_circle,
    define_polygon_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from knife_hanger_stud_spec import (
    CDRILL_DEPTH,
    CDRILL_DIA,
    COLLAR_DIA,
    COLLAR_H,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    NUT_AF,
    NUT_H,
    SHANK_DIA,
    SHANK_LEN,
    THREAD_DIA,
    THREAD_LEN,
    TIP_DIA,
    TIP_LEN,
    TOTAL_LEN,
    WASHER_DIA,
    WASHER_T,
)

PART_NAME = "knife-hanger-stud"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright hardware

# Every hex offset dim is linear in the across-flats (radius = AF/sqrt 3), so a
# single NutAF global drives them all via dimensionless coefficients -- unit-safe
# (no mm/inch trap) and no SolidWorks sqr() syntax to get wrong.
_INV_SQRT3 = 1.0 / math.sqrt(3.0)  # radius / AF
_HALF_INV_SQRT3 = 0.5 * _INV_SQRT3  # (radius/2) / AF

# Feature stack stations (local y, bottom of the shank = 0).
PLAIN_LEN = SHANK_LEN - THREAD_LEN  # plain-shank run above the thread (36.75)
WASHER_Y = SHANK_LEN
NUT_Y = WASHER_Y + WASHER_T
COLLAR_Y = NUT_Y + NUT_H
TIP_Y = COLLAR_Y + COLLAR_H
assert TIP_Y + TIP_LEN == TOTAL_LEN
assert THREAD_LEN + PLAIN_LEN == SHANK_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    # The lengths are extrude DEPTHS (feature parameters) -- declared as knobs,
    # but nothing in drive_jobs references them.
    await set_global(adapter, "ThreadDia", f"{THREAD_DIA}mm")
    await set_global(adapter, "ThreadLen", f"{THREAD_LEN}mm")
    await set_global(adapter, "ShankDia", f"{SHANK_DIA}mm")
    await set_global(adapter, "ShankLen", f"{PLAIN_LEN}mm")
    await set_global(adapter, "WasherDia", f"{WASHER_DIA}mm")
    await set_global(adapter, "WasherT", f"{WASHER_T}mm")
    await set_global(adapter, "NutAF", f"{NUT_AF}mm")
    await set_global(adapter, "NutH", f"{NUT_H}mm")
    await set_global(adapter, "CollarDia", f"{COLLAR_DIA}mm")
    await set_global(adapter, "CollarH", f"{COLLAR_H}mm")
    await set_global(adapter, "TipDia", f"{TIP_DIA}mm")
    await set_global(adapter, "TipLen", f"{TIP_LEN}mm")
    await set_global(adapter, "CDrillDia", f"{CDRILL_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Threaded engagement 0..12: modeled at the reduced O10.6, just under the
    # knife-mount's 10.716 tap drill (repo convention: modeled thread < tap
    # drill), so the assembly interference gate sees zero stud/mount overlap.
    thread_dims = SketchDims()
    check("create_sketch thread", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, THREAD_DIA / 2.0, "thread", dims=thread_dims,
        names=("ThreadCx", "ThreadCz", "ThreadDia"),
        drives=(None, None, '"ThreadDia"'),
    )
    await ensure_fully_defined(adapter, "thread sketch")
    check("exit_sketch thread", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadProfile")
    drive_jobs += thread_dims.apply(adapter, "ThreadProfile")
    extrude_at_offset(adapter, THREAD_LEN, 0.0)
    name_last_feature(adapter, "Thread")
    name_dimensions(adapter, "Thread", ["ThreadLg"])
    v_thread = math.pi * (THREAD_DIA / 2.0) ** 2 * THREAD_LEN
    expected = v_thread
    await volume_check(adapter, "thread", expected, 0.005 * v_thread)

    # Plain shank 12..48.75 (rides the crossbar's O13.49 close-clearance bore
    # at the full 1/2-13 major; on-axis circle: only the diameter is a dim).
    shank_dims = SketchDims()
    check("create_sketch shank", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, SHANK_DIA / 2.0, "shank", dims=shank_dims,
        names=("ShankCx", "ShankCz", "ShankDia"),
        drives=(None, None, '"ShankDia"'),
    )
    await ensure_fully_defined(adapter, "shank sketch")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    drive_jobs += shank_dims.apply(adapter, "ShankProfile")
    extrude_at_offset(adapter, PLAIN_LEN, THREAD_LEN)
    name_last_feature(adapter, "Shank")
    name_dimensions(adapter, "Shank", ["ShankLg"])
    v_shank = math.pi * (SHANK_DIA / 2.0) ** 2 * PLAIN_LEN
    expected += v_shank
    await volume_check(adapter, "shank", expected, 0.005 * v_shank)

    # Integral washer disc 48.75..51.25.
    washer_dims = SketchDims()
    check("create_sketch washer", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, WASHER_DIA / 2.0, "washer", dims=washer_dims,
        names=("WasherCx", "WasherCz", "WasherDia"),
        drives=(None, None, '"WasherDia"'),
    )
    await ensure_fully_defined(adapter, "washer sketch")
    check("exit_sketch washer", await adapter.exit_sketch())
    name_last_feature(adapter, "WasherProfile")
    drive_jobs += washer_dims.apply(adapter, "WasherProfile")
    extrude_at_offset(adapter, WASHER_T, WASHER_Y)
    name_last_feature(adapter, "Washer")
    name_dimensions(adapter, "Washer", ["WasherT"])
    v_washer = math.pi * (WASHER_DIA / 2.0) ** 2 * WASHER_T
    expected += v_washer
    await volume_check(adapter, "washer", expected, 0.005 * v_washer)

    # Integral hex nut 51.25..62.25 (AF 19; exact-arithmetic vertices
    # (r/2, AF/2) keep the flats' offsets exactly axis-parallel for the
    # polygon anchoring scheme; Top sketch: sketch (x, y) -> global (X, -Z)).
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
    # Emission order (anchor vertex 0 on +X axis = 1 dim; then segments 0..4,
    # segment 5 closes): V0x, S0dx, S0dy, S1dx, S2dx, S2dy, S3dx, S3dy, S4dx.
    _rx = f'"NutAF" * {_INV_SQRT3!r}'      # radius
    _rx2 = f'"NutAF" * {_HALF_INV_SQRT3!r}'  # radius / 2
    _hf = '"NutAF" / 2'                      # half_flat
    nut_dims = SketchDims()
    check("create_sketch hex nut", await adapter.create_sketch("Top"))
    nut = await add_line_chain(adapter, points)
    await define_polygon_chain(
        adapter, nut, points, label="hex nut", dims=nut_dims,
        names=["NutV0X", "NutS0dx", "NutS0dy", "NutS1dx",
               "NutS2dx", "NutS2dy", "NutS3dx", "NutS3dy", "NutS4dx"],
        drives=[_rx, _rx2, _hf, _rx, _rx2, _hf, _rx2, _hf, _rx],
    )
    await ensure_fully_defined(adapter, "hex nut sketch")
    check("exit_sketch hex nut", await adapter.exit_sketch())
    name_last_feature(adapter, "HexNutProfile")
    drive_jobs += nut_dims.apply(adapter, "HexNutProfile")
    extrude_at_offset(adapter, NUT_H, NUT_Y)
    name_last_feature(adapter, "HexNut")
    name_dimensions(adapter, "HexNut", ["NutHt"])
    v_nut = math.sqrt(3.0) / 2.0 * NUT_AF**2 * NUT_H
    expected += v_nut
    await volume_check(adapter, "hex nut", expected, 0.005 * v_nut)

    # Turned collar 62.25..65.25.
    collar_dims = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, COLLAR_DIA / 2.0, "collar", dims=collar_dims,
        names=("CollarCx", "CollarCz", "CollarDia"),
        drives=(None, None, '"CollarDia"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar_dims.apply(adapter, "CollarProfile")
    extrude_at_offset(adapter, COLLAR_H, COLLAR_Y)
    name_last_feature(adapter, "Collar")
    name_dimensions(adapter, "Collar", ["CollarHt"])
    v_collar = math.pi * (COLLAR_DIA / 2.0) ** 2 * COLLAR_H
    expected += v_collar
    await volume_check(adapter, "collar", expected, 0.005 * v_collar)

    # Tip 65.25..69.25.
    tip_dims = SketchDims()
    check("create_sketch tip", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, TIP_DIA / 2.0, "tip", dims=tip_dims,
        names=("TipCx", "TipCz", "TipDia"),
        drives=(None, None, '"TipDia"'),
    )
    await ensure_fully_defined(adapter, "tip sketch")
    check("exit_sketch tip", await adapter.exit_sketch())
    name_last_feature(adapter, "TipProfile")
    drive_jobs += tip_dims.apply(adapter, "TipProfile")
    extrude_at_offset(adapter, TIP_LEN, TIP_Y)
    name_last_feature(adapter, "Tip")
    name_dimensions(adapter, "Tip", ["TipLg"])
    v_tip = math.pi * (TIP_DIA / 2.0) ** 2 * TIP_LEN
    expected += v_tip
    await volume_check(adapter, "tip", expected, 0.005 * v_tip)

    # Cosmetic center-drill cut in the tip end face (the turned tip's drive
    # center in the top.png crops).  A CUT's default direction is OPPOSITE the
    # sketch normal (FeatureCut4 remarks), so from the tip-top plane it already
    # cuts DOWN into the tip.
    check("create_plane TipTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane",
                              offset=TOTAL_LEN)))
    name_last_feature(adapter, "TipTop")
    cdrill_dims = SketchDims()
    check("create_sketch center drill", await adapter.create_sketch("TipTop"))
    await define_circle(
        adapter, 0.0, 0.0, CDRILL_DIA / 2.0, "center drill", dims=cdrill_dims,
        names=("CDrillCx", "CDrillCz", "CDrillDiaDim"),
        drives=(None, None, '"CDrillDia"'),
    )
    await ensure_fully_defined(adapter, "center drill sketch")
    check("exit_sketch center drill", await adapter.exit_sketch())
    name_last_feature(adapter, "CenterDrillProfile")
    drive_jobs += cdrill_dims.apply(adapter, "CenterDrillProfile")
    check("cut center drill", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=CDRILL_DEPTH)))
    name_last_feature(adapter, "CenterDrill")
    v_cdrill = math.pi * (CDRILL_DIA / 2.0) ** 2 * CDRILL_DEPTH
    expected -= v_cdrill
    await volume_check(adapter, "center drill", expected, 0.02 * v_cdrill)

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven stud (equations neutral)", expected, 0.02 * v_cdrill
    )

    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "stud axis")
    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))

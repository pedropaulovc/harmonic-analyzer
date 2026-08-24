r"""Shared recipe for the McMaster 91882A* knurled-head thumb screws.

Two sizes (#4-40 x 7/16" and 1/4"-20 x 5/16"), one parametric recipe,
straight from the vendor tree: shank extrude + tip chamfer P*0.75 ->
collar boss -> head boss -> Chamfer2 (HH/10 on head top rim, head bottom
rim, collar bottom rim) -> Fillet1 (HH*0.1 at the collar-top/
head-underside corner) -> split at the collar underside -> tip-seeded
thread helix (L+P) + symmetric cutter law, sweep scoped to the shank
body -> Combine (ADD) re-unites the bodies (no runout boss on this
family) -> knurl: V-notch cutter (half-angle 1 deg, depth HH/40) swept
down a steep helix (pitch HH*20, 0.05 rev over the head height),
mirrored across the groove's start meridian, both circular-patterned x90
(geometry pattern) = the crossed diamond knurl.
Vendor equations: Chamfer1 = P*.75, Chamfer2 = HH/10, Fillet1 = HH*.1,
root flat D1 = P/8, knurl pattern count = (360/2deg)*.5 = 90.

Per-part entry points: ``diag_build_91882A221.py`` / ``diag_build_91882A412.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    check,
    name_last_feature,
    volume_check,
)
from diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    bodies,
    insert_helix,
    offset_plane,
    thread_sweep_cut,
)

THUMB_SPECS = {
    "91882A221": dict(major_r=2.8448 / 2.0, pitch=0.635, length=11.1125,
                      collar_r=6.35 / 2.0, collar_h=2.38125,
                      head_r=9.525 / 2.0, head_h=2.38125),
    "91882A412": dict(major_r=6.35 / 2.0, pitch=1.27, length=7.9375,
                      collar_r=12.7 / 2.0, collar_h=9.525,
                      head_r=25.4 / 2.0, head_h=6.35),
}


async def build_thumb_screw(adapter, part_no: str):
    from _common import (add_line_chain, _early_bound, _read_member)
    from diag_mcmaster_lib import (combine_union, mass_properties,
                                   no_sketch_inference, split_at_plane)
    from solidworks_mcp.adapters.base import (CircularPatternParameters,
                                              CreateAxisParameters,
                                              ExtrusionParameters,
                                              MirrorFeatureParameters,
                                              RevolveParameters)

    s = THUMB_SPECS[part_no]
    major_r, pitch, length = s["major_r"], s["pitch"], s["length"]
    collar_r, collar_h = s["collar_r"], s["collar_h"]
    head_r, head_h = s["head_r"], s["head_h"]
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    tip_ch = pitch * 0.75
    tip_y = -length
    head_top = collar_h + head_h
    ch2 = head_h / 10.0
    fil = head_h * 0.1
    knurl_w = head_r * math.tan(math.radians(1.0))
    knurl_d = head_h / 40.0

    # --- shank with tip chamfer (vendor Extrude1 + Chamfer1) ----------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, 0.0, 0.0, 0.0, tip_y / 1000.0, 0.0) is None:
        raise RuntimeError("thumb shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (major_r, tip_y + tip_ch),
            (major_r - tip_ch, tip_y),
            (0.0, tip_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * (length - tip_ch)
               + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    # --- collar + head bosses ----------------------------------------------
    check("create_sketch collar", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, collar_r / 1000.0) is None:
            raise RuntimeError("collar circle failed")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    check("collar boss", await adapter.create_extrusion(ExtrusionParameters(
        depth=collar_h)))
    name_last_feature(adapter, "Collar")
    v_collar = math.pi * collar_r ** 2 * collar_h
    await volume_check(adapter, "collar boss",
                       v_shank + v_collar, 0.005 * v_collar)

    offset_plane(adapter, "HeadBasePlane", collar_h)
    check("create_sketch head", await adapter.create_sketch("HeadBasePlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, head_r / 1000.0) is None:
            raise RuntimeError("head circle failed")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    check("head boss", await adapter.create_extrusion(ExtrusionParameters(
        depth=head_h)))
    name_last_feature(adapter, "Head")
    v_head = math.pi * head_r ** 2 * head_h
    await volume_check(adapter, "head boss",
                       v_shank + v_collar + v_head, 0.005 * v_head)

    # --- Chamfer2 (three rims, HH/10 x 45deg) then Fillet1 ------------------
    check("chamfer2", await adapter.add_chamfer(ch2, [
        [head_r, head_top, 0.0],       # head top rim
        [head_r, collar_h, 0.0],       # head bottom rim
        [collar_r, 0.0, 0.0],          # collar bottom rim
    ]))
    name_last_feature(adapter, "RimChamfers")
    check("fillet1", await adapter.add_fillet(
        fil, [[collar_r, collar_h, 0.0]]))
    name_last_feature(adapter, "CollarFillet")

    # --- split at the collar underside, thread the shank, re-combine --------
    body_boxes = split_at_plane(adapter, "Top Plane", "ThreadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    offset_plane(adapter, "TipPlane", tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, (length + pitch) / pitch, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    cy = tip_y - 7.0 * pitch / 16.0
    top_r = major_r + h_sharp / 16.0
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (top_r, cy + 15.0 * pitch / 32.0),
            (root_r, cy + pitch / 16.0),
            (root_r, cy - pitch / 16.0),
            (top_r, cy - 15.0 * pitch / 32.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove", tangency=(0, 0))
    combine_union(adapter, "Recombine")
    v_after_thread = mass_properties(adapter)["volume_mm3"]
    _telemetry.info(f"post-thread volume: {v_after_thread}")

    # --- crossed knurl ------------------------------------------------------
    offset_plane(adapter, "KnurlTopPlane", head_top)
    check("create_sketch knurl helix seed",
          await adapter.create_sketch("KnurlTopPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, head_r / 1000.0) is None:
        raise RuntimeError("knurl helix seed failed")
    insert_helix(adapter, head_h * 20.0, 0.05, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="KnurlHelix")

    # V-notch cutter in plan on the head top, at the +x meridian (the same
    # meridian the Front mirror plane contains, so the mirrored groove's
    # crossings land on the pattern grid exactly as the vendor's do).
    check("create_sketch knurl cutter",
          await adapter.create_sketch("KnurlTopPlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (head_r, knurl_w),
            (head_r - knurl_d, 0.0),
            (head_r, -knurl_w),
        ])
    check("exit_sketch knurl cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "KnurlCutter")
    merged = bodies(adapter)
    if len(merged) != 1:
        raise RuntimeError(f"expected 1 body before knurl, have {len(merged)}")
    merged_name = str(_read_member(_early_bound(merged[0], "IBody2"), "Name"))
    thread_sweep_cut(adapter, "KnurlCutter", "KnurlHelix", merged_name,
                     "KnurlGroove", tangency=(0, 0))

    check("knurl mirror", await adapter.mirror_feature(MirrorFeatureParameters(
        plane="Front Plane", features=["KnurlGroove"])))
    name_last_feature(adapter, "KnurlMirror")

    check("pattern axis", await adapter.create_axis(CreateAxisParameters(
        mode="two_planes", planes=["Front Plane", "Right Plane"])))
    name_last_feature(adapter, "PatternAxis")
    check("knurl pattern", await adapter.circular_pattern_feature(
        CircularPatternParameters(
            axis_name="PatternAxis",
            features=["KnurlGroove", "KnurlMirror"],
            count=90, angle=360.0, equal_spacing=True,
            geometry_pattern=True)))
    name_last_feature(adapter, "KnurlPattern")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]

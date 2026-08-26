r"""McMaster 91410A538 -- square-head cup-point set screw, 1/4"-20 x 5/8".

Two boss revolves (shank+cup point, then the head), the square cut as a
ThroughAll FeatureCut4 with Flip=True (remove OUTSIDE the 6.35-square --
the head revolve's OD is major_d*sqrt(2) so the square's corners land
exactly on it), 75-deg chamfer cones top+bottom of the head, split at
the junction, tip-seeded ascending helix L+P (13.5 revs, vendor stores
start angle 90 explicitly), the SYMMETRIC 90114A511 cutter law at
tip - 7P/16 in air, sweep scoped to the shank, 60-deg runout frustum at
the junction (re-merges).  Cup point: 45-deg outer chamfer to the rim,
59-deg interior cone (rim radius 1.739789 as solved in Sketch2).
Frame: junction y=0, head +y (vendor origin is the junction too).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91410A538.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
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
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

SQ_MAJOR_R = 6.35 / 2.0
SQ_LEN = 15.875
SQ_HH = 4.7625
SQ_PITCH = 1.27
SQ_CUP_RIM_R = 1.739789   # Sketch2 solved rim; 45/59 deg from its dims
SQ_CHAMFER_DEG = 75.0     # head chamfer cones (Sketch3 D1/D2)


async def build_91410A538(adapter, truth=None):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import RevolveParameters

    major_r = SQ_MAJOR_R
    pitch = SQ_PITCH
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    od_r = major_r * math.sqrt(2.0)          # head revolve OD 4.490128
    cham = (od_r - major_r) * math.tan(math.radians(90.0 - SQ_CHAMFER_DEG))
    rim_r = SQ_CUP_RIM_R
    cup_apex_y = -SQ_LEN + rim_r / math.tan(math.radians(59.0))
    cham_start_y = -SQ_LEN + (major_r - rim_r)   # 45-deg outer chamfer

    # --- shank + cup point ---------------------------------------------------
    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, 0.0, 0.0,
                           0.0, -SQ_LEN / 1000.0, 0.0) is None:
        raise RuntimeError("91410 shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (major_r, cham_start_y),
            (rim_r, -SQ_LEN),
            (0.0, cup_apex_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * -cham_start_y
               + _rev_frustum(cham_start_y + SQ_LEN, major_r, rim_r)
               - _rev_frustum(cup_apex_y + SQ_LEN, rim_r, 0.0))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    # --- head revolve (OD cylinder + 75-deg chamfer cones) -------------------
    check("create_sketch head", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, 0.0, 0.0,
                           0.0, SQ_HH / 1000.0, 0.0) is None:
        raise RuntimeError("91410 head: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, SQ_HH),
            (major_r, SQ_HH),
            (od_r, SQ_HH - cham),
            (od_r, cham),
            (major_r, 0.0),
            (0.0, 0.0),
        ])
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    check("revolve head", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Head")
    v_head = (math.pi * od_r ** 2 * (SQ_HH - 2.0 * cham)
              + 2.0 * _rev_frustum(cham, od_r, major_r))
    await volume_check(adapter, "head revolve", v_shank + v_head,
                       0.005 * v_head)

    # --- square (ThroughAll cut, remove OUTSIDE the profile) -----------------
    offset_plane(adapter, "HeadTopPlane", SQ_HH)
    check("create_sketch square", await adapter.create_sketch("HeadTopPlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-major_r, -major_r),
            (major_r, -major_r),
            (major_r, major_r),
            (-major_r, major_r),
        ])
    check("exit_sketch square", await adapter.exit_sketch())
    name_last_feature(adapter, "SquareProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "SquareProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, True, False,           # single ended, Flip=outside, default dir
        1, 0, 0.0, 0.0,              # T1 ThroughAll
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False,                       # NormalCut
        False, True,                 # UseFeatScope, UseAutoSelect
        False, False, False,         # assembly scope args
        0, 0.0, False,               # T0 sketch plane
        False)                       # OptimizeGeometry
    if feat is None:
        raise RuntimeError("square cut failed")
    name_last_feature(adapter, "SquareCut")
    # corner segments beyond the 6.35 square inside the OD circle: exact on
    # the OD band, Simpson over each chamfer cone
    def _seg(R):
        if R <= major_r:
            return 0.0
        th = 2.0 * math.acos(major_r / R)
        return 4.0 * R * R / 2.0 * (th - math.sin(th))
    n, acc = 50, 0.0
    for i in range(n + 1):
        w = (1 if i in (0, n) else (4 if i % 2 else 2))
        acc += w * _seg(major_r + (od_r - major_r) * i / n)
    v_cham_cut = acc * (cham / n) / 3.0
    v_sq_cut = _seg(od_r) * (SQ_HH - 2.0 * cham) + 2.0 * v_cham_cut
    await volume_check(adapter, "square cut",
                       v_shank + v_head - v_sq_cut, 0.01 * v_sq_cut)

    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- tip-seeded ascending helix, L+P (vendor stores start angle 90) -----
    offset_plane(adapter, "TipPlane", -SQ_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, SQ_LEN / pitch + 1.0, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    cy = -SQ_LEN - 7.0 * pitch / 16.0
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
                     "ThreadGroove")

    # --- 60-deg runout at the junction (their Boss-Extrude1, draft 60) ------
    taper_h = (major_r - root_r) / math.sqrt(3.0)
    check("create_sketch runout", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    if sk2.CreateCenterLine(0.0, 0.0, 0.0,
                            0.0, -taper_h / 1000.0, 0.0) is None:
        raise RuntimeError("runout: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, 0.0),
            (major_r, 0.0),
            (root_r, -taper_h),
            (0.0, -taper_h),
        ])
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    check("runout cone", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "ThreadRunout")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("91410A538", build_91410A538))

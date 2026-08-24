r"""McMaster 92865A585 -- Grade 5 zinc steel hex head screw, 5/16"-18 x 1-1/4".

The 93075A194 recipe scaled up, minus the crown dish, plus the Grade 5
marking (a 0.381-wide stadium dash from r=2.54 to r=5.08 cut 0.254 deep
into the head top, patterned 3x at 120 deg -- authored here as three
rotated profiles in ONE sketch instead of CirPattern) and a washer-face
step (0.128984 = HH*.025 trimmed off the head bottom outside
r = HW*.95/2).  Frame: vendor origin (mid overall), underside +13.295,
top +18.455, tip -18.455.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_92865A585.py

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
from diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

G5_MAJOR_R = 7.9502 / 2.0
G5_LEN = 31.75
G5_HW = 12.7
G5_HH = 5.159375
G5_PITCH = 25.4 / 18.0     # stored 1.411111
G5_UNDERSIDE = 13.2953125   # (L + HH)/2 - HH: vendor origin is mid-overall


async def build_92865A585(adapter, truth):
    from _common import (add_line_chain, _early_bound, _feature_by_name,
                         _read_member)
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r = G5_MAJOR_R
    pitch = G5_PITCH
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    flat_r = G5_HW / 2.0
    hex_R = flat_r * 2.0 / math.sqrt(3.0)
    tip_y = G5_UNDERSIDE - G5_LEN            # -18.455
    top_y = G5_UNDERSIDE + G5_HH             # +18.455 (once rounded)
    tip_ch = pitch * 0.851                   # 1.200856
    mark_w = G5_HW * 0.03                    # 0.381 dash width
    mark_r1 = G5_HW * 0.4 / 2.0              # 2.54 inner extent
    mark_r2 = G5_HW * 0.8 / 2.0              # 5.08 outer extent
    mark_d = 0.254
    step_r = G5_HW * 0.95 / 2.0              # 6.0325
    step_d = G5_HH * 0.025                   # 0.128984

    check("create_sketch shank", await adapter.create_sketch("Front"))
    sk = adapter.currentSketchManager
    if sk.CreateCenterLine(0.0, G5_UNDERSIDE / 1000.0, 0.0,
                           0.0, tip_y / 1000.0, 0.0) is None:
        raise RuntimeError("92865 shank: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, G5_UNDERSIDE),
            (major_r, G5_UNDERSIDE),
            (major_r, tip_y + tip_ch),
            (major_r - tip_ch, tip_y),
            (0.0, tip_y),
        ])
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    check("revolve shank", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Shank")
    v_shank = (math.pi * major_r ** 2 * (G5_LEN - tip_ch)
               + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "shank revolve", v_shank, 0.005 * v_shank)

    offset_plane(adapter, "UndersidePlane", G5_UNDERSIDE)
    check("create_sketch hex", await adapter.create_sketch("UndersidePlane"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, hex_R),
            (-flat_r, hex_R / 2.0),
            (-flat_r, -hex_R / 2.0),
            (0.0, -hex_R),
            (flat_r, -hex_R / 2.0),
            (flat_r, hex_R / 2.0),
        ])
    check("exit_sketch hex", await adapter.exit_sketch())
    name_last_feature(adapter, "HexProfile")
    check("extrude hex", await adapter.create_extrusion(ExtrusionParameters(
        depth=G5_HH)))
    name_last_feature(adapter, "HexHead")
    v_hex = G5_HW ** 2 * math.sqrt(3.0) / 2.0 * G5_HH
    await volume_check(adapter, "hex head", v_shank + v_hex, 0.005 * v_hex)

    offset_plane(adapter, "HeadTopPlane", top_y)
    check("create_sketch trim", await adapter.create_sketch("HeadTopPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, flat_r / 1000.0) is None:
        raise RuntimeError("trim circle failed")
    check("exit_sketch trim", await adapter.exit_sketch())
    name_last_feature(adapter, "TrimProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "TrimProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, True, False, 1, 0, 0.0, 0.0,
        True, False, False, False, math.radians(60.0), 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False)
    if feat is None:
        raise RuntimeError("corner trim cut failed")
    name_last_feature(adapter, "CornerTrim")
    from diag_mcmaster_lib import mass_properties
    v_after_trim = mass_properties(adapter)["volume_mm3"]

    # --- Grade 5 dashes: one stadium slot cut per 120-deg position.
    # A hand-authored arc+line stadium contour is rejected by FeatureCut4
    # (loop never closes exactly); the dedicated CreateSketchSlot API
    # (straight, center-to-center) builds a cuttable slot directly.
    def _rot(x, y, deg):
        a = math.radians(deg)
        return (x * math.cos(a) - y * math.sin(a),
                x * math.sin(a) + y * math.cos(a))

    hw = mark_w / 2.0
    for i, deg in enumerate((0.0, 120.0, 240.0)):
        check(f"create_sketch mark{i}",
              await adapter.create_sketch("HeadTopPlane"))
        sk3 = adapter.currentSketchManager
        c1 = _rot(0.0, mark_r1 + hw, deg)
        c2 = _rot(0.0, mark_r2 - hw, deg)
        with no_sketch_inference(adapter):
            if sk3.CreateSketchSlot(
                    0, 0, mark_w / 1000.0,
                    c1[0] / 1000.0, c1[1] / 1000.0, 0.0,
                    c2[0] / 1000.0, c2[1] / 1000.0, 0.0,
                    0.0, 0.0, 0.0, 1, False) is None:
                raise RuntimeError(f"mark slot failed at {deg}")
        check(f"exit_sketch mark{i}", await adapter.exit_sketch())
        name_last_feature(adapter, f"MarkProfile{i}")
        model.ClearSelection2(True)
        _feature_by_name(adapter, f"MarkProfile{i}").Select2(False, 0)
        feat = fm.FeatureCut4(
            True, False, False,              # single, no flip, default dir
            0, 0, mark_d / 1000.0, 0.0,      # blind 0.254
            False, False, False, False, 0.0, 0.0,
            False, False, False, False,
            False, False, True, False, False, False,
            0, 0.0, False, False)
        if feat is None:
            raise RuntimeError(f"grade mark cut {i} failed")
        name_last_feature(adapter, f"GradeMark{i}")
    slot_area = mark_w * (mark_r2 - mark_r1 - mark_w) + math.pi * (mark_w / 2.0) ** 2
    v_marks = 3.0 * slot_area * mark_d
    await volume_check(adapter, "grade marks",
                       v_after_trim - v_marks, 0.05 * v_marks)

    # --- washer-face step: trim outside r=step_r at the head bottom ---------
    check("create_sketch step", await adapter.create_sketch("UndersidePlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, step_r / 1000.0) is None:
            raise RuntimeError("step circle failed")
    check("exit_sketch step", await adapter.exit_sketch())
    name_last_feature(adapter, "StepProfile")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "StepProfile").Select2(False, 0)
    feat = fm.FeatureCut4(
        True, True, True,                # single, Flip=outside, Dir=up
        0, 0, step_d / 1000.0, 0.0,      # blind
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False)
    if feat is None:
        raise RuntimeError("washer step cut failed")
    name_last_feature(adapter, "WasherStep")
    v_step = (G5_HW ** 2 * math.sqrt(3.0) / 2.0
              - math.pi * step_r ** 2) * step_d
    await volume_check(adapter, "washer step",
                       v_after_trim - v_marks - v_step, 0.05 * v_step)

    body_boxes = split_at_plane(adapter, "UndersidePlane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < G5_UNDERSIDE - 1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    offset_plane(adapter, "TipPlane", tip_y)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, G5_LEN / pitch + 1.0, clockwise=False,
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

    check("create_sketch runout", await adapter.create_sketch("UndersidePlane"))
    with no_sketch_inference(adapter):
        if adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, (major_r + 0.0508) / 1000.0) is None:
            raise RuntimeError("runout circle failed")
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    from solidworks_mcp.adapters.pywin32_adapter import null_callout
    part = _early_bound(adapter.currentModel, "IPartDoc")
    thread_body = None
    for b in part.GetBodies2(0, False) or []:
        b2 = _early_bound(b, "IBody2")
        box = [float(x) * 1000 for x in (b2.GetBodyBox() or [])]
        if box and min(box[1], box[4]) < G5_UNDERSIDE - 1.0:
            thread_body = str(_read_member(b2, "Name"))
    if thread_body is None:
        raise RuntimeError("no threaded shank body found")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RunoutProfile").Select2(False, 0)
    if not model.Extension.SelectByID2(thread_body, "SOLIDBODY", 0, 0, 0, True,
                                       1, null_callout(), 0):
        raise RuntimeError("runout body ref select failed")
    feat = fm.FeatureExtrusion3(
        False, False, True,
        7, 0,                            # T1 UpToBody (vendor end_cond1=7)
        0.0, 0.254 / 1000.0,
        True, False, False, False,
        math.radians(20.0), 0.0,
        False, False, False, False,
        True, False, False,
        0, 0.0, False)
    if feat is None:
        raise RuntimeError("runout extrude failed")
    name_last_feature(adapter, "ThreadRunout")

    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("92865A585", build_92865A585))

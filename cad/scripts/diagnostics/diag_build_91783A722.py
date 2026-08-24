r"""McMaster 91783A722 -- 18-8 SS slotted round head screw, 1/2" x 2-1/2".

56 TPI, partially threaded (Minimum Thread Length 38.1).  All laws from the
vendor equations + solved sketches: slot = HD*.135 wide x 1.5x deep from
the apex, band = HH*.1, Fillet3 = HH*.02 on BOTH band rims (after the
slot), tip chamfer 45 deg x 0.7P, cutter identical to the fillister law
(root flat P/8 at root_r spanning 3P/8..P/2, corners root_r+7P/16*sqrt3
@ 15P/16 and root_r+13P/32*sqrt3 @ -P/32 -- vendor Sketch6 matches to
4 decimals), head-seeded descending helix L+P tall.  The partial thread
is their Boss-Extrude1: a refill cylinder r=major from the junction down
to -(L - thread_len) plus a 30-deg-from-axis taper frustum below it
(draft1=30 through-all down; the frustum bottom disc sits at root_r,
submerged).  Fillet4 = P*.2 at the shank-underside junction, last.
Frame: junction y=0, head +y (vendor origin mid-span, junction at
z = +27.2415 = (L+HH)/2 - HH).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_91783A722.py

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
    _spherical_cap_volume,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

RH_MAJOR_R = 12.7 / 2.0
RH_LEN = 63.5
RH_HH = 9.017
RH_HEAD_R = 20.6502 / 2.0
RH_PITCH = 25.4 / 56.0     # stored 0.453571
RH_THREAD_LEN = 38.1       # Minimum Thread Length@Sketch1


async def build_91783A722(adapter, truth):
    from _common import add_line_chain
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import RevolveParameters

    major_r, head_r = RH_MAJOR_R, RH_HEAD_R
    pitch = RH_PITCH
    band = RH_HH * 0.1         # D1@Sketch1 = Head Height * .1
    dome_h = RH_HH - band
    apex_y = RH_HH
    slot_w = 2.0 * head_r * 0.135   # D1@Sketch4 = Head Diameter * .135
    slot_d = slot_w * 1.5           # D2@Sketch4
    tip_ch = 0.7 * pitch            # D2@Sketch3 = Thread Pitch * .7
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    cap_R = (head_r ** 2 + dome_h ** 2) / (2.0 * dome_h)
    fillet3_r = RH_HH * 0.02        # 0.18034
    fillet4_r = pitch * 0.2         # 0.090714
    fill_len = RH_LEN - RH_THREAD_LEN   # 25.4: unthreaded shank below head

    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    if sk_mgr.CreateCenterLine(0.0, apex_y / 1000.0, 0.0,
                               0.0, -RH_LEN / 1000.0, 0.0) is None:
        raise RuntimeError("91783 profile: CreateCenterLine failed")
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0, apex_y / 1000.0, 0.0,
            head_r / 1000.0, band / 1000.0, 0.0,
            cap_R * math.cos(ang_mid) / 1000.0,
            (yc + cap_R * math.sin(ang_mid)) / 1000.0, 0.0,
        )
        if arc is None:
            raise RuntimeError("91783 profile: dome arc failed")
        await add_line_chain(adapter, [
            (head_r, band),
            (head_r, 0.0),
            (major_r, 0.0),
            (major_r, -(RH_LEN - tip_ch)),
            (major_r - tip_ch, -RH_LEN),
            (0.0, -RH_LEN),
            (0.0, apex_y),
        ], close=False)
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_spherical_cap_volume(head_r, dome_h)
         + math.pi * head_r ** 2 * band
         + math.pi * major_r ** 2 * (RH_LEN - tip_ch)
         + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-slot_w / 2.0, apex_y + 0.5),
            (slot_w / 2.0, apex_y + 0.5),
            (slot_w / 2.0, apex_y - slot_d),
            (-slot_w / 2.0, apex_y - slot_d),
        ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    from solidworks_mcp.adapters.base import ExtrusionParameters
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=4.0 * head_r, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")

    check("band fillets", await adapter.add_fillet(
        fillet3_r, [[head_r, 0.0, 0.0], [head_r, band, 0.0]]))
    name_last_feature(adapter, "BandFillets")

    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    check("create_sketch helix seed", await adapter.create_sketch("Top"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, RH_LEN / pitch + 1.0, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (root_r + (7.0 * pitch / 16.0) * math.sqrt(3.0),
             15.0 * pitch / 16.0),
            (root_r + (13.0 * pitch / 32.0) * math.sqrt(3.0),
             -pitch / 32.0),
            (root_r, 3.0 * pitch / 8.0),
            (root_r, pitch / 2.0),
        ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name,
                     "ThreadGroove")

    # Partial-thread refill + 30-deg runout in ONE double-ended extrude,
    # exactly like the vendor's Boss-Extrude1: dir2 blind fill_len up to
    # the junction (refills the grooves, re-merges the split bodies),
    # dir1 ThroughAll down with a 30-deg shrinking draft (the taper cone
    # dives under the thread root after (major_r-root_r)*sqrt(3) and adds
    # nothing deeper).  This MUST stay one feature: authoring the refill
    # cylinder and the taper as two separate features produces the same
    # nominal geometry but a pathological merged body whose
    # IMassProperty under-integrates by 22.44 mm^3 / 10.45 mm^2 (the
    # flush-over-84-helical-crest-remnants merge), failing the volume
    # gate against a healthy vendor body.  Empirical flag inversion:
    # Ddir1=False shrinks the drafted cone here (docs say True=inward).
    from _common import _early_bound, _feature_by_name, _read_member

    offset_plane(adapter, "RefillPlane", -fill_len)
    check("create_sketch refill", await adapter.create_sketch("RefillPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("refill circle failed")
    check("exit_sketch refill", await adapter.exit_sketch())
    name_last_feature(adapter, "RefillProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "RefillProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureExtrusion3(
        False, False, True,          # double ended, dir1 down
        1, 0,                        # T1 ThroughAll, T2 blind
        0.0, fill_len / 1000.0,      # D1, D2
        True, False, False, False,   # draft on dir1, shrinking
        math.radians(30.0), 0.0,
        False, False, False, False,
        True, False, True,           # Merge, UseFeatScope, UseAutoSelect
        0, 0.0, False)
    if feat is None:
        raise RuntimeError("refill/runout extrude failed")
    name_last_feature(adapter, "ThreadRunout")

    check("underhead fillet", await adapter.add_fillet(
        fillet4_r, [[major_r, 0.0, 0.0]]))
    name_last_feature(adapter, "UnderheadFillet")

    # Vendor origin is mid-span of L+HH (apex +36.2585); their under-head
    # junction sits at z = +27.2415.  My junction y=0, head +y.
    adapter._mcm_com_map = lambda v: [
        v[1], v[2] - ((RH_LEN + RH_HH) / 2.0 - RH_HH), v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("91783A722", build_91783A722))

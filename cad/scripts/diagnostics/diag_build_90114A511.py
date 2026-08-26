r"""McMaster 90114A511 -- brass fillister head slotted screw, #4-40 x 1/4".

Same idiom family as 90280A* with its own laws (all from the vendor
equations + solved sketches): FULL spherical dome (apex ON the axis,
cap through apex + head rim), head band = HH*0.75, slot 0.9906 x 1.2192
from the apex, junction fillet HH*0.05 BEFORE the slot, tip chamfer
45 deg x 0.75P, helix seeded at the TIP ascending L+P (11 revs,
overrunning the JUNCTION by P -- harmless: the sweep is scoped to the
shank body), SYMMETRIC cutter at tip+7P/16 in air (root flat P/8 at
root_r, top 15P/16 at major+H/16), 45-deg runout cone at the junction.
Frame: head UP, junction y=0 (vendor origin is the junction too).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_90114A511.py

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
    _spherical_cap_volume,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

BF_MAJOR_R = 2.8448 / 2.0
BF_LEN = 6.35
BF_HH = 2.7178
BF_HEAD_R = 4.6482 / 2.0
BF_PITCH = 0.635
BF_SLOT_W = 0.9906   # Slot Width@Sketch1
BF_SLOT_D = 1.2192   # Slot Depth@Sketch1


async def build_90114A511(adapter, truth=None):
    from _common import add_line_chain
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    major_r, head_r = BF_MAJOR_R, BF_HEAD_R
    pitch = BF_PITCH
    band = BF_HH * 0.75
    dome_h = BF_HH - band
    apex_y = BF_HH
    tip_ch = 0.75 * pitch
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    cap_R = (head_r ** 2 + dome_h ** 2) / (2.0 * dome_h)
    fillet_r = BF_HH * 0.05

    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    if sk_mgr.CreateCenterLine(0.0, apex_y / 1000.0, 0.0,
                               0.0, -BF_LEN / 1000.0, 0.0) is None:
        raise RuntimeError("90114 profile: CreateCenterLine failed")
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
            raise RuntimeError("90114 profile: dome arc failed")
        await add_line_chain(adapter, [
            (head_r, band),
            (head_r, 0.0),
            (major_r, 0.0),
            (major_r, -(BF_LEN - tip_ch)),
            (major_r - tip_ch, -BF_LEN),
            (0.0, -BF_LEN),
            (0.0, apex_y),
        ], close=False)
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_spherical_cap_volume(head_r, dome_h)
         + math.pi * head_r ** 2 * band
         + math.pi * major_r ** 2 * (BF_LEN - tip_ch)
         + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    # Vendor Fillet1 (before the slot) rounds TWO edges: the head-OD
    # bottom rim (underside plane <-> band cylinder -- their 3.0508 torus
    # spans z 0..0.14 at r~2.32, and their underside annulus reads
    # pi*(2.188^2 - 1.4224^2), outer radius trimmed by the fillet while
    # the shank corner stays SHARP) AND the dome-to-band rim (the
    # spherical cap is not tangent to the head cylinder).
    check("junction fillet", await adapter.add_fillet(
        fillet_r, [[head_r, 0.0, 0.0], [head_r, band, 0.0]]))
    name_last_feature(adapter, "JunctionFillet")

    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (-BF_SLOT_W / 2.0, apex_y + 0.5),
            (BF_SLOT_W / 2.0, apex_y + 0.5),
            (BF_SLOT_W / 2.0, apex_y - BF_SLOT_D),
            (-BF_SLOT_W / 2.0, apex_y - BF_SLOT_D),
        ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=2.0 * BF_HEAD_R * 2.0, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")

    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # Tip-seeded ascending helix: flipped offset plane at the tip, 11 revs
    # to P past the junction.  clockwise=False here IS the vendor's
    # right-hand thread: their tip plane has normal -z with reverse=True,
    # ours +y with reverse=False, so the clockwise flag must invert
    # (proven on 93075A194, where clockwise=True left a mirror thread
    # whose sweep end slivers read +0.0575 mm^3 across every phase).
    offset_plane(adapter, "TipPlane", -BF_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, BF_LEN / pitch + 1.0, clockwise=False,
                 reversed_dir=False, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    cy = -BF_LEN - 7.0 * pitch / 16.0
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

    # 45-deg runout cone at the junction (their Boss-Extrude1, draft 45,
    # single direction, no offset -- a plain revolved frustum, merging
    # the split bodies back).
    taper_h = major_r - root_r  # 45 deg
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

    # Vendor frame: origin at the junction, head at +z per the COM sign
    # measured on the first gate run.  My junction y=0, head +y.
    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("90114A511", build_90114A511))

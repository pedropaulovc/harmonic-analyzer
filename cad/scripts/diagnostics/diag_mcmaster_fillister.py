r"""Shared recipe for the McMaster 90280A* narrow fillister head screws.

Five sizes, one parametric recipe: the vendor drives every derived number
off 5 named dims via equations, reproduced here:

- slot width = HeadDia*0.135, slot depth = width*1.5 (from the dome apex)
- head cylinder band = HeadHeight*0.8; dome = spherical cap (centre on
  the axis) through the apex and the head rim -- fully derived
- tip chamfer = 45 deg x 0.7P (tip face radius = major_r - 0.7P)
- helix = under-head junction to P past the tip (revs = L/P + 1)
- cutter (fractions of P, from their solved Sketch6): root flat at
  r = major - 0.75H spanning y 3P/8..P/2; left flank tops out at
  y 15P/16, right flank at y -P/32; 30-deg flanks.  The cutter
  overlaps the HEAD region in air -- hence the vendor's Split before
  the sweep, scoping the cut to the shank body.
- runout boss: r = major circle at the junction, 30-deg draft, P/2 deep
  (re-merges the split bodies); junction fillet r = P/10.

Frame: head UP, under-head junction at y = 0 (the stock Top Plane plays
the vendor Plane1's three roles: split plane, helix seed, runout).

Per-part entry points: ``diag_build_90280A108.py`` .. ``diag_build_90280A201.py``.
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
    thread_sweep_cut,
)

FILLISTER_SIZES = {
    # part:        (major dia, length, head height, head dia, pitch)
    "90280A108": (2.8448, 9.525, 2.7178, 4.6482, 0.635),
    "90280A194": (4.1656, 12.7, 3.9624, 6.858, 0.79375),
    "90280A196": (4.1656, 15.875, 3.9624, 6.858, 0.79375),
    "90280A199": (4.1656, 25.4, 3.9624, 6.858, 0.79375),
    "90280A201": (4.1656, 31.75, 3.9624, 6.858, 0.79375),
}


async def build_fillister(adapter, part_no: str):
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from diag_mcmaster_lib import no_sketch_inference, split_at_plane

    major_d, length, hh, hd, pitch = FILLISTER_SIZES[part_no]
    major_r = major_d / 2.0
    head_r = hd / 2.0
    band = hh * 0.8            # head cylinder height
    dome_h = hh - band         # spherical-cap height
    slot_w = hd * 0.135
    slot_d = slot_w * 1.5
    tip_ch = 0.7 * pitch
    h_sharp = pitch * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    revs = length / pitch + 1.0
    apex_y = band + dome_h
    # Spherical-cap centre on the axis through apex (0, apex_y) and rim
    # (head_r, band):  R - dome_h = sqrt(R^2 - head_r^2).
    cap_R = (head_r ** 2 + dome_h ** 2) / (2.0 * dome_h)

    # --- revolve profile ----------------------------------------------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    if sk_mgr.CreateCenterLine(0.0, hh / 1000.0, 0.0,
                               0.0, -length / 1000.0, 0.0) is None:
        raise RuntimeError("fillister profile: CreateCenterLine failed")
    # Dome arc as a THREE-POINT arc under no_sketch_inference.  Two traps,
    # both hit here: inference snapping is PIXEL-based (view-dependent)
    # and silently re-solved scripted arcs (centre snapped to the
    # centreline midpoint; an endpoint snapped horizontal with the apex);
    # and CreateArc's direction flag resolved INCONSISTENTLY across the
    # family sizes (A108's dome built fine, A194's identical-topology arc
    # made the revolve fail).  The mid-point form pins the bulge side with
    # no direction flag.
    yc = apex_y - cap_R
    ang_mid = (math.pi / 2.0 + math.atan2(band - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0, apex_y / 1000.0, 0.0,             # start: dome apex
            head_r / 1000.0, band / 1000.0, 0.0,   # end: head rim
            cap_R * math.cos(ang_mid) / 1000.0,    # mid, on the sphere
            (yc + cap_R * math.sin(ang_mid)) / 1000.0, 0.0,
        )
        if arc is None:
            raise RuntimeError("fillister profile: dome arc failed")
        await add_line_chain(adapter, [
            (head_r, band),
            (head_r, 0.0),
            (major_r, 0.0),
            (major_r, -(length - tip_ch)),
            (major_r - tip_ch, -length),
            (0.0, -length),
            (0.0, apex_y),
        ], close=False)
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_spherical_cap_volume(head_r, dome_h)
         + math.pi * head_r ** 2 * band
         + math.pi * major_r ** 2 * (length - tip_ch)
         + _rev_frustum(tip_ch, major_r, major_r - tip_ch))
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- driver slot (from the dome apex) -----------------------------------
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
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=2.0 * hd, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")

    # --- split at the under-head junction (scopes the sweep) ---------------
    body_boxes = split_at_plane(adapter, "Top Plane", "HeadSplit")
    shank_name = None
    for b in body_boxes:
        box = b["box_mm"]
        if box and box[1] < -1.0:  # extends below the junction
            shank_name = b["name"]
    if not shank_name:
        raise RuntimeError("split produced no shank body")
    _telemetry.info(f"shank body: {shank_name}")

    # --- helix (junction -> P past the tip) ---------------------------------
    check("create_sketch helix seed", await adapter.create_sketch("Top"))
    seed = adapter.currentSketchManager.CreateCircleByRadius(
        0.0, 0.0, 0.0, major_r / 1000.0)
    if seed is None:
        raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, pitch, revs, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    # --- thread groove -------------------------------------------------------
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

    # --- runout boss + junction fillet (re-merges the bodies) ---------------
    # The vendor's one Boss-Extrude1 (FromType=swStartOffset P/2, both
    # directions, 30-deg draft) decomposes into: a straight cylinder fill
    # from the junction down to -P/2, then a 30-deg taper cone below it
    # until the cone falls under the thread root (adds nothing deeper).
    check("create_sketch runout fill", await adapter.create_sketch("Top"))
    if adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0) is None:
        raise RuntimeError("runout fill circle failed")
    check("exit_sketch runout fill", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutFillProfile")
    check("runout fill", await adapter.create_extrusion(ExtrusionParameters(
        depth=pitch / 2.0, reverse_direction=True)))
    name_last_feature(adapter, "RunoutFill")

    # Taper as a revolved frustum: the adapter's extrusion path hardcodes
    # Dchk1=False, so its draft_angle never applies.  The frustum's bottom
    # disc sits at the thread root radius, fully submerged -- no face.
    taper_h = (major_r - root_r) * math.sqrt(3.0)  # 30 deg from the axis
    check("create_sketch runout taper", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    if sk2.CreateCenterLine(0.0, -pitch / 2.0 / 1000.0, 0.0,
                            0.0, (-pitch / 2.0 - taper_h) / 1000.0,
                            0.0) is None:
        raise RuntimeError("runout taper: CreateCenterLine failed")
    with no_sketch_inference(adapter):
        await add_line_chain(adapter, [
            (0.0, -pitch / 2.0),
            (major_r, -pitch / 2.0),
            (root_r, -pitch / 2.0 - taper_h),
            (0.0, -pitch / 2.0 - taper_h),
        ])
    check("exit_sketch runout taper", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutTaperProfile")
    check("runout taper", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "RunoutTaper")

    check("junction fillet", await adapter.add_fillet(
        pitch / 10.0, [[major_r, 0.0, 0.0]]))
    name_last_feature(adapter, "JunctionFillet")

    # Vendor frame: axis z with the head at +z (COM sits toward the heavy
    # head), origin mid-span, so their under-head junction is at
    # z = (L - HH)/2 -- exactly where their helix seed plane resolved
    # (z = +3.4036 on A108).  My junction is y = 0.
    adapter._mcm_com_map = lambda v: [v[1], v[2] - (length - hh) / 2.0, v[0]]

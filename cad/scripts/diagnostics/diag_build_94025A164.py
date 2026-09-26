r"""McMaster 94025A164 -- 18-8 SS slotted cup-tip set screw, #10-32 x 3/8".

Same vendor recipe as 94025A150 (see ``diag_build_94025A150.py``):
through-axis revolve profile (tip cone + 45 deg cup cone + 55 deg slot-end
chamfer) -> slot Cut-Extrude (ThroughAllBoth) -> helix (seeded at the slot
face, height L+P = 13 revs, start angle 90 deg) -> thread Cut-Sweep (UN
cutter capped at 15P/16, centred 7P/16 past the face).  Every constant
below is read off ``cad/out/reports/mcmaster-94025A164-dump.json``.

Cup depth (c10 for the cone-tip adjuster): Sketch2 Line7 runs from the cup
rim (r 1.2065 at the end face) to the apex on the axis 1.2065 inside it.

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_94025A164.py

Part of the McMaster replica fleet -- see ``diag_build_mcmaster.py``.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    check,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    bodies,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    replica_main,
    thread_sweep_cut_modern,
)


def _strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


SS_MAJOR_R = 2.413        # Screw Size Decimal Equivalent@Sketch1 / 2
SS_LEN = 9.525            # Length@Sketch1 (full, slot face to cup rim)
SS_HALF = SS_LEN / 2.0    # vendor origin sits mid-length; mine too
SS_PITCH = 0.79375        # Pitch@Sketch1 (#10-32: 25.4/32)
SS_REVS = 14.0            # vendor 13 from the face; +1 lead-in rev in air
SS_CHAM_R = 2.155222      # slot-end rim chamfer inner radius (Sketch2 Line1)
SS_CHAM_H = 4.7625 - 4.582002  # its axial extent (0.180498)
SS_TIP_R = 1.2065         # tip cone end radius = cup rim radius (Sketch2)
SS_CONE_Y = 3.556         # tip cone start / cup apex |y| (Sketch2 Line7)
SS_SLOT_W = 0.804333      # D3@Sketch1 (slot width = major / 6)
SS_SLOT_D = 0.79375       # Drive Depth@Sketch1 (slot depth = P)
# Thread cutter (vendor Sketch7, exact): UN V capped at 15P/16, root flat
# P/8, centred 7P/16 past the slot-end face in air.
SS_CUT_TOP_R = 2.455963
SS_CUT_TOP_W = 0.744141   # 15P/16
SS_CUT_ROOT_R = 1.897444  # major_r - 0.75 * (P*sqrt(3)/2)
SS_CUT_ROOT_W = 0.099219  # P/8
SS_CUT_CY = SS_HALF + SS_PITCH + 7.0 * SS_PITCH / 16.0  # 7P/16 past the raised start
# The cone-tip adjuster's cup depth: apex to rim, 45 deg.
SS_CUP_DEPTH = SS_HALF - SS_CONE_Y
assert abs(SS_CUP_DEPTH - SS_TIP_R) < 1e-9


async def build_94025A164(adapter, truth=None):
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    # --- revolve profile (vendor Sketch2 mapped (r, y) = (y_v, -x_v)) -----
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        axis = sk_mgr.CreateCenterLine(0.0, SS_HALF / 1000.0, 0.0,
                                       0.0, -SS_HALF / 1000.0, 0.0)
        if axis is None:
            raise RuntimeError("set-screw profile: CreateCenterLine failed")
    await add_line_chain(adapter, [
        (SS_CHAM_R, SS_HALF),                    # slot-end rim
        (SS_MAJOR_R, SS_HALF - SS_CHAM_H),       # chamfer -> OD
        (SS_MAJOR_R, -SS_CONE_Y),                # OD -> tip cone
        (SS_TIP_R, -SS_HALF),                    # tip cone end (cup rim)
        (0.0, -SS_CONE_Y),                       # cup cone to the axis
        (0.0, SS_HALF),                          # axis
    ])
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check("revolve body", await adapter.create_revolve(
        RevolveParameters(angle=360.0, is_cut=False)))
    name_last_feature(adapter, "Body")
    v = (_rev_frustum(SS_CHAM_H, SS_MAJOR_R, SS_CHAM_R)
         + math.pi * SS_MAJOR_R ** 2 * (SS_LEN - SS_CHAM_H - (SS_HALF - SS_CONE_Y))
         + _rev_frustum(SS_HALF - SS_CONE_Y, SS_MAJOR_R, SS_TIP_R)
         - _rev_frustum(SS_HALF - SS_CONE_Y, SS_TIP_R, 0.0))
    volume = await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- driver slot (vendor Cut-Extrude1: ThroughAllBoth) ----------------
    check("create_sketch slot", await adapter.create_sketch("Front"))
    await add_line_chain(adapter, [
        (-SS_SLOT_W / 2.0, SS_HALF),
        (SS_SLOT_W / 2.0, SS_HALF),
        (SS_SLOT_W / 2.0, SS_HALF - SS_SLOT_D),
        (-SS_SLOT_W / 2.0, SS_HALF - SS_SLOT_D),
    ])
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    # Vendor end condition is ThroughAllBoth, but the adapter's cut path
    # passes Sd=True for ThroughAll (single-direction), so a midplane
    # blind cut deeper than the diameter stands in -- same geometry.
    check("cut slot", await adapter.create_cut_extrude(ExtrusionParameters(
        depth=6.0, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")
    # Slot volume: strip across the section, integrated over the chamfer
    # taper (the slot depth 0.794 reaches into the chamfer band 0.180).
    steps = 200
    v_slot = 0.0
    for i in range(steps):
        y = SS_HALF - SS_SLOT_D * (i + 0.5) / steps
        r = (SS_MAJOR_R if y <= SS_HALF - SS_CHAM_H else
             SS_MAJOR_R + (SS_CHAM_R - SS_MAJOR_R)
             * (y - (SS_HALF - SS_CHAM_H)) / SS_CHAM_H)
        v_slot += _strip_area(r, SS_SLOT_W) * SS_SLOT_D / steps
    volume = await volume_check(adapter, "driver slot", volume - v_slot,
                                0.02 * v_slot)

    # --- helix ------------------------------------------------------------
    # Seeded one pitch above the slot face, descending 14 revs to one pitch
    # PAST the cup rim (vendor: at the face, 13 revs = L + P; the overrun fades the groove out
    # over the cup cone).  The cutter sits 7P/16 ABOVE the path start in
    # air -- the proven 91829A560 configuration; with the cutter at the
    # path's FAR end instead, InsertCutSwept5 returns None.
    offset_plane(adapter, "ThreadTopPlane", SS_HALF + SS_PITCH)
    check("create_sketch helix seed",
          await adapter.create_sketch("ThreadTopPlane"))
    with no_sketch_inference(adapter):
        seed = adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, SS_MAJOR_R / 1000.0)
        if seed is None:
            raise RuntimeError("helix seed circle failed")
    insert_helix(adapter, SS_PITCH, SS_REVS, clockwise=True,
                 reversed_dir=True, start_angle_rad=math.pi / 2.0,
                 feature_name="ThreadHelix")

    # --- thread groove (vendor Cut-Sweep1, cutter coords exact) -----------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    await add_line_chain(adapter, [
        (SS_CUT_TOP_R, SS_CUT_CY + SS_CUT_TOP_W / 2.0),
        (SS_CUT_ROOT_R, SS_CUT_CY + SS_CUT_ROOT_W / 2.0),
        (SS_CUT_ROOT_R, SS_CUT_CY - SS_CUT_ROOT_W / 2.0),
        (SS_CUT_TOP_R, SS_CUT_CY - SS_CUT_TOP_W / 2.0),
    ])
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    bl = bodies(adapter)
    if len(bl) != 1:
        raise RuntimeError(f"expected 1 body before thread cut, got {len(bl)}")
    thread_sweep_cut_modern(adapter, "ThreadCutter", "ThreadHelix",
                            "ThreadGroove")

    # Vendor slot end is +z in their frame (COM-verified: the cup end
    # loses mass to the cone+cup, so mass biases toward the slot; the
    # 94025A164 dump COM is +0.156 z).
    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("94025A164", build_94025A164))

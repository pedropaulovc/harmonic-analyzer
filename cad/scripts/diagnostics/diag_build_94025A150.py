r"""McMaster 94025A150 -- 18-8 SS slotted cup-tip set screw, 5/16"-18 x 1/2".

Vendor tree: through-axis revolve profile (integral tip cone + cup cone +
slot-end chamfer) -> slot Cut-Extrude (ThroughAllBoth) -> helix (seeded at
the cup tip, height L+..., start angle 90 deg) -> thread Cut-Sweep (UN
cutter capped at 15P/16, centred 7P/16 past the slot-end face in air,
scoped to the body; no Split -- the cutter never crosses other geometry).
Frame: replica axial = +y with the SLOT end up (vendor axial = z, cup at
+z; map my (x,y,z) = (vendor y, -vendor z, vendor x)).

Run standalone (SolidWorks open)::

    uv run python cad\scripts\diagnostics\diag_build_94025A150.py

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
from diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    bodies,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut_modern,
)


def _strip_area(r: float, w: float) -> float:
    """Plan area of a width-w strip across a radius-r circle (exact)."""
    h = w / 2.0
    return 2.0 * (h * math.sqrt(r * r - h * h) + r * r * math.asin(h / r))


SS_MAJOR_R = 3.9751       # Screw Size Decimal Equivalent@Sketch1 / 2
SS_LEN = 12.7             # Length@Sketch1 (full, slot face to cup rim)
SS_HALF = SS_LEN / 2.0    # vendor origin sits mid-length; mine too
SS_PITCH = 1.411111       # Pitch@Sketch1 (5/16-18: 25.4/18)
SS_REVS = 11.0            # vendor 10 from the face; +1 lead-in rev in air
SS_CHAM_R = 3.516828      # slot-end rim chamfer inner radius (Sketch2)
SS_CHAM_H = 6.35 - 6.029115  # its axial extent (0.320885)
SS_TIP_R = 1.98755        # tip cone end radius = cup rim radius (Sketch2)
SS_CONE_Y = 4.36245       # tip cone start / cup apex |y| (Sketch2)
SS_SLOT_W = 1.325033      # D3@Sketch1 (slot width)
SS_SLOT_D = 1.411111      # Drive Depth@Sketch1 (slot depth)
# Thread cutter (vendor Sketch7, exact): UN V capped at 15P/16, root flat
# P/8, centred 7P/16 past the slot-end face in air.
SS_CUT_TOP_R = 4.051479
SS_CUT_TOP_W = 1.322917   # 15P/16
SS_CUT_ROOT_R = 3.058556  # major_r - 0.75 * (P*sqrt(3)/2)
SS_CUT_ROOT_W = 0.176389  # P/8
SS_CUT_CY = SS_HALF + SS_PITCH + 7.0 * SS_PITCH / 16.0  # 7P/16 past the raised start


async def build_94025A150(adapter, truth):
    from _common import add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    # --- revolve profile (vendor Sketch2 mapped (r, y) = (y_v, -x_v)) -----
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
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
        depth=12.0, both_directions=True)))
    name_last_feature(adapter, "DriverSlot")
    # Slot volume: strip across the section, integrated over the chamfer
    # taper (the slot depth 1.411 reaches into the chamfer band 0.321).
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
    # Seeded AT the slot face, descending 10 revs to one pitch PAST the
    # cup rim (height 14.111 = L + P; the overrun fades the groove out
    # over the cup cone).  The cutter sits 7P/16 ABOVE the path start in
    # air -- the proven 91829A560 configuration; with the cutter at the
    # path's FAR end instead, InsertCutSwept5 returns None.
    offset_plane(adapter, "ThreadTopPlane", SS_HALF + SS_PITCH)
    check("create_sketch helix seed",
          await adapter.create_sketch("ThreadTopPlane"))
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
    # loses ~49 mm^3 to the cone+cup, so mass biases toward the slot).
    adapter._mcm_com_map = lambda v: [v[1], v[2], v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("94025A150", build_94025A150))

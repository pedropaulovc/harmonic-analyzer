r"""McMaster 91255A148 -- black-oxide alloy steel button head SHCS, #6-32 x 1/2".

Modelled from the catalog dimensions only; no vendor SLDPRT is harvested and
none may be committed (cad/references/mcmaster/README.md).  Source: the U30
cone-tip attachment handoff, which read the product page on 2026-09-23 (rule-12
W22): head Ø0.262 in (6.65) x 0.073 in (1.85), 5/64 hex drive, fully threaded,
1/2 in (12.7) under the head.  A re-read on 2026-09-24 was refused (HTTP 403).

Laws (assumptions, flagged where the catalog is silent):

- head: flat bearing face, a short cylindrical edge band of 0.2 x head height
  (assumed; ASME B18.3 draws a small edge), and a spherical dome through the
  band's rim and the apex.
- drive: 5/64 hex socket, flat-bottomed, with full hex depth
  ``SOCKET_KEY_ENGAGEMENT`` at the corners.  0.028 in is the ASME B18.3 key
  engagement minimum for a #6 button head (assumed from the standard; not on
  the catalog page).  The socket stays inside the head, so no fit reads it.
- shank and thread: the 90280A* fillister family's thread laws unchanged
  (``diag_mcmaster_fillister``): 45 deg x 0.7P tip chamfer, helix from the
  under-head junction to P past the tip, the vendor-derived UN cutter, the
  split that scopes the sweep to the shank, and the runout boss + P/10
  junction fillet.  They are copied, not imported, so this recipe cannot
  re-key the fillister fleet.

Frame: head UP, under-head junction at y = 0 (the fillister frame).

Run standalone (SolidWorks open; there is no vendor truth to compare)::

    uv run python cad\scripts\diagnostics\diag_build_91255A148.py
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
from _hole_spec import THREAD_MAJOR_MM  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    _spherical_cap_volume,
    insert_helix,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)

IN = 25.4
MAJOR_DIA = THREAD_MAJOR_MM["#6-32"]  # 3.505
PITCH = IN / 32.0
LENGTH = 0.5 * IN  # under the head, fully threaded
HEAD_DIA = 0.262 * IN  # 6.6548
HEAD_H = 0.073 * IN  # 1.8542
HEAD_BAND = 0.2 * HEAD_H  # assumed edge band
HEX_AF = 5.0 / 64.0 * IN  # 1.984
SOCKET_KEY_ENGAGEMENT = 0.028 * IN  # 0.711, ASME B18.3 #6 button head (assumed)


def dome_radius() -> float:
    """Sphere radius of the dome through the band rim and the apex."""
    rim = HEAD_DIA / 2.0
    rise = HEAD_H - HEAD_BAND
    return (rim**2 + rise**2) / (2.0 * rise)


def dome_height_at(r: float) -> float:
    """Height of the dome surface above the bearing face at radius ``r``."""
    big_r = dome_radius()
    return HEAD_H - big_r + math.sqrt(big_r**2 - r**2)


def socket_floor_y() -> float:
    """Flat socket floor: full hex depth measured at the hex corners."""
    corner_r = HEX_AF / math.sqrt(3.0)
    return dome_height_at(corner_r) - SOCKET_KEY_ENGAGEMENT


def socket_volume(steps: int = 240) -> float:
    """Hex prism from the floor up to the dome (midpoint grid over the hex)."""
    corner_r = HEX_AF / math.sqrt(3.0)
    floor = socket_floor_y()
    half_af = HEX_AF / 2.0
    cell = 2.0 * corner_r / steps
    total = 0.0
    for i in range(steps):
        x = -corner_r + (i + 0.5) * cell
        for j in range(steps):
            y = -corner_r + (j + 0.5) * cell
            # Flats at |y| = AF/2; the slanted flats at |x| sin60 + |y| cos60.
            if abs(y) > half_af:
                continue
            if abs(x) * math.sqrt(3.0) / 2.0 + abs(y) / 2.0 > half_af:
                continue
            total += (dome_height_at(math.hypot(x, y)) - floor) * cell * cell
    return total


if socket_floor_y() <= HEAD_BAND:
    raise ValueError("91255A148 socket floor falls into the head's edge band")


async def build_91255A148(adapter, truth=None):
    from _common import _feature_by_name, _early_bound, _read_member, add_line_chain
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters
    from diagnostics.diag_mcmaster_lib import no_sketch_inference, split_at_plane

    major_r = MAJOR_DIA / 2.0
    head_r = HEAD_DIA / 2.0
    dome_h = HEAD_H - HEAD_BAND
    cap_r = dome_radius()
    tip_ch = 0.7 * PITCH
    h_sharp = PITCH * math.sqrt(3.0) / 2.0
    root_r = major_r - 0.75 * h_sharp
    revs = LENGTH / PITCH + 1.0

    # --- revolve profile (the fillister's, with a button dome) --------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(0.0, HEAD_H / 1000.0, 0.0, 0.0, -LENGTH / 1000.0, 0.0)
            is None
        ):
            raise RuntimeError("button head profile: CreateCenterLine failed")
    # Three-point dome arc under no_sketch_inference: the fillister's proven
    # form (inference snapping and CreateArc's direction flag both misfire).
    yc = HEAD_H - cap_r
    ang_mid = (math.pi / 2.0 + math.atan2(HEAD_BAND - yc, head_r)) / 2.0
    with no_sketch_inference(adapter):
        arc = sk_mgr.Create3PointArc(
            0.0,
            HEAD_H / 1000.0,
            0.0,  # start: dome apex
            head_r / 1000.0,
            HEAD_BAND / 1000.0,
            0.0,  # end: band rim
            cap_r * math.cos(ang_mid) / 1000.0,  # mid, on the sphere
            (yc + cap_r * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError("button head profile: dome arc failed")
        await add_line_chain(
            adapter,
            [
                (head_r, HEAD_BAND),
                (head_r, 0.0),
                (major_r, 0.0),
                (major_r, -(LENGTH - tip_ch)),
                (major_r - tip_ch, -LENGTH),
                (0.0, -LENGTH),
                (0.0, HEAD_H),
            ],
            close=False,
        )
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "BodyProfile")
    check(
        "revolve body",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "Body")
    v = (
        _spherical_cap_volume(head_r, dome_h)
        + math.pi * head_r**2 * HEAD_BAND
        + math.pi * major_r**2 * (LENGTH - tip_ch)
        + _rev_frustum(tip_ch, major_r, major_r - tip_ch)
    )
    volume = await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- hex socket: blind cut down from the apex plane ---------------------
    # 92865A585's grade-mark idiom: a sketch on a Top-offset plane at the head
    # top, FeatureCut4 single-direction, default direction, blind -- proven to
    # cut down into the head.
    offset_plane(adapter, "HeadTopPlane", HEAD_H)
    check("create_sketch socket", await adapter.create_sketch("HeadTopPlane"))
    flat = HEX_AF / 2.0
    corner = HEX_AF / math.sqrt(3.0)
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (0.0, corner),
                (-flat, corner / 2.0),
                (-flat, -corner / 2.0),
                (0.0, -corner),
                (flat, -corner / 2.0),
                (flat, corner / 2.0),
            ],
        )
    check("exit_sketch socket", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketProfile")
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    model.ClearSelection2(True)
    _feature_by_name(adapter, "SocketProfile").Select2(False, 0)
    fm = _early_bound(_read_member(model, "FeatureManager"), "IFeatureManager")
    feat = fm.FeatureCut4(
        True, False, False,  # single, no flip, default dir
        0, 0, (HEAD_H - socket_floor_y()) / 1000.0, 0.0,  # blind to the floor
        False, False, False, False, 0.0, 0.0,
        False, False, False, False,
        False, False, True, False, False, False,
        0, 0.0, False, False,
    )
    if feat is None:
        raise RuntimeError("hex socket cut failed")
    name_last_feature(adapter, "HexSocket")
    v_socket = socket_volume()
    await volume_check(adapter, "hex socket", volume - v_socket, 0.03 * v_socket)

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
    with no_sketch_inference(adapter):
        seed = adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, major_r / 1000.0
        )
        if seed is None:
            raise RuntimeError("helix seed circle failed")
    insert_helix(
        adapter,
        PITCH,
        revs,
        clockwise=True,
        reversed_dir=True,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- thread groove (the fillister family's cutter) ----------------------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (root_r + (7.0 * PITCH / 16.0) * math.sqrt(3.0), 15.0 * PITCH / 16.0),
                (root_r + (13.0 * PITCH / 32.0) * math.sqrt(3.0), -PITCH / 32.0),
                (root_r, 3.0 * PITCH / 8.0),
                (root_r, PITCH / 2.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(adapter, "ThreadCutter", "ThreadHelix", shank_name, "ThreadGroove")

    # --- runout boss + junction fillet (re-merges the bodies) ---------------
    check("create_sketch runout fill", await adapter.create_sketch("Top"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, major_r / 1000.0
            )
            is None
        ):
            raise RuntimeError("runout fill circle failed")
    check("exit_sketch runout fill", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutFillProfile")
    check(
        "runout fill",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PITCH / 2.0, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "RunoutFill")

    taper_h = (major_r - root_r) * math.sqrt(3.0)  # 30 deg from the axis
    check("create_sketch runout taper", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0, -PITCH / 2.0 / 1000.0, 0.0, 0.0, (-PITCH / 2.0 - taper_h) / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError("runout taper: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, -PITCH / 2.0),
                (major_r, -PITCH / 2.0),
                (root_r, -PITCH / 2.0 - taper_h),
                (0.0, -PITCH / 2.0 - taper_h),
            ],
        )
    check("exit_sketch runout taper", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutTaperProfile")
    check(
        "runout taper",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "RunoutTaper")

    check(
        "junction fillet", await adapter.add_fillet(PITCH / 10.0, [[major_r, 0.0, 0.0]])
    )
    name_last_feature(adapter, "JunctionFillet")

    # No vendor frame is known; assume the fillister family's (axis z, head
    # +z, origin mid-overall) for any future native comparison.
    adapter._mcm_com_map = lambda v: [v[1], v[2] - (LENGTH - HEAD_H) / 2.0, v[0]]


if __name__ == "__main__":
    sys.exit(replica_main("91255A148", build_91255A148))

r"""McMaster 90325A174 -- 18-8 stainless precision shoulder screw, hex socket,
shoulder Ø3/16 x 1/2, 8-32 x 3/8 (MHA-VN-041, the transgear pivot screw).

Catalogue-only: the live page (read 2026-10-14) gives the shoulder, thread,
head envelope and 3/32 hex drive; its CAD download was refused, so there is
no vendor model and no replica gate.  ASME B18.3-2012 Table 13 (hexagon
socket head shoulder screws, 3/16 row) bounds what the page omits: the
socket's key engagement, the head-rim chamfer and the thread neck.  Every
number is imported from ``_mcmaster_90325a174``; none is typed
here.

The construction is the retired 91829A205 recipe's (the 91829A560 family's
replica-gated feature order) with the slot replaced by a hex socket:

1.  Base solid: head HEAD_DIA x HEAD_H up from the under-head shoulder face
    (y = 0); shoulder SHOULDER_DIA x SHOULDER_LEN and thread shank
    THREAD_MAJOR x THREAD_LEN down from it.
2.  Thread neck under the shoulder's END face: a R NECK_FILLET_R
    quarter-fillet into a Ø NECK_DIA land, flat to NECK_FLAT_END below the end
    face, then a 45 deg flank back to the major, reached FULL_THREAD_START
    below it.
3.  Hex socket SOCKET_AF across flats, SOCKET_DEPTH deep, cut down from the
    head top.
4.  Helix: seeded on the tip plane, ascending, pitch PITCH over THREAD_LEN.
5.  Chamfers, 45 deg: the head rim HEAD_CHAMFER and the thread start
    TIP_CHAMFER.
6.  Split at the neck's land bottom, so the thread sweep is scoped to the
    tail and cannot touch the shoulder or the fillet.
7.  Thread groove: the UN 60 deg V truncated to a P/8 root flat at
    r = major - 0.75 H and capped at a 15P/16 top width, placed 7P/16 past the
    tip in air, swept along the helix, tail-scoped.
8.  Combine unions the bodies back.

Class 2A and the shoulder's tolerances are not modelled (nominal sizes,
nominal UN cutter).

Frame: axis +Y, head up, the under-head shoulder face at y = 0 (Top Plane).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _stock_recipe import stock_recipe  # noqa: E402

import _telemetry  # noqa: E402

if __package__:
    from . import _script_paths  # noqa: F401
else:
    import _script_paths  # noqa: F401
from _check import check  # noqa: E402
from _extrude import extrude_at_offset  # noqa: E402
from _feature_tree import name_last_feature  # noqa: E402
from _part_checks import volume_check  # noqa: E402
from _sketch import add_line_chain  # noqa: E402
from _sketch_circle import define_circle  # noqa: E402
from _shoulder_screw_geometry import _undercut_volume  # noqa: E402
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    combine_union,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    split_at_plane,
    thread_sweep_cut,
)
from _mcmaster_90325a174 import (  # noqa: E402
    FULL_THREAD_START,
    HEAD_CHAMFER,
    HEAD_DIA,
    HEAD_H,
    NECK_DIA,
    NECK_FILLET_R,
    NECK_FLAT_END,
    PITCH,
    SHOULDER_DIA,
    SHOULDER_LEN,
    SKU,
    SOCKET_AF,
    SOCKET_DEPTH,
    THREAD_LEN,
    THREAD_MAJOR,
    TIP_CHAMFER,
)

PART_NO = SKU

UNDERHEAD_LEN = SHOULDER_LEN + THREAD_LEN
MAJOR_R = THREAD_MAJOR / 2.0
SHOULDER_R = SHOULDER_DIA / 2.0
NECK_R = NECK_DIA / 2.0
NECK_LAND = NECK_FLAT_END - NECK_FILLET_R
REVS = THREAD_LEN / PITCH  # tip to the shoulder's end face
# A regular hexagon's corner stands AF / sqrt(3) from its centre.
SOCKET_CORNER_R = SOCKET_AF / math.sqrt(3.0)
SOCKET_VOLUME = math.sqrt(3.0) / 2.0 * SOCKET_AF**2 * SOCKET_DEPTH

# Neck heights in the part frame.
Y_SHOULDER_END = -SHOULDER_LEN
Y_LAND_TOP = Y_SHOULDER_END - NECK_FILLET_R
Y_LAND_BOT = Y_SHOULDER_END - NECK_FLAT_END  # also the split plane

# The UN thread cutter.
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_R - 0.75 * H_SHARP
ROOT_FLAT = PITCH / 8.0
CUT_TOP_W = 15.0 * PITCH / 16.0
CUT_TOP_R = ROOT_R + (CUT_TOP_W - ROOT_FLAT) / 2.0 * math.sqrt(3.0)
CUT_CENTRE_Y = -UNDERHEAD_LEN - 7.0 * PITCH / 16.0  # past the tip, in air

if not SOCKET_DEPTH < HEAD_H:
    raise ValueError(f"{PART_NO}: the hex socket falls through the head")
if not SOCKET_CORNER_R < HEAD_DIA / 2.0 - HEAD_CHAMFER:
    raise ValueError(f"{PART_NO}: the hex socket breaks into the head-rim chamfer")
if not CUT_TOP_R > MAJOR_R:
    raise ValueError(f"{PART_NO}: the thread cutter does not clear the major")
# The fillet runs radially off the end face and lands tangent on the neck,
# so its radius IS the major-to-land rise; _undercut_volume assumes it.
if not math.isclose(NECK_FILLET_R, MAJOR_R - NECK_R, abs_tol=1e-6):
    raise ValueError(f"{PART_NO}: neck fillet R != major-to-land rise")
if not (0.0 < NECK_LAND and FULL_THREAD_START < THREAD_LEN - TIP_CHAMFER):
    raise ValueError(f"{PART_NO}: the neck leaves no land or no full thread")


def _tail_body(boxes: list[dict]) -> str:
    """The one body the split left wholly below the neck's land bottom."""
    below = [
        b["name"] for b in boxes if b["box_mm"] and b["box_mm"][4] <= Y_LAND_BOT + 0.01
    ]
    if len(below) != 1:
        raise RuntimeError(f"{PART_NO}: split left {below!r} below the neck land")
    return below[0]


@stock_recipe("90325A174", threaded=True)
async def build_90325A174(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    # --- base solid -----------------------------------------------------------
    check("create_sketch head", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    check(
        "extrude head",
        await adapter.create_extrusion(ExtrusionParameters(depth=HEAD_H)),
    )
    v = math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_H
    volume = await volume_check(adapter, "head", v, 0.005 * v)

    check("create_sketch shoulder", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, SHOULDER_R, "shoulder")
    check("exit_sketch shoulder", await adapter.exit_sketch())
    name_last_feature(adapter, "ShoulderProfile")
    extrude_at_offset(adapter, SHOULDER_LEN, -SHOULDER_LEN)
    v = math.pi * SHOULDER_R**2 * SHOULDER_LEN
    volume = await volume_check(adapter, "shoulder", volume + v, 0.005 * v)

    check("create_sketch shank", await adapter.create_sketch("Top"))
    await define_circle(adapter, 0.0, 0.0, MAJOR_R, "thread shank")
    check("exit_sketch shank", await adapter.exit_sketch())
    name_last_feature(adapter, "ShankProfile")
    extrude_at_offset(adapter, THREAD_LEN, -UNDERHEAD_LEN)
    v = math.pi * MAJOR_R**2 * THREAD_LEN
    volume = await volume_check(adapter, "thread shank", volume + v, 0.005 * v)

    # --- thread neck (fillet + land + 45 deg flank) -----------------------------
    check("create_sketch neck", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        axis = sk_mgr.CreateCenterLine(
            0.0, Y_SHOULDER_END / 1000.0, 0.0, 0.0, -UNDERHEAD_LEN / 1000.0, 0.0
        )
        if axis is None:
            raise RuntimeError(f"{PART_NO} neck: CreateCenterLine failed")
    prev_db = bool(sk_mgr.AddToDB)
    sk_mgr.AddToDB = True
    try:
        # quarter-fillet from the end face at the major down to the land top
        arc = sk_mgr.CreateArc(
            MAJOR_R / 1000.0,
            Y_LAND_TOP / 1000.0,
            0.0,
            MAJOR_R / 1000.0,
            Y_SHOULDER_END / 1000.0,
            0.0,
            NECK_R / 1000.0,
            Y_LAND_TOP / 1000.0,
            0.0,
            1,
        )
        if arc is None:
            raise RuntimeError(f"{PART_NO} neck: fillet arc failed")
        await add_line_chain(
            adapter,
            [
                (NECK_R, Y_LAND_TOP),
                (NECK_R, Y_LAND_BOT),
                (SHOULDER_R, Y_LAND_BOT - (SHOULDER_R - NECK_R)),
                (SHOULDER_R, Y_SHOULDER_END),
                (MAJOR_R, Y_SHOULDER_END),
            ],
            close=False,
        )
    finally:
        sk_mgr.AddToDB = prev_db
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadNeckProfile")
    check(
        "revolve-cut neck",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=True)),
    )
    name_last_feature(adapter, "ThreadNeck")
    v = _undercut_volume(MAJOR_R, NECK_R, NECK_LAND)
    volume = await volume_check(adapter, "thread neck", volume - v, 0.01 * v)

    # --- hex socket, blind down from the head top --------------------------------
    offset_plane(adapter, "HeadTop", HEAD_H)
    check("create_sketch socket", await adapter.create_sketch("HeadTop"))
    flat = SOCKET_AF / 2.0
    corner = SOCKET_CORNER_R
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
    check(
        "cut hex socket",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SOCKET_DEPTH)),
    )
    name_last_feature(adapter, "HexSocket")
    volume = await volume_check(
        adapter, "hex socket", volume - SOCKET_VOLUME, 0.02 * SOCKET_VOLUME
    )

    # --- helix (tip-seeded, ascending) -------------------------------------------
    # 91829A560's proven flags in this frame: Clockwised=False is a right-hand
    # thread, start azimuth +X on the Front plane's cutter.
    offset_plane(adapter, "TipPlane", -UNDERHEAD_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        seed = adapter.currentSketchManager.CreateCircleByRadius(
            0.0, 0.0, 0.0, MAJOR_R / 1000.0
        )
        if seed is None:
            raise RuntimeError(f"{PART_NO} helix seed circle failed")
    insert_helix(
        adapter,
        PITCH,
        REVS,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- chamfers (after the helix, before the thread cut) -----------------------
    head_r = HEAD_DIA / 2.0
    check(
        "chamfer head rim",
        await adapter.add_chamfer(HEAD_CHAMFER, [[0.0, HEAD_H, head_r]]),
    )
    name_last_feature(adapter, "HeadChamfer")
    v = math.pi * HEAD_CHAMFER**2 * (head_r - HEAD_CHAMFER / 3.0)
    volume = await volume_check(adapter, "head chamfer", volume - v, 0.03 * v)

    check(
        "chamfer thread start",
        await adapter.add_chamfer(TIP_CHAMFER, [[MAJOR_R, -UNDERHEAD_LEN, 0.0]]),
    )
    name_last_feature(adapter, "TipChamfer")
    v = math.pi * TIP_CHAMFER**2 * (MAJOR_R - TIP_CHAMFER / 3.0)
    await volume_check(adapter, "tip chamfer", volume - v, 0.02 * v)

    # --- split at the land bottom -------------------------------------------------
    offset_plane(adapter, "SplitPlane", Y_LAND_BOT)
    tail = _tail_body(split_at_plane(adapter, "SplitPlane", "TailSplit"))
    _telemetry.info(f"tail body: {tail}")

    # --- thread groove --------------------------------------------------------------
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    await add_line_chain(
        adapter,
        [
            (CUT_TOP_R, CUT_CENTRE_Y + CUT_TOP_W / 2.0),
            (ROOT_R, CUT_CENTRE_Y + ROOT_FLAT / 2.0),
            (ROOT_R, CUT_CENTRE_Y - ROOT_FLAT / 2.0),
            (CUT_TOP_R, CUT_CENTRE_Y - CUT_TOP_W / 2.0),
        ],
    )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(
        adapter, "ThreadCutter", "ThreadHelix", tail, "ThreadGroove", tangency=(0, 0)
    )

    # --- combine ----------------------------------------------------------------------
    combine_union(adapter, "ThreadedUnion")

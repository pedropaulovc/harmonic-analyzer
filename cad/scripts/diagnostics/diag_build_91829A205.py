r"""McMaster 91829A205 -- slotted 18-8 stainless precision shoulder screw,
shoulder Ø3/16 x 1/2, 8-32 x 3/16 (MHA-168, the transgear pivot screw).

Catalogue: the live page (``transgear-evidence/mcmaster-skus.md``, R1,
re-verified 2026-09-30).  Laws: the vendor model
``cad/references/mcmaster/91829A205.SLDPRT`` (SHA-256
bb7a805e75e4e656242ff71cc97cf7e34a7f97c4a90fd66f4b05cb3ebe24601c, harvested
on amet 2026-09-30; read-only dump
``cad/out/reports/mcmaster-91829A205-dump.json``; coordinator ruling R9-7).
The vendor file is local-only (© McMaster, gitignored, never committed; see
cad/references/mcmaster/README.md).  Vendor truth: volume 451.9447 mm^3,
area 485.1899 mm^2, 20 faces.  Every number is imported from
``transgear_pivot_screw_spec``; none is typed here.

The vendor tree is the 91829A560 family's (``diag_build_91829A560.py``, the
replica-gated original), reproduced feature for feature at this size:

1.  Base solid (their Revolve1): head HEAD_DIA x HEAD_H up from the
    under-head shoulder face (y = 0); shoulder SHOULDER_DIA x SHOULDER_LEN and
    thread shank THREAD_MAJOR x THREAD_LEN down from it.  Stacked extrudes
    make the same solid.
2.  Thread neck (their Cut-Revolve1 / Sketch5): under the shoulder's END face
    a R NECK_FILLET_R quarter-fillet (radial at the end face, tangent to the
    land) into a Ø NECK_DIA land, flat to NECK_FLAT_END below the end face,
    then a 45 deg flank back to the major, reached FULL_THREAD_START below it.
3.  Driver slot (their Cut-Extrude2 / Sketch8) SLOT_WIDTH x SLOT_DEPTH across
    the full head.
4.  Helix (their Helix/Spiral2): seeded on the tip plane, ascending, pitch
    PITCH x THREAD_LEN / PITCH revs (6).
5.  Chamfers, 45 deg (their Chamfer1/2): head rim HEAD_CHAMFER (the slot has
    already split the rim into two edges) and thread start TIP_CHAMFER.
6.  Split (their Split2 at Plane1) at the neck's land bottom, so the thread
    sweep is scoped to the tail and cannot touch the shoulder or the fillet.
7.  Thread groove (their Cut-Sweep1 / Sketch10): the UN 60 deg V truncated to
    a P/8 root flat at r = major - 0.75 H and capped at a 15P/16 top width,
    placed 7P/16 past the tip in air, swept along the helix, tail-scoped,
    start/end tangency none.
8.  Combine (their Combine1) unions the bodies back.

Class 2A and the shoulder's tolerances are not modelled (nominal sizes,
nominal UN cutter), as on the vendor model.

Frame: axis +Y, head up, the under-head shoulder face at y = 0 (Top Plane).
The vendor origin sits mid-overall (axis z, head +z), so their under-head
face is at z = (HEAD_H + SHOULDER_LEN + THREAD_LEN) / 2 - HEAD_H.

Run standalone (SolidWorks open, vendor file and dump local); it is the
replica gate::

    uv run python cad\scripts\diagnostics\diag_build_91829A205.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import _telemetry  # noqa: E402
from _common import (  # noqa: E402
    add_line_chain,
    check,
    define_centered_rectangle,
    define_circle,
    extrude_at_offset,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_build_91829A560 import (  # noqa: E402
    _slot_strip_area,
    _slotted_rim_chamfer_volume,
    _undercut_volume,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    combine_union,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    replica_main,
    split_at_plane,
    thread_sweep_cut,
)
from transgear_pivot_screw_spec import (  # noqa: E402
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
    SLOT_DEPTH,
    SLOT_WIDTH,
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

# Neck heights in the part frame.
Y_SHOULDER_END = -SHOULDER_LEN
Y_LAND_TOP = Y_SHOULDER_END - NECK_FILLET_R
Y_LAND_BOT = Y_SHOULDER_END - NECK_FLAT_END  # also the split plane (Plane1)

# The UN thread cutter (vendor Sketch10).
H_SHARP = PITCH * math.sqrt(3.0) / 2.0
ROOT_R = MAJOR_R - 0.75 * H_SHARP
ROOT_FLAT = PITCH / 8.0
CUT_TOP_W = 15.0 * PITCH / 16.0
CUT_TOP_R = ROOT_R + (CUT_TOP_W - ROOT_FLAT) / 2.0 * math.sqrt(3.0)
CUT_CENTRE_Y = -UNDERHEAD_LEN - 7.0 * PITCH / 16.0  # past the tip, in air

# The vendor origin is mid-overall, head +z.
VENDOR_UNDERHEAD_Z = (HEAD_H + UNDERHEAD_LEN) / 2.0 - HEAD_H

if not SLOT_DEPTH < HEAD_H:
    raise ValueError(f"{PART_NO}: the driver slot falls through the head")
if not CUT_TOP_R > MAJOR_R:
    raise ValueError(f"{PART_NO}: the thread cutter does not clear the major")
# The vendor fillet runs radially off the end face and lands tangent on the
# neck, so its radius IS the major-to-land rise; _undercut_volume assumes it.
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


async def build_91829A205(adapter, truth=None):
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    # --- base solid (vendor Revolve1) -----------------------------------------
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

    # --- thread neck (vendor Cut-Revolve1: fillet + land + 45 deg flank) ------
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

    # --- driver slot (vendor Cut-Extrude2) ------------------------------------
    offset_plane(adapter, "HeadTop", HEAD_H)
    check("create_sketch slot", await adapter.create_sketch("HeadTop"))
    await define_centered_rectangle(
        adapter, HEAD_DIA / 2.0 + 1.0, SLOT_WIDTH / 2.0, "slot"
    )
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=SLOT_DEPTH)),
    )
    name_last_feature(adapter, "DriverSlot")
    v = _slot_strip_area(HEAD_DIA / 2.0, SLOT_WIDTH) * SLOT_DEPTH
    volume = await volume_check(adapter, "driver slot", volume - v, 0.02 * v)

    # --- helix (vendor Helix/Spiral2: tip-seeded, ascending) ------------------
    # 91829A560's proven flags in this frame: Clockwised=False is the vendor's
    # right-hand thread, start azimuth +X on the Front plane's cutter.
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

    # --- chamfers (vendor order: after the helix, before the thread cut) ------
    head_r = HEAD_DIA / 2.0
    check(
        "chamfer head rim",
        await adapter.add_chamfer(
            HEAD_CHAMFER, [[0.0, HEAD_H, head_r], [0.0, HEAD_H, -head_r]]
        ),
    )
    name_last_feature(adapter, "HeadChamfer")
    v = _slotted_rim_chamfer_volume(head_r, HEAD_CHAMFER, SLOT_WIDTH)
    volume = await volume_check(adapter, "head chamfer", volume - v, 0.03 * v)

    check(
        "chamfer thread start",
        await adapter.add_chamfer(TIP_CHAMFER, [[MAJOR_R, -UNDERHEAD_LEN, 0.0]]),
    )
    name_last_feature(adapter, "TipChamfer")
    v = math.pi * TIP_CHAMFER**2 * (MAJOR_R - TIP_CHAMFER / 3.0)
    await volume_check(adapter, "tip chamfer", volume - v, 0.02 * v)

    # --- split at the land bottom (vendor Split2 @ Plane1) --------------------
    offset_plane(adapter, "SplitPlane", Y_LAND_BOT)
    tail = _tail_body(split_at_plane(adapter, "SplitPlane", "TailSplit"))
    _telemetry.info(f"tail body: {tail}")

    # --- thread groove (vendor Cut-Sweep1) ------------------------------------
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

    # --- combine (vendor Combine1) --------------------------------------------
    combine_union(adapter, "ThreadedUnion")

    # Vendor frame: axis z, head +z, origin mid-overall.
    adapter._mcm_com_map = lambda v: [v[0], v[2] - VENDOR_UNDERHEAD_Z, v[1]]


if __name__ == "__main__":
    sys.exit(replica_main(PART_NO, build_91829A205))

r"""McMaster 91794A055 -- 18-8 stainless slotted fillister screw, #0-80 x 1/4
(MHA-161, the transgear disc screws).

Every number is imported from ``transgear_disc_screw_spec`` (catalogue and
the laws read off the vendor model, each with its dump source); none is
typed here.  The vendor file ``cad/references/mcmaster/91794A055.SLDPRT``
(SHA-256 3b7b3ee38a51864b0c9d495e44ade30c80816d4b5498b8801211b8edb82676dc,
harvested on amet 2026-09-30) is local-only: (c) McMaster-Carr, gitignored,
never committed.  Vendor truth: volume 13.8241 mm^3, area 64.5474 mm^2,
26 faces.

This is NOT the 90280A narrow-fillister tree (``diag_mcmaster_fillister``):
the vendor tree is reproduced feature for feature.

1.  Revolve1: dome (spherical cap through the apex and the rim), a 5 deg
    drafted side down to the under-head face, the Ø1.02 D neck, the major
    shank and the 45 deg x 0.75 P tip chamfer.
2.  Cut-Extrude1: the driver slot, through all both ways, its floor 1.5 dome
    heights under the apex.
3.  Fillet1: the slot floor's two edges.
4.  Fillet2: the under-head rim and the dome rim (which the slot has split
    into two edges).
5.  Helix/Spiral1: seeded on the tip plane, ascending L + P (21 turns).
6.  Cut-Sweep1: the 60 deg V truncated to a P/8 root flat at major - 0.75 H,
    its 7P/8 top ON the major, placed past the tip in air; unscoped on the
    one body.  Its last turn runs above the under-head face, inside the
    head, as a closed void -- the vendor model carries that void (faces 20
    to 25 of the harvest), so the replica does too.
7.  Boss-Extrude1: the runout, a Ø(major + 0.1016) cylinder from the neck's
    step up to the under-head face, drafted 60 deg from the axis toward the
    tip.  Authored as a revolve: the adapter's extrusion path hardcodes
    Dchk1=False, so a drafted extrude cannot be requested through it.  The
    frustum stops at the thread root, fully submerged (no face).

Frame: axis +Y, head up, the under-head face at y = 0 (Top Plane).  The
vendor origin sits mid-overall (axis z, head +z) and its profile lies on
the Right Plane, so vendor +y is replica +x.

Cut to fit (optional, ``cut_length`` with ``cut_end_break``; R9-47): a
screw cut at assembly, as MHA-161's are, is drawn as installed, in the
``diag_mcmaster_oval`` idiom.  Revolve1 ends the shank at y = -cut_length
with a 45 deg break of radial leg ``cut_end_break`` in place of the factory
0.75 P tip chamfer, and ``revolved_volume`` follows the cut.  Everything
else is the supplied screw's: the helix stays seeded on the factory tip
plane and the cutter in air past it, so the groove is the vendor thread and
its first turns sweep air beyond the cut.  Without them the build is the
supplied screw, which the replica gate runs.

Run standalone (SolidWorks open, vendor file and dump local); it is the
replica gate::

    uv run python cad\scripts\diagnostics\diag_build_91794A055.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from _common import (  # noqa: E402
    add_line_chain,
    check,
    name_last_feature,
    volume_check,
)
from diagnostics.diag_mcmaster_lib import (  # noqa: E402
    _rev_frustum,
    _spherical_cap_volume,
    insert_helix,
    no_sketch_inference,
    offset_plane,
    replica_main,
    thread_sweep_cut,
)
from transgear_disc_screw_spec import (  # noqa: E402
    CUTTER_CENTRE_PAST_TIP,
    CUTTER_TOP_W,
    DOME_H,
    DOME_R,
    HEAD_BAND,
    HEAD_DIA,
    HEAD_FILLET_R,
    HEAD_H,
    HELIX_REVS,
    NECK_DIA,
    NECK_LEN,
    PITCH,
    ROOT_DIA,
    ROOT_FLAT,
    RUNOUT_DIA,
    RUNOUT_DRAFT_DEG,
    SHANK_DIA,
    SHANK_LEN,
    SKU,
    SLOT_DEPTH,
    SLOT_FILLET_R,
    SLOT_WIDTH,
    TIP_CHAMFER,
    UNDER_HEAD_DIA,
)

PART_NO = SKU

HEAD_R = HEAD_DIA / 2.0
UNDER_HEAD_R = UNDER_HEAD_DIA / 2.0
NECK_R = NECK_DIA / 2.0
MAJOR_R = SHANK_DIA / 2.0
ROOT_R = ROOT_DIA / 2.0
RUNOUT_R = RUNOUT_DIA / 2.0
SLOT_FLOOR_Y = HEAD_H - SLOT_DEPTH
# Runout frustum depth from the neck step down to the thread root.
RUNOUT_TAPER_H = (RUNOUT_R - ROOT_R) / math.tan(math.radians(RUNOUT_DRAFT_DEG))
# The vendor origin is mid-overall, head +z.
VENDOR_UNDERHEAD_Z = (HEAD_H + SHANK_LEN) / 2.0 - HEAD_H


def shank_end(
    cut_length: float | None = None, cut_end_break: float | None = None
) -> tuple[float, float]:
    """(length under the head, 45 deg end chamfer leg): the supplied screw's
    factory tip, or the cut end of a screw cut to fit."""
    if cut_length is None and cut_end_break is None:
        return SHANK_LEN, TIP_CHAMFER
    if cut_length is None or cut_end_break is None:
        raise ValueError(f"{PART_NO}: a cut needs both its length and its end break")
    if not cut_length < SHANK_LEN - TIP_CHAMFER:
        raise ValueError(
            f"{PART_NO}: a {cut_length} mm cut does not clear the supplied "
            f"{SHANK_LEN} mm screw's factory tip"
        )
    if not 0.0 < cut_end_break < MAJOR_R:
        raise ValueError(f"{PART_NO}: cut end break {cut_end_break} mm")
    if not NECK_LEN + RUNOUT_TAPER_H < cut_length - cut_end_break:
        raise ValueError(f"{PART_NO}: the {cut_length} mm cut leaves no shank")
    return cut_length, cut_end_break


def revolved_volume(
    cut_length: float | None = None, cut_end_break: float | None = None
) -> float:
    """Revolve1's solid: cap + drafted band + neck + shank + end frustum."""
    length, end_ch = shank_end(cut_length, cut_end_break)
    return (
        _spherical_cap_volume(HEAD_R, DOME_H)
        + _rev_frustum(HEAD_BAND, UNDER_HEAD_R, HEAD_R)
        + math.pi * NECK_R**2 * NECK_LEN
        + math.pi * MAJOR_R**2 * (length - NECK_LEN - end_ch)
        + _rev_frustum(end_ch, MAJOR_R, MAJOR_R - end_ch)
    )


async def build_91794A055(
    adapter,
    truth=None,
    *,
    cut_length: float | None = None,
    cut_end_break: float | None = None,
):
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    length, end_ch = shank_end(cut_length, cut_end_break)
    # --- Revolve1 --------------------------------------------------------------
    check("create_sketch profile", await adapter.create_sketch("Front"))
    sk_mgr = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk_mgr.CreateCenterLine(
                0.0, HEAD_H / 1000.0, 0.0, 0.0, -length / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NO} profile: CreateCenterLine failed")
        # Three-point dome arc: the mid point pins the bulge with no direction
        # flag (the fillister family's lesson on inference-snapped arcs).
        yc = HEAD_H - DOME_R
        ang_mid = (math.pi / 2.0 + math.atan2(HEAD_BAND - yc, HEAD_R)) / 2.0
        arc = sk_mgr.Create3PointArc(
            0.0,
            HEAD_H / 1000.0,
            0.0,  # start: dome apex
            HEAD_R / 1000.0,
            HEAD_BAND / 1000.0,
            0.0,  # end: dome rim
            DOME_R * math.cos(ang_mid) / 1000.0,  # mid, on the sphere
            (yc + DOME_R * math.sin(ang_mid)) / 1000.0,
            0.0,
        )
        if arc is None:
            raise RuntimeError(f"{PART_NO} profile: dome arc failed")
        await add_line_chain(
            adapter,
            [
                (HEAD_R, HEAD_BAND),
                (UNDER_HEAD_R, 0.0),
                (NECK_R, 0.0),
                (NECK_R, -NECK_LEN),
                (MAJOR_R, -NECK_LEN),
                (MAJOR_R, -(length - end_ch)),  # factory tip or cut-end break
                (MAJOR_R - end_ch, -length),
                (0.0, -length),
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
    v = revolved_volume(cut_length, cut_end_break)
    await volume_check(adapter, "revolved body", v, 0.005 * v)

    # --- Cut-Extrude1: driver slot ---------------------------------------------
    check("create_sketch slot", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (-SLOT_WIDTH / 2.0, HEAD_H + 0.5),
                (SLOT_WIDTH / 2.0, HEAD_H + 0.5),
                (SLOT_WIDTH / 2.0, SLOT_FLOOR_Y),
                (-SLOT_WIDTH / 2.0, SLOT_FLOOR_Y),
            ],
        )
    check("exit_sketch slot", await adapter.exit_sketch())
    name_last_feature(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * HEAD_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, "DriverSlot")

    # --- Fillet1 / Fillet2 ---------------------------------------------------------
    check(
        "slot floor fillets",
        await adapter.add_fillet(
            SLOT_FILLET_R,
            [
                [SLOT_WIDTH / 2.0, SLOT_FLOOR_Y, 0.0],
                [-SLOT_WIDTH / 2.0, SLOT_FLOOR_Y, 0.0],
            ],
        ),
    )
    name_last_feature(adapter, "SlotFillet")
    check(
        "head fillets",
        await adapter.add_fillet(
            HEAD_FILLET_R,
            [
                [UNDER_HEAD_R, 0.0, 0.0],
                [HEAD_R, HEAD_BAND, 0.0],
                [-HEAD_R, HEAD_BAND, 0.0],
            ],
        ),
    )
    name_last_feature(adapter, "HeadFillet")

    # --- Helix/Spiral1: tip-seeded, L + P up ------------------------------------
    # Their tip plane has normal -z with clockwise=True, reverse=True; ours is
    # +y, so both flags invert (91255A148 / 93075A194 proved the handedness);
    # start azimuth on the Front plane's +x cutter.
    offset_plane(adapter, "TipPlane", -SHANK_LEN)
    check("create_sketch helix seed", await adapter.create_sketch("TipPlane"))
    with no_sketch_inference(adapter):
        if (
            adapter.currentSketchManager.CreateCircleByRadius(
                0.0, 0.0, 0.0, MAJOR_R / 1000.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NO} helix seed circle failed")
    insert_helix(
        adapter,
        PITCH,
        HELIX_REVS,
        clockwise=False,
        reversed_dir=False,
        start_angle_rad=math.pi / 2.0,
        feature_name="ThreadHelix",
    )

    # --- Cut-Sweep1: thread groove ---------------------------------------------
    cy = -SHANK_LEN - CUTTER_CENTRE_PAST_TIP
    check("create_sketch cutter", await adapter.create_sketch("Front"))
    with no_sketch_inference(adapter):
        await add_line_chain(
            adapter,
            [
                (MAJOR_R, cy + CUTTER_TOP_W / 2.0),
                (MAJOR_R, cy - CUTTER_TOP_W / 2.0),
                (ROOT_R, cy - ROOT_FLAT / 2.0),
                (ROOT_R, cy + ROOT_FLAT / 2.0),
            ],
        )
    check("exit_sketch cutter", await adapter.exit_sketch())
    name_last_feature(adapter, "ThreadCutter")
    thread_sweep_cut(
        adapter, "ThreadCutter", "ThreadHelix", None, "ThreadGroove", tangency=(0, 0)
    )

    # --- Boss-Extrude1: runout -------------------------------------------------
    check("create_sketch runout", await adapter.create_sketch("Front"))
    sk2 = adapter.currentSketchManager
    with no_sketch_inference(adapter):
        if (
            sk2.CreateCenterLine(
                0.0, 0.0, 0.0, 0.0, -(NECK_LEN + RUNOUT_TAPER_H) / 1000.0, 0.0
            )
            is None
        ):
            raise RuntimeError(f"{PART_NO} runout: CreateCenterLine failed")
        await add_line_chain(
            adapter,
            [
                (0.0, 0.0),
                (RUNOUT_R, 0.0),
                (RUNOUT_R, -NECK_LEN),
                (ROOT_R, -NECK_LEN - RUNOUT_TAPER_H),
                (0.0, -NECK_LEN - RUNOUT_TAPER_H),
            ],
        )
    check("exit_sketch runout", await adapter.exit_sketch())
    name_last_feature(adapter, "RunoutProfile")
    check(
        "runout",
        await adapter.create_revolve(RevolveParameters(angle=360.0, is_cut=False)),
    )
    name_last_feature(adapter, "ThreadRunout")

    # Vendor frame: axis z, head +z, origin mid-overall, profile on the
    # Right Plane (vendor +y = replica +x).
    adapter._mcm_com_map = lambda v: [v[1], v[2] - VENDOR_UNDERHEAD_Z, v[0]]


if __name__ == "__main__":
    sys.exit(replica_main(PART_NO, build_91794A055))

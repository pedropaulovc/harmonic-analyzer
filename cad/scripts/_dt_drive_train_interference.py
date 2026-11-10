"""Explicit, volume-bounded interference-fit contract for the drive train.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_dt_drive_train_assembly (and the
assemblies that contain it) and verify_soundness:dt_drive_train fold this
module, so it imports only what its own pairs need.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from _hole_spec import blind_cut_dia_mm
from _hole_spec import THREAD_MAJOR_MM
from _hole_spec import TAP_DRILL_MM
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from dt_crank_hub_spec import (
    HUB_BARREL_DIA as _HUB_W,
    HUB_BORE_DIA as _HUB_BORE,
    SERVICE_PIN_HOLE_SPEC as _HUB_PILOT_SPEC,
)
from dt_crank_pin_spec import (
    BIG_END_DIA as _PIN_D0,
    PIN_LENGTH as _PIN_L,
    SMALL_END_DIA as _PIN_D1,
)
from dt_crank_pin_ring_spec import PIN_PROUD as _PIN_PROUD

# The shaft diameter's owner, not dt_crankshaft_spec: this table and the drive
# train's soundness gate need only the diameter, so a crankshaft length or
# station edit must not re-key them.
from dt_crank_hub_geometry import SHAFT_DIA as _CS_DIA

# Only nominal penetration is shared across assemblies, not the part's full
# drawing/placement recipe (which depends on the cone/channel station grid).
from dt_post_mount_stack import POST_SCREW_ENGAGEMENT_NOMINAL as _POST_SCREW_ENGAGEMENT
from sh_vn_arbor_set_screw_spec import LENGTH as _ARBOR_SET_SCREW_LENGTH
from sh_vn_arbor_set_screw_spec import THREAD as _ARBOR_SET_SCREW_THREAD
from _sprocket_seat_geometry import DRIVE_PIN_DIA as _SEAT_PIN_DIA
from _sprocket_seat_geometry import DRIVE_PIN_HOLE_DIA as _SEAT_PIN_HOLE_DIA
from dt_vn_crank_seat_drive_pin_spec import PRESS_DEPTH as _CRANK_SEAT_PIN_DEPTH
from dt_cone_tip_block_spec import DOWEL_HOLE_DEPTH as _TIP_DOWEL_PRESS_DEPTH
from dt_vn_locating_pin_spec import DIA as _LOCATING_PIN_DIA
from dt_vn_locating_pin_spec import PRESS_HOLE_DIA as _LOCATING_PIN_PRESS_HOLE_DIA
from cone_tip_cluster import (
    BUSHING_BORE_DIA_MM as _BUSHING_BORE_DIA,
    BUSHING_LENGTH_MM as _BUSHING_LENGTH,
    STEM_DIA_MM as _PIVOT_DIA,
)


# Crank taper pin in its PILOT holes (ch11 p.14): released drawings drill the
# separate hub #14 (4.623) and shaft #9 (4.978), then taper-ream them together
# at assembly.  Bound each overlap at 1.10 x the analytic
# frustum-minus-cylinder volume over the receiver span (hub barrel minus its
# through bore; shaft diameter).  The arm is outboard of this station and has
# no MHA-DT-09 overlap.

_CS_PILOT = 4.978  # #9 drill (build_dt_crankshaft's wizard cross-hole)


def _pin_overlap(s0: float, s1: float, hole_dia: float) -> float:
    """Volume of the taper pin between axial stations s0..s1 (from the big end)
    that lies OUTSIDE a straight hole of ``hole_dia`` on the same axis."""
    n = 200
    total = 0.0
    for i in range(n):
        s = s0 + (s1 - s0) * (i + 0.5) / n
        d = _PIN_D0 - (_PIN_D0 - _PIN_D1) * s / _PIN_L
        total += max(0.0, math.pi / 4.0 * (d * d - hole_dia * hole_dia)) * (s1 - s0) / n
    return total


_HUB_PILOT = blind_cut_dia_mm(_HUB_PILOT_SPEC)

# Hub -X face at s=PIN_PROUD; its axial shaft bore occupies the middle chord.
_HUB_S0, _HUB_S1 = _PIN_PROUD, _PIN_PROUD + _HUB_W
_BORE_S0 = _PIN_PROUD + (_HUB_W - _HUB_BORE) / 2.0
_BORE_S1 = _BORE_S0 + _HUB_BORE
_CS_S0 = _PIN_PROUD + (_HUB_W - _CS_DIA) / 2.0
_CS_S1 = _CS_S0 + _CS_DIA
_CRANK_PIN_HUB_MM3 = _pin_overlap(_HUB_S0, _BORE_S0, _HUB_PILOT) + _pin_overlap(
    _BORE_S1, _HUB_S1, _HUB_PILOT
)
_CRANK_PIN_SHAFT_MM3 = _pin_overlap(_CS_S0, _CS_S1, _CS_PILOT)

# Independent SolidWorks-kernel observations for the exact stock bodies in
# their production receivers, each with ten-percent bounded headroom so any
# materially deeper insertion fails.
#
# The tip block's pinch screw was read by the mha092-r3-8b1b drive-train leaf
# (8b1bdef31, farm run 20260925T225229777Z; assembly:drive_train log line
# 333/335, verify_soundness:drive_train line 115/117): 91794A112 pinch screw
# (15.875, 17-wide block): 7.8008 mm3.  It replaces the analytic 22.78 (6.47
# read on the 14-wide block, scaled by far-jaw length), which ran 2.9x high:
# the per-length scaling does not hold.
#
# The MHA-DT-VN-60 hold-down (91251A108 #4-40 x 3/8 SHCS) up through the platform
# into the MHA-DT-21 foot tap: 5.6585 mm3, read by the first prism-block
# drive-train leaf (cc7f631ab, farm run 20260929T224514758Z,
# assembly:drive_train log line 465).
_TIP_PINCH_OBSERVED_MM3 = 7.8008
_TIP_PINCH_GATE_LIMIT_MM3 = _TIP_PINCH_OBSERVED_MM3 * 1.10
_TIP_HOLDDOWN_OBSERVED_MM3 = 5.6585
_TIP_HOLDDOWN_GATE_LIMIT_MM3 = _TIP_HOLDDOWN_OBSERVED_MM3 * 1.10
# MHA-DT-39, the 1/4-28 end screw (owner decision C1 keyed, 2026-11-09, PR
# #1992), runs through MHA-DT-21's whole tapped depth with its threaded end
# proud of the south face, so its axial setting does not change the overlap:
# 34.1729 mm3, read by the PR 2 drive-train leaf (6fda5a47590f, farm run
# 20261110T001845485Z, assembly:dt_drive_train log line 601; the smooth
# annulus bound was 104.31, 3.1x the reading).
_END_SCREW_OBSERVED_MM3 = 34.1729
_END_SCREW_GATE_LIMIT_MM3 = _END_SCREW_OBSERVED_MM3 * 1.10
# MHA-DT-38 pressed on MHA-DT-37's pivot: the modelled press is the nominal
# pivot in the nominal .0615 bore over the bushing's whole length.
_BUSHING_PRESS_GATE_LIMIT_MM3 = smooth_annulus_limit_mm3(
    _PIVOT_DIA, _BUSHING_BORE_DIA, _BUSHING_LENGTH
)

ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    frozenset(("dt-crank-pin-1", "dt-crank-hub-1")): 1.10 * _CRANK_PIN_HUB_MM3,
    frozenset(("dt-crank-pin-1", "dt-crankshaft-1")): 1.10 * _CRANK_PIN_SHAFT_MM3,
    # MHA-DT-VN-70 #2-56 major in the arm's #50 tap drill: the stock 6.35
    # shank minus the 1.194 jack-chain wire under its head and 0.02 face air.
    frozenset(
        ("dt-vn-keeper-chain-screw-1", "dt-crank-arm-1")
    ): smooth_annulus_limit_mm3(THREAD_MAJOR_MM["#2-56"], TAP_DRILL_MM["#2-56"], 5.14),
    # MHA-DT-32 #6-32 major in the arm's #36 tap drill: the full thread past the
    # 1.5 relief (6.5 of the 8.0 arm) plus its 0.5 lead cone.  The size is
    # named here, not imported from dt_crank_handle_pivot_screw_spec, so this
    # table stays clear of the handle specs; the MHA-DT-32 tests pin
    # it to that spec's THREAD_SIZE.
    frozenset(
        ("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1")
    ): smooth_annulus_limit_mm3(THREAD_MAJOR_MM["#4-40"], TAP_DRILL_MM["#4-40"], 7.0),
    # MHA-DT-39's 1/4-28 thread in the tapped block, observed above.
    frozenset(
        ("dt-cone-tip-end-screw-1", "dt-cone-tip-block-1")
    ): _END_SCREW_GATE_LIMIT_MM3,
    frozenset(
        ("dt-vn-cone-tip-pinch-screw-1", "dt-cone-tip-block-1")
    ): _TIP_PINCH_GATE_LIMIT_MM3,
    frozenset(
        ("dt-vn-cone-tip-block-screw-1", "dt-cone-tip-block-1")
    ): _TIP_HOLDDOWN_GATE_LIMIT_MM3,
    # The bushing's press on the pivot.  The LOCTITE 638 bonded slip fits
    # (T024 on land 2, T018/T012 on the spigot, the spigot in MHA-DT-04's
    # socket) are modelled line-to-line at their nominal sizes and need no
    # allowance.
    frozenset(
        ("dt-cone-tip-bushing-1", "dt-cone-tip-gear-1")
    ): _BUSHING_PRESS_GATE_LIMIT_MM3,
    # U30 (I22): each MHA-DT-VN-61 (1/4-20 MSC 40923906, major 6.35) in its #7
    # (5.105) MHA-DT-20 tap, as deep as the cut length runs past the post's
    # grip (the counterbore floor).  The smooth-annulus upper bound until the
    # first drive-train build observes the helical overlap.
    **numbered_pairs(
        "dt-vn-post-mount-screw",
        (1, 2),
        "dt-cone-swing-platform",
        smooth_annulus_limit_mm3(6.35, 5.105, _POST_SCREW_ENGAGEMENT),
    ),
    # #743 Q3: the MHA-DT-VN-64 #4-40 apex set screw in each pedestal's crown tap,
    # bounded over its whole length (the crown holds a little less: the cup
    # point stands in the bore clearance and the socket stands
    # cylinder_bank_layout.SET_SCREW_SOCKET_PROUD over the apex). Pedestal and
    # screw are both placed south first, so their suffixes match. #911: this
    # smooth-annulus bound serves the first build only -- re-pin it to the
    # measured overlap x 1.10 from the first drive_train leaf, as #838 did for
    # the tip-block pairs.
    **numbered_pairs(
        "sh-vn-arbor-set-screw",
        range(1, 3),
        "dt-arbor-pedestal",
        smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD],
            TAP_DRILL_MM[_ARBOR_SET_SCREW_THREAD],
            _ARBOR_SET_SCREW_LENGTH,
        ),
        second_number=None,
    ),
    # The two MHA-DT-VN-67 dowels pressed into MHA-DT-11's seat-collar holes
    # (ø2.38125 pin in a ø2.3622 (.0930) ream over the press depth): the press fit.
    **numbered_pairs(
        "dt-vn-crank-seat-drive-pin",
        range(1, 3),
        "dt-crankshaft",
        smooth_annulus_limit_mm3(
            _SEAT_PIN_DIA, _SEAT_PIN_HOLE_DIA, _CRANK_SEAT_PIN_DEPTH
        ),
    ),
    # The MHA-DT-VN-69 tip dowel (rule-23 retention, owner ruling 2026-11-07
    # (MHA-DT-00 rubric sample, PR #2248)) pressed up to the floor
    # of the MHA-DT-21 foot's blind .0620 ream: the press fit over the ream's
    # depth.  Its lower end is a slip fit in the MHA-DT-20 plate.
    **numbered_pairs(
        "dt-vn-locating-pin",
        range(1, 2),
        "dt-cone-tip-block",
        smooth_annulus_limit_mm3(
            _LOCATING_PIN_DIA, _LOCATING_PIN_PRESS_HOLE_DIA, _TIP_DOWEL_PRESS_DEPTH
        ),
    ),
}

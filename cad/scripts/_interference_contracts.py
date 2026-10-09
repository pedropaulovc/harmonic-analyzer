"""Explicit, volume-bounded interference-fit contracts for assembly gates.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from _hole_spec import blind_cut_dia_mm
from fr_harmonic_base_fasteners import (
    HOLD_DOWN_ENGAGEMENT as _HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_TAP_DRILL_DIA as _HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD as _HOLD_DOWN_THREAD,
    PEDESTAL_SCREW_ENGAGEMENT as _PEDESTAL_SCREW_ENGAGEMENT,
)
from _hole_spec import THREAD_MAJOR_MM
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
# The shaft diameter's owner, not dt_crankshaft_spec: every assembly imports this
# module, so a crankshaft length or station edit must not re-key them all.
from dt_crank_hub_geometry import SHAFT_DIA as _CS_DIA
import sm_summing_lever_spec
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1
from fr_frame_attachment_spec import COLUMN_SOCKET_DIAMETER
from vn_frame_cross_screw_spec import SHANK_DIA as _FRAME_CROSS_DIA
from vn_frame_cross_screw_spec import SHANK_LEN as _FRAME_CROSS_LENGTH
from vn_frame_cross_screw_spec import THREAD as _FRAME_CROSS_THREAD
from _hole_spec import TAP_DRILL_MM
from vn_post_mount_screw_spec import CUT_LENGTH_MM as _POST_SCREW_CUT_LENGTH
from vn_post_mount_screw_spec import GRIP_MM as _POST_SCREW_GRIP
from vn_arbor_set_screw_spec import LENGTH as _ARBOR_SET_SCREW_LENGTH
from vn_arbor_set_screw_spec import THREAD as _ARBOR_SET_SCREW_THREAD
from vn_swing_stop_screw_spec import EMBED_LEN as _STOP_EMBED_LEN
from vn_swing_stop_screw_spec import SHANK_DIA as _STOP_SHANK_DIA
from vn_swing_stop_screw_spec import THREAD as _STOP_THREAD
from pd_transgear_removable_spec import DRIVE_PIN_DIA as _SEAT_PIN_DIA
from pd_transgear_removable_spec import DRIVE_PIN_HOLE_DIA as _SEAT_PIN_HOLE_DIA
from vn_crank_seat_drive_pin_spec import PRESS_DEPTH as _CRANK_SEAT_PIN_DEPTH
from vn_transgear_knob_drive_pin_spec import PRESS_DEPTH as _KNOB_SEAT_PIN_DEPTH
from magnifying_bracket_joint_layout import (
    ENGAGEMENT as _BRACKET_SCREW_ENGAGEMENT,
    SCREW_MAJOR_DIA as _BRACKET_SCREW_MAJOR_DIA,
    TAP_DRILL_DIA as _BRACKET_TAP_DRILL_DIA,
)
from vn_knife_mount_dowel_spec import DIA_MAX as _KNIFE_DOWEL_DIA_MAX
from vn_knife_mount_dowel_spec import PRESS_DEPTH as _KNIFE_DOWEL_PRESS_DEPTH


def _smooth_annulus_limit_mm3(
    major_d: float,
    tap_d: float,
    length: float,
) -> float:
    """Return a 10%-headroom bound for smooth thread-envelope engagement."""
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _numbered_pairs(
    first_stem: str,
    numbers: Iterable[int],
    second_stem: str,
    limit: float,
    *,
    second_number: int | None = 1,
) -> dict[frozenset[str], float]:
    """Build exact numbered component pairs, optionally matching suffixes."""
    return {
        frozenset(
            (
                f"{first_stem}-{number}",
                f"{second_stem}-{number if second_number is None else second_number}",
            )
        ): limit
        for number in numbers
    }


# Crank taper pin in its PILOT holes (ch11 p.14): released drawings drill the
# separate hub #14 (4.623) and shaft #9 (4.978), then taper-ream them together
# at assembly.  Bound each overlap at 1.10 x the analytic
# frustum-minus-cylinder volume over the receiver span (hub barrel minus its
# through bore; shaft diameter).  The arm is outboard of this station and has
# no MHA-DT-009 overlap.

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
# materially deeper insertion fails.  The cup-tip adjuster makes its intended
# thrust contact with the shaft end at 0.13 mm3: the 45 deg cup's analytic
# (2/3)*pi*r^3 for the 0.79 stub (0.131), re-read at 0.1309 by the
# mha092-r3-8b1b drive-train leaf on rule-12 E11's 94025A164.  The 1/16 in
# tip land doubles the stub radius, so the contact scales by r^3: 0.13 * 8 =
# 1.04 (analytic 1.047) until the next drive-train build re-observes it.
#
# The tip block's two threaded pairs were read by that same leaf (8b1bdef31,
# farm run 20260925T225229777Z; assembly:drive_train log line 333/335,
# verify_soundness:drive_train line 115/117):
# - 91794A112 pinch screw (15.875, 17-wide block): 7.8008 mm3.  It replaces
#   the analytic 22.78 (6.47 read on the 14-wide block, scaled by far-jaw
#   length), which ran 2.9x high: the per-length scaling does not hold.
# - 94025A164 adjuster (#10-32, 9.5 embed): 16.4412 mm3 over its 13 thread
#   bodies.  It replaces the smooth-annulus bound (major 4.826 in the #21
#   4.0386 drill, 9.5 deep: 57.29), 3.5x the reading, loose enough to hide a
#   regression.
#
# The MHA-VN-030 hold-down (91251A108 #4-40 x 3/8 SHCS) up through the platform
# into the MHA-DT-021 foot tap: 5.6585 mm3, read by the first prism-block
# drive-train leaf (cc7f631ab, farm run 20260929T224514758Z,
# assembly:drive_train log line 465).
_TIP_PINCH_OBSERVED_MM3 = 7.8008
_TIP_PINCH_GATE_LIMIT_MM3 = _TIP_PINCH_OBSERVED_MM3 * 1.10
_TIP_ADJUSTER_OBSERVED_MM3 = 16.4412
_TIP_ADJUSTER_GATE_LIMIT_MM3 = _TIP_ADJUSTER_OBSERVED_MM3 * 1.10
_TIP_HOLDDOWN_OBSERVED_MM3 = 5.6585
_TIP_HOLDDOWN_GATE_LIMIT_MM3 = _TIP_HOLDDOWN_OBSERVED_MM3 * 1.10
_ADJUSTER_THRUST_GATE_LIMIT_MM3 = 0.13 * 8.0 * 1.10

_DRIVE_TRAIN_ALLOWED_PAIRS = {
    frozenset(("dt-crank-pin-1", "dt-crank-hub-1")): 1.10 * _CRANK_PIN_HUB_MM3,
    frozenset(("dt-crank-pin-1", "dt-crankshaft-1")): 1.10 * _CRANK_PIN_SHAFT_MM3,
    # Stock 6.35 shank minus the 1.0 eye wire and 0.02 face clearance.
    frozenset(("vn-fillister-screw-1", "dt-crank-arm-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.33
    ),
    # MHA-DT-032 #6-32 major in the arm's #36 tap drill: the full thread past the
    # 1.5 relief (6.5 of the 8.0 arm) plus its 0.5 lead cone.  The size is
    # named here, not imported from dt_crank_handle_pivot_screw_spec, so every
    # assembly's recipe stays clear of the handle specs; the MHA-DT-032 tests pin
    # it to that spec's THREAD_SIZE.
    frozenset(("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1")): _smooth_annulus_limit_mm3(
        THREAD_MAJOR_MM["#4-40"], TAP_DRILL_MM["#4-40"], 7.0
    ),
    # Rule-12 E11: #10-32 94025A164 in the tapped block, observed above.
    frozenset(
        ("vn-cone-tip-adjuster-1", "dt-cone-tip-block-1")
    ): _TIP_ADJUSTER_GATE_LIMIT_MM3,
    frozenset(
        ("vn-cone-tip-pinch-screw-1", "dt-cone-tip-block-1")
    ): _TIP_PINCH_GATE_LIMIT_MM3,
    frozenset(
        ("vn-cone-tip-block-screw-1", "dt-cone-tip-block-1")
    ): _TIP_HOLDDOWN_GATE_LIMIT_MM3,
    frozenset(
        ("vn-cone-tip-adjuster-1", "dt-cone-gear-shaft-1")
    ): _ADJUSTER_THRUST_GATE_LIMIT_MM3,
    # U30 (I22): each MHA-VN-031 (1/4-20 MSC 40923898, major 6.35) in its #7
    # (5.105) MHA-DT-020 tap, as deep as the cut length runs past the post's
    # grip (the counterbore floor).  The smooth-annulus upper bound until the
    # first drive-train build observes the helical overlap.
    **_numbered_pairs(
        "vn-post-mount-screw",
        (1, 2),
        "dt-cone-swing-platform",
        _smooth_annulus_limit_mm3(
            6.35, 5.105, _POST_SCREW_CUT_LENGTH - _POST_SCREW_GRIP
        ),
    ),
    # #743 Q3: the MHA-VN-034 #4-40 apex set screw in each pedestal's crown tap,
    # bounded over its whole length (the crown holds a little less: the cup
    # point stands in the bore clearance and the socket stands
    # cylinder_bank_layout.SET_SCREW_SOCKET_PROUD over the apex). Pedestal and
    # screw are both placed south first, so their suffixes match. #911: this
    # smooth-annulus bound serves the first build only -- re-pin it to the
    # measured overlap x 1.10 from the first drive_train leaf, as #838 did for
    # the tip-block pairs.
    **_numbered_pairs(
        "vn-arbor-set-screw",
        range(1, 3),
        "dt-arbor-pedestal",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD],
            TAP_DRILL_MM[_ARBOR_SET_SCREW_THREAD],
            _ARBOR_SET_SCREW_LENGTH,
        ),
        second_number=None,
    ),
    # The two MHA-VN-044 dowels pressed into MHA-DT-011's seat-collar holes
    # (ø2.38125 pin in a ø2.38 ream over the press depth): the press fit.
    **_numbered_pairs(
        "vn-crank-seat-drive-pin",
        range(1, 3),
        "dt-crankshaft",
        _smooth_annulus_limit_mm3(
            _SEAT_PIN_DIA, _SEAT_PIN_HOLE_DIA, _CRANK_SEAT_PIN_DEPTH
        ),
    ),
}

# Minimum socket chord across the screw's complete major-diameter envelope.
# Only the two tapped casting lands may overlap the stock helical thread.
# Neither the clearance-drilled tubes nor the cap skirts receive an exemption.
_FRAME_CROSS_CASTING_LENGTH = _FRAME_CROSS_LENGTH - math.sqrt(
    COLUMN_SOCKET_DIAMETER**2 - _FRAME_CROSS_DIA**2
)
_FRAME_CROSS_GATE_LIMIT_MM3 = _smooth_annulus_limit_mm3(
    _FRAME_CROSS_DIA,
    TAP_DRILL_MM[_FRAME_CROSS_THREAD],
    _FRAME_CROSS_CASTING_LENGTH,
)

_FRAME_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "vn-lag-screw",
        range(1, 5),
        "fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_HOLD_DOWN_THREAD],
            _HOLD_DOWN_TAP_DRILL_DIA,
            _HOLD_DOWN_ENGAGEMENT,
        ),
    ),
    **_numbered_pairs(
        "vn-frame-cross-screw",
        range(1, 5),
        "fr-harmonic-base",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    **_numbered_pairs(
        "vn-frame-cross-screw",
        range(5, 9),
        "fr-top-frame",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    frozenset(("vn-gooseneck-set-screw-1", "fr-top-frame-1")): _smooth_annulus_limit_mm3(
        6.35, 5.105, 6.95
    ),
    # Four nameplate corners: 6.35-mm stock shank through the 1.5-mm plate.
    **_numbered_pairs(
        "vn-fillister-screw",
        range(1, 5),
        "fr-harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.85),
    ),
}

_MAGNIFIER_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "vn-clamp-screw",
        range(1, 3),
        "sh-column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 4.85),
    ),
    frozenset(("vn-thumb-screw-1", "mg-magnifying-clamp-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 3.9
    ),
}

_COUNTER_ANCHOR_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    ANCHOR_9490T1.thread_major_dia_mm,
    blind_cut_dia_mm(sm_summing_lever_spec.COUNTER_HOLE_SPEC),
    sm_summing_lever_spec.ANCHOR_H,
)
_CHANNEL_ANCHOR_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    ANCHOR_9489T111.thread_major_dia_mm,
    blind_cut_dia_mm(sm_summing_lever_spec.HOLE_SPEC),
    sm_summing_lever_spec.PLATE_T,
)
# MHA-VN-024 #6-32 (91251A157) in each knife mount's #36 tap drill over its
# nominal reach, 8.10: the 30.0 crossbar grip under the 38.1 screw
# (build_sm_summing_assembly.HANGER_REACH; a literal, test-pinned, so a
# knife-mount or top-frame edit does not re-key every assembly).
_KNIFE_HANGER_REACH = 8.10
# Each MHA-VN-051 dowel pressed to the floor of its knife mount's Ø3.175 ream
# (sm_knife_mount_spec.PIN_HOLE_DIA, band +0/-0.010: smallest 3.165,
# test-pinned).  The models are line to line, so this bounds the press at its
# print-worst: the largest catalogue pin in the smallest ream, the whole depth.
# Two per mount, inserted front mount first (build_sm_summing_assembly):
# dowels 1-2 in sm-knife-mount-1, 3-4 in sm-knife-mount-2.
_KNIFE_DOWEL_HOLE_MIN = 3.165
_KNIFE_DOWEL_PRESS_LIMIT = _smooth_annulus_limit_mm3(
    _KNIFE_DOWEL_DIA_MAX, _KNIFE_DOWEL_HOLE_MIN, _KNIFE_DOWEL_PRESS_DEPTH
)
_SUMMING_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "vn-knife-hanger-stud",
        range(1, 3),
        "sm-knife-mount",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["#6-32"], TAP_DRILL_MM["#6-32"], _KNIFE_HANGER_REACH
        ),
        second_number=None,
    ),
    **_numbered_pairs(
        "vn-knife-mount-dowel", range(1, 3), "sm-knife-mount", _KNIFE_DOWEL_PRESS_LIMIT
    ),
    **_numbered_pairs(
        "vn-knife-mount-dowel",
        range(3, 5),
        "sm-knife-mount",
        _KNIFE_DOWEL_PRESS_LIMIT,
        second_number=2,
    ),
    frozenset(("vn-boss-hook-1", "sm-summing-lever-1")): _COUNTER_ANCHOR_THREAD_LIMIT,
}

_PEN_ALLOWED_PAIRS = {
    frozenset(("vn-pen-set-screw-1", "pn-pen-frame-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.0
    ),
    frozenset(("vn-hanger-screw-1", "pn-pen-hanger-1")): _smooth_annulus_limit_mm3(
        4.1656, 3.454, 3.0
    ),
}


def _cross_pin_overlap_mm3(pin_od: float, pin_id: float, shaft_d: float) -> float:
    """Volume a tube pin lying diametrally across a solid shaft shares with it:
    the perpendicular-cylinder intersection at its OD less that at its ID.
    _holes.cross_hole_volume_mm3's trapezoid integral, restated so every
    assembly's recipe stays clear of the Hole Wizard helpers."""

    def solid(pin_d: float, n: int = 20001) -> float:
        r, big_r = pin_d / 2.0, shaft_d / 2.0
        dx = 2.0 * r / (n - 1)
        total = 0.0
        for i in range(n):
            x = -r + i * dx
            weight = 0.5 if i in (0, n - 1) else 1.0
            total += (
                weight
                * 4.0
                * math.sqrt(max(big_r**2 - x * x, 0.0))
                * math.sqrt(max(r**2 - x * x, 0.0))
            )
        return total * dx

    return solid(pin_od) - solid(pin_id)


# MHA-VN-037, a 1/16-in tube with a 0.012-in wall, lies diametrally across
# MHA-PD-008's Ø6.35 core, whose hole is drilled at assembly and not modelled.
_CROSS_PIN_CORE_MM3 = _cross_pin_overlap_mm3(
    25.4 / 16.0, 25.4 / 16.0 - 2.0 * 0.012 * 25.4, 6.35
)

# MHA-VN-048 (98296A031), the same tube 5/8 long, lies diametrally across the
# MHA-PD-008 journal's rear end (Ø8.5) and both walls of the MHA-PD-016 cup ring,
# in a hole match-drilled through both at assembly and not modelled (R9-70,
# K-1): its chord through the journal, and the rest of its length in the cup
# (its ends stay inside the cup's O.D.).
_CUP_PIN_OD = 25.4 / 16.0
_CUP_PIN_ID = _CUP_PIN_OD - 2.0 * 0.012 * 25.4
_CUP_PIN_JOURNAL_MM3 = _cross_pin_overlap_mm3(_CUP_PIN_OD, _CUP_PIN_ID, 8.5)
_CUP_PIN_CUP_MM3 = (
    math.pi / 4.0 * (_CUP_PIN_OD**2 - _CUP_PIN_ID**2) * (5.0 * 25.4 / 8.0)
    - _CUP_PIN_JOURNAL_MM3
)

# MHA-VN-047, McMaster 97431A260: the vendor replica's three prong arcs on its
# free diameter, atan(3/4) of the turn each (diag_build_97431A260's outline:
# the window prongs from 90 to 126.87 deg, the far one +/-atan(1/3)).
_RING_PRONG_SHARE = 3.0 * math.atan(0.75) / (2.0 * math.pi)


# Pattern instances are numbered by seed creation while the two backs and
# guides are numbered by insertion order, so their suffixes cross or interleave.
#
# The transgear rows (CONTRACT-paper-drive round 10, R9-68): every stock
# screw carries its thread at the basic major, and every receiving tap is
# cut at its tap drill, so each bound is the smooth annulus over the span
# where the major body lies inside the receiver.  Sizes and spans are
# literals, as the MHA-DT-032 row above, so no assembly re-keys on a transgear
# spec; test_pd_paper_drive_interference_contracts pins each to its owner.
# Pairs with NO row, modelled line to line or with clearance, which the gate
# reads as contact: the MHA-PD-017 hub's D-bore on the sleeve's Ø9 boss and
# D-flat, the MHA-VN-042 dowel in the arm's Ø3.175 ream, the sleeve and both
# bushings on the MHA-PD-023 pin (Ø3.9), the disc bore on the boss (Ø9), the
# knob journal in the plate bore (Ø8.5), the collar bore on the core
# (Ø6.35), the MHA-VN-037 pin in the collar's 1.8 slot, the MHA-VN-038 dowels
# in the T24's Ø2.5 holes, every screw in its clearance hole, and the
# MHA-PD-014 latch hook: its base on the bar's back face under the MHA-VN-043
# heads, their shanks through its Ø3.2 holes, and the MHA-VN-042 pin through
# its Ø3.3 pin hole.
_PAPER_DRIVE_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "vn-clamp-screw",
        range(1, 3),
        "sh-column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
        second_number=2,
    ),
    **_numbered_pairs(
        "vn-clamp-screw",
        range(3, 5),
        "sh-column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
    ),
    **_numbered_pairs(
        "vn-fillister-screw",
        range(1, 5),
        "pd-platen",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.5),
    ),
    **_numbered_pairs(
        "vn-fillister-screw",
        range(5, 15, 2),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
    ),
    **_numbered_pairs(
        "vn-fillister-screw",
        range(6, 15, 2),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
        second_number=2,
    ),
    # MHA-VN-046 guide-lock screws (R9-31, R9-48): seeds -1/-2, then the grid
    # -3..-8; each 9.525 shank passes the 2.0 lock plate into the guide's
    # rear through tap.
    **_numbered_pairs(
        "vn-guide-lock-screw",
        (1, 2, 4, 7),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 7.525),
    ),
    **_numbered_pairs(
        "vn-guide-lock-screw",
        (3, 5, 6, 8),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 7.525),
        second_number=2,
    ),
    # MHA-VN-040 #8-32 x 5/8 (vn_transgear_arm_plate_screw_spec; from the top of the
    # oval head's bevel, flush in the plate's countersink) through the 5.0
    # plate's Ø4.5 clearance, cut flush with the arm's front face (R9-44): the
    # cut length 12.9375 - 5.0 = the arm's 7.9375 in its #29 through tap.
    **_numbered_pairs(
        "vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 12.9375 - 5.0),
    ),
    # MHA-VN-041 (vn_transgear_pivot_screw_spec) in the support bar's blind #8-32
    # tap: its 4.7625 thread less the 1.1938 neck flat under the shoulder,
    # whose Ø3.02 stays inside the #29 drill -- the full thread plus the 45°
    # ramp back to the major (the MHA-DT-032 row's relief-and-lead-cone reading),
    # 3.5687 of overlap. The contract's engagement (R9-7, vendor neck) counts
    # full thread only: 4.7625 - 1.7653 = 2.9972 (0.72 D); the ramp adds
    # solid overlap with the tap but carries no thread.
    frozenset(("vn-transgear-pivot-screw-1", "pd-support-bar-1")): _smooth_annulus_limit_mm3(
        4.1656, 3.454, 4.7625 - 1.1938
    ),
    # MHA-VN-043 #4-40 x 3/8 (vn_latch_hook_bracket_screw_spec) through the
    # MHA-PD-014 hook's 0.8 base (Ø3.2 clearance): 9.525 - 0.8 = 8.725 in the
    # support bar's #43 taps.
    **_numbered_pairs(
        "vn-latch-hook-bracket-screw",
        range(1, 3),
        "pd-support-bar",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 9.525 - 0.8),
    ),
    # MHA-PD-023 (pd_transgear_pin_spec, Ø3.900) pressed through the arm's Ø3.874
    # ream (pd_transgear_arm_geometry) over the whole 7.9375 stock: the press.
    frozenset(("pd-transgear-pin-1", "pd-transgear-arm-1")): _smooth_annulus_limit_mm3(
        3.9, 3.874, 7.9375
    ),
    # MHA-PD-020 (pd_transgear_pivot_spacer_spec, Ø4.727 ream) pressed on the
    # MHA-VN-041 Ø4.7625 shoulder over its whole 5.5 length (R9-71): the press.
    frozenset(("pd-transgear-pivot-spacer-1", "vn-transgear-pivot-screw-1")): (
        _smooth_annulus_limit_mm3(4.7625, 4.727, 5.5)
    ),
    # MHA-VN-047 (vn_transgear_retaining_ring_spec) in the MHA-PD-023 groove: the
    # vendor replica is the ring as McMaster ships it, its prongs on the
    # Ø2.8956 free diameter, 0.0254 inside the Ø2.9464 groove floor: the grip,
    # over the prong arcs (above) and the 0.635 thickness.  The prong-corner
    # fillets only shorten the arcs: run 20261002T153039266Z read 0.03591
    # over the three prongs (assembly:paper_drive), 0.72 of this bound.
    frozenset(("vn-transgear-retaining-ring-1", "pd-transgear-pin-1")): _RING_PRONG_SHARE
    * _smooth_annulus_limit_mm3(2.9464, 2.8956, 0.635),
    # MHA-VN-039 #0-80 x 1/4 (vn_transgear_disc_screw_spec) through the hub
    # flange's Ø1.7 clearance into the disc's 3/64 taps (pd_rack_pinion_spec),
    # cut at assembly (R9-47) to 5.3 under the head: 5.3 - 2.4 = 2.9 of the
    # 3.0 face.
    **_numbered_pairs(
        "vn-transgear-disc-screw",
        range(1, 4),
        "pd-rack-pinion",
        _smooth_annulus_limit_mm3(1.524, 1.191, 5.3 - 2.4),
    ),
    # MHA-VN-048 through the knob shaft's journal and the cup (above).
    frozenset(("vn-transgear-knob-cup-pin-1", "pd-transgear-knob-shaft-1")): 1.10
    * _CUP_PIN_JOURNAL_MM3,
    frozenset(("vn-transgear-knob-cup-pin-1", "pd-transgear-knob-cup-1")): 1.10
    * _CUP_PIN_CUP_MM3,
    # Seats modelled line to line that the gate read as solid overlap on run
    # 20261001T035353825Z (assembly:paper_drive, R9-35): each MHA-VN-040 oval
    # head in its 82-degree countersink (0.00809 mm^3).  Sub-micron slivers
    # of coincident faces; the observed reading plus ten percent, so a head
    # sunk even 1 um into its seat (~0.05 mm^3) still fails.
    **_numbered_pairs(
        "vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm-plate",
        1.10 * 0.00809042475,
    ),
    # MHA-PD-013's 1/4-20 tap drill 5.105 (pd_transgear_thumbnut_spec) on MHA-PD-008's
    # Ø6.22 thread blank at the nominal collar setting: the tip 23.9 in front
    # of F, the nut seated on the collar's pilot (R9-70), 6.2 (collar set,
    # pd_transgear_drive_collar_spec) + 2.9 (the fitted pilot) in front of F, so
    # 23.9 - 6.2 - 2.9 = 14.8, all on the blank (it starts 7.5 in front of F,
    # behind the nut's seat at 9.1).
    frozenset(
        ("pd-transgear-thumbnut-1", "pd-transgear-knob-shaft-1")
    ): _smooth_annulus_limit_mm3(6.22, 5.105, 23.9 - 6.2 - 2.9),
    # The cross pin's whole tube chord through the core (above).
    frozenset(("vn-transgear-collar-cross-pin-1", "pd-transgear-knob-shaft-1")): 1.10
    * _CROSS_PIN_CORE_MM3,
    # The two MHA-VN-038 dowels pressed into the MHA-PD-022 collar's through reams,
    # the crank-seat twin (the collar's PIN_HOLE_DIA is the seat interface's
    # DRIVE_PIN_HOLE_DIA): the pin's length behind the seat face.
    **_numbered_pairs(
        "vn-transgear-knob-drive-pin",
        range(1, 3),
        "pd-transgear-drive-collar",
        _smooth_annulus_limit_mm3(
            _SEAT_PIN_DIA, _SEAT_PIN_HOLE_DIA, _KNOB_SEAT_PIN_DEPTH
        ),
    ),
}

# The cone-platform pivot screw now carries its full McMaster #10-24 thread
# envelope. Bound its exact nested tap engagement by the same conservative
# smooth-annulus contract as every other migrated stock thread.
_HARMONIC_ANALYZER_ALLOWED_PAIRS = {
    # Two #2-56 x 1/4 screws seat on the shallow counterbore floors.
    # Only thread/lever overlap is allowed; the bracket must remain clear.
    **_numbered_pairs(
        "mg-magnifier-1/vn-magnifying-bracket-screw",
        range(1, 3),
        "sm-summing-1/sm-summing-lever",
        _smooth_annulus_limit_mm3(
            _BRACKET_SCREW_MAJOR_DIA, _BRACKET_TAP_DRILL_DIA, _BRACKET_SCREW_ENGAGEMENT
        ),
    ),
    **_numbered_pairs(
        "ch-channel-1/vn-spring-hook",
        range(1, sm_summing_lever_spec.HOLE_COUNT + 1),
        "sm-summing-1/sm-summing-lever",
        _CHANNEL_ANCHOR_THREAD_LIMIT,
    ),
    frozenset(
        (
            "fr-frame-1/fr-harmonic-base-1",
            "dt-drive-train-1/vn-cone-pivot-screw-1",
        )
    ): _smooth_annulus_limit_mm3(4.826, 3.797, 9.525),
    **_numbered_pairs(
        "dt-drive-train-1/vn-cone-lock-knob",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(6.35, 5.105, 12.7),
    ),
    **_numbered_pairs(
        "dt-drive-train-1/vn-swing-stop-screw",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            _STOP_SHANK_DIA, TAP_DRILL_MM[_STOP_THREAD], _STOP_EMBED_LEN
        ),
    ),
    # Rule 12 (audit E10): the 31.75 #8-32 x 1-1/4 block screws pass the
    # 20.5 pinion block and engage 11.25 of the base seat.
    **_numbered_pairs(
        "dt-drive-train-1/vn-slotted-screw",
        range(1, 5),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 31.75 - 20.5),
    ),
    **_numbered_pairs(
        "dt-drive-train-1/vn-foot-screw",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 8.725),
    ),
    # U34c: the #8-32 x 3/4 (19.05) MHA-VN-032 hold-downs pass the 5.0 pedestal
    # ledge and engage 14.05 of the transferred base seats.
    **_numbered_pairs(
        "dt-drive-train-1/vn-pedestal-hold-down-screw",
        range(1, 3),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            4.1656, 3.454, _PEDESTAL_SCREW_ENGAGEMENT
        ),
    ),
    **_numbered_pairs(
        "ch-channel-1/vn-frame-side-screw",
        range(1, 3),
        "fr-frame-1/fr-top-frame",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.6624),
    ),
    # #743 PR2: the four #8-32 x 3/4 (19.05) MHA-VN-032 rocker-bracket hold-downs
    # pass the 6.0 bracket foot and engage 13.05 of the support rail's
    # transferred seats. Literals, like the rows above, so every assembly does
    # not re-key on the rocker bank's layout; test_rocker_bracket_seat_layout
    # pins them to rocker_bracket_seat_layout.
    **_numbered_pairs(
        "ch-channel-1/vn-pedestal-hold-down-screw",
        range(1, 5),
        "fr-frame-1/fr-rocker-arm-support",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 19.05 - 6.0),
    ),
}

# The MHA-CH-011 bar pivot pins (ch_bar_pivot_pin_spec), Ø1.984375 drill rod
# pressed into each MHA-CH-001 bar's Ø1.968 top-pin ream through both
# top-notch cheeks: 6.35 bar less the 3.20 notch. Channel j's pin and bar are
# both its (j + 1)th instance (build_ch_channel_assembly inserts one pin per
# channel in channel order; _copied_chain_instances pins the bar's number).
# Literals, like the rows above, so every assembly does not re-key on the pin
# spec; test_ch_bar_pivot_fit pins them to it.
BAR_PIVOT_PIN_PRESS = (1.984375, 1.968, 6.35 - 3.20)
# The MHA-CH-010 rod pivot pins (ch_rod_pivot_pin_spec), the same drill rod
# pressed into each MHA-CH-003 rod's Ø1.968 fork ream through both tines:
# 6.075 fork less the 2.625 slot (user ruling 2026-10-09, PR #1292 review F1).
# Channel j's pin and rod are both its (j + 1)th instance, as the bar pin's
# are; test_ch_rod_pivot_fit pins the literals to the pin spec.
ROD_PIVOT_PIN_PRESS = (1.984375, 1.968, 6.075 - 2.625)
_CHANNEL_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "ch-bar-pivot-pin",
        range(1, 21),
        "ch-amplitude-bar",
        _smooth_annulus_limit_mm3(*BAR_PIVOT_PIN_PRESS),
        second_number=None,
    ),
    **_numbered_pairs(
        "ch-rod-pivot-pin",
        range(1, 21),
        "ch-connecting-rod",
        _smooth_annulus_limit_mm3(*ROD_PIVOT_PIN_PRESS),
        second_number=None,
    ),
}

_BY_ASSEMBLY: dict[str, Mapping[frozenset[str], float]] = {
    "ch-channel": _CHANNEL_ALLOWED_PAIRS,
    "dt-drive-train": _DRIVE_TRAIN_ALLOWED_PAIRS,
    "fr-frame": _FRAME_ALLOWED_PAIRS,
    "mg-magnifier": _MAGNIFIER_ALLOWED_PAIRS,
    "sm-summing": _SUMMING_ALLOWED_PAIRS,
    "pn-pen": _PEN_ALLOWED_PAIRS,
    "pd-paper-drive": _PAPER_DRIVE_ALLOWED_PAIRS,
    "ha-harmonic-analyzer": _HARMONIC_ANALYZER_ALLOWED_PAIRS,
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    return _BY_ASSEMBLY.get(name, {})

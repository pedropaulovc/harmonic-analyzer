"""Explicit, volume-bounded interference-fit contracts for assembly gates.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Explicit ``@Role:N`` selectors are resolved to
observed native names only after file, selected member and reference readback.
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
from fr_harmonic_base_spec import POCKET_SKIN as _BASE_DECK_SKIN
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
from fr_vn_frame_cross_screw_spec import SHANK_DIA as _FRAME_CROSS_DIA
from fr_vn_frame_cross_screw_spec import SHANK_LEN as _FRAME_CROSS_LENGTH
from fr_vn_frame_cross_screw_spec import THREAD as _FRAME_CROSS_THREAD
from _hole_spec import TAP_DRILL_MM

# Only nominal penetration is shared across assemblies, not the part's full
# drawing/placement recipe (which depends on the cone/channel station grid).
from dt_post_mount_stack import POST_SCREW_ENGAGEMENT_NOMINAL as _POST_SCREW_ENGAGEMENT
from sh_vn_arbor_set_screw_spec import LENGTH as _ARBOR_SET_SCREW_LENGTH
from sh_vn_arbor_set_screw_spec import THREAD as _ARBOR_SET_SCREW_THREAD
from dt_swing_stop_screw_spec import EMBED_LEN as _STOP_EMBED_LEN
from dt_swing_stop_screw_spec import SHANK_DIA as _STOP_SHANK_DIA
from dt_swing_stop_screw_spec import THREAD as _STOP_THREAD
from _sprocket_seat_geometry import DRIVE_PIN_DIA as _SEAT_PIN_DIA
from _sprocket_seat_geometry import DRIVE_PIN_HOLE_DIA as _SEAT_PIN_HOLE_DIA
from dt_vn_crank_seat_drive_pin_spec import PRESS_DEPTH as _CRANK_SEAT_PIN_DEPTH
from pd_vn_transgear_knob_drive_pin_spec import PRESS_DEPTH as _KNOB_SEAT_PIN_DEPTH
from magnifying_bracket_joint_layout import (
    ENGAGEMENT as _BRACKET_SCREW_ENGAGEMENT,
    SCREW_MAJOR_DIA as _BRACKET_SCREW_MAJOR_DIA,
    TAP_DRILL_DIA as _BRACKET_TAP_DRILL_DIA,
)
from dt_pinion_pivot_block_geometry import BLOCK_HEIGHT as _PINION_BLOCK_HEIGHT
from dt_vn_slotted_screw_spec import SHANK_DIA as _BLOCK_SCREW_DIA
from dt_vn_slotted_screw_spec import SHANK_LEN as _BLOCK_SCREW_LENGTH
from dt_vn_slotted_screw_spec import THREAD as _BLOCK_SCREW_THREAD


def _smooth_annulus_limit_mm3(
    major_d: float,
    tap_d: float,
    length: float,
) -> float:
    """Return a 10%-headroom bound for smooth thread-envelope engagement."""
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _occurrence(prefix: str, number: int) -> str:
    """Append an ordinal to an explicit role prefix or a native family."""
    return f"{prefix}{number}" if prefix.endswith(":") else f"{prefix}-{number}"


def _numbered_pairs(
    first_stem: str,
    numbers: Iterable[int],
    second_stem: str,
    limit: float,
    *,
    second_number: int | None = 1,
) -> dict[frozenset[str], float]:
    """Build exact native or explicit ``@Role:N`` pairs, retaining each bound."""
    return {
        frozenset(
            (
                _occurrence(first_stem, number),
                _occurrence(
                    second_stem, number if second_number is None else second_number
                ),
            )
        ): limit
        for number in numbers
    }


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
# materially deeper insertion fails.  The cup-tip adjuster makes its intended
# thrust contact with the shaft end at 0.13 mm3: the 45 deg cup's analytic
# (2/3)*pi*r^3 for the 0.79 stub (0.131), re-read at 0.1309 by the
# mha092-r3-8b1b drive-train leaf on drawing-guidelines.md rule 18 (thread engagement) E11's 94025A164.  The 1/16 in
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
# The MHA-DT-VN-60 hold-down (91251A108 #4-40 x 3/8 SHCS) up through the platform
# into the MHA-DT-21 foot tap: 5.6585 mm3, read by the first prism-block
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
    frozenset(("sh-vn-brass-fillister-screw-1", "dt-crank-arm-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.33
    ),
    # MHA-DT-32 #6-32 major in the arm's #36 tap drill: the full thread past the
    # 1.5 relief (6.5 of the 8.0 arm) plus its 0.5 lead cone.  The size is
    # named here, not imported from dt_crank_handle_pivot_screw_spec, so every
    # assembly's recipe stays clear of the handle specs; the MHA-DT-32 tests pin
    # it to that spec's THREAD_SIZE.
    frozenset(("dt-crank-handle-pivot-screw-1", "dt-crank-arm-1")): _smooth_annulus_limit_mm3(
        THREAD_MAJOR_MM["#4-40"], TAP_DRILL_MM["#4-40"], 7.0
    ),
    # drawing-guidelines.md rule 18 (thread engagement) E11: #10-32 94025A164 in the tapped block, observed above.
    frozenset(
        ("dt-vn-cone-tip-adjuster-1", "dt-cone-tip-block-1")
    ): _TIP_ADJUSTER_GATE_LIMIT_MM3,
    frozenset(
        ("dt-vn-cone-tip-pinch-screw-1", "dt-cone-tip-block-1")
    ): _TIP_PINCH_GATE_LIMIT_MM3,
    frozenset(
        ("dt-vn-cone-tip-block-screw-1", "dt-cone-tip-block-1")
    ): _TIP_HOLDDOWN_GATE_LIMIT_MM3,
    frozenset(
        ("dt-vn-cone-tip-adjuster-1", "dt-cone-gear-shaft-1")
    ): _ADJUSTER_THRUST_GATE_LIMIT_MM3,
    # U30 (I22): each MHA-DT-VN-61 (1/4-20 MSC 40923906, major 6.35) in its #7
    # (5.105) MHA-DT-20 tap, as deep as the cut length runs past the post's
    # grip (the counterbore floor).  The smooth-annulus upper bound until the
    # first drive-train build observes the helical overlap.
    **_numbered_pairs(
        "dt-vn-post-mount-screw",
        (1, 2),
        "dt-cone-swing-platform",
        _smooth_annulus_limit_mm3(6.35, 5.105, _POST_SCREW_ENGAGEMENT),
    ),
    # #743 Q3: the MHA-DT-VN-64 #4-40 apex set screw in each pedestal's crown tap,
    # bounded over its whole length (the crown holds a little less: the cup
    # point stands in the bore clearance and the socket stands
    # cylinder_bank_layout.SET_SCREW_SOCKET_PROUD over the apex). Pedestal and
    # screw are both placed south first, so their suffixes match. #911: this
    # smooth-annulus bound serves the first build only -- re-pin it to the
    # measured overlap x 1.10 from the first drive_train leaf, as #838 did for
    # the tip-block pairs.
    **_numbered_pairs(
        "sh-vn-arbor-set-screw",
        range(1, 3),
        "dt-arbor-pedestal",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD],
            TAP_DRILL_MM[_ARBOR_SET_SCREW_THREAD],
            _ARBOR_SET_SCREW_LENGTH,
        ),
        second_number=None,
    ),
    # The two MHA-DT-VN-67 dowels pressed into MHA-DT-11's seat-collar holes
    # (ø2.38125 pin in a ø2.38 ream over the press depth): the press fit.
    **_numbered_pairs(
        "dt-vn-crank-seat-drive-pin",
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
        "fr-vn-lag-screw",
        range(1, 5),
        "fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_HOLD_DOWN_THREAD],
            _HOLD_DOWN_TAP_DRILL_DIA,
            _HOLD_DOWN_ENGAGEMENT,
        ),
    ),
    **_numbered_pairs(
        "fr-vn-frame-cross-screw",
        range(1, 5),
        "fr-harmonic-base",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    **_numbered_pairs(
        "fr-vn-frame-cross-screw",
        range(5, 9),
        "fr-top-frame",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    # MHA-FR-VN-52 / 91410A540 1/4-20 (major 6.35, #7 drill 5.105): thread from
    # the hub's spot face, 21.0 from the bore axis (fr_top_frame_spec
    # HUB_SET_SPOT_FROM_AXIS), to the cup tip 8.15 from the axis (0.21 clear of
    # the gooseneck's O15.875 sleeve): 12.5 to the O17 bore wall plus the tip's 0.35 into the bore.
    frozenset(("fr-vn-gooseneck-set-screw-1", "fr-top-frame-1")): _smooth_annulus_limit_mm3(
        6.35, 5.105, 12.85
    ),
    # Four nameplate corners: 6.35-mm stock shank through the 1.5-mm plate.
    **_numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(1, 5),
        "fr-harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.85),
    ),
}
# Independent runtime oracles: importing the magnifier's fit/pose modules here
# would re-key every assembly for an unrelated fixture station or groove edit.
# test_mg_fixture_installation pins these triples to their geometry owners.
# The nominal smooth major/tap-drill annulus through the entire neck is the
# cosmetic-thread overlap. The incomplete root runout is wholly outside it.
_MG_LEVER_THREAD_TRIPLE_MM = (6.35, 5.105, 12.5)
_MG_FIXTURE_THREAD_TRIPLE_MM = (2.8448, 2.261, 10.1)
# #1559 clamp (MHA-MG-02): the 91882A221 #4-40 shank in the thumb tap's
# Ø2.261 drill from the top face to the lever-bore top (THUMB_TAP_LENGTH 6.30).
_MG_CLAMP_THUMB_TRIPLE_MM = (2.8448, 2.261, 6.3)
# The vertical rod's #4-40 end (modelled at the 2.845 major) in the clamp's
# bottom-face Ø2.261 tap drill. Envelope 6.0 = ROD_THREAD_LEN - RELIEF_WIDTH:
# the full-major section from the tip to the relief, which also covers the tip
# chamfer (its cone lies inside that cylinder); the Ø1.85 MAX relief is smaller
# than the drill and overlaps nothing.
_MG_ROD_THREAD_TRIPLE_MM = (2.845, 2.261, 6.0)

_MG_LEVER_THREAD_LIMIT = _smooth_annulus_limit_mm3(*_MG_LEVER_THREAD_TRIPLE_MM)
# Only the major/thread-drill annulus from the spigot face to the rod-bore
# breakout (10.1 mm), not the tangent screw tip or screw/rod overlap, is allowed.
_MG_FIXTURE_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    *_MG_FIXTURE_THREAD_TRIPLE_MM
)
_MG_CLAMP_THUMB_LIMIT = _smooth_annulus_limit_mm3(*_MG_CLAMP_THUMB_TRIPLE_MM)
_MG_ROD_THREAD_LIMIT = _smooth_annulus_limit_mm3(*_MG_ROD_THREAD_TRIPLE_MM)

_MAGNIFIER_ALLOWED_PAIRS = {
    # 1.25 in screw - 9.5 wheel bar - 17.4 front arc - 0.5 grip gap (the back
    # arc's mating face stops short of the column axis,
    # sh_column_clamp_back_geom.GRIP_OFFSET) = 4.35 in the back arc's tap.
    **_numbered_pairs(
        "sh-vn-clamp-screw",
        range(1, 3),
        "sh-column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 4.35),
    ),
    frozenset(("sh-vn-thumb-screw-1", "mg-magnifying-clamp-1")): _MG_CLAMP_THUMB_LIMIT,
    frozenset(
        ("mg-magnifying-vertical-rod-1", "mg-magnifying-clamp-1")
    ): _MG_ROD_THREAD_LIMIT,
    # MHA-MG-07 drill-rod pin (Ø4.7625, mg_wheel_axle_spec.PIN_DIA) pressed in
    # the wheel bar's Ø4.7371 reamed bore (mg_wheel_bar_geom.AXLE_BORE_DIA)
    # over at most 9.0 of the bar's 9.5 depth (its back end 0.60 sunk at
    # nominal, mg_wheel_axle_spec.BACK_Y): the press.
    frozenset(("mg-wheel-axle-1", "mg-wheel-bar-1")): _smooth_annulus_limit_mm3(
        4.7625, 4.7371, 9.0
    ),
    frozenset(("sh-vn-thumb-screw-2", "mg-output-fixture-1")): _MG_FIXTURE_THREAD_LIMIT,
    frozenset(
        ("mg-magnifying-lever-1", "mg-magnifying-bracket-1")
    ): _MG_LEVER_THREAD_LIMIT,
}

_COUNTER_ANCHOR_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    ANCHOR_9490T1.thread_major_dia_mm,
    blind_cut_dia_mm(sm_summing_lever_spec.COUNTER_HOLE_SPEC),
    sm_summing_lever_spec.ANCHOR_H,
)
_CHANNEL_ANCHOR_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    ANCHOR_9489T111.thread_major_dia_mm,
    blind_cut_dia_mm(sm_summing_lever_spec.HOLE_SPEC),
    sm_summing_lever_spec.COEFFICIENT_T,
)
# MHA-SM-VN-52 #10-24 cut hex bolt (92314A253) in each knife mount's #25 tap
# drill over its 8.9173 nominal reach: 46.70 cut length less the 36.50 grip
# to the faced top and the 96659A104 washer's 1.2827 nominal thickness. Keep
# this literal, test-pinned to build_sm_summing_assembly, to avoid broad
# recipe cache keys.
_KNIFE_HANGER_REACH = 8.9173
# Each MHA-SM-VN-53 dowel pressed up to the floor of its Ø3.175 ream in the
# MHA-FR-02 crossbar's faced underside (owner ruling 2026-10-24, T+H3;
# sm_vn_knife_mount_dowel_spec.PRESS_HOLE_DIA, band +0/-0.010: smallest
# 3.165), its largest catalogue diameter 3.18262 over its 12.0 press depth
# (sm_vn_knife_mount_dowel_spec.DIA_MAX, PRESS_DEPTH).  All three are
# literals, test-pinned to their owners like _KNIFE_HANGER_REACH, so a
# crossbar or dowel edit does not re-key every assembly.  The models are line
# to line, so this bounds the press at its print-worst: the largest catalogue
# pin in the smallest ream, the whole depth.  The dowels belong to the summing
# subassembly and the crossbar to the frame's, so the pairs are checked at the
# top level (_HARMONIC_ANALYZER_ALLOWED_PAIRS); in the summing subassembly
# each pin slips in its knife mount's round hole or slot, with no overlap.
_KNIFE_DOWEL_HOLE_MIN = 3.165
_KNIFE_DOWEL_DIA_MAX = 3.18262
_KNIFE_DOWEL_PRESS_DEPTH = 12.0
_KNIFE_DOWEL_PRESS_LIMIT = _smooth_annulus_limit_mm3(
    _KNIFE_DOWEL_DIA_MAX, _KNIFE_DOWEL_HOLE_MIN, _KNIFE_DOWEL_PRESS_DEPTH
)
# MHA-SM-04 1/4-28 in the #3 drill of the blind 1/4-28 tap in MHA-SM-01's
# solid end piece, from the arm-end counterbore floor to the screw's tip,
# which the model seats at the free gap short of the tap's full thread
# (round(min(sm_gooseneck_spring_joint.SCREW_REACH, TAP_THREAD_DEPTH) -
# COUNTERBORE_DEPTH, 2)): the screw's major clears the Ø7.00 counterbore. A
# literal, test-pinned to its owners like _KNIFE_HANGER_REACH, so a screw or
# gooseneck edit does not re-key every assembly that imports this module.
_GOOSENECK_THREAD_LENGTH = 11.84
# Bearing seats are exact face contacts, NOT interference fits. Zero volume
# permits a reported coincidence but no unmeasured kernel sliver allowance.
_KNIFE_HANGER_SEAT_OVERLAP_LIMIT = 0.0
_SUMMING_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "sm-vn-knife-hanger-stud",
        range(1, 3),
        "sm-knife-mount",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["#10-24"], TAP_DRILL_MM["#10-24"], _KNIFE_HANGER_REACH
        ),
        second_number=None,
    ),
    **_numbered_pairs(
        "sm-vn-knife-hanger-stud",
        range(1, 3),
        "sm-vn-knife-hanger-washer",
        _KNIFE_HANGER_SEAT_OVERLAP_LIMIT,
        second_number=None,
    ),
    frozenset(("sm-vn-boss-hook-1", "sm-summing-lever-1")): _COUNTER_ANCHOR_THREAD_LIMIT,
    # Spring/support contact has no allowance and remains independently gated.
    frozenset(("sm-gooseneck-spring-screw-1", "sm-gooseneck-1")): (
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["1/4-28"], TAP_DRILL_MM["1/4-28"], _GOOSENECK_THREAD_LENGTH
        )
    ),
}

_PEN_ALLOWED_PAIRS = {
    # #4-40 thumb screw through the stirrup's 6.0 bottom rail (pn_pen_frame_spec.RAIL_END).
    frozenset(("pn-vn-pen-set-screw-1", "pn-pen-frame-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 6.0
    ),
    # #4-40 x 3/16 rod set screw wholly in the v-block's tap (pn_vn_pen_rod_set_screw_spec.LENGTH).
    frozenset(("pn-vn-pen-rod-set-screw-1", "pn-pen-v-block-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 4.7625
    ),
    # #0-80 adjuster stud threaded 3.2 into the rod top (pn_pen_rod_spec.STUD_ENGAGEMENT).
    frozenset(("pn-pen-adjust-screw-1", "pn-pen-rod-1")): _smooth_annulus_limit_mm3(
        1.524, 1.191, 3.2
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


# MHA-PD-VN-62 (98296A031), a 1/16-in tube with a 0.012-in wall, 5/8 long, lies
# diametrally across the MHA-PD-08 journal's rear end and the MHA-PD-16 cup ring,
# in a hole match-drilled through both at assembly and not modelled (R9-70,
# K-1): its chord through the journal, and the rest of its length in the cup
# (its ends stay inside the cup's O.D.).
_CUP_PIN_OD = 25.4 / 16.0
_CUP_PIN_ID = _CUP_PIN_OD - 2.0 * 0.012 * 25.4
_CUP_PIN_JOURNAL_MM3 = _cross_pin_overlap_mm3(_CUP_PIN_OD, _CUP_PIN_ID, 6.0)
_CUP_PIN_CUP_MM3 = (
    math.pi / 4.0 * (_CUP_PIN_OD**2 - _CUP_PIN_ID**2) * (5.0 * 25.4 / 8.0)
    - _CUP_PIN_JOURNAL_MM3
)

# MHA-PD-VN-61, McMaster 97431A260: the vendor replica's three prong arcs on its
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
# literals, as the MHA-DT-32 row above, so no assembly re-keys on a transgear
# spec; test_pd_paper_drive_interference_contracts pins each to its owner.
# Pairs with NO row, modelled line to line or with clearance, which the gate
# reads as contact: the MHA-PD-17 hub's D-bore on the sleeve's Ø9 boss and
# D-flat, the MHA-PD-VN-58 dowel in the arm's Ø3.175 ream, the sleeve and both
# bushings on the MHA-PD-23 pin (Ø3.9), the disc bore on the boss (Ø9), the
# knob journal in the plate bore (Ø6), the D-collar bore on the core
# (Ø4.9), the MHA-PD-VN-54 dowels in the T24's Ø2.5 holes, every screw in its
# clearance hole, and the MHA-PD-14 latch hook: its base on the bar's back
# face under the MHA-PD-VN-59 heads, their shanks through its Ø3.2 holes, and
# the MHA-PD-VN-58 pin through its Ø3.3 pin hole.
_PAPER_DRIVE_ALLOWED_PAIRS = {
    # The bar-clamp screws: the receiver length past bar, front arc and the
    # 0.5 grip gap (build_pd_paper_drive_assembly's clamp stack).
    **_numbered_pairs(
        "sh-vn-clamp-screw",
        range(1, 3),
        "sh-column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.5124),
        second_number=2,
    ),
    **_numbered_pairs(
        "sh-vn-clamp-screw",
        range(3, 5),
        "sh-column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.5124),
    ),
    # MHA-PD-VN-65 #2-56 clip screws: 6.35 shank - 0.8 clip sheet = 5.55 in the
    # platen's through tap (3.85 plate + 1.70 rear boss).
    **_numbered_pairs(
        "pd-vn-platen-clip-screw",
        range(1, 5),
        "pd-platen",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["#2-56"], TAP_DRILL_MM["#2-56"], 5.55
        ),
    ),
    # MHA-PD-VN-52 guide screws: seed -1, then the grid -2..-10, alternating
    # between the two guide rails.
    **_numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(1, 11, 2),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
    ),
    **_numbered_pairs(
        "sh-vn-brass-fillister-screw",
        range(2, 11, 2),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.4178),
        second_number=2,
    ),
    # MHA-PD-VN-60 guide-lock screws (R9-31, R9-48): seeds -1/-2, then the grid
    # -3..-8; each 9.525 shank passes the 1.5875 (1/16 sheet) lock plate into
    # the guide's rear through tap.
    **_numbered_pairs(
        "pd-vn-guide-lock-screw",
        (1, 2, 4, 7),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 7.9375),
    ),
    **_numbered_pairs(
        "pd-vn-guide-lock-screw",
        (3, 5, 6, 8),
        "pd-platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 7.9375),
        second_number=2,
    ),
    # MHA-PD-VN-56 #8-32 x 5/8 (pd_vn_transgear_arm_plate_screw_spec; from the top of the
    # oval head's bevel, flush in the plate's countersink) through the 5.0
    # plate's Ø4.5 clearance, cut flush with the arm's front face (R9-44): the
    # cut length 12.9375 - 5.0 = the arm's 7.9375 in its #29 through tap.
    **_numbered_pairs(
        "pd-vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 12.9375 - 5.0),
    ),
    # MHA-PD-VN-57 (pd_vn_transgear_pivot_screw_spec, 90325A174 faced to fit) in the
    # support bar's THROUGH #8-32 tap: its fitted 9.15 thread less the 1.1938
    # neck flat under the shoulder, whose Ø3.02 stays inside the #29 drill --
    # the full thread plus the 45° ramp back to the major (the MHA-DT-32 row's
    # relief-and-lead-cone reading), 7.9562 of overlap; the faced tip stands
    # inside the front face. The contract's engagement (transgear_hanger_joints)
    # counts full thread only, less one pitch at the faced tip.
    frozenset(
        ("pd-vn-transgear-pivot-screw-1", "pd-support-bar-1")
    ): _smooth_annulus_limit_mm3(4.1656, 3.454, 9.15 - 1.1938),
    # MHA-SH-VN-52 #4-40 x 3/8 (pd_latch_hook_bracket_screw_spec) through the
    # MHA-PD-14 hook's 0.8 base (Ø3.2 clearance): 9.525 - 0.8 = 8.725 in the
    # support bar's #43 taps.
    **_numbered_pairs(
        "sh-vn-fillister-screw-90280a108",
        range(1, 3),
        "pd-support-bar",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 9.525 - 0.8),
    ),
    # MHA-PD-23 (pd_transgear_pin_spec, Ø3.900) pressed through the arm's Ø3.874
    # ream (pd_transgear_arm_geometry) over the whole 7.9375 stock: the press.
    frozenset(("pd-transgear-pin-1", "pd-transgear-arm-1")): _smooth_annulus_limit_mm3(
        3.9, 3.874, 7.9375
    ),
    # The two MHA-PD-VN-64 dowels (pd_vn_transgear_arm_plate_locating_pin_spec,
    # Ø2.0 model) pressed into the arm's Ø1.995 through reams
    # (pd_transgear_arm_geometry); _transgear_arm_plate_locating_interface
    # owns the 1.70 proud set in their 6.0 - 1.70 insertion: the press.
    # They slip in the plate's Ø2.015 holes, so that pair has no row.
    **_numbered_pairs(
        "pd-vn-transgear-arm-plate-locating-pin",
        range(1, 3),
        "pd-transgear-arm",
        _smooth_annulus_limit_mm3(2.0, 1.995, 6.0 - 1.70),
    ),
    # MHA-PD-20 (pd_transgear_pivot_spacer_spec, Ø4.727 ream) pressed on the
    # MHA-PD-VN-57 Ø4.7625 shoulder over its whole 5.0 length (R9-71): the press.
    frozenset(("pd-transgear-pivot-spacer-1", "pd-vn-transgear-pivot-screw-1")): (
        _smooth_annulus_limit_mm3(4.7625, 4.727, 5.0)
    ),
    # MHA-PD-VN-61 (pd_vn_transgear_retaining_ring_spec) in the MHA-PD-23 groove: the
    # vendor replica is the ring as McMaster ships it, its prongs on the
    # Ø2.8956 free diameter, 0.0254 inside the Ø2.9464 groove floor: the grip,
    # over the prong arcs (above) and the 0.635 thickness.  The prong-corner
    # fillets only shorten the arcs: run 20261002T153039266Z read 0.03591
    # over the three prongs (assembly:paper_drive), 0.72 of this bound.
    frozenset(("pd-vn-transgear-retaining-ring-1", "pd-transgear-pin-1")): _RING_PRONG_SHARE
    * _smooth_annulus_limit_mm3(2.9464, 2.8956, 0.635),
    # MHA-PD-VN-55 #0-80 x 1/4 (pd_vn_transgear_disc_screw_spec) through the hub
    # flange's Ø1.7 clearance into the disc's 3/64 taps (pd_rack_pinion_spec),
    # cut at assembly (R9-47) to 5.3 under the head: 5.3 - 2.4 = 2.9 of the
    # 3.0 face.
    **_numbered_pairs(
        "pd-vn-transgear-disc-screw",
        range(1, 4),
        "pd-rack-pinion",
        _smooth_annulus_limit_mm3(1.524, 1.191, 5.3 - 2.4),
    ),
    # MHA-PD-VN-62 through the knob shaft's journal and the cup (above).
    frozenset(("pd-vn-transgear-knob-cup-pin-1", "pd-transgear-knob-shaft-1")): 1.10
    * _CUP_PIN_JOURNAL_MM3,
    frozenset(("pd-vn-transgear-knob-cup-pin-1", "pd-transgear-knob-cup-1")): 1.10
    * _CUP_PIN_CUP_MM3,
    # Seats modelled line to line that the gate read as solid overlap on run
    # 20261001T035353825Z (assembly:paper_drive, R9-35): each MHA-PD-VN-56 oval
    # head in its 82-degree countersink (0.00809 mm^3).  Sub-micron slivers
    # of coincident faces; the observed reading plus ten percent, so a head
    # sunk even 1 um into its seat (~0.05 mm^3) still fails.
    **_numbered_pairs(
        "pd-vn-transgear-arm-plate-screw",
        range(1, 3),
        "pd-transgear-arm-plate",
        1.10 * 0.00809042475,
    ),
    # MHA-PD-13's #8-32 tap drill 3.454 on MHA-PD-08's Ø4.070 thread blank:
    # at the nominal fitted collar length 6.2, whose rear face reacts on F,
    # the nut seats on the pilot 2.9 in front of the wheel seat. The overlap
    # is 23.9 - 6.2 - 2.9 = 14.8, entirely on the blank, which starts 7.5
    # in front of F, behind the nut's seat at 9.1.
    frozenset(
        ("pd-transgear-thumbnut-1", "pd-transgear-knob-shaft-1")
    ): _smooth_annulus_limit_mm3(4.070, 3.454, 23.9 - 6.2 - 2.9),
    # The two MHA-PD-VN-54 dowels pressed into the MHA-PD-22 collar's through reams,
    # the crank-seat twin (the collar's PIN_HOLE_DIA is the seat interface's
    # DRIVE_PIN_HOLE_DIA): the pin's length behind the seat face.
    **_numbered_pairs(
        "pd-vn-transgear-knob-drive-pin",
        range(1, 3),
        "pd-transgear-drive-collar",
        _smooth_annulus_limit_mm3(
            _SEAT_PIN_DIA, _SEAT_PIN_HOLE_DIA, _KNOB_SEAT_PIN_DEPTH
        ),
    ),
    # Chain-mesh contact at the closing station: the MHA-PD-VN-66 connecting
    # link closes the chain at station 67, whose forward pin is pin 0 on the
    # T24's pitch circle, the same seated-chain mesh the gate allows every
    # MHA-SH-VN-50 InnerLink/OuterLink member on a mounted removable. The
    # separate connecting-link SKU remains excluded from the generic shared
    # native-member exemption: only this exact bounded pair is intentional.
    # Two bodies, 3.512 + 2.105 = 5.617 mm^3 on run 20261015T010201208Z
    # (assembly:pd_paper_drive); the reading plus ten percent, so a deeper
    # seat or a clash with any other part still fails.
    frozenset(("pd-transgear-removable-1", "pd-vn-chain-connecting-link-1")): 1.10
    * 5.61663709,
}

# The cone-platform pivot screw now carries its full McMaster #10-24 thread
# envelope. Bound its exact nested tap engagement by the same conservative
# smooth-annulus contract as every other migrated stock thread.
_HARMONIC_ANALYZER_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "sm-summing-1/sm-vn-knife-hanger-stud",
        range(1, 3),
        "sm-summing-1/sm-vn-knife-hanger-washer",
        _KNIFE_HANGER_SEAT_OVERLAP_LIMIT,
        second_number=None,
    ),
    **_numbered_pairs(
        "sm-summing-1/sm-vn-knife-hanger-washer",
        range(1, 3),
        "fr-frame-1/fr-top-frame",
        _KNIFE_HANGER_SEAT_OVERLAP_LIMIT,
    ),
    # Four MHA-SM-VN-53 dowels, two per knife mount, all in the one crossbar.
    **_numbered_pairs(
        "sm-summing-1/sm-vn-knife-mount-dowel",
        range(1, 5),
        "fr-frame-1/fr-top-frame",
        _KNIFE_DOWEL_PRESS_LIMIT,
    ),
    frozenset(
        ("mg-magnifier-1/sh-vn-thumb-screw-2", "mg-magnifier-1/mg-output-fixture-1")
    ): _MG_FIXTURE_THREAD_LIMIT,
    frozenset(
        (
            "mg-magnifier-1/mg-magnifying-vertical-rod-1",
            "mg-magnifier-1/mg-magnifying-clamp-1",
        )
    ): _MG_ROD_THREAD_LIMIT,
    frozenset(
        (
            "mg-magnifier-1/mg-magnifying-lever-1",
            "mg-magnifier-1/mg-magnifying-bracket-1",
        )
    ): _MG_LEVER_THREAD_LIMIT,
    # Two #2-56 x 1/4 screws seat on the flange's front face.
    # Only thread/lever overlap is allowed; the bracket must remain clear.
    **_numbered_pairs(
        "mg-magnifier-1/mg-vn-magnifying-bracket-screw",
        range(1, 3),
        "sm-summing-1/sm-summing-lever",
        _smooth_annulus_limit_mm3(
            _BRACKET_SCREW_MAJOR_DIA, _BRACKET_TAP_DRILL_DIA, _BRACKET_SCREW_ENGAGEMENT
        ),
    ),
    **_numbered_pairs(
        "ch-channel-1/ch-vn-spring-hook",
        range(1, sm_summing_lever_spec.HOLE_COUNT + 1),
        "sm-summing-1/sm-summing-lever",
        _CHANNEL_ANCHOR_THREAD_LIMIT,
    ),
    frozenset(
        (
            "fr-frame-1/fr-harmonic-base-1",
            "dt-drive-train-1/dt-vn-cone-pivot-screw-1",
        )
    ): _smooth_annulus_limit_mm3(4.826, 3.797, 9.525),
    **_numbered_pairs(
        "dt-drive-train-1/dt-vn-cone-lock-knob",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(6.35, 5.105, 12.7),
    ),
    **_numbered_pairs(
        "dt-drive-train-1/@SwingStopScrew:",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            _STOP_SHANK_DIA, TAP_DRILL_MM[_STOP_THREAD], _STOP_EMBED_LEN
        ),
    ),
    # Bound only the threaded material actually inside the base seat.
    **_numbered_pairs(
        "dt-drive-train-1/dt-vn-slotted-screw",
        range(1, 5),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            _BLOCK_SCREW_DIA,
            TAP_DRILL_MM[_BLOCK_SCREW_THREAD],
            _BLOCK_SCREW_LENGTH - _PINION_BLOCK_HEIGHT,
        ),
    ),
    **_numbered_pairs(
        "dt-drive-train-1/@FootScrew:",
        range(1, 2),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 8.725),
    ),
    # The unchanged #8-32 x 3/4 stock inserts 14.05 through the pedestal ledge.
    # Only the retained skin can overlap: the protruding tip is in pocket air.
    **_numbered_pairs(
        "dt-drive-train-1/dt-vn-pedestal-hold-down-screw",
        range(1, 3),
        "fr-frame-1/fr-harmonic-base",
        _smooth_annulus_limit_mm3(
            4.1656, 3.454, min(_PEDESTAL_SCREW_ENGAGEMENT, _BASE_DECK_SKIN)
        ),
    ),
    # The two #2-56 x 7/16 (11.1125) MHA-CH-VN-52 keeper foot screws: the head
    # sits flush in the 8.0 foot's 2.1082 counterbore, so 11.1125 - (8.0 -
    # 2.1082) = 5.2207 enters the top frame's tap (ch_fulcrum_keeper_spec).
    **_numbered_pairs(
        "ch-channel-1/ch-vn-frame-side-screw",
        range(1, 3),
        "fr-frame-1/fr-top-frame",
        _smooth_annulus_limit_mm3(2.1844, 1.778, 5.2207),
    ),
    # #743 PR2: the two #8-32 x 5/8 (15.875) MHA-CH-VN-57 rocker-bracket hold-downs
    # (one per bracket since the 2026-10-09 flip; 5/8 since owner Q13c) pass
    # the 6.0 bracket foot and engage 9.875 of the support's transferred seats.
    # Literals, like the rows above, so every assembly does not re-key on the
    # rocker bank's layout; test_rocker_bracket_seat_layout pins them to
    # rocker_bracket_seat_layout.
    **_numbered_pairs(
        "ch-channel-1/ch-vn-bracket-hold-down-screw",
        range(1, 3),
        "fr-frame-1/fr-rocker-arm-support",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 15.875 - 6.0),
    ),
}

# The MHA-CH-11 bar pivot pins (ch_bar_pivot_pin_spec), Ø1.984375 drill rod
# pressed into each MHA-CH-01 bar's Ø1.9558 (.077 in) top-pin ream through both
# top-notch cheeks: 6.35 bar less the 3.15 notch. Channel j's pin and bar are
# both its (j + 1)th instance (build_ch_channel_assembly inserts one pin per
# channel in channel order; _copied_chain_instances pins the bar's number).
# Literals, like the rows above, so every assembly does not re-key on the pin
# spec; test_ch_bar_pivot_fit pins them to it.
BAR_PIVOT_PIN_PRESS = (1.984375, 1.9558, 6.35 - 3.15)
# The MHA-CH-10 rod pivot pins (ch_rod_pivot_pin_spec), the same drill rod
# pressed into each MHA-CH-03 rod's Ø1.9558 fork ream through both tines:
# 6.075 fork less the 2.675 slot (user ruling 2026-10-09, PR #1292 review F1;
# slot widened from 2.625, #982).
# Channel j's pin and rod are both its (j + 1)th instance, as the bar pin's
# are; test_ch_rod_pivot_fit pins the literals to the pin spec.
ROD_PIVOT_PIN_PRESS = (1.984375, 1.9558, 6.075 - 2.675)
# The MHA-CH-VN-53 #4-40 apex set screws (user, 2026-10-10), one down through
# each MHA-CH-08 ear's arch (apex 9.80 over the bore since #1371) into its
# Ø6.5 bore, the tap cut at its drill. The thread's major envelope crosses no
# longer a metal column than the apex's height over the bore axis less the
# bore's height at the envelope's edge, so the smooth annulus over that column
# bounds the overlap; the cup on the modelled shaft flat is contact, as the
# arbor's screws on the arbor. Screw n is placed with bracket n (south first).
# Literals (apex over the bore, bore), like the rows above, so every assembly
# does not re-key on the bracket spec; test_ch_channel_assembly_drawing pins
# them to ch_pivot_bracket_spec. #911: re-pin to the measured overlap x 1.10
# from the first channel leaf.
PIVOT_EAR_APEX_AND_BORE = (9.8, 6.5)
_PIVOT_EAR_TAP_COLUMN = PIVOT_EAR_APEX_AND_BORE[0] - math.sqrt(
    (PIVOT_EAR_APEX_AND_BORE[1] / 2.0) ** 2
    - (THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD] / 2.0) ** 2
)
PIVOT_EAR_SET_SCREW_LIMIT = _smooth_annulus_limit_mm3(
    THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD],
    TAP_DRILL_MM[_ARBOR_SET_SCREW_THREAD],
    _PIVOT_EAR_TAP_COLUMN,
)
FULCRUM_SET_SCREW_THREAD = (1.854, 1.511, 3.96875)
CHANNEL_ANCHOR_NUT_THREAD = (3.505, 2.705, 3.60)
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
    **_numbered_pairs(
        "sh-vn-arbor-set-screw",
        range(1, 3),
        "ch-pivot-bracket",
        PIVOT_EAR_SET_SCREW_LIMIT,
        second_number=None,
    ),
    # The two MHA-CH-VN-55 #1-72 x 5/32 (3.96875) set screws in the keeper crown
    # taps (#53 drill, 1.511), bounded over the screw's whole length; rear
    # keeper and screw are both placed first, so their suffixes match. A
    # smooth-annulus bound for the first build -- re-pin to the measured
    # overlap x 1.10 from the first channel leaf. Literals, like the rows
    # above; test_ch_fulcrum_shaft_drawing pins them to the specs.
    **_numbered_pairs(
        "ch-vn-fulcrum-set-screw",
        range(1, 3),
        "ch-fulcrum-keeper",
        _smooth_annulus_limit_mm3(*FULCRUM_SET_SCREW_THREAD),
        second_number=None,
    ),
    # Each MHA-CH-VN-51 anchor's #6-32 major envelope in its MHA-CH-14 round
    # jam nut's #36 tap drill over the nut's 3.60 thickness; anchor and nut
    # are placed in the same channel loop, so their suffixes match.  Literals,
    # like the rows above; test_ch_vn_spring_hook_drawing pins them to the specs.
    **_numbered_pairs(
        "ch-vn-spring-hook",
        range(1, 21),
        "ch-anchor-jam-nut",
        _smooth_annulus_limit_mm3(*CHANNEL_ANCHOR_NUT_THREAD),
        second_number=None,
    ),
}

# The MHA-MS-00 stop: the #4-40 MHA-MS-VN-50 thumbscrew fills the block's whole
# 8.5344 (.336) tapped wall (ms_stop_spec.FLOOR_THICKNESS) up to the window, and
# each #2-56 x 1/4 MHA-MS-VN-51 plate screw passes the 1.016 (.040) cover and
# engages 5.334 of its Ø1.8542 (#49, .073) blind tap. Everything else is contact
# (bar on the roof, tip on the bar's underside, cover on the block) or clear.
# Literals, like the rows above, so every assembly does not re-key on the
# stop's layout; test_ms_measuring_stick_assembly pins them to the specs.
MS_THUMB_SCREW_THREAD = (2.8448, 2.261, 8.5344)
MS_PLATE_SCREW_THREAD = (2.1844, 1.8542, 6.35 - 1.016)
_MS_MEASURING_STICK_ALLOWED_PAIRS = {
    frozenset(("sh-vn-thumb-screw-1", "ms-stop-block-1")): _smooth_annulus_limit_mm3(
        *MS_THUMB_SCREW_THREAD
    ),
    **_numbered_pairs(
        "ms-vn-stop-plate-screw",
        range(1, 3),
        "ms-stop-block",
        _smooth_annulus_limit_mm3(*MS_PLATE_SCREW_THREAD),
    ),
}

# Oblique shop fixture: only physical bonded-seat, dowel and smooth-thread
# envelope overlap. Plain shoulder pivots, shims and spacers are running fits
# or face contacts, never blanket interference exceptions.
_JIG = "ch-rocker-arm-tl-oblique"
_JIG_VENDOR = "ch-rocker-arm-tl-vn-oblique"
# (diameter, overlap): the .4000 pin's .79 cut less the .24 riser and .080 set
# leaves the .47 carrier; the 1/4 dowel spans the whole .47 carrier.
JIG_HUB_PIN_SEAT = (10.16, 11.938)
JIG_CL_DOWEL_PRESS = (6.35, 11.938)  # (diameter, carrier thickness)
JIG_RAIL_SCREW_THREAD = (4.1656, 3.454, 9.35)  # #8-32 into each base bar
JIG_BRACKET_SCREW_THREAD = (4.1656, 3.454, 8.7376)  # #8-32 into a end bracket
JIG_CARRIAGE_SCREW_THREAD = (4.0, 3.242, 4.8006)  # M4 cut to fit .189 into each HGH15 carriage from the .570 floor
JIG_PILLOW_BLOCK_SCREW_THREAD = (3.5052, 2.705, 10.875)  # #6-32 into a end bracket
JIG_NUT_SCREW_THREAD = (2.8448, 2.261, 8.89)  # #4-40 X 3/4 past the .40 nut into the feed block
JIG_RISER_SCREW_THREAD = (2.8448, 2.261, 10.334168)  # #4-40 into the carrier past the .24 riser's Ø.25 CSK
JIG_CLAMP_SCREW_THREAD = (6.35, 5.105, 11.938)  # 1/4-20 through the .47 carrier
JIG_LEVER_SCREW_THREAD = (7.9375, 6.528, 10.414)  # 5/16-18 into the carrier
JIG_PIVOT_SCREW_THREAD = (7.9375, 6.528, 14.478)  # 5/16-18 cut to .570 below shoulder-end floor
JIG_T_NUT_THREAD = (12.7, 10.716, 14.0)  # 1/2-13 stud in its T-nut
JIG_FLANGE_NUT_THREAD = (12.7, 10.716, 13.0)  # 1/2-13 stud in its flange nut
# The Tr8 screw in the shop-made TL-27 nut's Ø.242 tap drill, .40 long. The
# nut touches nothing else over the carriage's travel (the jig spec's
# ``feed_nut_travel_gaps``), so no other pair names it.
JIG_FEED_NUT_THREAD = (8.0, 6.147, 10.16)
_ROCKER_OBLIQUE_JIG_ALLOWED_PAIRS = {
    frozenset((f"{_JIG_VENDOR}-hub-pin-1", f"{_JIG}-carrier-1")): (
        1.10 * math.pi * JIG_HUB_PIN_SEAT[0] ** 2 * JIG_HUB_PIN_SEAT[1] / 4.0
    ),
    frozenset((f"{_JIG_VENDOR}-cl-dowel-1", f"{_JIG}-carrier-1")): (
        1.10 * math.pi * JIG_CL_DOWEL_PRESS[0] ** 2 * JIG_CL_DOWEL_PRESS[1] / 4.0
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(1, 8),
        f"{_JIG}-base-bar",
        _smooth_annulus_limit_mm3(*JIG_RAIL_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-rail-screw",
        range(8, 15),
        f"{_JIG}-base-bar",
        _smooth_annulus_limit_mm3(*JIG_RAIL_SCREW_THREAD),
        second_number=2,
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-bracket-screw",
        range(1, 5),
        f"{_JIG}-end-bracket",
        _smooth_annulus_limit_mm3(*JIG_BRACKET_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-bracket-screw",
        range(5, 9),
        f"{_JIG}-end-bracket",
        _smooth_annulus_limit_mm3(*JIG_BRACKET_SCREW_THREAD),
        second_number=2,
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-carriage-screw",
        range(1, 5),
        f"{_JIG_VENDOR}-carriage",
        _smooth_annulus_limit_mm3(*JIG_CARRIAGE_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-carriage-screw",
        range(5, 9),
        f"{_JIG_VENDOR}-carriage",
        _smooth_annulus_limit_mm3(*JIG_CARRIAGE_SCREW_THREAD),
        second_number=2,
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-kp08-screw",
        range(1, 3),
        f"{_JIG}-end-bracket",
        _smooth_annulus_limit_mm3(*JIG_PILLOW_BLOCK_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-kp08-screw",
        range(3, 5),
        f"{_JIG}-end-bracket",
        _smooth_annulus_limit_mm3(*JIG_PILLOW_BLOCK_SCREW_THREAD),
        second_number=2,
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-nut-screw",
        range(1, 3),
        f"{_JIG}-feed-block",
        _smooth_annulus_limit_mm3(*JIG_NUT_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-riser-screw",
        range(1, 5),
        f"{_JIG}-carrier",
        _smooth_annulus_limit_mm3(*JIG_RISER_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-clamp-screw",
        range(1, 2),
        f"{_JIG}-carrier",
        _smooth_annulus_limit_mm3(*JIG_CLAMP_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-lever-screw",
        range(1, 3),
        f"{_JIG}-carrier",
        _smooth_annulus_limit_mm3(*JIG_LEVER_SCREW_THREAD),
    ),
    **_numbered_pairs(
        "@HoldDownStud:",
        range(1, 5),
        "@TNut:",
        _smooth_annulus_limit_mm3(*JIG_T_NUT_THREAD),
        second_number=None,
    ),
    **_numbered_pairs(
        "@HoldDownStud:",
        range(1, 5),
        "@FlangeNut:",
        _smooth_annulus_limit_mm3(*JIG_FLANGE_NUT_THREAD),
        second_number=None,
    ),
    **_numbered_pairs(
        f"{_JIG}-feed-nut",
        range(1, 2),
        f"{_JIG_VENDOR}-leadscrew",
        _smooth_annulus_limit_mm3(*JIG_FEED_NUT_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-pivot-screw",
        range(1, 2),
        f"{_JIG}-feed-block",
        _smooth_annulus_limit_mm3(*JIG_PIVOT_SCREW_THREAD),
    ),
    **_numbered_pairs(
        f"{_JIG_VENDOR}-pivot-screw",
        range(2, 3),
        f"{_JIG}-pivot-block",
        _smooth_annulus_limit_mm3(*JIG_PIVOT_SCREW_THREAD),
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
    "ms-measuring-stick": _MS_MEASURING_STICK_ALLOWED_PAIRS,
    "ch-rocker-arm-tl-oblique-jig": _ROCKER_OBLIQUE_JIG_ALLOWED_PAIRS,
    "ha-harmonic-analyzer": _HARMONIC_ANALYZER_ALLOWED_PAIRS,
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    return _BY_ASSEMBLY.get(name, {})

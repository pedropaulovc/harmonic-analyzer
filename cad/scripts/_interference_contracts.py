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
from harmonic_base_fasteners import (
    HOLD_DOWN_ENGAGEMENT as _HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_TAP_DRILL_DIA as _HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD as _HOLD_DOWN_THREAD,
    PEDESTAL_SCREW_ENGAGEMENT as _PEDESTAL_SCREW_ENGAGEMENT,
)
from _hole_spec import THREAD_MAJOR_MM
from crank_hub_spec import (
    HUB_BARREL_DIA as _HUB_W,
    HUB_BORE_DIA as _HUB_BORE,
    SERVICE_PIN_HOLE_SPEC as _HUB_PILOT_SPEC,
)
from crank_pin_spec import (
    BIG_END_DIA as _PIN_D0,
    PIN_LENGTH as _PIN_L,
    SMALL_END_DIA as _PIN_D1,
)
from crank_pin_ring_spec import PIN_PROUD as _PIN_PROUD
# The shaft diameter's owner, not crankshaft_spec: every assembly imports this
# module, so a crankshaft length or station edit must not re-key them all.
from crank_hub_geometry import SHAFT_DIA as _CS_DIA
import summing_lever_spec
from stock_anchor_geom import ANCHOR_9489T111, ANCHOR_9490T1
from frame_attachment_spec import COLUMN_SOCKET_DIAMETER
from frame_cross_screw_spec import SHANK_DIA as _FRAME_CROSS_DIA
from frame_cross_screw_spec import SHANK_LEN as _FRAME_CROSS_LENGTH
from frame_cross_screw_spec import THREAD as _FRAME_CROSS_THREAD
from _hole_spec import TAP_DRILL_MM
from post_mount_screw_spec import CUT_LENGTH_MM as _POST_SCREW_CUT_LENGTH
from post_mount_screw_spec import GRIP_MM as _POST_SCREW_GRIP
from arbor_set_screw_spec import LENGTH as _ARBOR_SET_SCREW_LENGTH
from arbor_set_screw_spec import THREAD as _ARBOR_SET_SCREW_THREAD
from swing_stop_screw_spec import EMBED_LEN as _STOP_EMBED_LEN
from swing_stop_screw_spec import SHANK_DIA as _STOP_SHANK_DIA
from swing_stop_screw_spec import THREAD as _STOP_THREAD
from transgear_removable_spec import DRIVE_PIN_DIA as _SEAT_PIN_DIA
from transgear_removable_spec import DRIVE_PIN_HOLE_DIA as _SEAT_PIN_HOLE_DIA
from crank_seat_drive_pin_spec import PRESS_DEPTH as _CRANK_SEAT_PIN_DEPTH
from transgear_knob_drive_pin_spec import PRESS_DEPTH as _KNOB_SEAT_PIN_DEPTH


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
# no MHA-024 overlap.

_CS_PILOT = 4.978  # #9 drill (build_crankshaft's wizard cross-hole)


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
# The MHA-140 hold-down (91251A108 #4-40 x 3/8 SHCS) up through the platform
# into the MHA-092 foot tap: 5.6585 mm3, read by the first prism-block
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
    frozenset(("crank-pin-1", "crank-hub-1")): 1.10 * _CRANK_PIN_HUB_MM3,
    frozenset(("crank-pin-1", "crankshaft-1")): 1.10 * _CRANK_PIN_SHAFT_MM3,
    # Stock 6.35 shank minus the 1.0 eye wire and 0.02 face clearance.
    frozenset(("fillister-screw-1", "crank-arm-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.33
    ),
    # MHA-139 #6-32 major in the arm's #36 tap drill: the full thread past the
    # 1.5 relief (6.5 of the 8.0 arm) plus its 0.5 lead cone.  The size is
    # named here, not imported from crank_handle_pivot_screw_spec, so every
    # assembly's recipe stays clear of the handle specs; the MHA-139 tests pin
    # it to that spec's THREAD_SIZE.
    frozenset(("crank-handle-pivot-screw-1", "crank-arm-1")): _smooth_annulus_limit_mm3(
        THREAD_MAJOR_MM["#4-40"], TAP_DRILL_MM["#4-40"], 7.0
    ),
    # Rule-12 E11: #10-32 94025A164 in the tapped block, observed above.
    frozenset(
        ("cone-tip-adjuster-1", "cone-tip-block-1")
    ): _TIP_ADJUSTER_GATE_LIMIT_MM3,
    frozenset(
        ("cone-tip-pinch-screw-1", "cone-tip-block-1")
    ): _TIP_PINCH_GATE_LIMIT_MM3,
    frozenset(
        ("cone-tip-block-screw-1", "cone-tip-block-1")
    ): _TIP_HOLDDOWN_GATE_LIMIT_MM3,
    frozenset(
        ("cone-tip-adjuster-1", "cone-gear-shaft-1")
    ): _ADJUSTER_THRUST_GATE_LIMIT_MM3,
    # U30 (I22): each MHA-142 (1/4-20 MSC 40923898, major 6.35) in its #7
    # (5.105) MHA-091 tap, as deep as the cut length runs past the post's
    # grip (the counterbore floor).  The smooth-annulus upper bound until the
    # first drive-train build observes the helical overlap.
    **_numbered_pairs(
        "post-mount-screw",
        (1, 2),
        "cone-swing-platform",
        _smooth_annulus_limit_mm3(
            6.35, 5.105, _POST_SCREW_CUT_LENGTH - _POST_SCREW_GRIP
        ),
    ),
    # #743 Q3: the MHA-147 #4-40 apex set screw in each pedestal's crown tap,
    # bounded over its whole length (the crown holds a little less: the cup
    # point stands in the bore clearance and the socket stands
    # cylinder_bank_layout.SET_SCREW_SOCKET_PROUD over the apex). Pedestal and
    # screw are both placed south first, so their suffixes match. #911: this
    # smooth-annulus bound serves the first build only -- re-pin it to the
    # measured overlap x 1.10 from the first drive_train leaf, as #838 did for
    # the tip-block pairs.
    **_numbered_pairs(
        "arbor-set-screw",
        range(1, 3),
        "arbor-pedestal",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_ARBOR_SET_SCREW_THREAD],
            TAP_DRILL_MM[_ARBOR_SET_SCREW_THREAD],
            _ARBOR_SET_SCREW_LENGTH,
        ),
        second_number=None,
    ),
    # The two MHA-173 dowels pressed into MHA-026's seat-collar holes
    # (ø2.38125 pin in a ø2.38 ream over the press depth): the press fit.
    **_numbered_pairs(
        "crank-seat-drive-pin",
        range(1, 3),
        "crankshaft",
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
        "lag-screw",
        range(1, 5),
        "harmonic-base",
        _smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM[_HOLD_DOWN_THREAD],
            _HOLD_DOWN_TAP_DRILL_DIA,
            _HOLD_DOWN_ENGAGEMENT,
        ),
    ),
    **_numbered_pairs(
        "frame-cross-screw",
        range(1, 5),
        "harmonic-base",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    **_numbered_pairs(
        "frame-cross-screw",
        range(5, 9),
        "top-frame",
        _FRAME_CROSS_GATE_LIMIT_MM3,
    ),
    frozenset(("gooseneck-set-screw-1", "top-frame-1")): _smooth_annulus_limit_mm3(
        6.35, 5.105, 6.95
    ),
    # Four nameplate corners: 6.35-mm stock shank through the 1.5-mm plate.
    **_numbered_pairs(
        "fillister-screw",
        range(1, 5),
        "harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.85),
    ),
}

_MAGNIFIER_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "clamp-screw",
        range(1, 3),
        "column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 4.85),
    ),
    frozenset(("thumb-screw-1", "magnifying-clamp-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 3.9
    ),
}

_COUNTER_ANCHOR_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    ANCHOR_9490T1.thread_major_dia_mm,
    blind_cut_dia_mm(summing_lever_spec.COUNTER_HOLE_SPEC),
    summing_lever_spec.ANCHOR_H,
)
_CHANNEL_ANCHOR_THREAD_LIMIT = _smooth_annulus_limit_mm3(
    ANCHOR_9489T111.thread_major_dia_mm,
    blind_cut_dia_mm(summing_lever_spec.HOLE_SPEC),
    summing_lever_spec.PLATE_T,
)
_SUMMING_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "knife-hanger-stud",
        range(1, 3),
        "knife-mount",
        _smooth_annulus_limit_mm3(12.7, 10.716, 11.3735),
        second_number=None,
    ),
    frozenset(("boss-hook-1", "summing-lever-1")): _COUNTER_ANCHOR_THREAD_LIMIT,
}

_PEN_ALLOWED_PAIRS = {
    frozenset(("pen-set-screw-1", "pen-frame-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.0
    ),
    frozenset(("hanger-screw-1", "pen-hanger-1")): _smooth_annulus_limit_mm3(
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


# MHA-154, a 1/16-in tube with a 0.012-in wall, lies diametrally across
# MHA-078's Ø6.35 core, whose hole is drilled at assembly and not modelled.
_CROSS_PIN_CORE_MM3 = _cross_pin_overlap_mm3(
    25.4 / 16.0, 25.4 / 16.0 - 2.0 * 0.012 * 25.4, 6.35
)


# Pattern instances are numbered by seed creation while the two backs and
# guides are numbered by insertion order, so their suffixes cross or interleave.
#
# The transgear rows (CONTRACT-paper-drive round 10): every stock screw and
# the MHA-082 stud carry their thread at the basic major, and every receiving
# tap is cut at its tap drill, so each bound is the smooth annulus over the
# span where the major body lies inside the receiver.  Sizes and spans are
# literals, as the MHA-139 row above, so no assembly re-keys on a transgear
# spec; test_paper_drive_interference_contracts pins each to its owner.
# Pairs with NO row, modelled line to line or with clearance, which the gate
# reads as contact: the MHA-159 hub's Ø8.2 bore on the sleeve's Ø8.2 shank,
# the MHA-169 dowel in the arm's Ø3.175 ream, the stud journal in the sleeve
# bore (Ø3.9), the disc bore on the spigot (Ø10), the knob journal in the
# plate bore (Ø8.5), the collar bore on the core (Ø6.35), the MHA-175 rivets
# (Ø1.5875) in the Ø1.65 hook and flap holes, the MHA-154 pin in the collar's
# 1.8 slot, the MHA-155 dowels in the T24's Ø2.5 holes, and every screw in
# its clearance hole.
_PAPER_DRIVE_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "clamp-screw",
        range(1, 3),
        "column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
        second_number=2,
    ),
    **_numbered_pairs(
        "clamp-screw",
        range(3, 5),
        "column-clamp-back",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(1, 5),
        "platen",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.0),
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(5, 15, 2),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.2678),
    ),
    **_numbered_pairs(
        "fillister-screw",
        range(6, 15, 2),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 5.2678),
        second_number=2,
    ),
    # MHA-176 guide-lock screws (R9-31, R9-48): seeds -1/-2, then the grid
    # -3..-8; each 9.525 shank passes the 2.0 lock plate into the guide's
    # rear through tap.
    **_numbered_pairs(
        "guide-lock-screw",
        (1, 2, 4, 7),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 7.525),
    ),
    **_numbered_pairs(
        "guide-lock-screw",
        (3, 5, 6, 8),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 7.525),
        second_number=2,
    ),
    # MHA-166 #8-32 x 5/8 (transgear_arm_plate_screw_spec; from the top of the
    # oval head's bevel, flush in the plate's countersink) through the 5.0
    # plate's Ø4.5 clearance, cut flush with the arm's front face (R9-44): the
    # cut length 12.9375 - 5.0 = the arm's 7.9375 in its #29 through tap.
    **_numbered_pairs(
        "transgear-arm-plate-screw",
        range(1, 3),
        "transgear-arm",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 12.9375 - 5.0),
    ),
    # MHA-168 (transgear_pivot_screw_spec) in the support bar's blind #8-32
    # tap: its 4.7625 thread less the 1.1938 neck flat under the shoulder,
    # whose Ø3.02 stays inside the #29 drill -- the full thread plus the 45°
    # ramp back to the major (the MHA-139 row's relief-and-lead-cone reading),
    # 3.5687 of overlap. The contract's engagement (R9-7, vendor neck) counts
    # full thread only: 4.7625 - 1.7653 = 2.9972 (0.72 D); the ramp adds
    # solid overlap with the tap but carries no thread.
    frozenset(("transgear-pivot-screw-1", "support-bar-1")): _smooth_annulus_limit_mm3(
        4.1656, 3.454, 4.7625 - 1.1938
    ),
    # MHA-171 #4-40 x 3/8 (latch_hook_bracket_screw_spec) through the
    # bracket's 1.5 sheet (Ø3.2 clearance): 9.525 - 1.5 = 8.025 in the
    # support bar's #43 taps.
    **_numbered_pairs(
        "latch-hook-bracket-screw",
        range(1, 3),
        "support-bar",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 9.525 - 1.5),
    ),
    # MHA-082's rear #10-32 (transgear_stub_spec), a plain 4.826 cylinder
    # 9.25 long from the collar face as fitted (R9-47), fills the arm's #21
    # through tap over the whole 7.9375 stock (the taps' countersinks only
    # shrink it).
    frozenset(("transgear-stub-1", "transgear-arm-1")): _smooth_annulus_limit_mm3(
        4.826, 4.0386, 7.9375
    ),
    # MHA-160 (transgear_hub_cap_spec: 5.8 long, #36 tapped through) seated
    # on the stud's journal shoulder: the stud's 3.505 #6-32 cylinder starts
    # past the Ø2.4 x 1.1 relief, so 5.8 - 1.1 = 4.7 of the cap.
    frozenset(("transgear-hub-cap-1", "transgear-stub-1")): _smooth_annulus_limit_mm3(
        3.505, 2.705, 5.8 - 1.1
    ),
    # MHA-161 #0-80 x 1/4 (transgear_disc_screw_spec) through the hub
    # flange's Ø1.7 clearance into the disc's 3/64 taps (rack_pinion_spec),
    # cut at assembly (R9-47) to 5.3 under the head: 5.3 - 2.4 = 2.9 of the
    # 3.0 face.
    **_numbered_pairs(
        "transgear-disc-screw",
        range(1, 4),
        "rack-pinion",
        _smooth_annulus_limit_mm3(1.524, 1.191, 5.3 - 2.4),
    ),
    # MHA-158 #8-32 x 7/16 (transgear_knob_retaining_screw_spec, 11.1125
    # under the head) on the MHA-157 cup's 2.6 floor: 11.1125 - 2.6 = 8.5125
    # in the shaft's blind #29 rear tap (transgear_knob_shaft_spec).
    frozenset(
        ("transgear-knob-retaining-screw-1", "transgear-knob-shaft-1")
    ): _smooth_annulus_limit_mm3(4.1656, 3.454, 11.1125 - 2.6),
    # Seats modelled line to line that the gate read as solid overlap on run
    # 20261001T035353825Z (assembly:paper_drive, R9-35): each MHA-166 oval
    # head in its 82-degree countersink (0.00809 mm^3) and the MHA-158 pan
    # head on the cup's counterbore floor (5.26e-5 mm^3).  Sub-micron slivers
    # of coincident faces; the observed reading plus ten percent, so a head
    # sunk even 1 um into its seat (~0.05 / ~0.04 mm^3) still fails.
    **_numbered_pairs(
        "transgear-arm-plate-screw",
        range(1, 3),
        "transgear-arm-plate",
        1.10 * 0.00809042475,
    ),
    frozenset(("transgear-knob-retaining-screw-1", "transgear-knob-cup-1")): (
        1.10 * 5.26003719e-05
    ),
    # MHA-126's 1/4-20 tap drill 5.105 (transgear_thumbnut_spec) on MHA-078's
    # Ø6.22 thread blank at the nominal collar setting: the tip 23.9 in front
    # of F, the nut seated on the T24's front face 6.2 (collar set,
    # transgear_drive_collar_spec) + 2.8 (plate, transgear_removable_spec)
    # in front of F, so 23.9 - 6.2 - 2.8 = 14.9, all on the blank (it starts
    # 7.5 in front of F, behind the nut's seat at 9.0).
    frozenset(
        ("transgear-thumbnut-1", "transgear-knob-shaft-1")
    ): _smooth_annulus_limit_mm3(6.22, 5.105, 23.9 - 6.2 - 2.8),
    # The cross pin's whole tube chord through the core (above).
    frozenset(("transgear-collar-cross-pin-1", "transgear-knob-shaft-1")): 1.10
    * _CROSS_PIN_CORE_MM3,
    # The two MHA-155 dowels pressed into the MHA-177 collar's through reams,
    # the crank-seat twin (the collar's PIN_HOLE_DIA is the seat interface's
    # DRIVE_PIN_HOLE_DIA): the pin's length behind the seat face.
    **_numbered_pairs(
        "transgear-knob-drive-pin",
        range(1, 3),
        "transgear-drive-collar",
        _smooth_annulus_limit_mm3(
            _SEAT_PIN_DIA, _SEAT_PIN_HOLE_DIA, _KNOB_SEAT_PIN_DEPTH
        ),
    ),
}

# The cone-platform pivot screw now carries its full McMaster #10-24 thread
# envelope. Bound its exact nested tap engagement by the same conservative
# smooth-annulus contract as every other migrated stock thread.
_HARMONIC_ANALYZER_ALLOWED_PAIRS = {
    **_numbered_pairs(
        "channel-1/spring-hook",
        range(1, summing_lever_spec.HOLE_COUNT + 1),
        "summing-1/summing-lever",
        _CHANNEL_ANCHOR_THREAD_LIMIT,
    ),
    frozenset(
        (
            "frame-1/harmonic-base-1",
            "drive-train-1/cone-pivot-screw-1",
        )
    ): _smooth_annulus_limit_mm3(4.826, 3.797, 9.525),
    **_numbered_pairs(
        "drive-train-1/cone-lock-knob",
        range(1, 2),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(6.35, 5.105, 12.7),
    ),
    **_numbered_pairs(
        "drive-train-1/swing-stop-screw",
        range(1, 2),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(
            _STOP_SHANK_DIA, TAP_DRILL_MM[_STOP_THREAD], _STOP_EMBED_LEN
        ),
    ),
    # Rule 12 (audit E10): the 31.75 #8-32 x 1-1/4 block screws pass the
    # 20.5 pinion block and engage 11.25 of the base seat.
    **_numbered_pairs(
        "drive-train-1/slotted-screw",
        range(1, 5),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 31.75 - 20.5),
    ),
    **_numbered_pairs(
        "drive-train-1/foot-screw",
        range(1, 2),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 8.725),
    ),
    # U34c: the #8-32 x 3/4 (19.05) MHA-143 hold-downs pass the 5.0 pedestal
    # ledge and engage 14.05 of the transferred base seats.
    **_numbered_pairs(
        "drive-train-1/pedestal-hold-down-screw",
        range(1, 3),
        "frame-1/harmonic-base",
        _smooth_annulus_limit_mm3(
            4.1656, 3.454, _PEDESTAL_SCREW_ENGAGEMENT
        ),
    ),
    **_numbered_pairs(
        "channel-1/frame-side-screw",
        range(1, 3),
        "frame-1/top-frame",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.6624),
    ),
    # #743 PR2: the four #8-32 x 3/4 (19.05) MHA-143 rocker-bracket hold-downs
    # pass the 6.0 bracket foot and engage 13.05 of the support rail's
    # transferred seats. Literals, like the rows above, so every assembly does
    # not re-key on the rocker bank's layout; test_rocker_bracket_seat_layout
    # pins them to rocker_bracket_seat_layout.
    **_numbered_pairs(
        "channel-1/pedestal-hold-down-screw",
        range(1, 5),
        "frame-1/rocker-arm-support",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 19.05 - 6.0),
    ),
}

_BY_ASSEMBLY: dict[str, Mapping[frozenset[str], float]] = {
    "drive-train": _DRIVE_TRAIN_ALLOWED_PAIRS,
    "frame": _FRAME_ALLOWED_PAIRS,
    "magnifier": _MAGNIFIER_ALLOWED_PAIRS,
    "summing": _SUMMING_ALLOWED_PAIRS,
    "pen": _PEN_ALLOWED_PAIRS,
    "paper-drive": _PAPER_DRIVE_ALLOWED_PAIRS,
    "harmonic-analyzer": _HARMONIC_ANALYZER_ALLOWED_PAIRS,
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    return _BY_ASSEMBLY.get(name, {})

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
from build_harmonic_base import (
    HOLD_DOWN_ENGAGEMENT as _HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_TAP_DRILL_DIA as _HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD as _HOLD_DOWN_THREAD,
    PEDESTAL_FLANGE_THICKNESS as _PEDESTAL_FLANGE_THICKNESS,
    PEDESTAL_SCREW_LEN as _PEDESTAL_SCREW_LEN,
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
_PIN_PROUD = 3.85  # build_drive_train_assembly.PIN_PROUD (kept in step by test)


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
# their production receivers.  The 90280A108's modeled helical thread and
# under-head runout overlapped the native #4-40 far jaw by 6.47 mm3 over its
# 2.625 of far-jaw engagement; the cup-tip adjuster makes its intended thrust
# contact with the shaft end at 0.13 mm3.  That is the 45 deg cup's analytic
# (2/3)*pi*r^3 for the 0.79 stub (0.131); rule-12 E11's 94025A164 cup is also
# 45 deg (vendor Sketch2).  The 1/16 in tip land doubles the stub radius, so
# the contact scales by r^3: 0.13 * 8 = 1.04 (analytic 1.047) until the next
# drive-train build re-observes it.  Rule-12 E1 lengthened the pinch
# screw to the 12.7 90280A110 (5.80 in the far jaw), so its limit scales that
# observation by engagement -- an over-estimate, since the runout share does
# not grow -- until the next drive-train build re-observes it.  Ten-percent
# bounded headroom still fails any materially deeper insertion.
# 6.47 * 5.80 / 2.625 = 14.296, rounded up.
_TIP_PINCH_OBSERVED_MM3 = 14.30
_TIP_PINCH_GATE_LIMIT_MM3 = _TIP_PINCH_OBSERVED_MM3 * 1.10
_ADJUSTER_THRUST_GATE_LIMIT_MM3 = 0.13 * 8.0 * 1.10

_DRIVE_TRAIN_ALLOWED_PAIRS = {
    frozenset(("crank-pin-1", "crank-hub-1")): 1.10 * _CRANK_PIN_HUB_MM3,
    frozenset(("crank-pin-1", "crankshaft-1")): 1.10 * _CRANK_PIN_SHAFT_MM3,
    # Stock 6.35 shank minus the 1.0 eye wire and 0.02 face clearance.
    frozenset(("fillister-screw-1", "crank-arm-1")): _smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.33
    ),
    # MHA-139 #8-32 major in the arm's #29 tap drill: the full thread past the
    # 1.5 relief (6.5 of the 8.0 arm) plus its 0.5 lead cone.  The size is
    # named here, not imported from crank_handle_pivot_screw_spec, so every
    # assembly's recipe stays clear of the handle specs; the MHA-139 tests pin
    # it to that spec's THREAD_SIZE.
    frozenset(("crank-handle-pivot-screw-1", "crank-arm-1")): _smooth_annulus_limit_mm3(
        THREAD_MAJOR_MM["#8-32"], TAP_DRILL_MM["#8-32"], 7.0
    ),
    # Rule-12 E11: #10-32 94025A164 (major 4.826) in the #21 (4.0386) tap
    # drill, ADJUSTER_EMBED 9.5 deep.
    frozenset(("cone-tip-adjuster-1", "cone-tip-block-1")): _smooth_annulus_limit_mm3(
        4.826, 4.0386, 9.5
    ),
    frozenset(
        ("cone-tip-pinch-screw-1", "cone-tip-block-1")
    ): _TIP_PINCH_GATE_LIMIT_MM3,
    frozenset(
        ("cone-tip-adjuster-1", "cone-gear-shaft-1")
    ): _ADJUSTER_THRUST_GATE_LIMIT_MM3,
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

# Pattern instances are numbered by seed creation while the two backs and
# guides are numbered by insertion order, so their suffixes cross or interleave.
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
    **_numbered_pairs(
        "fillister-screw",
        (15, 16, 18, 21),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.35),
    ),
    **_numbered_pairs(
        "fillister-screw",
        (17, 19, 20, 22),
        "platen-guide",
        _smooth_annulus_limit_mm3(2.8448, 2.261, 4.35),
        second_number=2,
    ),
    **_numbered_pairs(
        "bracket-screw",
        range(1, 3),
        "support-bar",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.7),
    ),
    # The front latch uses the third stock screw through the support bar's 9-mm tap.
    frozenset(("bracket-screw-3", "support-bar-1")): _smooth_annulus_limit_mm3(
        4.1656, 3.454, 9.0
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
        _smooth_annulus_limit_mm3(4.1656, 3.454, 15.525),
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
            4.1656, 3.454, _PEDESTAL_SCREW_LEN - _PEDESTAL_FLANGE_THICKNESS
        ),
    ),
    **_numbered_pairs(
        "channel-1/frame-side-screw",
        range(1, 3),
        "frame-1/top-frame",
        _smooth_annulus_limit_mm3(4.1656, 3.454, 8.6624),
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

"""Intended-fit interference contracts for the top (harmonic-analyzer) assembly.

Read by ``build_harmonic_analyzer_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_contracts import numbered_pairs, smooth_annulus_limit_mm3
from _hole_spec import blind_cut_dia_mm
from build_harmonic_base import (
    PEDESTAL_FLANGE_THICKNESS as _PEDESTAL_FLANGE_THICKNESS,
    PEDESTAL_SCREW_LEN as _PEDESTAL_SCREW_LEN,
)
import summing_lever_spec
from stock_anchor_geom import ANCHOR_9489T111


_CHANNEL_ANCHOR_THREAD_LIMIT = smooth_annulus_limit_mm3(
    ANCHOR_9489T111.thread_major_dia_mm,
    blind_cut_dia_mm(summing_lever_spec.HOLE_SPEC),
    summing_lever_spec.PLATE_T,
)

# The cone-platform pivot screw now carries its full McMaster #10-24 thread
# envelope. Bound its exact nested tap engagement by the same conservative
# smooth-annulus contract as every other migrated stock thread.
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
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
    ): smooth_annulus_limit_mm3(4.826, 3.797, 9.525),
    **numbered_pairs(
        "drive-train-1/cone-lock-knob",
        range(1, 2),
        "frame-1/harmonic-base",
        smooth_annulus_limit_mm3(6.35, 5.105, 12.7),
    ),
    **numbered_pairs(
        "drive-train-1/swing-stop-screw",
        range(1, 2),
        "frame-1/harmonic-base",
        smooth_annulus_limit_mm3(4.1656, 3.454, 15.525),
    ),
    # Rule 12 (audit E10): the 31.75 #8-32 x 1-1/4 block screws pass the
    # 20.5 pinion block and engage 11.25 of the base seat.
    **numbered_pairs(
        "drive-train-1/slotted-screw",
        range(1, 5),
        "frame-1/harmonic-base",
        smooth_annulus_limit_mm3(4.1656, 3.454, 31.75 - 20.5),
    ),
    **numbered_pairs(
        "drive-train-1/foot-screw",
        range(1, 2),
        "frame-1/harmonic-base",
        smooth_annulus_limit_mm3(2.8448, 2.261, 8.725),
    ),
    # U34c: the #8-32 x 3/4 (19.05) MHA-143 hold-downs pass the 5.0 pedestal
    # ledge and engage 14.05 of the transferred base seats.
    **numbered_pairs(
        "drive-train-1/pedestal-hold-down-screw",
        range(1, 3),
        "frame-1/harmonic-base",
        smooth_annulus_limit_mm3(
            4.1656, 3.454, _PEDESTAL_SCREW_LEN - _PEDESTAL_FLANGE_THICKNESS
        ),
    ),
    **numbered_pairs(
        "channel-1/frame-side-screw",
        range(1, 3),
        "frame-1/top-frame",
        smooth_annulus_limit_mm3(4.1656, 3.454, 8.6624),
    ),
}

"""Explicit, volume-bounded interference-fit contract for the summing assembly.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_sm_summing_assembly, the top
assembly's table (which reuses the seat limit below) and
verify_soundness:sm_summing fold this module, so it imports only what its own
pairs need.
"""

from __future__ import annotations

from collections.abc import Mapping

import sm_summing_lever_spec
from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM, blind_cut_dia_mm
from _interference_common import numbered_pairs, smooth_annulus_limit_mm3
from stock_anchor_geom import ANCHOR_9490T1

_COUNTER_ANCHOR_THREAD_LIMIT = smooth_annulus_limit_mm3(
    ANCHOR_9490T1.thread_major_dia_mm,
    blind_cut_dia_mm(sm_summing_lever_spec.COUNTER_HOLE_SPEC),
    sm_summing_lever_spec.ANCHOR_H,
)
# MHA-SM-VN-52 #10-24 cut hex bolt (92314A253) in each knife mount's #25 tap
# drill over its 8.9173 nominal reach: 46.70 cut length less the 36.50 grip
# to the faced top and the 96659A104 washer's 1.2827 nominal thickness. Keep
# this literal, test-pinned to build_sm_summing_assembly, to avoid broad
# recipe cache keys.
_KNIFE_HANGER_REACH = 8.9173
# MHA-SM-04 1/4-28 in the #3 drill of the blind 1/4-28 tap in MHA-SM-01's
# solid end piece, from the arm-end counterbore floor to the screw's tip,
# which the model seats at the free gap short of the tap's full thread
# (round(min(sm_gooseneck_spring_joint.SCREW_REACH, TAP_THREAD_DEPTH) -
# COUNTERBORE_DEPTH, 2)): the screw's major clears the Ø7.00 counterbore. A
# literal, test-pinned to its owners like _KNIFE_HANGER_REACH, so a screw or
# gooseneck edit does not re-key this table or the summing soundness gate.
_GOOSENECK_THREAD_LENGTH = 11.84
# Bearing seats are exact face contacts, NOT interference fits. Zero volume
# permits a reported coincidence but no unmeasured kernel sliver allowance.
_KNIFE_HANGER_SEAT_OVERLAP_LIMIT = 0.0
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "sm-vn-knife-hanger-stud",
        range(1, 3),
        "sm-knife-mount",
        smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["#10-24"], TAP_DRILL_MM["#10-24"], _KNIFE_HANGER_REACH
        ),
        second_number=None,
    ),
    **numbered_pairs(
        "sm-vn-knife-hanger-stud",
        range(1, 3),
        "sm-vn-knife-hanger-washer",
        _KNIFE_HANGER_SEAT_OVERLAP_LIMIT,
        second_number=None,
    ),
    frozenset(
        ("sm-vn-boss-hook-1", "sm-summing-lever-1")
    ): _COUNTER_ANCHOR_THREAD_LIMIT,
    # Spring/support contact has no allowance and remains independently gated.
    frozenset(("sm-gooseneck-spring-screw-1", "sm-gooseneck-1")): (
        smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["1/4-28"], TAP_DRILL_MM["1/4-28"], _GOOSENECK_THREAD_LENGTH
        )
    ),
}

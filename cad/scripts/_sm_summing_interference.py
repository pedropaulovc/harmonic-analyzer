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
# MHA-SM-VN-56's 10-24 thread (McMaster 91829A566, 3/8 long) in the #25
# drill of the blind #10-24 tap in the MHA-SM-05 end plug: the shoulder
# seats on the plug's end face, so the whole thread length stands in the tap
# (owner ruling 2026-11-08 (Pedro), #2144 item 11.4: plain tap, no
# counterbore; owner rulings 2026-11-08 (Pedro), #2315: the tap is the
# plug's).  A literal, test-pinned to
# sm_vn_gooseneck_shoulder_screw_spec.THREAD_LENGTH like _KNIFE_HANGER_REACH,
# so a screw or plug edit does not re-key this table or the summing
# soundness gate.  The plug's spigot sits in MHA-SM-01's bore at the bond's
# diametral clearance (sm_gooseneck_spring_joint.BOND_CLEARANCE_MIN/MAX), so
# plug and tube have no pair: any overlap between them fails the gate.
_GOOSENECK_THREAD_LENGTH = 9.525
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
    frozenset(("sm-vn-gooseneck-shoulder-screw-1", "sm-gooseneck-end-plug-1")): (
        smooth_annulus_limit_mm3(
            THREAD_MAJOR_MM["#10-24"], TAP_DRILL_MM["#10-24"], _GOOSENECK_THREAD_LENGTH
        )
    ),
}

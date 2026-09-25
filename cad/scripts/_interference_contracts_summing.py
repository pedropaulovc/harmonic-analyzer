"""Intended-fit interference contracts for the summing assembly.

Read by ``build_summing_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_contracts import numbered_pairs, smooth_annulus_limit_mm3
from _hole_spec import blind_cut_dia_mm
import summing_lever_spec
from stock_anchor_geom import ANCHOR_9490T1


_COUNTER_ANCHOR_THREAD_LIMIT = smooth_annulus_limit_mm3(
    ANCHOR_9490T1.thread_major_dia_mm,
    blind_cut_dia_mm(summing_lever_spec.COUNTER_HOLE_SPEC),
    summing_lever_spec.ANCHOR_H,
)

ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "knife-hanger-stud",
        range(1, 3),
        "knife-mount",
        smooth_annulus_limit_mm3(12.7, 10.716, 11.3735),
        second_number=None,
    ),
    frozenset(("boss-hook-1", "summing-lever-1")): _COUNTER_ANCHOR_THREAD_LIMIT,
}

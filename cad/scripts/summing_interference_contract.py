"""The summing assembly's intended-fit interference contract.

Summing owns this module instead of ``_interference_contracts`` holding it:
every assembly script imports ``_interference_contracts``, so a static import
of the knife-hanger joint there would put ``knife_hanger_interface`` in every
assembly's recipe closure and re-key the whole fleet on each joint tweak.
``_interference_contracts.allowed_interference_pairs("summing")`` loads this
module by name; ``build_summing_assembly`` imports it directly, so summing's
own recipe (and, through its execution token, its soundness leaf) still tracks
every change here.
"""

from __future__ import annotations

import knife_hanger_interface as hanger
import summing_lever_spec
from _hole_spec import blind_cut_dia_mm
from _interference_contracts import _numbered_pairs, _smooth_annulus_limit_mm3
from stock_anchor_geom import ANCHOR_9490T1

# Option D (user, 2026-09-22): each stepped stud's turned #10-24 tip sits in
# its knife mount's tap. The CAD models the tip at the thread's major diameter
# and the tap at its drill, so the solids overlap as an annulus over the whole
# tip below the seat plane. The bound spans the modelled tip, not the smaller
# full-thread engagement, because the chamfer and the mouth break shave only a
# sliver of that annulus, well inside the 10% headroom.
HANGER_TIP_THREAD_LIMIT_MM3 = _smooth_annulus_limit_mm3(
    hanger.THREAD_MAJOR_DIA_MM,
    hanger.TAP_DRILL_DIA_MM,
    hanger.STUD_TIP_LENGTH_MM,
)
COUNTER_ANCHOR_THREAD_LIMIT_MM3 = _smooth_annulus_limit_mm3(
    ANCHOR_9490T1.thread_major_dia_mm,
    blind_cut_dia_mm(summing_lever_spec.COUNTER_HOLE_SPEC),
    summing_lever_spec.ANCHOR_H,
)

ALLOWED_PAIRS = {
    **_numbered_pairs(
        "knife-hanger-stud",
        range(1, 3),
        "knife-mount",
        HANGER_TIP_THREAD_LIMIT_MM3,
        second_number=None,
    ),
    frozenset(("boss-hook-1", "summing-lever-1")): COUNTER_ANCHOR_THREAD_LIMIT_MM3,
}

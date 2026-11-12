"""Explicit, volume-bounded interference-fit contract for the T006 fly cutter.

Most nominal CAD solids must never overlap. The fixture's one intended
overlap is the #4-40 x 1/4 set screw's modelled major diameter in the bar's
tap, end face to the bit; the bit's slip fit in the reamed cross hole and the
screw's cup on the bit are contact or clearance. Only
build_dt_cone_tip_gear_tl_cutter_assembly and verify_soundness:
dt_cone_tip_gear_tl_cutter fold this module, so it imports only what its own
pair needs.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_common import smooth_annulus_limit_mm3

# Major .112, tap drill #43 (.089), over the screw's whole .25 length
# (sh_vn_arbor_set_screw_spec.LENGTH): literals, so this table does not
# re-key on the bar's layout; test_dt_cone_tip_gear_tl_cutter_assembly_drawing
# pins them to the specs.
SET_SCREW_THREAD = (2.8448, 2.261, 6.35)
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    frozenset(
        ("sh-vn-arbor-set-screw-1", "dt-cone-tip-gear-tl-cutter-bar-1")
    ): smooth_annulus_limit_mm3(*SET_SCREW_THREAD),
}

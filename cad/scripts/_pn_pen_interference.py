"""Explicit, volume-bounded interference-fit contract for the pen.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_pn_pen_assembly (and the assemblies
that contain it) and verify_soundness:pn_pen fold this module, so it imports
only what its own pairs need.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_common import smooth_annulus_limit_mm3

ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    # #4-40 thumb screw through the stirrup's .24 bottom rail (pn_pen_frame_spec.RAIL_END).
    frozenset(("pn-vn-pen-set-screw-1", "pn-pen-frame-1")): smooth_annulus_limit_mm3(
        2.8448, 2.261, 6.096
    ),
    # #4-40 x 1/4 rod set screw wholly in the v-block's tap (sh_vn_arbor_set_screw_spec.LENGTH).
    frozenset(
        ("sh-vn-arbor-set-screw-1", "pn-pen-v-block-1")
    ): smooth_annulus_limit_mm3(2.8448, 2.261, 6.35),
    # #0-80 adjuster stud threaded 3.2 into the rod top (pn_pen_rod_spec.STUD_ENGAGEMENT).
    frozenset(("pn-pen-adjust-screw-1", "pn-pen-rod-1")): smooth_annulus_limit_mm3(
        1.524, 1.191, 3.2
    ),
}

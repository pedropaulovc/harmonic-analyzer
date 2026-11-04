"""Explicit, volume-bounded interference-fit contract for the measuring stick.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions here lets both
the assembly build and the reopened soundness gate apply the same exact pair
and maximum-volume contract. Only build_ms_measuring_stick_assembly (and the
assemblies that contain it) and verify_soundness:ms_measuring_stick fold this module, so
it imports only what its own pairs need.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_common import numbered_pairs, smooth_annulus_limit_mm3

# The MHA-MS-00 stop: the #4-40 MHA-MS-VN-50 thumbscrew fills the block's whole
# 8.5344 (.336) tapped wall (ms_stop_spec.FLOOR_THICKNESS) up to the window, and
# each #2-56 x 1/4 MHA-MS-VN-51 plate screw passes the 1.016 (.040) cover and
# engages 5.334 of its Ø1.8542 (#49, .073) blind tap. Everything else is contact
# (bar on the roof, tip on the bar's underside, cover on the block) or clear.
# Literals, so this table does not re-key on the stop's layout;
# test_ms_measuring_stick_assembly pins them to the specs.
MS_THUMB_SCREW_THREAD = (2.8448, 2.261, 8.5344)
MS_PLATE_SCREW_THREAD = (2.1844, 1.8542, 6.35 - 1.016)
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    frozenset(("sh-vn-thumb-screw-1", "ms-stop-block-1")): smooth_annulus_limit_mm3(
        *MS_THUMB_SCREW_THREAD
    ),
    **numbered_pairs(
        "ms-vn-stop-plate-screw",
        range(1, 3),
        "ms-stop-block",
        smooth_annulus_limit_mm3(*MS_PLATE_SCREW_THREAD),
    ),
}

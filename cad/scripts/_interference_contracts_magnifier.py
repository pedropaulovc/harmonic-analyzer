"""Intended-fit interference contracts for the magnifier assembly.

Read by ``build_magnifier_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_contracts import numbered_pairs, smooth_annulus_limit_mm3


ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "clamp-screw",
        range(1, 3),
        "column-clamp-back",
        smooth_annulus_limit_mm3(4.1656, 3.454, 4.85),
    ),
    frozenset(("thumb-screw-1", "magnifying-clamp-1")): smooth_annulus_limit_mm3(
        2.8448, 2.261, 3.9
    ),
}

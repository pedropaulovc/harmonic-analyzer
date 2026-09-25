"""Intended-fit interference contracts for the pen assembly.

Read by ``build_pen_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_contracts import smooth_annulus_limit_mm3


ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    frozenset(("pen-set-screw-1", "pen-frame-1")): smooth_annulus_limit_mm3(
        2.8448, 2.261, 5.0
    ),
    frozenset(("hanger-screw-1", "pen-hanger-1")): smooth_annulus_limit_mm3(
        4.1656, 3.454, 3.0
    ),
}

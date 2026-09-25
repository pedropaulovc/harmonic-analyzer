"""Intended-fit interference contracts for the paper-drive assembly.

Read by ``build_paper_drive_assembly`` directly, so only that assembly's recipe
carries the geometry these limits are computed from; ``verify.py`` reaches the
same table through ``_interference_contracts.allowed_interference_pairs``.
"""

from __future__ import annotations

from collections.abc import Mapping

from _interference_contracts import numbered_pairs, smooth_annulus_limit_mm3


# Pattern instances are numbered by seed creation while the two backs and
# guides are numbered by insertion order, so their suffixes cross or interleave.
ALLOWED_PAIRS: Mapping[frozenset[str], float] = {
    **numbered_pairs(
        "clamp-screw",
        range(1, 3),
        "column-clamp-back",
        smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
        second_number=2,
    ),
    **numbered_pairs(
        "clamp-screw",
        range(3, 5),
        "column-clamp-back",
        smooth_annulus_limit_mm3(4.1656, 3.454, 9.0124),
    ),
    **numbered_pairs(
        "fillister-screw",
        range(1, 5),
        "platen",
        smooth_annulus_limit_mm3(2.8448, 2.261, 4.0),
    ),
    **numbered_pairs(
        "fillister-screw",
        range(5, 15, 2),
        "platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 5.2678),
    ),
    **numbered_pairs(
        "fillister-screw",
        range(6, 15, 2),
        "platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 5.2678),
        second_number=2,
    ),
    **numbered_pairs(
        "fillister-screw",
        (15, 16, 18, 21),
        "platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 4.35),
    ),
    **numbered_pairs(
        "fillister-screw",
        (17, 19, 20, 22),
        "platen-guide",
        smooth_annulus_limit_mm3(2.8448, 2.261, 4.35),
        second_number=2,
    ),
    **numbered_pairs(
        "bracket-screw",
        range(1, 3),
        "support-bar",
        smooth_annulus_limit_mm3(4.1656, 3.454, 8.7),
    ),
    # The front latch uses the third stock screw through the support bar's 9-mm tap.
    frozenset(("bracket-screw-3", "support-bar-1")): smooth_annulus_limit_mm3(
        4.1656, 3.454, 9.0
    ),
}

"""Pure helpers shared by the per-assembly allowed-interference tables.

Each assembly's exact intended-fit pairs and maximum overlap volumes live in
its own ``_<stem>_interference.py`` (``_buildgraph.interference_module``).
Every one of those modules imports this file, so an edit here re-keys every
assembly, its soundness gate and its drawing: only pure helpers used by more
than one table belong here, never an assembly-specific constant or spec import.
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def smooth_annulus_limit_mm3(
    major_d: float,
    tap_d: float,
    length: float,
) -> float:
    """Return a 10%-headroom bound for smooth thread-envelope engagement."""
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def _occurrence(prefix: str, number: int) -> str:
    """Append an ordinal to an explicit role prefix or a native family."""
    return f"{prefix}{number}" if prefix.endswith(":") else f"{prefix}-{number}"


def numbered_pairs(
    first_stem: str,
    numbers: Iterable[int],
    second_stem: str,
    limit: float,
    *,
    second_number: int | None = 1,
) -> dict[frozenset[str], float]:
    """Build exact native or explicit ``@Role:N`` pairs, retaining each bound."""
    return {
        frozenset(
            (
                _occurrence(first_stem, number),
                _occurrence(
                    second_stem, number if second_number is None else second_number
                ),
            )
        ): limit
        for number in numbers
    }

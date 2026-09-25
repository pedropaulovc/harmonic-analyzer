"""Explicit, volume-bounded interference-fit contracts for assembly gates.

Most nominal CAD solids must never overlap. A small set of manufactured
interference fits intentionally do; keeping those exceptions in one table per
assembly lets both the assembly build and the reopened soundness gate apply the
same exact pair and maximum-volume contract.

Each table lives in ``_interference_contracts_<assembly>.py`` and its builder
imports it directly, so an assembly's recipe carries only the part geometry its
own limits are computed from (#888).  This core holds the shared helpers and
the by-name lookup the verify gates and the refresh entrypoint use.  The lookup
imports a table by module name at call time: a static import here would put
every table, and every spec they read, back on every assembly's recipe.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Iterable, Mapping


def smooth_annulus_limit_mm3(
    major_d: float,
    tap_d: float,
    length: float,
) -> float:
    """Return a 10%-headroom bound for smooth thread-envelope engagement."""
    return 1.10 * math.pi * (major_d**2 - tap_d**2) * length / 4.0


def numbered_pairs(
    first_stem: str,
    numbers: Iterable[int],
    second_stem: str,
    limit: float,
    *,
    second_number: int | None = 1,
) -> dict[frozenset[str], float]:
    """Build exact numbered component pairs, optionally matching suffixes."""
    return {
        frozenset(
            (
                f"{first_stem}-{number}",
                f"{second_stem}-{number if second_number is None else second_number}",
            )
        ): limit
        for number in numbers
    }


# Assembly name -> its contract module.  An assembly with no intended fit
# (channel) has no module and reads an empty table.
CONTRACT_MODULES: Mapping[str, str] = {
    "drive-train": "_interference_contracts_drive_train",
    "frame": "_interference_contracts_frame",
    "magnifier": "_interference_contracts_magnifier",
    "summing": "_interference_contracts_summing",
    "pen": "_interference_contracts_pen",
    "paper-drive": "_interference_contracts_paper_drive",
    "harmonic-analyzer": "_interference_contracts_harmonic_analyzer",
}


def allowed_interference_pairs(name: str) -> Mapping[frozenset[str], float]:
    """Return exact intended-fit pairs and maximum overlap volumes for *name*."""
    module = CONTRACT_MODULES.get(name)
    if module is None:
        return {}
    return importlib.import_module(module).ALLOWED_PAIRS

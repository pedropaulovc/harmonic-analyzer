"""Which incremental tier can bring a saved assembly up to its current inputs.

``dodo.build_or_refresh`` records, beside every successful ``.SLDASM``, the
digest of each input its cache key folds (the recipe files plus every referenced
artefact and execution token). The next run compares that ledger with the
current digests and picks the cheapest tier that provably reproduces a FULL
build:

* ``PARTS`` -- only referenced parts/subassemblies changed: reopen and reload
  (``_assembly.refresh_assembly``);
* ``FULL``  -- anything else: insert and mate from scratch.

Kept outside every builder's import closure: dodo.py and refresh_assembly.py
are its only importers, so editing it re-keys no artefact.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum

# How many changed inputs a decision's reason names before eliding the rest.
_REASON_PATHS = 4


class RefreshTier(Enum):
    """The incremental tier that brings an assembly to its current inputs.

    The values are also refresh_assembly.py's tier argument."""

    PARTS = "parts"
    FULL = "full"


def _named(paths: set[str]) -> str:
    shown = sorted(paths)[:_REASON_PATHS]
    more = len(paths) - len(shown)
    return ", ".join(shown) + (f" (+{more} more)" if more else "")


def classify_refresh(
    recorded: Mapping[str, str] | None,
    current: Mapping[str, str],
    recipe: frozenset[str],
) -> tuple[RefreshTier, str]:
    """The tier that brings a saved assembly built from ``recorded`` up to
    ``current`` (both ``input -> digest``), and why.

    ``recipe`` names the current inputs that are build instructions (scripts,
    helper modules, config); every other input is a referenced artefact or its
    execution token. ``recorded`` is None when there is no saved assembly or no
    ledger for it."""
    if recorded is None:
        return RefreshTier.FULL, "no recorded build inputs"
    changed = {
        path
        for path in current.keys() | recorded.keys()
        if current.get(path) != recorded.get(path)
    }
    references = current.keys() - recipe
    # A path the current inputs no longer list counts as a recipe change.
    changed_recipe = changed - references
    if changed_recipe:
        return RefreshTier.FULL, f"recipe changed: {_named(changed_recipe)}"
    if not changed:
        return RefreshTier.PARTS, "no build input changed"
    return RefreshTier.PARTS, f"referenced artefact changed: {_named(changed)}"

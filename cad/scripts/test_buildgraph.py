r"""Static tests for the build-graph enumeration (no SolidWorks required).

``_buildgraph`` is pure filesystem/string logic, so this runs in plain CI:

    python cad/scripts/test_buildgraph.py        # or: pytest cad/scripts/test_buildgraph.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _buildgraph import (  # noqa: E402
    ASSEMBLY_ORDER,
    dependents_of,
    part_stems,
    references_of,
)


def test_references_is_inverse_of_dependents():
    """``references_of`` is the DIRECT inverse of the legacy ``dependents_of``.

    ``dependents_of`` adds a transitive ``harmonic_analyzer`` edge whenever a part
    flows into any sub-assembly (the old --rebuild's "rebuild the top too"). The
    doit graph propagates that through ``output.SLDASM -> harmonic-analyzer.SLDASM``
    instead, so ``references_of`` carries only direct edges. The two must agree
    exactly once that documented transitive add is accounted for.
    """
    candidates = part_stems() + list(ASSEMBLY_ORDER)
    for s in candidates:
        direct = {a for a in ASSEMBLY_ORDER if s in references_of(a)}
        legacy = set(dependents_of(s))
        if direct and "harmonic_analyzer" not in direct:
            assert legacy == direct | {"harmonic_analyzer"}, (
                f"{s}: legacy {legacy} != direct {direct} + transitive top")
        else:
            assert legacy == direct, f"{s}: legacy {legacy} != direct {direct}"


def test_output_references_its_parts_only():
    """The output assembly inserts leaf parts, never a sub-assembly."""
    refs = references_of("output")
    assert refs, "output should reference its parts"
    parts = set(part_stems())
    assert set(refs) <= parts, f"output references non-parts: {set(refs) - parts}"
    assert not (set(refs) & set(ASSEMBLY_ORDER)), "output must not reference a sub-assembly"


def test_top_references_the_four_subassemblies():
    """harmonic-analyzer mates the four subs (and no leaf parts directly)."""
    refs = references_of("harmonic_analyzer")
    assert set(refs) == {"frame", "drive_train", "channel", "output"}, refs


def _run() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  OK  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  XX  {name}: {exc}")
    print(f"\n{'FAIL' if failures else 'PASS'}: "
          f"{failures} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run())

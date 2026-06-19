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
    SCRIPTS_DIR,
    dependents_of,
    module_deps_of,
    part_stems,
    references_of,
    script_for,
)


def _helper_names(stem_script: str) -> set[str]:
    return {Path(p).stem for p in module_deps_of(SCRIPTS_DIR / stem_script)}


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


def test_leaf_parts_do_not_depend_on_assembly_helpers():
    """A leaf part must NOT pull in _assembly/_transforms -- the whole point of
    splitting them out of _common is that assembly-only edits skip every part."""
    for stem in part_stems():
        helpers = _helper_names(f"build_{stem}.py")
        assert "_assembly" not in helpers, f"{stem} wrongly depends on _assembly"
        assert "_transforms" not in helpers, f"{stem} wrongly depends on _transforms"
        assert "_common" in helpers, f"{stem} lost its _common dependency"


def test_assemblies_depend_on_assembly_helpers():
    """Every assembly imports _assembly (mates/placement) and _common."""
    for stem in ASSEMBLY_ORDER:
        helpers = _helper_names(script_for(stem).name)
        assert {"_assembly", "_common"} <= helpers, f"{stem}: {helpers}"


def test_module_deps_are_transitive():
    """The closure follows imports through helper chains: a chain-link part pulls
    _chain_link -> _chain -> _common, and _config arrives via _common's lazy
    import (so parts.yaml-driven custom properties stay correctly tracked)."""
    links = _helper_names("build_chain_inner_link.py")
    assert {"_chain_link", "_chain", "_common"} <= links, links
    assert "_config" in _helper_names("build_lever_bushing.py"), "lazy _config edge lost"


def test_specialized_helper_blast_radius_is_narrow():
    """_gear / _nameplate_geometry reach only their real importers, not the fleet."""
    gear_users = [s for s in part_stems() if "_gear" in _helper_names(f"build_{s}.py")]
    np_users = [s for s in part_stems() if "_nameplate_geometry" in _helper_names(f"build_{s}.py")]
    feat_users = [s for s in part_stems() if "_features" in _helper_names(f"build_{s}.py")]
    assert 0 < len(gear_users) < len(part_stems()), gear_users
    assert np_users == ["nameplate"], np_users
    # spring/screw/nameplate feature builders reach only their handful of parts
    assert 0 < len(feat_users) <= 6, feat_users


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

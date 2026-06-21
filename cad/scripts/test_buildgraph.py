r"""Static tests for the build-graph enumeration (no SolidWorks required).

``_buildgraph`` is pure filesystem/string logic, so this runs in plain CI:

    python cad/scripts/test_buildgraph.py        # or: pytest cad/scripts/test_buildgraph.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _buildgraph as bg  # noqa: E402
from _buildgraph import (  # noqa: E402
    ASSEMBLY_ORDER,
    SCRIPTS_DIR,
    config_files_of,
    dependents_of,
    module_deps_of,
    part_stems,
    references_of,
    script_for,
    stamps_part_properties,
)


def _helper_names(stem_script: str) -> set[str]:
    return {Path(p).stem for p in module_deps_of(SCRIPTS_DIR / stem_script)}


def test_references_is_inverse_of_dependents():
    """``references_of`` is the DIRECT inverse of the legacy ``dependents_of``.

    ``dependents_of`` adds a transitive ``harmonic_analyzer`` edge whenever a part
    flows into any sub-assembly (the old --rebuild's "rebuild the top too"). The
    doit graph propagates that through ``<sub>.SLDASM -> harmonic-analyzer.SLDASM``
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


def test_output_subs_reference_their_parts_only():
    """Each output sub inserts leaf parts, never another sub-assembly."""
    for stem in ("summing", "magnifier", "pen", "paper_drive"):
        refs = references_of(stem)
        assert refs, f"{stem} should reference its parts"
        parts = set(part_stems())
        assert set(refs) <= parts, f"{stem} references non-parts: {set(refs) - parts}"
        assert not (set(refs) & set(ASSEMBLY_ORDER)), \
            f"{stem} must not reference a sub-assembly"


def test_top_references_subassemblies_and_loose_parts():
    """harmonic-analyzer mates the seven subs plus the one loose top-level part:
    the generic measuring-stick sits directly on the base. The spare
    transgear-removable rides inside paper-drive (a flat sibling of its mounted
    T24), not here -- at the top level its leaf name would collide with the
    T12/T24 instances nested in drive-train / paper-drive."""
    refs = set(references_of("harmonic_analyzer"))
    subs = {"frame", "drive_train", "channel", "summing", "magnifier", "pen",
            "paper_drive"}
    loose = {"measuring_stick"}
    assert refs == subs | loose, refs


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


def test_closure_follows_reused_build_scripts():
    """A part that reuses another build script inherits that script's helper
    closure: channel-spring-installed imports build_channel_spring (which imports
    _features), so an edit to _features must mark it stale (codex review #2)."""
    deps = _helper_names("build_channel_spring_installed.py")
    assert "build_channel_spring" in deps, deps
    assert "_features" in deps, deps


def test_specialized_helper_blast_radius_is_narrow():
    """_gear / _nameplate_geometry reach only their real importers, not the fleet."""
    gear_users = [s for s in part_stems() if "_gear" in _helper_names(f"build_{s}.py")]
    np_users = [s for s in part_stems() if "_nameplate_geometry" in _helper_names(f"build_{s}.py")]
    feat_users = [s for s in part_stems() if "_features" in _helper_names(f"build_{s}.py")]
    assert 0 < len(gear_users) < len(part_stems()), gear_users
    assert np_users == ["nameplate"], np_users
    # spring/screw/nameplate feature builders reach only their handful of parts
    # (their direct importers + any part that reuses one of those build scripts)
    assert 0 < len(feat_users) <= 8, feat_users


def _tokens(text: str) -> frozenset[str]:
    """Run ``_config_tokens_in_source`` on an inline source snippet (single file)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(text)
        path = Path(fh.name)
    try:
        return bg._config_tokens_in_source(path)
    finally:
        path.unlink()


def test_config_files_no_part_reads_dimensions():
    """The 98 KB narrative dimensions.yaml is read by NO part/assembly build
    script (only the offline DIMENSIONS gate touches it), so the fine-grained
    dependency must never list it -- editing dimensions.yaml rebuilds nothing."""
    for stem in part_stems():
        assert "dimensions.yaml" not in config_files_of(SCRIPTS_DIR / f"build_{stem}.py"), stem
    for stem in ASSEMBLY_ORDER:
        assert "dimensions.yaml" not in config_files_of(script_for(stem)), stem


def test_config_files_track_real_reads():
    """The read-set follows the actual _config calls, at SUB-FILE granularity:
    a gear reads machine("gear_train", ...) -> machine/gear_train.yaml ONLY, so a
    machine channels.active_count edit (machine/channels.yaml) skips it -- the
    original problem. The channel/drive-train assemblies read channels.yaml
    (amplitudes/cone_teeth); every part needs the parts registry via _common."""
    cone = config_files_of(SCRIPTS_DIR / "build_cone_gear.py")
    assert "machine/gear_train.yaml" in cone
    assert "machine/channels.yaml" not in cone, "gear must NOT depend on active_count's file"
    assert "parts/*" in cone, "stamps its own properties -> parts registry token"
    assert "channels.yaml" in config_files_of(script_for("drive_train"))
    assert "channels.yaml" in config_files_of(script_for("channel"))


def test_config_files_subset_of_known_tokens():
    """Every real script resolves to known tokens (concrete files that exist, or
    the machine/* | parts/* | ** globs). The set can only NARROW the old whole-
    config dep, never invent a missing-file dependency."""
    globs = {"machine/*", "parts/*", "**"}
    for stem in part_stems():
        for tok in config_files_of(SCRIPTS_DIR / f"build_{stem}.py"):
            assert tok in globs or (bg.CONFIG_DIR / tok).is_file(), f"{stem}: {tok}"


def test_config_files_conservative_on_unknown_use():
    """CORRECTNESS > speed: any _config use we can't classify -- an unmapped
    accessor, an unresolvable provenance/_doc doc arg, or a bare-name import --
    must raise so the caller falls back to the WHOLE config (never
    under-invalidate). Note machine()/parts() with a dynamic arg are NOT errors:
    they widen to the whole family (machine/* | parts/*), still conservative."""
    raise_cases = [
        "import _config\nx = _config.frobnicate()\n",            # unmapped accessor
        "import _config\nd = 'machine'\nx = _config._doc(d)\n",  # dynamic doc arg
        "import _config\nx = _config.provenance(name)\n",        # dynamic provenance
        "import _config\nf = _config._doc\n",                    # family accessor, not a literal call
        "import _config\nx = _config._doc('nope')\n",            # literal but unknown doc
        "import _config\nx = _config.machine('no_such_sub')\n",  # unknown machine subsystem
        "from _config import machine\nx = machine()\n",          # bare-name import (untracked)
    ]
    for src in raise_cases:
        try:
            _tokens(src)
        except bg._UnknownConfigUse:
            continue
        raise AssertionError(f"expected _UnknownConfigUse for: {src!r}")


def test_config_files_resolve_known_forms():
    """The classifiable forms resolve to exactly the right file token(s)."""
    assert _tokens("import _config\nx = _config.machine('gear_train', 'k')\n") == frozenset({"machine/gear_train.yaml"})
    assert _tokens("import _config\nx = _config.active_count()\n") == frozenset({"machine/channels.yaml"})
    assert _tokens("import _config\nx = _config.fit('g', 'k')\n") == frozenset({"tolerances.yaml"})
    assert _tokens("import _config\nx = _config.channels()\n") == frozenset({"channels.yaml"})
    assert _tokens("import _config\nx = _config._doc('tolerances')\n") == frozenset({"tolerances.yaml"})
    # a dynamic machine/parts arg widens to the whole family (conservative, not an error).
    assert _tokens("import _config\nx = _config.machine(sub, 'k')\n") == frozenset({"machine/*"})
    assert _tokens("import _config\nx = _config.parts(name)\n") == frozenset({"parts/*"})
    # an aliased module import is still tracked.
    assert _tokens("import _config as cfg\nx = cfg.machine('output')\n") == frozenset({"machine/output.yaml"})
    # no _config use at all -> empty read-set (no config dependency).
    assert _tokens("WIDTH = 3.0\n") == frozenset()


def test_config_accessor_coverage():
    """Every accessor defined in _config.py is classified here (fixed-file or
    family). A new accessor added without an entry reads as 'unknown' and falls
    back to the whole config -- safe, but this test fails loud so the perf benefit
    is restored deliberately, not lost silently."""
    import inspect

    import _config

    accessors = {
        name for name, fn in inspect.getmembers(_config, inspect.isfunction)
        if fn.__module__ == "_config" and not name.startswith("__") and name != "_load"
    }
    classified = set(bg._FIXED_ACCESSOR_TOKENS) | set(bg._FAMILY_ACCESSORS)
    missing = accessors - classified
    assert not missing, f"unclassified _config accessors (map them in _buildgraph): {missing}"


def test_stamps_part_properties_only_in_script_stampers():
    """Only assemblies that stamp a registry row IN-SCRIPT are flagged (so only
    they depend on parts rows directly); a part is always a stamper (it saves its
    own properties), and _common (universal machinery) must not flag everything."""
    assert stamps_part_properties(script_for("channel")), "channel stamps stretched springs"
    assert not stamps_part_properties(script_for("frame")), "frame only inserts parts"
    # every part stamps its own properties via save_part_and_images.
    assert stamps_part_properties(SCRIPTS_DIR / "build_fillister_screw.py")


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

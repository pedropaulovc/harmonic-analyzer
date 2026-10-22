"""Configuration-only visibility edits spare generic visibility part recipes."""

from pathlib import Path

import pytest

import _buildgraph as bg
from test_dodo_recipe import REPO_ROOT, _load_dodo


def test_configuration_visibility_owner_enters_only_cone_part_closure():
    try:
        bg.clear_import_caches()
        closures = {
            script.stem.removeprefix("build_"): {
                Path(p).name for p in bg.module_deps_of(script)
            }
            for script in bg.part_scripts()
        }
        assert closures, "production part enumeration must not be empty"
        configured = {
            stem for stem, closure in closures.items()
            if "_configuration_visibility.py" in closure
        }
        generic = {
            stem for stem, closure in closures.items()
            if "_visibility.py" in closure
        }
        assert configured == {"dt_cone_gear"}
        assert configured < generic
        assert len(generic) > 2, "the generic boundary must retain real consumers"
    finally:
        bg.clear_import_caches()


@pytest.fixture
def visibility_part_keys(tmp_path, monkeypatch):
    """Use real part dependency/key builders with all writes in a copied tree."""
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    dodo = _load_dodo()
    stems = ("dt_cone_gear", "fr_top_frame")
    sources = {
        dodo.RELEASE_VERSION_FILE,
        dodo.PART_TEMPLATE,
        *dodo.CONFIG_DIR.rglob("*.yaml"),
    }
    for stem in stems:
        script = dodo.SCRIPTS_DIR / f"build_{stem}.py"
        sources.update((script, *(Path(p) for p in dodo._helper_deps(script))))
        sources.update(Path(p) for p in bg.data_deps_of(script))
    root = tmp_path / "repo"
    for source in sources:
        target = root / source.resolve().relative_to(REPO_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())

    for owner in (dodo, dodo._cache):
        monkeypatch.setattr(owner, "REPO_ROOT", root)
    scripts = root / "cad" / "scripts"
    config = root / dodo.CONFIG_DIR.relative_to(REPO_ROOT)
    for owner in (dodo, bg):
        monkeypatch.setattr(owner, "SCRIPTS_DIR", scripts)
        monkeypatch.setattr(owner, "CONFIG_DIR", config)
        monkeypatch.setattr(owner, "CAD_OUT", root / "cad" / "out")
    monkeypatch.setattr(bg, "ASSEMBLY_CONTRACT_DIR", config / "assemblies")
    monkeypatch.setattr(bg, "REFERENCES_DIR", root / "cad" / "references")
    monkeypatch.setattr(
        dodo, "RELEASE_VERSION_FILE",
        root / dodo.RELEASE_VERSION_FILE.relative_to(REPO_ROOT),
    )
    monkeypatch.setattr(
        dodo, "PART_TEMPLATE", root / dodo.PART_TEMPLATE.relative_to(REPO_ROOT)
    )
    monkeypatch.setattr(dodo, "_FASTENER_CATALOG", scripts / "_fastener_catalog.py")
    adapter = root / ".adapter-part.digest"
    adapter.write_bytes(b"fixed native adapter identity\n")
    monkeypatch.setattr(dodo, "_submodule_part_dep", lambda: str(adapter))

    def snapshot():
        bg.clear_import_caches()
        bg.config_files_of.cache_clear()
        dodo._ARTEFACT_DIGEST_MEMO.clear()
        result = {}
        for stem in stems:
            script = scripts / f"build_{stem}.py"
            deps = dodo._part_file_deps(script, stem)
            assert deps and all(
                Path(p).resolve().is_relative_to(root.resolve()) for p in deps
            ), stem
            result[stem] = (
                dodo._digest_files(deps), dodo._cache_key(deps, f"part:{stem}")
            )
        return result

    try:
        yield scripts, stems, snapshot
    finally:
        bg.clear_import_caches()
        bg.config_files_of.cache_clear()


def test_configuration_visibility_owner_has_narrow_production_key_impact(
    visibility_part_keys,
):
    scripts, stems, snapshot = visibility_part_keys
    cone, generic = stems
    before = snapshot()
    assert snapshot() == before, "unchanged production keys must be stable"
    closures = {
        stem: {Path(p).name for p in bg.module_deps_of(scripts / f"build_{stem}.py")}
        for stem in stems
    }
    assert all("_visibility.py" in closure for closure in closures.values())
    assert "_configuration_visibility.py" in closures[cone]
    assert "_configuration_visibility.py" not in closures[generic]

    owner = scripts / "_configuration_visibility.py"
    source = owner.read_text(encoding="utf-8")
    mutated = source.replace(
        "ShowConfiguration2 refused", "ShowConfiguration2 rejected"
    )
    assert mutated != source, "the moved-helper mutation must not be vacuous"
    owner.write_text(mutated, encoding="utf-8")
    after = snapshot()
    assert all(a != b for a, b in zip(before[cone], after[cone]))
    assert after[generic] == before[generic]

    shared = scripts / "_visibility.py"
    source = shared.read_text(encoding="utf-8")
    mutated = source.replace(
        "construction geometry would save shown",
        "construction geometry would remain shown",
    )
    assert mutated != source, "the shared-assertion mutation must not be vacuous"
    shared.write_text(mutated, encoding="utf-8")
    shared_after = snapshot()
    for stem in stems:
        assert all(a != b for a, b in zip(after[stem], shared_after[stem])), stem

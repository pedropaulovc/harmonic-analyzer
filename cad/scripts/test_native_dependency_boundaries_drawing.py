"""Whole production recipes, with one Python input's byte digest perturbed.

No native artifact, execution token, ledger or production source is written.
The assertions cover both unused-input isolation and real producer invalidation.
"""

import ast
import hashlib

import pytest

from test_dodo_recipe import _load_dodo


CALLOUTS = {
    "cone_pivot_post": "DIMENSION_CALLOUTS",
    "crank_drive_gear": "DIMENSION_CALLOUTS",
    "cone_pivot_screw": "SIDE_DIMENSION_CALLOUTS",
    "fillister_screw": "SIDE_DIMENSION_CALLOUTS",
}


def _definition_file(directory, filenames, name):
    """Find the actual definition before OR after a structural extraction."""
    matches = []
    for filename in filenames:
        path = directory / filename
        if not path.exists():
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            names = []
            if isinstance(node, ast.FunctionDef):
                names = [node.name]
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [target.id for target in targets if isinstance(target, ast.Name)]
            if name in names:
                matches.append(path)
    assert len(matches) == 1, (name, matches)
    return matches[0]


@pytest.fixture(scope="module")
def recipes(request):
    monkeypatch = pytest.MonkeyPatch()
    request.addfinalizer(monkeypatch.undo)
    dodo = _load_dodo()
    sidecars = {}

    def retain_sidecar(path, digest):
        path = str(path.resolve())
        sidecars[path] = (digest + "\n").encode()
        return path

    original_md5 = dodo._canonical_file_md5

    def read_md5(path):
        if path in sidecars:
            return hashlib.md5(sidecars[path]).hexdigest()
        return original_md5(path)

    monkeypatch.setattr(dodo, "_write_digest_sidecar", retain_sidecar)
    monkeypatch.setattr(dodo, "_canonical_file_md5", read_md5)
    files = {
        f"part:{script.stem.removeprefix('build_')}": dodo._part_file_deps(
            script, script.stem.removeprefix("build_")
        )
        for script in dodo.part_scripts()
    }
    files.update(
        {f"assembly:{stem}": dodo._recipe_files(stem) for stem in dodo.ASSEMBLY_ORDER}
    )
    files.update(
        {
            f"drawing:{task['name']}": task["file_dep"]
            for task in dodo.task_drawing()
            if task["name"] in CALLOUTS
        }
    )
    assert sum(name.startswith("part:") for name in files) == 108
    assert sum(name.startswith("assembly:") for name in files) == 8
    assert sum(name.startswith("drawing:") for name in files) == 4

    def snapshot():
        dodo._ARTEFACT_DIGEST_MEMO.clear()
        return {name: dodo._digest_files(deps) for name, deps in files.items()}

    baseline = snapshot()

    def changed_by(path):
        selected = str(path.resolve())
        changed_md5 = hashlib.md5(path.read_bytes() + b"\n# changed input\n").hexdigest()

        def changed_read_md5(candidate):
            return changed_md5 if candidate == selected else read_md5(candidate)

        with monkeypatch.context() as patch:
            patch.setattr(dodo, "_canonical_file_md5", changed_read_md5)
            current = snapshot()
        dodo._ARTEFACT_DIGEST_MEMO.clear()
        return {name for name in baseline if current[name] != baseline[name]}

    return dodo, files, changed_by


def test_unused_prefix_implementation_invalidates_no_native_producer(recipes):
    dodo, _files, changed_by = recipes
    helper = _definition_file(
        dodo.SCRIPTS_DIR,
        ["_drawing_marks.py", "_dimension_prefix.py"],
        "set_dimension_prefix",
    )
    changed = changed_by(helper)
    assert not {name for name in changed if not name.startswith("drawing:")}
    assert not changed


def test_unused_prefix_isolation_rejects_drawing_only_dependency(recipes, monkeypatch):
    dodo, files, changed_by = recipes
    helper = dodo.SCRIPTS_DIR / "_dimension_prefix.py"
    drawing = "drawing:cone_pivot_post"
    monkeypatch.setitem(files, drawing, [*files[drawing], str(helper.resolve())])
    assert changed_by(helper) == {drawing}
    with pytest.raises(AssertionError, match="drawing:cone_pivot_post"):
        test_unused_prefix_implementation_invalidates_no_native_producer(recipes)


@pytest.mark.parametrize("stem", CALLOUTS)
def test_callout_map_invalidates_its_source_and_drawing_not_other_parts(recipes, stem):
    dodo, _files, changed_by = recipes
    callouts = _definition_file(
        dodo.SCRIPTS_DIR, [f"{stem}_spec.py", f"{stem}_callouts.py"], CALLOUTS[stem]
    )
    changed = changed_by(callouts)
    assert {name for name in changed if name.startswith("part:")} == {f"part:{stem}"}
    assert f"drawing:{stem}" in changed
    assert not {
        "part:cone_swing_platform", "part:harmonic_base", "part:platen_clip"
    }.intersection(changed)


@pytest.mark.parametrize("stem", ["magnifier", "summing"])
def test_provenance_only_assembly_import_does_not_reach_dimension_operations(
    recipes, stem
):
    dodo, files, _changed_by = recipes
    assert str((dodo.SCRIPTS_DIR / "_drawing_marks.py").resolve()) not in files[
        f"assembly:{stem}"
    ]


def test_actual_author_metadata_remains_an_input_of_all_assemblies(recipes):
    dodo, _files, changed_by = recipes
    provenance = _definition_file(
        dodo.SCRIPTS_DIR, ["_drawing_marks.py", "_model_provenance.py"], "DRAWN_BY"
    )
    changed = changed_by(provenance)
    assert {name for name in changed if name.startswith("assembly:")} == {
        f"assembly:{stem}" for stem in dodo.ASSEMBLY_ORDER
    }


@pytest.mark.parametrize(
    ("stem", "consumer"),
    [
        ("cone_pivot_post", "cone_swing_platform"),
        ("crank_drive_gear", "cone_swing_platform"),
        ("cone_pivot_screw", "harmonic_base"),
        ("fillister_screw", "platen_clip"),
    ],
)
def test_geometric_spec_still_invalidates_its_real_scalar_consumer(
    recipes, stem, consumer
):
    dodo, _files, changed_by = recipes
    changed = changed_by(dodo.SCRIPTS_DIR / f"{stem}_spec.py")
    assert {name for name in changed if name.startswith("part:")} == {
        f"part:{stem}", f"part:{consumer}"
    }
    assert f"drawing:{stem}" in changed


@pytest.mark.parametrize(
    ("stem", "name"), [*CALLOUTS.items(), ("fillister_screw", "DIMENSION_TEXT")]
)
def test_callout_migration_audit_recognizes_only_the_redirected_map_import(stem, name):
    from diagnostics.check_model_callout_migration import ApprovedCalloutChanges

    def classified(suffix):
        source = f"from {stem}_{suffix} import {name}\n"
        return ast.dump(ApprovedCalloutChanges(f"draw_{stem}").visit(ast.parse(source)))

    assert classified("spec") == classified("callouts")


@pytest.mark.parametrize(
    "source",
    [
        "from cone_pivot_post_callouts import BORE_HEIGHT\n",
        "from cone_pivot_post_callouts import DIMENSION_CALLOUTS, BORE_HEIGHT\n",
        "from unrelated_callouts import DIMENSION_CALLOUTS\n",
        "from pinion_pivot_shaft_callouts import DIMENSION_CALLOUTS\n",
        "from cone_pivot_screw_callouts import DIMENSION_CALLOUTS\n",
    ],
)
def test_callout_migration_audit_keeps_geometry_and_unowned_imports(source):
    from diagnostics.check_model_callout_migration import ApprovedCalloutChanges

    result = ApprovedCalloutChanges("draw_cone_pivot_post").visit(ast.parse(source))
    assert len(result.body) == 1
    imported = result.body[0]
    assert isinstance(imported, ast.ImportFrom)
    names = {name.name for name in imported.names}
    if "BORE_HEIGHT" in source:
        assert "BORE_HEIGHT" in names
        return
    assert names == {"DIMENSION_CALLOUTS"}


@pytest.mark.parametrize(
    ("drawing", "source"),
    [
        ("draw_pinion_pivot_shaft", "from . import DIMENSION_CALLOUTS\n"),
        ("draw_cone_pivot_post", "from .cone_pivot_post_callouts import DIMENSION_CALLOUTS\n"),
        ("draw_cone_pivot_post", "from .cone_pivot_post_spec import DIMENSION_CALLOUTS\n"),
    ],
)
def test_callout_migration_audit_keeps_relative_import_ownership(drawing, source):
    from diagnostics.check_model_callout_migration import ApprovedCalloutChanges

    original = ast.dump(ast.parse(source))
    actual = ApprovedCalloutChanges(drawing).visit(ast.parse(source))
    assert ast.dump(actual) == original

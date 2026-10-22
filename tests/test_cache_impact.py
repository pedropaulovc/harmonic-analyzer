"""Behavior tests: real dodo/_buildgraph APIs, scratch sources, fresh processes.

No builders execute, no native outputs are necessary, and no live recipe is
mutated. Git test repositories are local scratch directories only.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cache_impact", ROOT / "cache_impact.py")
impact = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(impact)
BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40


def put(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def source_bytes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and not path.is_relative_to(root / "cad/out")
    }


@pytest.fixture(scope="module")
def source_fixture(tmp_path_factory):
    root = tmp_path_factory.mktemp("impact-source") / "source"
    scripts = root / "cad/scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(ROOT / "dodo.py", root / "dodo.py")
    for path in (ROOT / "cad/scripts").glob("*.py"):
        if not path.name.startswith(("build_", "draw_", "test_")):
            shutil.copyfile(path, scripts / path.name)
    shutil.copytree(ROOT / "cad/config", root / "cad/config")
    shutil.copytree(ROOT / "cad/scripts/prompts", scripts / "prompts")
    guidelines = root / "cad/docs/drawing-guidelines.md"
    guidelines.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / "cad/docs/drawing-guidelines.md", guidelines)
    # Adjust only fixture task declarations. All discovery, config projection,
    # sidecar and content-digest implementations remain production code.
    graph_path = scripts / "_buildgraph.py"
    graph_source = graph_path.read_text(encoding="utf-8")
    tree = ast.parse(graph_source)
    assignment = next(
        node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "ASSEMBLY_ORDER" for target in node.targets)
    )
    lines = graph_source.splitlines(keepends=True)
    lines[assignment.lineno - 1:assignment.end_lineno] = ["ASSEMBLY_ORDER = ('impact_group', 'impact_top')\n"]
    graph_path.write_text("".join(lines), encoding="utf-8")
    registry_path = scripts / "_drawing_registry.py"
    registry = registry_path.read_text(encoding="utf-8").split("DRAWINGS: tuple[DrawingSpec, ...] =", 1)[0]
    registry += '''DRAWINGS: tuple[DrawingSpec, ...] = (
    DrawingSpec(name="impact_leaf", part="impact_leaf", artifact_stem="impact-leaf",
                script_name="draw_impact_leaf.py", layout=DrawingLayout.LANDSCAPE),
    DrawingSpec(name="impact_group", part="impact_group", artifact_stem="impact-group",
                script_name="draw_impact_group.py", layout=DrawingLayout.LANDSCAPE,
                source_kind="assembly"),
)
DRAWINGS_BY_NAME = {spec.name: spec for spec in DRAWINGS}
'''
    registry_path.write_text(registry, encoding="utf-8")
    put(root, "cad/scripts/build_impact_leaf.py", "from impact_bridge import VALUE\nraise AssertionError('recipe imported')\n")
    put(root, "cad/scripts/impact_bridge.py", "from impact_dimensions import VALUE\n")
    put(root, "cad/scripts/impact_dimensions.py", "VALUE = 1\n")
    put(root, "cad/scripts/build_impact_unrelated.py", "raise AssertionError('unrelated builder imported')\n")
    put(root, "cad/scripts/build_impact_group_assembly.py", "async def build(adapter):\n    await place_component(adapter, 'impact-leaf', p, r, q)\n")
    put(root, "cad/scripts/build_impact_top_assembly.py", "async def build(adapter):\n    await place_component(adapter, 'impact-group', p, r, q)\n")
    put(root, "cad/scripts/build_kinematic_probe.py", "raise AssertionError('probe imported')\n")
    put(root, "cad/scripts/draw_impact_leaf.py", """from _feature_requirements import requirement
from _machinist_review_mode import MachinistReviewMode
MACHINIST_REVIEW = MachinistReviewMode.LEARN
requirement("fixture", kind="plane", faces=(), requirements=(), fields={})
raise AssertionError('drawing imported')
""")
    put(root, "cad/scripts/draw_impact_group.py", "raise AssertionError('drawing imported')\n")
    put(root, "cad/scripts/impact_leaf_spec.py", "VALUE = 1\nFEATURE_STEP_CONFIGURATIONS = ('Operational',)\n")
    put(root, "cad/config/parts/impact-leaf.yaml", "description: Fixture part\n")
    for stem in ("impact-group", "impact-top"):
        put(root, f"cad/config/assemblies/{stem}.yaml", "description: Fixture assembly\n")
    put(root, "cad/config/release.yaml", "version: 1\n")
    put(root, "cad/templates/harmonic-analyzer.PRTDOT", "fixture binary template\n")
    put(root, "cad/templates/harmonic-analyzer-landscape.DRWDOT", "fixture drawing template\n")
    put(root, "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/feature.py", "FEATURE = 1\n")
    put(root, "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/drawing.py", "DRAWING = 1\n")
    put(root, "book/unrelated.md", "Unrelated text.\n")
    return root


@pytest.fixture(scope="module")
def base_snapshot(source_fixture, tmp_path_factory):
    before = source_bytes(source_fixture)
    result = impact.analyze_tree(
        source_fixture, tmp_path_factory.mktemp("impact-base") / "state",
        {"SolidworksMCP-python": {"sha": "c" * 40, "available": True}},
    )
    assert source_bytes(source_fixture) == before
    assert not list((source_fixture / "cad/out").rglob("*.SLDPRT"))
    return result


def changed_snapshot(source_fixture, tmp_path, mutate, gitlinks=None):
    root = tmp_path / "source"
    shutil.copytree(source_fixture, root, ignore=shutil.ignore_patterns("out", "__pycache__"))
    mutate(root)
    before = source_bytes(root)
    result = impact.analyze_tree(
        root, tmp_path / "state",
        gitlinks if gitlinks is not None else {"SolidworksMCP-python": {"sha": "c" * 40, "available": True}},
    )
    assert source_bytes(root) == before
    assert not list((root / "cad/out").rglob("*.execution"))
    return result


def labels(report, key):
    return {row["task"] for row in report[key]}


def test_relevant_helper_change_has_real_import_cause_and_native_downstream(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: put(root, "cad/scripts/impact_dimensions.py", "VALUE = 2\n"))
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert labels(report, "direct_recipe_changes") == {"part:impact_leaf"}
    assert labels(report, "transitive_recipe_changes") == {
        "assembly:impact_group", "assembly:impact_top", "drawing:impact_leaf", "drawing:impact_group",
        "verify_soundness:impact_group", "verify_soundness:impact_top", "export",
        "package:features:impact_leaf", "package:release",
    }
    assert labels(report, "potential_execution_identity_dependents") == labels(report, "transitive_recipe_changes")
    assert all(entry["also_recipe_affected"] for entry in report["potential_execution_identity_dependents"])
    assert report["execution_dependency_changes"] == []
    assert labels(report, "potential_generated_content_dependents") == {
        "check:machinist_review:impact_leaf", "export", "package:release",
    }
    review_path = next(entry["path"] for entry in report["potential_generated_content_dependents"]
                       if entry["task"] == "check:machinist_review:impact_leaf")
    assert review_path == ["part:impact_leaf", "drawing:impact_leaf", "check:machinist_review:impact_leaf"]
    native_input = "cad/out/sldprt/impact-leaf.SLDPRT"
    before_digest = base_snapshot["tasks"]["assembly:impact_group"]["native_recipe_inputs"][native_input]["digest"]
    after_digest = head["tasks"]["assembly:impact_group"]["native_recipe_inputs"][native_input]["digest"]
    assert before_digest != after_digest
    assert not (source_fixture / native_input).exists()
    top = next(entry for entry in report["transitive_recipe_changes"] if entry["task"] == "assembly:impact_top")
    assert top["path"] == ["part:impact_leaf", "assembly:impact_group", "assembly:impact_top"]
    change = report["direct_recipe_changes"][0]["changed_inputs"][0]
    assert change["input"] == "cad/scripts/impact_dimensions.py"
    assert change["causes"][1] == {
        "revision": "head", "input": "cad/scripts/impact_dimensions.py", "kind": "module_import",
        "path": ["part:impact_leaf", "cad/scripts/build_impact_leaf.py",
                 "cad/scripts/impact_bridge.py", "cad/scripts/impact_dimensions.py"],
    }
    assert report["complete"]
    assert report["cost_estimate"]["available"] is False
    assert report["cost_estimate"]["covered_tasks"] == 0
    assert report["kind"] == "source_impact"
    assert "not observed cache misses" in impact.markdown(report)
    assert "part:impact_unrelated" not in labels(report, "potential_execution_identity_dependents")


def test_unrelated_edit_has_no_recipe_or_native_impact(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: put(root, "book/unrelated.md", "Different prose.\n"))
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert report["counts"] == {"added": 0, "removed": 0, "direct": 0, "transitive_recipe": 0,
                                "execution_potential": 0, "generated_potential": 0, "uncertain": 0}


def test_added_and_removed_tasks_are_distinct_from_existing_recipe_changes(source_fixture, base_snapshot, tmp_path):
    def mutate(root):
        (root / "cad/scripts/build_impact_unrelated.py").unlink()
        put(root, "cad/scripts/build_impact_new.py", "raise AssertionError('must not import')\n")
    head = changed_snapshot(source_fixture, tmp_path, mutate)
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert report["added_tasks"] == ["part:impact_new"]
    assert report["removed_tasks"] == ["part:impact_unrelated"]
    assert report["direct_recipe_changes"] == []


def test_same_sized_mutation_and_identical_tree_processes_are_isolated(source_fixture, base_snapshot, tmp_path):
    changed = changed_snapshot(source_fixture, tmp_path / "changed", lambda root: put(root, "cad/scripts/impact_dimensions.py", "VALUE = 9\n"))
    identical = changed_snapshot(source_fixture, tmp_path / "identical", lambda root: None)
    assert changed != base_snapshot
    assert identical == base_snapshot
    assert impact.compare(base_snapshot, identical, BASE_SHA, HEAD_SHA)["counts"]["direct"] == 0


def test_revision_default_text_reads_preserve_unicode_independently_of_locale(source_fixture, base_snapshot, tmp_path, monkeypatch):
    # Start in a UTF-8 locale rather than C so Python 3.14's automatic C-locale
    # UTF-8 mode cannot mask the regression. Revision code then selects C.
    monkeypatch.setenv("LANG", "C.UTF-8")

    def mutate(root):
        put(root, "cad/scripts/impact_dimensions.py", "VALUE = 'café — 中文'\n")
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + """
import ast as _impact_ast
import locale as _impact_locale
_impact_locale.setlocale(_impact_locale.LC_CTYPE, "C")
_impact_value = _impact_ast.literal_eval(
    _impact_ast.parse((SCRIPTS_DIR / "impact_dimensions.py").read_text()).body[0].value
)
if _impact_value != "café — 中文":
    raise ValueError("revision default-encoding read corrupted Unicode source")
""", encoding="utf-8")

    head = changed_snapshot(source_fixture, tmp_path, mutate)
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert report["complete"]
    assert labels(report, "direct_recipe_changes") == {"part:impact_leaf"}
    changes = report["direct_recipe_changes"][0]["changed_inputs"]
    assert [change["input"] for change in changes] == ["cad/scripts/impact_dimensions.py"]
    assert changes[0]["head"]["available"]
    assert changes[0]["base"]["digest"] != changes[0]["head"]["digest"]
    assert (base_snapshot["tasks"]["part:impact_leaf"]["production_part_cache_key"]
            != head["tasks"]["part:impact_leaf"]["production_part_cache_key"])


def test_missing_required_template_is_reported_not_silently_hashed_as_empty(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: (root / "cad/templates/harmonic-analyzer.PRTDOT").unlink())
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert not report["complete"]
    assert report["unavailable_inputs"]["part:impact_leaf"]["head"] == ["cad/templates/harmonic-analyzer.PRTDOT"]
    assert labels(report, "direct_recipe_changes") == {"part:impact_leaf", "part:impact_unrelated"}


def test_unavailable_adapter_pin_is_unknown_even_when_unchanged_and_changed_pin_is_conservative(source_fixture, tmp_path):
    def remove_adapter(root):
        shutil.rmtree(root / "SolidworksMCP-python")
    missing = {"SolidworksMCP-python": {"sha": "c" * 40, "available": False}}
    base = changed_snapshot(source_fixture, tmp_path / "base", remove_adapter, missing)
    same = changed_snapshot(source_fixture, tmp_path / "same", remove_adapter, missing)
    report = impact.compare(base, same, BASE_SHA, HEAD_SHA)
    assert report["counts"]["direct"] == 0
    expected_uncertain = {label for label, task in base["tasks"].items() if task["unavailable_inputs"]}
    assert report["counts"]["uncertain"] == len(expected_uncertain)
    assert {"part:impact_leaf", "assembly:impact_group", "drawing:impact_leaf"} <= expected_uncertain
    assert "check:machinist_review:impact_leaf" not in expected_uncertain
    assert not report["complete"]
    head = changed_snapshot(source_fixture, tmp_path / "changed", remove_adapter,
                            {"SolidworksMCP-python": {"sha": "d" * 40, "available": False}})
    report = impact.compare(base, head, BASE_SHA, HEAD_SHA)
    expected_direct = {label for label, task in base["tasks"].items()
                       if "unavailable-gitlink:SolidworksMCP-python" in task["inputs"]}
    assert labels(report, "direct_recipe_changes") == expected_direct
    assert "check:machinist_review:impact_leaf" not in expected_direct


def test_real_adapter_tier_projection_preserves_part_and_assembly_boundaries(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: put(root, "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/drawing.py", "DRAWING = 2\n"))
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert labels(report, "direct_recipe_changes") == {"drawing:impact_leaf", "drawing:impact_group"}
    assert report["transitive_recipe_changes"] == []
    assert report["potential_execution_identity_dependents"] == []
    assert labels(report, "potential_generated_content_dependents") == {
        "check:machinist_review:impact_leaf", "package:release",
    }


@pytest.mark.parametrize("content, changed", [("# comment only\nversion: 1\n", False), ("version: 2\n", True)])
def test_config_uses_production_parsed_content_semantics(source_fixture, base_snapshot, tmp_path, content, changed):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: put(root, "cad/config/release.yaml", content))
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    expected = {label for label, task in base_snapshot["tasks"].items()
                if "cad/config/release.yaml" in task["inputs"]} if changed else set()
    if changed:
        assert {"part:impact_leaf", "drawing:impact_leaf", "package:features:impact_leaf", "package:release"} <= expected
    assert labels(report, "direct_recipe_changes") == expected


def test_duration_evidence_is_validated_and_never_extrapolated(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: put(root, "cad/scripts/impact_dimensions.py", "VALUE = 2\n"))
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA,
                            {"source": "actual-run/task-spans.json", "durations_seconds": {"part:impact_leaf": 12.5, "part:impact_unrelated": 999}})
    cost = report["cost_estimate"]
    assert cost["available"]
    assert cost["covered_tasks"] == 1
    assert cost["affected_head_tasks"] == 11
    assert cost["covered_work_seconds"] == 12.5
    assert len(cost["missing_tasks"]) == 10
    assert cost["direct_work"]["covered_work_seconds"] == 12.5
    assert cost["transitive_recipe_only_work"]["affected_tasks"] == 9
    assert cost["execution_potential_only_work"]["affected_tasks"] == 0
    assert cost["generated_potential_only_work"]["affected_tasks"] == 1
    for bad in (float("nan"), -1, True, "12"):
        with pytest.raises(impact.ImpactError, match="invalid measured duration"):
            impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA,
                           {"source": "evidence", "durations_seconds": {"part:impact_leaf": bad}})


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return result.stdout.decode().strip()


def commit(root, message):
    git(root, "add", ".")
    git(root, "-c", "user.name=Impact Test", "-c", "user.email=impact@example.invalid", "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def test_cli_materializes_exact_shas_ignores_dirty_checkout_and_writes_only_reports(source_fixture, tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(source_fixture, repo, ignore=shutil.ignore_patterns("out", "__pycache__"))
    adapter = repo / "SolidworksMCP-python"
    git(adapter, "init")
    commit(adapter, "adapter fixture")
    git(repo, "init")
    git(repo, "config", "core.autocrlf", "false")
    base = commit(repo, "base")
    put(repo, "cad/scripts/impact_dimensions.py", "VALUE = 2\n")
    head = commit(repo, "head")
    put(repo, "cad/scripts/impact_dimensions.py", "dirty checkout, not valid Python!\n")
    before = source_bytes(repo)
    json_path, md_path = tmp_path / "report.json", tmp_path / "report.md"
    command = [sys.executable, "-B", str(ROOT / "cache_impact.py"), "--repo", str(repo),
               "--base", base, "--head", head, "--json", str(json_path), "--markdown", str(md_path)]
    subprocess.run(command, check=True, capture_output=True)
    first = json_path.read_bytes(), md_path.read_bytes()
    report = json.loads(first[0])
    assert report["base_sha"] == base and report["head_sha"] == head
    assert labels(report, "direct_recipe_changes") == {"part:impact_leaf"}
    assert report["complete"]
    assert report["counts"]["uncertain"] == 0
    assert report["revisions"]["base"]["tasks"]["part:impact_leaf"]["production_part_cache_key"]
    subprocess.run(command, check=True, capture_output=True)
    assert (json_path.read_bytes(), md_path.read_bytes()) == first
    assert source_bytes(repo) == before


def test_materialization_reads_pinned_submodule_objects_not_dirty_submodule_files(tmp_path):
    repo, store = tmp_path / "repo", tmp_path / "repo/SolidworksMCP-python"
    store.mkdir(parents=True)
    git(store, "init")
    put(store, "src/solidworks_mcp/feature.py", "VALUE = 1\n")
    pin = commit(store, "adapter")
    git(repo, "init")
    git(repo, "add", "SolidworksMCP-python")
    sha = commit(repo, "gitlink")
    put(store, "src/solidworks_mcp/feature.py", "DIRTY\n")
    isolated = tmp_path / "isolated"
    materialized = impact.materialize(repo, sha, isolated)
    assert materialized["gitlinks"] == {"SolidworksMCP-python": {"sha": pin, "available": True}}
    assert (isolated / "SolidworksMCP-python/src/solidworks_mcp/feature.py").read_text() == "VALUE = 1\n"
    assert (store / "src/solidworks_mcp/feature.py").read_text() == "DIRTY\n"
    assert git(isolated, "rev-parse", "HEAD") == sha
    assert git(isolated / "SolidworksMCP-python", "rev-parse", "HEAD") == pin
    assert git(isolated, "ls-files") == git(repo, "ls-files")


def test_tool_errors_produce_artifacts_and_nonzero_status(tmp_path):
    json_path, md_path = tmp_path / "impact.json", tmp_path / "impact.md"
    code = impact.main(["--base", "main", "--head", HEAD_SHA,
                        "--json", str(json_path), "--markdown", str(md_path)])
    assert code == 2
    assert "full commit SHAs" in json.loads(json_path.read_text())["error"]
    assert "No impact conclusion is available" in md_path.read_text()


@pytest.mark.skipif(not hasattr(os, "fchmod"), reason="descriptor chmod is unavailable")
def test_revision_discovery_allows_real_descriptor_chmod_in_isolated_output(source_fixture, base_snapshot, tmp_path):
    def mutate(root):
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + """
_impact_descriptor_path = CAD_OUT / "descriptor-chmod.txt"
_impact_descriptor_path.parent.mkdir(parents=True, exist_ok=True)
with _impact_descriptor_path.open("wb") as _impact_descriptor:
    os.fchmod(_impact_descriptor.fileno(), 0o600)
    _impact_descriptor.write(b"descriptor chmod completed")
""", encoding="utf-8")
    head = changed_snapshot(source_fixture, tmp_path, mutate)
    output = tmp_path / "source/cad/out/descriptor-chmod.txt"
    assert output.read_bytes() == b"descriptor chmod completed"
    if os.name == "posix":
        assert output.stat().st_mode & 0o777 == 0o600
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert report["complete"]
    assert all(count == 0 for count in report["counts"].values())


@pytest.mark.parametrize("operation", [
    "(REPO_ROOT / 'unexpected').write_text('not allowed')",
    "(SCRIPTS_DIR / 'impact_dimensions.py').chmod(0o600)",
])
def test_revision_discovery_rejects_source_tree_writes(source_fixture, tmp_path, operation):
    def mutate(root):
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + f"\n{operation}\n", encoding="utf-8")
    with pytest.raises(impact.ImpactError, match="outside isolated state"):
        changed_snapshot(source_fixture, tmp_path, mutate)
    assert not (tmp_path / "source/unexpected").exists()


@pytest.mark.parametrize("name", ["../escape", "/escape", "C:/escape", "back\\slash", ".git/config"])
def test_unsafe_tracked_paths_are_rejected(tmp_path, name):
    with pytest.raises(impact.ImpactError, match="unsafe tracked path"):
        impact._safe_path(tmp_path, name)


def test_merge_base_mode_records_requested_base_separately(source_fixture, tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(source_fixture, repo, ignore=shutil.ignore_patterns("out", "__pycache__"))
    git(repo / "SolidworksMCP-python", "init")
    commit(repo / "SolidworksMCP-python", "adapter")
    git(repo, "init")
    ancestor = commit(repo, "common ancestor")
    put(repo, "cad/scripts/impact_dimensions.py", "VALUE = 2\n")
    head = commit(repo, "PR head")
    git(repo, "checkout", "--detach", ancestor)
    put(repo, "book/unrelated.md", "Base branch advanced independently.\n")
    requested_base = commit(repo, "advanced base")
    report = impact.report_revisions(repo, requested_base, head, merge_base=True)
    assert report["requested_base_sha"] == requested_base
    assert report["base_sha"] == ancestor
    assert report["head_sha"] == head
    assert report["comparison_mode"] == "merge_base"
    assert labels(report, "direct_recipe_changes") == {"part:impact_leaf"}


def test_global_cache_context_changes_are_not_mislabeled_as_own_recipe_changes(source_fixture, base_snapshot, tmp_path):
    def mutate(root):
        path = root / "cad/scripts/_artifact_cache.py"
        source = path.read_text(encoding="utf-8")
        assignment = next(
            node for node in ast.parse(source).body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "_CACHE_EPOCH" for target in node.targets)
        )
        lines = source.splitlines(keepends=True)
        lines[assignment.lineno - 1:assignment.end_lineno] = ["_CACHE_EPOCH = 'impact-test-epoch'\n"]
        path.write_text("".join(lines), encoding="utf-8")
    head = changed_snapshot(source_fixture, tmp_path, mutate)
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert report["direct_recipe_changes"] == []
    assert report["global_cache_context_affected_tasks"] == sorted(head["tasks"])
    assert report["global_cache_context_changes"][0]["input"] == "epoch"


def test_markdown_escapes_untrusted_task_and_evidence_text(base_snapshot):
    import copy
    head = copy.deepcopy(base_snapshot)
    head["tasks"]["bad`<img src=x onerror=alert(1)>"] = head["tasks"].pop("part:impact_unrelated")
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    rendered = impact.markdown(report)
    assert "<img" not in rendered
    assert "bad&#96;&lt;img" in rendered


def test_nonrecipe_symlinks_materialize_as_plain_files_without_escape(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    put(repo, "research/CLAUDE.md", "../../outside")
    oid = git(repo, "hash-object", "-w", "research/CLAUDE.md")
    git(repo, "update-index", "--add", "--cacheinfo", f"120000,{oid},research/CLAUDE.md")
    git(repo, "-c", "user.name=Impact Test", "-c", "user.email=impact@example.invalid", "commit", "-m", "symlink")
    sha = git(repo, "rev-parse", "HEAD")
    isolated = tmp_path / "isolated"
    materialized = impact.materialize(repo, sha, isolated)
    assert materialized["symlinks"] == ["research/CLAUDE.md"]
    assert not (isolated / "research/CLAUDE.md").is_symlink()
    assert (isolated / "research/CLAUDE.md").read_text() == "../../outside"


@pytest.mark.parametrize("symlink_input", [
    "cad/templates/harmonic-analyzer.PRTDOT",
    "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/feature.py",
])
def test_recipe_symlink_inputs_fail_loud(source_fixture, tmp_path, symlink_input):
    root = tmp_path / "source"
    shutil.copytree(source_fixture, root, ignore=shutil.ignore_patterns("out", "__pycache__"))
    with pytest.raises(impact.ImpactError, match="symlink recipe input"):
        impact.analyze_tree(root, tmp_path / "state",
                            {"SolidworksMCP-python": {"sha": "c" * 40, "available": True}},
                            symlinks=[symlink_input])


def test_gitlink_pin_change_is_visible_even_when_tier_digests_are_unchanged(base_snapshot):
    import copy
    head = copy.deepcopy(base_snapshot)
    head["gitlinks"]["SolidworksMCP-python"]["sha"] = "d" * 40
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert report["direct_recipe_changes"] == []
    assert report["changed_gitlinks"][0]["input"] == "SolidworksMCP-python"


def fixture_repo(source_fixture, tmp_path):
    repo = tmp_path / "repo"
    shutil.copytree(source_fixture, repo, ignore=shutil.ignore_patterns("out", "__pycache__"))
    git(repo, "init")
    git(repo, "config", "core.autocrlf", "false")
    return repo


def test_cli_incomplete_adapter_inputs_return_three_with_evidence(source_fixture, tmp_path):
    repo = fixture_repo(source_fixture, tmp_path)
    sha = commit(repo, "regular files, no adapter gitlink")
    json_path, md_path = tmp_path / "incomplete.json", tmp_path / "incomplete.md"
    code = impact.main(["--repo", str(repo), "--base", sha, "--head", sha,
                        "--json", str(json_path), "--markdown", str(md_path)])
    report = json.loads(json_path.read_text())
    assert code == 3
    assert not report["complete"] and "error" not in report
    assert "SolidworksMCP-python" in report["unavailable_inputs"]["part:impact_leaf"]["head"]
    assert "Unavailable inputs" in md_path.read_text()


def test_unknown_generated_input_fails_instead_of_being_omitted(source_fixture, tmp_path):
    def mutate(root):
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + """
_original_part_file_deps = _part_file_deps
def _part_file_deps(script, stem):
    return [*_original_part_file_deps(script, stem), str(CAD_OUT / '.unknown.digest')]
""", encoding="utf-8")
    with pytest.raises(impact.ImpactError, match="unclassified generated recipe input"):
        changed_snapshot(source_fixture, tmp_path, mutate)


def test_native_target_without_pure_recipe_digest_fails_before_any_byte_fallback(source_fixture, tmp_path):
    def mutate(root):
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + "\n_stable_artefact_digest = lambda path: None\n", encoding="utf-8")
    with pytest.raises(impact.ImpactError, match="native target lacks a pure recipe digest"):
        changed_snapshot(source_fixture, tmp_path, mutate)


def test_unavailable_native_recipe_propagates_unknown_not_a_confident_digest(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: (root / "cad/templates/harmonic-analyzer.PRTDOT").unlink())
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA,
                            {"source": "measured-run", "durations_seconds": {"part:impact_leaf": 12.5}})
    native = head["tasks"]["assembly:impact_group"]["native_recipe_inputs"]["cad/out/sldprt/impact-leaf.SLDPRT"]
    assert native["digest"] is None and not native["available"]
    assert "native-recipe:assembly:impact_group" in head["tasks"]["assembly:impact_top"]["unavailable_inputs"]
    assert report["transitive_recipe_changes"] == []
    assert report["cost_estimate"]["uncertain_work"]["affected_tasks"] == sum(
        bool(task["unavailable_inputs"]) for task in head["tasks"].values()
    )
    assert report["cost_estimate"]["uncertain_work"]["covered_work_seconds"] == 12.5


@pytest.mark.parametrize("change", ["key_only", "inputs_only"])
def test_production_part_key_parity_mismatch_is_a_tool_error(base_snapshot, change):
    import copy
    head = copy.deepcopy(base_snapshot)
    task = head["tasks"]["part:impact_leaf"]
    if change == "key_only":
        task["production_part_cache_key"] = "different-key"
    else:
        task["inputs"]["cad/scripts/impact_dimensions.py"]["digest"] = "different-input"
    with pytest.raises(impact.ImpactError, match="production part-key/input parity mismatch"):
        impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)


def test_duration_file_with_no_covered_tasks_has_an_accurate_unavailable_reason(base_snapshot):
    report = impact.compare(base_snapshot, base_snapshot, BASE_SHA, HEAD_SHA,
                            {"source": "measured-run", "durations_seconds": {"part:unregistered": 12.5}})
    assert not report["cost_estimate"]["available"]
    assert "No supplied measured durations cover" in impact.markdown(report)


def test_cli_worker_timeout_returns_two_and_error_artifacts(source_fixture, tmp_path):
    repo = fixture_repo(source_fixture, tmp_path)
    path = repo / "dodo.py"
    path.write_text(path.read_text(encoding="utf-8") + "\ntime.sleep(10)\n", encoding="utf-8")
    sha = commit(repo, "deliberately slow discovery")
    json_path, md_path = tmp_path / "timeout.json", tmp_path / "timeout.md"
    code = impact.main(["--repo", str(repo), "--base", sha, "--head", sha, "--timeout", "1",
                        "--json", str(json_path), "--markdown", str(md_path)])
    assert code == 2
    assert "timed out" in json.loads(json_path.read_text())["error"]
    assert "No impact conclusion is available" in md_path.read_text()


def test_multiple_merge_bases_are_refused_before_analysis(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    put(repo, "file.txt", "common tree\n")
    ancestor = commit(repo, "ancestor")
    tree = git(repo, "rev-parse", "HEAD^{tree}")

    def node(message, *parents):
        arguments = ["-c", "user.name=Impact Test", "-c", "user.email=impact@example.invalid",
                     "commit-tree", tree, "-m", message]
        for parent in parents:
            arguments.extend(("-p", parent))
        return git(repo, *arguments)

    left, right = node("left", ancestor), node("right", ancestor)
    first, second = node("merge one", left, right), node("merge two", right, left)
    with pytest.raises(impact.ImpactError, match="exactly one merge base"):
        impact.report_revisions(repo, first, second, merge_base=True)


@pytest.mark.parametrize("event", ["os.exec", "os.spawn", "os.posix_spawn",
                                  "os.startfile", "os.startfile/2", "_winapi.CreateProcess"])
def test_worker_process_audit_bypasses_are_blocked_with_nonexecuting_sentinels(tmp_path, event):
    # sys.audit emits only the event. No exec/spawn/startfile/process API is
    # called, even if the guard is broken; a surviving sentinel fails safely.
    # Keep inert event names and source code out of the native-launch command
    # classifier, without removing its environment or refusal markers.
    state = tmp_path / "state"
    state.mkdir()
    event_file = put(tmp_path, "audit-event.txt", event)
    script_file = put(tmp_path, "audit-sentinel.py", """
import importlib.util
import os
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location('cache_impact_sentinel', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
state = Path(sys.argv[2]).resolve()
module._restrict_worker_writes(state, state / 'out')
# Register the reporting hook first so this synthetic event tests that hook.
# The suite guard remains enabled for real native APIs with its markers intact.
if sys.platform == "win32" and os.environ.get("HARMONIC_TEST_FORBID_SOLIDWORKS"):
    sys.path.insert(0, str(Path(sys.argv[1]).parent / "tests" / "_child_guard"))
    import harmonic_solidworks_guard
    harmonic_solidworks_guard.install_child_guard()
event = Path(sys.argv[3]).read_text(encoding="utf-8")
try:
    sys.audit(event, None, None, None)
except module.ImpactError as error:
    print(error)
else:
    raise SystemExit('nonexecuting audit sentinel escaped')
""")
    result = subprocess.run([sys.executable, "-I", "-B", str(script_file),
                             str(ROOT / "cache_impact.py"), str(state), str(event_file)],
                            check=True, capture_output=True, text=True)
    assert f"host/network action: {event}" in result.stdout


def test_canonical_inventory_covers_native_review_verification_export_and_packaging(base_snapshot):
    expected = {
        "part:impact_leaf", "part:impact_unrelated", "assembly:impact_group", "assembly:impact_top",
        "drawing:impact_leaf", "drawing:impact_group", "check:machinist_review:impact_leaf",
        "verify_soundness:impact_group", "verify_soundness:impact_top", "verify:kinematics",
        "preflight", "export", "package:features:impact_leaf", "package:release",
    }
    assert set(base_snapshot["inventory"]) == expected == set(base_snapshot["tasks"])
    assert not any(task["unavailable_inputs"] for task in base_snapshot["tasks"].values())
    assert {item["producer"] for item in base_snapshot["conditional_auxiliary_keys"]} == {
        "assembly:impact_group", "assembly:impact_top",
    }


def test_expected_generated_bytes_have_producers_without_claiming_digests_or_incomplete_sources(base_snapshot):
    tasks = base_snapshot["tasks"]
    review = tasks["check:machinist_review:impact_leaf"]
    pdf = next(info for name, info in review["generated_content_inputs"].items() if name.endswith(".pdf"))
    assert pdf["producer"] == "drawing:impact_leaf" and pdf["digest"] is None
    assert not pdf["available"]
    drawing_inputs = tasks["package:release"]["generated_content_inputs"]
    assert {info["producer"] for name, info in drawing_inputs.items() if name.endswith(".SLDDRW")} == {
        "drawing:impact_leaf", "drawing:impact_group",
    }
    features = tasks["export"]["generated_content_inputs"]
    assert {info["producer"] for info in features.values()} == {"package:features:impact_leaf"}
    assert any(name.endswith("-Operational.STEP") for name in features)
    assert all(info["digest"] is None for info in features.values())
    report = impact.compare(base_snapshot, base_snapshot, BASE_SHA, HEAD_SHA)
    assert report["complete"] and not report["unavailable_inputs"]
    assert report["counts"]["generated_potential"] == 0
    assert report["offline_unknown_inputs"]["check:machinist_review:impact_leaf"]["head"]["generated_content"]
    assert "not evaluable offline" in impact.markdown(report)


def test_production_review_profile_callback_changes_context_digest_without_source_or_pdf_mutation(source_fixture, base_snapshot, tmp_path):
    def mutate(root):
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + """
def _machinist_review_profile():
    return registered_review_profile()._replace(model="fixture-alternate-model")
""", encoding="utf-8")
    head = changed_snapshot(source_fixture, tmp_path, mutate)
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    label = "check:machinist_review:impact_leaf"
    assert labels(report, "direct_recipe_changes") == {label}
    assert report["transitive_recipe_changes"] == []
    assert report["potential_generated_content_dependents"] == []
    config = "cad/scripts/machinist_review_config.py"
    assert base_snapshot["tasks"][label]["inputs"][config]["digest"] != head["tasks"][label]["inputs"][config]["digest"]
    provenance = head["tasks"][label]["digest_provenance"]
    assert provenance["profile"] == {
        **base_snapshot["tasks"][label]["digest_provenance"]["profile"],
        "model": "fixture-alternate-model",
    }
    assert provenance["method"] == "_machinist_review_cache_key contextual callback"
    assert head["tasks"][label]["production_part_cache_key"] is None


def test_missing_tracked_review_input_is_incomplete_unlike_expected_missing_pdf(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(source_fixture, tmp_path, lambda root: (root / "cad/docs/drawing-guidelines.md").unlink())
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    label = "check:machinist_review:impact_leaf"
    assert not report["complete"]
    assert report["unavailable_inputs"] == {label: {"head": ["cad/docs/drawing-guidelines.md"]}}
    assert labels(report, "direct_recipe_changes") == {label}
    assert report["offline_unknown_inputs"][label]["head"]["generated_content"]


def test_changed_review_capture_contract_fails_loud_instead_of_using_noncontextual_digest(source_fixture, tmp_path):
    def mutate(root):
        path = root / "dodo.py"
        path.write_text(path.read_text(encoding="utf-8") + """
def _machinist_review_cache_key(stem, profile, label=None):
    return None
""", encoding="utf-8")
    with pytest.raises(impact.ImpactError, match="production review digest/input contract changed"):
        changed_snapshot(source_fixture, tmp_path, mutate)


def test_feature_declaration_source_change_impacts_features_and_export_without_native_recipe_claims(source_fixture, base_snapshot, tmp_path):
    head = changed_snapshot(
        source_fixture, tmp_path,
        lambda root: put(root, "cad/scripts/impact_leaf_spec.py",
                         "VALUE = 2\nFEATURE_STEP_CONFIGURATIONS = ('Operational',)\n"),
    )
    report = impact.compare(base_snapshot, head, BASE_SHA, HEAD_SHA)
    assert labels(report, "direct_recipe_changes") == {"package:features:impact_leaf"}
    assert report["transitive_recipe_changes"] == []
    assert report["potential_execution_identity_dependents"] == []
    assert labels(report, "potential_generated_content_dependents") == {"export"}
    assert report["potential_generated_content_dependents"][0]["path"] == [
        "package:features:impact_leaf", "export",
    ]
    assert report["complete"]

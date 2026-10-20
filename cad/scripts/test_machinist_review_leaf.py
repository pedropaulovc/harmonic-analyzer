"""Cached machinist verdicts and AST enforcement, without models or SolidWorks."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import threading
from contextlib import nullcontext
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest
from doit.loader import load_tasks

from _buildgraph import RECIPE_SKIP_MODULES
from _machinist_review_mode import MachinistReviewMode, mode_for_drawing
import _machinist_review_settings as review_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def loaded_dodo():
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def dodo(loaded_dodo, monkeypatch):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.delenv(review_settings.SETTINGS_ENV, raising=False)
    loaded_dodo._reviewed_drawings.cache_clear()
    yield loaded_dodo
    loaded_dodo._reviewed_drawings.cache_clear()


# OFF never reaches the action: it yields no task.
REVIEWED_MODES = [MachinistReviewMode.LEARN, MachinistReviewMode.ENFORCE]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("raise RuntimeError('must not import')\n", MachinistReviewMode.OFF),
        ("MACHINIST_REVIEW = MachinistReviewMode.OFF\n", MachinistReviewMode.OFF),
        (
            "MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n",
            MachinistReviewMode.ENFORCE,
        ),
        ("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n", MachinistReviewMode.LEARN),
        ("def helper():\n    MACHINIST_REVIEW = 'local'\n", MachinistReviewMode.OFF),
    ],
)
def test_mode_is_read_without_importing(tmp_path, source, expected):
    script = tmp_path / "draw_probe.py"
    script.write_text(source, encoding="utf-8")
    assert mode_for_drawing(script) is expected


@pytest.mark.parametrize(
    "source",
    [
        "MACHINIST_REVIEW = 'enforce'",
        "MACHINIST_REVIEW = True",
        "MACHINIST_REVIEW = MachinistReviewMode.UNKNOWN",
        "MACHINIST_REVIEW = Other.ENFORCE",
        "MACHINIST_REVIEW = choose_mode()",
        "MACHINIST_REVIEW: str = MachinistReviewMode.ENFORCE",
        "if enabled:\n    MACHINIST_REVIEW = MachinistReviewMode.ENFORCE",
        "MACHINIST_REVIEW = MachinistReviewMode.LEARN\nMACHINIST_REVIEW = MachinistReviewMode.ENFORCE",
        "from settings import MACHINIST_REVIEW",
        "def MACHINIST_REVIEW(): pass",
    ],
)
def test_invalid_modes_fail_loud_at_graph_load(tmp_path, source):
    script = tmp_path / "draw_probe.py"
    script.write_text(source + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="MACHINIST_REVIEW must be"):
        mode_for_drawing(script)


def _local_import_closure(entry: Path) -> set[str]:
    """Unlike the CAD recipe walker, include non-underscore review modules too."""
    scripts = entry.parent
    found = set()
    pending = [entry]
    while pending:
        path = pending.pop()
        if path.name in found or path.name in RECIPE_SKIP_MODULES:
            continue
        found.add(path.name)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for name in names:
                local = scripts / f"{name}.py"
                # Registry is only used by the interactive name/--all selectors.
                # The leaf supplies PDF/kind/name and never calls those paths.
                if local.is_file() and name != "_drawing_registry":
                    pending.append(local)
    return found


def test_declared_review_modules_equal_the_real_import_closure(dodo):
    assert _local_import_closure(dodo.SCRIPTS_DIR / "machinist_review.py") == set(
        dodo._MACHINIST_REVIEW_MODULES
    )


def test_explicit_pdf_command_cannot_select_a_registry_package(dodo):
    stem = "pd_platen_guide"
    command = dodo._machinist_review_command(stem)
    assert command[0] == dodo.sys.executable
    assert command[2:] == [
        "--pdf",
        str(dodo.DRAWINGS_BY_NAME[stem].outputs["pdf"]),
        "--name",
        stem,
        "--kind",
        "part",
        "--runs",
        "3",
        *review_settings.resolve_settings().cli_args(),
        "--report-dir",
        str(dodo._machinist_review_dir(stem)),
    ]


@pytest.fixture
def inputs(dodo, tmp_path, monkeypatch):
    root = tmp_path / "repo"
    scripts = root / "cad" / "scripts"
    prompts = scripts / "prompts"
    prompts.mkdir(parents=True)
    for name in dodo._MACHINIST_REVIEW_MODULES:
        (scripts / name).write_text("# review code\n", encoding="utf-8")
    for name in (
        "machinist_review_part.md",
        "machinist_review_assembly.md",
        "machinist_review_part_severity.md",
        "machinist_review_assembly_severity.md",
        "machinist_review_schema.json",
        "machinist_review_judge.md",
        "machinist_review_judge_schema.json",
    ):
        (prompts / name).write_text("{}", encoding="utf-8")
    guidelines = root / "cad" / "docs" / "drawing-guidelines.md"
    guidelines.parent.mkdir()
    guidelines.write_text("guidelines", encoding="utf-8")
    config = root / "cad" / "config"
    (config / "parts").mkdir(parents=True)
    (config / "assemblies").mkdir()
    exception = config / "parts" / "probe.yaml"
    exception.write_text("probe: {}\n", encoding="utf-8")
    pdf = root / "cad" / "out" / "pdf" / "probe.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"PDF fixture")
    draw = scripts / "draw_probe.py"
    draw.write_text("# LEARN by default\n", encoding="utf-8")
    registry = scripts / "_drawing_registry.py"
    registry.write_text("# unrelated registry row\n", encoding="utf-8")
    spec = SimpleNamespace(
        outputs={"pdf": pdf},
        source_kind="part",
        script=draw,
    )
    monkeypatch.setattr(dodo, "REPO_ROOT", root)
    monkeypatch.setattr(dodo, "SCRIPTS_DIR", scripts)
    monkeypatch.setattr(dodo, "CONFIG_DIR", config)
    monkeypatch.setattr(dodo, "REPORTS", root / "cad" / "out" / "reports")
    monkeypatch.setattr(dodo, "DRAWINGS_BY_NAME", {"probe": spec})
    monkeypatch.setattr(dodo._cache, "REPO_ROOT", root)
    return SimpleNamespace(
        module=dodo,
        root=root,
        scripts=scripts,
        pdf=pdf,
        exception=exception,
        prompts=prompts,
        draw=draw,
        registry=registry,
        spec=spec,
    )


def test_key_changes_only_with_review_inputs(inputs):
    dodo = inputs.module

    def key():
        return dodo._cache_key(dodo._machinist_review_file_deps("probe"))

    initial = key()
    changed_inputs = [
        inputs.pdf,
        inputs.exception,
        inputs.scripts / "machinist_review.py",
        inputs.prompts / "machinist_review_part.md",
        inputs.prompts / "machinist_review_judge.md",
        inputs.prompts / "machinist_review_judge_schema.json",
    ]
    for path in changed_inputs:
        before = path.read_bytes()
        path.write_bytes(before + b"\nchanged: true\n")
        assert key() != initial, path
        path.write_bytes(before)
    inputs.registry.write_text("# registry changes do not affect explicit PDFs\n")
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n")
    assert key() == initial
    inputs.exception.unlink()
    assert key() != initial
    inputs.spec.source_kind = "assembly"
    assert key() != initial


def test_key_tracks_only_selected_kind_severity_contract(inputs):
    dodo = inputs.module

    def key():
        return dodo._cache_key(dodo._machinist_review_file_deps("probe"))

    for selected, opposite in (("part", "assembly"), ("assembly", "part")):
        inputs.spec.source_kind = selected
        initial = key()
        for kind in (selected, opposite):
            path = inputs.prompts / f"machinist_review_{kind}_severity.md"
            before = path.read_bytes()
            path.write_bytes(before + b"\nchanged: true\n")
            if kind == selected:
                assert key() != initial, path
            else:
                assert key() == initial, path
            path.write_bytes(before)
            assert key() == initial


def test_review_keys_exclude_the_shared_recipe_skip_set(inputs, monkeypatch):
    dodo = inputs.module
    for name in RECIPE_SKIP_MODULES:
        (inputs.scripts / name).write_text("# observation-only infrastructure\n")
    deps = dodo._machinist_review_file_deps("probe")
    assert {Path(path).name for path in deps}.isdisjoint(RECIPE_SKIP_MODULES)
    initial = dodo._cache_key(deps)
    # An inert import entering the explicit manifest must still follow the
    # recipe policy, rather than accidentally charging for another review.
    monkeypatch.setattr(
        dodo,
        "_MACHINIST_REVIEW_MODULES",
        (*dodo._MACHINIST_REVIEW_MODULES, *sorted(RECIPE_SKIP_MODULES)),
    )
    assert dodo._machinist_review_file_deps("probe") == deps
    for name in RECIPE_SKIP_MODULES:
        (inputs.scripts / name).write_text("# logging-only edit must not re-review\n")
        assert dodo._cache_key(dodo._machinist_review_file_deps("probe")) == initial


def test_assembly_exception_uses_bare_dashed_config_stem(inputs):
    dodo = inputs.module
    inputs.spec.source_kind = "assembly"
    dodo.DRAWINGS_BY_NAME["probe_assembly"] = inputs.spec
    path = dodo.CONFIG_DIR / "assemblies" / "probe.yaml"
    path.write_text("machinist_exceptions: []\n")
    assert str(path.resolve()) in dodo._machinist_review_file_deps("probe_assembly")


def test_mode_and_input_set_changes_invalidate_doit_but_not_the_verdict_key(
    inputs,
    monkeypatch,
):
    dodo = inputs.module
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n")

    def tracker():
        dodo._reviewed_drawings.cache_clear()
        return next(dodo._machinist_review_tasks())["uptodate"][0]

    first = tracker()
    assert not first(None, {})
    saved = {"_config_changed": first.config_digest}
    assert tracker()(None, saved)
    key = dodo._cache_key(dodo._machinist_review_file_deps("probe"))
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n")
    assert not tracker()(None, saved)
    assert dodo._cache_key(dodo._machinist_review_file_deps("probe")) == key
    enforced = tracker()
    saved = {"_config_changed": enforced.config_digest}
    inputs.exception.unlink()
    assert not tracker()(None, saved)


def test_review_telemetry_has_a_stage_resource(dodo):
    assert dodo._stage_name("check:machinist_review:probe") == "check-machinist-review"


@pytest.fixture
def action(inputs, monkeypatch):
    dodo = inputs.module
    original_probe = dodo._probe_cache
    original_store = dodo._cache.store
    calls = {"run": 0, "store": 0, "warnings": [], "probe": [], "commands": []}
    state = {
        "verdict": "SHIP", "error": None, "hit": False, "code": 0,
        "skipped": True, "run_errors": (), "missing_runs": (), "edit": None,
    }
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    monkeypatch.setattr(dodo, "_cache_key", lambda *_args: "a" * 64)
    monkeypatch.setattr(
        dodo._telemetry,
        "span",
        lambda *_args, **_kwargs: nullcontext(
            SimpleNamespace(set_attribute=lambda *_args: None)
        ),
    )
    monkeypatch.setattr(dodo._telemetry, "warn", calls["warnings"].append)

    def forbidden(*_args, **_kwargs):
        pytest.fail("review touched COM or dispatched to the farm")

    monkeypatch.setattr(dodo, "_com_seat", forbidden)
    monkeypatch.setattr(dodo, "_farm_build", forbidden)

    def report():
        directory = dodo._machinist_review_dir("probe")
        directory.mkdir(parents=True, exist_ok=True)
        selected = dodo._machinist_review_settings()
        blind = {
            "reviewer": selected.reviewer, "model": selected.model, "effort": selected.effort,
        }
        judge = {
            "reviewer": selected.judge_reviewer, "model": selected.judge_model,
            "effort": selected.judge_effort, "skipped": state["skipped"],
        }
        runs = []
        for index in range(1, 4):
            run_id = f"r{index}"
            error = "provider down" if run_id in state["run_errors"] else None
            runs.append({"run_id": run_id, "error": error, "report": "old/worktree/report.json"})
            if run_id in state["missing_runs"]:
                continue
            path = directory / "probe" / "runs" / run_id / "probe.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({**blind, "error": error}), encoding="utf-8")
        if not state["skipped"]:
            path = directory / "probe" / "judge" / "probe.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(judge), encoding="utf-8")
        (directory / "probe.aggregate.json").write_text(
            json.dumps({
                "name": "probe", "kind": "part", "verdict": state["verdict"],
                "gating_count": 0 if state["verdict"] == "SHIP" else 2,
                "error": state["error"], **blind, "judge": judge, "runs": runs,
            }),
            encoding="utf-8",
        )
        if state["edit"] is not None:
            state["edit"](directory)

    def probe(_key, outputs, label, _span):
        calls["probe"].append(label)
        if state["hit"]:
            report()
            return "hit"
        return "miss"

    def run(command, *_args, **_kwargs):
        calls["run"] += 1
        calls["commands"].append(command)
        report()
        return state["code"]

    def store(_key, outputs, _label):
        calls["store"] += 1
        assert outputs == [dodo._machinist_review_dir("probe")]
        assert not dodo._machinist_review_stamp("probe").exists()
        return "stored"

    monkeypatch.setattr(dodo, "_probe_cache", probe)
    monkeypatch.setattr(dodo, "_run_subprocess", run)
    monkeypatch.setattr(dodo._cache, "store", store)
    return SimpleNamespace(
        dodo=dodo,
        calls=calls,
        state=state,
        original_probe=original_probe,
        original_store=original_store,
    )


@pytest.mark.parametrize("verdict", ["SHIP", "FIX", "ERROR"])
@pytest.mark.parametrize("mode", REVIEWED_MODES)
@pytest.mark.parametrize("hit", [False, True])
def test_cached_verdict_policy_and_error_publication(action, verdict, mode, hit):
    action.state.update(verdict=verdict, hit=hit, code=0 if verdict == "SHIP" else 1)
    if mode is MachinistReviewMode.ENFORCE and verdict != "SHIP":
        with pytest.raises(RuntimeError, match=f"{verdict}, gating_count=2"):
            action.dodo._cached_machinist_review_action("probe", mode)
    else:
        action.dodo._cached_machinist_review_action("probe", mode)
    assert action.calls["run"] == int(not hit)
    assert action.calls["store"] == int(not hit and verdict != "ERROR")
    assert len(action.calls["warnings"]) == int(
        mode is MachinistReviewMode.LEARN and verdict != "SHIP"
    )
    assert action.dodo._machinist_review_stamp("probe").exists() == (
        verdict != "ERROR"
        and not (mode is MachinistReviewMode.ENFORCE and verdict == "FIX")
    )


@pytest.mark.parametrize("executor", ["local", "farm"])
@pytest.mark.parametrize("outcome", ["stored", "error", "provider_error"])
def test_forced_review_uses_shared_refresh_probe_store_and_freshness(
    action, monkeypatch, executor, outcome
):
    dodo = action.dodo
    label = "check:machinist_review:probe"
    reason = "Owner - Refresh cached judgement"
    refreshes = []
    monkeypatch.setenv("HARMONIC_EXECUTOR", executor)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv(
        "HARMONIC_CACHE_REFRESH", json.dumps({"labels": [label], "reason": reason})
    )
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    dodo.DRAWINGS_BY_NAME["probe"].script.write_text(
        "MACHINIST_REVIEW = MachinistReviewMode.LEARN\n"
    )
    dodo._reviewed_drawings.cache_clear()
    monkeypatch.setattr(dodo, "_probe_cache", action.original_probe)
    monkeypatch.setattr(dodo._cache, "store", action.original_store)
    monkeypatch.setattr(
        dodo._cache, "restore", lambda *_args: pytest.fail("forced review restored")
    )
    monkeypatch.setattr(
        dodo._cache, "note_refresh", lambda *args: refreshes.append(args)
    )
    monkeypatch.setattr(dodo._cache, "_REFRESH_ETAGS", {(label, "a" * 64): None})

    def publish(_key, outputs, published_label, *, replace_etag=None):
        action.calls["store"] += 1
        assert outputs == [dodo._machinist_review_dir("probe")]
        assert published_label == label
        assert not dodo._machinist_review_stamp("probe").exists()
        return outcome

    monkeypatch.setattr(dodo._cache, "_store", publish)
    task = next(dodo._machinist_review_tasks())
    assert False in task["uptodate"]
    if outcome == "provider_error":
        action.state.update(verdict="ERROR", error="provider unavailable", code=1)
    run, arguments = task["actions"][0]
    if outcome == "stored":
        run(*arguments)
    else:
        expected = "ERROR" if outcome == "provider_error" else "did not store outputs"
        with pytest.raises(RuntimeError, match=expected):
            run(*arguments)
    assert refreshes == [(label, "a" * 64, reason)]
    assert action.calls["run"] == 1
    assert action.calls["store"] == int(outcome != "provider_error")
    assert dodo._machinist_review_stamp("probe").exists() == (outcome == "stored")
    assert not action.calls["warnings"]


@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize(
    ("verdict", "error"),
    [
        ("ERROR", None),
        ("ERROR", "provider unavailable"),
        ("SHIP", "provider unavailable"),
    ],
)
def test_provider_error_is_not_cached_and_forced_refresh_overrides_learning(
    action, monkeypatch, refresh, verdict, error
):
    action.state.update(verdict=verdict, error=error, code=int(verdict == "ERROR"))
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
    if refresh:
        monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
        monkeypatch.setenv(
            "HARMONIC_CACHE_REFRESH",
            json.dumps(
                {
                    "labels": ["check:machinist_review:probe"],
                    "reason": "provider recovery requested",
                }
            ),
        )
        with pytest.raises(RuntimeError, match=f"{verdict}, gating_count="):
            action.dodo._cached_machinist_review_action(
                "probe", MachinistReviewMode.LEARN
            )
    else:
        action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.LEARN)
        assert f"{verdict}, gating_count=" in action.calls["warnings"][0]
    assert action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()
    assert bool(action.calls["warnings"]) is not refresh


def test_failed_runner_cannot_reuse_a_previous_aggregate(action, monkeypatch):
    directory = action.dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    (directory / "probe.aggregate.json").write_text('{"verdict": "SHIP"}')
    monkeypatch.setattr(action.dodo, "_run_subprocess", lambda *_args, **_kwargs: 2)
    action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.LEARN)
    assert action.calls["store"] == 0
    assert "ERROR" in action.calls["warnings"][0]


def test_cache_hit_replaces_instead_of_mixing_previous_evidence(action):
    directory = action.dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    old_attempt = directory / "unrelated-old-attempt.json"
    old_attempt.write_text("{}")
    action.state["hit"] = True
    action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.LEARN)
    assert not old_attempt.exists()
    assert action.calls["run"] == 0
    assert action.calls["store"] == 0


@pytest.mark.parametrize("mode", REVIEWED_MODES)
def test_farm_restore_lock_uses_the_drawing_error_policy(action, monkeypatch, mode):
    def locked(*_args):
        raise action.dodo._cache.RestoreLocked(
            "probe", "a" * 64, PermissionError("locked")
        )

    monkeypatch.setattr(action.dodo, "_probe_cache", locked)
    if mode is MachinistReviewMode.ENFORCE:
        with pytest.raises(RuntimeError, match="ERROR"):
            action.dodo._cached_machinist_review_action("probe", mode)
    else:
        action.dodo._cached_machinist_review_action("probe", mode)
        assert "ERROR" in action.calls["warnings"][0]
    assert action.calls["run"] == action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()


def test_invalid_refresh_carrier_is_not_demoted_to_a_learning_warning(
    action, monkeypatch
):
    def malformed(*_args):
        raise ValueError("malformed HARMONIC_CACHE_REFRESH")

    monkeypatch.setattr(action.dodo, "_probe_cache", malformed)
    with pytest.raises(ValueError, match="HARMONIC_CACHE_REFRESH"):
        action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.LEARN)
    assert not action.calls["warnings"]


@pytest.mark.parametrize("winner,loser", [("FIX", "SHIP"), ("SHIP", "FIX")])
@pytest.mark.parametrize("mode", REVIEWED_MODES)
def test_losing_review_restores_full_winner_and_rereads_verdict(
    action, monkeypatch, winner, loser, mode
):
    from test_artifact_cache import _BlockBlobService

    dodo = action.dodo
    cache = dodo._cache
    root = dodo.REPO_ROOT
    directory = dodo._machinist_review_dir("probe")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", root / "cad" / "out")
    monkeypatch.setattr(cache, "_REPORTS", dodo.REPORTS)
    monkeypatch.setattr(cache, "_EVENTS_LOG", dodo.REPORTS / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", dodo.REPORTS / "cache-keys")
    backend = cache._BlobBackend(_BlockBlobService())
    monkeypatch.setattr(cache, "_BACKEND", backend)
    monkeypatch.setattr(
        dodo, "_cache_key",
        lambda deps, label=None: cache.cache_key(deps, dodo.ContentChecker._digest, label),
    )
    key = dodo._cache_key(dodo._machinist_review_file_deps("probe"))
    directory.mkdir(parents=True)
    (directory / "probe.aggregate.json").write_text(json.dumps({
        "name": "probe", "kind": "part", "verdict": winner,
        "gating_count": 2 if winner == "FIX" else 0, "error": None,
    }), encoding="utf-8")
    (directory / "winner-evidence.json").write_text('{"producer":"A"}', encoding="utf-8")
    winning_archive = cache._pack([directory])
    # The first probe misses. Another producer publishes only once our own
    # expensive review has completed, before its conditional publication.
    run = dodo._run_subprocess
    action.state.update(verdict=loser, code=int(loser == "FIX"))

    def competing_review(*args, **kwargs):
        code = run(*args, **kwargs)
        (directory / "loser-only-attempt.json").write_text("{}", encoding="utf-8")
        backend.put(key, winning_archive)
        return code

    monkeypatch.setattr(dodo, "_run_subprocess", competing_review)
    monkeypatch.setattr(dodo, "_probe_cache", action.original_probe)
    monkeypatch.setattr(cache, "store", action.original_store)
    if mode is MachinistReviewMode.ENFORCE and winner == "FIX":
        with pytest.raises(RuntimeError, match="FIX, gating_count=2"):
            dodo._cached_machinist_review_action("probe", mode)
    else:
        dodo._cached_machinist_review_action("probe", mode)
    assert dodo._read_machinist_aggregate("probe")["verdict"] == winner
    assert (directory / "winner-evidence.json").is_file()
    assert not (directory / "loser-only-attempt.json").exists()
    assert dodo._machinist_review_stamp("probe").exists() == (
        winner == "SHIP" or mode is MachinistReviewMode.LEARN
    )
    assert action.calls["run"] == 1
    assert cache.last_stored_key("check:machinist_review:probe") is None


@pytest.mark.parametrize("failure", ["missing", "locked", "cleanup", "invalid-aggregate"])
def test_failed_review_adoption_is_fatal_even_in_learn(action, monkeypatch, failure):
    dodo = action.dodo
    directory = dodo._machinist_review_dir("probe")
    monkeypatch.setattr(dodo._cache, "store", lambda *_args: "lost")

    def restore(key, outputs, label):
        assert outputs == [directory]
        if failure == "locked":
            raise dodo._cache.RestoreLocked(label, key, PermissionError("locked"))
        if failure == "invalid-aggregate":
            directory.mkdir()
            (directory / "probe.aggregate.json").write_text("{}", encoding="utf-8")
            return True
        return False

    monkeypatch.setattr(dodo._cache, "restore", restore)
    if failure == "cleanup":
        def locked_cleanup(_path):
            raise PermissionError("report directory locked")

        monkeypatch.setattr(dodo.shutil, "rmtree", locked_cleanup)
    with pytest.raises(RuntimeError, match="canonical|share-locked"):
        dodo._cached_machinist_review_action("probe", MachinistReviewMode.LEARN)
    assert not dodo._machinist_review_stamp("probe").exists()
    assert not action.calls["warnings"]


def test_only_opted_in_drawings_are_submitter_only_build_and_release_leaves(
    dodo,
    tmp_path,
    monkeypatch,
):
    import build

    stems = list(dodo.DRAWINGS_BY_NAME)
    declared = {
        dodo.DRAWINGS_BY_NAME[stems[0]].script: MachinistReviewMode.LEARN,
        dodo.DRAWINGS_BY_NAME[stems[1]].script: MachinistReviewMode.ENFORCE,
    }
    monkeypatch.setattr(
        dodo,
        "mode_for_drawing",
        lambda script: declared.get(script, MachinistReviewMode.OFF),
    )
    leaves = {task["name"]: task for task in dodo._machinist_review_tasks()}
    expected = {f"machinist_review:{stem}" for stem in stems[:2]}
    assert set(leaves) == expected
    reviews_in = [
        name for name in dodo.task_build()["task_dep"]
        if name.startswith("check:machinist_review:")
    ]
    assert set(reviews_in) == {f"check:{name}" for name in leaves}
    assert {f"check:{name}" for name in leaves} <= set(dodo.task_release()["task_dep"])
    assert f"check:machinist_review:{stems[2]}" not in dodo.task_release()["task_dep"]
    tasks = list(load_tasks(vars(dodo), [], allow_delayed=False))
    control = build._validate_farm_selection(tasks, ["build"])
    (tmp_path / "agent").mkdir()
    (tmp_path / "agent" / "protocol.py").write_text("# intercepted protocol")
    (tmp_path / "pyproject.toml").write_text("# intercepted project")
    queried = []

    def protocol_query(_argv, **kwargs):
        queried.extend(json.loads(kwargs["input"]))
        return SimpleNamespace(
            returncode=0,
            stderr="",
            stdout=json.dumps(
                {
                    "refused": [
                        task
                        for task in queried
                        if task.startswith("check:machinist_review:")
                    ],
                    "agent_identity": "fixture",
                    "agent_version": "fixture",
                }
            ),
        )

    monkeypatch.setattr(build.subprocess, "run", protocol_query)
    monkeypatch.setattr(build, "_pool_home", lambda: tmp_path)
    dispatchable, _identity = build._require_leaf_admission(control)
    assert queried == dispatchable
    assert dispatchable
    assert not {f"check:{name}" for name in leaves} & set(dispatchable)
    for name, task in leaves.items():
        stem = name.split(":", 1)[1]
        assert (
            str(dodo.DRAWINGS_BY_NAME[stem].outputs["pdf"].resolve())
            in task["file_dep"]
        )
        assert task["task_dep"] == [f"drawing:{stem}"]
        assert task["actions"][0][0]._remote_cache_action
        assert not getattr(task["actions"][0][0], "_farm_leaf_action", False)


def test_invalid_declaration_is_checked_when_generating_graph(
    dodo, tmp_path, monkeypatch
):
    stem, original = next(iter(dodo.DRAWINGS_BY_NAME.items()))
    script = tmp_path / "draw_invalid.py"
    script.write_text("MACHINIST_REVIEW = 'typo'\n")
    monkeypatch.setattr(
        dodo,
        "DRAWINGS_BY_NAME",
        {
            stem: replace(original, script_name=str(script)),
        },
    )
    with pytest.raises(ValueError, match="MACHINIST_REVIEW"):
        list(dodo._machinist_review_tasks())


@pytest.mark.parametrize(("field", "value"), [
    ("reviewer", "codex"), ("model", "alternate"), ("effort", "high"),
    ("judge_reviewer", "codex"), ("judge_model", "alternate"), ("judge_effort", "high"),
])
def test_selection_is_both_doit_and_remote_cache_input(inputs, monkeypatch, field, value):
    dodo = inputs.module
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n")
    default = review_settings.resolve_settings()
    first = next(dodo._machinist_review_tasks())
    tracker = first["uptodate"][0]
    saved = {"_config_changed": tracker.config_digest}
    key = dodo._cache_key(first["file_dep"])
    selected = replace(default, **{field: value})
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    changed = next(dodo._machinist_review_tasks())
    assert not changed["uptodate"][0](None, saved)
    assert dodo._cache_key(changed["file_dep"]) != key
    assert dodo._machinist_review_file_deps("probe") == changed["file_dep"]
    monkeypatch.setenv(review_settings.SETTINGS_ENV, default.canonical())
    assert dodo._cache_key(dodo._machinist_review_file_deps("probe")) == key


def test_selection_sidecar_is_stable_content_addressed_and_report_root_scoped(inputs):
    dodo = inputs.module
    default = review_settings.resolve_settings()
    codex = review_settings.resolve_settings(reviewer="codex", judge_reviewer="codex")
    root = dodo.REPORTS.resolve()
    first = Path(dodo._machinist_review_settings_dep(root, default))
    timestamp = first.stat().st_mtime_ns
    dodo._machinist_review_settings_dep.cache_clear()
    assert Path(dodo._machinist_review_settings_dep(root, default)) == first
    assert first.stat().st_mtime_ns == timestamp
    second = Path(dodo._machinist_review_settings_dep(root, codex))
    assert first != second
    assert first.read_text(encoding="utf-8") == default.identity() + "\n"
    assert second.read_text(encoding="utf-8") == codex.identity() + "\n"
    assert Path(dodo._machinist_review_settings_dep(root / "other", default)) != first


def test_all_off_graph_validates_current_carrier_after_dodo_preimport(dodo, monkeypatch):
    monkeypatch.setattr(dodo, "_drawing_order", lambda: [])
    monkeypatch.setattr(
        dodo, "_machinist_review_settings_dep",
        lambda *_args: pytest.fail("all-OFF validation materialized a sidecar"),
    )
    assert list(dodo._machinist_review_tasks()) == []
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken")
    with pytest.raises(ValueError, match=review_settings.SETTINGS_ENV):
        list(dodo._machinist_review_tasks())
    monkeypatch.setenv(
        review_settings.SETTINGS_ENV, review_settings.resolve_settings(reviewer="codex").canonical(),
    )
    assert list(dodo._machinist_review_tasks()) == []


@pytest.mark.parametrize("hit", [False, True])
def test_missing_explicitly_failed_attempt_does_not_reject_partial_ship(action, hit):
    action.state.update(hit=hit, run_errors=("r1",), missing_runs=("r1",))
    action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.ENFORCE)
    assert action.calls["store"] == int(not hit)
    assert action.dodo._machinist_review_stamp("probe").exists()


@pytest.mark.parametrize("hit", [False, True])
def test_partial_run_ship_keeps_matching_failed_run_provenance_cacheable(action, hit):
    action.state.update(hit=hit, run_errors=("r1",))
    action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.ENFORCE)
    assert action.calls["run"] == int(not hit)
    assert action.calls["store"] == int(not hit)
    assert action.dodo._machinist_review_stamp("probe").exists()
    assert not (action.dodo._machinist_review_dir("probe") / "probe" / "judge").exists()


@pytest.mark.parametrize("hit", [False, True])
def test_all_run_error_skips_judge_without_publishing_or_stamping(action, hit):
    action.state.update(
        hit=hit, verdict="ERROR", error="all runs failed", code=1,
        run_errors=("r1", "r2", "r3"),
    )
    with pytest.raises(RuntimeError, match="all runs failed"):
        action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.ENFORCE)
    assert action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()
    assert not (action.dodo._machinist_review_dir("probe") / "probe" / "judge").exists()


@pytest.mark.parametrize("hit", [False, True])
@pytest.mark.parametrize("target", ["aggregate", "run", "judge", "missing_run", "run_ids"])
def test_wrong_selection_or_incomplete_reports_never_cache_or_stamp(action, hit, target):
    action.state.update(hit=hit, skipped=False)

    def corrupt(directory):
        aggregate = directory / "probe.aggregate.json"
        if target == "missing_run":
            (directory / "probe" / "runs" / "r2" / "probe.json").unlink()
            return
        path = {
            "aggregate": aggregate, "run": directory / "probe" / "runs" / "r1" / "probe.json",
            "judge": directory / "probe" / "judge" / "probe.json", "run_ids": aggregate,
        }[target]
        report = json.loads(path.read_text(encoding="utf-8"))
        if target == "run_ids":
            report["runs"][2]["run_id"] = "r2"
        else:
            report["effort"] = "wrong"
        path.write_text(json.dumps(report), encoding="utf-8")

    action.state["edit"] = corrupt
    with pytest.raises(RuntimeError):
        action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.ENFORCE)
    assert action.calls["run"] == int(not hit)
    assert action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()


def test_codex_action_emits_exact_selected_options_and_checks_executed_judge(action, monkeypatch):
    selected = review_settings.resolve_settings(
        reviewer="codex", model="gpt-6-astra", effort="high",
        judge_reviewer="codex", judge_model="gpt-6-astra", judge_effort="high",
    )
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    action.state["skipped"] = False
    action.dodo._cached_machinist_review_action("probe", MachinistReviewMode.ENFORCE)
    command = action.calls["commands"][0]
    assert command[command.index("--runs") + 1] == "3"
    start = command.index("--reviewer")
    assert command[start:start + 12] == selected.cli_args()
    assert action.calls["store"] == 1


def test_review_status_and_action_dependencies_use_the_same_selected_key(inputs, monkeypatch):
    dodo = inputs.module
    selected = review_settings.resolve_settings(
        reviewer="codex", effort="high", judge_reviewer="codex", judge_effort="high",
    )
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    label = "check:machinist_review:probe"
    dependencies = dodo._machinist_review_file_deps("probe")
    expected = dodo._cache_key(dependencies, label)
    observed = []
    monkeypatch.setattr(dodo, "_cache_rows", lambda: [(label, dodo._machinist_review_file_deps("probe"))])
    monkeypatch.setattr(dodo._cache, "probe", lambda key: (observed.append(key), False)[1])
    monkeypatch.setattr(dodo._cache, "last_stored_key", lambda _label: None)
    dodo._cache_status([label])
    assert observed == [expected]


def test_selection_never_enters_native_dependency_inventories(dodo, monkeypatch):
    def native_rows():
        return {
            label: dependencies for label, dependencies in dodo._cache_rows()
            if label.startswith(("part:", "assembly:", "drawing:", "verify_soundness:"))
        }

    before = native_rows()
    before_keys = {label: dodo._cache_key(deps, label) for label, deps in before.items()}
    monkeypatch.setenv(
        review_settings.SETTINGS_ENV,
        review_settings.resolve_settings(
            reviewer="codex", effort="high", judge_reviewer="codex", judge_effort="high",
        ).canonical(),
    )
    after = native_rows()
    assert after == before
    assert {label: dodo._cache_key(deps, label) for label, deps in after.items()} == before_keys
    assert any(label.startswith("drawing:") for label in before)
    assert any(label.startswith("part:") for label in before)
    assert any(label.startswith("assembly:") for label in before)
    assert all(
        "_machinist_review_settings.py" != Path(dependency).name
        and ".machinist-review-settings" not in Path(dependency).parts
        for dependencies in before.values() for dependency in dependencies
    )


def test_same_selection_sidecar_materialization_is_serialized(inputs, monkeypatch):
    dodo = inputs.module
    writer = dodo._write_digest_sidecar
    active = 0
    maximum = 0
    guard = threading.Lock()
    barrier = threading.Barrier(4, timeout=10)

    def record(path, digest):
        nonlocal active, maximum
        with guard:
            active += 1
            maximum = max(maximum, active)
        try:
            return writer(path, digest)
        finally:
            with guard:
                active -= 1

    monkeypatch.setattr(dodo, "_write_digest_sidecar", record)
    selected = review_settings.resolve_settings(reviewer="codex", effort="high")

    def materialize(_index):
        barrier.wait()
        return dodo._machinist_review_settings_dep.__wrapped__(dodo.REPORTS.resolve(), selected)

    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(materialize, range(4)))
    assert len(set(paths)) == 1
    assert maximum == 1
    assert Path(paths[0]).read_text(encoding="utf-8") == selected.identity() + "\n"


def test_independent_submitter_processes_share_only_identical_selection_sidecars(inputs):
    dodo = inputs.module
    repository = Path(dodo.__file__).resolve().parent
    script = (
        "from pathlib import Path; import sys; import dodo; "
        "from _machinist_review_settings import resolve_settings; "
        "print(dodo._machinist_review_settings_dep("
        "Path(sys.argv[1]), resolve_settings(reviewer=sys.argv[2])))"
    )

    def materialize(reviewer):
        result = subprocess.run(
            [sys.executable, "-c", script, str(dodo.REPORTS.resolve()), reviewer],
            cwd=repository, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return Path(result.stdout.strip().splitlines()[-1])

    with ThreadPoolExecutor(max_workers=3) as pool:
        claude, codex_one, codex_two = list(pool.map(materialize, ("claude", "codex", "codex")))
    assert claude != codex_one == codex_two
    assert claude.read_text(encoding="utf-8") == review_settings.resolve_settings().identity() + "\n"
    assert codex_one.read_text(encoding="utf-8") == (
        review_settings.resolve_settings(reviewer="codex").identity() + "\n"
    )

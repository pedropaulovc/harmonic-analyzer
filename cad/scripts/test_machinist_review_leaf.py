"""Cached machinist verdicts and AST enforcement, without models or SolidWorks."""

from __future__ import annotations

import ast
from concurrent.futures import ThreadPoolExecutor
import threading
from contextlib import nullcontext
from dataclasses import replace
import importlib.util
import os
import sys
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from doit.loader import load_tasks

from _buildgraph import RECIPE_SKIP_MODULES
from _machinist_review_mode import MachinistReviewMode, mode_for_drawing
import machinist_review_config as review_settings

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
    monkeypatch.delenv("HARMONIC_MACHINIST_REVIEWER", raising=False)
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
                # Registry is only used by interactive name/--all selectors.
                # The leaf supplies PDF/kind/name and always passes --force,
                # so the lazy _drawing_diff precheck import is unreachable too.
                if local.is_file() and name not in {"_drawing_registry", "_drawing_diff"}:
                    pending.append(local)
    return found


def test_declared_review_modules_equal_the_real_import_closure(dodo):
    assert _local_import_closure(dodo.SCRIPTS_DIR / "machinist_review.py") == set(
        dodo._MACHINIST_REVIEW_MODULES
    )


def test_forced_leaf_never_imports_or_calls_diff(inputs, monkeypatch):
    import builtins
    import sys

    original_import = builtins.__import__

    def no_diff_import(name, *args, **kwargs):
        assert name != "_drawing_diff", "forced leaf imported PDF diff implementation"
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_diff_import)
    spec = importlib.util.spec_from_file_location(
        "_forced_leaf_review", REPO_ROOT / "cad" / "scripts" / "machinist_review.py"
    )
    review = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, review)
    spec.loader.exec_module(review)
    calls = []

    def clean_review(package, **kwargs):
        calls.append(package)
        result = replace(
            review._failed_review(
                package, kwargs["reviewer"], kwargs["model"], kwargs["effort"],
                [review._sha256(source) for source in package.sources], "unused",
            ),
            verdict={
                "verdict": "SHIP",
                "summary": "No findings.",
                **{category: [] for category in review.FINDING_KEYS},
            },
            error=None,
            passed=True,
            sheet_count=1,
            extra={"inspection_proven": True},
        )
        review.write_review(result, kwargs["report_dir"])
        return result

    def no_precheck(*args, **kwargs):
        pytest.fail("forced leaf invoked precheck despite --force")

    monkeypatch.setattr(review, "review_package", clean_review)
    monkeypatch.setattr(review, "_review_session", no_precheck)
    selected = inputs.module._machinist_review_settings()
    assert isinstance(selected, review_settings.ReviewSettings)
    command = inputs.module._machinist_review_command("probe", selected)
    assert command.count("--force") == 1
    assert review.main(command[2:]) == 0
    assert len(calls) == 3
    assert all(package.before_sources == () for package in calls)
    aggregate = inputs.module._read_machinist_aggregate("probe", selected)
    assert aggregate["precheck"]["forced"] is True
    assert aggregate["precheck"]["skipped"] is False
    assert aggregate["error"] is None


def test_explicit_pdf_command_cannot_select_a_registry_package(dodo):
    stem = "pd_platen_guide"
    command = dodo._machinist_review_command(stem, dodo._machinist_review_settings())
    assert command[0] == dodo.sys.executable
    assert command[2:] == [
        "--pdf",
        str(dodo.DRAWINGS_BY_NAME[stem].outputs["pdf"]),
        "--name",
        stem,
        "--kind",
        "part",
        "--force",
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
    (scripts / "_drawing_diff.py").write_text("# unused PDF diff\n", encoding="utf-8")
    pairing = root / "cad" / "comparisons" / "tools" / "release_diff.py"
    pairing.parent.mkdir(parents=True)
    pairing.write_text("# release identity pairing\n", encoding="utf-8")
    for name in (
        "machinist_review_part.md",
        "machinist_review_assembly.md",
        "machinist_review_part_severity.md",
        "machinist_review_assembly_severity.md",
        "machinist_review_schema.json",
        "machinist_review_judge.md",
        "machinist_review_judge_schema.json",
        "machinist_review_precheck.md",
        "machinist_review_precheck_schema.json",
    ):
        (prompts / name).write_text("{}", encoding="utf-8")
    guidelines = root / "cad" / "docs" / "drawing-guidelines.md"
    guidelines.parent.mkdir()
    guidelines.write_text("guidelines", encoding="utf-8")
    config = root / "cad" / "config"
    (config / "parts").mkdir(parents=True)
    (config / "assemblies").mkdir()
    for name in ("current-identity-map.json", "identity-migration-map.json"):
        (config / name).write_text("{}", encoding="utf-8")
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


def _review_key(dodo, stem="probe", label=None, settings=None):
    selected = dodo._machinist_review_settings() if settings is None else settings
    return dodo._machinist_review_cache_key(stem, selected, label)


def test_key_changes_only_with_review_inputs(inputs):
    dodo = inputs.module

    def key():
        return _review_key(dodo)

    initial = key()
    changed_inputs = [
        Path(path) for path in dodo._machinist_review_file_deps("probe")
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


@pytest.mark.parametrize(
    "relative_path",
    [
        "cad/scripts/_drawing_diff.py",
        "cad/comparisons/tools/release_diff.py",
        "cad/config/current-identity-map.json",
        "cad/config/identity-migration-map.json",
        "cad/scripts/prompts/machinist_review_precheck.md",
        "cad/scripts/prompts/machinist_review_precheck_schema.json",
    ],
)
def test_bypassed_precheck_inputs_do_not_invalidate_forced_review_cache(
    inputs, relative_path
):
    dodo = inputs.module
    path = inputs.root / relative_path
    assert str(path.resolve()) not in dodo._machinist_review_file_deps("probe")
    initial = _review_key(dodo)
    path.write_bytes(path.read_bytes() + b"\nchanged precheck dependency\n")
    assert _review_key(dodo) == initial


def test_key_tracks_only_selected_kind_severity_contract(inputs):
    dodo = inputs.module

    def key():
        return _review_key(dodo)

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
    initial = _review_key(dodo)
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
        assert _review_key(dodo) == initial


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
    key = _review_key(dodo)
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n")
    assert not tracker()(None, saved)
    assert _review_key(dodo) == key
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
    original_key = dodo._machinist_review_cache_key
    settings = dodo._machinist_review_settings()
    calls = {"run": 0, "store": 0, "warnings": [], "probe": [], "commands": []}
    state = {
        "verdict": "SHIP", "error": None, "hit": False, "code": 0,
        "skipped": True, "run_errors": (), "missing_runs": (), "edit": None,
        "settings": settings,
    }
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", lambda *_args: "a" * 64)
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
        selected = state["settings"]
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
        report=report,
        original_probe=original_probe,
        original_key=original_key,
        settings=settings,
        original_store=original_store,
    )


@pytest.fixture
def review_sessions(monkeypatch):
    """Replace provider execution, retaining canonical session report publication."""
    import machinist_review as mr

    seen = []

    def session(package, **kwargs):
        findings = kwargs.get("judge_findings")
        role = "judge" if findings is not None else "reviewer"
        seen.append((role, kwargs["reviewer"], kwargs["model"], kwargs["effort"]))
        claim = {
            "where": "front view", "issue": "hermetic claim", "fix": "check the sheet",
        }
        if findings is None:
            verdict = {
                "verdict": "FIX", "summary": "requires adjudication",
                "blockers": [claim], "over_specification": [], "clarity": [], "minor": [],
            }
        else:
            verdict = {"clusters": [{
                **claim, "category": "blockers", "decision": "rejected",
                "member_ids": [finding["id"] for finding in findings],
                "reason": "The hermetic judge rejects this synthetic claim.",
            }]}
        review = replace(
            mr._failed_review(
                package, kwargs["reviewer"], kwargs["model"], kwargs["effort"],
                [mr._sha256(source) for source in package.sources], "unused",
            ),
            verdict=verdict, error=None, passed=findings is not None, sheet_count=1,
            prompt_sha256="hermetic-session", extra={"inspection_proven": True},
        )
        mr.write_review(review, kwargs["report_dir"])
        return review

    monkeypatch.setattr(mr, "_review_session", session)
    return SimpleNamespace(module=mr, seen=seen)


@pytest.mark.parametrize(
    ("selector", "expected"),
    [
        (None, ("claude", "claude-opus-5-5", "medium")),
        ("claude", ("claude", "claude-opus-5-5", "medium")),
        ("codex", ("codex", "gpt-6-astra", "low")),
    ],
)
def test_registered_selection_reaches_real_cli_reviewers_and_judge(
    action, review_sessions, monkeypatch, selector, expected
):
    dodo = action.dodo
    if selector is not None:
        monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", selector)
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    monkeypatch.setattr(
        dodo, "mode_for_drawing", lambda _script: MachinistReviewMode.ENFORCE
    )
    task = next(dodo._machinist_review_tasks())
    # The task's frozen settings own command AND key even if the ambient
    # selector or internal carrier changes after graph generation.
    snapshot = task["actions"][0][1][2]
    assert isinstance(snapshot, str)
    selected = review_settings.from_carrier(snapshot)
    assert selected == review_settings.resolve_settings(
        reviewer=expected[0], judge_reviewer=expected[0],
    )
    assert snapshot == selected.canonical()
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid-after-snapshot")
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken-after-snapshot")
    keyed_settings = []
    monkeypatch.setattr(
        dodo, "_machinist_review_cache_key",
        lambda stem, settings, label: keyed_settings.append(settings) or "a" * 64,
    )

    def run(command, *_args, **_kwargs):
        return review_sessions.module.main(command[2:])

    monkeypatch.setattr(dodo, "_run_subprocess", run)
    execute, arguments = task["actions"][0]
    execute(*arguments)
    assert keyed_settings == [selected]
    assert sorted(review_sessions.seen) == sorted([
        ("reviewer", *expected), ("reviewer", *expected), ("reviewer", *expected),
        ("judge", *expected),
    ])
    aggregate = dodo._read_machinist_aggregate("probe", selected)
    assert (aggregate["reviewer"], aggregate["model"], aggregate["effort"]) == expected
    assert tuple(aggregate["judge"][name] for name in ("reviewer", "model", "effort")) == expected
    assert aggregate["judge"]["skipped"] is False
    assert aggregate["verdict"] == "SHIP"
    assert dodo._machinist_review_stamp("probe").is_file()


@pytest.mark.parametrize("selected", [
    review_settings.resolve_settings(
        reviewer="codex", model="explicit-review", effort="high",
        judge_reviewer="claude", judge_model="explicit-judge", judge_effort="low",
    ),
    review_settings.resolve_settings(
        reviewer="claude", model="explicit-review", effort="low",
        judge_reviewer="codex", judge_model="explicit-judge", judge_effort="high",
    ),
])
def test_complete_carrier_reaches_real_cli_with_independent_frozen_roles(
    action, review_sessions, monkeypatch, selected,
):
    dodo = action.dodo
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid-but-carrier-is-complete")
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    monkeypatch.setattr(
        dodo, "mode_for_drawing", lambda _script: MachinistReviewMode.ENFORCE,
    )
    task = next(dodo._machinist_review_tasks())
    snapshot = task["actions"][0][1][2]
    assert isinstance(snapshot, str)
    assert snapshot == selected.canonical()
    assert review_settings.from_carrier(snapshot) == selected
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken-after-graph")
    keyed = []
    monkeypatch.setattr(
        dodo, "_machinist_review_cache_key",
        lambda _stem, settings, _label: keyed.append(settings) or "a" * 64,
    )
    monkeypatch.setattr(
        dodo, "_run_subprocess",
        lambda command, *_args, **_kwargs: review_sessions.module.main(command[2:]),
    )
    execute, arguments = task["actions"][0]
    execute(*arguments)
    assert keyed == [review_settings.from_carrier(snapshot)]
    blind = (selected.reviewer, selected.model, selected.effort)
    judge = (selected.judge_reviewer, selected.judge_model, selected.judge_effort)
    assert sorted(review_sessions.seen) == sorted([
        ("reviewer", *blind), ("reviewer", *blind), ("reviewer", *blind),
        ("judge", *judge),
    ])
    aggregate = dodo._read_machinist_aggregate(
        "probe", review_settings.from_carrier(snapshot)
    )
    assert (aggregate["reviewer"], aggregate["model"], aggregate["effort"]) == blind
    assert tuple(aggregate["judge"][field] for field in ("reviewer", "model", "effort")) == judge
    assert aggregate["judge"]["skipped"] is False
    assert aggregate["verdict"] == "SHIP"
    assert dodo._machinist_review_stamp("probe").is_file()


def test_graph_freezes_one_six_field_snapshot_before_yielding_any_review(inputs, monkeypatch):
    dodo = inputs.module
    selected = review_settings.resolve_settings(
        reviewer="codex", model="review-model", effort="high",
        judge_reviewer="claude", judge_model="judge-model", judge_effort="low",
    )
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    monkeypatch.setitem(dodo.DRAWINGS_BY_NAME, "other", inputs.spec)
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe", "other"])
    monkeypatch.setattr(
        dodo, "mode_for_drawing", lambda _script: MachinistReviewMode.LEARN,
    )
    selections = []
    select = dodo._machinist_review_settings

    def select_once():
        selections.append(None)
        return select()

    monkeypatch.setattr(dodo, "_machinist_review_settings", select_once)
    tasks = dodo._machinist_review_tasks()
    first = next(tasks)
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken-after-first-task")
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid-after-first-task")
    second = next(tasks)
    snapshot = first["actions"][0][1][2]
    assert isinstance(snapshot, str)
    assert snapshot == selected.canonical()
    assert review_settings.from_carrier(snapshot) == selected
    assert second["actions"][0][1][2] == snapshot
    assert list(tasks) == []
    assert selections == [None]


@pytest.mark.parametrize("mode", REVIEWED_MODES)
@pytest.mark.parametrize(
    ("selector", "explicit"),
    [
        (None, None),
        ("claude", None),
        ("codex", None),
        ("invalid-with-complete-carrier", review_settings.resolve_settings(
            reviewer="codex", model="explicit-review", effort="high",
            judge_reviewer="claude", judge_model="explicit-judge", judge_effort="low",
        )),
        ("invalid-with-complete-carrier", review_settings.resolve_settings(
            reviewer="claude", model="explicit-review", effort="low",
            judge_reviewer="codex", judge_model="explicit-judge", judge_effort="high",
        )),
    ],
)
def test_registered_review_serializes_with_selected_pool_without_execution(
    inputs, monkeypatch, selector, explicit, mode
):
    """Exercise the selected pool implementation, never a serializer stand-in."""
    import builtins
    import subprocess

    from doit.task import dict_to_task

    # Match build.py's selected-pool convention. An explicitly selected but
    # unavailable checkout is an error; only the absent optional sibling skips.
    selected_pool = os.environ.get("SOLIDWORKS_POOL_HOME")
    pool = Path(
        selected_pool if selected_pool is not None else REPO_ROOT.parent / "solidworks-pool"
    ).resolve()
    runner_path = pool / "agent" / "job_runner.py"
    if not runner_path.is_file():
        if selected_pool is not None:
            pytest.fail(f"selected pool serializer is unavailable: {runner_path}")
        pytest.skip("real serializer requires SOLIDWORKS_POOL_HOME or sibling solidworks-pool")

    dodo = inputs.module
    if selector is not None:
        monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", selector)
    if explicit is not None:
        monkeypatch.setenv(review_settings.SETTINGS_ENV, explicit.canonical())
    expected = explicit or review_settings.resolve_settings(
        reviewer=selector or "claude", judge_reviewer=selector or "claude",
    )
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    monkeypatch.setattr(dodo, "mode_for_drawing", lambda _script: mode)
    task = dict_to_task(next(dodo._machinist_review_tasks()))
    assert len(task.actions) == 1
    registered = task.actions[0]
    assert registered.py_callable is dodo._cached_machinist_review_action

    def forbidden(*_args, **_kwargs):
        pytest.fail("graph serialization attempted execution or host work")

    for name in (
        "_machinist_review_dir", "_machinist_review_stamp",
        "_machinist_review_cache_key", "_machinist_review_command",
        "_probe_cache", "_run_subprocess",
    ):
        monkeypatch.setattr(dodo, name, forbidden)
    for name in ("restore", "store"):
        monkeypatch.setattr(dodo._cache, name, forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", forbidden)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        assert name.split(".")[0] not in {
            "machinist_review", "win32com", "pythoncom", "pywintypes",
            "comtypes", "SolidworksMCP", "solidworks_mcp", "_solidworks", "winreg",
        }, f"graph serialization imported reviewer/native module {name}"
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    # Load all relative dependencies from this checkout in an isolated package,
    # without changing the selected pool, environment, or global import path.
    package_name = "_machinist_transport_selected_pool"
    assert not any(
        name == package_name or name.startswith(package_name + ".")
        for name in sys.modules
    )
    package = ModuleType(package_name)
    package.__path__ = [str(pool / "agent")]
    monkeypatch.setitem(sys.modules, package_name, package)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    module_name = package_name + ".job_runner"
    spec = importlib.util.spec_from_file_location(module_name, runner_path)
    runner = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, runner)
    try:
        spec.loader.exec_module(runner)
        serializer = runner._python_action_record
        assert Path(runner.__file__).resolve() == runner_path
        assert Path(serializer.__code__.co_filename).resolve() == runner_path
        assert Path(runner._normalized_action_value.__code__.co_filename).resolve() == runner_path
        record = serializer(inputs.root, task.name, 0, registered)
        assert record == {
            "kind": "python",
            "callable": "dodo._cached_machinist_review_action",
            "args": ["probe", mode.value, expected.canonical()],
            "kwargs": {},
        }
        exported = json.loads(json.dumps(record))
        assert type(exported["args"][2]) is str
        assert exported["args"][2] == expected.canonical()
        assert review_settings.from_carrier(exported["args"][2]) == expected

        # The same real serializer must reject the former typed action args.
        # Construct a doit action but do not execute or patch its executor.
        old_task = dict_to_task({
            "name": task.name,
            "actions": [(dodo._cached_machinist_review_action, ["probe", mode, expected])],
        })
        with pytest.raises(runner.JobRunnerError, match="unsupported type .*ReviewSettings"):
            serializer(inputs.root, old_task.name, 0, old_task.actions[0])
    finally:
        for name in tuple(sys.modules):
            if name.startswith(package_name + "."):
                sys.modules.pop(name, None)


@pytest.mark.parametrize(
    ("flags", "reviewer", "judge"),
    [
        ([], ("claude", "claude-opus-5-5", "medium"),
         ("claude", "claude-opus-5-5", "medium")),
        (["--reviewer", "codex"], ("codex", "gpt-6-astra", "low"),
         ("claude", "claude-opus-5-5", "medium")),
        (["--reviewer", "codex", "--model", "explicit-review", "--effort", "high",
          "--judge-reviewer", "claude", "--judge-model", "explicit-judge",
          "--judge-effort", "low"],
         ("codex", "explicit-review", "high"), ("claude", "explicit-judge", "low")),
    ],
)
def test_standalone_cli_ignores_registered_selector(
    inputs, review_sessions, monkeypatch, tmp_path, flags, reviewer, judge
):
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid-for-registered-gate")
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken-internal-carrier")
    assert review_sessions.module.main([
        "--pdf", str(inputs.pdf), "--name", "probe", "--kind", "part", "--force",
        "--report-dir", str(tmp_path / "standalone"), *flags,
    ]) == 0
    assert sorted(review_sessions.seen) == sorted([
        ("reviewer", *reviewer), ("reviewer", *reviewer), ("reviewer", *reviewer),
        ("judge", *judge),
    ])


@pytest.mark.parametrize("selector", ["", "Claude", "codex ", "other"])
def test_invalid_selector_fails_before_graph_inputs_cache_or_output_changes(
    action, monkeypatch, selector
):
    dodo = action.dodo
    stamp = dodo._machinist_review_stamp("probe")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("prior success")
    directory = dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    evidence = directory / "prior-evidence.json"
    evidence.write_text("prior evidence")
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", selector)

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid selector performed review work")

    monkeypatch.setattr(dodo, "_drawing_order", forbidden)
    monkeypatch.setattr(dodo, "_machinist_review_file_deps", forbidden)
    monkeypatch.setattr(dodo, "_probe_cache", forbidden)
    monkeypatch.setattr(dodo, "_run_subprocess", forbidden)
    monkeypatch.setattr(dodo._cache, "store", forbidden)
    with pytest.raises(ValueError, match="HARMONIC_MACHINIST_REVIEWER must be"):
        list(dodo._machinist_review_tasks())
    assert stamp.read_text() == "prior success"
    assert evidence.read_text() == "prior evidence"


@pytest.mark.parametrize(
    "settings",
    [
        None,
        1,
        {},
        review_settings.resolve_settings(),
        {"reviewer": "codex", "model": "gpt-6-astra", "effort": "low"},
        "",
        "{broken",
        "null",
        "[]",
        "1",
        '"settings"',
        "{}",
        *(
            json.dumps({
                field: getattr(review_settings.resolve_settings(), field)
                for field in review_settings.SETTING_FIELDS if field != missing
            })
            for missing in review_settings.SETTING_FIELDS
        ),
        json.dumps({
            **json.loads(review_settings.resolve_settings().canonical()),
            "extra": "unexpected",
        }),
        *(
            replace(review_settings.resolve_settings(), **{field: value}).canonical()
            for field in review_settings.SETTING_FIELDS
            for value in ("", "two tokens", None, 1, True, [], {})
        ),
        replace(review_settings.resolve_settings(), reviewer="invalid").canonical(),
        replace(review_settings.resolve_settings(), judge_reviewer="invalid").canonical(),
    ],
)
def test_direct_action_rejects_unresolved_or_invalid_settings_before_work(
    action, monkeypatch, settings
):
    dodo = action.dodo
    stamp = dodo._machinist_review_stamp("probe")
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text("prior success")
    directory = dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    evidence = directory / "prior-evidence.json"
    evidence.write_text("prior evidence")

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid action settings performed review work")

    monkeypatch.setattr(dodo, "_machinist_review_dir", forbidden)
    monkeypatch.setattr(dodo, "_machinist_review_stamp", forbidden)
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", forbidden)
    monkeypatch.setattr(dodo, "_probe_cache", forbidden)
    monkeypatch.setattr(dodo, "_run_subprocess", forbidden)
    monkeypatch.setattr(dodo._cache, "store", forbidden)
    message = (
        "registered machinist review requires a complete settings carrier"
        if not isinstance(settings, str)
        else "HARMONIC_MACHINIST_REVIEW_SETTINGS"
    )
    with pytest.raises(ValueError, match=message):
        dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.ENFORCE, settings
        )
    assert stamp.read_text() == "prior success"
    assert evidence.read_text() == "prior evidence"


@pytest.mark.parametrize(("changed", "value"), [
    ("reviewer", "codex"), ("model", "other-model"), ("effort", "high"),
    ("judge_reviewer", "codex"), ("judge_model", "other-judge-model"), ("judge_effort", "high"),
])
def test_effective_settings_invalidate_real_freshness_and_cached_action(
    action, review_sessions, monkeypatch, changed, value
):
    from doit.task import Stream, dict_to_task

    from test_artifact_cache import _BlockBlobService

    dodo = action.dodo
    cache = dodo._cache
    root = dodo.REPO_ROOT
    label = "check:machinist_review:probe"
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setattr(cache, "_CACHE_OUTPUT_ROOT", root / "cad" / "out")
    monkeypatch.setattr(cache, "_REPORTS", dodo.REPORTS)
    monkeypatch.setattr(cache, "_EVENTS_LOG", dodo.REPORTS / "cache.jsonl")
    monkeypatch.setattr(cache, "_KEYDIR", dodo.REPORTS / "cache-keys")
    monkeypatch.setattr(cache, "_BACKEND", cache._BlobBackend(_BlockBlobService()))
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", action.original_key)
    monkeypatch.setattr(dodo, "_probe_cache", action.original_probe)
    monkeypatch.setattr(cache, "store", action.original_store)
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    monkeypatch.setattr(
        dodo, "mode_for_drawing", lambda _script: MachinistReviewMode.ENFORCE
    )
    commands = []

    def run(command, *_args, **_kwargs):
        commands.append(command)
        return review_sessions.module.main(command[2:])

    monkeypatch.setattr(dodo, "_run_subprocess", run)

    def registered_task():
        return dict_to_task(next(dodo._machinist_review_tasks()))

    def freshness(task, values):
        check, args, kwargs = task.uptodate[0]
        return check(task, values, *args, **kwargs)

    def execute(previous):
        task = registered_task()
        # Task construction registers config_changed's saver; doit evaluates
        # freshness before execution and saves values only after success.
        assert not freshness(task, previous)
        assert task.execute(Stream(0)) is None
        task.save_extra_values()
        key = _review_key(dodo, label=label)
        return dict(task.values), key, dict(cache._KEY_INPUTS[(label, key)])

    saved, first_key, first_inputs = execute({})
    assert freshness(registered_task(), saved)
    assert len(commands) == 1 and len(review_sessions.seen) == 4
    selected = replace(action.settings, **{changed: value})
    with monkeypatch.context() as change:
        # Change one field only, so a provider mutation cannot be hidden by
        # the selected provider's different default model or effort.
        change.setenv(review_settings.SETTINGS_ENV, selected.canonical())
        assert not freshness(registered_task(), saved)
        second_saved, second_key, second_inputs = execute(saved)
        assert first_key != second_key
        assert len(commands) == 2 and len(review_sessions.seen) == 8
        aggregate = dodo._read_machinist_aggregate("probe", selected)
        observed = (
            aggregate["judge"][changed.removeprefix("judge_")]
            if changed.startswith("judge_") else aggregate[changed]
        )
        assert observed == value
        assert observed != getattr(action.settings, changed)

    reverted = registered_task()
    assert freshness(reverted, saved)
    assert not freshness(reverted, second_saved)
    _, restored_key, _ = execute(second_saved)
    assert restored_key == first_key
    assert len(commands) == 2 and len(review_sessions.seen) == 8
    aggregate = dodo._read_machinist_aggregate("probe", action.settings)
    assert (aggregate["reviewer"], aggregate["model"], aggregate["effort"]) == (
        "claude", "claude-opus-5-5", "medium",
    )
    config_tag = "cad/scripts/machinist_review_config.py"
    assert {path for path in first_inputs if first_inputs[path] != second_inputs[path]} == {
        config_tag,
    }
    assert all((root / path).is_file() for path in first_inputs)
    config_path = str(root / config_tag)
    effective = action.settings.canonical()
    source = dodo.ContentChecker._digest(config_path)
    assert first_inputs[config_tag] == dodo.hashlib.sha256(
        f"{source}\0{effective}".encode()
    ).hexdigest()
    assert cache.key_input_paths(label, first_key) == sorted(first_inputs)


@pytest.mark.parametrize("verdict", ["SHIP", "FIX", "ERROR"])
@pytest.mark.parametrize("mode", REVIEWED_MODES)
@pytest.mark.parametrize("hit", [False, True])
def test_cached_verdict_policy_and_error_publication(action, verdict, mode, hit):
    action.state.update(verdict=verdict, hit=hit, code=0 if verdict == "SHIP" else 1)
    if mode is MachinistReviewMode.ENFORCE and verdict != "SHIP":
        with pytest.raises(RuntimeError, match=f"{verdict}, gating_count=2"):
            action.dodo._cached_machinist_review_action("probe", mode, action.settings.canonical())
    else:
        action.dodo._cached_machinist_review_action("probe", mode, action.settings.canonical())
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
                "probe", MachinistReviewMode.LEARN, action.settings.canonical()
            )
    else:
        action.dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.LEARN, action.settings.canonical()
        )
        assert f"{verdict}, gating_count=" in action.calls["warnings"][0]
    assert action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()
    assert bool(action.calls["warnings"]) is not refresh


def test_failed_runner_cannot_reuse_a_previous_aggregate(action, monkeypatch):
    directory = action.dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    (directory / "probe.aggregate.json").write_text('{"verdict": "SHIP"}')
    monkeypatch.setattr(action.dodo, "_run_subprocess", lambda *_args, **_kwargs: 2)
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.LEARN, action.settings.canonical()
    )
    assert action.calls["store"] == 0
    assert "ERROR" in action.calls["warnings"][0]


def test_cache_hit_replaces_instead_of_mixing_previous_evidence(action):
    directory = action.dodo._machinist_review_dir("probe")
    directory.mkdir(parents=True)
    old_attempt = directory / "unrelated-old-attempt.json"
    old_attempt.write_text("{}")
    action.state["hit"] = True
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.LEARN, action.settings.canonical()
    )
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
            action.dodo._cached_machinist_review_action("probe", mode, action.settings.canonical())
    else:
        action.dodo._cached_machinist_review_action("probe", mode, action.settings.canonical())
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
        action.dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.LEARN, action.settings.canonical()
        )
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
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", action.original_key)
    key = _review_key(dodo)
    action.state["verdict"] = winner
    action.report()
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
            dodo._cached_machinist_review_action("probe", mode, action.settings.canonical())
    else:
        dodo._cached_machinist_review_action("probe", mode, action.settings.canonical())
    assert dodo._read_machinist_aggregate("probe", action.settings)["verdict"] == winner
    assert (directory / "winner-evidence.json").is_file()
    assert not (directory / "loser-only-attempt.json").exists()
    assert dodo._machinist_review_stamp("probe").exists() == (
        winner == "SHIP" or mode is MachinistReviewMode.LEARN
    )
    assert action.calls["run"] == 1
    assert cache.last_stored_key("check:machinist_review:probe") is None


@pytest.mark.parametrize("mode", REVIEWED_MODES, ids=["learn", "enforce"])
@pytest.mark.parametrize(
    ("carrier", "winner_matches_selected"),
    [
        ("stable", True),
        ("removed", True),
        ("changed", True),
        ("changed", False),
    ],
    ids=["stable-selected", "removed-selected", "changed-selected", "changed-wrong-winner"],
)
def test_losing_review_keeps_action_selection_when_carrier_changes(
    action, monkeypatch, mode, carrier, winner_matches_selected
):
    dodo = action.dodo
    selected = review_settings.resolve_settings(
        reviewer="codex", model="gpt-6-astra", effort="high",
        judge_reviewer="codex", judge_model="gpt-6-astra", judge_effort="high",
    )
    drifted = replace(selected, effort="low", judge_effort="low")
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    action.state.update(skipped=False, settings=selected)
    directory = dodo._machinist_review_dir("probe")
    label = "check:machinist_review:probe"
    monkeypatch.setattr(dodo, "_machinist_review_cache_key", action.original_key)
    key = _review_key(dodo, label=label, settings=selected)
    assert key != _review_key(dodo, label=label, settings=drifted)
    winner_files = {}
    phases = []

    def store(stored_key, outputs, stored_label):
        assert (stored_key, outputs, stored_label) == (key, [directory], label)
        assert not dodo._machinist_review_stamp("probe").exists()
        assert dodo._read_machinist_aggregate("probe", selected)["verdict"] == "SHIP"
        action.calls["store"] += 1
        if not winner_matches_selected:
            # Build a complete, valid winner for T, not malformed S evidence.
            monkeypatch.setenv(review_settings.SETTINGS_ENV, drifted.canonical())
            action.state["settings"] = drifted
            action.report()
            action.state["settings"] = selected
            assert dodo._read_machinist_aggregate("probe", drifted)["verdict"] == "SHIP"
        winner_files.update({
            path.relative_to(directory): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()
        })
        winner_files[Path("winner-evidence.json")] = b'{"producer":"winner"}'
        (directory / "loser-only-attempt.json").write_text("{}", encoding="utf-8")
        if carrier == "removed":
            monkeypatch.delenv(review_settings.SETTINGS_ENV)
        elif carrier == "changed":
            monkeypatch.setenv(review_settings.SETTINGS_ENV, drifted.canonical())
        phases.append("store")
        return "lost"

    def restore(restored_key, outputs, restored_label):
        assert (restored_key, outputs, restored_label) == (key, [directory], label)
        assert phases == ["store"]
        assert not directory.exists()  # canonical adoption removed all loser evidence
        for relative, content in winner_files.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        phases.append("restore")
        return True

    monkeypatch.setattr(dodo._cache, "store", store)
    monkeypatch.setattr(dodo._cache, "restore", restore)
    if winner_matches_selected:
        dodo._cached_machinist_review_action("probe", mode, selected.canonical())
        assert dodo._read_machinist_aggregate("probe", selected)["verdict"] == "SHIP"
    else:
        with pytest.raises(
            RuntimeError, match="could not adopt canonical reports.*provenance mismatch"
        ):
            dodo._cached_machinist_review_action("probe", mode, selected.canonical())
        assert dodo._read_machinist_aggregate("probe", drifted)["verdict"] == "SHIP"
    assert dodo._machinist_review_stamp("probe").exists() == winner_matches_selected
    assert phases == ["store", "restore"]
    assert action.calls["run"] == action.calls["store"] == 1
    assert not action.calls["warnings"]
    command = action.calls["commands"][0]
    start = command.index("--reviewer")
    assert command[start:start + 12] == selected.cli_args()
    assert (directory / "winner-evidence.json").read_bytes() == b'{"producer":"winner"}'
    assert not (directory / "loser-only-attempt.json").exists()



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
        dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.LEARN, action.settings.canonical()
        )
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
    key = _review_key(dodo, settings=default)
    selected = replace(default, **{field: value})
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    changed = next(dodo._machinist_review_tasks())
    assert not changed["uptodate"][0](None, saved)
    assert _review_key(dodo, settings=selected) != key
    assert changed["file_dep"] == first["file_dep"]
    assert dodo._machinist_review_file_deps("probe") == changed["file_dep"]
    assert changed["actions"][0][1][2] == selected.canonical()
    monkeypatch.setenv(review_settings.SETTINGS_ENV, default.canonical())
    assert _review_key(dodo, settings=default) == key


def test_selection_graph_and_contextual_keys_never_create_settings_files(inputs, monkeypatch):
    dodo = inputs.module
    monkeypatch.setattr(dodo, "_drawing_order", lambda: ["probe"])
    inputs.draw.write_text("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n")
    before = {
        path: path.read_bytes() if path.is_file() else None
        for path in inputs.root.rglob("*")
    }
    default = review_settings.resolve_settings()
    codex = review_settings.resolve_settings(reviewer="codex", judge_reviewer="codex")
    dependencies = dodo._machinist_review_file_deps("probe")
    keys = []
    for selected in (default, codex, default):
        monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
        task = next(dodo._machinist_review_tasks())
        assert task["file_dep"] == dependencies
        assert task["actions"][0][1][2] == selected.canonical()
        keys.append(_review_key(dodo, settings=selected))
    assert keys[0] == keys[2] != keys[1]
    assert {path: path.read_bytes() if path.is_file() else None for path in inputs.root.rglob("*")} == before
    assert not dodo.REPORTS.exists()


def test_all_off_graph_validates_current_carrier_after_dodo_preimport(dodo, monkeypatch, tmp_path):
    monkeypatch.setattr(dodo, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(dodo, "_drawing_order", lambda: [])
    monkeypatch.setattr(
        dodo, "_machinist_review_file_deps",
        lambda *_args: pytest.fail("all-OFF validation reached file dependencies"),
    )
    assert list(dodo._machinist_review_tasks()) == []
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken")
    with pytest.raises(ValueError, match=review_settings.SETTINGS_ENV):
        list(dodo._machinist_review_tasks())
    monkeypatch.setenv(
        review_settings.SETTINGS_ENV, review_settings.resolve_settings(reviewer="codex").canonical(),
    )
    assert list(dodo._machinist_review_tasks()) == []
    assert not dodo.REPORTS.exists()


@pytest.mark.parametrize("hit", [False, True])
def test_missing_explicitly_failed_attempt_does_not_reject_partial_ship(action, hit):
    action.state.update(hit=hit, run_errors=("r1",), missing_runs=("r1",))
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.ENFORCE, action.settings.canonical()
    )
    assert action.calls["store"] == int(not hit)
    assert action.dodo._machinist_review_stamp("probe").exists()


@pytest.mark.parametrize("hit", [False, True])
def test_partial_run_ship_keeps_matching_failed_run_provenance_cacheable(action, hit):
    action.state.update(hit=hit, run_errors=("r1",))
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.ENFORCE, action.settings.canonical()
    )
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
        action.dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.ENFORCE, action.settings.canonical()
        )
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
        action.dodo._cached_machinist_review_action(
            "probe", MachinistReviewMode.ENFORCE, action.settings.canonical()
        )
    assert action.calls["run"] == int(not hit)
    assert action.calls["store"] == 0
    assert not action.dodo._machinist_review_stamp("probe").exists()


def test_codex_action_emits_exact_selected_options_and_checks_executed_judge(action, monkeypatch):
    selected = review_settings.resolve_settings(
        reviewer="codex", model="gpt-6-astra", effort="high",
        judge_reviewer="codex", judge_model="gpt-6-astra", judge_effort="high",
    )
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    action.state.update(skipped=False, settings=selected)
    # Direct callers must supply the frozen selection, never re-read the carrier.
    monkeypatch.setenv("HARMONIC_MACHINIST_REVIEWER", "invalid-after-selection")
    monkeypatch.setenv(review_settings.SETTINGS_ENV, "{broken-after-selection")
    action.dodo._cached_machinist_review_action(
        "probe", MachinistReviewMode.ENFORCE, selected.canonical()
    )
    command = action.calls["commands"][0]
    assert command[command.index("--runs") + 1] == "3"
    start = command.index("--reviewer")
    assert command[start:start + 12] == selected.cli_args()
    assert all(command.count("--" + field.replace("_", "-")) == 1 for field in review_settings.SETTING_FIELDS)
    assert action.calls["store"] == 1


def test_review_status_and_action_dependencies_use_the_same_selected_key(inputs, monkeypatch):
    dodo = inputs.module
    selected = review_settings.resolve_settings(
        reviewer="codex", effort="high", judge_reviewer="codex", judge_effort="high",
    )
    monkeypatch.setenv(review_settings.SETTINGS_ENV, selected.canonical())
    label = "check:machinist_review:probe"
    dependencies = dodo._machinist_review_file_deps("probe")
    expected = _review_key(dodo, label=label, settings=selected)
    observed = []
    monkeypatch.setattr(dodo, "_cache_rows", lambda: [(label, dependencies)])
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
        "machinist_review_config.py" != Path(dependency).name
        and ".machinist-review-settings" not in Path(dependency).parts
        for dependencies in before.values() for dependency in dependencies
    )


def test_concurrent_frozen_selection_keys_are_pure_and_profile_independent(inputs):
    dodo = inputs.module
    default = review_settings.resolve_settings()
    codex = review_settings.resolve_settings(reviewer="codex", effort="high")
    selections = (default, review_settings.from_carrier(default.canonical()), codex, codex)
    before = set(inputs.root.rglob("*"))
    dependencies = dodo._machinist_review_file_deps("probe")
    barrier = threading.Barrier(4, timeout=10)

    def key(selected):
        barrier.wait()
        return _review_key(dodo, settings=selected), dodo._machinist_review_file_deps("probe")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(key, selections))
    keys = [result[0] for result in results]
    assert keys[0] == keys[1] != keys[2] == keys[3]
    assert all(result[1] == dependencies for result in results)
    assert set(inputs.root.rglob("*")) == before
    assert not dodo.REPORTS.exists()


@pytest.mark.parametrize(("field", "value"), [
    ("reviewer", "codex"), ("model", "alternate"), ("effort", "high"),
    ("judge_reviewer", "codex"), ("judge_model", "alternate"), ("judge_effort", "high"),
])
def test_contextual_selection_provenance_uses_only_existing_real_inputs(inputs, field, value):
    dodo = inputs.module
    default = review_settings.resolve_settings()
    selected = replace(default, **{field: value})
    label = "check:machinist_review:probe"
    before = set(inputs.root.rglob("*"))
    first = _review_key(dodo, label=label, settings=default)
    second = _review_key(dodo, label=label, settings=selected)
    first_inputs = dict(dodo._cache._KEY_INPUTS[(label, first)])
    second_inputs = dict(dodo._cache._KEY_INPUTS[(label, second)])
    config_tag = "cad/scripts/machinist_review_config.py"
    assert first != second
    assert set(first_inputs) == set(second_inputs)
    assert {path for path in first_inputs if first_inputs[path] != second_inputs[path]} == {config_tag}
    assert all((inputs.root / path).is_file() for path in first_inputs)
    assert dodo._cache.key_input_paths(label, first) == sorted(first_inputs)
    assert dodo._cache.key_input_paths(label, second) == sorted(second_inputs)
    source = dodo.ContentChecker._digest(str(inputs.root / config_tag))
    for settings, recorded in ((default, first_inputs), (selected, second_inputs)):
        assert recorded[config_tag] == dodo.hashlib.sha256(
            f"{source}\0{settings.canonical()}".encode()
        ).hexdigest()
    assert set(inputs.root.rglob("*")) == before
    assert not dodo.REPORTS.exists()

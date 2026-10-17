"""Cached machinist verdicts and AST enforcement, without models or SolidWorks."""

from __future__ import annotations

import ast
from contextlib import nullcontext
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from doit.loader import load_tasks

from _machinist_review_mode import MachinistReviewMode, mode_for_drawing

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
    return loaded_dodo


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("raise RuntimeError('must not import')\n", MachinistReviewMode.LEARN),
        (
            "MACHINIST_REVIEW = MachinistReviewMode.ENFORCE\n",
            MachinistReviewMode.ENFORCE,
        ),
        ("MACHINIST_REVIEW = MachinistReviewMode.LEARN\n", MachinistReviewMode.LEARN),
        ("def helper():\n    MACHINIST_REVIEW = 'local'\n", MachinistReviewMode.LEARN),
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
        if path.name in found:
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

    def tracker():
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
    calls = {"run": 0, "store": 0, "warnings": [], "probe": []}
    state = {"verdict": "SHIP", "error": None, "hit": False, "code": 0}
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
        (directory / "probe.aggregate.json").write_text(
            json.dumps(
                {
                    "name": "probe",
                    "kind": "part",
                    "verdict": state["verdict"],
                    "gating_count": 0 if state["verdict"] == "SHIP" else 2,
                    "error": state["error"],
                }
            ),
            encoding="utf-8",
        )

    def probe(_key, outputs, label, _span):
        calls["probe"].append(label)
        if state["hit"]:
            report()
            return "hit"
        return "miss"

    def run(*_args, **_kwargs):
        calls["run"] += 1
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
@pytest.mark.parametrize("mode", list(MachinistReviewMode))
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
    monkeypatch.setattr(dodo, "_probe_cache", action.original_probe)
    monkeypatch.setattr(dodo._cache, "store", action.original_store)
    monkeypatch.setattr(
        dodo._cache, "restore", lambda *_args: pytest.fail("forced review restored")
    )
    monkeypatch.setattr(
        dodo._cache, "note_refresh", lambda *args: refreshes.append(args)
    )

    def publish(_key, outputs, published_label):
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


@pytest.mark.parametrize("mode", list(MachinistReviewMode))
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


def test_every_registered_drawing_is_a_submitter_only_build_and_release_leaf(
    dodo,
    tmp_path,
    monkeypatch,
):
    import build

    leaves = {task["name"]: task for task in dodo._machinist_review_tasks()}
    expected = {f"machinist_review:{stem}" for stem in dodo.DRAWINGS_BY_NAME}
    assert set(leaves) == expected
    assert {f"check:{name}" for name in leaves} <= set(dodo.task_build()["task_dep"])
    assert {f"check:{name}" for name in leaves} <= set(dodo.task_release()["task_dep"])
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

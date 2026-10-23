"""Behavioral selected-loader coverage with real, serial doit and no native work."""

from __future__ import annotations

import copy
import functools
import hashlib
import json
import ntpath
import os
import posixpath
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from doit.cmd_base import TaskLoader2, tasks_and_deps_iter
from doit.control import TaskControl
from doit.doit_cmd import DoitMain
from doit.task import Task

import build
from cad.scripts import _selected_execution as selected

_COMMIT = "a" * 40
_ROOT = "assembly:root"
_CHILD = "part:child"
_CAPABILITY = "canonical-closure-v1"


class RecipeTracker:
    def __init__(self, case, name):
        self.case = case
        self.name = name

    def configure_task(self, task):
        task.value_savers.append(self.save)

    def __call__(self, task, values):
        self.case.events.append(("tracker", task.name))
        return values.get("recipe") == self.case.revision

    def save(self):
        self.case.events.append(("save", self.name))
        return {"recipe": self.case.revision}


class IdentityTracker:
    def __call__(self, task, values):
        del values
        native, token = task.targets
        try:
            return Path(token).read_text() == hashlib.sha256(Path(native).read_bytes()).hexdigest()
        except OSError:
            return False


def _identity(graph):
    payload = {key: value for key, value in graph.items() if key != "graph_identity_sha256"}
    return hashlib.sha256(json.dumps(
        payload, allow_nan=False, ensure_ascii=False,
        separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()


def _write_graph(case, graph):
    graph = copy.deepcopy(graph)
    graph["graph_identity_sha256"] = _identity(graph)
    case.graph_path.write_text(json.dumps(graph), encoding="utf-8")
    return graph["graph_identity_sha256"]


def _graph(case):
    control = TaskControl(case.make_tasks([_CHILD, _ROOT] + (["part"] if case.group else [])))
    control.process([_ROOT])
    records = []
    for task in tasks_and_deps_iter(control.tasks, control.selected_tasks):
        record = selected.task_record(case.workspace, task)
        record["actions"] = [
            {"kind": "python", "callable": name, "args": list(action.args), "kwargs": action.kwargs}
            for name, action in zip(record["actions"], task.actions)
        ]
        records.append(record)
    return {
        "schema_version": 3, "farm_protocol_version": 7, "commit": _COMMIT,
        "execution_loader": _CAPABILITY, "requested_targets": [_ROOT],
        "tasks": sorted(records, key=lambda record: record["name"]),
    }


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)
    monkeypatch.setattr(selected, "_source_commit", lambda workspace: _COMMIT)
    (tmp_path / "recipe.py").write_text("canonical recipe\n")
    case = SimpleNamespace(
        workspace=tmp_path, graph_path=tmp_path / "trusted-graph.json",
        events=[], made=[], requested=[], ownership_queries=[],
        revision="recipe-1", fail=False, group=False,
    )

    def hook(action):
        @functools.wraps(action)
        def wrapped(*args, **kwargs):
            case.events.append(("hook-before", _ROOT))
            result = action(*args, **kwargs)
            if result is not False:
                Path("root.ledger").write_text(case.revision)
                case.events.append(("hook-after", _ROOT))
            return result
        wrapped._remote_cache_action = True
        return wrapped

    def child_action():
        case.events.append(("action", _CHILD))
        Path("child.native").write_text("canonical child")
        Path("child.execution").write_text(hashlib.sha256(Path("child.native").read_bytes()).hexdigest())
        return {"child_result": "kept"}

    @hook
    def root_action(executable, dependencies, changed, targets):
        case.events.append(("action", _ROOT))
        case.injection = (executable, dependencies, changed, targets)
        assert Path("child.native").read_text() == "canonical child"
        assert Path("child.execution").read_text() == hashlib.sha256(Path("child.native").read_bytes()).hexdigest()
        if case.fail:
            return False
        Path("root.native").write_text(json.dumps({
            "recipe": Path("recipe.py").read_text(), "changed": sorted(changed),
        }, sort_keys=True))
        return {"root_result": "kept"}

    def stamp():
        case.events.append(("stamp", _ROOT))
        Path("root.execution").write_text(hashlib.sha256(Path("root.native").read_bytes()).hexdigest())

    def teardown():
        case.events.append(("teardown", _ROOT))

    def make_tasks(names):
        case.requested.append(list(names))
        tasks = []
        for name in names:
            if name == _CHILD:
                task = Task(
                    name, [child_action], file_dep=["recipe.py"],
                    targets=["child.native", "child.execution"],
                    uptodate=[RecipeTracker(case, name), IdentityTracker()], subtask_of="part",
                )
            elif name == _ROOT:
                task = Task(
                    name, [(root_action, [sys.executable]), stamp],
                    file_dep=["recipe.py", "child.native", "child.execution"],
                    task_dep=["part"] if case.group else [],
                    targets=["root.native", "root.execution"],
                    uptodate=[RecipeTracker(case, name), IdentityTracker()],
                    teardown=[teardown], subtask_of="assembly",
                )
            elif name == "part" and case.group:
                task = Task(name, None, task_dep=[_CHILD], has_subtask=True)
            else:
                raise ValueError(f"unexpected canonical task {name!r}")
            tasks.append(task)
        case.made = tasks
        return tasks

    def target_owners(paths=None):
        case.ownership_queries.append(None if paths is None else set(paths))
        return {
            selected._path_identity(selected._workspace_path(case.workspace, path)): name
            for path, name in {
                "child.native": _CHILD, "child.execution": _CHILD,
                "root.native": _ROOT, "root.execution": _ROOT,
            }.items()
        }

    case.make_tasks = make_tasks
    case.module = SimpleNamespace(
        REPO_ROOT=tmp_path,
        DOIT_CONFIG={"backend": "json", "dep_file": str(tmp_path / "deps.json")},
        canonical_tasks=make_tasks,
        canonical_target_owners=target_owners,
    )
    monkeypatch.setitem(sys.modules, "dodo", case.module)
    case.graph = _graph(case)
    case.identity = _write_graph(case, case.graph)
    case.events.clear()
    case.requested.clear()
    return case


def _loader(case, identity=None):
    return selected.SelectedTaskLoader(
        case.workspace, case.graph_path, _ROOT, identity or case.identity,
        capability=_CAPABILITY, isolate_tasks=build._isolated_tasks,
    )


def _run(case, *, force=False, refresh=False):
    task_loader = _loader(case)
    main_class = build._RefreshDoitMain if refresh else DoitMain
    main = main_class(task_loader=task_loader, config_filenames=())
    if refresh:
        main.refresh_labels = [_ROOT]
    argv = ["run"] + (["--always-execute"] if force else []) + ["-n", "0", _ROOT]
    return main.run(argv)


def _run_ordinary(case):
    """The same full synthetic factory through ordinary doit, without selection."""
    class OrdinaryLoader(TaskLoader2):
        def load_doit_config(self):
            return dict(case.module.DOIT_CONFIG)

        def load_tasks(self, cmd, pos_args):
            assert cmd.get_name() == "run" and pos_args == [_ROOT]
            return case.make_tasks([_ROOT, _CHILD] + (["part"] if case.group else []))

    return DoitMain(
        task_loader=OrdinaryLoader(), config_filenames=(),
    ).run(["run", "-n", "0", _ROOT])


def _observation(case):
    executable, dependencies, changed, targets = case.injection
    return {
        "injection": {
            "executable": executable, "dependencies": sorted(dependencies),
            "changed": sorted(changed), "targets": list(targets),
        },
        "outputs": {
            name: Path(name).read_bytes()
            for name in (
                "child.native", "child.execution",
                "root.native", "root.execution", "root.ledger",
            )
        },
        "task_values": {task.name: dict(task.values) for task in case.made},
        "events": list(case.events),
    }


def _mutate_real_input():
    recipe = Path("recipe.py")
    previous = recipe.stat()
    recipe.write_text(recipe.read_text() + "mutated real input\n")
    # Locked doit's MD5Checker first compares mtime. Advance it explicitly so
    # this real byte change is independent of filesystem timestamp granularity.
    os.utime(recipe, ns=(previous.st_atime_ns, previous.st_mtime_ns + 2_000_000_000))


def _ordinary_lifecycle(case, monkeypatch):
    """Independent cwd/DB, identical factory, recipe bytes and input timeline."""
    workspace = case.workspace / "ordinary-control"
    workspace.mkdir()
    (workspace / "recipe.py").write_bytes((case.workspace / "recipe.py").read_bytes())
    observations = {}
    with monkeypatch.context() as patch:
        patch.chdir(workspace)
        patch.setitem(case.module.DOIT_CONFIG, "dep_file", str(workspace / "deps.json"))
        for stage in ("initial", "unchanged", "mutated-real-input"):
            if stage == "mutated-real-input":
                _mutate_real_input()
            case.events.clear()
            assert _run_ordinary(case) == 0
            observations[stage] = _observation(case)
    case.events.clear()
    case.requested.clear()
    return observations


def test_real_tasks_keep_injection_trackers_savers_hooks_stamps_and_dependencies(
    case, capsys, monkeypatch,
):
    ordinary = _ordinary_lifecycle(case, monkeypatch)
    assert _run(case) == 0
    assert case.requested == [[_ROOT, _CHILD]]
    tasks = {task.name: task for task in case.made}
    assert all(type(task) is Task for task in tasks.values())
    assert tasks[_ROOT].task_dep == [_CHILD]
    assert tasks[_ROOT].subtask_of == "assembly"
    assert tasks[_CHILD].subtask_of == "part"
    executable, dependencies, changed, targets = case.injection
    assert executable == sys.executable
    assert set(dependencies) == {"recipe.py", "child.native", "child.execution"}
    # get_status evaluates uptodate trackers before file dependencies. An initial
    # false tracker can short-circuit changed; the ordinary loader is authority.
    assert set(changed) == set(ordinary["initial"]["injection"]["changed"])
    assert _observation(case) == ordinary["initial"]
    assert targets == ["root.native", "root.execution"]
    assert tasks[_ROOT].values == {"root_result": "kept", "recipe": case.revision}
    assert tasks[_CHILD].values == {"child_result": "kept", "recipe": case.revision}
    assert ("tracker", _ROOT) in case.events
    assert case.events.index(("action", _CHILD)) < case.events.index(("action", _ROOT))
    assert case.events.index(("hook-before", _ROOT)) < case.events.index(("action", _ROOT))
    assert case.events.index(("hook-after", _ROOT)) < case.events.index(("stamp", _ROOT))
    assert ("teardown", _ROOT) in case.events
    assert Path("root.ledger").read_text() == case.revision
    assert IdentityTracker()(tasks[_ROOT], {})
    assert len(tasks[_ROOT].value_savers) == 1
    markers = [json.loads(line.removeprefix("farm-execution "))
               for line in capsys.readouterr().out.splitlines() if line.startswith("farm-execution ")]
    assert {
        "dodo_import", "task_construction", "ownership_index", "control_validation",
        "first_action", "selected_action",
    } <= {
        marker["phase"] for marker in markers
    }
    phase_names = [marker["phase"] for marker in markers]
    assert phase_names.index("task_construction") < phase_names.index("ownership_index")
    assert phase_names.index("ownership_index") < phase_names.index("control_validation")
    first = next(marker for marker in markers if marker["phase"] == "first_action")
    assert first["task"] == _CHILD and first["selected_root"] is False
    root = next(marker for marker in markers if marker["phase"] == "selected_action")
    assert root["task"] == _ROOT and root["dependency_restore_in_head"] is True
    case.events.clear()
    assert _run(case) == 0
    assert ("action", _ROOT) not in case.events
    assert ("action", _CHILD) not in case.events
    assert ("tracker", _ROOT) in case.events
    assert _observation(case) == ordinary["unchanged"]
    _mutate_real_input()
    case.events.clear()
    assert _run(case) == 0
    mutated = _observation(case)
    assert mutated == ordinary["mutated-real-input"]
    assert mutated["injection"]["changed"] == ["recipe.py"]
    assert ("action", _CHILD) in case.events
    assert ("action", _ROOT) in case.events
    assert mutated["outputs"]["root.native"] != ordinary["initial"]["outputs"]["root.native"]
    assert mutated["outputs"]["root.execution"] != ordinary["initial"]["outputs"]["root.execution"]
    consumer = json.loads(mutated["outputs"]["root.native"])
    assert consumer == {
        "recipe": Path("recipe.py").read_text(), "changed": ["recipe.py"],
    }


def test_failure_never_saves_recipe_ledger_or_success_stamp(case):
    case.fail = True
    assert _run(case) == 1
    assert ("save", _CHILD) in case.events
    assert ("save", _ROOT) not in case.events
    assert ("stamp", _ROOT) not in case.events
    assert not Path("root.execution").exists()
    assert not Path("root.ledger").exists()
    case.fail = False
    case.events.clear()
    assert _run(case) == 0
    assert ("save", _ROOT) in case.events
    assert ("stamp", _ROOT) in case.events


def test_refresh_preserves_trackers_and_forces_only_admitted_root(case):
    assert _run(case) == 0
    case.events.clear()
    assert _run(case, refresh=True) == 0
    assert ("action", _CHILD) not in case.events
    assert ("tracker", _ROOT) in case.events
    assert ("action", _ROOT) in case.events
    assert ("save", _ROOT) in case.events
    task = next(task for task in case.made if task.name == _ROOT)
    assert len(task.value_savers) == 1
    assert any(entry[0] is False for entry in task.uptodate)


def test_forced_attempt_still_executes_canonical_dependency_traversal(case):
    assert _run(case) == 0
    case.events.clear()
    assert _run(case, force=True) == 0
    assert ("action", _CHILD) in case.events
    assert ("action", _ROOT) in case.events


def test_group_tasks_remain_genuine_and_preserve_full_child_dependencies(case):
    case.group = True
    case.graph = _graph(case)
    case.identity = _write_graph(case, case.graph)
    case.events.clear()
    case.requested.clear()
    assert _run(case) == 0
    assert case.requested == [[_ROOT, "part", _CHILD]]
    group = next(task for task in case.made if task.name == "part")
    assert group.has_subtask is True
    assert group.task_dep == [_CHILD]
    assert group.actions == []


@pytest.mark.parametrize("field", ["dependencies", "file_dependencies", "targets", "actions"])
def test_canonical_mismatch_fails_before_any_action(case, field, capsys):
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    if field == "dependencies":
        # Keep the child reachable through an exported root, but forge the edge.
        root[field] = []
        case.graph["requested_targets"].append(_CHILD)
    elif field == "file_dependencies":
        root[field].append("unexpected.py")
        root[field].sort()
    elif field == "targets":
        root[field] = ["forged.native"]
    else:
        root[field][0]["callable"] = "forged.module.action"
    case.identity = _write_graph(case, case.graph)
    assert _run(case) == 3
    assert not case.events
    assert not Path("root.native").exists()
    assert "canonical" in capsys.readouterr().err or field == "dependencies"


def test_omitted_implicit_producer_is_rejected_even_with_existing_outputs(case, capsys):
    Path("child.native").write_text("old untrusted output")
    Path("child.execution").write_text("b" * 64)
    case.graph["tasks"] = [record for record in case.graph["tasks"] if record["name"] != _CHILD]
    case.graph["tasks"][0]["dependencies"] = []
    case.identity = _write_graph(case, case.graph)
    assert _run(case) == 3
    assert not case.events
    assert "omits implicit producer" in capsys.readouterr().err


def test_graph_action_arguments_are_not_deserialized_or_executed(case):
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    root["actions"][0]["args"] = [{"environment_path": "Scripts/python.exe"}]
    root["actions"][0]["kwargs"] = {"targets": ["attacker.target"]}
    case.identity = _write_graph(case, case.graph)
    assert _run(case) == 0
    assert case.injection[0] == sys.executable
    assert case.injection[3] == ["root.native", "root.execution"]
    assert not Path("attacker.target").exists()


@pytest.mark.parametrize("field,value", [
    ("schema_version", 2), ("schema_version", 4), ("schema_version", True),
    ("farm_protocol_version", 6), ("farm_protocol_version", 8), ("farm_protocol_version", True),
    ("commit", "b" * 40), ("commit", "a" * 12),
    ("execution_loader", "canonical-full-v1"), ("execution_loader", None),
])
def test_graph_identity_contract_fails_before_factory_import(case, field, value, monkeypatch):
    case.graph[field] = value
    case.identity = _write_graph(case, case.graph)
    def forbidden_import(name):
        pytest.fail(f"must not import {name} before graph validation")
    monkeypatch.setattr(selected.importlib, "import_module", forbidden_import)
    with pytest.raises(selected.SelectedExecutionError):
        _loader(case)
    assert case.requested == []
    assert not case.events


def test_separate_identity_rejects_replaced_self_consistent_graph(case):
    trusted_identity = case.identity
    case.graph["tasks"][0]["actions"][0]["args"] = ["replacement"]
    _write_graph(case, case.graph)
    with pytest.raises(selected.SelectedExecutionError, match="trusted identity"):
        _loader(case, trusted_identity)
    assert not case.events


def test_duplicate_graph_records_fail_before_construction(case):
    case.graph["tasks"].append(copy.deepcopy(case.graph["tasks"][0]))
    case.identity = _write_graph(case, case.graph)
    with pytest.raises(selected.SelectedExecutionError, match="unique"):
        _loader(case)
    assert not case.requested


def test_duplicate_json_keys_are_rejected(case):
    case.graph_path.write_text('{"tasks":[],"tasks":[]}')
    with pytest.raises(selected.SelectedExecutionError, match="duplicate JSON key"):
        _loader(case)


@pytest.mark.parametrize("mutation", ["dangling", "cycle", "orphan", "duplicate-dependency", "absolute-path"])
def test_malformed_closures_fail_before_actions(case, mutation):
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    child = next(record for record in case.graph["tasks"] if record["name"] == _CHILD)
    if mutation == "dangling":
        root["dependencies"] = ["part:missing"]
    elif mutation == "cycle":
        child["dependencies"] = [_ROOT]
    elif mutation == "orphan":
        root["dependencies"] = []
    elif mutation == "duplicate-dependency":
        root["dependencies"] = [_CHILD, _CHILD]
    else:
        root["file_dependencies"] = [str(case.workspace / "recipe.py")]
    case.identity = _write_graph(case, case.graph)
    with pytest.raises(selected.SelectedExecutionError):
        _loader(case)
    assert not case.events


def test_duplicate_or_incomplete_factory_results_are_rejected(case):
    make_tasks = case.make_tasks
    def duplicate(names):
        tasks = make_tasks(names)
        return tasks + [tasks[0]]
    case.module.canonical_tasks = duplicate
    assert _run(case) == 3
    assert not case.events


def test_incomplete_target_ownership_index_is_rejected(case):
    case.module.canonical_target_owners = lambda paths=None: {}
    assert _run(case) == 3
    assert not case.events


@pytest.mark.parametrize("argv", [
    ["run", "--single", "-n", "0", _ROOT],
    ["run", "-n", "1", _ROOT], ["run", "-n", "0", _CHILD],
    ["list"], ["run", "-n", "0", _ROOT, _CHILD],
    ["-f", "other.py", "run", "-n", "0", _ROOT],
])
def test_internal_invocation_rejects_dependency_bypasses_and_other_selection(argv):
    with pytest.raises(selected.SelectedExecutionError):
        selected.validate_invocation(argv, _ROOT)


@pytest.mark.parametrize("force", [False, True])
def test_build_cli_uses_selected_loader_without_full_fallback(case, monkeypatch, force, capsys):
    monkeypatch.setattr(build, "REPO_ROOT", case.workspace)
    def forbidden_full_loader(*args, **kwargs):
        pytest.fail("ordinary full task loader must never be called")
    monkeypatch.setattr(selected.loader, "load_tasks", forbidden_full_loader)
    argv = [
        "--farm-execution-graph", str(case.graph_path),
        "--farm-execution-task", _ROOT,
        "--farm-execution-identity", case.identity,
        "run", *(["--always-execute"] if force else []), "-n", "0", _ROOT,
    ]
    assert build.main(argv) == 0
    assert ("action", _ROOT) in case.events
    assert '"phase":"build_import"' in capsys.readouterr().out


def test_partial_internal_cli_and_farm_executor_fail_without_running_doit(case, monkeypatch):
    def forbidden_doit(*args, **kwargs):
        pytest.fail("invalid selected mode must not instantiate DoitMain")
    monkeypatch.setattr(build, "DoitMain", forbidden_doit)
    assert build.main(["--farm-execution-task", _ROOT, "run", "-n", "0", _ROOT]) == 2
    assert build.main([
        "--executor", "farm", "--farm-execution-graph", str(case.graph_path),
        "--farm-execution-task", _ROOT, "--farm-execution-identity", case.identity,
        "run", "-n", "0", _ROOT,
    ]) == 2


def test_declared_capability_validation_failure_never_falls_back(case, monkeypatch):
    monkeypatch.setattr(build, "REPO_ROOT", case.workspace)
    def forbidden_doit(*args, **kwargs):
        pytest.fail("invalid selected graph must not instantiate any ordinary loader")
    monkeypatch.setattr(build, "DoitMain", forbidden_doit)
    assert build.main([
        "--farm-execution-graph", str(case.graph_path), "--farm-execution-task", _ROOT,
        "--farm-execution-identity", "0" * 64, "run", "-n", "0", _ROOT,
    ]) == 2
    assert not case.events


def test_task_record_normalizes_workspace_paths_without_serializing_environment_args(case):
    task = Task("check:paths", [], file_dep=[str(case.workspace / "recipe.py")],
                targets=[str(case.workspace / "result.stamp")])
    record = selected.task_record(case.workspace, task)
    assert record["file_dependencies"] == ["recipe.py"]
    assert record["targets"] == ["result.stamp"]
    assert record["actions"] == []
    task.file_dep.add(str(case.workspace.parent / "outside.py"))
    with pytest.raises(selected.SelectedExecutionError, match="escapes"):
        selected.task_record(case.workspace, task)


@pytest.mark.parametrize("mode", ["missing-root", "actionless-root", "relative-graph"])
def test_selected_graph_requires_present_action_bearing_root_and_absolute_path(case, mode):
    if mode == "relative-graph":
        with pytest.raises(selected.SelectedExecutionError, match="absolute"):
            selected.SelectedTaskLoader(
                case.workspace, Path("trusted-graph.json"), _ROOT, case.identity,
                capability=_CAPABILITY, isolate_tasks=build._isolated_tasks,
            )
    else:
        if mode == "missing-root":
            case.graph["tasks"] = [
                record for record in case.graph["tasks"] if record["name"] != _ROOT
            ]
        else:
            root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
            root["actions"] = []
        case.identity = _write_graph(case, case.graph)
        with pytest.raises(selected.SelectedExecutionError):
            _loader(case)
    assert not case.requested
    assert not case.events


def test_factory_must_return_every_named_dependency(case):
    make_tasks = case.make_tasks

    def missing_dependency(names):
        return make_tasks(name for name in names if name != _CHILD)

    case.module.canonical_tasks = missing_dependency
    assert _run(case) == 3
    assert not case.events


def test_unselected_graph_paths_are_checked_lexically_not_resolved(case, monkeypatch):
    case.graph["tasks"].append({
        "name": "check:unselected", "dependencies": [],
        "file_dependencies": ["unselected/source.py"], "targets": ["unselected/result.stamp"],
        "actions": [{
            "kind": "python", "callable": "unselected.module.action",
            "args": [], "kwargs": {},
        }],
    })
    case.graph["tasks"].sort(key=lambda record: record["name"])
    case.graph["requested_targets"].append("check:unselected")
    case.identity = _write_graph(case, case.graph)
    workspace_path = selected._workspace_path

    def only_selected_paths(workspace, value):
        assert not value.startswith("unselected/"), "must not resolve unrelated graph paths"
        return workspace_path(workspace, value)

    monkeypatch.setattr(selected, "_workspace_path", only_selected_paths)
    assert _run(case) == 0
    assert case.requested == [[_ROOT, _CHILD]]


def test_current_export_contract_is_exactly_schema3_protocol7_and_v1_records(case):
    assert build.SELECTIVE_EXECUTION_CAPABILITY == _CAPABILITY == "canonical-closure-v1"
    assert selected._SCHEMA_VERSION == case.graph["schema_version"] == 3
    assert selected._FARM_PROTOCOL_VERSION == case.graph["farm_protocol_version"] == 7
    assert selected._RECORD_KEYS == {
        "name", "dependencies", "file_dependencies", "targets", "actions",
    }
    for record in case.graph["tasks"]:
        assert set(record) == selected._RECORD_KEYS
        for action in record["actions"]:
            assert set(action) == {"kind", "callable", "args", "kwargs"}
            assert action["kind"] == "python"
    assert _run(case) == 0


@pytest.mark.parametrize("level", ["task", "action"])
def test_future_record_shape_requires_explicit_migration_before_factory_import(
    case, monkeypatch, level,
):
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    destination = root if level == "task" else root["actions"][0]
    destination["future_contract_field"] = "must-not-be-silently-accepted"
    case.identity = _write_graph(case, case.graph)

    def forbidden_import(name):
        pytest.fail(f"future record shape must not import {name}")

    monkeypatch.setattr(selected.importlib, "import_module", forbidden_import)
    with pytest.raises(selected.SelectedExecutionError):
        _loader(case)
    assert not case.requested
    assert not case.events


def test_ownership_queries_include_all_live_targets_and_file_dependencies(case):
    assert _run(case) == 0
    assert case.ownership_queries == [{
        "recipe.py", "child.native", "child.execution", "root.native", "root.execution",
    }]


@pytest.mark.parametrize("error_type", [ValueError, OSError])
def test_ownership_index_errors_refuse_before_actions_with_separate_timing(
    case, capsys, error_type,
):
    def invalid_index(paths=None):
        raise error_type("invalid canonical target metadata")

    case.module.canonical_target_owners = invalid_index
    assert _run(case) == 3
    assert not case.events
    captured = capsys.readouterr()
    assert "cannot construct canonical target ownership index" in captured.err
    markers = [
        json.loads(line.removeprefix("farm-execution "))
        for line in captured.out.splitlines() if line.startswith("farm-execution ")
    ]
    ownership = next(marker for marker in markers if marker["phase"] == "ownership_index")
    assert ownership["status"] == "error"
    assert not any(marker["phase"] == "control_validation" for marker in markers)


@pytest.mark.parametrize("export_warm", [False, True])
@pytest.mark.parametrize("execute_warm", [False, True])
def test_windows_path_comparison_preserves_records_across_filesystem_states(
    case, monkeypatch, export_warm, execute_warm,
):
    monkeypatch.setattr(selected.os.path, "normcase", ntpath.normcase)
    native_paths = [Path("root.native"), Path("child.native")]

    def set_outputs(warm):
        for path in native_paths:
            if warm:
                path.write_text("preexisting output with on-disk spelling")
            else:
                path.unlink(missing_ok=True)

    resolve = Path.resolve

    def on_disk_case(path, *args, **kwargs):
        resolved = resolve(path, *args, **kwargs)
        if path.name in {"root.native", "child.native"} and path.exists():
            return resolved.with_name(path.name.upper())
        return resolved

    monkeypatch.setattr(Path, "resolve", on_disk_case)
    set_outputs(export_warm)
    case.graph = _graph(case)
    case.identity = _write_graph(case, case.graph)
    graph_bytes = case.graph_path.read_bytes()
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    assert ("ROOT.NATIVE" if export_warm else "root.native") in root["targets"]
    assert ("CHILD.NATIVE" if export_warm else "child.native") in root["file_dependencies"]

    set_outputs(execute_warm)
    task_loader = _loader(case)
    records = copy.deepcopy(task_loader.records)
    case.events.clear()
    main = DoitMain(task_loader=task_loader, config_filenames=())
    assert main.run(["run", "-n", "0", _ROOT]) == 0
    assert ("action", _ROOT) in case.events
    assert task_loader.records == records
    assert case.graph_path.read_bytes() == graph_bytes


@pytest.mark.parametrize("field", ["file_dependencies", "targets"])
@pytest.mark.parametrize("normcase", [ntpath.normcase, posixpath.normcase], ids=["windows", "posix"])
def test_only_os_equivalent_record_paths_compare_equal(case, monkeypatch, field, normcase):
    monkeypatch.setattr(selected.os.path, "normcase", normcase)
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    root[field] = sorted(path.upper() for path in root[field])
    case.identity = _write_graph(case, case.graph)
    case.events.clear()

    equivalent = normcase("Part.x") == normcase("part.x")
    assert _run(case) == (0 if equivalent else 3)
    if not equivalent:
        assert not case.events


def test_windows_case_alias_cannot_hide_an_omitted_implicit_producer(case, monkeypatch, capsys):
    monkeypatch.setattr(selected.os.path, "normcase", ntpath.normcase)
    make_tasks = case.make_tasks

    def aliased_consumer(names):
        tasks = make_tasks(names)
        for task in tasks:
            if task.name == _ROOT:
                task.file_dep = {"recipe.py", "CHILD.NATIVE"}
        return tasks

    case.module.canonical_tasks = aliased_consumer
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    root["dependencies"] = []
    root["file_dependencies"] = ["CHILD.NATIVE", "recipe.py"]
    case.graph["tasks"] = [root]
    case.identity = _write_graph(case, case.graph)
    case.events.clear()

    assert _run(case) == 3
    assert not case.events
    assert "omits implicit producer" in capsys.readouterr().err


def test_windows_path_identity_does_not_fold_callable_names(case, monkeypatch):
    monkeypatch.setattr(selected.os.path, "normcase", ntpath.normcase)
    root = next(record for record in case.graph["tasks"] if record["name"] == _ROOT)
    root["actions"][0]["callable"] = root["actions"][0]["callable"].upper()
    case.identity = _write_graph(case, case.graph)

    assert _run(case) == 3
    assert not case.events


def test_path_resolution_errors_use_selected_refusal_before_actions(case, monkeypatch, capsys):
    resolve = Path.resolve

    def unreadable_path(path, *args, **kwargs):
        if path.name == "child.native":
            raise OSError("cannot resolve target path")
        return resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", unreadable_path)
    assert _run(case) == 3
    assert not case.events
    assert "cannot normalize task path" in capsys.readouterr().err


def test_outside_ownership_target_uses_same_escape_refusal_before_actions(case, capsys):
    def outside_index(paths=None):
        return {selected._workspace_path(case.workspace, "../outside.target"): _ROOT}

    case.module.canonical_target_owners = outside_index
    assert _run(case) == 3
    assert not case.events
    assert "escapes selected workspace" in capsys.readouterr().err


def test_foreign_cwd_roots_relative_factory_inputs_and_actions_in_workspace(case, monkeypatch):
    foreign = case.workspace.parent / f"{case.workspace.name}-foreign"
    foreign.mkdir()
    make_tasks = case.module.canonical_tasks
    factory_inputs = []

    def relative_factory(names):
        factory_inputs.append(Path("recipe.py").read_text())
        return make_tasks(names)

    case.module.canonical_tasks = relative_factory
    monkeypatch.chdir(foreign)

    assert _run(case) == 0
    assert Path.cwd() == case.workspace
    assert factory_inputs == ["canonical recipe\n"]
    assert json.loads((case.workspace / "root.native").read_text())["recipe"] == "canonical recipe\n"
    assert (case.workspace / "deps.json").exists()
    assert not (foreign / "root.native").exists()
    assert not (foreign / "deps.json").exists()


@pytest.mark.parametrize("mode", [
    "missing", "none", "relative", "bytes", "nul", "other-workspace", "workspace-child",
])
def test_provider_root_must_be_loader_workspace_before_tasks_or_ownership(
    case, capsys, mode, monkeypatch,
):
    other = case.workspace / "other-checkout"
    other.mkdir()
    roots = {
        "none": None, "relative": ".", "bytes": bytes(case.workspace),
        "nul": str(case.workspace) + "\0", "other-workspace": other,
        "workspace-child": case.workspace / "cad",
    }
    if mode == "missing":
        del case.module.REPO_ROOT
    else:
        case.module.REPO_ROOT = roots[mode]
    foreign = case.workspace.parent / f"{case.workspace.name}-foreign"
    foreign.mkdir()
    monkeypatch.chdir(foreign)

    assert _run(case) == 3
    assert Path.cwd() == foreign
    # Refused at dodo configuration: no factory, ownership query, dep DB or action.
    assert case.requested == []
    assert case.ownership_queries == []
    assert not case.events
    assert not (case.workspace / "deps.json").exists()
    assert "REPO_ROOT" in capsys.readouterr().err


@pytest.mark.parametrize("spelling", ["path", "string", "dotted"])
def test_equivalent_provider_root_spellings_share_one_authority(case, spelling):
    (case.workspace / "nested").mkdir()
    case.module.REPO_ROOT = {
        "path": case.workspace,
        "string": str(case.workspace),
        "dotted": str(case.workspace / "nested" / ".."),
    }[spelling]
    assert _run(case) == 0
    assert ("action", _ROOT) in case.events


def test_matching_provider_root_keeps_workspace_escape_refusal(case, capsys):
    # A shared root does not relax normalization: escaping targets still refuse.
    case.module.REPO_ROOT = str(case.workspace)
    make_tasks = case.make_tasks

    def escaping(names):
        tasks = make_tasks(names)
        tasks[-1].targets.append(str(case.workspace.parent / "outside.target"))
        return tasks

    case.module.canonical_tasks = escaping
    assert _run(case) == 3
    assert not case.events
    assert "escapes selected workspace" in capsys.readouterr().err

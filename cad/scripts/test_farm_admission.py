"""Selected-pool leaf admission, with real doit parsing but no farm or COM.

The pool fixture deliberately admits exact task names, not production prefixes.
Only its stdlib protocol runs in a child Python; uv, the fleet and ownership are
intercepted before they can contact a service or write a production request.
"""

import ast
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import doit.cmd_base as _doit_cmd_base
from doit.cmd_base import ModuleTaskLoader
from doit.control import TaskControl
from doit.dependency import CHECKERS, Dependency, JsonDB
from doit.task import Task

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import build  # noqa: E402

_REAL_RUN = subprocess.run
_REAL_FARM_DOIT = build._FarmDoitMain
_LABEL = "Offline selected-pool admission regression"


@pytest.fixture
def admission(tmp_path, monkeypatch):
    events = []
    calls = []
    monkeypatch.setenv("HARMONIC_FARM_DISPLAY_NAME", _LABEL)
    monkeypatch.setenv("HARMONIC_FARM_REQUESTS", str(tmp_path / "requests"))
    for key in (
        "HARMONIC_EXECUTOR",
        "HARMONIC_FARM_COMMIT",
        "HARMONIC_FARM_BUILD_ID",
        "HARMONIC_FARM_PARALLELISM",
        "HARMONIC_FARM_LEAF_TIMEOUT_S",
        "HARMONIC_VERBOSITY",
    ):
        # Track originally absent keys too: build.main writes executor state
        # directly, so a plain delenv on an absent key would not restore it.
        monkeypatch.setenv(key, "fixture-clear")
        monkeypatch.delenv(key, raising=False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("admission contacted the fleet or dispatched a farm leaf")

    monkeypatch.setattr(build, "_pool_farm", forbidden)
    monkeypatch.setattr(_farm, "run_leaf", forbidden)
    monkeypatch.setattr(build, "_farm_preflight", lambda: events.append("preflight"))
    monkeypatch.setattr(_farm, "_build_id", lambda: events.append("mint") or "fixture-id")

    class Ownership:
        def __enter__(self):
            events.append("ownership")
            _farm._build_id()
            events.append("register")
            return self

        def finish(self, success):
            events.append(("finish", success))

        def __exit__(self, *_exc):
            events.append("close")
            return False

    def producer(label):
        assert label == _LABEL
        events.append("producer")
        return Ownership()

    monkeypatch.setattr(_farm, "producer_build", producer)

    class MemoryJsonDB(JsonDB):
        def __init__(self, name, codec, *, module_name=None):
            self.name = name
            self.codec = codec
            self._db = {}

        def dump(self):
            pass

    monkeypatch.setattr(_doit_cmd_base, "JsonDB", MemoryJsonDB)

    def pool(name="selected-pool", accepted=(), protocol=None):
        home = tmp_path / name
        package = home / "agent"
        package.mkdir(parents=True)
        (home / "rule.json").write_text(json.dumps(list(accepted)), encoding="utf-8")
        if protocol is None:
            protocol = (
                "import json\n"
                "from pathlib import Path\n"
                "HOME = Path(__file__).resolve().parents[1]\n"
                "def leaf_admitted(task):\n"
                "    with (HOME / 'queried.jsonl').open('a', encoding='utf-8') as log:\n"
                "        log.write(json.dumps(task) + '\\n')\n"
                "    return task in json.loads((HOME / 'rule.json').read_text(encoding='utf-8'))\n"
            )
        (package / "protocol.py").write_text(protocol, encoding="utf-8")
        monkeypatch.setenv("SOLIDWORKS_POOL_HOME", str(home))
        return home

    def intercept(argv, **kwargs):
        argv = list(argv)
        home = Path(os.environ["SOLIDWORKS_POOL_HOME"])
        assert argv[:7] == [
            "uv", "run", "--frozen", "--project", str(home), "python", "-c"
        ], "only the selected-pool admission program may start a subprocess"
        assert len(argv) == 9
        assert argv[8] == str(home)
        assert kwargs["cwd"] == REPO_ROOT
        assert kwargs["text"] is True
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.PIPE
        candidates = json.loads(kwargs["input"])
        assert isinstance(candidates, list)
        assert all(isinstance(task, str) for task in candidates)
        assert len(candidates) == len(set(candidates))
        calls.append((argv, candidates))
        # Execute the actual production -c program, not a duplicated protocol
        # query. The fixture protocol needs no pool dependencies or installation.
        child_kwargs = dict(kwargs)
        child_kwargs["timeout"] = 10
        return _REAL_RUN([sys.executable, *argv[6:]], **child_kwargs)

    monkeypatch.setattr(build.subprocess, "run", intercept)

    def action(name, marked=True):
        def record(*_args, **_kwargs):
            events.append(("action", name))
            return True

        return _farm.leaf_action(record) if marked else record

    def install(specs, defaults=("build",)):
        namespace = {"DOIT_CONFIG": {"default_tasks": list(defaults)}}
        groups = {}
        for name, definition in specs.items():
            prefix, separator, suffix = name.partition(":")
            if separator:
                groups.setdefault(prefix, []).append({"name": suffix, **definition})
            else:
                def task(definition=definition):
                    return definition.copy()

                namespace["task_" + prefix] = task
        for prefix, definitions in groups.items():
            def task(definitions=definitions):
                yield from (definition.copy() for definition in definitions)

            namespace["task_" + prefix] = task

        class FixtureFarmDoit(_REAL_FARM_DOIT):
            def __init__(self):
                super().__init__(
                    task_loader=ModuleTaskLoader(namespace),
                    extra_config={"GLOBAL": {"backend": "json", "dep_file": ":memory:"}},
                )

            def run(self, args):
                # Explicit serial execution keeps the fake action observations
                # in this process and avoids workers, subprocesses and a DB.
                return super().run(args)

        monkeypatch.setattr(build, "_FarmDoitMain", FixtureFarmDoit)

    def run(*selectors):
        return build.main(["--executor", "farm", "-n", "0", *selectors])

    def queried(home):
        log = home / "queried.jsonl"
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]

    return SimpleNamespace(
        events=events, calls=calls, pool=pool, action=action,
        install=install, run=run, queried=queried, tmp_path=tmp_path,
    )


def _assert_no_ownership_or_actions(admission):
    assert admission.events == [], "refused admission ran preflight, ownership or an action"
    assert not (admission.tmp_path / "requests").exists()
    assert os.environ.get("HARMONIC_FARM_BUILD_ID") is None
    assert os.environ.get("HARMONIC_FARM_COMMIT") is None


@pytest.mark.parametrize("selector", ["features:probe", "novel:probe", "part:probe"])
def test_direct_marked_task_obeys_pool_rule_not_a_ha_prefix_list(
    admission, capsys, selector
):
    home = admission.pool(accepted=["irrelevant:fixture-ok"])
    admission.install({selector: {"actions": [admission.action(selector)]}})

    assert admission.run(selector) == 2
    error = capsys.readouterr().err
    assert error.startswith("farm:")
    assert selector in error
    assert f"prefix: {selector.partition(':')[0]}" in error
    assert str(home) in error
    assert admission.queried(home) == [selector]
    _assert_no_ownership_or_actions(admission)


@pytest.mark.parametrize("edge", ["task_dep", "file_dep", "setup"])
def test_unadmitted_dependency_is_checked_before_any_local_or_farm_action(
    admission, capsys, edge
):
    home = admission.pool()
    target = admission.tmp_path / "would-be-produced.bin"
    leaf = {"actions": [admission.action("features:probe")], "targets": [str(target)]}
    root = {"actions": [admission.action("local", marked=False)]}
    if edge == "file_dep":
        root[edge] = [str(target)]
    else:
        root[edge] = ["features:probe"]
    admission.install({"features:probe": leaf, "local": root})

    assert admission.run("local") == 2
    assert "features:probe" in capsys.readouterr().err
    assert admission.queried(home) == ["features:probe"]
    assert not target.exists()
    _assert_no_ownership_or_actions(admission)


def test_requested_closure_reports_every_refused_prefix_and_skips_unselected_leaf(
    admission, capsys, request
):
    home = admission.pool(accepted=["unusual:fixture-ok"])
    target = admission.tmp_path / "inferred.bin"
    admission.install({
        "features:probe": {
            "actions": [admission.action("features:probe")], "targets": [str(target)],
        },
        "novel:probe": {"actions": [admission.action("novel:probe")]},
        "unusual:fixture-ok": {"actions": [admission.action("unusual:fixture-ok")]},
        "unselected:probe": {"actions": [admission.action("unselected:probe")]},
        "local": {
            "actions": [admission.action("local", marked=False)],
            "file_dep": [str(target)], "setup": ["novel:probe"],
        },
        "build": {"actions": [], "task_dep": ["local", "unusual:fixture-ok"]},
    })

    assert admission.run("build") == 2
    error = capsys.readouterr().err
    assert "features:probe (prefix: features)" in error
    assert "novel:probe (prefix: novel)" in error
    assert "unselected:probe" not in error
    assert "unusual:fixture-ok (prefix:" not in error
    assert set(admission.queried(home)) == {
        "features:probe", "novel:probe", "unusual:fixture-ok",
    }
    assert len(admission.calls) == 1
    _assert_no_ownership_or_actions(admission)
    # The focused -s invocation doubles as an offline refusal demonstration.
    # capsys otherwise captures even with -s, so release it only for that mode.
    if request.config.getoption("capture") == "no":
        with capsys.disabled():
            print(error, end="")


@pytest.mark.parametrize("selectors", [("features:*",), ()], ids=["wildcard", "defaults"])
def test_wildcard_and_default_selections_check_all_selected_leaves(
    admission, capsys, selectors
):
    home = admission.pool()
    admission.install({
        "features:first": {"actions": [admission.action("features:first")]},
        "features:second": {"actions": [admission.action("features:second")]},
        "novel:unselected": {"actions": [admission.action("novel:unselected")]},
        "build": {"actions": [], "task_dep": ["features:*"]},
    })

    assert admission.run(*selectors) == 2
    error = capsys.readouterr().err
    assert "features:first" in error
    assert "features:second" in error
    assert set(admission.queried(home)) == {"features:first", "features:second"}
    _assert_no_ownership_or_actions(admission)


def test_admitted_unknown_prefix_reaches_fake_ownership_and_actions(admission):
    home = admission.pool(accepted=["features:fixture-ok", "novel:fixture-ok"])
    admission.install({
        "features:fixture-ok": {
            "actions": [(admission.action("features:fixture-ok"), ["tuple-argument"])],
        },
        "novel:fixture-ok": {"actions": [admission.action("novel:fixture-ok")]},
        "local": {"actions": [admission.action("local", marked=False)]},
        "build": {
            "actions": [],
            "task_dep": ["features:fixture-ok", "novel:fixture-ok", "local"],
        },
    })

    assert admission.run("build") == 0
    assert set(admission.queried(home)) == {"features:fixture-ok", "novel:fixture-ok"}
    assert admission.events[:5] == ["preflight", "producer", "ownership", "mint", "register"]
    assert set(admission.events[5:-2]) == {
        ("action", "features:fixture-ok"), ("action", "novel:fixture-ok"), ("action", "local"),
    }
    assert admission.events[-2:] == [("finish", True), "close"]


def test_changing_selected_pool_changes_admission_for_the_same_task(admission, capsys):
    admission.install({"features:probe": {"actions": [admission.action("features:probe")]}})
    denied = admission.pool("denying-pool")
    assert admission.run("features:probe") == 2
    assert "features:probe" in capsys.readouterr().err
    _assert_no_ownership_or_actions(admission)

    allowed = admission.pool("allowing-pool", accepted=["features:probe"])
    assert admission.run("features:probe") == 0
    assert admission.queried(denied) == ["features:probe"]
    assert admission.queried(allowed) == ["features:probe"]
    assert [Path(argv[4]) for argv, _tasks in admission.calls] == [denied, allowed]
    assert ("action", "features:probe") in admission.events


def test_selected_pool_protocol_overrides_an_inherited_import_path(admission, monkeypatch):
    decoy = admission.pool(
        "decoy-pool",
        protocol="raise RuntimeError('inherited protocol must not be imported')\n",
    )
    (decoy / "agent" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(decoy))
    home = admission.pool("selected-pool", accepted=["features:fixture-ok"])
    admission.install({
        "features:fixture-ok": {"actions": [admission.action("features:fixture-ok")]},
    })

    assert admission.run("features:fixture-ok") == 0
    assert admission.queried(home) == ["features:fixture-ok"]
    assert not (decoy / "queried.jsonl").exists()


def test_only_aggregate_and_local_actions_skip_pool_lookup_and_query(admission, monkeypatch):
    admission.install({
        "features:local": {"actions": [admission.action("local", marked=False)]},
        "features:unselected": {"actions": [admission.action("features:unselected")]},
        "build": {"actions": [], "task_dep": ["features:local"]},
    })
    monkeypatch.setattr(build, "_pool_home", lambda: pytest.fail("no leaf needs a pool"))

    assert admission.run("build") == 0
    assert admission.calls == []
    assert ("action", "local") in admission.events
    assert ("action", "features:unselected") not in admission.events


def test_selection_and_admission_leave_original_dependencies_and_actions_intact(admission):
    home = admission.pool(accepted=["features:first", "features:second"])
    output = str(admission.tmp_path / "producer.bin")
    first = Task("features:first", [admission.action("features:first")], targets=[output])
    second = Task("features:second", [admission.action("features:second")])
    root = Task("build", [], task_dep=["features:*"], file_dep=[output])
    consumer = Task("consumer", [], file_dep=[output])
    tasks = [first, second, root, consumer]
    before = {task.name: list(task.task_dep) for task in tasks}
    original_actions = [first.actions[0], second.actions[0]]

    control = build._validate_farm_selection(tasks, ["build", "consumer"])
    assert isinstance(control, TaskControl)
    build._require_leaf_admission(control)

    assert {task.name: task.task_dep for task in tasks} == before
    assert first.actions[0] is original_actions[0]
    assert second.actions[0] is original_actions[1]
    assert set(admission.queried(home)) == {"features:first", "features:second"}
    assert admission.events == []


@pytest.mark.parametrize(
    "protocol",
    [
        "raise RuntimeError('fixture import failure')\n",
        "def different_api(task):\n    return True\n",
        "def leaf_admitted(task):\n    raise RuntimeError('fixture rule failure')\n",
    ],
    ids=["module-import", "missing-contract", "rule-failure"],
)
def test_pool_import_or_rule_failure_is_fail_closed(admission, capsys, protocol):
    admission.pool(protocol=protocol)
    admission.install({"features:probe": {"actions": [admission.action("features:probe")]}})

    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert error.startswith("farm:")
    assert "admission" in error
    assert "exit" in error
    _assert_no_ownership_or_actions(admission)


@pytest.mark.parametrize(
    "stdout",
    ["", "not JSON", "{}", "null", "[true]", "[17]", '["unselected:probe"]', "noise\n[]"],
    ids=["empty", "non-json", "object", "null", "bool", "number", "noncandidate", "noise"],
)
def test_invalid_pool_response_is_fail_closed(admission, monkeypatch, capsys, stdout):
    admission.pool()
    admission.install({"features:probe": {"actions": [admission.action("features:probe")]}})
    monkeypatch.setattr(
        build.subprocess, "run", lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 0, stdout, "")
    )

    assert admission.run("features:probe") == 2
    assert "invalid response" in capsys.readouterr().err
    _assert_no_ownership_or_actions(admission)


def test_admission_subprocess_unavailable_is_fail_closed(admission, monkeypatch, capsys):
    admission.pool()
    admission.install({"features:probe": {"actions": [admission.action("features:probe")]}})

    def unavailable(*_args, **_kwargs):
        raise FileNotFoundError(2, "fixture uv unavailable", "uv")

    monkeypatch.setattr(build.subprocess, "run", unavailable)
    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert "admission" in error
    assert "could not start" in error
    assert "fixture uv unavailable" in error
    _assert_no_ownership_or_actions(admission)


def test_nonzero_admission_exit_does_not_trust_successful_looking_stdout(
    admission, monkeypatch, capsys
):
    admission.pool()
    admission.install({"features:probe": {"actions": [admission.action("features:probe")]}})
    monkeypatch.setattr(
        build.subprocess, "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 19, "[]", "fixture protocol unavailable"),
    )

    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert "exit 19" in error
    assert "fixture protocol unavailable" in error
    _assert_no_ownership_or_actions(admission)


def test_leaf_action_marker_preserves_callable_identity_without_invoking_it():
    def action():
        pytest.fail("marking an action must not invoke it")

    assert _farm.leaf_action(action) is action
    assert action._farm_leaf_action is True


def test_all_four_dodo_dispatch_action_functions_are_marked_without_execution():
    save_success = Dependency.save_success
    json_dump = JsonDB.dump
    missing = object()
    content_checker = CHECKERS.get("content", missing)
    try:
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        assert spec is not None and spec.loader is not None
        dodo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dodo)
        for name in (
            "_cached_com_action", "_cached_drawing_action", "_cached_part_action", "build_or_refresh",
        ):
            action = getattr(dodo, name)
            assert callable(action)
            assert getattr(action, "_farm_leaf_action", False) is True, name
    finally:
        Dependency.save_success = save_success
        JsonDB.dump = json_dump
        if content_checker is missing:
            CHECKERS.pop("content", None)
        else:
            CHECKERS["content"] = content_checker


def test_every_direct_dodo_dispatch_helper_has_an_admission_marker():
    tree = ast.parse((REPO_ROOT / "dodo.py").read_text(encoding="utf-8"))
    helpers = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name != "_farm_build"
        and any(
            isinstance(call, ast.Call)
            and (
                (
                    isinstance(call.func, ast.Name)
                    and call.func.id in {"_farm_build", "_cached_com_action"}
                )
                or (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "_farm"
                    and call.func.attr == "run_leaf"
                )
            )
            for call in ast.walk(node)
        )
    ]
    names = {node.name for node in helpers}
    # Anchors make an accidentally empty or narrowed AST scan fail rather than
    # silently removing protection when another dispatch helper is introduced.
    assert {
        "_cached_com_action", "_cached_drawing_action",
        "_cached_part_action", "build_or_refresh",
    } <= names
    for helper in helpers:
        assert any(
            isinstance(decorator, ast.Attribute)
            and isinstance(decorator.value, ast.Name)
            and decorator.value.id == "_farm"
            and decorator.attr == "leaf_action"
            for decorator in helper.decorator_list
        ), f"{helper.name} dispatches a farm leaf but bypasses admission"

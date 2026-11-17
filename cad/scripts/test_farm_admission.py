"""Selected-pool leaf admission, with real doit parsing but no farm or COM.

The pool fixture deliberately admits exact task names, not production prefixes.
``farm_build.run_farm_build`` loads its stdlib protocol in-process; the fleet
check and ownership are intercepted before they can contact a service or write
a production record.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import doit.cmd_base as _doit_cmd_base
from doit.cmd_base import tasks_and_deps_iter
from doit.control import TaskControl
from doit.dependency import JsonDB
from doit.task import Task

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import _undefined_names  # noqa: E402
import build  # noqa: E402
import farm_build  # noqa: E402

_REAL_RUN = subprocess.run
_REAL_RUN_LEAF = _farm.run_leaf
_LABEL = "Offline selected-pool admission regression"


@pytest.fixture
def admission(tmp_path, monkeypatch):
    events = []
    selected = {"pool": tmp_path / "no-pool-selected"}
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(tmp_path / "run"))
    for key in (
        "HARMONIC_FARM_BUILD_ID",
        "HARMONIC_FARM_ADMITTED_LEAVES",
        "HARMONIC_CACHE_REFRESH",
    ):
        # Track originally absent keys too: run_farm_build writes admission
        # state directly, so a plain delenv on an absent key would not restore it.
        monkeypatch.setenv(key, "fixture-clear")
        monkeypatch.delenv(key, raising=False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("admission dispatched a farm leaf")

    monkeypatch.setattr(_farm, "run_leaf", forbidden)
    monkeypatch.setattr(
        farm_build,
        "require_fleet_protocol",
        lambda _pool, _protocol: events.append("preflight"),
    )
    monkeypatch.setattr(
        _undefined_names,
        "scan_undefined_names",
        lambda _root: subprocess.CompletedProcess([], 0, "", ""),
    )
    monkeypatch.setattr(
        _farm, "_build_id", lambda: events.append("mint") or "fixture-id"
    )

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
        selected["pool"] = home
        return home

    def action(name, marked=True):
        def record(*_args, **_kwargs):
            events.append(("action", name))
            return True

        return _farm.leaf_action(record) if marked else record

    def install(specs):
        namespace = {}
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
        selected["namespace"] = namespace

    def run(*selectors):
        record = {
            "targets": list(selectors),
            "pool_home": str(selected["pool"]),
            "display_name": _LABEL,
            "force_cache_refresh": [],
            "force_cache_refresh_reason": None,
        }
        # Explicit serial execution keeps the fake action observations in this
        # process and avoids workers, subprocesses and a DB.
        return farm_build.run_farm_build(
            record,
            selected["namespace"],
            extra_config={"GLOBAL": {"backend": "json", "dep_file": ":memory:"}},
            parallelism="0",
        )

    def queried(home):
        log = home / "queried.jsonl"
        return [
            json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
        ]

    return SimpleNamespace(
        events=events,
        pool=pool,
        action=action,
        install=install,
        run=run,
        queried=queried,
        tmp_path=tmp_path,
    )


def _assert_no_ownership_or_actions(admission):
    assert admission.events == [], (
        "refused admission ran preflight, ownership or an action"
    )
    assert not (admission.tmp_path / "run").exists()
    assert os.environ.get("HARMONIC_FARM_BUILD_ID") is None
    assert os.environ.get("HARMONIC_FARM_ADMITTED_LEAVES") is None


def _closure(tasks, selection):
    control = build._validate_farm_selection(tasks, selection)
    assert isinstance(control, TaskControl)
    return list(tasks_and_deps_iter(control.tasks, control.selected_tasks))


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
    admission.install(
        {
            "features:probe": {
                "actions": [admission.action("features:probe")],
                "targets": [str(target)],
            },
            "novel:probe": {"actions": [admission.action("novel:probe")]},
            "unusual:fixture-ok": {"actions": [admission.action("unusual:fixture-ok")]},
            "unselected:probe": {"actions": [admission.action("unselected:probe")]},
            "local": {
                "actions": [admission.action("local", marked=False)],
                "file_dep": [str(target)],
                "setup": ["novel:probe"],
            },
            "build": {"actions": [], "task_dep": ["local", "unusual:fixture-ok"]},
        }
    )

    assert admission.run("build") == 2
    error = capsys.readouterr().err
    assert "features:probe (prefix: features)" in error
    assert "novel:probe (prefix: novel)" in error
    assert "unselected:probe" not in error
    assert "unusual:fixture-ok (prefix:" not in error
    assert set(admission.queried(home)) == {
        "features:probe",
        "novel:probe",
        "unusual:fixture-ok",
    }
    _assert_no_ownership_or_actions(admission)
    # The focused -s invocation doubles as an offline refusal demonstration.
    # capsys otherwise captures even with -s, so release it only for that mode.
    if request.config.getoption("capture") == "no":
        with capsys.disabled():
            print(error, end="")


def test_wildcard_selection_checks_all_selected_leaves(admission, capsys):
    home = admission.pool()
    admission.install(
        {
            "features:first": {"actions": [admission.action("features:first")]},
            "features:second": {"actions": [admission.action("features:second")]},
            "novel:unselected": {"actions": [admission.action("novel:unselected")]},
            "build": {"actions": [], "task_dep": ["features:*"]},
        }
    )

    assert admission.run("features:*") == 2
    error = capsys.readouterr().err
    assert "features:first" in error
    assert "features:second" in error
    assert set(admission.queried(home)) == {"features:first", "features:second"}
    _assert_no_ownership_or_actions(admission)


def test_admitted_unknown_prefix_reaches_fake_ownership_and_actions(admission):
    home = admission.pool(accepted=["features:fixture-ok", "novel:fixture-ok"])
    admission.install(
        {
            "features:fixture-ok": {
                "actions": [
                    (admission.action("features:fixture-ok"), ["tuple-argument"])
                ],
            },
            "novel:fixture-ok": {"actions": [admission.action("novel:fixture-ok")]},
            "local": {"actions": [admission.action("local", marked=False)]},
            "build": {
                "actions": [],
                "task_dep": ["features:fixture-ok", "novel:fixture-ok", "local"],
            },
        }
    )

    assert admission.run("build") == 0
    assert set(admission.queried(home)) == {"features:fixture-ok", "novel:fixture-ok"}
    assert admission.events[:5] == [
        "preflight",
        "producer",
        "ownership",
        "mint",
        "register",
    ]
    assert set(admission.events[5:-2]) == {
        ("action", "features:fixture-ok"),
        ("action", "novel:fixture-ok"),
        ("action", "local"),
    }
    assert admission.events[-2:] == [("finish", True), "close"]


def test_changing_selected_pool_changes_admission_for_the_same_task(admission, capsys):
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )
    denied = admission.pool("denying-pool")
    assert admission.run("features:probe") == 2
    assert "features:probe" in capsys.readouterr().err
    _assert_no_ownership_or_actions(admission)

    allowed = admission.pool("allowing-pool", accepted=["features:probe"])
    assert admission.run("features:probe") == 0
    assert admission.queried(denied) == ["features:probe"]
    assert admission.queried(allowed) == ["features:probe"]
    assert ("action", "features:probe") in admission.events


def test_selected_pool_protocol_overrides_an_inherited_import_path(
    admission, monkeypatch
):
    decoy = admission.pool(
        "decoy-pool",
        protocol="raise RuntimeError('inherited protocol must not be imported')\n",
    )
    (decoy / "agent" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(decoy))
    home = admission.pool("selected-pool", accepted=["features:fixture-ok"])
    admission.install(
        {
            "features:fixture-ok": {
                "actions": [admission.action("features:fixture-ok")]
            },
        }
    )

    assert admission.run("features:fixture-ok") == 0
    assert admission.queried(home) == ["features:fixture-ok"]
    assert not (decoy / "queried.jsonl").exists()


def test_only_aggregate_and_local_actions_skip_pool_lookup_and_query(admission):
    # No pool is selected at all: the fixture's default home does not exist.
    admission.install(
        {
            "features:local": {"actions": [admission.action("local", marked=False)]},
            "features:unselected": {
                "actions": [admission.action("features:unselected")]
            },
            "build": {"actions": [], "task_dep": ["features:local"]},
        }
    )

    assert admission.run("build") == 0
    assert ("action", "local") in admission.events
    assert ("action", "features:unselected") not in admission.events


def test_selection_and_admission_leave_original_dependencies_and_actions_intact(
    admission,
):
    home = admission.pool(accepted=["features:first", "features:second"])
    output = str(admission.tmp_path / "producer.bin")
    first = Task(
        "features:first", [admission.action("features:first")], targets=[output]
    )
    second = Task("features:second", [admission.action("features:second")])
    root = Task("build", [], task_dep=["features:*"], file_dep=[output])
    consumer = Task("consumer", [], file_dep=[output])
    tasks = [first, second, root, consumer]
    before = {task.name: list(task.task_dep) for task in tasks}
    original_actions = [first.actions[0], second.actions[0]]

    farm_build.require_leaf_admission(_closure(tasks, ["build", "consumer"]), home)

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
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )

    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert error.startswith("farm:")
    assert "admission" in error
    assert "could not be read" in error
    _assert_no_ownership_or_actions(admission)


def test_missing_pool_protocol_is_refused(admission, capsys):
    home = admission.pool(accepted=["features:probe"])
    (home / "agent" / "protocol.py").unlink()
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )
    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert "agent/protocol.py" in error
    assert str(home) in error
    _assert_no_ownership_or_actions(admission)


@pytest.mark.parametrize(
    "marked", [True, False], ids=["label-mismatch", "unmarked-wrapper"]
)
@pytest.mark.parametrize(
    "inherited", [None, '["outer:admission"]'], ids=["absent", "inherited"]
)
def test_actual_dispatch_label_requires_scoped_admission(
    admission, monkeypatch, marked, inherited
):
    task_name = "package:fixture-ok"
    dispatched_label = "features:unadmitted"
    admission.pool(accepted=[task_name])
    if inherited is not None:
        monkeypatch.setenv("HARMONIC_FARM_ADMITTED_LEAVES", inherited)

    def forbidden(*_args, **_kwargs):
        pytest.fail("unadmitted label reached a request, span or reservation")

    monkeypatch.setattr(_farm._telemetry, "span", forbidden)
    monkeypatch.setattr(_farm, "LeafRequest", forbidden)
    monkeypatch.setattr(_farm, "_dispatch", forbidden)

    errors = []

    def action():
        expected = [task_name] if marked else []
        assert json.loads(os.environ["HARMONIC_FARM_ADMITTED_LEAVES"]) == expected
        try:
            return _REAL_RUN_LEAF(dispatched_label, "k" * 64)
        except RuntimeError as error:
            # doit's reporter can retain its import-time output stream. Capture
            # the actual guard error, then preserve the runner's failure path.
            errors.append(str(error))
            raise

    admission.install(
        {
            task_name: {"actions": [_farm.leaf_action(action) if marked else action]},
        }
    )
    assert admission.run(task_name) == 2
    assert len(errors) == 1
    assert dispatched_label in errors[0]
    assert "lacks preflight admission" in errors[0]
    assert admission.events[-2:] == [("finish", False), "close"]


def test_real_graph_every_marked_action_dispatches_its_task_name():
    # A fresh child avoids dodo's process-wide doit patches. Every native/cache
    # effect is intercepted, and capturing the label aborts before post-build
    # stamps or recipe sidecars can be written.
    #
    # The child bounds itself by CPU time, not wall time: loading the real graph
    # costs about 60 s of CPU cold and 10 s warm, while a loaded host only
    # stretches the wall clock (a 120 s wall timeout failed in an 8 h root run).
    # Its budget is 5x the cold cost. A child that stops consuming CPU for 300
    # consecutive watchdog ticks is blocked, not starved (a starved process still
    # runs between the watchdog's own wake-ups), and is dumped and killed.
    program = """
import faulthandler
import os
import sys
import threading
import time

def watchdog(cpu_budget_s=300.0, stalled_ticks=300, progress_s=0.05):
    previous, idle = time.process_time(), 0
    while True:
        time.sleep(1)
        used = time.process_time()
        if used - previous >= progress_s:
            previous, idle = used, 0
        else:
            idle += 1
        if used > cpu_budget_s or idle >= stalled_ticks:
            print(f'real-graph child exceeded its budget: {used:.1f} s CPU, '
                  f'{idle} idle ticks', file=sys.stderr, flush=True)
            faulthandler.dump_traceback(all_threads=True)
            os._exit(3)

threading.Thread(target=watchdog, daemon=True).start()

import json
from contextlib import nullcontext
from types import SimpleNamespace
from doit.loader import load_tasks
import dodo

def forbidden(*args, **kwargs):
    raise AssertionError('native or remote work escaped the graph invariant')

class CapturedLabel(Exception):
    pass

def capture(label, *args):
    raise CapturedLabel(label)

dodo._farm_build = capture
dodo._farm.enabled = lambda: True
dodo._farm.run_leaf = forbidden
dodo._com_seat = forbidden
dodo._exec_com = forbidden
dodo._sw_ensure_once = forbidden
dodo._cache_key = lambda *args: 'k' * 64
dodo._digest_files = lambda *args: 'fixture-digest'
dodo._probe_cache = lambda *args, **kwargs: 'miss'
dodo._telemetry.span = lambda *args, **kwargs: nullcontext(
    SimpleNamespace(set_attribute=lambda *args: None)
)
known = {
    dodo._cached_com_action, dodo._cached_drawing_action,
    dodo._cached_part_action, dodo.build_or_refresh,
}
checked = 0
helpers = set()
for task in load_tasks(vars(dodo), [], allow_delayed=False):
    for action in task.actions:
        function = getattr(action, 'py_callable', None)
        if not getattr(function, '_farm_leaf_action', False):
            continue
        assert function in known, (task.name, function)
        kwargs = dict(action.kwargs)
        if function is dodo.build_or_refresh:
            kwargs.update(dependencies=[], changed=[], targets=task.targets)
        try:
            function(*action.args, **kwargs)
        except CapturedLabel as captured:
            assert captured.args[0] == task.name, (task.name, captured.args[0])
        else:
            raise AssertionError((task.name, 'marked action did not dispatch'))
        checked += 1
        helpers.add(function.__name__)
assert checked > 0
assert helpers == {function.__name__ for function in known}
print(json.dumps({'checked': checked, 'helpers': sorted(helpers)}))
"""
    env = {
        **os.environ,
        "HARMONIC_EXECUTOR": "local",
        "HARMONIC_REMOTE_CACHE_MODE": "off",
        "HARMONIC_SW_AUTOSTART": "0",
        # The root conftest hands the session an empty syntax-facts store, so
        # in-process tests that patch the analyzer never write the real one.
        # This child patches no analyzer code; re-parsing every source cold
        # took 46 s of this test's 120 s alone on amet (16 s warm). A store of
        # its own, kept across sessions, stays content-keyed like the real one.
        "HARMONIC_BUILDGRAPH_CACHE": str(
            Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache")
            / "harmonic-analyzer"
            / "buildgraph-unpatched-test-children"
        ),
    }
    result = _REAL_RUN(
        [sys.executable, "-B", "-c", program],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout.splitlines()[-1])
    assert summary["checked"] > 0


def test_every_direct_dodo_dispatch_helper_has_an_admission_marker():
    tree = ast.parse((REPO_ROOT / "dodo.py").read_text(encoding="utf-8"))
    helpers = [
        node
        for node in ast.walk(tree)
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
        "_cached_com_action",
        "_cached_drawing_action",
        "_cached_part_action",
        "build_or_refresh",
    } <= names
    for helper in helpers:
        assert any(
            isinstance(decorator, ast.Attribute)
            and isinstance(decorator.value, ast.Name)
            and decorator.value.id == "_farm"
            and decorator.attr == "leaf_action"
            for decorator in helper.decorator_list
        ), f"{helper.name} dispatches a farm leaf but bypasses admission"

"""Selected-pool leaf admission, with real doit parsing but no farm or COM.

The pool fixture deliberately admits exact task names, not production prefixes.
Only its stdlib protocol runs in a child Python; uv, the fleet and ownership are
intercepted before they can contact a service or write a production request.
"""

import ast
import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import doit.cmd_base as _doit_cmd_base
from doit.cmd_base import ModuleTaskLoader
from doit.control import TaskControl
from doit.dependency import JsonDB
from doit.task import Task

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import build  # noqa: E402

_REAL_RUN = subprocess.run
_REAL_FARM_DOIT = build._FarmDoitMain
_REAL_RUN_LEAF = _farm.run_leaf
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
        "HARMONIC_FARM_ADMITTED_LEAVES",
        "HARMONIC_FARM_AGENT_IDENTITY",
        "HARMONIC_FARM_PREPARATION_READINESS",
    ):
        # Track originally absent keys too: build.main writes executor state
        # directly, so a plain delenv on an absent key would not restore it.
        monkeypatch.setenv(key, "fixture-clear")
        monkeypatch.delenv(key, raising=False)

    def forbidden(*_args, **_kwargs):
        pytest.fail("admission contacted the fleet or dispatched a farm leaf")

    monkeypatch.setattr(build, "_pool_farm", forbidden)
    monkeypatch.setattr(_farm, "run_leaf", forbidden)
    monkeypatch.setattr(
        build, "_farm_preflight", lambda **_kwargs: events.append("preflight")
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

    def pool(name="selected-pool", accepted=(), protocol=None, identity="a" * 64, preparation=None):
        home = tmp_path / name
        package = home / "agent"
        package.mkdir(parents=True)
        (home / "rule.json").write_text(json.dumps(list(accepted)), encoding="utf-8")
        (home / "pyproject.toml").write_text(
            '[project]\nname = "admission-fixture-pool"\nversion = "0.0.0"\n'
            'requires-python = ">=3.12,<3.15"\n[tool.uv]\npackage = false\n',
            encoding="utf-8",
        )
        (package / "contract.py").write_text(
            "def agent_identity_tag(identity):\n    return 'fixture-' + identity[:8]\n",
            encoding="utf-8",
        )
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
        protocol += f"\ndef agent_identity(_directory):\n    return {identity!r}\n"
        (package / "protocol.py").write_text(protocol, encoding="utf-8")
        if preparation is not None:
            (package / "preparation.py").write_text(preparation, encoding="utf-8")
        monkeypatch.setenv("SOLIDWORKS_POOL_HOME", str(home))
        return home

    def intercept(argv, **kwargs):
        argv = list(argv)
        candidates = json.loads(kwargs["input"])
        assert isinstance(candidates, list)
        assert all(isinstance(task, str) for task in candidates)
        assert len(candidates) == len(set(candidates))
        calls.append((argv, candidates))
        # Execute the actual production -c program, not a duplicated protocol
        # query. The fixture protocol needs no pool dependencies or installation.
        child_kwargs = dict(kwargs)
        child_kwargs["timeout"] = 10
        code_index = argv.index("-c")
        return _REAL_RUN([sys.executable, *argv[code_index:]], **child_kwargs)

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
                    extra_config={
                        "GLOBAL": {"backend": "json", "dep_file": ":memory:"}
                    },
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
        return [
            json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
        ]

    return SimpleNamespace(
        events=events,
        calls=calls,
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
    assert len(admission.calls) == 1
    _assert_no_ownership_or_actions(admission)
    # The focused -s invocation doubles as an offline refusal demonstration.
    # capsys otherwise captures even with -s, so release it only for that mode.
    if request.config.getoption("capture") == "no":
        with capsys.disabled():
            print(error, end="")


@pytest.mark.parametrize(
    "selectors", [("features:*",), ()], ids=["wildcard", "defaults"]
)
def test_wildcard_and_default_selections_check_all_selected_leaves(
    admission, capsys, selectors
):
    home = admission.pool()
    admission.install(
        {
            "features:first": {"actions": [admission.action("features:first")]},
            "features:second": {"actions": [admission.action("features:second")]},
            "novel:unselected": {"actions": [admission.action("novel:unselected")]},
            "build": {"actions": [], "task_dep": ["features:*"]},
        }
    )

    assert admission.run(*selectors) == 2
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


def test_only_aggregate_and_local_actions_skip_pool_lookup_and_query(
    admission, monkeypatch
):
    admission.install(
        {
            "features:local": {"actions": [admission.action("local", marked=False)]},
            "features:unselected": {
                "actions": [admission.action("features:unselected")]
            },
            "build": {"actions": [], "task_dep": ["features:local"]},
        }
    )
    monkeypatch.setattr(
        build, "_pool_home", lambda: pytest.fail("no leaf needs a pool")
    )

    assert admission.run("build") == 0
    assert admission.calls == []
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
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )

    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert error.startswith("farm:")
    assert "admission" in error
    assert "exit" in error
    _assert_no_ownership_or_actions(admission)


@pytest.mark.parametrize(
    "stdout",
    [
        "",
        "not JSON",
        "{}",
        "null",
        "[true]",
        "[17]",
        '["unselected:probe"]',
        "noise\n[]",
        '{"refused":["unselected:probe"],"agent_identity":"id","agent_version":"tag"}',
        '{"refused":[],"agent_identity":"","agent_version":"tag"}',
        '{"refused":[],"agent_identity":"id","agent_version":null}',
    ],
    ids=[
        "empty",
        "non-json",
        "object",
        "null",
        "bool",
        "number",
        "noncandidate",
        "noise",
        "foreign-task",
        "missing-identity",
        "missing-tag",
    ],
)
def test_invalid_pool_response_is_fail_closed(admission, monkeypatch, capsys, stdout):
    admission.pool()
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )
    monkeypatch.setattr(
        build.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(argv, 0, stdout, ""),
    )

    assert admission.run("features:probe") == 2
    assert "invalid response" in capsys.readouterr().err
    _assert_no_ownership_or_actions(admission)


def test_admission_subprocess_unavailable_is_fail_closed(
    admission, monkeypatch, capsys
):
    admission.pool()
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )

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
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )
    monkeypatch.setattr(
        build.subprocess,
        "run",
        lambda argv, **_kwargs: subprocess.CompletedProcess(
            argv, 19, "[]", "fixture protocol unavailable"
        ),
    )

    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert "exit 19" in error
    assert "fixture protocol unavailable" in error
    _assert_no_ownership_or_actions(admission)


def _identity_fleet(versions, *, ignored=()):
    def worker(index, version):
        return {
            "worker_id": f"worker-{index}",
            "agent_version": version,
            "farm_protocol_version": 5,
            "fresh": True,
        }

    return {
        "farm_protocol_version": 5,
        "verdict": "matched",
        "workers": [worker(i, version) for i, version in enumerate(versions)],
        "ignored": [worker(i, version) for i, version in enumerate(ignored)],
        "fresh_within_s": 120,
        "evidence_horizon_s": 1209600,
    }


@pytest.mark.parametrize(
    "versions",
    [["fixture-bbbbbbbb"], ["fixture-aaaaaaaa", "fixture-bbbbbbbb"], [None], []],
    ids=["different", "mixed", "missing", "unreported"],
)
def test_admitted_pool_rule_is_refused_when_deployed_identity_does_not_match(
    admission, monkeypatch, capsys, versions
):
    home = admission.pool(accepted=["features:probe"])
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )
    queried = []

    def agents(pool, *args):
        queried.append((pool, args))
        return subprocess.CompletedProcess(
            [], 0, json.dumps(_identity_fleet(versions)), ""
        )

    monkeypatch.setattr(build, "_pool_farm", agents)
    monkeypatch.setattr(
        build,
        "_farm_preflight",
        lambda **kwargs: build._require_fleet_protocol(home, 5, **kwargs),
    )
    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert "PoolHome agent identity " + "a" * 64 in error
    assert "agent_version fixture-aaaaaaaa" in error
    assert "reported fleet identities" in error
    for version in set(versions):
        assert (
            f"{version or '<unreported>'}: {versions.count(version)} worker(s)" in error
        )
    if not versions:
        assert "<unreported>: 0 worker(s)" in error
    assert (
        "Check out the deployed pool release at PoolHome, or finish the rollout."
        in error
    )
    assert queried == [(home, ("agents", "--json"))]
    assert admission.queried(home) == ["features:probe"]
    _assert_no_ownership_or_actions(admission)


@pytest.mark.parametrize(
    ("versions", "ignored"),
    [
        (["fixture-aaaaaaaa", "fixture-aaaaaaaa"], []),
        ([], ["fixture-aaaaaaaa"]),
        (["fixture-aaaaaaaa"], ["fixture-bbbbbbbb"]),
    ],
    ids=["matching", "last-report", "obsolete-report-ignored"],
)
def test_pool_identity_uses_existing_fleet_query_and_pool_canonical_tag(
    admission, monkeypatch, versions, ignored
):
    home = admission.pool(accepted=["features:probe"])
    control = build._validate_farm_selection(
        [Task("features:probe", [admission.action("features:probe")])],
        ["features:probe"],
    )
    labels, identity, readiness = build._require_leaf_admission(control)
    assert labels == ["features:probe"]
    assert identity == ("a" * 64, "fixture-aaaaaaaa")
    assert readiness is None
    queries = []

    def agents(pool, *args):
        queries.append((pool, args))
        return subprocess.CompletedProcess(
            [], 0, json.dumps(_identity_fleet(versions, ignored=ignored)), ""
        )

    monkeypatch.setattr(build, "_pool_farm", agents)
    build._require_fleet_protocol(home, 5, pool_identity=identity)
    assert queries == [(home, ("agents", "--json"))]
    assert admission.events == []


@pytest.mark.parametrize("missing", ["pyproject.toml", "agent/protocol.py"])
def test_missing_pool_admission_files_are_refused_before_starting_uv(
    admission, monkeypatch, capsys, missing
):
    home = admission.pool(accepted=["features:probe"])
    (home / missing).unlink()
    admission.install(
        {"features:probe": {"actions": [admission.action("features:probe")]}}
    )
    monkeypatch.setattr(
        build.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("missing files started uv"),
    )
    assert admission.run("features:probe") == 2
    error = capsys.readouterr().err
    assert "missing required admission files" in error
    assert str(home) in error
    assert str(Path(missing)) in error
    _assert_no_ownership_or_actions(admission)


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not available")
def test_real_uv_uses_the_selected_pool_project_and_environment(admission, monkeypatch):
    protocol = """
import json, os, sys
from pathlib import Path
def leaf_admitted(task):
    Path('runtime.json').write_text(json.dumps({
        'prefix': sys.prefix, 'cwd': os.getcwd(),
        'virtual_env': os.environ.get('VIRTUAL_ENV'),
    }), encoding='utf-8')
    return task == 'features:fixture-ok'
"""
    home = admission.pool(accepted=["features:fixture-ok"], protocol=protocol)
    monkeypatch.setenv("UV_PYTHON", sys.executable)
    monkeypatch.setenv("UV_PYTHON_DOWNLOADS", "never")
    monkeypatch.setenv("UV_OFFLINE", "1")
    inherited = str(admission.tmp_path / "unrelated-outer-venv")
    monkeypatch.setenv("VIRTUAL_ENV", inherited)
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    locked = _REAL_RUN(
        ["uv", "lock", "--offline", "--project", str(home)],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert locked.returncode == 0, locked.stdout + locked.stderr
    monkeypatch.setattr(build.subprocess, "run", _REAL_RUN)
    control = build._validate_farm_selection(
        [Task("features:fixture-ok", [admission.action("features:fixture-ok")])],
        ["features:fixture-ok"],
    )
    labels, identity, readiness = build._require_leaf_admission(control)
    assert labels == ["features:fixture-ok"]
    assert identity == ("a" * 64, "fixture-aaaaaaaa")
    assert readiness is None
    runtime = json.loads((home / "runtime.json").read_text(encoding="utf-8"))
    assert Path(runtime["cwd"]).resolve() == home.resolve()
    assert Path(runtime["prefix"]).resolve() == (home / ".venv").resolve()
    assert Path(runtime["virtual_env"]).resolve() == (home / ".venv").resolve()
    assert runtime["virtual_env"] != inherited
    assert admission.events == []


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
    assert os.environ.get("HARMONIC_FARM_ADMITTED_LEAVES") == inherited
    assert admission.events[-2:] == [("finish", False), "close"]


def test_real_graph_every_marked_action_dispatches_its_task_name():
    # A fresh child avoids dodo's process-wide doit patches. Every native/cache
    # effect is intercepted, and capturing the label aborts before post-build
    # stamps or recipe sidecars can be written.
    program = """
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
        timeout=120,
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


@pytest.mark.parametrize("readiness", [
    {"capability": "preparation-publish-v1", "configured": True,
     "account": "fixturebootstrap", "configuration_error": False},
    {"capability": "preparation-publish-v1", "configured": False,
     "account": None, "configuration_error": False},
    {"capability": "preparation-publish-v1", "configured": False,
     "account": None, "configuration_error": True},
])
def test_admission_captures_pure_readiness_in_same_selected_pool_query(admission, readiness):
    preparation = (
        "import sys\n"
        "from . import protocol\n"
        "def publisher_readiness(*, account=None):\n"
        "    assert protocol.agent_identity(None) == " + repr("a" * 64) + "\n"
        "    assert not any(name == 'azure' or name.startswith('azure.') for name in sys.modules)\n"
        "    return " + repr(readiness) + "\n"
    )
    home = admission.pool(accepted=["features:probe"], preparation=preparation)
    control = build._validate_farm_selection(
        [Task("features:probe", [admission.action("features:probe")])],
        ["features:probe"],
    )
    labels, identity, actual_readiness = build._require_leaf_admission(control)
    assert labels == ["features:probe"]
    assert identity == ("a" * 64, "fixture-aaaaaaaa")
    assert actual_readiness == readiness
    assert admission.queried(home) == ["features:probe"]
    assert len(admission.calls) == 1
    assert admission.events == []


def test_preparation_module_without_readiness_api_is_explicitly_unknown(admission):
    admission.pool(accepted=["features:probe"], preparation="OLD_PREPARATION_MODULE = True\n")
    control = build._validate_farm_selection(
        [Task("features:probe", [admission.action("features:probe")])],
        ["features:probe"],
    )
    labels, identity, readiness = build._require_leaf_admission(control)
    assert labels == ["features:probe"]
    assert identity == ("a" * 64, "fixture-aaaaaaaa")
    assert readiness is None
    assert len(admission.calls) == 1


def test_unconfigured_readiness_does_not_block_nondispatching_leaf_action(
    admission, monkeypatch,
):
    readiness = {
        "capability": "preparation-publish-v1", "configured": False,
        "account": None, "configuration_error": False,
    }
    previous = '{"previous":"readiness"}'
    monkeypatch.setenv("HARMONIC_FARM_PREPARATION_READINESS", previous)
    admission.pool(
        accepted=["features:probe"],
        preparation="def publisher_readiness(*, account=None):\n    return " + repr(readiness) + "\n",
    )

    @_farm.leaf_action
    def restored_leaf():
        assert json.loads(os.environ["HARMONIC_FARM_PREPARATION_READINESS"]) == readiness
        admission.events.append("restored-without-dispatch")
        return True

    admission.install({"features:probe": {"actions": [restored_leaf]}})
    assert admission.run("features:probe") == 0
    assert "restored-without-dispatch" in admission.events
    assert os.environ["HARMONIC_FARM_PREPARATION_READINESS"] == previous


@pytest.mark.parametrize(("preparation", "error_name"), [
    (
        "import sys\nprint('sensitive-config-value')\n"
        "print('sensitive-config-value', file=sys.stderr)\n"
        "raise ImportError('sensitive-config-value')\n",
        "ImportError",
    ),
    (
        "def publisher_readiness():\n    raise AttributeError('sensitive-config-value')\n",
        "AttributeError",
    ),
    (
        "def publisher_readiness():\n    raise TypeError('sensitive-config-value')\n",
        "TypeError",
    ),
    (
        "def publisher_readiness():\n    raise SystemExit('sensitive-config-value')\n",
        "SystemExit",
    ),
    (
        "def publisher_readiness():\n    return b'sensitive-config-value'\n",
        "TypeError",
    ),
])
def test_optional_readiness_probe_failure_does_not_block_cache_only_work(
    admission, preparation, error_name
):
    home = admission.pool(accepted=["features:probe"], preparation=preparation)
    captured = []

    @_farm.leaf_action
    def restored_leaf():
        captured.append(json.loads(os.environ["HARMONIC_FARM_PREPARATION_READINESS"]))
        return True

    admission.install({"features:probe": {"actions": [restored_leaf]}})
    assert admission.run("features:probe") == 0
    assert captured == [{"capability": None, "probe_error": error_name}]
    assert "sensitive-config-value" not in json.dumps(captured)
    assert admission.queried(home) == ["features:probe"]
    assert len(admission.calls) == 1


@pytest.mark.parametrize("failure", ["identity", "admission"])
def test_optional_probe_never_catches_mandatory_identity_or_admission_errors(
    admission, failure
):
    options = {"identity": None} if failure == "identity" else {
        "protocol": "def leaf_admitted(task):\n    raise RuntimeError('definitive admission refusal')\n",
    }
    home = admission.pool(
        accepted=["features:probe"],
        preparation=(
            "from pathlib import Path\n"
            "Path(__file__).with_name('probe-ran').write_text('optional probe ran')\n"
        ),
        **options,
    )
    control = build._validate_farm_selection(
        [Task("features:probe", [admission.action("features:probe")])],
        ["features:probe"],
    )
    expected = "TypeError" if failure == "identity" else "definitive admission refusal"
    with pytest.raises(build.FarmPreflightError, match=expected):
        build._require_leaf_admission(control)
    assert not (home / "agent" / "probe-ran").exists()
    assert admission.events == []


def test_optional_readiness_probe_does_not_sanitize_keyboard_interrupt(admission):
    admission.pool(
        accepted=["features:probe"],
        preparation="raise KeyboardInterrupt('probe interrupted')\n",
    )
    control = build._validate_farm_selection(
        [Task("features:probe", [admission.action("features:probe")])],
        ["features:probe"],
    )
    with pytest.raises(build.FarmPreflightError, match="KeyboardInterrupt"):
        build._require_leaf_admission(control)
    assert admission.events == []


@pytest.fixture
def bounded_pool_bridge(tmp_path, monkeypatch):
    """Own only inert handles; simulated waits advance the chosen clock domain."""
    state = SimpleNamespace(
        pool=tmp_path / "pool", events=[], returncode=0, clock=0.0,
        popen_error=None, adopt_error=None, wait_error=None, kill_error=None,
        cleanup_wait_error=None, cleanup_wait_elapsed=0.0,
        setup_elapsed=0.0, popen_elapsed=0.0, adopt_elapsed=0.0,
        kill_elapsed=0.0, termination_elapsed=0.0,
        work_timeouts=0, termination=True, termination_error=None,
        close_error=None, cleaning=False, closed=False, after_popen=None,
        after_adopt=None, during_wait=None, during_termination=None,
        during_close=None, on_popen=None, work_wait_elapsed=0.0,
        argv=["inert-owned-publisher", "--private-body"],
        env={"OWNERSHIP_FIXTURE": "inert"},
    )

    class OwnedProcess:
        # Deliberately no PID: a live ownership helper must never see this fake.
        def wait(self, *, timeout):
            phase = "cleanup" if state.cleaning else "work"
            state.events.append(("wait", timeout, phase))
            if state.cleaning:
                state.clock += (
                    timeout if isinstance(state.cleanup_wait_error, subprocess.TimeoutExpired)
                    else state.cleanup_wait_elapsed
                )
                if state.cleanup_wait_error is not None:
                    raise state.cleanup_wait_error
            else:
                state.clock += state.work_wait_elapsed
                if state.during_wait is not None:
                    state.during_wait()
                if state.wait_error is not None:
                    if isinstance(state.wait_error, subprocess.TimeoutExpired):
                        state.clock += timeout
                    raise state.wait_error
                if state.work_timeouts is None or state.work_timeouts > 0:
                    if state.work_timeouts is not None:
                        state.work_timeouts -= 1
                    # No wall-clock sleep, including for fractional last slices.
                    state.clock += timeout
                    raise subprocess.TimeoutExpired(state.argv, timeout)
            return state.returncode

        def kill(self):
            state.cleaning = True
            state.events.append(("kill-owned-handle",))
            state.clock += state.kill_elapsed
            if state.kill_error is not None:
                raise state.kill_error

    process = OwnedProcess()

    class OwnedTree:
        @property
        def popen_options(self):
            # Invalid for a live Popen: losing that mock must fail before spawn.
            return {"ownership_test_only": True}

        def adopt(self, adopted):
            assert adopted is process
            state.events.append(("adopt",))
            state.clock += state.adopt_elapsed
            if state.after_adopt is not None:
                state.after_adopt()
            if state.adopt_error is not None:
                raise state.adopt_error

        def terminate(self, adopted, *, timeout_s):
            assert adopted is process
            state.cleaning = True
            state.events.append(("terminate", timeout_s))
            state.clock += state.termination_elapsed
            if state.during_termination is not None:
                state.during_termination()
            if state.termination_error is not None:
                raise state.termination_error
            return state.termination

        def close(self):
            state.closed = True
            state.events.append(("close-tree",))
            if state.during_close is not None:
                state.during_close()
            if state.close_error is not None:
                raise state.close_error

    tree = OwnedTree()

    def forbidden(*args, **kwargs):
        pytest.fail("bounded publisher used an unowned subprocess collaborator")

    def popen(argv, **kwargs):
        assert kwargs.pop("ownership_test_only") is True
        assert kwargs["cwd"] == build.REPO_ROOT
        assert "VIRTUAL_ENV" not in kwargs["env"]
        assert kwargs["text"] is True
        # Telemetry is inherited, never a pipe or an unbounded retained file.
        assert kwargs["stdout"] is None
        state.events.append(("popen", list(argv)))
        state.clock += state.popen_elapsed
        if state.popen_error is not None:
            raise state.popen_error
        if state.on_popen is not None:
            state.on_popen(list(argv))
        if state.after_popen is not None:
            state.after_popen()
        return process

    def process_tree(pool):
        assert pool == state.pool
        state.events.append(("tree",))
        state.clock += state.setup_elapsed
        return tree

    def run(*, operation_deadline=900.0, process_margin_s=10.0, clock=None):
        return build._bounded_pool_farm(
            state.pool, state.argv, state.env,
            operation_deadline=operation_deadline,
            process_margin_s=process_margin_s,
            clock=clock,
        )

    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "unrelated-outer-venv"))
    monkeypatch.setattr(build, "time", SimpleNamespace(monotonic=lambda: state.clock))
    monkeypatch.setattr(build, "_pool_process_tree", process_tree)
    monkeypatch.setattr(build.subprocess, "Popen", popen)
    monkeypatch.setattr(build.subprocess, "run", forbidden)
    state.process = process
    state.tree = tree
    state.run = run
    state.publication_clock = lambda: state.clock
    return state


@pytest.mark.parametrize("returncode", [0, 23])
def test_bounded_pool_bridge_confirms_tree_without_capturing_telemetry(
    bounded_pool_bridge, returncode,
):
    state = bounded_pool_bridge
    state.returncode = returncode
    result = state.run()
    assert result.returncode == returncode
    assert result.args == state.argv
    assert result.stdout is None and result.stderr is None
    assert [event[0] for event in state.events] == [
        "tree", "popen", "adopt", "wait", "terminate", "close-tree",
    ]
    assert ("wait", 1.0, "work") in state.events
    assert ("terminate", 5.0) in state.events


def test_publisher_retries_share_original_nine_hundred_second_deadline(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.work_timeouts = None
    with pytest.raises(build.FarmPreflightError, match="deadline") as failure:
        state.run()
    assert not isinstance(failure.value, build.PoolProcessCleanupError)
    waits = [event[1] for event in state.events if event[0] == "wait"]
    assert len(waits) == 900
    assert all(0 < timeout <= 1.0 for timeout in waits)
    assert sum(waits) == 900.0
    assert state.clock == 900.0
    assert state.events[-2:] == [("terminate", 5.0), ("close-tree",)]


@pytest.mark.parametrize("elapsed_phase", ["setup_elapsed", "popen_elapsed", "adopt_elapsed"])
def test_prelaunch_and_setup_time_eat_original_deadline(bounded_pool_bridge, elapsed_phase):
    state = bounded_pool_bridge
    setattr(state, elapsed_phase, 2.25)
    state.work_timeouts = None
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.run(operation_deadline=3.5)
    waits = [event[1] for event in state.events if event[0] == "wait"]
    assert waits == [1.0, 0.25]
    assert state.clock == 3.5
    assert state.events[-2:] == [("terminate", 5.0), ("close-tree",)]


def test_expired_setup_does_not_launch_after_original_deadline(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.setup_elapsed = 2.0
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.run(operation_deadline=1.0)
    assert [event[0] for event in state.events] == ["tree", "close-tree"]


@pytest.mark.parametrize("normal_exit", [False, True])
def test_unconfirmed_owned_tree_cannot_return_or_report_completed_failure(
    bounded_pool_bridge, normal_exit,
):
    state = bounded_pool_bridge
    state.termination = False
    state.returncode = 23
    if not normal_exit:
        state.work_timeouts = None
    with pytest.raises(build.PoolProcessCleanupError) as failure:
        state.run(operation_deadline=2.0)
    assert failure.value.cleanup_confirmed is False
    assert state.events[-1] == ("close-tree",)


def test_failed_adoption_kills_root_before_tree_confirmation_and_reaping(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.adopt_error = OSError("assignment failed while owned child remained suspended")
    with pytest.raises(build.FarmPreflightError, match="create or adopt") as failure:
        state.run()
    assert failure.value.__cause__ is state.adopt_error
    assert [event[0] for event in state.events] == [
        "tree", "popen", "adopt", "kill-owned-handle", "terminate", "wait", "close-tree",
    ]
    assert state.events[-2] == ("wait", 5.0, "cleanup")


def test_failed_adoption_cleanup_spends_one_cumulative_reserve(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.adopt_error = OSError("resume failed after assignment")
    state.kill_elapsed = 1.25
    state.termination_elapsed = 2.5
    state.cleanup_wait_elapsed = 1.25
    with pytest.raises(build.FarmPreflightError, match="create or adopt") as failure:
        state.run()
    assert failure.value.__cause__ is state.adopt_error
    assert ("terminate", 3.75) in state.events
    assert ("wait", 1.25, "cleanup") in state.events
    assert state.clock == 5.0
    assert [event[0] for event in state.events].count("terminate") == 1
    assert [event[2] for event in state.events if event[0] == "wait"] == ["cleanup"]


def test_cleanup_reserve_is_capped_by_original_deadline_plus_margin(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.adopt_elapsed = 10.5
    state.adopt_error = OSError("late resume failure")
    state.termination_elapsed = 1.0
    state.cleanup_wait_elapsed = 0.5
    with pytest.raises(build.FarmPreflightError, match="create or adopt"):
        state.run(operation_deadline=2.0, process_margin_s=10.0)
    # C=min(10.5+5, 2+10)=12, not a fresh five seconds at each step.
    assert ("terminate", 1.5) in state.events
    assert ("wait", 0.5, "cleanup") in state.events
    assert state.clock == 12.0


def test_exhausted_cleanup_reserve_never_becomes_negative_or_renews(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.adopt_elapsed = 12.0
    state.adopt_error = OSError("resume failed beyond supervision margin")
    with pytest.raises(build.FarmPreflightError, match="create or adopt"):
        state.run(operation_deadline=2.0)
    assert ("terminate", 0.0) in state.events
    assert ("wait", 0.0, "cleanup") in state.events
    assert state.clock == 12.0


def test_adoption_cleanup_still_uses_tree_if_owned_handle_kill_is_interrupted(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.adopt_error = OSError("assignment failed")
    state.kill_error = KeyboardInterrupt()
    state.termination = False
    with pytest.raises(build.PoolProcessCleanupError):
        state.run()
    assert [event[0] for event in state.events] == [
        "tree", "popen", "adopt", "kill-owned-handle", "terminate", "wait", "close-tree",
    ]


def test_unreaped_unassigned_root_is_unconfirmed_even_when_tree_is_empty(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.adopt_error = OSError("assignment failed")
    state.cleanup_wait_error = subprocess.TimeoutExpired(state.argv, 5.0)
    with pytest.raises(build.PoolProcessCleanupError) as failure:
        state.run()
    assert failure.value.cleanup_confirmed is False
    assert [event[0] for event in state.events][-4:] == [
        "kill-owned-handle", "terminate", "wait", "close-tree",
    ]


def test_publisher_baseexception_confirms_owned_tree_before_propagating(bounded_pool_bridge):
    state = bounded_pool_bridge
    interrupted = KeyboardInterrupt()
    state.wait_error = interrupted
    with pytest.raises(KeyboardInterrupt) as failure:
        state.run()
    assert failure.value is interrupted
    assert [event[0] for event in state.events] == [
        "tree", "popen", "adopt", "wait", "terminate", "close-tree",
    ]


def test_publisher_cleanup_exception_is_unconfirmed_not_terminal(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.work_timeouts = None
    state.termination_error = RuntimeError("ownership confirmation unavailable")
    with pytest.raises(build.PoolProcessCleanupError):
        state.run(operation_deadline=2.0)
    assert state.events[-1] == ("close-tree",)


def test_failed_popen_closes_tree_without_claiming_a_created_process(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.popen_error = OSError("could not create owned child")
    with pytest.raises(build.FarmPreflightError, match="create or adopt") as failure:
        state.run()
    assert failure.value.__cause__ is state.popen_error
    assert [event[0] for event in state.events] == ["tree", "popen", "close-tree"]


@pytest.mark.parametrize("helper", ["bounded", "close"])
def test_generic_duration_helpers_default_to_monotonic_not_publication_counter(
    bounded_pool_bridge, monkeypatch, helper,
):
    state = bounded_pool_bridge
    monkeypatch.setattr(build, "time", SimpleNamespace(
        monotonic=lambda: state.clock, perf_counter=lambda: 9_000_000.0,
    ))
    if helper == "bounded":
        state.setup_elapsed = 2.25
        state.work_timeouts = None
        with pytest.raises(build.FarmPreflightError, match="deadline"):
            state.run(operation_deadline=3.5)
        assert [event[1] for event in state.events if event[0] == "wait"] == [1.0, 0.25]
        assert state.clock == 3.5
    else:
        state.clock = 10.0
        state.kill_elapsed = 1.25
        state.termination_elapsed = 2.5
        state.cleanup_wait_elapsed = 1.25
        assert build._close_owned_pool_process(
            state.tree, state.process, adopted=False, cleanup_deadline=15.0,
        ) is True
        assert ("terminate", 3.75) in state.events
        assert ("wait", 1.25, "cleanup") in state.events
        assert state.clock == 15.0
        state.tree.close()
    assert state.closed


def test_default_pool_bridge_keeps_existing_unbounded_run_contract(tmp_path, monkeypatch):
    expected = subprocess.CompletedProcess(["fixture"], 0, "existing stdout")
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return expected

    def forbidden(*args, **kwargs):
        pytest.fail("default bridge used bounded ownership machinery")

    monkeypatch.setattr(build.subprocess, "run", run)
    monkeypatch.setattr(build.subprocess, "Popen", forbidden)
    monkeypatch.setattr(build, "_pool_process_tree", forbidden)
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "outer"))
    assert build._pool_farm(tmp_path, "agents", "--json") is expected
    assert len(calls) == 1
    argv, options = calls[0]
    assert argv[-3:] == [str(tmp_path / "farm.py"), "agents", "--json"]
    assert options["stdout"] == subprocess.PIPE and options["text"] is True
    assert options["cwd"] == build.REPO_ROOT
    assert "VIRTUAL_ENV" not in options["env"]
    assert "timeout" not in options


def test_process_tree_loads_exact_selected_file_without_cached_agent(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("cached foreign agent ownership helper was used")

    monkeypatch.setitem(sys.modules, "agent.process_tree", SimpleNamespace(ProcessTree=forbidden))
    baseline = {name for name in sys.modules if name.startswith("_harmonic_selected_")}
    for label in ("first-pool", "second-pool"):
        pool = tmp_path / label
        (pool / "agent").mkdir(parents=True)
        (pool / "agent" / "process_tree.py").write_text(
            "class ProcessTree:\n"
            "    def __init__(self, *, log):\n"
            "        self.log = log\n"
            "        self.marker = " + repr(label) + "\n",
            encoding="utf-8",
        )
        tree = build._pool_process_tree(pool)
        assert tree.marker == label
        assert tree.log is build._pool_process_log
    assert {name for name in sys.modules if name.startswith("_harmonic_selected_")} == baseline


def test_publication_clock_loads_exact_selected_callable_without_cached_agent(
    tmp_path, monkeypatch,
):
    def forbidden(*args, **kwargs):
        pytest.fail("publication clock used a foreign protocol or local fallback")

    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace(__path__=["foreign-pool"]))
    monkeypatch.setitem(
        sys.modules, "agent.protocol", SimpleNamespace(publication_clock=forbidden),
    )
    monkeypatch.setattr(build, "time", SimpleNamespace(
        monotonic=forbidden, perf_counter=forbidden,
    ))
    baseline = {name for name in sys.modules if name.startswith("_harmonic_selected_")}
    for label, epoch in (("first-pool", 50_000.0), ("second-pool", 17.0)):
        pool = tmp_path / label
        package = pool / "agent"
        package.mkdir(parents=True)
        (package / "protocol.py").write_text(
            "PUBLICATION_EPOCH = " + repr(epoch) + "\n"
            "def publication_clock():\n"
            "    return PUBLICATION_EPOCH\n",
            encoding="utf-8",
        )
        clock = build._pool_publication_clock(pool)
        assert clock is clock.__globals__["publication_clock"]
        assert clock.__module__.startswith("_harmonic_selected_protocol_")
        assert clock() == epoch
    assert {name for name in sys.modules if name.startswith("_harmonic_selected_")} == baseline


@pytest.mark.parametrize("missing", ["file", "helper", "callable"])
def test_missing_selected_publication_clock_fails_closed_without_any_publication(
    tmp_path, monkeypatch, missing,
):
    if missing != "file":
        package = tmp_path / "agent"
        package.mkdir()
        (package / "protocol.py").write_text(
            "UNRELATED_API = True\n" if missing == "helper" else "publication_clock = None\n",
            encoding="utf-8",
        )

    def forbidden(*args, **kwargs):
        pytest.fail("missing selected clock fell back or started publication work")

    monkeypatch.setitem(
        sys.modules, "agent.protocol", SimpleNamespace(publication_clock=forbidden),
    )
    monkeypatch.setattr(build, "time", SimpleNamespace(
        monotonic=forbidden, perf_counter=forbidden,
    ))
    monkeypatch.setattr(build, "_pool_process_tree", forbidden)
    monkeypatch.setattr(build.subprocess, "Popen", forbidden)
    monkeypatch.setattr(build.subprocess, "run", forbidden)
    monkeypatch.setattr(build.tempfile, "TemporaryDirectory", forbidden)
    baseline = {name for name in sys.modules if name.startswith("_harmonic_selected_")}
    with pytest.raises(build.FarmPreflightError):
        build._pool_publication_clock(tmp_path)
    assert {name for name in sys.modules if name.startswith("_harmonic_selected_")} == baseline


@pytest.mark.parametrize("missing", ["file", "class"])
def test_bounded_bridge_refuses_missing_ownership_api_before_spawn(tmp_path, monkeypatch, missing):
    if missing == "class":
        (tmp_path / "agent").mkdir()
        (tmp_path / "agent" / "process_tree.py").write_text("NOT_THE_REQUIRED_API = True\n")

    def forbidden(*args, **kwargs):
        pytest.fail("missing ownership API launched an unowned process")

    monkeypatch.setattr(build.subprocess, "Popen", forbidden)
    monkeypatch.setattr(build.subprocess, "run", forbidden)
    monkeypatch.setattr(build, "time", SimpleNamespace(monotonic=lambda: 0.0))
    with pytest.raises(build.FarmPreflightError, match="process_tree helper|ProcessTree"):
        build._bounded_pool_farm(
            tmp_path, ["inert-publisher"], {},
            operation_deadline=900.0, process_margin_s=10.0,
        )


def test_close_error_cannot_mask_unconfirmed_cleanup_as_terminal_failure(bounded_pool_bridge):
    state = bounded_pool_bridge
    state.work_timeouts = None
    state.termination = False
    state.close_error = OSError("ownership handle close failed")
    with pytest.raises(build.PoolProcessCleanupError) as failure:
        state.run(operation_deadline=2.0)
    assert failure.value.cleanup_confirmed is False
    assert state.closed


@pytest.fixture
def publisher_signals(bounded_pool_bridge, monkeypatch):
    """Deliver synthetic SIGINT only through the supervisor's installed handler."""
    state = SimpleNamespace(
        interrupted=KeyboardInterrupt("synthetic publisher cancellation"),
        delivered=[], installed=[], main=True,
    )

    def original(signum, frame):
        state.delivered.append((signum, frame))
        raise state.interrupted

    state.handler = original
    main_thread = object()
    worker_thread = object()

    def install(signum, handler):
        assert signum == 2
        previous = state.handler
        state.handler = handler
        state.installed.append(handler)
        return previous

    def fire():
        state.handler(2, None)

    monkeypatch.setattr(build, "signal", SimpleNamespace(
        SIGINT=2, SIG_IGN=object(), getsignal=lambda signum: state.handler,
        signal=install,
    ))
    monkeypatch.setattr(build, "threading", SimpleNamespace(
        main_thread=lambda: main_thread,
        current_thread=lambda: main_thread if state.main else worker_thread,
    ))
    state.original = original
    state.fire = fire
    return state


@pytest.mark.parametrize("critical_point", ["after_popen", "after_adopt"])
def test_launch_cancellation_waits_until_handle_is_stored_and_adopted(
    bounded_pool_bridge, publisher_signals, critical_point,
):
    state = bounded_pool_bridge
    signals = publisher_signals
    setattr(state, critical_point, signals.fire)
    with pytest.raises(KeyboardInterrupt) as failure:
        state.run()
    assert failure.value is signals.interrupted
    assert [event[0] for event in state.events] == [
        "tree", "popen", "adopt", "terminate", "close-tree",
    ]
    assert signals.delivered == [(2, None)]
    assert signals.handler is signals.original


def test_second_cleanup_sigint_cannot_mask_unconfirmed_containment(
    bounded_pool_bridge, publisher_signals,
):
    state = bounded_pool_bridge
    signals = publisher_signals
    state.after_adopt = signals.fire
    state.during_termination = signals.fire
    state.termination = False
    with pytest.raises(build.PoolProcessCleanupError) as failure:
        state.run()
    assert failure.value.cleanup_confirmed is False
    assert failure.value.__cause__ is signals.interrupted
    assert signals.delivered == [(2, None)]
    assert signals.handler is signals.original
    assert state.events[-2:] == [("terminate", 5.0), ("close-tree",)]


def test_non_main_thread_cancellation_uses_finally_without_signal_registration(
    bounded_pool_bridge, publisher_signals,
):
    state = bounded_pool_bridge
    signals = publisher_signals
    signals.main = False
    state.wait_error = signals.interrupted
    with pytest.raises(KeyboardInterrupt) as failure:
        state.run()
    assert failure.value is signals.interrupted
    assert signals.installed == []
    assert state.events[-2:] == [("terminate", 5.0), ("close-tree",)]


def test_publication_cancellation_poll_without_running_loop_is_inert():
    assert build._raise_if_pool_publication_cancelled() is None


def test_already_cancelling_runner_task_cannot_create_publication_tree(bounded_pool_bridge):
    state = bounded_pool_bridge

    async def main():
        task = asyncio.current_task()
        task.cancel()
        assert task.cancelling() == 1
        try:
            state.run(clock=state.publication_clock)
        except asyncio.CancelledError:
            assert state.events == []
            raise
        pytest.fail("synchronous publication accepted an already-cancelling Runner task")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main())
    assert state.events == []


@pytest.mark.parametrize("cancel_point", [
    "before-wait", "timed-wait", "normal-wait", "terminate", "close",
])
def test_runner_first_task_cancellation_finishes_owned_cleanup_before_propagating(
    bounded_pool_bridge, cancel_point,
):
    state = bounded_pool_bridge
    observed = []

    async def main():
        task = asyncio.current_task()

        def cancel():
            assert task.cancelling() == 0
            task.cancel()
            assert task.cancelling() == 1

        if cancel_point == "before-wait":
            state.after_adopt = cancel
        elif cancel_point in ("timed-wait", "normal-wait"):
            state.during_wait = cancel
            state.work_timeouts = 1 if cancel_point == "timed-wait" else 0
        elif cancel_point == "terminate":
            state.during_termination = cancel
        else:
            state.during_close = cancel
        try:
            state.run(clock=state.publication_clock)
        except asyncio.CancelledError:
            observed.append(task.cancelling())
            assert state.cleaning and state.closed
            assert state.events[-2:] == [("terminate", 5.0), ("close-tree",)]
            raise
        pytest.fail("synchronous publication returned normally with cancellation pending")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main())
    assert observed == [1]
    assert [event[0] for event in state.events].count("terminate") == 1
    assert [event[0] for event in state.events].count("close-tree") == 1
    waits = [event for event in state.events if event[0] == "wait"]
    assert len(waits) == (0 if cancel_point == "before-wait" else 1)


@pytest.mark.parametrize("critical_point", ["after_popen", "after_adopt"])
def test_deferred_first_sigint_replays_runner_task_cancel_before_publication_wait(
    bounded_pool_bridge, publisher_signals, critical_point,
):
    state = bounded_pool_bridge
    signals = publisher_signals
    observed = []

    async def main():
        task = asyncio.current_task()
        runner_handler = signal.getsignal(signal.SIGINT)
        assert callable(runner_handler)

        def first_press(signum, frame):
            signals.delivered.append((signum, frame))
            assert task.cancelling() == 0
            runner_handler(signum, frame)
            assert task.cancelling() == 1

        signals.original = signals.handler = first_press
        setattr(state, critical_point, signals.fire)
        try:
            state.run(clock=state.publication_clock)
        except asyncio.CancelledError:
            observed.append(task.cancelling())
            assert state.cleaning and state.closed
            raise
        pytest.fail("first SIGINT cancelled Runner's task but publication kept running")

    # asyncio.Runner translates the propagated first-press task cancellation to
    # KeyboardInterrupt only after the synchronous owned cleanup has completed.
    with pytest.raises(KeyboardInterrupt):
        asyncio.run(main())
    assert observed == [1]
    assert signals.delivered == [(signal.SIGINT, None)]
    assert signals.handler is signals.original
    assert [event[0] for event in state.events] == [
        "tree", "popen", "adopt", "terminate", "close-tree",
    ]


@pytest.fixture
def preparation_bridge(bounded_pool_bridge, tmp_path, monkeypatch):
    """Use the real bridge/supervisor with one scripted selected-protocol authority."""
    state = bounded_pool_bridge
    state.workspace = tmp_path / "workspace"
    state.workspace.mkdir()
    state.commit = "c" * 40
    state.receipt_payload = b"opaque selected-protocol receipt"
    state.receipt_stage = "launch"
    state.decode_error = None
    state.decode_elapsed = 0.0
    state.decode_result = {"ok": True, "result": {"published": True, "source": "selected"}}
    state.decode_calls = []
    state.argument_calls = []
    state.protocol_load_elapsed = 0.0
    state.arguments_elapsed = 0.0
    state.storage_cleanup_elapsed = 0.0
    state.storage_cleanup_error = None
    state.storages = []
    state.result_file = None
    real_storage = build.tempfile.TemporaryDirectory
    state.selected_helper_loader = build._load_pool_helper

    def storage(*args, **kwargs):
        owned = real_storage(*args, **kwargs)
        original_cleanup = owned.cleanup
        state.storages.append((owned, original_cleanup))

        def cleanup():
            state.events.append(("receipt-cleanup",))
            state.clock += state.storage_cleanup_elapsed
            if state.storage_cleanup_error is not None:
                raise state.storage_cleanup_error
            original_cleanup()

        owned.cleanup = cleanup
        return owned

    def arguments(workspace, *, operation_deadline, result_file, commit=None):
        assert workspace == state.workspace
        assert commit == state.commit
        state.result_file = Path(result_file)
        assert state.result_file.parent.is_dir()
        assert not state.result_file.exists()
        state.argument_calls.append((operation_deadline, state.result_file, commit))
        state.events.append(("body-arguments", operation_deadline))
        state.clock += state.arguments_elapsed
        state.body_argv = [
            "-I", "-c", "INERT_SELECTED_PRIVATE_BODY", str(state.pool),
            "--workspace", str(workspace), "--commit", commit,
            "--operation-deadline", str(operation_deadline),
            "--result-file", str(result_file),
        ]
        return state.body_argv

    def decode(payload, returncode):
        # Receipt syntax/schema belongs to pool protocol tests, not this bridge.
        # The authority decides whether each scripted envelope is acceptable.
        assert state.closed
        assert state.cleaning and state.termination
        state.events.append(("decode-receipt", returncode))
        state.decode_calls.append((payload, returncode))
        state.clock += state.decode_elapsed
        if state.decode_error is not None:
            raise state.decode_error
        return state.decode_result

    state.protocol = SimpleNamespace(
        PREPARATION_OPERATION_TIMEOUT_S=900.0,
        PREPARATION_PROCESS_MARGIN_S=10.0,
        PREPARATION_RECEIPT_MAX_BYTES=64 * 1024,
        publication_body_arguments=arguments,
        publication_clock=state.publication_clock,
        decode_publication_receipt=decode,
    )

    def load(pool, module_name):
        assert pool == state.pool and module_name == "protocol"
        state.events.append(("selected-protocol",))
        state.clock += state.protocol_load_elapsed
        return state.protocol

    def write_receipt():
        if state.receipt_payload is not None:
            state.result_file.write_bytes(state.receipt_payload)

    def launched(argv):
        assert argv == [
            "uv", "run", "--frozen", "--project", str(state.pool), "python",
            *state.body_argv,
        ]
        assert str(state.pool / "farm.py") not in argv
        if state.receipt_stage == "launch":
            write_receipt()

    def terminate():
        if state.receipt_stage == "cleanup":
            write_receipt()

    def run(*, operation_deadline=900.0, process_margin_s=10.0):
        return build._pool_preparation(
            state.pool, state.workspace, commit=state.commit,
            operation_deadline=operation_deadline,
            process_margin_s=process_margin_s,
            clock=state.publication_clock,
        )

    def forbidden(*args, **kwargs):
        pytest.fail("publication used the public CLI or another supervisor")

    monkeypatch.setattr(build, "_load_pool_helper", load)
    monkeypatch.setattr(build, "_pool_farm", forbidden)
    monkeypatch.setattr(build.tempfile, "TemporaryDirectory", storage)
    state.on_popen = launched
    state.during_termination = terminate
    state.publish = run
    yield state
    # Retention is asserted while the bridge is responsible for the directory;
    # the fixture still removes its own deliberate residue after each test.
    for _owned, original_cleanup in state.storages:
        original_cleanup()


@pytest.mark.parametrize("wait_times_out", [False, True])
def test_preparation_task_cancellation_cleans_owned_tree_and_receipt_before_propagating(
    preparation_bridge, wait_times_out,
):
    state = preparation_bridge
    observed = []

    async def main():
        task = asyncio.current_task()

        def cancel():
            assert task.cancelling() == 0
            task.cancel()

        state.during_wait = cancel
        state.work_timeouts = 1 if wait_times_out else 0
        try:
            state.publish()
        except asyncio.CancelledError:
            observed.append(task.cancelling())
            assert state.cleaning and state.closed
            assert state.decode_calls == []
            assert state.events[-3:] == [
                ("terminate", 5.0), ("close-tree",), ("receipt-cleanup",),
            ]
            assert not state.result_file.parent.exists()
            raise
        pytest.fail("preparation accepted a receipt after its Runner task was cancelled")

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main())
    assert observed == [1]
    assert len([event for event in state.events if event[0] == "wait"]) == 1


@pytest.fixture(params=[
    (50_000.0, 17.0, 9_000_000.0),
    (17.0, 50_000.0, 0.0),
], ids=["selected-ahead-of-monotonic", "selected-behind-monotonic"])
def selected_publication_bridge(preparation_bridge, monkeypatch, request):
    """The selected authority, local monotonic and local counter have distinct epochs."""
    state = preparation_bridge
    epoch, monotonic_epoch, counter_epoch = request.param
    state.clock = state.selected_epoch = epoch
    monkeypatch.setattr(build, "time", SimpleNamespace(
        monotonic=lambda: state.clock + (monotonic_epoch - epoch),
        perf_counter=lambda: state.clock + (counter_epoch - epoch),
    ))
    assert state.protocol.publication_clock is state.publication_clock
    return state


def test_preparation_forwards_exact_selected_clock_to_supervision_and_owned_cleanup(
    selected_publication_bridge, monkeypatch,
):
    state = selected_publication_bridge
    clock = build._pool_publication_clock(state.pool)
    assert clock is state.protocol.publication_clock is state.publication_clock
    real_bounded = build._bounded_pool_farm
    real_close = build._close_owned_pool_process
    seen = []

    def bounded(*args, clock, **kwargs):
        assert clock is state.publication_clock
        seen.append("bounded")
        return real_bounded(*args, clock=clock, **kwargs)

    def close(*args, clock, **kwargs):
        assert clock is state.publication_clock
        seen.append("close")
        return real_close(*args, clock=clock, **kwargs)

    monkeypatch.setattr(build, "_bounded_pool_farm", bounded)
    monkeypatch.setattr(build, "_close_owned_pool_process", close)
    assert state.publish(operation_deadline=state.selected_epoch + 2.0) is state.decode_result["result"]
    assert seen == ["bounded", "close"]
    assert state.decode_calls == [(state.receipt_payload, 0)]
    assert not state.result_file.parent.exists()


@pytest.mark.parametrize(("cap", "caller_budget", "deadline_delta", "waits"), [
    (900.0, 3.5, 3.5, [1.0, 0.5]),
    (2.5, 100.0, 3.75, [1.0, 0.75]),
], ids=["original-caller-deadline", "selected-protocol-cap"])
def test_selected_epoch_caps_and_setup_subtract_from_one_original_deadline(
    selected_publication_bridge, cap, caller_budget, deadline_delta, waits,
):
    state = selected_publication_bridge
    state.protocol.PREPARATION_OPERATION_TIMEOUT_S = cap
    state.protocol_load_elapsed = 1.25
    state.arguments_elapsed = 0.75
    state.work_timeouts = None
    deadline = state.selected_epoch + deadline_delta
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.publish(operation_deadline=state.selected_epoch + caller_budget)
    assert state.argument_calls == [(deadline, state.result_file, state.commit)]
    assert [event[1] for event in state.events if event[0] == "wait"] == waits
    assert state.clock == deadline
    assert state.events[-3:] == [
        ("terminate", 5.0), ("close-tree",), ("receipt-cleanup",),
    ]
    assert state.decode_calls == []
    assert not state.result_file.parent.exists()


def test_selected_epoch_expired_argument_setup_cannot_spawn_late(
    selected_publication_bridge,
):
    state = selected_publication_bridge
    state.arguments_elapsed = 3.0
    deadline = state.selected_epoch + 2.0
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.publish(operation_deadline=deadline)
    assert state.argument_calls == [(deadline, state.result_file, state.commit)]
    assert state.clock == state.selected_epoch + 3.0
    assert not any(event[0] in ("tree", "popen") for event in state.events)
    assert state.decode_calls == []
    assert not state.result_file.parent.exists()


def test_selected_epoch_successful_wait_cannot_accept_after_original_deadline(
    selected_publication_bridge,
):
    state = selected_publication_bridge
    state.work_wait_elapsed = 2.25
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.publish(operation_deadline=state.selected_epoch + 2.0)
    assert state.clock == state.selected_epoch + 2.25
    assert ("wait", 1.0, "work") in state.events
    assert state.closed and state.cleaning
    assert state.decode_calls == []
    assert not state.result_file.parent.exists()


def test_selected_epoch_cleanup_c_and_each_remaining_subtraction_share_the_same_clock(
    selected_publication_bridge,
):
    state = selected_publication_bridge
    state.adopt_elapsed = 10.5
    state.adopt_error = OSError("late fixture adoption failure")
    state.kill_elapsed = 0.25
    state.termination_elapsed = 0.75
    state.cleanup_wait_elapsed = 0.5
    with pytest.raises(build.FarmPreflightError, match="create or adopt") as failure:
        state.publish(operation_deadline=state.selected_epoch + 2.0)
    assert failure.value.__cause__ is state.adopt_error
    # C=min(epoch+10.5+5, epoch+2+10)=epoch+12. Killing, tree
    # termination and root reaping must subtract from that same C in order.
    assert ("terminate", 1.25) in state.events
    assert ("wait", 0.5, "cleanup") in state.events
    assert state.clock == state.selected_epoch + 12.0
    assert [event[0] for event in state.events].count("terminate") == 1
    assert state.events[-2:] == [("close-tree",), ("receipt-cleanup",)]
    assert state.decode_calls == []
    assert not state.result_file.parent.exists()


@pytest.mark.parametrize("phase", ["before-read", "decode", "storage-cleanup"])
def test_selected_epoch_receipt_window_never_uses_local_monotonic_or_counter(
    selected_publication_bridge, phase,
):
    state = selected_publication_bridge
    if phase == "before-read":
        state.termination_elapsed = 12.0
    elif phase == "decode":
        state.decode_elapsed = 12.0
    else:
        state.storage_cleanup_elapsed = 12.0
    with pytest.raises(build.FarmPreflightError, match="margin"):
        state.publish(operation_deadline=state.selected_epoch + 2.0)
    assert state.clock == state.selected_epoch + 12.0
    assert state.decode_calls == (
        [] if phase == "before-read" else [(state.receipt_payload, 0)]
    )
    assert state.closed and state.cleaning
    assert not state.result_file.parent.exists()


def test_selected_epoch_receipt_can_finish_inside_original_margin_without_renewal(
    selected_publication_bridge,
):
    state = selected_publication_bridge
    state.work_wait_elapsed = 1.5
    state.termination_elapsed = 1.0
    state.decode_elapsed = 9.25
    state.storage_cleanup_elapsed = 0.125
    assert state.publish(operation_deadline=state.selected_epoch + 2.0) is state.decode_result["result"]
    assert state.clock == state.selected_epoch + 11.875
    assert state.decode_calls == [(state.receipt_payload, 0)]
    assert state.events[-3:] == [
        ("close-tree",), ("decode-receipt", 0), ("receipt-cleanup",),
    ]
    assert not state.result_file.parent.exists()


def test_preparation_uses_original_deadline_private_uv_body_and_sole_owned_tree(preparation_bridge):
    state = preparation_bridge
    state.clock = 100.0
    state.protocol_load_elapsed = 2.0
    state.arguments_elapsed = 3.0
    state.work_timeouts = None
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.publish(operation_deadline=107.5)
    assert state.argument_calls == [(107.5, state.result_file, state.commit)]
    waits = [event[1] for event in state.events if event[0] == "wait"]
    assert waits == [1.0, 1.0, 0.5]
    assert state.clock == 107.5
    assert [event[0] for event in state.events].count("tree") == 1
    assert [event[0] for event in state.events].count("popen") == 1
    assert state.decode_calls == []
    assert not state.result_file.parent.exists()


@pytest.mark.parametrize("receipt_stage", ["launch", "cleanup"])
def test_preparation_accepts_receipt_only_after_confirmed_subtree_and_cleans_storage(
    preparation_bridge, receipt_stage,
):
    state = preparation_bridge
    state.receipt_stage = receipt_stage
    result = state.publish()
    assert result is state.decode_result["result"]
    assert state.decode_calls == [(state.receipt_payload, 0)]
    names = [event[0] for event in state.events]
    assert names.index("terminate") < names.index("close-tree") < names.index("decode-receipt")
    assert names[-1] == "receipt-cleanup"
    assert not state.result_file.parent.exists()


@pytest.mark.parametrize("failure_kind", ["malformed", "oversized", "nonzero", "ok-false"])
def test_preparation_uses_shared_decoder_authority_for_safe_rejection(
    preparation_bridge, failure_kind, capsys,
):
    state = preparation_bridge
    secret = "receipt-token-must-never-leak"
    if failure_kind == "malformed":
        state.receipt_payload = ("not-json-" + secret).encode()
        state.decode_error = ValueError(secret)
    elif failure_kind == "oversized":
        state.receipt_payload = b"x" * (state.protocol.PREPARATION_RECEIPT_MAX_BYTES + 100)
        state.decode_error = ValueError(secret)
    elif failure_kind == "nonzero":
        state.returncode = 23
        state.decode_error = ValueError(secret)
    else:
        state.returncode = 1
        state.decode_result = {
            "ok": False,
            "error": {"code": "azure", "message": "Preparation Azure operation failed."},
        }
    with pytest.raises(build.FarmPreflightError) as failure:
        state.publish()
    expected = "Preparation Azure operation failed." if failure_kind == "ok-false" else "invalid result receipt"
    assert expected in str(failure.value)
    assert len(state.decode_calls) == 1
    payload, returncode = state.decode_calls[0]
    assert returncode == state.returncode
    assert payload == state.receipt_payload[:state.protocol.PREPARATION_RECEIPT_MAX_BYTES + 1]
    assert secret not in str(failure.value)
    assert secret not in "".join(capsys.readouterr())
    assert not state.result_file.parent.exists()


def test_missing_preparation_receipt_is_safe_failure_after_confirmed_cleanup(preparation_bridge):
    state = preparation_bridge
    state.receipt_payload = None
    with pytest.raises(build.FarmPreflightError, match="receipt"):
        state.publish()
    assert state.closed
    assert state.decode_calls == []
    assert not state.result_file.parent.exists()


def test_unconfirmed_preparation_cleanup_retains_parent_owned_result_directory(preparation_bridge):
    state = preparation_bridge
    state.termination = False
    with pytest.raises(build.PoolProcessCleanupError) as failure:
        state.publish()
    assert failure.value.cleanup_confirmed is False
    assert state.decode_calls == []
    assert state.result_file.is_file()
    assert "receipt-cleanup" not in [event[0] for event in state.events]
    assert any(str(state.result_file.parent) in note for note in failure.value.__notes__)


def test_successful_preparation_cannot_hide_result_storage_cleanup_failure(
    preparation_bridge, capsys,
):
    state = preparation_bridge
    secret = "local-path-secret-must-not-leak"
    state.storage_cleanup_error = OSError(secret)
    with pytest.raises(build.FarmPreflightError, match="result cleanup failed") as failure:
        state.publish()
    assert state.decode_calls == [(state.receipt_payload, 0)]
    assert state.result_file.exists()
    assert secret not in str(failure.value)
    assert secret not in "".join(capsys.readouterr())


def test_secondary_result_cleanup_failure_preserves_primary_receipt_failure(
    preparation_bridge, caplog,
):
    state = preparation_bridge
    state.decode_error = ValueError("secret-receipt-diagnostic")
    state.storage_cleanup_error = OSError("secret-cleanup-diagnostic")
    with pytest.raises(build.FarmPreflightError, match="invalid result receipt") as failure:
        state.publish()
    assert any("result cleanup failed" in note for note in failure.value.__notes__)
    assert "secret-cleanup-diagnostic" not in str(failure.value.__notes__)
    assert "secret-receipt-diagnostic" not in str(failure.value)
    assert "secret-cleanup-diagnostic" not in caplog.text


def test_preparation_refuses_expired_deadline_before_creating_result_storage(preparation_bridge):
    state = preparation_bridge
    state.clock = 900.0
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.publish(operation_deadline=900.0)
    assert state.argument_calls == []
    assert state.storages == []
    assert [event[0] for event in state.events] == ["selected-protocol"]


def test_preparation_argument_setup_cannot_restart_deadline_or_launch_late(preparation_bridge):
    state = preparation_bridge
    state.arguments_elapsed = 2.0
    with pytest.raises(build.FarmPreflightError, match="deadline"):
        state.publish(operation_deadline=1.0)
    assert state.argument_calls == [(1.0, state.result_file, state.commit)]
    assert state.decode_calls == []
    assert not any(event[0] == "popen" for event in state.events)
    assert not state.result_file.parent.exists()


def test_preparation_receipt_classification_cannot_extend_supervision_margin(preparation_bridge):
    state = preparation_bridge
    state.decode_elapsed = 12.0
    with pytest.raises(build.FarmPreflightError, match="margin"):
        state.publish(operation_deadline=2.0)
    assert state.clock == 12.0
    assert state.decode_calls == [(state.receipt_payload, 0)]
    assert not state.result_file.parent.exists()


def test_result_storage_cleanup_cannot_turn_expired_margin_into_success(preparation_bridge):
    state = preparation_bridge
    state.storage_cleanup_elapsed = 12.0
    with pytest.raises(build.FarmPreflightError, match="margin"):
        state.publish(operation_deadline=2.0)
    assert state.decode_calls == [(state.receipt_payload, 0)]
    assert not state.result_file.parent.exists()


def test_preparation_loads_exact_selected_protocol_not_foreign_cached_agent(
    preparation_bridge, tmp_path, monkeypatch,
):
    state = preparation_bridge

    def forbidden(*args, **kwargs):
        pytest.fail("publication reused a foreign cached agent protocol")

    monkeypatch.setitem(sys.modules, "agent", SimpleNamespace(__path__=["foreign-pool"]))
    monkeypatch.setitem(sys.modules, "agent.protocol", SimpleNamespace(
        publication_body_arguments=forbidden,
        publication_clock=forbidden,
        decode_publication_receipt=forbidden,
    ))
    monkeypatch.setattr(build, "_load_pool_helper", state.selected_helper_loader)
    baseline = {name for name in sys.modules if name.startswith("_harmonic_selected_")}

    def launched(argv):
        assert argv[:6] == ["uv", "run", "--frozen", "--project", str(state.pool), "python"]
        assert argv[6:8] == ["-I", "-c"]
        assert argv[9] == str(state.pool)
        assert str(state.pool / "farm.py") not in argv
        state.result_file = Path(argv[argv.index("--result-file") + 1])
        assert state.result_file.parent.is_dir()
        state.result_file.write_bytes(b"opaque selected-file receipt")

    state.on_popen = launched
    for label in ("first-pool", "second-pool"):
        state.pool = tmp_path / label
        state.cleaning = False
        state.closed = False
        package = state.pool / "agent"
        package.mkdir(parents=True)
        (package / "protocol.py").write_text(
            "from pathlib import Path\n"
            "PREPARATION_OPERATION_TIMEOUT_S = 900.0\n"
            "PREPARATION_PROCESS_MARGIN_S = 10.0\n"
            "PREPARATION_RECEIPT_MAX_BYTES = 65536\n"
            "def publication_clock():\n"
            "    return 0.0\n"
            "def publication_body_arguments(workspace, *, operation_deadline, result_file, commit=None):\n"
            "    return ['-I', '-c', 'INERT_SELECTED_FILE_BODY', str(Path(__file__).resolve().parents[1]),\n"
            "            '--workspace', str(workspace), '--operation-deadline', str(operation_deadline),\n"
            "            '--result-file', str(result_file)]\n"
            "def decode_publication_receipt(payload, returncode):\n"
            "    assert payload == b'opaque selected-file receipt' and returncode == 0\n"
            "    return {'ok': True, 'result': {'selected': " + repr(label) + "}}\n",
            encoding="utf-8",
        )
        state.publication_clock = build._pool_publication_clock(state.pool)
        assert state.publish() == {"selected": label}
        assert not state.result_file.parent.exists()
    assert {name for name in sys.modules if name.startswith("_harmonic_selected_")} == baseline


@pytest.mark.parametrize("missing", [
    "publication_body_arguments", "decode_publication_receipt",
    "PREPARATION_RECEIPT_MAX_BYTES", "publication_clock",
])
def test_preparation_refuses_missing_selected_protocol_capability_before_spawn(
    preparation_bridge, missing,
):
    state = preparation_bridge
    delattr(state.protocol, missing)
    with pytest.raises(build.FarmPreflightError, match="bounded preparation API"):
        state.publish()
    assert state.argument_calls == []
    assert state.storages == []
    assert state.events == [("selected-protocol",)]

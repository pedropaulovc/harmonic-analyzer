"""Farm executor (``HARMONIC_EXECUTOR=farm``): the submitter never takes the COM
seat, never publishes, and turns a farm outcome into the task's outcome."""

import asyncio
import getpass
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import doit.cmd_base as _doit_cmd_base
from doit.cmd_base import ModuleTaskLoader
from doit.dependency import CHECKERS, Dependency, JsonDB
from doit.doit_cmd import DoitMain as _RealDoitMain

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import build  # noqa: E402

PROTOCOL = 7
_RealRefreshDoitMain = build._RefreshDoitMain

SHA = "c" * 40
DISPLAY_NAME = "Test farm build"
BUILD_ID = "20261010T190000.000000Z-" + "b" * 32
FARM_ENV = (
    "HARMONIC_FARM_COMMIT",
    "HARMONIC_EXECUTOR",
    "HARMONIC_SW_AUTOSTART",
)


def _load_dodo():
    """Load dodo without leaking its process-wide doit patches into other tests."""
    save_success = Dependency.save_success
    json_dump = JsonDB.dump
    missing = object()
    content_checker = CHECKERS.get("content", missing)
    try:
        spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        Dependency.save_success = save_success
        JsonDB.dump = json_dump
        if content_checker is missing:
            CHECKERS.pop("content", None)
        else:
            CHECKERS["content"] = content_checker


def _leaf_result(**overrides):
    fields = dict(
        state="succeeded",
        exit_code=0,
        worker_id="sw-01@3",
        attempt=1,
        cache_present=True,
        log_blob="results/leaf/part__pen_rod/" + "k" * 64 + "/1/task.log",
        failure_category=None,
        failure_message=None,
    )
    fields.update(overrides)
    return _farm.LeafResult(**fields)


_FAILED_LEAF = dict(
    state="failed",
    exit_code=87,
    cache_present=False,
    failure_category="task_failed",
    failure_message="SolidWorks connect timed out",
)


def _refuse_local_build(dodo, monkeypatch, calls):
    """No COM seat, no local build, and record any ``cache.store`` attempt."""
    monkeypatch.setattr(
        dodo._cache, "store", lambda *args: calls["store"].append(args) or "stored"
    )
    monkeypatch.setattr(
        dodo, "_com_seat", lambda label: pytest.fail(f"{label} took the COM seat")
    )
    monkeypatch.setattr(
        dodo, "_exec_com", lambda *_a, **_kw: pytest.fail("built locally")
    )


@pytest.fixture(autouse=True)
def _farm_identity(monkeypatch):
    """Every dispatch below runs under a named build owned by this parent."""
    monkeypatch.setenv("HARMONIC_FARM_DISPLAY_NAME", DISPLAY_NAME)
    monkeypatch.setenv("HARMONIC_FARM_BUILD_ID", BUILD_ID)
    monkeypatch.setattr(_farm, "STATUS_POLL_INTERVAL_S", 0)

    class Producer:
        def __enter__(self):
            return self

        def finish(self, success):
            pass

        def __exit__(self, *_exc):
            return False

    # Real in-process doit coverage must not read TLS config or contact Temporal.
    monkeypatch.setattr(_farm, "producer_build", lambda _label: Producer())


def _restore_sequence(dodo, monkeypatch, calls, outcomes, on_hit=None):
    """``_cache.restore`` answering ``outcomes`` in turn; ``on_hit`` runs on True."""
    pending = iter(outcomes)

    def restore(key, outputs, label):
        calls["restore"].append((key, outputs, label))
        hit = next(pending)
        if hit and on_hit:
            on_hit()
        return hit

    monkeypatch.setattr(dodo._cache, "restore", restore)


@pytest.fixture
def farm_part(tmp_path, monkeypatch):
    """A farm-mode ``part:pen_rod`` whose probe misses; returns (dodo, script, calls)."""
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    script = tmp_path / "build_pen_rod.py"
    script.write_text("", encoding="utf-8")
    output = tmp_path / "pen-rod.SLDPRT"
    calls: dict[str, list] = {"restore": [], "store": [], "stamp": []}

    monkeypatch.setattr(dodo, "_part_file_deps", lambda _script, _stem: [str(script)])
    monkeypatch.setattr(dodo, "_part_cache_outputs", lambda _stem: [output])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "k" * 64)
    monkeypatch.setattr(
        dodo, "_stamp_part_execution", lambda stem: calls["stamp"].append(stem)
    )
    _refuse_local_build(dodo, monkeypatch, calls)

    def restore(outcomes):
        _restore_sequence(dodo, monkeypatch, calls, outcomes)

    return dodo, script, calls, restore


def test_failed_leaf_fails_the_task_with_the_farm_diagnosis(farm_part, monkeypatch):
    dodo, script, calls, restore = farm_part
    restore((False,))
    monkeypatch.setattr(
        dodo._farm, "run_leaf", lambda label, key: _leaf_result(**_FAILED_LEAF)
    )

    with pytest.raises(RuntimeError) as failure:
        dodo._cached_part_action("pen_rod", script)

    # The diagnosis and the forensics hint are authored by two different
    # changes, so this pins each half rather than one exact string that the
    # other half silently invalidates on merge.
    assert str(failure.value).startswith(
        "part:pen_rod failed on sw-01@3 [task_failed] exit 87: SolidWorks connect "
        "timed out (log: results/leaf/part__pen_rod/" + "k" * 64 + "/1/task.log)"
    )
    assert "failures/*" in str(failure.value)
    assert calls["stamp"] == []
    assert calls["store"] == []


def test_success_without_the_key_is_an_infrastructure_fault(farm_part, monkeypatch):
    dodo, script, calls, restore = farm_part
    restore((False, False))  # probe miss, then the post-farm restore also misses
    monkeypatch.setattr(dodo._farm, "run_leaf", lambda label, key: _leaf_result())

    with pytest.raises(RuntimeError, match=r"farm reported success but cache key k{12} is absent"):
        dodo._cached_part_action("pen_rod", script)

    assert len(calls["restore"]) == 2
    assert calls["stamp"] == []


def test_success_restores_the_leaf_key_and_stamps_without_publishing(
    farm_part, monkeypatch
):
    dodo, script, calls, restore = farm_part
    restore((False, True))
    dispatched = []
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: dispatched.append((label, key)) or _leaf_result(),
    )

    dodo._cached_part_action("pen_rod", script)

    assert dispatched == [("part:pen_rod", "k" * 64)]
    assert [r[0] for r in calls["restore"]] == ["k" * 64, "k" * 64]
    assert calls["stamp"] == ["pen_rod"]
    assert calls["store"] == [], "the worker publishes; the submitter never does"


def test_cache_missing_names_the_likely_causes(farm_part, monkeypatch):
    dodo, script, calls, restore = farm_part
    restore((False,))
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: _leaf_result(
            state="failed",
            cache_present=False,
            failure_category="cache_missing",
            failure_message=f"{label} exited 0 but cache key {key[:12]} is absent",
        ),
    )

    with pytest.raises(RuntimeError) as failure:
        dodo._cached_part_action("pen_rod", script)

    message = str(failure.value)
    assert message.startswith("part:pen_rod failed on sw-01@3 [cache_missing] exit 0:")
    assert _farm.CACHE_MISSING_CAUSES in message
    assert "failures/*" in message


ASM_BYTES = b"SLDASM restored from the farm"


@pytest.fixture
def farm_assembly(tmp_path, monkeypatch):
    """A farm-mode ``assembly:pen`` whose probe misses.

    The execution token and input ledger are real files under ``tmp_path``
    and the real ``_stamp_assembly_execution`` hashes the restored .SLDASM, so
    the token's content proves the restore happened before the stamp.
    """
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    out = tmp_path / "sldasm"
    asm = out / "pen.SLDASM"
    token = out / ".pen.execution"
    ledger = out / ".pen.inputs.json"
    calls: dict[str, list] = {"restore": [], "store": []}

    monkeypatch.setattr(dodo, "_recipe_files", lambda _stem: [])
    monkeypatch.setattr(dodo, "_ledger_inputs", lambda _deps: {"cad/x.py": "d" * 32})
    monkeypatch.setattr(dodo, "_assembly_cache_outputs", lambda _stem: [asm])
    monkeypatch.setattr(dodo, "_assembly_file_deps", lambda _stem: [])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "a" * 64)
    monkeypatch.setattr(dodo, "_sldasm", lambda _stem: str(asm))
    monkeypatch.setattr(dodo, "_assembly_execution_token", lambda _stem: str(token))
    _refuse_local_build(dodo, monkeypatch, calls)

    def land_assembly():
        asm.parent.mkdir(parents=True, exist_ok=True)
        asm.write_bytes(ASM_BYTES)

    def restore(outcomes):
        _restore_sequence(dodo, monkeypatch, calls, outcomes, on_hit=land_assembly)

    files = {"asm": asm, "token": token, "ledger": ledger}
    return dodo, files, calls, restore


def _build_assembly(dodo, files):
    dodo.build_or_refresh("pen", [], [], [str(files["asm"])])


def test_assembly_success_restores_then_stamps_token_and_recipe(
    farm_assembly, monkeypatch
):
    dodo, files, calls, restore = farm_assembly
    restore((False, True))
    dispatched = []
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: dispatched.append((label, key)) or _leaf_result(),
    )

    _build_assembly(dodo, files)

    assert dispatched == [("assembly:pen", "a" * 64)]
    assert [r[0] for r in calls["restore"]] == ["a" * 64, "a" * 64]
    assert files["token"].read_text(encoding="utf-8").strip() == (
        hashlib.sha256(ASM_BYTES).hexdigest()
    ), "token identifies the restored artefact, so restore ran before the stamp"
    assert json.loads(files["ledger"].read_text(encoding="utf-8")) == {
        "inputs": {"cad/x.py": "d" * 32}
    }
    assert calls["store"] == []


def test_assembly_failure_leaves_no_token_and_no_sidecar(farm_assembly, monkeypatch):
    dodo, files, calls, restore = farm_assembly
    restore((False,))
    monkeypatch.setattr(
        dodo._farm, "run_leaf", lambda label, key: _leaf_result(**_FAILED_LEAF)
    )

    with pytest.raises(RuntimeError, match=r"assembly:pen failed on sw-01@3 \[task_failed\]"):
        _build_assembly(dodo, files)

    assert len(calls["restore"]) == 1
    assert not files["token"].exists()
    assert not files["ledger"].exists()
    assert calls["store"] == []


@pytest.fixture
def farm_drawing(tmp_path, monkeypatch):
    """A farm-mode drawing (first registry entry) whose probe misses."""
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    stem = next(iter(dodo.DRAWINGS_BY_NAME))
    outputs = [tmp_path / "drawing.SLDDRW", tmp_path / "drawing.pdf"]
    calls: dict[str, list] = {"restore": [], "store": []}

    monkeypatch.setattr(dodo, "_drawing_cache_outputs", lambda _stem: outputs)
    monkeypatch.setattr(dodo, "_drawing_file_deps", lambda _stem: [])
    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "w" * 64)
    _refuse_local_build(dodo, monkeypatch, calls)

    def restore(outcomes):
        _restore_sequence(dodo, monkeypatch, calls, outcomes)

    return dodo, stem, calls, restore


def test_drawing_success_restores_without_seat_or_store(farm_drawing, monkeypatch):
    dodo, stem, calls, restore = farm_drawing
    restore((False, True))
    dispatched = []
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: dispatched.append((label, key)) or _leaf_result(),
    )

    assert dodo._cached_drawing_action(stem) is None

    assert dispatched == [(f"drawing:{stem}", "w" * 64)]
    assert [r[0] for r in calls["restore"]] == ["w" * 64, "w" * 64]
    assert calls["store"] == []


def test_drawing_failure_raises_the_farm_diagnosis(farm_drawing, monkeypatch):
    dodo, stem, calls, restore = farm_drawing
    restore((False,))
    monkeypatch.setattr(
        dodo._farm, "run_leaf", lambda label, key: _leaf_result(**_FAILED_LEAF)
    )

    with pytest.raises(RuntimeError, match=rf"drawing:{stem} failed on sw-01@3"):
        dodo._cached_drawing_action(stem)

    assert len(calls["restore"]) == 1
    assert calls["store"] == []


@pytest.fixture
def farm_gate(tmp_path, monkeypatch):
    """A farm-mode COM gate (``verify_soundness:pen``) whose probe misses.

    A gate's cached output is its stamp, so this is the shape every gate, the
    neutral export and the release Pack-and-Go share (`_cached_com_action`).
    """
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    stamp = tmp_path / "verify-soundness-pen.ok"
    calls: dict[str, list] = {"restore": [], "store": []}

    monkeypatch.setattr(dodo, "_cache_key", lambda _deps, _label: "g" * 64)
    _refuse_local_build(dodo, monkeypatch, calls)

    def restore(outcomes):
        _restore_sequence(
            dodo,
            monkeypatch,
            calls,
            outcomes,
            on_hit=lambda: stamp.write_text("verify_soundness:pen\n", encoding="utf-8"),
        )

    def run():
        dodo._cached_com_action(
            "verify_soundness:pen",
            ["verify.py", "pen", "--suite", "soundness"],
            ["verify.py"],
            [stamp],
            "verify-soundness-pen",
            str(stamp),
        )

    return dodo, stamp, calls, restore, run


def test_a_com_gate_is_dispatched_and_its_stamp_restored(farm_gate, monkeypatch):
    """The gates are farm leaves now: the submitter holds no seat, runs no
    SolidWorks, publishes nothing, and ends up with the stamp the worker made."""
    dodo, stamp, calls, restore, run = farm_gate
    restore((False, True))
    dispatched = []
    monkeypatch.setattr(
        dodo._farm,
        "run_leaf",
        lambda label, key: dispatched.append((label, key)) or _leaf_result(),
    )

    assert run() is None

    assert dispatched == [("verify_soundness:pen", "g" * 64)]
    assert calls["store"] == []
    assert stamp.read_text(encoding="utf-8") == "verify_soundness:pen\n"


def test_a_failed_gate_leaf_fails_the_task_and_leaves_no_stamp(farm_gate, monkeypatch):
    dodo, stamp, calls, restore, run = farm_gate
    restore((False,))
    monkeypatch.setattr(
        dodo._farm, "run_leaf", lambda label, key: _leaf_result(**_FAILED_LEAF)
    )

    with pytest.raises(
        RuntimeError, match=r"verify_soundness:pen failed on sw-01@3 \[task_failed\]"
    ):
        run()

    assert not stamp.exists(), "a failed gate must not stamp"
    assert calls["store"] == []


def test_a_cached_gate_never_dispatches_a_leaf(farm_gate, monkeypatch):
    dodo, stamp, calls, restore, run = farm_gate
    restore((True,))
    monkeypatch.setattr(
        dodo._farm, "run_leaf", lambda label, key: pytest.fail("dispatched on a hit")
    )

    assert run() is None

    assert len(calls["restore"]) == 1
    assert calls["store"] == []
    # The restored stamp IS the gate's verdict -- a hit that leaves no stamp
    # would make doit re-run the gate on the next build.
    assert stamp.read_text(encoding="utf-8") == "verify_soundness:pen\n"


# --- build.py: the local entry point -----------------------------------------


def _fixture_namespace(executed):
    def record():
        executed.append({key: os.environ.get(key) for key in FARM_ENV})

    def task_part():
        yield {"name": "x", "actions": [record]}

    return {"task_part": task_part}


def _install_real_doit(monkeypatch, namespace=None):
    """Use doit's real parser, loader and execution boundary with isolated state."""
    seen = []
    executed = []
    task_namespace = namespace or _fixture_namespace(executed)

    class MemoryJsonDB(JsonDB):
        def __init__(self, name, codec, *, module_name=None):
            self.name = name
            self.codec = codec
            self._db = {}

        def dump(self):
            pass

    monkeypatch.setattr(_doit_cmd_base, "JsonDB", MemoryJsonDB)
    config = {"GLOBAL": {"backend": "json", "dep_file": ":memory:"}}

    class FixtureLocalDoit(_RealRefreshDoitMain):
        def __init__(self):
            super().__init__(
                task_loader=ModuleTaskLoader(task_namespace), extra_config=config
            )

        def run(self, args):
            seen.append(list(args))
            return super().run(args)

    monkeypatch.setattr(build, "DoitMain", FixtureLocalDoit)
    monkeypatch.setattr(build, "_RefreshDoitMain", FixtureLocalDoit)
    return seen, executed


def test_build_py_is_local_whatever_the_environment_says(monkeypatch):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["part:x"]) == 0
    assert seen == [["part:x"]]
    assert len(executed) == 1
    assert executed[0]["HARMONIC_EXECUTOR"] == "local"
    assert not _farm.enabled()


def test_default_build_target_carries_the_verify_gates_under_every_executor(
    monkeypatch,
):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    local_deps = _load_dodo().task_build()["task_dep"]
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    farm_deps = _load_dodo().task_build()["task_dep"]

    assert [d for d in local_deps if d.startswith("verify:")] == [
        "verify:soundness",
        "verify:kinematics",
    ]
    assert farm_deps == local_deps
    assert any(d.startswith("check:") for d in farm_deps)
    assert any(d.startswith("drawing:") for d in farm_deps)


@pytest.mark.parametrize(
    ("given", "runs"),
    [
        (["assembly:x"], True),
        (["run", "assembly:x"], True),
        (["list"], False),
        ([], True),
        (["--help"], False),
        (["-h"], False),
        (["--version"], False),
        (["-f", "dodo.py", "list"], False),
        (["-kf", "dodo.py", "part:x"], True),
        (["profile=ci", "list"], False),
        (["profile=ci", "run", "x"], True),
        (["strace", "part:x"], True),
        # doit has no per-command help: its parser rejects these and exits 3.
        (["run", "--help"], False),
        (["-n", "abc", "x"], False),
        (["run", "--", "--help"], True),
    ],
)
def test_only_task_executing_commands_count_as_executing(given, runs):
    assert (build._executing_command(list(given), _RealDoitMain()) is not None) is runs


def test_help_names_the_wrapper_options_then_doit_commands(monkeypatch, capsys):
    seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--help"]) == 0
    assert build.main(["help", "run"]) == 0
    assert seen == [["--help"], ["help", "run"]]
    assert executed == []
    out = capsys.readouterr().out
    assert "--verbosity" in out
    assert "farm_build.py" in out


# --- _farm: config and the Temporal boundary ---------------------------------


TOKEN = "eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJzdWJtaXR0ZXItdGVzdCJ9.c2ln"


def _write_config(tmp_path: Path, **overrides) -> Path:
    for name in ("ca.pem", "client.pem", "client-key.pem"):
        (tmp_path / name).write_bytes(b"-----BEGIN " + name.encode() + b"-----\n")
    (tmp_path / "token.jwt").write_text(TOKEN + "\n", encoding="ascii")
    (tmp_path / "empty.jwt").write_bytes(b"")
    (tmp_path / "blank.jwt").write_text(" \n\n", encoding="ascii")
    (tmp_path / "bom.jwt").write_bytes(b"\xef\xbb\xbf" + TOKEN.encode("ascii"))
    config = {
        "temporal_address": "farm.example.invalid:7233",
        "namespace": "solidworks",
        "ca_cert": "ca.pem",
        "client_cert": "client.pem",
        "client_key": "client-key.pem",
        "token": "token.jwt",
    }
    config.update(overrides)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("overrides", "problem"),
    [
        ({"namespace": ""}, "namespace must be a non-empty string"),
        ({"client_key": 7}, "client_key must be a non-empty string"),
        ({"client_cert": "missing.pem"}, "client_cert file is not readable"),
        ({"token": ""}, "token must be a non-empty string"),
        ({"token": "missing.jwt"}, "token file is not readable"),
        ({"token": "empty.jwt"}, "token file is empty"),
        ({"token": "blank.jwt"}, "token file is empty"),
        ({"token": "bom.jwt"}, "token file is not an ASCII JWT"),
    ],
)
def test_config_problems_name_the_path_and_key(tmp_path, overrides, problem):
    path = _write_config(tmp_path, **overrides)
    with pytest.raises(RuntimeError) as failure:
        _farm.load_config(path)
    assert str(failure.value) == f"farm config {path}: {problem}"


def test_config_without_a_token_is_refused_before_any_connection(tmp_path):
    path = _write_config(tmp_path)
    config = json.loads(path.read_text(encoding="utf-8"))
    del config["token"]
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(RuntimeError, match=r"token must be a non-empty string$"):
        _farm.load_config(path)


@pytest.mark.parametrize(
    ("text", "problem"),
    [("[1, 2]", "expected a JSON object"), ("{not json", "invalid JSON")],
)
def test_config_must_be_a_json_object(tmp_path, text, problem):
    path = tmp_path / "config.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(RuntimeError, match=rf"^farm config .*config\.json: {problem}"):
        _farm.load_config(path)


def test_missing_config_points_at_credentials_issue(tmp_path):
    path = tmp_path / "absent.json"
    with pytest.raises(RuntimeError) as failure:
        _farm.load_config(path)
    assert str(failure.value) == (
        f"farm config {path}: not found; run `farm.py credentials issue` first"
    )


@pytest.mark.parametrize(
    "admission",
    [
        None,
        "",
        "{not json",
        "null",
        "true",
        "42",
        '"part:pen_rod"',
        '{"part:pen_rod": true}',
        "[]",
        '["part:other"]',
        '["part:pen_rod:child"]',
        '["part:*"]',
        '["part:pen_rod", null]',
        '["part:pen_rod", 1]',
        '["part:pen_rod", true]',
        '["part:pen_rod", []]',
        '["part:pen_rod", {}]',
        '["part:pen_rod", ""]',
        '["part:pen_rod", " \\t"]',
        '[" part:pen_rod "]',
    ],
)
def test_run_leaf_without_exact_preflight_admission_is_locally_refused(
    monkeypatch, admission
):
    from temporalio.client import Client

    if admission is None:
        monkeypatch.delenv("HARMONIC_FARM_ADMITTED_LEAVES", raising=False)
    else:
        monkeypatch.setenv("HARMONIC_FARM_ADMITTED_LEAVES", admission)

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted leaf touched the farm boundary")

    for name in (
        "_dispatch",
        "_record_leaf",
        "_record_json",
        "_rpc_update",
        "_connect_client",
        "load_config",
        "submitter",
        "_required_build_id",
        "leaf_timeout_s",
        "workflow_id",
        "LeafRequest",
    ):
        monkeypatch.setattr(_farm, name, forbidden)
    monkeypatch.setattr(_farm._telemetry, "span", forbidden)
    monkeypatch.setattr(Client, "connect", forbidden)

    with pytest.raises(RuntimeError) as failure:
        _farm.run_leaf("part:pen_rod", "k" * 64)
    assert "part:pen_rod" in str(failure.value)
    assert "lacks preflight admission" in str(failure.value)
    assert "HARMONIC_FARM_ADMITTED_LEAVES" in str(failure.value)


def test_run_leaf_reads_current_admission_in_nested_environment(monkeypatch):
    monkeypatch.setenv("HARMONIC_FARM_COMMIT", SHA)
    monkeypatch.setenv("HARMONIC_FARM_BUILD_ID", BUILD_ID)
    monkeypatch.setenv("HARMONIC_FARM_LEAF_TIMEOUT_S", "900")
    monkeypatch.setenv("HARMONIC_FARM_ADMITTED_LEAVES", '["part:pen_rod"]')
    monkeypatch.setattr(_farm, "submitter", lambda: "offline@test")
    dispatched = []
    result = _leaf_result()

    async def dispatch(request, workflow):
        dispatched.append((request.task, workflow))
        return result

    monkeypatch.setattr(_farm, "_dispatch", dispatch)
    assert _farm.run_leaf("part:pen_rod", "k" * 64) is result
    with monkeypatch.context() as child:
        child.setenv("HARMONIC_FARM_ADMITTED_LEAVES", '["check:math"]')
        with pytest.raises(RuntimeError, match="lacks preflight admission"):
            _farm.run_leaf("part:pen_rod", "k" * 64)
        assert _farm.run_leaf("check:math", None) is result
    assert _farm.run_leaf("part:pen_rod", "k" * 64) is result
    assert [task for task, _ in dispatched] == [
        "part:pen_rod",
        "check:math",
        "part:pen_rod",
    ]


@pytest.fixture
def temporal_boundary(tmp_path, monkeypatch):
    """Hermetic TLS connection, coordinator updates, and exact-run result."""
    from temporalio.client import Client

    monkeypatch.setenv("SOLIDWORKS_POOL_CONFIG", str(_write_config(tmp_path)))
    monkeypatch.setenv("HARMONIC_FARM_COMMIT", SHA)
    monkeypatch.setenv(
        "HARMONIC_FARM_ADMITTED_LEAVES",
        json.dumps(["part:pen_rod", "check:math"]),
    )
    monkeypatch.delenv("HARMONIC_FARM_RUN", raising=False)
    monkeypatch.delenv("HARMONIC_FARM_RUN_DIR", raising=False)
    calls = {"connect": [], "start": [], "submit": [], "handles": [], "queries": []}
    calls["workflow_type"] = _farm.WORKFLOW_BUILD_FIFO
    outcome = {}

    class Handle:
        async def describe(self, **options):
            return SimpleNamespace(workflow_type=calls["workflow_type"])

        async def result(self, *, follow_runs):
            assert follow_runs is False, "result must not follow a replacement run"
            if isinstance(outcome["result"], BaseException):
                raise outcome["result"]
            return outcome["result"]

        async def execute_update(self, name, arg, **options):
            assert name == "submit_leaf"
            calls["submit"].append((arg, options))
            request = arg.request
            key = _farm.LeafKey(request.build_id, _farm.workflow_id(
                request.build_id, request.task, request.cache_key, request.commit,
                request.leaf_timeout_s or 900))
            return _farm.LeafStatus(key, "reserved", None, [])

        async def query(self, name, arg, **options):
            assert name == "leaf_status"
            calls["queries"].append((arg, options))
            binding = _farm.LeafBinding(arg.build_id, arg.workflow_id, "exact-run")
            return _farm.LeafStatus(arg, "bound", binding, [])

    class FakeClient:
        async def start_workflow(self, workflow, **options):
            assert workflow == _farm.WORKFLOW_BUILD_FIFO, "producer must never start a leaf"
            calls["start"].append((workflow, options))
            return Handle()

        def get_workflow_handle(self, workflow_id, **options):
            calls["handles"].append((workflow_id, options))
            return Handle()

    async def connect(target_host, **options):
        calls["connect"].append((target_host, options))
        return FakeClient()

    monkeypatch.setattr(Client, "connect", connect)

    def resolve(result):
        outcome["result"] = result

    return calls, resolve


def test_run_leaf_rejects_wrong_type_before_submission_or_request_record(
    temporal_boundary, tmp_path, monkeypatch
):
    calls, resolve = temporal_boundary
    # A usable protocol-7 result cannot make an old coordinator type safe.
    resolve(_leaf_result())
    calls["workflow_type"] = "BuildFifo"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(run_dir))

    with pytest.raises(RuntimeError) as failure:
        _farm.run_leaf("part:pen_rod", "k" * 64)

    message = str(failure.value)
    assert f"expected workflow type {_farm.WORKFLOW_BUILD_FIFO!r}" in message
    assert "found 'BuildFifo'" in message
    assert "coordinated producer/pool/worker cutover" in message
    assert calls["submit"] == []
    assert calls["queries"] == []
    assert list(run_dir.iterdir()) == []


def test_workflow_id_is_logged_before_acceptance_and_attachment_before_wait(
    tmp_path, monkeypatch
):
    from temporalio.client import Client

    monkeypatch.setenv("SOLIDWORKS_POOL_CONFIG", str(_write_config(tmp_path)))
    records = []
    monkeypatch.setattr(
        _farm._telemetry,
        "info",
        lambda message, **fields: records.append(("info", message, fields)),
    )
    monkeypatch.setattr(
        _farm._telemetry,
        "event",
        lambda name, **fields: records.append(("event", name, fields)),
    )
    request = _farm.LeafRequest(
        farm_protocol_version=PROTOCOL,
        commit=SHA,
        task="part:pen_rod",
        cache_key="k" * 64,
        traceparent=None,
        submitter="test@submitter",
        build_id=BUILD_ID,
    )
    wf_id = f"leaf:{BUILD_ID}:part:pen_rod:" + "k" * 64 + ":900s"
    cancellations = []

    async def exercise():
        submit_entered = asyncio.Event()
        release_submit = asyncio.Event()
        result_entered = asyncio.Event()
        release_result = asyncio.Event()

        class Handle:
            async def describe(self, **options):
                return SimpleNamespace(workflow_type=_farm.WORKFLOW_BUILD_FIFO)

            async def execute_update(self, name, arg, **options):
                assert name == "submit_leaf"
                submit_entered.set()
                await release_submit.wait()
                return _farm.LeafStatus(_farm.LeafKey(BUILD_ID, wf_id), "reserved", None, [])

            async def query(self, name, arg, **options):
                return _farm.LeafStatus(arg, "bound", _farm.LeafBinding(BUILD_ID, wf_id, "exact-run"), [])

            async def result(self, *, follow_runs):
                assert follow_runs is False
                result_entered.set()
                await release_result.wait()
                return _leaf_result()

            async def cancel(self):
                cancellations.append("cancel")

        class FakeClient:
            async def start_workflow(self, *_args, **_kwargs):
                assert _args == (_farm.WORKFLOW_BUILD_FIFO,)
                return Handle()

            def get_workflow_handle(self, workflow_id, **options):
                if workflow_id == wf_id:
                    assert options == {"run_id": "exact-run", "result_type": _farm.LeafResult}
                return Handle()

        async def connect(*_args, **_kwargs):
            return FakeClient()

        monkeypatch.setattr(Client, "connect", connect)
        dispatch = asyncio.create_task(_farm._dispatch(request, wf_id))
        await submit_entered.wait()
        assert records == [
            (
                "info",
                f"Farm workflow requested: {wf_id}",
                {"workflow_id": wf_id, "task": request.task, "commit": SHA, "build_id": BUILD_ID},
            )
        ]

        release_submit.set()
        await result_entered.wait()
        identity = {"workflow_id": wf_id, "task": request.task, "commit": SHA, "build_id": BUILD_ID}
        assert records == [
            ("info", f"Farm workflow requested: {wf_id}", identity),
            ("info", f"Farm workflow attached: {wf_id}", identity),
            ("event", "farm.attached", identity),
        ]

        dispatch.cancel()
        with pytest.raises(asyncio.CancelledError):
            await dispatch

    asyncio.run(exercise())
    assert cancellations == []


def test_run_leaf_submits_to_coordinator_and_waits_exact_binding(temporal_boundary):

    calls, resolve = temporal_boundary
    resolve(_leaf_result(worker_id="sw-02@7", attempt=2))

    result = _farm.run_leaf("part:pen_rod", "k" * 64)

    assert result == _leaf_result(worker_id="sw-02@7", attempt=2)
    [(host, connect)] = calls["connect"]
    assert host == "farm.example.invalid:7233"
    assert connect["namespace"] == "solidworks"
    assert connect["identity"] == _farm.submitter()
    assert connect["tls"].domain == "farm.example.invalid"
    assert connect["tls"].server_root_ca_cert == b"-----BEGIN ca.pem-----\n"
    assert connect["tls"].client_cert == b"-----BEGIN client.pem-----\n"
    assert connect["tls"].client_private_key == b"-----BEGIN client-key.pem-----\n"
    assert connect["api_key"] == TOKEN, "the JWT is sent as Authorization: Bearer"

    [(submission, update_options)] = calls["submit"]
    request = submission.request
    assert submission.farm_run is None
    assert request == _farm.LeafRequest(
        farm_protocol_version=PROTOCOL,
        commit=SHA,
        task="part:pen_rod",
        cache_key="k" * 64,
        traceparent=request.traceparent,
        submitter=_farm.submitter(),
        build_id=BUILD_ID,
        leaf_timeout_s=None,
    )
    assert request.traceparent is None or request.traceparent.startswith("00-")
    assert calls["handles"][-1] == (
        f"leaf:{BUILD_ID}:part:pen_rod:" + "k" * 64 + ":900s",
        {"run_id": "exact-run", "result_type": _farm.LeafResult},
    )
    assert calls["handles"][0] == ("solidworks-build-fifo-7", {})
    assert calls["queries"]
    assert update_options["id"]


@pytest.mark.parametrize("same_build", [False, True], ids=["separate-builds", "same-build"])
def test_concurrent_identical_leaves_have_build_scoped_identity(
    temporal_boundary, monkeypatch, same_build
):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    other_build_id = BUILD_ID if same_build else "20261010T190001.000000Z-" + "d" * 32
    build_ids = (BUILD_ID, other_build_id)
    current_build = threading.local()
    monkeypatch.setattr(_farm, "_required_build_id", lambda: current_build.build_id)
    submitted = threading.Barrier(2)
    original_update = _farm._rpc_update
    bindings = {}
    lock = threading.Lock()

    async def concurrent_update(handle, name, arg, result_type, operation):
        assert name == "submit_leaf"
        status = await original_update(handle, name, arg, result_type, operation)
        with lock:
            bindings.setdefault(
                status.key,
                _farm.LeafBinding(
                    status.key.build_id, status.key.workflow_id, f"exact-run-{len(bindings)}"
                ),
            )
        submitted.wait(timeout=5)
        return status

    async def exact_binding(handle, name, key, result_type):
        assert name == "leaf_status"
        with lock:
            binding = bindings[key]
        return _farm.LeafStatus(key, "bound", binding, [])

    monkeypatch.setattr(_farm, "_rpc_update", concurrent_update)
    monkeypatch.setattr(_farm, "_rpc_query", exact_binding)

    def run(build_id):
        current_build.build_id = build_id
        return _farm.run_leaf("part:pen_rod", "k" * 64)

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(run, build_ids))

    assert results == [_leaf_result(), _leaf_result()]
    assert len(calls["submit"]) == 2
    assert {submission.request.build_id for submission, _options in calls["submit"]} == set(build_ids)
    expected_ids = {
        f"leaf:{build_id}:part:pen_rod:" + "k" * 64 + ":900s"
        for build_id in build_ids
    }
    attached = [(workflow_id, options) for workflow_id, options in calls["handles"]
                if workflow_id != "solidworks-build-fifo-7"]
    assert len(attached) == 2
    assert {workflow_id for workflow_id, _options in attached} == expected_ids
    assert len(bindings) == (1 if same_build else 2)
    assert len({options["id"] for _submission, options in calls["submit"]}) == len(bindings)
    assert len({options["run_id"] for _workflow_id, options in attached}) == len(bindings)
    for binding in bindings.values():
        assert (binding.workflow_id, {
            "run_id": binding.run_id, "result_type": _farm.LeafResult,
        }) in attached


def test_ready_leaf_is_submitted_with_zero_reserved_capacity(
    temporal_boundary, monkeypatch
):
    from temporalio.client import Client

    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setattr(_farm, "FIFO_HEARTBEAT_INTERVAL_S", 0.01)
    monkeypatch.setattr(_farm, "STATUS_POLL_INTERVAL_S", 0.002)
    monkeypatch.setattr(_farm, "FIFO_RPC_TIMEOUT_S", 0.5)
    interrupts = []
    monkeypatch.setattr(_farm._thread, "interrupt_main", lambda: interrupts.append("interrupt"))
    heartbeat = threading.Event()
    updates = []
    fake_connect = Client.connect

    def status(build_id, *, closed=False):
        return _farm.BuildStatus(
            build_id=build_id,
            fifo_ordinal=2,
            producer_state="closed" if closed else "open",
            ownership_state="waiting",
            lease_deadline=(datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
            outstanding_leaf_count=0,
            unconfirmed_attempt_count=0,
            reserved_capacity=0,
            occupied_capacity=0,
        )

    async def guarded_connect(*args, **kwargs):
        client = await fake_connect(*args, **kwargs)
        coordinator = client.get_workflow_handle("solidworks-build-fifo-7")
        submit = coordinator.execute_update
        query_leaf = coordinator.query

        async def execute_update(name, arg, **options):
            updates.append((name, arg))
            if name == "register_build":
                assert isinstance(arg, _farm.RegisterBuild)
                return status(arg.build_id)
            if name == "heartbeat_build":
                assert isinstance(arg, _farm.HeartbeatBuild)
                heartbeat.set()
                return status(arg.build_id)
            if name == "close_build":
                assert isinstance(arg, _farm.CloseBuild)
                return status(arg.build_id, closed=True)
            assert name == "submit_leaf", "producer must not start or grant a leaf"
            assert any(method == "register_build" for method, _arg in updates)
            return await submit(name, arg, **options)

        async def query(name, arg, **options):
            assert name == "leaf_status", "scheduler must not wait for build capacity or ownership"
            # Waiting for a leaf binding must not stop the independent lease thread.
            deadline = asyncio.get_running_loop().time() + 0.25
            while not heartbeat.is_set():
                assert asyncio.get_running_loop().time() < deadline, "producer stopped renewing"
                await asyncio.sleep(0.002)
            return await query_leaf(name, arg, **options)

        coordinator.execute_update = execute_update
        coordinator.query = query
        get_handle = client.get_workflow_handle
        client.get_workflow_handle = lambda workflow_id, **options: (
            coordinator if workflow_id == "solidworks-build-fifo-7"
            else get_handle(workflow_id, **options)
        )
        return client

    monkeypatch.setattr(Client, "connect", guarded_connect)
    # Bypass the autouse fake context to exercise registration and renewal.
    ownership = _farm._ProducerBuild(DISPLAY_NAME)
    with ownership:
        assert _farm.run_leaf("part:pen_rod", "k" * 64) == _leaf_result()
        ownership.finish(True)

    assert heartbeat.is_set()
    assert interrupts == []
    assert len(calls["submit"]) == 1
    submission, _options = calls["submit"][0]
    assert submission.request.build_id == ownership.build_id
    assert calls["handles"][-1] == (
        f"leaf:{ownership.build_id}:part:pen_rod:" + "k" * 64 + ":900s",
        {"run_id": "exact-run", "result_type": _farm.LeafResult},
    )
    assert [arg.reason for method, arg in updates if method == "close_build"] == ["finished"]
    assert os.environ["HARMONIC_FARM_BUILD_ID"] == BUILD_ID


def test_a_launcher_run_is_supplied_to_coordinator(temporal_boundary, monkeypatch):
    # The coordinator, not the producer, owns creator memo and leaf startup.
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setenv("HARMONIC_FARM_RUN", "20260929T000000000Z-abc")

    _farm.run_leaf("part:pen_rod", "k" * 64)

    [(submission, _options)] = calls["submit"]
    assert submission.farm_run == "20260929T000000000Z-abc"
    assert submission.request.build_id == BUILD_ID


@pytest.mark.parametrize("label", [None, "", " \t", "x" * 161,
    pytest.param("\U0001f680" * 161, id="supplementary161"),
    pytest.param("\u03a9" * 80 + "\U0001f680" * 81, id="mixed161"),
    "a\tb", "a\0b", "a\x01b", "a\x1fb", "a\x7fb", "a\rb", "a\nb", "a\u0085b", "a\u2028b", "a\u2029b", "a\u202eb", "a\ud800b", "a\udfffb"])
def test_invalid_dispatch_display_name_has_no_side_effects(
    temporal_boundary, tmp_path, monkeypatch, label
):
    calls, _resolve = temporal_boundary
    if label is None:
        monkeypatch.delenv("HARMONIC_FARM_DISPLAY_NAME", raising=False)
    elif "\0" in label or any(0xD800 <= ord(char) <= 0xDFFF for char in label):
        get = os.environ.get
        monkeypatch.setattr(os.environ, "get", lambda key, default=None: label if key == "HARMONIC_FARM_DISPLAY_NAME" else get(key, default))
    else:
        monkeypatch.setenv("HARMONIC_FARM_DISPLAY_NAME", label)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(run_dir))
    monkeypatch.setattr(_farm, "load_config", lambda *args, **kwargs: pytest.fail("config before valid label"))
    with pytest.raises(RuntimeError, match="HARMONIC_FARM_DISPLAY_NAME"):
        _farm.run_leaf("part:pen_rod", "k" * 64)
    assert calls["connect"] == []
    assert calls["start"] == []
    assert list(run_dir.iterdir()) == []


@pytest.mark.parametrize("label", ["x", "x" * 160,
    pytest.param("\U0001f680" * 160, id="supplementary160"),
    pytest.param("\u03a9" * 80 + "\U0001f680" * 80, id="mixed160"),
    "  Review Ω: gear train  ", "Review \U0001f680: gear train", "مراجعة שלום", "Review 👩\u200d🔧: gear\u200ctrain", "-review", "--executor"])
def test_dispatch_preserves_valid_display_name(temporal_boundary, monkeypatch, label):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setenv("HARMONIC_FARM_DISPLAY_NAME", label)
    _farm.run_leaf("part:pen_rod", "k" * 64)
    [(submission, _options)] = calls["submit"]
    assert submission.request.task == "part:pen_rod"
    assert submission.request.cache_key == "k" * 64
    assert calls["handles"][-1][0] == f"leaf:{BUILD_ID}:part:pen_rod:" + "k" * 64 + ":900s"


def test_a_launcher_run_names_each_workflow_before_creating_it(
    temporal_boundary, tmp_path, monkeypatch
):
    # farm_build.py cancel reads these to reconcile every reservation.
    from temporalio.client import Client

    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(run_dir))
    fake_connect = Client.connect
    named_at_start = []

    async def observing_connect(*args, **kwargs):
        client = await fake_connect(*args, **kwargs)
        handle = client.get_workflow_handle("solidworks-build-fifo-7")
        submit = handle.execute_update

        async def execute_update(*update_args, **update_options):
            named_at_start.extend(
                json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((run_dir / "leaves").iterdir())
            )
            return await submit(*update_args, **update_options)

        handle.execute_update = execute_update
        get_handle = client.get_workflow_handle
        client.get_workflow_handle = lambda workflow_id, **options: (
            handle if workflow_id == "solidworks-build-fifo-7" else get_handle(workflow_id, **options)
        )
        return client

    monkeypatch.setattr(Client, "connect", observing_connect)

    _farm.run_leaf("part:pen_rod", "k" * 64)

    wf_id = f"leaf:{BUILD_ID}:part:pen_rod:" + "k" * 64 + ":900s"
    assert named_at_start == [{
        "task": "part:pen_rod", "workflow_id": wf_id,
        "build_id": BUILD_ID, "farm_run": None,
        "refresh_reason": None, "state": "requested",
    }]
    assert len(calls["submit"]) == 1


def test_a_request_that_cannot_be_named_is_never_dispatched(
    temporal_boundary, tmp_path, monkeypatch
):
    # An unnamed workflow could outlive farm_build.py cancel.
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(tmp_path / "absent"))

    with pytest.raises(FileNotFoundError):
        _farm.run_leaf("part:pen_rod", "k" * 64)

    assert calls["submit"] == []


def test_a_keyless_leaf_uses_the_commit_in_its_workflow_identity(temporal_boundary):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())

    _farm.run_leaf("check:math", None)

    [(submission, _options)] = calls["submit"]
    assert submission.request.commit == SHA
    assert calls["handles"][-1][0] == f"leaf:{BUILD_ID}:check:math:{SHA[:16]}:900s"


def test_a_run_can_raise_the_per_leaf_budget(temporal_boundary, monkeypatch):
    # A cold closure run needs more than the control plane's default budget; a
    # warm run must not pay for it, so the budget travels with the leaf.
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setenv("HARMONIC_FARM_LEAF_TIMEOUT_S", "5400")

    _farm.run_leaf("part:pen_rod", "k" * 64)

    [(submission, _options)] = calls["submit"]
    assert submission.request.leaf_timeout_s == 5400
    # The timeout remains part of canonical leaf identity.
    assert calls["handles"][-1][0].endswith(":5400s")


def test_uncertain_submission_preserves_request_for_reconciliation(
    temporal_boundary, tmp_path, monkeypatch
):
    calls, _resolve = temporal_boundary
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(run_dir))
    original = _farm._rpc_update

    async def uncertain(handle, name, arg, result_type, operation):
        if name == "submit_leaf":
            raise TimeoutError("response lost after possible acceptance")
        return await original(handle, name, arg, result_type, operation)

    monkeypatch.setattr(_farm, "_rpc_update", uncertain)
    with pytest.raises(TimeoutError, match="possible acceptance"):
        _farm.run_leaf("part:pen_rod", "k" * 64)
    records = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (run_dir / "leaves").iterdir()
    ]
    assert records == [{
        "task": "part:pen_rod",
        "workflow_id": f"leaf:{BUILD_ID}:part:pen_rod:" + "k" * 64 + ":900s",
        "build_id": BUILD_ID,
        "farm_run": None,
        "refresh_reason": None,
        "state": "requested",
    }]
    assert calls["handles"][-1] == ("solidworks-build-fifo-7", {})


def test_dispatch_without_build_ownership_never_connects(temporal_boundary, monkeypatch):
    calls, _resolve = temporal_boundary
    monkeypatch.delenv("HARMONIC_FARM_BUILD_ID")
    with pytest.raises(_farm.BuildOwnershipError, match="parent build ownership"):
        _farm.run_leaf("part:pen_rod", "k" * 64)
    assert calls["connect"] == []
    assert calls["submit"] == []


def test_an_unreadable_budget_stops_the_run_instead_of_dispatching(
    temporal_boundary, monkeypatch
):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setenv("HARMONIC_FARM_LEAF_TIMEOUT_S", "90m")

    with pytest.raises(RuntimeError) as failure:
        _farm.run_leaf("part:pen_rod", "k" * 64)

    assert "HARMONIC_FARM_LEAF_TIMEOUT_S" in str(failure.value)
    assert calls["start"] == []


def test_only_a_cancelled_workflow_becomes_a_cancelled_result(temporal_boundary):
    from temporalio.client import WorkflowFailureError
    from temporalio.exceptions import ApplicationError, CancelledError

    calls, resolve = temporal_boundary

    resolve(WorkflowFailureError(cause=CancelledError("cancelled by operator")))
    cancelled = _farm.run_leaf("part:pen_rod", "k" * 64)
    assert cancelled.state == "failed"
    assert cancelled.failure_category == "cancelled"
    assert cancelled.cache_present is False

    resolve(WorkflowFailureError(cause=ApplicationError("workflow timed out")))
    with pytest.raises(WorkflowFailureError) as failure:
        _farm.run_leaf("part:pen_rod", "k" * 64)
    assert isinstance(failure.value.cause, ApplicationError)


@pytest.mark.parametrize("foreign", ["build", "workflow", "empty-run"])
def test_foreign_binding_fails_closed_before_result(
    temporal_boundary, monkeypatch, foreign
):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())

    async def query(handle, name, key, result_type):
        binding = _farm.LeafBinding(
            "foreign" if foreign == "build" else key.build_id,
            "foreign" if foreign == "workflow" else key.workflow_id,
            "" if foreign == "empty-run" else "exact-run",
        )
        return _farm.LeafStatus(key, "bound", binding, [])

    monkeypatch.setattr(_farm, "_rpc_query", query)
    monkeypatch.setattr(_farm, "STATUS_POLL_INTERVAL_S", 0)
    with pytest.raises(_farm.BuildOwnershipError, match="foreign leaf binding"):
        _farm.run_leaf("part:pen_rod", "k" * 64)
    assert calls["handles"] == [("solidworks-build-fifo-7", {})]


def test_mismatched_child_build_id_is_refused_before_connection(
    temporal_boundary, monkeypatch
):
    calls, _resolve = temporal_boundary
    request = _farm.LeafRequest(
        farm_protocol_version=PROTOCOL, commit=SHA, task="part:pen_rod",
        cache_key="k" * 64, traceparent=None, submitter="child",
        build_id="foreign",
    )
    with pytest.raises(_farm.BuildOwnershipError, match="does not match"):
        asyncio.run(_farm._dispatch(request, "leaf:foreign:part:pen_rod:" + "k" * 64 + ":900s"))
    assert calls["connect"] == []


@pytest.mark.parametrize(
    ("state", "error_code", "bound"),
    [
        ("recovery_required", "fifo_start_failed", False),
        ("recovery_required", "fifo_grant_failed", True),
        ("recovery_required", "fifo_observation_failed", True),
        ("bound", "fifo_observation_failed", True),
    ],
)
def test_reservation_recovery_failure_stops_dispatch_before_attaching(
    temporal_boundary, monkeypatch, state, error_code, bound
):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())

    async def query(handle, name, key, result_type):
        binding = _farm.LeafBinding(key.build_id, key.workflow_id, "exact-run") if bound else None
        return _farm.LeafStatus(
            key, state, binding, [], error_code, "exact history needs operator evidence"
        )

    monkeypatch.setattr(_farm, "_rpc_query", query)
    with pytest.raises(_farm.BuildOwnershipError, match=f"operator recovery \\[{error_code}\\]"):
        _farm.run_leaf("part:pen_rod", "k" * 64)

    assert len(calls["submit"]) == 1
    assert calls["handles"] == [("solidworks-build-fifo-7", {})]


@pytest.mark.parametrize("state", ["missing_closed", "drained"])
def test_settled_unbound_reply_cannot_be_used_as_a_leaf_result(
    temporal_boundary, monkeypatch, state
):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())

    async def query(handle, name, key, result_type):
        return _farm.LeafStatus(key, state, None, [])

    monkeypatch.setattr(_farm, "_rpc_query", query)
    with pytest.raises(_farm.BuildOwnershipError, match="closed without a proven run binding"):
        _farm.run_leaf("part:pen_rod", "k" * 64)

    assert calls["handles"] == [("solidworks-build-fifo-7", {})]


@pytest.mark.parametrize("reason", [
    None, "", " \t", "x" * 161, "a\nb", "a\tb", "a\0b", "a\u0085b",
    "a\u2028b", "a\u2029b", "a\u061cb", "a\u200eb", "a\u202eb", "a\u2066b",
    "a\ud800b",
])
def test_refresh_reason_is_required_before_any_graph_work(monkeypatch, capsys, reason):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setattr(
        build, "_executing_command", lambda *_a: pytest.fail("parsed command before reason")
    )
    args = ["--force-cache-refresh", "part:x", "part:x"]
    if reason is not None:
        args.append(f"--force-cache-refresh-reason={reason}")
    assert build.main(args) == 2
    assert "--force-cache-refresh-reason" in capsys.readouterr().err


def test_refresh_reason_without_labels_is_rejected_before_graph_work(monkeypatch, capsys):
    monkeypatch.setattr(
        build, "_executing_command", lambda *_a: pytest.fail("parsed command before labels")
    )
    assert build.main([
        "--force-cache-refresh-reason", "Re-evaluate cached output", "part:x",
    ]) == 2
    assert "--force-cache-refresh-reason requires --force-cache-refresh labels" in (
        capsys.readouterr().err
    )


@pytest.mark.parametrize("mode", ["ro", "off"])
def test_refresh_refuses_nonwritable_cache_before_graph_work(monkeypatch, capsys, mode):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", mode)
    monkeypatch.setattr(
        build, "_executing_command", lambda *_a: pytest.fail("parsed command before mode")
    )
    assert build.main([
        "--force-cache-refresh", "part:x",
        "--force-cache-refresh-reason", "Re-evaluate", "part:x",
    ]) == 2
    assert "requires HARMONIC_REMOTE_CACHE_MODE=rw" in capsys.readouterr().err


def _refresh_namespace(monkeypatch, observed, target=None):
    import _artifact_cache

    @_artifact_cache.keyed_action
    def record():
        observed.append(json.loads(os.environ["HARMONIC_CACHE_REFRESH"]))

    def task_leaf():
        for stem in ("x", "other"):
            yield {
                "name": stem, "actions": [record],
                "targets": [str(target)] if target is not None and stem == "x" else [],
                "uptodate": [True],
            }

    return {
        "task_leaf": task_leaf,
        "task_check": lambda: {"actions": [lambda: pytest.fail("ran uncached task")]},
        "task_group": lambda: {"actions": None, "task_dep": ["leaf:x"]},
    }


@pytest.mark.parametrize(("label", "selector", "diagnostic"), [
    ("missing", "missing", "unknown task 'missing'"),
    ("check", "check", "not a remote-cache-keyed leaf"),
    ("group", "group", "not a remote-cache-keyed leaf"),
    ("leaf:other", "leaf:x", "not in the selected task closure"),
])
def test_refresh_refuses_unknown_uncached_and_unselected_labels(
    monkeypatch, capsys, label, selector, diagnostic
):
    observed = []
    namespace = _refresh_namespace(monkeypatch, observed)
    _install_real_doit(monkeypatch, namespace)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    assert build.main([
        "--force-cache-refresh", label,
        "--force-cache-refresh-reason", "Re-evaluate unchanged inputs", selector,
    ]) == 2
    assert diagnostic in capsys.readouterr().err
    assert observed == []
    assert "HARMONIC_CACHE_REFRESH" not in os.environ


@pytest.mark.parametrize("single", ["-s", "--single"])
@pytest.mark.parametrize(("selection", "expected_exit"), [
    (["group"], 2),
    (["leaf:x"], 0),
    (["group", "leaf:x"], 2),
    (["leaf:x", "group"], 0),
    (["leaf:*"], 0),
    (["leaf:*", "group"], 0),
])
def test_refresh_single_only_admits_explicitly_selected_tasks(
    monkeypatch, capsys, single, selection, expected_exit
):
    observed = []
    _install_real_doit(monkeypatch, _refresh_namespace(monkeypatch, observed))
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    reason = "Re-evaluate explicitly selected leaf"
    assert build.main([
        "--force-cache-refresh", "leaf:x",
        "--force-cache-refresh-reason", reason, single, *selection,
    ]) == expected_exit
    if expected_exit:
        assert "task 'leaf:x' is not in the selected task closure" in capsys.readouterr().err
        assert observed == []
    else:
        assert observed == [{"labels": ["leaf:x"], "reason": reason}]
    assert "HARMONIC_CACHE_REFRESH" not in os.environ


@pytest.mark.parametrize("inherited", [None, "previous carrier"])
def test_refresh_runs_fresh_targets_with_scoped_deduplicated_carrier(
    monkeypatch, tmp_path, inherited
):
    observed = []
    target = tmp_path / "fresh.out"
    target.write_text("already built", encoding="utf-8")
    namespace = _refresh_namespace(monkeypatch, observed, target)
    _install_real_doit(monkeypatch, namespace)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    if inherited is not None:
        monkeypatch.setenv("HARMONIC_CACHE_REFRESH", inherited)
    reason = "  Owner - Re-evaluate Ω 👩\u200d🔧  "
    args = [
        "--force-cache-refresh", "leaf:x,leaf:other",
        "--force-cache-refresh", "leaf:x", f"--force-cache-refresh-reason={reason}",
        "group", "leaf:other",
    ]
    # Repeat the same invocation: a successful prior refresh must not consume it.
    assert build.main(args) == 0
    assert build.main(args) == 0
    assert observed == [{"labels": ["leaf:x", "leaf:other"], "reason": reason}] * 4
    assert os.environ.get("HARMONIC_CACHE_REFRESH") == inherited


def test_refresh_farm_submitter_only_restores_after_the_worker_publishes(
    farm_part, monkeypatch
):
    dodo, script, calls, restore = farm_part
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": ["part:pen_rod"], "reason": "Re-evaluate",
    }))
    snapshots = []
    monkeypatch.setattr(
        dodo._cache, "capture_refresh", lambda *args: snapshots.append(args)
    )
    restore((True,))
    dispatched = []
    monkeypatch.setattr(
        dodo._farm, "run_leaf",
        lambda label, key: dispatched.append((label, key)) or _leaf_result(),
    )
    dodo._cached_part_action("pen_rod", script)
    assert dispatched == [("part:pen_rod", "k" * 64)]
    assert len(calls["restore"]) == 1
    assert calls["store"] == []
    assert calls["stamp"] == ["pen_rod"]
    assert snapshots == [("part:pen_rod", "k" * 64)]


def test_leaf_refresh_wire_and_durable_record_are_scoped_to_the_listed_task(
    temporal_boundary, tmp_path, monkeypatch
):
    from dataclasses import asdict

    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    monkeypatch.setenv("HARMONIC_FARM_RUN_DIR", str(run_dir))
    monkeypatch.setenv("HARMONIC_FARM_LEAF_TIMEOUT_S", "900")
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "rw")
    monkeypatch.setenv("HARMONIC_CACHE_REFRESH", json.dumps({
        "labels": ["part:pen_rod"], "reason": "Re-evaluate unchanged inputs",
    }))
    assert _farm.FARM_PROTOCOL_VERSION == 7
    _farm.run_leaf("part:pen_rod", "k" * 64)
    _farm.run_leaf("check:math", None)
    wire = [asdict(submission.request) for submission, _ in calls["submit"]]
    assert [request["refresh_reason"] for request in wire] == [
        "Re-evaluate unchanged inputs", None,
    ]
    records = {
        record["task"]: record
        for path in (run_dir / "leaves").iterdir()
        for record in [json.loads(path.read_text(encoding="utf-8"))]
    }
    assert records["part:pen_rod"]["refresh_reason"] == wire[0]["refresh_reason"]
    assert records["check:math"]["refresh_reason"] is None
    assert records["part:pen_rod"]["workflow_id"] == (
        f"leaf:{BUILD_ID}:part:pen_rod:{'k' * 64}:900s"
    )


def test_check_pytest_process_does_not_apply_its_builds_refresh_carrier(tmp_path):
    environment = dict(os.environ)
    environment["HARMONIC_REMOTE_CACHE_MODE"] = "rw"
    environment["HARMONIC_CACHE_REFRESH"] = json.dumps({
        "labels": ["part:x"], "reason": "Refresh an actual build, not test fixtures",
    })
    # This child tests root-conftest isolation, not installed third-party plugins,
    # the caller's worker pool, or the developer's live telemetry collector.
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    for endpoint in (
        "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    ):
        environment[endpoint] = ""

    # A nested session must not spend its deadline recursively pruning unrelated
    # runs. Real stale sibling directories make removal of --basetemp observable.
    ambient_temp = tmp_path / "other-pytest-sessions"
    environment["PYTEST_DEBUG_TEMPROOT"] = str(ambient_temp)
    unrelated = ambient_temp / f"pytest-of-{getpass.getuser()}"
    sentinels = []
    for number in range(4):
        session = unrelated / f"pytest-{number}"
        session.mkdir(parents=True)
        sentinel = session / "keep.txt"
        sentinel.write_text("another session's evidence", encoding="utf-8")
        sentinels.append(sentinel)

    # This normal cache test expects an empty publication to remain fail-soft.
    # Without suite isolation, the inherited request makes it raise instead.
    stdout_path = tmp_path / "nested-pytest.stdout.txt"
    stderr_path = tmp_path / "nested-pytest.stderr.txt"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    "--basetemp", str(tmp_path / "nested-pytest"),
                    "cad/scripts/test_artifact_cache.py::test_store_nothing_on_disk_logs_empty",
                ],
                cwd=REPO_ROOT,
                env=environment,
                stdout=stdout,
                stderr=stderr,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            exc.add_note(f"Retained child output: {stdout_path}; {stderr_path}")
            for path in (stdout_path, stderr_path):
                exc.add_note(
                    f"{path.name} (last 4000 characters):\n"
                    + path.read_text(encoding="utf-8", errors="replace")[-4000:]
                )
            raise
    output = (
        stdout_path.read_text(encoding="utf-8", errors="replace")
        + stderr_path.read_text(encoding="utf-8", errors="replace")
    )
    assert result.returncode == 0, output[-8000:]
    assert "1 passed" in output, output[-8000:]
    assert all(path.read_text(encoding="utf-8") == "another session's evidence" for path in sentinels)

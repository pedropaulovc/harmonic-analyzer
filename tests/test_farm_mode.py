"""Farm executor (``HARMONIC_EXECUTOR=farm``): the submitter never takes the COM
seat, never publishes, and turns a farm outcome into the task's outcome."""

import asyncio
import hashlib
import importlib.util
import inspect
import json
import multiprocessing
import os
import subprocess
import sys
import threading
import time
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path

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

_RealFarmDoitMain = build._FarmDoitMain

SHA = "c" * 40
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


_REMOVE_FAILURE_LOG_LOCK_MUTANT_ENV = "HARMONIC_TEST_REMOVE_FARM_LOG_LOCK"


def _emit_failed_log_in_process(
    output_path: str, retrieval_barrier, begin_count, both_begun, name: str
) -> None:
    """Fetch in parallel and make unlocked block emission overlap deterministically."""

    def fetch(
        _pool,
        *args,
        interpreter=None,
        stdout=subprocess.PIPE,
        stderr=None,
        timeout_s=None,
    ):
        retrieval_barrier.wait(timeout=10)
        diagnostic = f"retrieval diagnostic for {name}\n"
        if stderr is None:
            sys.stderr.write(diagnostic)
            sys.stderr.flush()
        else:
            stderr.write(diagnostic.encode())
        stdout.write(f"worker log for {name}\n".encode())
        return subprocess.CompletedProcess(args, 0)

    class CoordinatedOutput:
        def __init__(self, output):
            self.output = output

        def write(self, text):
            written = self.output.write(text)
            self.output.flush()
            if text.startswith("--- begin failed farm task log:"):
                with begin_count.get_lock():
                    begin_count.value += 1
                    position = begin_count.value
                    if position == 2:
                        both_begun.set()
                if position == 1:
                    both_begun.wait(timeout=1)
            return written

        def flush(self):
            self.output.flush()

    if os.environ.get(_REMOVE_FAILURE_LOG_LOCK_MUTANT_ENV) == "1":

        class NoOutputLock:
            def __init__(self, _path):
                pass

            def acquire(self):
                pass

            def release(self):
                pass

        _farm.FileLock = NoOutputLock

    _farm.run_pool_cli = fetch
    result = _farm.LeafResult(
        state="failed",
        exit_code=87,
        worker_id=f"worker-{name}",
        attempt=1,
        cache_present=False,
        log_blob=f"results/{name}/task.log",
        failure_category="task_failed",
        failure_message=f"{name} failed",
    )
    with Path(output_path).open("a", encoding="utf-8", buffering=1) as output:
        previous = sys.stderr
        sys.stderr = CoordinatedOutput(output)
        try:
            _farm._emit_failed_task_log(f"part:{name}", f"leaf:{name}", result)
        finally:
            sys.stderr = previous


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


ASM_BYTES = b"SLDASM restored from the farm"


@pytest.fixture
def farm_assembly(tmp_path, monkeypatch):
    """A farm-mode ``assembly:pen`` whose probe misses.

    The execution token and recipe sidecar are real files under ``tmp_path``
    and the real ``_stamp_assembly_execution`` hashes the restored .SLDASM, so
    the token's content proves the restore happened before the stamp.
    """
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    dodo = _load_dodo()
    out = tmp_path / "sldasm"
    asm = out / "pen.SLDASM"
    token = out / ".pen.execution"
    sidecar = out / ".pen.recipe.md5"
    calls: dict[str, list] = {"restore": [], "store": []}

    monkeypatch.setattr(dodo, "_recipe_files", lambda _stem: [])
    monkeypatch.setattr(dodo, "_digest_files", lambda _files: "d" * 32)
    monkeypatch.setattr(dodo, "_recipe_sidecar", lambda _stem: sidecar)
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

    files = {"asm": asm, "token": token, "sidecar": sidecar}
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
    assert files["sidecar"].read_text(encoding="utf-8") == "d" * 32 + "\n"
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
    assert not files["sidecar"].exists()
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


# --- build.py: farm preflight and argv handling ------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _fixture_namespace(executed):
    def record():
        executed.append({key: os.environ.get(key) for key in FARM_ENV})

    def task_part():
        yield {"name": "x", "actions": [record]}

    def task_assembly():
        yield {"name": "x", "actions": [record]}

    return {"task_part": task_part, "task_assembly": task_assembly}


def _install_real_doit(monkeypatch, namespace=None, *, reporter_output=None):
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
    if reporter_output is not None:
        config["GLOBAL"]["outfile"] = reporter_output

    class FixtureFarmDoit(_RealFarmDoitMain):
        def __init__(self):
            super().__init__(
                task_loader=ModuleTaskLoader(task_namespace), extra_config=config
            )

        def run(self, args):
            seen.append(list(args))
            # Exercise the real serial runner in-process while retaining the
            # wrapper's injected farm argv in ``seen``.
            serial = list(args)
            for index in range(len(serial) - 1):
                if serial[index : index + 2] == ["-n", "8"]:
                    serial[index + 1] = "0"
                    break
            return super().run(serial)

    class FixtureLocalDoit(_RealDoitMain):
        def __init__(self):
            super().__init__(
                task_loader=ModuleTaskLoader(task_namespace), extra_config=config
            )

        def run(self, args):
            seen.append(list(args))
            return super().run(args)

    monkeypatch.setattr(build, "_FarmDoitMain", FixtureFarmDoit)
    monkeypatch.setattr(build, "DoitMain", FixtureLocalDoit)
    return seen, executed


def test_farm_build_refuses_a_dirty_tree_before_contacting_the_fleet(
    tmp_path, monkeypatch, capsys
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "tracked.txt").write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "init")
    (repo / "scratch.txt").write_text("wip\n", encoding="utf-8")
    monkeypatch.setattr(build, "REPO_ROOT", repo)
    _seen, executed = _install_real_doit(monkeypatch)

    launched = []
    real_run = build.subprocess.run

    def spy(argv, **kwargs):
        launched.append(argv)
        return real_run(argv, **kwargs)

    monkeypatch.setattr(build.subprocess, "run", spy)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert capsys.readouterr().err == "farm: working tree is dirty:\n  scratch.txt\n"
    assert all(argv[0] == "git" for argv in launched)
    assert executed == []


PROTOCOL = 4
AGENT_TAG = "7" * 16


def _worker(*, protocol=PROTOCOL, fresh=True, age_s=30, worker_id="swmaker000004@4"):
    return {
        "worker_id": worker_id,
        "farm_protocol_version": protocol,
        "agent_version": AGENT_TAG,
        "observed_at": "2026-09-18T10:39:07Z",
        "age_s": age_s,
        "written_age_s": None,
        "fresh": fresh,
    }


def _agents_summary(**overrides):
    """``farm.py agents --json``: one worker freshly reporting protocol 4."""
    summary = {
        "farm_protocol_version": PROTOCOL,
        "verdict": "matched",
        "report": None,
        "fresh_within_s": 120,
        "evidence_horizon_s": 1209600,
        "listed": 1,
        "workers": [_worker()],
        "ignored": [],
        "unreadable": [],
        "mismatch": [],
    }
    summary.update(overrides)
    return json.dumps(summary) + "\n"


_UNREPORTED_BLOCK = _agents_summary(
    verdict="mismatch",
    mismatch=[{"farm_protocol_version": 3, "workers": ["swmaker000004@4"]}],
    report=None,
)


def _preflight_fakes(monkeypatch, *, agents=None, logs_help=None, git=None):
    """Fake a clean local project and the pool's protocol/capability reports."""
    stdout = {
        "status": "",
        "submodule": "",
        "rev-parse": SHA + "\n",
    }
    stdout.update(git or {})
    if agents is None:
        agents = _agents_summary()
    if logs_help is None:
        logs_help = (
            "usage: farm.py logs [-h] "
            "[--log-blob results/.../task.log] [workflow_id]\n"
        )
    launched = []

    def fake_run(argv, **kwargs):
        launched.append(argv)
        if argv[0] == "git":
            out = stdout[argv[1]]
        else:
            command = argv[-2:]
            assert command in (["agents", "--json"], ["logs", "--help"])
            out = agents if command == ["agents", "--json"] else logs_help
        if isinstance(out, BaseException):
            raise out
        return subprocess.CompletedProcess(argv, 0, out, "")

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "ro")
    monkeypatch.delenv("HARMONIC_FARM_PARALLELISM", raising=False)
    for key in FARM_ENV:
        monkeypatch.delenv(key, raising=False)
    return launched


def test_successful_preflight_stamps_only_committed_head_without_mutating_refs(
    monkeypatch, capsys
):
    launched = _preflight_fakes(monkeypatch)
    seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0

    assert seen == [["-n", "8", "assembly:x"]]
    assert executed == [
        {
            "HARMONIC_FARM_COMMIT": SHA,
            "HARMONIC_EXECUTOR": "farm",
            "HARMONIC_SW_AUTOSTART": "0",
        }
    ]
    git_commands = [argv[1] for argv in launched if argv[0] == "git"]
    assert git_commands == ["status", "submodule", "rev-parse"]
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"],
        ["logs", "--help"],
    ]
    assert capsys.readouterr().out.splitlines()[:2] == [
        "farm: protocol 4 on 1 worker(s)",
        "farm: every SolidWorks task runs on the farm (parts, assemblies, "
        "drawings, verify:*, preflight, export, package:release)",
    ]


def _sources_root(tmp_path, monkeypatch, exclude):
    """A repo root whose ``.farm-sources.json`` declares ``exclude``."""
    root = tmp_path / "root"
    root.mkdir()
    if exclude is not None:
        (root / ".farm-sources.json").write_text(
            json.dumps({"exclude_submodules": exclude}), encoding="utf-8"
        )
    monkeypatch.setattr(build, "REPO_ROOT", root)
    return root


def test_an_uninitialized_excluded_submodule_does_not_block_a_dispatch(
    tmp_path, monkeypatch
):
    _sources_root(tmp_path, monkeypatch, ["references"])
    launched = _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 0
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"],
        ["logs", "--help"],
    ]


def test_an_uninitialized_submodule_the_local_graph_reads_still_blocks(
    tmp_path, monkeypatch, capsys
):
    _sources_root(tmp_path, monkeypatch, ["references"])
    launched = _preflight_fakes(
        monkeypatch,
        git={"submodule": "-" + "b" * 40 + " SolidworksMCP-python\n"},
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert "SolidworksMCP-python" in capsys.readouterr().err
    assert all(argv[0] == "git" for argv in launched)
    assert executed == []


def test_a_modified_excluded_submodule_still_blocks(tmp_path, monkeypatch, capsys):
    _sources_root(tmp_path, monkeypatch, ["references"])
    _preflight_fakes(
        monkeypatch,
        git={"submodule": "+" + "b" * 40 + " references (heads/main)\n"},
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert capsys.readouterr().err == "farm: working tree is dirty:\n  references\n"
    assert executed == []


def test_the_exemption_follows_the_declaration_not_the_submodule(
    tmp_path, monkeypatch, capsys
):
    _sources_root(tmp_path, monkeypatch, ["SolidworksMCP-python"])
    launched = _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert "references" in capsys.readouterr().err
    assert all(argv[0] == "git" for argv in launched)
    assert executed == []


def test_a_trailing_slash_declares_the_same_submodule(tmp_path, monkeypatch):
    _sources_root(tmp_path, monkeypatch, ["references/"])
    _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 0


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        '["references"]',
        '{"exclude_submodules": "references"}',
        '{"exclude_submodules": [3]}',
    ],
)
def test_a_malformed_declaration_stops_the_run_here(
    tmp_path, monkeypatch, capsys, content
):
    root = _sources_root(tmp_path, monkeypatch, [])
    (root / ".farm-sources.json").write_text(content, encoding="utf-8")
    launched = _preflight_fakes(monkeypatch)
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert ".farm-sources.json" in capsys.readouterr().err
    assert all(argv[0] == "git" for argv in launched)
    assert executed == []


def test_a_repo_declaring_no_exclusions_keeps_refusing_every_submodule(
    tmp_path, monkeypatch, capsys
):
    _sources_root(tmp_path, monkeypatch, None)
    _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert "references" in capsys.readouterr().err
    assert executed == []


def test_explicit_local_executor_overrides_an_inherited_farm_environment(monkeypatch):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    monkeypatch.setattr(
        build, "_farm_preflight", lambda: pytest.fail("preflight ran in local mode")
    )
    seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "local", "part:x"]) == 0
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
    ("agents", "message"),
    [
        (
            FileNotFoundError(2, "No such file", "uv"),
            "farm: agents could not start (uv): [Errno 2] No such file: 'uv'",
        ),
        (
            "reading seat reports\nnot json at all\n",
            "farm: agents printed no JSON summary; last line: not json at all",
        ),
        (
            _agents_summary(farm_protocol_version="4"),
            "farm: agents summary farm_protocol_version is not an integer: '4'",
        ),
        (
            _agents_summary(farm_protocol_version=3),
            "farm: pool CLI supports farm protocol 3, but this client requires 4",
        ),
        (
            _agents_summary(workers={"swmaker000004@4": "ready"}),
            "farm: agents summary workers is not a list: "
            + _agents_summary(workers={"swmaker000004@4": "ready"}).strip()[:200],
        ),
        (
            _agents_summary(fresh_within_s="120"),
            "farm: agents summary fresh_within_s is not an integer: '120'",
        ),
        (
            _agents_summary(evidence_horizon_s=1209600.0),
            "farm: agents summary evidence_horizon_s is not an integer: 1209600.0",
        ),
        (
            _agents_summary(ignored=None),
            "farm: agents summary ignored is not a list: "
            + _agents_summary(ignored=None).strip()[:200],
        ),
        (
            _UNREPORTED_BLOCK,
            "farm: agents returned verdict 'mismatch' without a report: "
            + _UNREPORTED_BLOCK.strip()[:200],
        ),
    ],
)
def test_preflight_protocol_faults_exit_2(agents, message, monkeypatch, capsys):
    _preflight_fakes(monkeypatch, agents=agents)
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == message + "\n"
    assert executed == []
    assert os.environ["HARMONIC_EXECUTOR"] == "farm"
    assert os.environ.get("HARMONIC_FARM_COMMIT") is None
    assert os.environ.get("HARMONIC_SW_AUTOSTART") is None


def test_protocol_four_cli_without_exact_log_capability_stops_before_actions(
    monkeypatch, capsys
):
    launched = _preflight_fakes(
        monkeypatch,
        logs_help="usage: farm.py logs [-h] [workflow_id]\n",
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == (
        "farm: pool CLI does not support exact failed-task log retrieval "
        "(--log-blob). Update SOLIDWORKS_POOL_HOME to a solidworks-pool "
        "checkout whose farm.py supports 'logs <workflow-id> --log-blob "
        "<results/.../task.log>'.\n"
    )
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"],
        ["logs", "--help"],
    ]
    assert executed == []
    assert os.environ.get("HARMONIC_FARM_COMMIT") is None
    assert os.environ.get("HARMONIC_SW_AUTOSTART") is None


def test_an_unknown_fleet_verdict_blocks_with_the_invalid_token(
    monkeypatch, capsys
):
    _preflight_fakes(
        monkeypatch, agents=_agents_summary(verdict="probably-fine")
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    error = capsys.readouterr().err
    assert error.startswith("farm:")
    assert "verdict" in error
    assert "probably-fine" in error
    assert executed == []
    assert os.environ["HARMONIC_EXECUTOR"] == "farm"
    assert os.environ.get("HARMONIC_FARM_COMMIT") is None
    assert os.environ.get("HARMONIC_SW_AUTOSTART") is None


def test_an_incompatible_fleet_stops_before_actions(monkeypatch, capsys):
    report = (
        "farm protocol 4 is required, but the fleet reports:\n"
        "  protocol 3: swmaker000004@4 (3h 0m ago)\n"
        "Deploy a protocol-compatible agent."
    )
    launched = _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            verdict="mismatch",
            workers=[_worker(protocol=3, fresh=False, age_s=10800)],
            mismatch=[
                {
                    "farm_protocol_version": 3,
                    "workers": ["swmaker000004@4"],
                }
            ],
            report=report,
        ),
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == f"farm: {report}\n"
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"]
    ]
    assert executed == []
    assert os.environ["HARMONIC_EXECUTOR"] == "farm"
    assert os.environ.get("HARMONIC_FARM_COMMIT") is None
    assert os.environ.get("HARMONIC_SW_AUTOSTART") is None


def test_an_unreadable_fleet_stops_like_a_protocol_mismatch(monkeypatch, capsys):
    report = (
        "1 worker(s) published a seat report without a readable farm protocol:\n"
        "  swmaker000004@4: invalid_report:seat report fields are wrong\n"
        "Deploy a protocol-compatible agent."
    )
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            verdict="unreadable",
            workers=[],
            listed=1,
            unreadable=[
                {
                    "worker_id": "swmaker000004@4",
                    "evidence": "invalid_report:seat report fields are wrong",
                }
            ],
            report=report,
        ),
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == f"farm: {report}\n"
    assert executed == []


def test_current_compatible_worker_allows_an_aged_retired_unreadable_report(
    monkeypatch, capsys
):
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            ignored=[
                {
                    "worker_id": "retired@1",
                    "farm_protocol_version": None,
                    "evidence": "invalid_report:missing farm_protocol_version",
                    "written_age_s": 1555200,
                    "fresh": False,
                }
            ]
        ),
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    assert executed
    assert "protocol 4" in capsys.readouterr().out.splitlines()[0]


def test_a_sleeping_compatible_fleet_says_so(monkeypatch, capsys):
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            workers=[_worker(fresh=False, age_s=21600)],
        ),
    )
    _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    status = capsys.readouterr().out.splitlines()[0]
    assert "protocol 4" in status
    assert "no worker has reported within 120s" in status
    assert "last report of 1 worker(s)" in status
    assert "supports it" in status


def test_a_fleet_that_never_reported_says_compatibility_is_unconfirmed(
    monkeypatch, capsys
):
    _preflight_fakes(
        monkeypatch, agents=_agents_summary(verdict="unverified", workers=[], listed=0)
    )
    _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    status = capsys.readouterr().out.splitlines()[0]
    assert "protocol 4" in status
    assert "no worker has ever reported" in status
    assert "unconfirmed" in status


def test_aged_out_compatible_reports_are_not_called_silence(monkeypatch, capsys):
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            verdict="unverified",
            workers=[],
            listed=2,
            ignored=[
                _worker(
                    fresh=False,
                    age_s=1555200,
                    worker_id=f"swmaker00000{instance}@{instance}",
                )
                for instance in (4, 5)
            ],
        ),
    )
    _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    status = capsys.readouterr().out.splitlines()[0]
    assert "protocol 4" in status
    assert "2 worker(s)" in status
    assert "more than 14d ago" in status
    assert "too old to prove the fleet is up" in status
    assert "never reported" not in status


@pytest.mark.parametrize(
    ("advertised", "omit_protocol", "diagnostic"),
    [
        (3, False, "protocol 3"),
        (None, True, "protocol unreadable"),
        (None, False, "protocol unreadable"),
        ("4", False, "protocol unreadable"),
        (True, False, "protocol unreadable"),
    ],
)
def test_an_aged_out_incompatible_or_unreadable_report_stops_the_run(
    advertised, omit_protocol, diagnostic, monkeypatch, capsys
):
    stale_report = _worker(
        protocol=advertised,
        fresh=False,
        age_s=1555200,
        worker_id="swmaker000004@4",
    )
    if omit_protocol:
        stale_report.pop("farm_protocol_version")
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            verdict="unverified",
            workers=[],
            listed=2,
            ignored=[
                stale_report,
                _worker(
                    fresh=False,
                    age_s=1555200,
                    worker_id="swmaker000005@5",
                ),
            ],
        ),
    )
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert executed == []
    error = capsys.readouterr().err
    assert "swmaker000004@4" in error
    assert diagnostic in error


@pytest.mark.parametrize(
    "selection",
    [
        ["part:arbor-pedestal"],
        ["part:x", "part:arbor-pedestal"],
    ],
)
def test_invalid_farm_selection_stops_before_preflight_or_actions(
    selection, monkeypatch, capsys
):
    from doit.dependency import Dependency

    preflights = []
    closes = []
    close = Dependency.close

    def record_close(manager):
        closes.append(manager)
        close(manager)

    monkeypatch.setattr(Dependency, "close", record_close)
    monkeypatch.setattr(build, "_farm_preflight", lambda: preflights.append(1))
    _seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", *selection]) == 3

    assert "part:arbor-pedestal" in capsys.readouterr().err
    assert preflights == []
    assert executed == []
    assert len(closes) == 1


def test_selection_validation_preserves_named_defaults_and_positional_args(
    monkeypatch
):
    observed = []

    def capture_configured(value):
        observed.append(("configured", value))

    def capture_release(channel, relargs):
        observed.append(("release", channel, relargs))

    def task_configured():
        return {
            "actions": [capture_configured],
            "params": [
                {
                    "name": "value",
                    "long": "value",
                    "default": "default-value",
                }
            ],
        }

    def task_release():
        return {
            "actions": [capture_release],
            "params": [
                {
                    "name": "channel",
                    "long": "channel",
                    "default": "stable",
                }
            ],
            "pos_arg": "relargs",
        }

    _preflight_fakes(monkeypatch)
    _install_real_doit(
        monkeypatch,
        {"task_configured": task_configured, "task_release": task_release},
    )

    assert (
        build.main(
            [
                "--executor",
                "farm",
                "configured",
                "--value",
                "requested",
                "release",
                "--",
                "v22",
                "--draft",
            ]
        )
        == 0
    )
    assert observed == [
        ("configured", "requested"),
        ("release", "stable", ["v22", "--draft"]),
    ]


def test_farm_selection_accepts_a_target_path_without_mutating_the_real_task(
    tmp_path, monkeypatch
):
    target = tmp_path / "out" / "artifact.bin"
    observed = []

    def task_artifact():
        return {
            "actions": [lambda: observed.append("artifact")],
            "targets": [str(target)],
        }

    _preflight_fakes(monkeypatch)
    _install_real_doit(monkeypatch, {"task_artifact": task_artifact})

    assert build.main(["--executor", "farm", str(target)]) == 0
    assert observed == ["artifact"]


def test_invalid_strace_selection_never_reaches_preflight(monkeypatch, capsys):
    preflights = []
    monkeypatch.setattr(build, "_farm_preflight", lambda: preflights.append(1))
    _seen, executed = _install_real_doit(monkeypatch)

    assert (
        build.main(["--executor", "farm", "strace", "part:arbor-pedestal"]) == 3
    )
    assert "part:arbor-pedestal" in capsys.readouterr().err
    assert preflights == []
    assert executed == []


def test_farm_command_wrappers_preserve_native_execute_signatures():
    from doit.cmd_run import Run
    from doit.cmd_strace import Strace

    for command_class in (Run, Strace):
        wrapped = build._farm_command(command_class)
        assert wrapped.get_name() == command_class.get_name()
        assert inspect.signature(wrapped._execute) == inspect.signature(
            command_class._execute
        )


@pytest.mark.parametrize(
    ("given", "expected", "runs"),
    [
        (["assembly:x"], ["-n", "8", "assembly:x"], True),
        (["run", "assembly:x"], ["run", "-n", "8", "assembly:x"], True),
        (["-n", "2", "assembly:x"], ["-n", "2", "assembly:x"], True),
        (["run", "-n", "2", "x"], ["run", "-n", "2", "x"], True),
        (["run", "--process=3", "part:y"], ["run", "--process=3", "part:y"], True),
        (["list"], ["list"], False),
        ([], ["-n", "8"], True),
        (["--help"], ["--help"], False),
        (["-h"], ["-h"], False),
        (["--version"], ["--version"], False),
        (["-f", "dodo.py", "list"], ["-f", "dodo.py", "list"], False),
        (["-f", "dodo.py", "part:x"], ["-f", "dodo.py", "-n", "8", "part:x"], True),
        (["-fdodo.py", "run", "part:x"], ["-fdodo.py", "run", "-n", "8", "part:x"], True),
        (["--file=dodo.py", "-k", "--help"], ["--file=dodo.py", "-k", "--help"], False),
        (["-d", ".", "clean"], ["-d", ".", "clean"], False),
        # doit's loader options are getopt: grouped shorts, unique long prefixes
        (["-kf", "dodo.py", "-h"], ["-kf", "dodo.py", "-h"], False),
        (["-kf", "dodo.py", "part:x"], ["-kf", "dodo.py", "-n", "8", "part:x"], True),
        (["--fi=dodo.py", "list"], ["--fi=dodo.py", "list"], False),
        # a loader parse error hands the whole argv to run, as doit does
        (["-f", "dodo.py", "-a", "x"], ["-n", "8", "-f", "dodo.py", "-a", "x"], True),
        # ``name=value`` command-line variables are dropped before the subcommand
        (["profile=ci", "list"], ["profile=ci", "list"], False),
        (["profile=ci", "run", "x"], ["profile=ci", "run", "-n", "8", "x"], True),
        (["profile=ci", "part:x"], ["-n", "8", "profile=ci", "part:x"], True),
        (["profile=ci", "-h"], ["profile=ci", "-h"], False),
        # a ``--`` the loader getopt swallowed still has to follow ``-n``
        (["--", "part:x"], ["-n", "8", "--", "part:x"], True),
        (["-f", "--", "x"], ["-f", "--", "-n", "8", "x"], True),
        # doit has no per-command help: its parser rejects these and exits 3
        # before any task, so no preflight and the argv passes untouched
        (["run", "--help"], ["run", "--help"], False),
        (["run", "-h"], ["run", "-h"], False),
        (["strace", "--help"], ["strace", "--help"], False),
        (["-f", "dodo.py", "--version"], ["-f", "dodo.py", "--version"], False),
        (["-n", "abc", "x"], ["-n", "abc", "x"], False),
        # ...and only its parser knows a help-looking token from an option
        # value (``-r --help`` is an unknown reporter; ``-o --help`` a file
        # name) or a task name after ``--``
        (["run", "-r", "--help", "x"], ["run", "-r", "--help", "x"], False),
        (["run", "-o", "--help", "x"], ["run", "-n", "8", "-o", "--help", "x"], True),
        (["run", "--", "--help"], ["run", "-n", "8", "--", "--help"], True),
    ],
)
def test_farm_runs_fan_out_unless_the_caller_chose(given, expected, runs, monkeypatch):
    monkeypatch.delenv("HARMONIC_FARM_PARALLELISM", raising=False)
    executing = build._executing_command(list(given), _RealDoitMain())
    assert (executing is not None) is runs
    result = (
        given
        if executing is None
        else build._with_farm_parallelism(list(given), *executing)
    )
    assert result == expected


def test_every_task_executing_command_gets_the_preflight_and_only_run_fans_out(
    monkeypatch,
):
    """``strace`` is a ``Run`` subclass (``execute_tasks``): its task action runs,
    so farm preflight still precedes it. It traces one task and has no ``-n``,
    so the fan-out stays run-only. ``list`` executes nothing."""
    preflights = []
    monkeypatch.setattr(build, "_farm_preflight", lambda: preflights.append(1))
    monkeypatch.delenv("HARMONIC_FARM_PARALLELISM", raising=False)
    seen, _executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "strace", "part:x"]) == 0
    assert len(preflights) == 1
    assert build.main(["--executor", "farm", "list"]) == 0
    assert len(preflights) == 1
    assert build.main(["--executor", "farm", "run", "part:x"]) == 0
    assert len(preflights) == 2

    assert seen == [
        ["strace", "part:x"],
        ["list"],
        ["run", "-n", "8", "part:x"],
    ]


def test_help_and_non_run_commands_skip_the_preflight(monkeypatch, capsys):
    def no_git(argv, **kwargs):
        pytest.fail(f"preflight launched {argv}")

    monkeypatch.setattr(build.subprocess, "run", no_git)
    seen, executed = _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "--help"]) == 0
    assert build.main(["--executor", "farm", "-kf", "dodo.py", "-h"]) == 0
    assert build.main(["--executor", "farm", "help", "run"]) == 0
    assert build.main(["--executor", "farm", "profile=ci", "list"]) == 0
    assert build.main(["--executor", "farm", "run", "--help"]) == 3

    # A leading --help/-h, grouped loader options included, is the wrapper's
    # (doit itself rejects ``-h``): its own options and the farm defaults, then
    # doit's command list. The doit-owned routes (``help run``, ``list``, with
    # or without a command-line variable) pass through unchanged, and so does
    # ``run --help``, which doit's own parser rejects before any task.
    assert seen == [
        ["--help"],
        ["--help"],
        ["help", "run"],
        ["profile=ci", "list"],
        ["run", "--help"],
    ]
    assert executed == []
    out = capsys.readouterr().out
    for flag in ("--verbosity", "--executor", "--leaf-timeout"):
        assert flag in out
    # Both knobs a no-flag farm run would silently inherit are named.
    assert "HARMONIC_FARM_PARALLELISM" in out
    assert "HARMONIC_FARM_LEAF_TIMEOUT_S" in out


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


@pytest.fixture
def temporal_boundary(tmp_path, monkeypatch):
    """Fake ``Client.connect``/``start_workflow``/``handle.result``; returns the
    recorded calls and a setter for what ``handle.result()`` does."""
    from temporalio.client import Client

    monkeypatch.setenv("SOLIDWORKS_POOL_CONFIG", str(_write_config(tmp_path)))
    monkeypatch.setenv("HARMONIC_FARM_COMMIT", SHA)
    calls: dict = {"connect": [], "start": []}
    outcome: dict = {}

    class Handle:
        async def result(self):
            if isinstance(outcome["result"], BaseException):
                raise outcome["result"]
            return outcome["result"]

    class FakeClient:
        async def start_workflow(self, workflow, arg, **options):
            calls["start"].append((workflow, arg, options))
            return Handle()

    async def connect(target_host, **options):
        calls["connect"].append((target_host, options))
        return FakeClient()

    monkeypatch.setattr(Client, "connect", connect)

    def resolve(result):
        outcome["result"] = result

    return calls, resolve


def test_exact_failed_leaf_log_is_captured_without_replacing_python_action_error(
    temporal_boundary, monkeypatch, capsys
):
    _calls, resolve = temporal_boundary
    failed = _leaf_result(**_FAILED_LEAF)
    resolve(failed)
    _preflight_fakes(monkeypatch)
    dodo = _load_dodo()
    expected_wf_id = "leaf:part:x:" + "k" * 64 + ":900s"

    def pool_cli(
        _pool,
        *args,
        interpreter=None,
        stdout=subprocess.PIPE,
        stderr=None,
        timeout_s=None,
    ):
        if args == ("agents", "--json"):
            return subprocess.CompletedProcess(args, 0, _agents_summary(), "")
        if args == ("logs", "--help"):
            return subprocess.CompletedProcess(args, 0, "--log-blob\n", "")
        if args[-2:] == ("--log-blob", failed.log_blob):
            stdout.write("failed execution log: café\n".encode())
            stdout.write(b"failed log with damaged UTF-8: \xff\n")
        else:
            stdout.write(b"newer execution under the same workflow ID\n")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(_farm, "run_pool_cli", pool_cli)

    def task_part():
        yield {
            "name": "x",
            "actions": [(dodo._farm_build, ["part:x", "k" * 64, []])],
            "verbosity": 2,
        }

    reporter_output = StringIO()
    _install_real_doit(
        monkeypatch, {"task_part": task_part}, reporter_output=reporter_output
    )
    exit_code = build.main(["--executor", "farm", "part:x"])

    captured = capsys.readouterr()
    log_output = captured.err
    report_output = reporter_output.getvalue()
    line_prefix = "[farm task=part:x] "
    begin = log_output.index("--- begin failed farm task log:")
    worker_log = log_output.index(line_prefix + "failed execution log: café")
    replacement = log_output.index(
        line_prefix + "failed log with damaged UTF-8: \ufffd"
    )
    end = log_output.index("--- end failed farm task log:")
    assert begin < worker_log < replacement < end
    assert (
        f"task=part:x workflow={expected_wf_id} log_blob={failed.log_blob}"
        in log_output
    )
    assert (
        "part:x failed on sw-01@3 [task_failed] exit 87: "
        "SolidWorks connect timed out"
    ) in report_output
    assert exit_code == 2


@pytest.mark.parametrize(
    ("chunks", "expected_lines"),
    [
        (
            [b"phase1\rphase2\n"],
            ["phase1", "phase2"],
        ),
        (
            [b"caf\xc3", b"\xa9\r", b"\nnext\r", b"last"],
            ["café", "next", "last"],
        ),
    ],
)
def test_spooled_log_normalizes_newlines_across_binary_read_boundaries(
    monkeypatch, chunks, expected_lines
):
    class ChunkedSpool(BytesIO):
        def __init__(self, parts):
            super().__init__(b"".join(parts))
            self.read_sizes = [len(part) for part in parts]
            self.read1_calls = 0

        def read1(self, size=-1):
            self.read1_calls += 1
            if not self.read_sizes:
                return b""
            part_size = self.read_sizes.pop(0)
            if size >= 0:
                part_size = min(part_size, size)
            return super().read(part_size)

    prefix = "[farm task=part:pen_rod] "
    spool = ChunkedSpool(chunks)
    output = StringIO()
    monkeypatch.setattr(sys, "stderr", output)

    _farm._write_spooled_utf8(spool, prefix)

    assert output.getvalue() == "".join(
        prefix + line + "\n" for line in expected_lines
    )
    assert spool.read1_calls >= len(chunks)
    assert not spool.closed


def test_retrieved_lines_remain_attributed_when_normal_output_interleaves(
    tmp_path, monkeypatch
):
    task = "part:pen_rod"
    workflow_id = "leaf:part:pen_rod:key:900s"
    failed = _leaf_result(**_FAILED_LEAF)
    line_prefix = f"[farm task={task}] "
    output = StringIO()
    retrieved_line_written = threading.Event()
    normal_line_written = threading.Event()

    class InterleavingOutput:
        def write(self, text):
            written = output.write(text)
            if text == line_prefix + "farm.py diagnostic\n":
                retrieved_line_written.set()
                if not normal_line_written.wait(timeout=3):
                    raise AssertionError("normal build writer did not interleave")
            return written

        def flush(self):
            output.flush()

    def normal_writer():
        if retrieved_line_written.wait(timeout=3):
            output.write("normal build output\n")
            normal_line_written.set()

    def retrieve(
        _pool,
        *args,
        interpreter=None,
        stdout=subprocess.PIPE,
        stderr=None,
        timeout_s=None,
    ):
        stderr.write(b"farm.py diagnostic\n")
        stdout.write(b"worker log line\n")
        stdout.write(b"unterminated worker line")
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setenv(
        "HARMONIC_FARM_LOG_LOCK", str(tmp_path / "farm-build-output.lock")
    )
    monkeypatch.setattr(_farm, "pool_home", lambda: tmp_path / "pool")
    monkeypatch.setattr(_farm, "run_pool_cli", retrieve)
    monkeypatch.setattr(sys, "stderr", InterleavingOutput())
    writer = threading.Thread(target=normal_writer)
    writer.start()
    try:
        _farm._emit_failed_task_log(task, workflow_id, failed)
    finally:
        writer.join(timeout=5)

    assert not writer.is_alive()
    lines = output.getvalue().splitlines()
    assert lines[0] == (
        "--- begin failed farm task log: "
        f"task={task} workflow={workflow_id} log_blob={failed.log_blob} ---"
    )
    assert line_prefix + "farm.py diagnostic" in lines
    assert "normal build output" in lines
    assert line_prefix + "worker log line" in lines
    assert line_prefix + "unterminated worker line" in lines
    assert not {
        "farm.py diagnostic",
        "worker log line",
        "unterminated worker line",
    }.intersection(lines)
    assert lines[-1] == (
        "--- end failed farm task log: "
        f"task={task} workflow={workflow_id} log_blob={failed.log_blob} ---"
    )
    assert lines.index(line_prefix + "farm.py diagnostic") < lines.index(
        "normal build output"
    )
    assert lines.index("normal build output") < lines.index(
        line_prefix + "worker log line"
    )


def test_parallel_failed_leaf_logs_are_emitted_as_complete_blocks(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "build-stderr.log"
    output_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(
        "HARMONIC_FARM_LOG_LOCK", str(tmp_path / "farm-build-output.lock")
    )
    context = multiprocessing.get_context("spawn")
    retrieval_barrier = context.Barrier(2)
    begin_count = context.Value("i", 0)
    both_begun = context.Event()
    processes = [
        context.Process(
            target=_emit_failed_log_in_process,
            args=(
                str(output_path),
                retrieval_barrier,
                begin_count,
                both_begun,
                name,
            ),
        )
        for name in ("a", "b")
    ]
    try:
        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=15)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    assert [process.exitcode for process in processes] == [0, 0]

    def block(name):
        task = f"part:{name}"
        identity = (
            f"task={task} workflow=leaf:{name} "
            f"log_blob=results/{name}/task.log"
        )
        prefix = f"[farm task={task}] "
        return (
            f"--- begin failed farm task log: {identity} ---\n"
            f"{prefix}retrieval diagnostic for {name}\n"
            f"{prefix}worker log for {name}\n"
            "\n"
            f"--- end failed farm task log: {identity} ---\n"
        )

    output = output_path.read_text(encoding="utf-8")
    assert output in (block("a") + block("b"), block("b") + block("a"))


@pytest.mark.parametrize(
    ("diagnostic_outcome", "reason", "warning"),
    [
        (
            subprocess.TimeoutExpired(["python", "farm.py", "logs"], 30),
            "retrieval_timeout",
            "task log retrieval timed out after 30s",
        ),
        (
            OSError("operator CLI unavailable"),
            "retrieval_start_error",
            "task log retrieval could not start",
        ),
        (
            subprocess.CompletedProcess(["python", "farm.py", "logs"], 19),
            "retrieval_exit",
            "task log retrieval exited 19",
        ),
    ],
)
def test_log_retrieval_faults_preserve_the_failed_leaf_result(
    temporal_boundary,
    monkeypatch,
    capsys,
    diagnostic_outcome,
    reason,
    warning,
):
    _calls, resolve = temporal_boundary
    failed = _leaf_result(**_FAILED_LEAF)
    resolve(failed)
    records = []

    def diagnose(*_args, **_kwargs):
        if isinstance(diagnostic_outcome, BaseException):
            raise diagnostic_outcome
        return diagnostic_outcome

    monkeypatch.setattr(_farm, "run_pool_cli", diagnose)
    monkeypatch.setattr(
        _farm._telemetry,
        "warn",
        lambda message, **fields: records.append((message, fields)),
    )

    assert _farm.run_leaf("part:pen_rod", "k" * 64) is failed
    assert len(records) == 1
    message, fields = records[0]
    assert warning in message
    assert fields == {
        "reason": reason,
        "task": "part:pen_rod",
        "workflow_id": "leaf:part:pen_rod:" + "k" * 64 + ":900s",
        "log_blob": failed.log_blob,
        "worker_id": "sw-01@3",
        "attempt": 1,
    }
    error = capsys.readouterr().err
    assert warning not in error
    assert "--- end failed farm task log:" in error


def test_failed_leaf_without_a_log_blob_reports_absence_without_a_cli_call(
    temporal_boundary, monkeypatch, capsys
):
    _calls, resolve = temporal_boundary
    failed = _leaf_result(**_FAILED_LEAF, log_blob=None)
    resolve(failed)
    records = []
    monkeypatch.setattr(
        _farm,
        "run_pool_cli",
        lambda *_args, **_kwargs: pytest.fail("queried logs without a log blob"),
    )
    monkeypatch.setattr(
        _farm._telemetry,
        "warn",
        lambda message, **fields: records.append((message, fields)),
    )

    assert _farm.run_leaf("part:pen_rod", "k" * 64) is failed
    assert len(records) == 1
    message, fields = records[0]
    assert "no task log was published" in message
    assert fields["reason"] == "log_blob_absent"
    assert fields["task"] == "part:pen_rod"
    assert fields["workflow_id"] == "leaf:part:pen_rod:" + "k" * 64 + ":900s"
    assert fields["log_blob"] == ""
    error = capsys.readouterr().err
    assert "no task log was published" not in error
    assert "--- end failed farm task log:" in error


@pytest.mark.parametrize(
    ("configured_environment", "environment"),
    [(None, Path(".venv")), ("pool-python", Path("pool-python"))],
)
def test_pool_python_resolves_relative_pool_and_environment_from_repo_root(
    monkeypatch, configured_environment, environment
):
    if configured_environment is None:
        monkeypatch.delenv("UV_PROJECT_ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", configured_environment)
    executable = (
        Path("Scripts") / "python.exe"
        if os.name == "nt"
        else Path("bin/python")
    )

    assert _farm._pool_python(Path("relative-pool")) == (
        (_farm.REPO_ROOT / "relative-pool").resolve() / environment / executable
    )


def test_bounded_log_retrieval_kills_the_direct_pool_process(
    tmp_path, monkeypatch
):
    pool = tmp_path / "pool"
    pool.mkdir()
    started = tmp_path / "started.txt"
    survived = tmp_path / "survived.txt"
    (pool / "farm.py").write_text(
        "import time\n"
        "from pathlib import Path\n"
        f"Path({str(started)!r}).write_text('started', encoding='utf-8')\n"
        "time.sleep(1.5)\n"
        f"Path({str(survived)!r}).write_text('survived', encoding='utf-8')\n",
        encoding="utf-8",
    )
    environment = Path(sys.executable).parents[1]
    monkeypatch.setenv("UV_PROJECT_ENVIRONMENT", str(environment))
    monkeypatch.setenv(
        "HARMONIC_FARM_LOG_LOCK", str(tmp_path / "farm-build-output.lock")
    )
    monkeypatch.setattr(_farm, "pool_home", lambda: pool)
    monkeypatch.setattr(_farm, "FAILED_LOG_TIMEOUT_S", 0.5)
    records = []
    monkeypatch.setattr(
        _farm._telemetry,
        "warn",
        lambda message, **fields: records.append((message, fields)),
    )

    _farm._emit_failed_task_log(
        "part:pen_rod",
        "leaf:part:pen_rod:key:900s",
        _leaf_result(**_FAILED_LEAF),
    )

    assert started.read_text(encoding="utf-8") == "started"
    time.sleep(1.2)
    assert not survived.exists(), "timed-out farm.py survived to finish its work"
    assert [fields["reason"] for _message, fields in records] == [
        "retrieval_timeout"
    ]


def test_successful_leaf_emits_no_task_log_diagnostic(
    temporal_boundary, monkeypatch, capsys
):
    _calls, resolve = temporal_boundary
    succeeded = _leaf_result()
    resolve(succeeded)
    monkeypatch.setattr(
        _farm,
        "run_pool_cli",
        lambda *_args, **_kwargs: pytest.fail("queried logs for a successful leaf"),
    )

    assert _farm.run_leaf("part:pen_rod", "k" * 64) is succeeded
    assert capsys.readouterr().err == ""


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
        farm_protocol_version=4,
        commit=SHA,
        task="part:pen_rod",
        cache_key="k" * 64,
        traceparent=None,
        submitter="test@submitter",
    )
    wf_id = "leaf:part:pen_rod:" + "k" * 64 + ":900s"
    cancellations = []

    async def exercise():
        start_entered = asyncio.Event()
        release_start = asyncio.Event()
        result_entered = asyncio.Event()
        release_result = asyncio.Event()

        class Handle:
            async def result(self):
                result_entered.set()
                await release_result.wait()
                return _leaf_result()

            async def cancel(self):
                cancellations.append("cancel")

        class FakeClient:
            async def start_workflow(self, *_args, **_kwargs):
                start_entered.set()
                await release_start.wait()
                return Handle()

        async def connect(*_args, **_kwargs):
            return FakeClient()

        monkeypatch.setattr(Client, "connect", connect)
        dispatch = asyncio.create_task(_farm._dispatch(request, wf_id))
        await start_entered.wait()
        assert records == [
            (
                "info",
                f"Farm workflow requested: {wf_id}",
                {"workflow_id": wf_id, "task": request.task, "commit": SHA},
            )
        ]

        release_start.set()
        await result_entered.wait()
        identity = {"workflow_id": wf_id, "task": request.task, "commit": SHA}
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


def test_run_leaf_starts_the_shared_workflow_with_the_contract(temporal_boundary):
    from temporalio.common import WorkflowIDConflictPolicy

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

    [(workflow, request, options)] = calls["start"]
    assert workflow == "BuildLeaf"
    assert request == _farm.LeafRequest(
        farm_protocol_version=4,
        commit=SHA,
        task="part:pen_rod",
        cache_key="k" * 64,
        traceparent=request.traceparent,
        submitter=_farm.submitter(),
        leaf_timeout_s=None,
    )
    assert request.traceparent is None or request.traceparent.startswith("00-")
    assert options["id"] == "leaf:part:pen_rod:" + "k" * 64 + ":900s"
    assert options["task_queue"] == "solidworks-control"
    assert options["id_conflict_policy"] is WorkflowIDConflictPolicy.USE_EXISTING
    assert options["execution_timeout"] == timedelta(hours=8)
    assert options["result_type"] is _farm.LeafResult


def test_a_keyless_leaf_uses_the_commit_in_its_workflow_identity(temporal_boundary):
    calls, resolve = temporal_boundary
    resolve(_leaf_result())

    _farm.run_leaf("check:math", None)

    [(_, request, options)] = calls["start"]
    assert request.commit == SHA
    assert options["id"] == f"leaf:check:math:{SHA[:16]}:900s"


def test_a_run_can_raise_the_per_leaf_budget(temporal_boundary, monkeypatch):
    # A cold closure run needs more than the control plane's default budget; a
    # warm run must not pay for it, so the budget travels with the leaf.
    calls, resolve = temporal_boundary
    resolve(_leaf_result())
    monkeypatch.setenv("HARMONIC_FARM_LEAF_TIMEOUT_S", "5400")

    _farm.run_leaf("part:pen_rod", "k" * 64)

    [(_, request, options)] = calls["start"]
    assert request.leaf_timeout_s == 5400
    # A raised budget cannot attach to a running 15 min execution: Temporal
    # cannot widen an existing run's timeout, so the budget is part of the id.
    assert options["id"].endswith(":5400s")


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


def test_the_build_wrapper_turns_minutes_into_the_leaf_budget(monkeypatch):
    monkeypatch.delenv("HARMONIC_FARM_LEAF_TIMEOUT_S", raising=False)
    _preflight_fakes(monkeypatch)
    _install_real_doit(monkeypatch)

    assert build.main(["--executor", "farm", "--leaf-timeout", "90", "part:x"]) == 0
    assert os.environ["HARMONIC_FARM_LEAF_TIMEOUT_S"] == "5400"
    assert _farm.leaf_timeout_s() == 5400


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

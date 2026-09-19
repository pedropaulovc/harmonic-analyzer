"""Farm executor (``HARMONIC_EXECUTOR=farm``): the submitter never takes the COM
seat, never publishes, and turns a farm outcome into the task's outcome."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from doit.doit_cmd import DoitMain as _RealDoitMain

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _farm  # noqa: E402
import build  # noqa: E402

SHA = "c" * 40
FARM_ENV = (
    "HARMONIC_FARM_COMMIT",
    "HARMONIC_EXECUTOR",
    "HARMONIC_SW_AUTOSTART",
)


def _load_dodo():
    spec = importlib.util.spec_from_file_location("dodo", REPO_ROOT / "dodo.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


class _NoDoit(_RealDoitMain):
    """A ``DoitMain`` that must never start: commands, ``execute_tasks`` and
    each command's option parser are doit's own, so the routing verdict is
    doit's, not the test's; only ``run`` is replaced."""

    def run(self, args):
        pytest.fail(f"doit ran {args}")


class _FakeDoit(_NoDoit):
    """Records the argv and the farm environment visible when doit starts."""

    seen: list = []

    def run(self, args):
        _FakeDoit.seen.append((args, {k: os.environ.get(k) for k in FARM_ENV}))
        return 0


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
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    launched = []
    real_run = build.subprocess.run

    def spy(argv, **kwargs):
        launched.append(argv)
        return real_run(argv, **kwargs)

    monkeypatch.setattr(build.subprocess, "run", spy)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert capsys.readouterr().err == "farm: working tree is dirty:\n  scratch.txt\n"
    assert all(argv[0] == "git" for argv in launched)


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


def _preflight_fakes(monkeypatch, *, agents=None, git=None):
    """Fake a clean local project and the pool's protocol report."""
    stdout = {
        "status": "",
        "submodule": "",
        "rev-parse": SHA + "\n",
    }
    stdout.update(git or {})
    if agents is None:
        agents = _agents_summary()
    launched = []

    def fake_run(argv, **kwargs):
        launched.append(argv)
        if argv[0] == "git":
            out = stdout[argv[1]]
        else:
            assert argv[-2:] == ["agents", "--json"]
            out = agents
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
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0

    assert _FakeDoit.seen == [
        (
            ["-n", "8", "assembly:x"],
            {
                "HARMONIC_FARM_COMMIT": SHA,
                "HARMONIC_EXECUTOR": "farm",
                "HARMONIC_SW_AUTOSTART": "0",
            },
        )
    ]
    git_commands = [argv[1] for argv in launched if argv[0] == "git"]
    assert git_commands == ["status", "submodule", "rev-parse"]
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"]
    ]
    assert capsys.readouterr().out == (
        "farm: protocol 4 on 1 worker(s)\n"
        "farm: every SolidWorks task runs on the farm (parts, assemblies, "
        "drawings, verify:*, preflight, export, package:release)\n"
    )


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
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "part:x"]) == 0
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"]
    ]


def test_an_uninitialized_submodule_the_local_graph_reads_still_blocks(
    tmp_path, monkeypatch, capsys
):
    _sources_root(tmp_path, monkeypatch, ["references"])
    launched = _preflight_fakes(
        monkeypatch,
        git={"submodule": "-" + "b" * 40 + " SolidworksMCP-python\n"},
    )
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert "SolidworksMCP-python" in capsys.readouterr().err
    assert all(argv[0] == "git" for argv in launched)


def test_a_modified_excluded_submodule_still_blocks(tmp_path, monkeypatch, capsys):
    _sources_root(tmp_path, monkeypatch, ["references"])
    _preflight_fakes(
        monkeypatch,
        git={"submodule": "+" + "b" * 40 + " references (heads/main)\n"},
    )
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert capsys.readouterr().err == "farm: working tree is dirty:\n  references\n"


def test_the_exemption_follows_the_declaration_not_the_submodule(
    tmp_path, monkeypatch, capsys
):
    _sources_root(tmp_path, monkeypatch, ["SolidworksMCP-python"])
    launched = _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert "references" in capsys.readouterr().err
    assert all(argv[0] == "git" for argv in launched)


def test_a_trailing_slash_declares_the_same_submodule(tmp_path, monkeypatch):
    _sources_root(tmp_path, monkeypatch, ["references/"])
    _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

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
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert ".farm-sources.json" in capsys.readouterr().err
    assert all(argv[0] == "git" for argv in launched)


def test_a_repo_declaring_no_exclusions_keeps_refusing_every_submodule(
    tmp_path, monkeypatch, capsys
):
    _sources_root(tmp_path, monkeypatch, None)
    _preflight_fakes(
        monkeypatch, git={"submodule": "-" + "b" * 40 + " references\n"}
    )
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "part:x"]) == 2
    assert "references" in capsys.readouterr().err


def test_explicit_local_executor_overrides_an_inherited_farm_environment(monkeypatch):
    monkeypatch.setenv("HARMONIC_EXECUTOR", "farm")
    monkeypatch.setattr(
        build, "_farm_preflight", lambda: pytest.fail("preflight ran in local mode")
    )
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "local", "part:x"]) == 0
    assert _FakeDoit.seen[0][0] == ["part:x"]
    assert os.environ["HARMONIC_EXECUTOR"] == "local"
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
            _agents_summary(verdict="probably-fine"),
            "farm: agents summary verdict is not one of "
            "('mismatch', 'unreadable', 'matched', 'unverified'): 'probably-fine'",
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
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == message + "\n"
    assert all(os.environ.get(key) is None for key in FARM_ENV)


def test_an_incompatible_fleet_stops_before_doit(monkeypatch, capsys):
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
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == f"farm: {report}\n"
    assert [argv[-2:] for argv in launched if argv[0] != "git"] == [
        ["agents", "--json"]
    ]
    assert all(os.environ.get(key) is None for key in FARM_ENV)


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
    monkeypatch.setattr(build, "DoitMain", _NoDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert capsys.readouterr().err == f"farm: {report}\n"


def test_a_sleeping_compatible_fleet_says_so(monkeypatch, capsys):
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            workers=[_worker(fresh=False, age_s=21600)],
        ),
    )
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "farm: protocol 4; no worker has reported within 120s, but the last "
        "report of 1 worker(s) supports it"
    )


def test_a_fleet_that_never_reported_says_compatibility_is_unconfirmed(
    monkeypatch, capsys
):
    _preflight_fakes(
        monkeypatch, agents=_agents_summary(verdict="unverified", workers=[], listed=0)
    )
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "farm: protocol 4; no worker has ever reported, so compatibility is "
        "unconfirmed"
    )


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
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "farm: protocol 4; 2 worker(s) last reported more than 14d ago "
        "supporting it, too old to prove the fleet is up but not contradicting it"
    )


def test_an_aged_out_incompatible_report_still_stops_the_run(monkeypatch):
    _preflight_fakes(
        monkeypatch,
        agents=_agents_summary(
            verdict="unverified",
            workers=[],
            listed=2,
            ignored=[
                _worker(protocol=3, fresh=False, age_s=1555200),
                _worker(
                    fresh=False,
                    age_s=1555200,
                    worker_id="swmaker000005@5",
                ),
            ],
        ),
    )
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "assembly:x"]) == 2
    assert _FakeDoit.seen == []


def test_an_aged_out_protocol_dissent_names_the_worker():
    named = build._dissenting_workers(
        [
            {
                "worker_id": "swmaker000004@4",
                "farm_protocol_version": 3,
                "age_s": 1555200,
                "written_age_s": None,
            },
            {"worker_id": "swmaker000005@5", "farm_protocol_version": 4},
            {"worker_id": "swmaker000006@6", "farm_protocol_version": None},
            "not a report",
        ],
        PROTOCOL,
    )

    assert named == ["swmaker000004@4 (protocol 3, last seen 18d ago)"]


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
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "strace", "part:x"]) == 0
    assert len(preflights) == 1
    assert build.main(["--executor", "farm", "list"]) == 0
    assert len(preflights) == 1
    assert build.main(["--executor", "farm", "run", "part:x"]) == 0
    assert len(preflights) == 2

    assert [args for args, _env in _FakeDoit.seen] == [
        ["strace", "part:x"],
        ["list"],
        ["run", "-n", "8", "part:x"],
    ]


def test_help_and_non_run_commands_skip_the_preflight(monkeypatch, capsys):
    def no_git(argv, **kwargs):
        pytest.fail(f"preflight launched {argv}")

    monkeypatch.setattr(build.subprocess, "run", no_git)
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

    assert build.main(["--executor", "farm", "--help"]) == 0
    assert build.main(["--executor", "farm", "-kf", "dodo.py", "-h"]) == 0
    assert build.main(["--executor", "farm", "help", "run"]) == 0
    assert build.main(["--executor", "farm", "profile=ci", "list"]) == 0
    assert build.main(["--executor", "farm", "run", "--help"]) == 0

    # A leading --help/-h, grouped loader options included, is the wrapper's
    # (doit itself rejects ``-h``): its own options and the farm defaults, then
    # doit's command list. The doit-owned routes (``help run``, ``list``, with
    # or without a command-line variable) pass through unchanged, and so does
    # ``run --help``, which doit's own parser rejects before any task.
    assert [args for args, _env in _FakeDoit.seen] == [
        ["--help"],
        ["--help"],
        ["help", "run"],
        ["profile=ci", "list"],
        ["run", "--help"],
    ]
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
    _FakeDoit.seen = []
    monkeypatch.setattr(build, "DoitMain", _FakeDoit)

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

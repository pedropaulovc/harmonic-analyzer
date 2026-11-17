"""farm_build.py: launch refusals, fleet protocol gate, and the run lifecycle.

The lifecycle tests launch real detached supervisors against a throwaway Git
repository whose committed ``farm_build.py`` is a stub ``_build``: no doit
graph, no fleet, no Temporal. They prove the contracts a caller relies on --
``run`` returns once the build registers, ``watch`` exit codes, and that
``cancel`` or a dead supervisor takes the whole process tree with it.
"""

import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import farm_build  # noqa: E402

PROTOCOL = 7
windows_only = pytest.mark.skipif(
    sys.platform != "win32", reason="farm runs are Windows-only"
)


# --- fleet protocol gate -------------------------------------------------------


def _worker(*, protocol=PROTOCOL, fresh=True, age_s=30, worker_id="swmaker000004@4"):
    return {
        "worker_id": worker_id,
        "farm_protocol_version": protocol,
        "agent_version": "7" * 16,
        "observed_at": "2026-09-18T10:39:07Z",
        "age_s": age_s,
        "written_age_s": None,
        "fresh": fresh,
    }


def _agents_summary(**overrides):
    """``farm.py agents --json``: one worker freshly reporting protocol 7."""
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


def _fleet(monkeypatch, agents):
    def pool_farm(_pool, *args):
        assert args == ("agents", "--json")
        if isinstance(agents, BaseException):
            raise agents
        return subprocess.CompletedProcess(args, 0, agents, "")

    monkeypatch.setattr(farm_build, "_pool_farm", pool_farm)


@pytest.mark.parametrize(
    ("agents", "message"),
    [
        (
            farm_build.FarmPreflightError("agents could not start (uv): gone"),
            "agents could not start (uv): gone",
        ),
        ("reading seat reports\nnot json at all\n", "not json at all"),
        (
            _agents_summary(farm_protocol_version="6"),
            "pool CLI supports farm protocol '6', but this client requires 7",
        ),
        (
            _agents_summary(farm_protocol_version=3),
            "pool CLI supports farm protocol 3, but this client requires 7",
        ),
        (_agents_summary(verdict="probably-fine"), "verdict 'probably-fine'"),
        (_agents_summary(verdict="mismatch"), "verdict 'mismatch'"),
        (
            _agents_summary(verdict="mismatch", report="farm protocol 7 is required"),
            "farm protocol 7 is required",
        ),
        (
            _agents_summary(
                verdict="unreadable", workers=[], report="seat report unreadable"
            ),
            "seat report unreadable",
        ),
    ],
)
def test_fleet_faults_refuse_the_build(agents, message, monkeypatch):
    _fleet(monkeypatch, agents)
    with pytest.raises(farm_build.FarmPreflightError) as refusal:
        farm_build.require_fleet_protocol(Path("pool"), PROTOCOL)
    assert message in str(refusal.value)


@pytest.mark.parametrize("verdict", ["matched", "unverified"])
def test_compatible_or_silent_fleets_are_admitted_and_named(
    verdict, monkeypatch, capsys
):
    _fleet(monkeypatch, _agents_summary(verdict=verdict))
    farm_build.require_fleet_protocol(Path("pool"), PROTOCOL)
    assert f"fleet verdict {verdict}" in capsys.readouterr().out


def test_unadmissible_refresh_stops_before_the_fleet(monkeypatch, capsys):
    import _artifact_cache

    @_artifact_cache.keyed_action
    def leaf():
        pytest.fail("ran a task")

    monkeypatch.setattr(
        farm_build,
        "require_fleet_protocol",
        lambda *_a: pytest.fail("fleet before refresh check"),
    )
    record = {
        "targets": ["leaf:x"],
        "pool_home": "no-pool",
        "display_name": "Refresh refusal",
        "force_cache_refresh": ["leaf:other"],
        "force_cache_refresh_reason": "Re-evaluate",
    }
    namespace = {
        "task_leaf": lambda: ({"name": n, "actions": [leaf]} for n in ("x", "other"))
    }
    assert farm_build.run_farm_build(record, namespace) == 2
    assert (
        "task 'leaf:other' is not in the selected task closure"
        in capsys.readouterr().err
    )


# --- launch refusals -------------------------------------------------------------


@windows_only
@pytest.mark.parametrize(
    ("argv", "diagnostic"),
    [
        (["part:x,,part:y"], "empty component"),
        (["profile=ci"], "not doit variables"),
        (["release"], "release publishes from the owning worktree"),
        (["part:x", "--leaf-timeout", "181"], "--leaf-timeout must be 1-180"),
        (["part:x", "--display-name", "bad\nlabel"], "HARMONIC_FARM_DISPLAY_NAME"),
        (
            ["part:x", "--force-cache-refresh-reason", "Why"],
            "requires --force-cache-refresh",
        ),
        (["part:x", "--force-cache-refresh", "part:x"], "--force-cache-refresh-reason"),
        (["part:x", "--tag", "two words"], "--tag takes"),
    ],
)
def test_invalid_launch_is_refused_before_any_record(
    argv, diagnostic, tmp_path, capsys
):
    argv = list(argv)
    root = tmp_path / "runs"
    options = {"--display-name": "Refusal test", "--leaf-timeout": "5"}
    for flag in options:
        if flag in argv:
            options[flag] = argv[argv.index(flag) + 1]
            del argv[argv.index(flag) : argv.index(flag) + 2]
    flags = [item for pair in options.items() for item in pair]
    assert farm_build.main(["run", *argv, *flags, "--runs-dir", str(root)]) == 2
    assert diagnostic in capsys.readouterr().err
    assert not root.exists()


# --- the run lifecycle -------------------------------------------------------------

_STUB = textwrap.dedent('''\
    """Stub ``farm_build.py _build``: behaviour from the committed mode.txt."""
    import json, subprocess, sys, time
    from pathlib import Path

    run_dir = Path(sys.argv[2])
    mode = Path("mode.txt").read_text(encoding="utf-8").strip()
    Path("cad/out").mkdir(parents=True, exist_ok=True)
    Path("cad/out/marker.txt").write_text("built", encoding="utf-8")
    if mode == "fail":
        sys.exit(3)
    if mode == "hang":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
        (run_dir / "grandchild.json").write_text(json.dumps(child.pid), encoding="utf-8")
    (run_dir / "build.json").write_text(json.dumps({"build_id": "fake-build"}), encoding="utf-8")
    if mode == "hang":
        time.sleep(600)
''')


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def farm(tmp_path_factory):
    """A runs root, a pool home, and a locked dependency-free stub project."""
    base = tmp_path_factory.mktemp("farm")
    pool = base / "pool"
    (pool / "agent").mkdir(parents=True)
    (pool / "farm.py").write_text("", encoding="utf-8")
    (pool / "agent" / "protocol.py").write_text("", encoding="utf-8")
    project = base / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(
        '[project]\nname = "stub"\nversion = "0"\ndependencies = []\n',
        encoding="utf-8",
    )
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(
        ["uv", "lock", "--offline", "--quiet"], cwd=project, env=env, check=True
    )
    return base / "runs", pool, project


@pytest.fixture
def launch(farm, tmp_path):
    root, pool, project = farm

    def start(mode):
        origin = tmp_path / f"{mode}-origin.git"
        repo = tmp_path / f"{mode}-repo"
        subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "farm_build.py").write_text(_STUB, encoding="utf-8")
        for name in ("pyproject.toml", "uv.lock"):
            (repo / name).write_bytes((project / name).read_bytes())
        (repo / "mode.txt").write_text(mode, encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-q", "-m", mode)
        _git(repo, "remote", "add", "origin", str(origin))
        _git(repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        _git(repo, "fetch", "-q", "origin")
        root.mkdir(exist_ok=True)
        before = set(root.iterdir())
        code = farm_build.main(
            [
                "run",
                "part:x",
                "--display-name",
                f"Lifecycle {mode}",
                "--leaf-timeout",
                "5",
                "--worktree",
                str(repo),
                "--runs-dir",
                str(root),
                "--pool-home",
                str(pool),
            ]
        )
        [run_dir] = [
            path
            for path in set(root.iterdir()) - before
            if farm_build.RUN_ID_PATTERN.fullmatch(path.name)
        ]
        return code, run_dir

    return root, start


def _watch(root, run_dir):
    return farm_build.main(
        ["watch", run_dir.name, "--runs-dir", str(root), "--poll-seconds", "0.2"]
    )


def _grandchild(run_dir):
    pid = json.loads((run_dir / "grandchild.json").read_text(encoding="utf-8"))
    identity = {"pid": pid, "created": farm_build.process_identity(pid)}
    assert farm_build.process_alive(identity)
    return identity


def _died(identity):
    deadline = time.monotonic() + 30
    while farm_build.process_alive(identity):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.1)
    return True


@windows_only
def test_a_run_returns_at_registration_and_keeps_its_outputs(launch):
    root, start = launch
    code, run_dir = start("ok")
    assert code == 0
    assert _watch(root, run_dir) == 0
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "succeeded"
    assert status["snapshot_removed"] is True
    assert (run_dir / "out" / "marker.txt").read_text(encoding="utf-8") == "built"
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert not Path(record["snapshot"]).exists()


@windows_only
def test_a_build_that_stops_before_registering_returns_its_exit_code(launch):
    root, start = launch
    code, run_dir = start("fail")
    assert code == 3
    assert _watch(root, run_dir) == 20
    assert not (run_dir / "build.json").exists()


@windows_only
def test_cancel_stops_the_whole_tree_and_settles_remote_work(
    launch, monkeypatch, capsys
):
    root, start = launch
    settled = []

    async def reconcile(build_id, leaves, reason, binding_wait_s):
        settled.append((build_id, reason))
        return [], []

    monkeypatch.setattr(farm_build, "reconcile_remote", reconcile)
    code, run_dir = start("hang")
    assert code == 0
    grandchild = _grandchild(run_dir)
    assert (
        farm_build.main(
            [
                "cancel",
                run_dir.name,
                "--why",
                "test",
                "--runs-dir",
                str(root),
            ]
        )
        == 0
    )
    assert _died(grandchild)
    assert settled == [("fake-build", f"test (farm_build.py cancel {run_dir.name})")]
    assert _watch(root, run_dir) == 22
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["cancel"]["supervisor"] == "running"


@windows_only
def test_a_dead_supervisor_takes_its_tree_and_is_never_called_cancelled(
    launch, monkeypatch
):
    root, start = launch
    code, run_dir = start("hang")
    assert code == 0
    grandchild = _grandchild(run_dir)
    supervisor = json.loads((run_dir / "supervisor.json").read_text(encoding="utf-8"))
    assert farm_build._stop_process(supervisor)
    assert _died(grandchild)
    assert _watch(root, run_dir) == 21

    async def unresolved(build_id, leaves, reason, binding_wait_s):
        return [], ["leaf:x: unresolved: no exact binding"]

    monkeypatch.setattr(farm_build, "reconcile_remote", unresolved)
    cancel = ["cancel", run_dir.name, "--why", "test", "--runs-dir", str(root)]
    assert farm_build.main(cancel) == 1
    assert not (run_dir / "status.json").exists()

    async def settled(build_id, leaves, reason, binding_wait_s):
        return [], []

    monkeypatch.setattr(farm_build, "reconcile_remote", settled)
    assert farm_build.main(cancel) == 0
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "cancelled"
    assert status["cancel"]["supervisor"] == "launcher-died"
    assert os.path.isdir(run_dir / "out")

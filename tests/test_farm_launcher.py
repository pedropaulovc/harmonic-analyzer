"""Windows contract tests for the tracked, supervised farm launcher."""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="scripts/farm-run.ps1 is a Windows launcher"
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "farm-run.ps1"

# A hang guard, never a correctness budget. Every wait below ends on the event
# it is waiting for (the launcher exits, a record appears, a line reaches the
# log); this ceiling only stops a broken launcher from hanging the suite, and its
# expiry reports what was observed. The spawn chain (pwsh -> git -> cmd ->
# python) takes 0.3-3 s idle but 10-45 s on a saturated host (a bare
# `pwsh -NoProfile -Command 'exit 0'` measured 9.6 s there), so any tight
# wall-clock budget fails healthy runs.
HANG_GUARD_S = 300

T = TypeVar("T")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "protocol.file.allow=always",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


BUILD_PY = "# launcher fixture\n"


def _launcher_fixture(tmp_path: Path, *, submodules: bool = False) -> dict[str, object]:
    worktree = tmp_path / "source worktree"
    worktree.mkdir()
    (worktree / "build.py").write_text(BUILD_PY, encoding="utf-8")
    (worktree / "uv.lock").write_text("# lock fixture\n", encoding="utf-8")
    _git(worktree, "init", "-q")
    if submodules:
        # A required submodule and one the commit's .farm-sources.json excludes.
        for name in ("required lib", "excluded refs"):
            library = tmp_path / name
            library.mkdir()
            (library / "marker.txt").write_text(f"{name}\n", encoding="utf-8")
            _git(library, "init", "-q")
            _git(library, "add", "marker.txt")
            _git(library, "commit", "-q", "-m", name)
        _git(worktree, "submodule", "add", "-q", str(tmp_path / "required lib"), "lib")
        _git(
            worktree, "submodule", "add", "-q", str(tmp_path / "excluded refs"), "refs"
        )
        (worktree / ".farm-sources.json").write_text(
            '{"exclude_submodules": ["./refs/"]}\n', encoding="utf-8"
        )
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "launcher fixture")
    _git(worktree, "update-ref", "refs/remotes/origin/main", "HEAD")

    pool = tmp_path / "pool checkout"
    pool.mkdir()
    (pool / "farm.py").write_text("# launcher fixture\n", encoding="utf-8")

    log_directory = tmp_path / "external launch records"
    tools = tmp_path / "stub tools"
    tools.mkdir()
    invocation = tmp_path / "uv invocation.json"
    syncs = tmp_path / "uv syncs.jsonl"
    stub = tools / "uv_stub.py"
    stub.write_text(
        """import json
import os
import subprocess
import sys
import time
from pathlib import Path

if sys.argv[1] == "venv":
    environment = Path(sys.argv[-1])
    environment.mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("relocatable = true\\n", encoding="utf-8")
    raise SystemExit(0)

if sys.argv[1] == "sync":
    with open(os.environ["UV_STUB_SYNCS"], "a", encoding="utf-8") as syncs:
        syncs.write(
            json.dumps(
                {
                    "argv": sys.argv[1:],
                    "cwd": os.getcwd(),
                    "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV"),
                }
            )
            + "\\n"
        )
    time.sleep(float(os.environ.get("UV_STUB_SYNC_DELAY", "0")))
    (Path(os.environ["VIRTUAL_ENV"]) / "synced.txt").write_text(
        str(os.getpid()), encoding="utf-8"
    )
    raise SystemExit(int(os.environ.get("UV_STUB_SYNC_EXIT", "0")))

blocked = os.environ.get("UV_STUB_BLOCK_OUTPUTS")
if blocked:
    # Occupy this run's outputs path so the launcher cannot move cad/out there.
    for record_path in Path(blocked).glob("*.run.json"):
        run = json.loads(record_path.read_text(encoding="utf-8-sig"))
        if Path(run["snapshot"]) == Path.cwd():
            Path(run["outputs"]).mkdir()


def record(**late):
    cwd = Path.cwd()
    Path(os.environ["UV_STUB_INVOCATION"]).write_text(
        json.dumps(
            {
                "argv": sys.argv[1:],
                "cwd": str(cwd),
                "head": subprocess.run(
                    ["git", "rev-parse", "HEAD"], capture_output=True, text=True
                ).stdout.strip(),
                "environment": {
                    "SOLIDWORKS_POOL_HOME": os.environ.get("SOLIDWORKS_POOL_HOME"),
                    "HARMONIC_REMOTE_CACHE_MODE": os.environ.get("HARMONIC_REMOTE_CACHE_MODE"),
                    "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED"),
                    "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV"),
                },
                "submodule_files": {
                    name: (cwd / name / "marker.txt").exists() for name in ("lib", "refs")
                },
                "environment_synced": (
                    Path(os.environ.get("VIRTUAL_ENV", "?")) / "synced.txt"
                ).exists(),
                **late,
            }
        ),
        encoding="utf-8",
    )


record()
reports = Path("cad") / "out" / "reports"
reports.mkdir(parents=True, exist_ok=True)
(reports / "stub-output.txt").write_text("built\\n", encoding="utf-8")
time.sleep(float(os.environ.get("UV_STUB_START_DELAY", "0")))
print("uv-stdout", flush=True)
print("uv-stderr", file=sys.stderr, flush=True)
release = os.environ.get("UV_STUB_RELEASE")
if release:
    deadline = time.monotonic() + float(os.environ["UV_STUB_RELEASE_GUARD"])
    while not Path(release).exists() and time.monotonic() < deadline:
        time.sleep(0.05)
record(build_py_at_exit=Path("build.py").read_text(encoding="utf-8"))
raise SystemExit(int(os.environ.get("UV_STUB_EXIT", "0")))
""",
        encoding="utf-8",
    )
    (tools / "uv.cmd").write_text(
        f'@echo off\r\n"{sys.executable}" "{stub}" %*\r\nexit /b %ERRORLEVEL%\r\n',
        encoding="utf-8",
    )

    pwsh = shutil.which("pwsh.exe")
    if pwsh is None:
        pytest.skip("PowerShell 7.3+ is not installed")

    environment = os.environ.copy()
    environment["PATH"] = str(tools) + os.pathsep + environment["PATH"]
    environment["UV_STUB_INVOCATION"] = str(invocation)
    environment["UV_STUB_SYNCS"] = str(syncs)
    environment["UV_STUB_EXIT"] = "0"
    environment["HARMONIC_CACHE_ACCOUNT"] = "fixture-account"
    environment.pop("HARMONIC_CACHE_CONTAINER", None)
    environment["HARMONIC_CACHE_SALT"] = "fixture-salt"
    # The fixture's submodules are local paths, which Git refuses to clone by
    # default; the launcher's own `submodule update` needs the same allowance.
    environment["GIT_CONFIG_COUNT"] = "1"
    environment["GIT_CONFIG_KEY_0"] = "protocol.file.allow"
    environment["GIT_CONFIG_VALUE_0"] = "always"

    return {
        "pwsh": pwsh,
        "worktree": worktree,
        "pool": pool,
        "log_directory": log_directory,
        "invocation": invocation,
        "syncs": syncs,
        "tools": tools,
        "environment": environment,
    }


def _command(
    fixture: dict[str, object], targets: str, *, tag: str = "test"
) -> list[str]:
    return [
        str(fixture["pwsh"]),
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(LAUNCHER),
        "-Worktree",
        str(fixture["worktree"]),
        "-PoolHome",
        str(fixture["pool"]),
        "-LogDirectory",
        str(fixture["log_directory"]),
        "-Targets",
        targets,
        "-LeafTimeout",
        "90",
        "-Tag",
        tag,
    ]


def _only(path: Path, pattern: str) -> Path:
    matches = list(path.glob(pattern))
    assert len(matches) == 1, matches
    return matches[0]


def _observed(log_directory: Path) -> str:
    if not log_directory.exists():
        return f"{log_directory} does not exist"
    names = sorted(entry.name for entry in log_directory.iterdir())
    return f"{log_directory} holds {names}"


def _run_launcher(
    fixture: dict[str, object], command: list[str], environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run the launcher to exit; only the hang guard can end the wait early."""
    try:
        return subprocess.run(
            command,
            env=environment,
            text=True,
            capture_output=True,
            timeout=HANG_GUARD_S,
        )
    except subprocess.TimeoutExpired as expired:
        raise AssertionError(
            f"launcher still running after the {HANG_GUARD_S} s hang guard; "
            f"{_observed(Path(fixture['log_directory']))}; "
            f"stdout={expired.stdout!r} stderr={expired.stderr!r}"
        ) from expired


def _record(path: Path) -> dict[str, object]:
    # The launcher renames each record into place. Right after the rename a
    # reader can briefly hit a sharing violation (EACCES) while the rename
    # handle or an on-access scanner still holds the new name; it clears on its
    # own, so retry until the record is readable. A contended 400-run loop hit
    # this once.
    deadline = time.monotonic() + HANG_GUARD_S
    while True:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.05)


def _wait_for(
    process: subprocess.Popen[str],
    probe: Callable[[], T | None],
    what: str,
    log_directory: Path,
) -> T | None:
    """Poll ``probe`` until it yields a value or the launcher exits.

    Returns ``None`` only when the launcher exited without producing it; the
    hang guard's expiry fails loud with what was observed instead.
    """
    started = time.monotonic()
    while time.monotonic() - started < HANG_GUARD_S:
        found = probe()
        if found is not None:
            return found
        if process.poll() is not None:
            return probe()
        time.sleep(0.05)
    raise AssertionError(
        f"no {what} after the {HANG_GUARD_S} s hang guard; launcher "
        f"exit={process.poll()}; {_observed(log_directory)}"
    )


def _observe_held_launch(
    process: subprocess.Popen[str],
    fixture: dict[str, object],
    release: Path,
    while_held: Callable[[dict[str, object]], None] | None = None,
) -> tuple[str, str, dict[str, object], Path]:
    """Check the live records while the stub is held, then release and reap."""
    log_directory = Path(fixture["log_directory"])
    run_paths = _wait_for(
        process,
        lambda: list(log_directory.glob("*.run.json")) or None,
        "startup record",
        log_directory,
    )
    assert run_paths is not None and len(run_paths) == 1, (
        run_paths,
        process.poll(),
        _observed(log_directory),
    )
    running = _record(run_paths[0])
    assert process.poll() is None
    assert running["state"] == "running"
    assert not Path(running["done"]).exists()

    def streamed() -> str | None:
        text = Path(running["log"]).read_text(encoding="utf-8")
        return text if "uv-stdout" in text and "uv-stderr" in text else None

    launch_log = _wait_for(
        process, streamed, "streamed child output", log_directory
    ) or Path(running["log"]).read_text(encoding="utf-8")
    assert "uv-stdout" in launch_log
    assert "uv-stderr" in launch_log
    # The stub is still held on the release file, so the launcher must still be
    # running: the log above streamed live rather than being written at exit.
    assert process.poll() is None
    assert not Path(running["done"]).exists()

    if while_held is not None:
        while_held(running)
    release.touch()
    stdout, stderr = process.communicate(timeout=HANG_GUARD_S)
    return stdout, stderr, running, run_paths[0]


# The child's first output lands a spawn chain after the startup record. The
# 6 s variant pins that the test waits for the output rather than for a fixed
# budget: the old 5 s window failed it with "assert 'uv-stdout' in ''", which is
# what a contended full-suite run hit on 82aa3330d.
@pytest.mark.parametrize("start_delay", ["0", "6"], ids=["prompt-child", "slow-child"])
def test_success_records_start_before_completion_and_preserves_native_arguments(
    tmp_path: Path, start_delay: str
) -> None:
    fixture = _launcher_fixture(tmp_path)
    release = tmp_path / "release uv stub"
    environment = dict(fixture["environment"])
    environment["UV_STUB_START_DELAY"] = start_delay
    environment["UV_STUB_RELEASE"] = str(release)
    environment["UV_STUB_RELEASE_GUARD"] = str(HANG_GUARD_S)
    command = _command(fixture, "part:pen_rod, drawing:pen", tag="spaces-ok")

    process = subprocess.Popen(
        command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr, running, run_path = _observe_held_launch(
            process, fixture, release
        )
    finally:
        release.touch()
        if process.poll() is None:
            process.kill()
            process.communicate()

    assert process.returncode == 0, (stdout, stderr)
    assert stderr == ""
    assert "uv-stdout" in stdout
    assert "uv-stderr" in stdout

    readiness = next(
        line for line in stdout.splitlines() if line.startswith("farm-launch started ")
    )
    _, _, readiness_run_id, readiness_record = readiness.split(" ", 3)
    assert readiness_run_id == running["run_id"]
    assert Path(readiness_record) == run_path
    assert run_path.name == f"{running['run_id']}.run.json"
    assert Path(running["log"]).name == f"{running['run_id']}.log"
    assert Path(running["done"]).name == f"{running['run_id']}.done"

    finished = _record(Path(running["done"]))
    assert finished["run_id"] == running["run_id"]
    assert finished["state"] == "succeeded"
    assert finished["exit_code"] == 0
    assert finished["targets"] == ["part:pen_rod", "drawing:pen"]
    assert finished["tag"] == "spaces-ok"
    assert finished["leaf_timeout_minutes"] == 90
    assert Path(finished["worktree"]) == Path(fixture["worktree"]).resolve()
    assert Path(finished["pool_home"]) == Path(fixture["pool"]).resolve()
    assert Path(finished["log"]).is_absolute()
    assert Path(finished["done"]).is_absolute()
    assert finished["cache_environment"] == {
        "HARMONIC_CACHE_ACCOUNT": "fixture-account",
        "HARMONIC_CACHE_CONTAINER": None,
        "HARMONIC_CACHE_SALT": "fixture-salt",
    }

    expected = [
        "uv",
        "run",
        "--frozen",
        "--no-sync",
        "--active",
        "python",
        "build.py",
        "--executor",
        "farm",
        "--leaf-timeout",
        "90",
        "--verbosity",
        "info",
        "--continue",
        "part:pen_rod",
        "drawing:pen",
    ]
    assert running["argv"] == expected
    invocation = json.loads(Path(fixture["invocation"]).read_text(encoding="utf-8"))
    assert invocation["argv"] == expected[1:]
    assert invocation["environment"] == {
        "SOLIDWORKS_POOL_HOME": str(Path(fixture["pool"]).resolve()),
        "HARMONIC_REMOTE_CACHE_MODE": "rw",
        "PYTHONUNBUFFERED": "1",
        "VIRTUAL_ENV": running["environment"],
    }
    assert Path(invocation["cwd"]) == Path(running["snapshot"])
    launch_log = Path(finished["log"]).read_text(encoding="utf-8")
    assert "uv-stdout" in launch_log
    assert "uv-stderr" in launch_log
    assert f"farm-launch snapshot {running['snapshot']}" in launch_log


def _held_launch(
    tmp_path: Path,
    fixture: dict[str, object],
    while_held: Callable[[dict[str, object]], None],
) -> tuple[subprocess.Popen[str], dict[str, object], dict[str, object]]:
    release = tmp_path / "release uv stub"
    environment = dict(fixture["environment"])
    environment["UV_STUB_RELEASE"] = str(release)
    environment["UV_STUB_RELEASE_GUARD"] = str(HANG_GUARD_S)
    process = subprocess.Popen(
        _command(fixture, "part:pen_rod"),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr, running, _ = _observe_held_launch(
            process, fixture, release, while_held
        )
    finally:
        release.touch()
        if process.poll() is None:
            process.kill()
            process.communicate()
    assert process.returncode == 0, (stdout, stderr)
    return process, running, _record(Path(running["done"]))


def _worktrees(repository: Path) -> list[Path]:
    listed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in listed.splitlines()
        if line.startswith("worktree ")
    ]


def test_the_build_runs_from_a_snapshot_the_caller_cannot_change(
    tmp_path: Path,
) -> None:
    """#1114: a commit or an edit in the caller's worktree mid-run never reaches
    the submitter, which builds the launch commit from its own snapshot, and the
    snapshot goes away afterwards while its outputs are kept."""
    fixture = _launcher_fixture(tmp_path)
    worktree = Path(fixture["worktree"])

    def edit_the_caller(running: dict[str, object]) -> None:
        assert Path(running["snapshot"]).resolve() in _worktrees(worktree)
        (worktree / "build.py").write_text("# committed mid-run\n", encoding="utf-8")
        _git(worktree, "commit", "-q", "-am", "mid-run commit")
        (worktree / "build.py").write_text("# edited mid-run\n", encoding="utf-8")

    _, running, finished = _held_launch(tmp_path, fixture, edit_the_caller)

    invocation = json.loads(Path(fixture["invocation"]).read_text(encoding="utf-8"))
    snapshot = Path(running["snapshot"])
    assert Path(invocation["cwd"]) == snapshot
    assert invocation["head"] == running["commit"]
    assert invocation["build_py_at_exit"] == BUILD_PY
    assert snapshot.parent == Path(running["log"]).parent / "snapshots"

    assert finished["state"] == "succeeded"
    assert finished["snapshot_removed"] is True
    assert finished["cleanup_errors"] == []
    assert not snapshot.exists()
    assert snapshot.resolve() not in _worktrees(worktree)
    assert finished["outputs_preserved"] is True
    assert Path(finished["outputs"]) == Path(running["log"]).with_suffix(".out")
    assert (Path(finished["outputs"]) / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"


def test_launches_share_one_environment_synced_once(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)

    finished = []
    for _ in range(2):
        result = _run_launcher(
            fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        finished.append(json.loads(result.stdout.splitlines()[-1]))

    first, second = finished
    assert first["environment"] == second["environment"]
    assert Path(first["environment"]).parent == (Path(first["log"]).parent / "envs")
    assert [first["environment_reused"], second["environment_reused"]] == [False, True]
    syncs = [
        json.loads(line)
        for line in Path(fixture["syncs"]).read_text(encoding="utf-8").splitlines()
    ]
    assert len(syncs) == 1, syncs
    assert syncs[0]["argv"] == ["sync", "--frozen", "--no-editable", "--active"]
    assert Path(syncs[0]["cwd"]) == Path(first["snapshot"])
    # Synced in a staging directory of its own, then published whole.
    staged = Path(syncs[0]["VIRTUAL_ENV"])
    assert staged.parent == Path(first["environment"]).parent
    assert staged.name.startswith(Path(first["environment"]).name + ".staging-")
    assert not staged.exists()
    assert sorted(p.name for p in staged.parent.iterdir()) == [
        Path(first["environment"]).name
    ]
    invocation = json.loads(Path(fixture["invocation"]).read_text(encoding="utf-8"))
    assert invocation["environment_synced"] is True


def test_concurrent_launches_publish_one_environment_and_both_build(
    tmp_path: Path,
) -> None:
    """Two launchers creating the same environment each sync privately; one
    publishes, the other adopts it, and neither touches the other's sync."""
    fixture = _launcher_fixture(tmp_path)
    processes = []
    invocations = []
    for index in range(2):
        environment = dict(fixture["environment"])
        environment["UV_STUB_SYNC_DELAY"] = "3"
        invocations.append(tmp_path / f"uv invocation {index}.json")
        environment["UV_STUB_INVOCATION"] = str(invocations[-1])
        processes.append(
            subprocess.Popen(
                _command(fixture, "part:pen_rod", tag=f"racer{index}"),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    results = [process.communicate(timeout=HANG_GUARD_S) for process in processes]

    for process, (stdout, stderr) in zip(processes, results):
        assert process.returncode == 0, (stdout, stderr)
    finished = [json.loads(stdout.splitlines()[-1]) for stdout, _ in results]
    assert finished[0]["environment"] == finished[1]["environment"]
    assert sorted(f["environment_reused"] for f in finished) == [False, True]
    syncs = Path(fixture["syncs"]).read_text(encoding="utf-8").splitlines()
    assert len({json.loads(line)["VIRTUAL_ENV"] for line in syncs}) == 2, syncs
    for invocation in invocations:
        built = json.loads(invocation.read_text(encoding="utf-8"))
        assert Path(built["environment"]["VIRTUAL_ENV"]) == Path(
            finished[0]["environment"]
        )
        assert built["environment_synced"] is True
    envs = Path(finished[0]["environment"]).parent
    assert sorted(p.name for p in envs.iterdir()) == [
        Path(finished[0]["environment"]).name
    ]


def test_a_stale_staging_directory_is_never_touched(tmp_path: Path) -> None:
    """A killed launcher can leave its uv syncing into its staging directory;
    a later launcher syncs and publishes its own instead of reusing or
    deleting that one."""
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_SYNC_EXIT"] = "5"
    failed = _run_launcher(fixture, _command(fixture, "part:pen_rod"), environment)
    assert failed.returncode == 1, (failed.stdout, failed.stderr)
    target = Path(
        _record(_only(Path(fixture["log_directory"]), "*.done"))["environment"]
    )
    orphan = target.parent / f"{target.name}.staging-0123456789ab"
    orphan.mkdir()
    (orphan / "half-synced.txt").write_text("still syncing\n", encoding="utf-8")

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    finished = json.loads(result.stdout.splitlines()[-1])
    assert Path(finished["environment"]) == target
    assert finished["environment_reused"] is False
    assert (target / "synced.txt").exists()
    assert (orphan / "half-synced.txt").read_text(encoding="utf-8") == "still syncing\n"


def test_outputs_that_cannot_be_kept_fail_the_run_and_keep_the_snapshot(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_BLOCK_OUTPUTS"] = str(fixture["log_directory"])

    result = _run_launcher(fixture, _command(fixture, "part:pen_rod"), environment)

    # The build itself exited 0, but its outputs are not where a finished
    # run's record says they are.
    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "the snapshot is kept" in result.stderr
    finished = json.loads(result.stdout.splitlines()[-1])
    assert finished["state"] == "failed"
    assert finished["exit_code"] == 1
    assert finished["outputs_preserved"] is False
    assert finished["snapshot_removed"] is False
    stranded = Path(finished["snapshot"]) / "cad" / "out"
    assert Path(finished["outputs"]) == stranded
    assert (stranded / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"


def test_a_changed_lock_gets_its_own_environment(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    worktree = Path(fixture["worktree"])
    environments = []
    for lock in ("# lock one\n", "# lock two\n"):
        (worktree / "uv.lock").write_text(lock, encoding="utf-8")
        _git(worktree, "commit", "-q", "-am", lock)
        _git(worktree, "update-ref", "refs/remotes/origin/main", "HEAD")
        result = _run_launcher(
            fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
        )
        assert result.returncode == 0, (result.stdout, result.stderr)
        environments.append(json.loads(result.stdout.splitlines()[-1])["environment"])

    assert environments[0] != environments[1]
    assert len(Path(fixture["syncs"]).read_text(encoding="utf-8").splitlines()) == 2


def test_the_snapshot_initializes_required_submodules_only(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path, submodules=True)

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    invocation = json.loads(Path(fixture["invocation"]).read_text(encoding="utf-8"))
    assert invocation["submodule_files"] == {"lib": True, "refs": False}
    finished = json.loads(result.stdout.splitlines()[-1])
    assert finished["snapshot_removed"] is True
    assert not Path(finished["snapshot"]).exists()


def test_a_failed_environment_sync_never_builds_and_still_cleans_up(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_SYNC_EXIT"] = "5"

    result = _run_launcher(fixture, _command(fixture, "part:pen_rod"), environment)

    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "uv sync of the shared environment" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    finished = _record(_only(Path(fixture["log_directory"]), "*.done"))
    assert finished["state"] == "failed"
    assert finished["snapshot_removed"] is True
    assert not Path(finished["snapshot"]).exists()
    # Neither a published environment nor the failed staging copy is left.
    assert not Path(finished["environment"]).parent.exists() or not any(
        Path(finished["environment"]).parent.iterdir()
    )


def test_a_dirty_worktree_is_refused_before_startup(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    (Path(fixture["worktree"]) / "scratch.py").write_text("x = 1\n", encoding="utf-8")

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode != 0
    assert "Worktree has uncommitted changes" in result.stderr
    assert "scratch.py" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    assert not list(Path(fixture["log_directory"]).glob("*.run.json"))


def test_log_directory_inside_any_git_worktree_is_refused(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    other = tmp_path / "other checkout"
    other.mkdir()
    _git(other, "init", "-q")
    fixture["log_directory"] = other / "records"

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode != 0
    assert "LogDirectory must be outside every Git worktree" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    assert not Path(fixture["log_directory"]).exists()


def test_record_read_waits_out_a_transient_sharing_violation(tmp_path: Path) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    record = tmp_path / "held.run.json"
    record.write_text('{"state": "running"}\n', encoding="utf-8")
    generic_read, no_sharing, open_existing = 0x80000000, 0, 3
    handle = kernel32.CreateFileW(
        str(record), generic_read, no_sharing, None, open_existing, 0, None
    )
    assert handle not in (None, wintypes.HANDLE(-1).value), ctypes.get_last_error()
    with pytest.raises(PermissionError):
        record.read_text(encoding="utf-8")

    release = threading.Timer(0.5, kernel32.CloseHandle, args=(handle,))
    release.start()
    try:
        assert _record(record) == {"state": "running"}
    finally:
        release.join()


def test_log_directory_with_brackets_is_treated_as_a_literal_path(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    fixture["log_directory"] = tmp_path / "external [launch] records"

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    log_directory = Path(fixture["log_directory"])
    finished = _record(_only(log_directory, "*.done"))
    assert finished["state"] == "succeeded"
    launch_log = Path(finished["log"]).read_text(encoding="utf-8")
    assert "uv-stdout" in launch_log
    assert "uv-stderr" in launch_log


def test_native_failure_preserves_exit_and_writes_a_failed_terminal_record(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_EXIT"] = "23"

    result = _run_launcher(fixture, _command(fixture, "part:pen_rod"), environment)

    assert result.returncode == 23, (result.stdout, result.stderr)
    log_directory = Path(fixture["log_directory"])
    running = _record(_only(log_directory, "*.run.json"))
    finished = _record(_only(log_directory, "*.done"))
    assert finished["run_id"] == running["run_id"]
    assert finished["state"] == "failed"
    assert finished["exit_code"] == 23
    assert finished["commit"] == running["commit"]
    assert finished["argv"] == running["argv"]
    # A failed build keeps its outputs for forensics; the snapshot is only the
    # recorded commit, so it goes either way.
    assert finished["outputs_preserved"] is True
    assert (Path(finished["outputs"]) / "reports" / "stub-output.txt").exists()
    assert finished["snapshot_removed"] is True
    assert not Path(finished["snapshot"]).exists()
    assert "uv-stdout" in Path(finished["log"]).read_text(encoding="utf-8")
    assert "uv-stderr" in Path(finished["log"]).read_text(encoding="utf-8")
    assert not any(
        _record(marker)["state"] == "succeeded"
        for marker in log_directory.glob("*.done")
    )


def test_wrapper_failure_after_startup_writes_a_failed_terminal_record(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    tools = Path(fixture["tools"])
    (tools / "uv.cmd").unlink()
    git_executable = shutil.which("git.exe") or shutil.which("git")
    assert git_executable is not None
    (tools / "git.cmd").write_text(
        f'@echo off\r\n"{git_executable}" %*\r\nexit /b %ERRORLEVEL%\r\n',
        encoding="utf-8",
    )
    environment = dict(fixture["environment"])
    environment["PATH"] = str(tools)

    result = _run_launcher(fixture, _command(fixture, "part:pen_rod"), environment)

    assert result.returncode == 1, (result.stdout, result.stderr)
    assert "farm-launch wrapper failed:" in result.stderr
    log_directory = Path(fixture["log_directory"])
    running = _record(_only(log_directory, "*.run.json"))
    finished = _record(_only(log_directory, "*.done"))
    assert finished["run_id"] == running["run_id"]
    assert finished["state"] == "failed"
    assert finished["exit_code"] == 1
    assert "farm-launch wrapper failed:" in Path(finished["log"]).read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    ("targets", "diagnostic"),
    [
        ("name=value", "not doit variables"),
        ("part:pen_rod,,drawing:pen", "empty component"),
        ("   ", "empty component"),
        ("part:pen_rod,-bad", "option-like selection"),
    ],
)
def test_invalid_targets_never_start_or_invoke_uv(
    tmp_path: Path, targets: str, diagnostic: str
) -> None:
    fixture = _launcher_fixture(tmp_path)

    result = _run_launcher(fixture, _command(fixture, targets), fixture["environment"])

    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not list(log_directory.glob("*.run.json"))
    assert not list(log_directory.glob("*.done"))


def test_tag_with_trailing_newline_is_rejected_before_startup(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)

    result = _run_launcher(
        fixture,
        _command(fixture, "part:pen_rod", tag="apparently-valid\n"),
        fixture["environment"],
    )

    assert result.returncode != 0
    assert "Tag" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not list(log_directory.glob("*.run.json"))
    assert not list(log_directory.glob("*.done"))


def test_head_not_known_on_origin_fails_before_startup(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    _git(Path(fixture["worktree"]), "update-ref", "-d", "refs/remotes/origin/main")

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode != 0
    assert (
        "HEAD is not known on origin; fetch and push before launching" in result.stderr
    )
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not list(log_directory.glob("*.run.json"))
    assert not list(log_directory.glob("*.done"))


def test_log_directory_must_be_outside_the_worktree(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    fixture["log_directory"] = Path(fixture["worktree"]) / "launch records"

    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod"), fixture["environment"]
    )

    assert result.returncode != 0
    assert "LogDirectory must be outside the target worktree" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    assert not Path(fixture["log_directory"]).exists()

"""Windows contract tests for the tracked, supervised farm launcher."""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="scripts/farm-run.ps1 is a Windows launcher"
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = REPO_ROOT / "scripts" / "farm-run.ps1"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _launcher_fixture(tmp_path: Path) -> dict[str, object]:
    worktree = tmp_path / "source worktree"
    worktree.mkdir()
    (worktree / "build.py").write_text("# launcher fixture\n", encoding="utf-8")
    _git(worktree, "init", "-q")
    _git(worktree, "add", "build.py")
    _git(worktree, "commit", "-q", "-m", "launcher fixture")
    _git(worktree, "update-ref", "refs/remotes/origin/main", "HEAD")

    pool = tmp_path / "pool checkout"
    pool.mkdir()
    (pool / "farm.py").write_text("# launcher fixture\n", encoding="utf-8")

    log_directory = tmp_path / "external launch records"
    tools = tmp_path / "stub tools"
    tools.mkdir()
    invocation = tmp_path / "uv invocation.json"
    stub = tools / "uv_stub.py"
    stub.write_text(
        """import json
import os
import sys
import time
from pathlib import Path

Path(os.environ["UV_STUB_INVOCATION"]).write_text(
    json.dumps(
        {
            "argv": sys.argv[1:],
            "environment": {
                "SOLIDWORKS_POOL_HOME": os.environ.get("SOLIDWORKS_POOL_HOME"),
                "HARMONIC_REMOTE_CACHE_MODE": os.environ.get("HARMONIC_REMOTE_CACHE_MODE"),
                "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED"),
            },
        }
    ),
    encoding="utf-8",
)
print("uv-stdout", flush=True)
print("uv-stderr", file=sys.stderr, flush=True)
time.sleep(float(os.environ.get("UV_STUB_SLEEP", "0")))
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
    environment["UV_STUB_EXIT"] = "0"
    environment["HARMONIC_CACHE_ACCOUNT"] = "fixture-account"
    environment.pop("HARMONIC_CACHE_CONTAINER", None)
    environment["HARMONIC_CACHE_SALT"] = "fixture-salt"

    return {
        "pwsh": pwsh,
        "worktree": worktree,
        "pool": pool,
        "log_directory": log_directory,
        "invocation": invocation,
        "tools": tools,
        "environment": environment,
    }


def _command(fixture: dict[str, object], targets: str, *, tag: str = "test") -> list[str]:
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


def _record(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_success_records_start_before_completion_and_preserves_native_arguments(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_SLEEP"] = "3"
    command = _command(fixture, "part:pen_rod, drawing:pen", tag="spaces-ok")

    process = subprocess.Popen(
        command,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    log_directory = Path(fixture["log_directory"])
    deadline = time.monotonic() + 10
    run_paths: list[Path] = []
    while time.monotonic() < deadline:
        run_paths = list(log_directory.glob("*.run.json"))
        if run_paths:
            break
        if process.poll() is not None:
            break
        time.sleep(0.05)

    assert len(run_paths) == 1
    running = _record(run_paths[0])
    assert process.poll() is None
    assert running["state"] == "running"
    assert not Path(running["done"]).exists()

    stream_deadline = time.monotonic() + 5
    launch_log = ""
    while time.monotonic() < stream_deadline:
        launch_log = Path(running["log"]).read_text(encoding="utf-8")
        if "uv-stdout" in launch_log and "uv-stderr" in launch_log:
            break
        if process.poll() is not None:
            break
        time.sleep(0.05)
    assert "uv-stdout" in launch_log
    assert "uv-stderr" in launch_log
    assert process.poll() is None

    stdout, stderr = process.communicate(timeout=10)
    assert process.returncode == 0, (stdout, stderr)
    assert stderr == ""
    assert "uv-stdout" in stdout
    assert "uv-stderr" in stdout

    readiness = next(
        line for line in stdout.splitlines() if line.startswith("farm-launch started ")
    )
    _, _, readiness_run_id, readiness_record = readiness.split(" ", 3)
    assert readiness_run_id == running["run_id"]
    assert Path(readiness_record) == run_paths[0]
    assert run_paths[0].name == f"{running['run_id']}.run.json"
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
        "python",
        "build.py",
        "--executor",
        "farm",
        "--leaf-timeout",
        "90",
        "--verbosity",
        "info",
        "-n",
        "4",
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
    }
    launch_log = Path(finished["log"]).read_text(encoding="utf-8")
    assert "uv-stdout" in launch_log
    assert "uv-stderr" in launch_log

def test_log_directory_with_brackets_is_treated_as_a_literal_path(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    fixture["log_directory"] = tmp_path / "external [launch] records"

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=20,
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

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode == 23, (result.stdout, result.stderr)
    log_directory = Path(fixture["log_directory"])
    running = _record(_only(log_directory, "*.run.json"))
    finished = _record(_only(log_directory, "*.done"))
    assert finished["run_id"] == running["run_id"]
    assert finished["state"] == "failed"
    assert finished["exit_code"] == 23
    assert finished["commit"] == running["commit"]
    assert finished["argv"] == running["argv"]
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

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
    )

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

    result = subprocess.run(
        _command(fixture, targets),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not list(log_directory.glob("*.run.json"))
    assert not list(log_directory.glob("*.done"))

def test_tag_with_trailing_newline_is_rejected_before_startup(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)

    result = subprocess.run(
        _command(fixture, "part:pen_rod", tag="apparently-valid\n"),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=20,
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

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "HEAD is not known on origin; fetch and push before launching" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not list(log_directory.glob("*.run.json"))
    assert not list(log_directory.glob("*.done"))


def test_log_directory_must_be_outside_the_worktree(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    fixture["log_directory"] = Path(fixture["worktree"]) / "launch records"

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "LogDirectory must be outside the target worktree" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    assert not Path(fixture["log_directory"]).exists()

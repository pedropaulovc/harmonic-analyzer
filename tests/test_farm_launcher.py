"""Windows contract tests for the tracked, supervised farm launcher."""

import hashlib
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
        """import hashlib
import json
import os
import sys
import time
from pathlib import Path


def build_py_digest():
    return hashlib.sha256(Path("build.py").read_bytes()).hexdigest()


invocation = {
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "build_py_sha256": build_py_digest(),
    "cad_out_present": Path("cad/out").exists(),
    "submodules_present": sorted(
        path for path in ("vendored", "excluded") if Path(path, "marker.txt").exists()
    ),
    "inherited": {
        name: os.environ.get(name) for name in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
    },
    "environment": {
        "SOLIDWORKS_POOL_HOME": os.environ.get("SOLIDWORKS_POOL_HOME"),
        "HARMONIC_REMOTE_CACHE_MODE": os.environ.get("HARMONIC_REMOTE_CACHE_MODE"),
        "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED"),
    },
}
record = Path(os.environ["UV_STUB_INVOCATION"])
record.write_text(json.dumps(invocation), encoding="utf-8")
print("uv-stdout", flush=True)
print("uv-stderr", file=sys.stderr, flush=True)
time.sleep(float(os.environ.get("UV_STUB_SLEEP", "0")))
invocation["build_py_sha256_after_sleep"] = build_py_digest()
record.write_text(json.dumps(invocation), encoding="utf-8")
if os.environ.get("UV_STUB_OUTPUTS"):
    out = Path("cad/out")
    for relative, content in {
        "png/probe.png": "built png",
        "sldprt/probe.SLDPRT": "built part",
        "sldprt/.probe.execution": "built token",
        "reports/telemetry/traces.jsonl": '{"span": "built"}\\n',
        ".drawing-registry/probe.digest": "build-local sidecar",
    }.items():
        (out / relative).parent.mkdir(parents=True, exist_ok=True)
        (out / relative).write_text(content, encoding="utf-8")
    (out / ".doit.db").write_text(
        json.dumps({"part:probe": {"built": True}, "drawing:probe": {"built": True}}),
        encoding="utf-8",
    )
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
    environment["VIRTUAL_ENV"] = str(tmp_path / "caller venv")
    environment["UV_PROJECT_ENVIRONMENT"] = str(tmp_path / "shared env")

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


def _registered_worktrees(repo: Path) -> list[Path]:
    listing = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]


def _assert_build_worktree_gone(fixture: dict[str, object], finished: dict) -> None:
    build_worktree = Path(finished["build_worktree"])
    assert finished["build_worktree_removed"] is True
    assert not build_worktree.exists()
    assert build_worktree.resolve() not in _registered_worktrees(Path(fixture["worktree"]))


def _committed_digest(fixture: dict[str, object]) -> str:
    return hashlib.sha256(
        (Path(fixture["worktree"]) / "build.py").read_bytes()
    ).hexdigest()


def _invocation(fixture: dict[str, object]) -> dict[str, object]:
    return json.loads(Path(fixture["invocation"]).read_text(encoding="utf-8"))


def test_build_runs_at_the_pinned_commit_while_the_caller_is_mutated_mid_run(
    tmp_path: Path,
) -> None:
    """Regression for knife-cc-8: an in-worktree edit during the run changed keys."""
    fixture = _launcher_fixture(tmp_path)
    committed = _committed_digest(fixture)
    caller = Path(fixture["worktree"])
    environment = dict(fixture["environment"])
    environment["UV_STUB_SLEEP"] = "3"

    process = subprocess.Popen(
        _command(fixture, "part:pen_rod"),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 15
    while not Path(fixture["invocation"]).exists() and time.monotonic() < deadline:
        assert process.poll() is None
        time.sleep(0.05)
    assert Path(fixture["invocation"]).exists()
    (caller / "build.py").write_text("# edited mid-run\n", encoding="utf-8")
    (caller / "scratch.txt").write_text("untracked mid-run\n", encoding="utf-8")

    stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 0, (stdout, stderr)
    invocation = _invocation(fixture)
    assert invocation["build_py_sha256"] == committed
    assert invocation["build_py_sha256_after_sleep"] == committed
    assert Path(invocation["cwd"]).resolve() != caller.resolve()
    finished = _record(_only(Path(fixture["log_directory"]), "*.done"))
    assert Path(invocation["cwd"]).resolve() == Path(finished["build_worktree"]).resolve()
    assert invocation["inherited"] == {"VIRTUAL_ENV": None, "UV_PROJECT_ENVIRONMENT": None}
    assert finished["state"] == "succeeded"
    assert finished["caller_dirty"] == []
    assert set(finished["phase_s"]) == {"prepare", "build", "harvest", "cleanup"}
    _assert_build_worktree_gone(fixture, finished)
    assert (caller / "build.py").read_text(encoding="utf-8") == "# edited mid-run\n"


def test_poisoned_caller_doit_state_never_reaches_the_build(tmp_path: Path) -> None:
    """Regression for knife-cc-9: a stale .doit.db record and artefact skewed keys."""
    fixture = _launcher_fixture(tmp_path)
    caller_out = Path(fixture["worktree"]) / "cad" / "out"
    (caller_out / "sldprt").mkdir(parents=True)
    (caller_out / "sldprt" / "probe.SLDPRT").write_text("stale part", encoding="utf-8")
    (caller_out / "sldprt" / ".probe.execution").write_text("stale token", encoding="utf-8")
    (caller_out / "reports" / "telemetry").mkdir(parents=True)
    (caller_out / "reports" / "telemetry" / "traces.jsonl").write_text(
        '{"span": "caller"}\n', encoding="utf-8"
    )
    (caller_out / ".doit.db").write_text(
        json.dumps(
            {
                "part:probe": {"poisoned": True},
                "part:unrelated": {"kept": True},
            }
        ),
        encoding="utf-8",
    )
    environment = dict(fixture["environment"])
    environment["UV_STUB_OUTPUTS"] = "1"

    result = subprocess.run(
        _command(fixture, "part:probe,drawing:probe"),
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    invocation = _invocation(fixture)
    assert invocation["cad_out_present"] is False
    finished = _record(_only(Path(fixture["log_directory"]), "*.done"))
    assert Path(finished["outputs_copied_to"]) == caller_out.resolve()
    assert finished["outputs_copied"] == 4
    assert finished["caller_tasks_forgotten"] == ["part:probe"]
    assert (caller_out / "png" / "probe.png").read_text(encoding="utf-8") == "built png"
    assert (caller_out / "sldprt" / "probe.SLDPRT").read_text(encoding="utf-8") == "built part"
    assert (caller_out / "sldprt" / ".probe.execution").read_text(
        encoding="utf-8"
    ) == "built token"
    assert (caller_out / "reports" / "telemetry" / "traces.jsonl").read_text(
        encoding="utf-8"
    ) == '{"span": "caller"}\n{"span": "built"}\n'
    assert not (caller_out / ".drawing-registry").exists()
    assert json.loads((caller_out / ".doit.db").read_text(encoding="utf-8")) == {
        "part:unrelated": {"kept": True}
    }
    _assert_build_worktree_gone(fixture, finished)


def test_dirty_caller_warns_that_its_edits_are_not_built(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    caller = Path(fixture["worktree"])
    (caller / "build.py").write_text("# uncommitted\n", encoding="utf-8")
    (caller / "notes.txt").write_text("untracked\n", encoding="utf-8")

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert "does NOT build" in result.stdout
    running = _record(_only(Path(fixture["log_directory"]), "*.run.json"))
    assert sorted(running["caller_dirty"]) == ["build.py", "notes.txt"]
    assert "does NOT build" in Path(running["log"]).read_text(encoding="utf-8")
    assert _invocation(fixture)["build_py_sha256"] != hashlib.sha256(
        b"# uncommitted\n"
    ).hexdigest()


def test_native_failure_still_harvests_and_removes_the_build_worktree(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_EXIT"] = "23"
    environment["UV_STUB_OUTPUTS"] = "1"

    result = subprocess.run(
        _command(fixture, "part:probe"),
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
    )

    assert result.returncode == 23, (result.stdout, result.stderr)
    finished = _record(_only(Path(fixture["log_directory"]), "*.done"))
    assert finished["state"] == "failed"
    assert finished["outputs_copied"] == 4
    _assert_build_worktree_gone(fixture, finished)


def test_concurrent_launches_from_one_caller_use_distinct_build_worktrees(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["UV_STUB_SLEEP"] = "2"
    environment["UV_STUB_INVOCATION"] = str(tmp_path / "ignored invocation.json")

    processes = [
        subprocess.Popen(
            _command(fixture, "part:pen_rod", tag=f"twin-{index}"),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(2)
    ]
    for process in processes:
        stdout, stderr = process.communicate(timeout=60)
        assert process.returncode == 0, (stdout, stderr)

    finished = [
        _record(path) for path in Path(fixture["log_directory"]).glob("*.done")
    ]
    assert len(finished) == 2
    assert finished[0]["build_worktree"] != finished[1]["build_worktree"]
    for record in finished:
        _assert_build_worktree_gone(fixture, record)


def test_submodules_follow_the_commit_and_its_farm_exclusions(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    caller = Path(fixture["worktree"])
    for name in ("vendored", "excluded"):
        source = tmp_path / f"{name} source"
        source.mkdir()
        (source / "marker.txt").write_text(name, encoding="utf-8")
        _git(source, "init", "-q")
        _git(source, "add", "marker.txt")
        _git(source, "commit", "-q", "-m", name)
        _git(
            caller,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            str(source),
            name,
        )
    (caller / ".farm-sources.json").write_text(
        json.dumps({"exclude_submodules": ["./excluded/"]}), encoding="utf-8"
    )
    _git(caller, "add", ".farm-sources.json")
    _git(caller, "commit", "-q", "-m", "submodules")
    _git(caller, "update-ref", "refs/remotes/origin/main", "HEAD")
    environment = dict(fixture["environment"])
    environment["GIT_CONFIG_COUNT"] = "1"
    environment["GIT_CONFIG_KEY_0"] = "protocol.file.allow"
    environment["GIT_CONFIG_VALUE_0"] = "always"

    result = subprocess.run(
        _command(fixture, "part:pen_rod"),
        env=environment,
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    assert _invocation(fixture)["submodules_present"] == ["vendored"]
    finished = _record(_only(Path(fixture["log_directory"]), "*.done"))
    assert "submodule excluded excluded by .farm-sources.json" in Path(
        finished["log"]
    ).read_text(encoding="utf-8")
    _assert_build_worktree_gone(fixture, finished)


@pytest.mark.parametrize("target", ["release", "gallery"])
def test_submitter_only_targets_are_rejected_before_startup(
    tmp_path: Path, target: str
) -> None:
    fixture = _launcher_fixture(tmp_path)

    result = subprocess.run(
        _command(fixture, f"part:pen_rod,{target}"),
        env=fixture["environment"],
        text=True,
        capture_output=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert f"Targets cannot include {target}" in result.stderr
    assert not Path(fixture["invocation"]).exists()
    assert not list(Path(fixture["log_directory"]).glob("*.run.json"))

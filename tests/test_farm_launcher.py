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
DISPLAY_NAME = "Fixture build: pen and drawing"

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
        """import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
# Keep redirected Python output UTF-8 rather than inheriting Windows'
# legacy Python pipe encoding.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


farm = next((i for i, arg in enumerate(sys.argv) if arg.endswith("farm.py")), None)
if farm is not None:
    # `uv run --project <pool> <pool>/farm.py <command> ...`, as the tracking
    # operations call it: a stateful fake of the farm's status/cancel.
    # A workflow is {"status": ..., "farm_run": ...}; the build half of this
    # stub creates a requested workflow's memo from HARMONIC_FARM_RUN (the farm
    # writes it on creation) unless its creator already set one. "_old": true
    # plays a farm.py that predates farm_run: status leaves the key out.
    # Status "UNREACHABLE" fails the query as a network outage would.
    # "_absent_for": N reports the workflow missing to its first N status
    # queries: a start RPC the farm had not committed yet.
    state_path = Path(os.environ["UV_STUB_FARM"])
    workflows = json.loads(state_path.read_text(encoding="utf-8"))
    command, *rest = sys.argv[farm + 1 :]
    workflow = rest[-1]
    absent = workflow in workflows and workflows[workflow].get("_absent_for", 0) > 0
    if absent and command == "status":
        workflows[workflow]["_absent_for"] -= 1
        state_path.write_text(json.dumps(workflows), encoding="utf-8")
    if workflow not in workflows or absent:
        print(f"Error: workflow not found for ID: {workflow}", file=sys.stderr)
        raise SystemExit(2)
    described = workflows[workflow]
    if described["status"] == "UNREACHABLE":
        print("Error: failed to connect to the farm", file=sys.stderr)
        raise SystemExit(1)
    if command == "status":
        shown = {
            key: value
            for key, value in described.items()
            if key not in ("_old", "_absent_for")
        }
        if described.get("_old"):
            shown.pop("farm_run", None)
        # "_attach": a run record to publish while the farm answers: a sibling
        # that attaches to this leaf mid-cancel.
        attach = described.pop("_attach", None)
        if attach is not None:
            state_path.write_text(json.dumps(workflows), encoding="utf-8")
            Path(attach["path"]).write_text(attach["record"], encoding="utf-8")
        print(json.dumps({"workflow_id": workflow, **shown}))
        raise SystemExit(0)
    if command == "cancel":
        described["status"] = "CANCELED"
        state_path.write_text(json.dumps(workflows), encoding="utf-8")
        with open(os.environ["UV_STUB_FARM_CANCELS"], "a", encoding="utf-8") as cancels:
            cancels.write(
                json.dumps(
                    {
                        "argv": sys.argv[farm + 1 :],
                        "VIRTUAL_ENV": os.environ.get("VIRTUAL_ENV"),
                    }
                )
                + "\\n"
            )
        raise SystemExit(0)
    raise SystemExit(64)

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
                "pid": os.getpid(),
                # The venv python.exe that started this interpreter; its
                # parent is the uv.cmd shim's cmd.exe.
                "ppid": os.getppid(),
                "argv": sys.argv[1:],
                "cwd": str(cwd),
                "head": subprocess.run(
                    ["git", "rev-parse", "HEAD"], capture_output=True, text=True
                ).stdout.strip(),
                "environment": {
                    "SOLIDWORKS_POOL_HOME": os.environ.get("SOLIDWORKS_POOL_HOME"),
                    "HARMONIC_REMOTE_CACHE_MODE": os.environ.get("HARMONIC_REMOTE_CACHE_MODE"),
                    "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED"),
                    "HARMONIC_FARM_DISPLAY_NAME": os.environ.get("HARMONIC_FARM_DISPLAY_NAME"),
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
lines = os.environ.get("UV_STUB_LINES")
if lines:
    # Build output as build.py prints it: farm dispatch, cache hits, doit errors.
    printed = Path(lines).read_text(encoding="utf-8")
    requested = re.findall(r"Farm workflow requested: (\\S+)", printed)
    # UV_STUB_UNLOGGED: workflows dispatched whose lines never reach the log,
    # as when -Cancel stops the launcher before it copies them.
    unlogged = [w for w in os.environ.get("UV_STUB_UNLOGGED", "").split(",") if w]
    farm_state = Path(os.environ["UV_STUB_FARM"])
    workflows = json.loads(farm_state.read_text(encoding="utf-8"))
    for workflow in requested + unlogged:
        # _farm._dispatch names the workflow in the run's request directory...
        requests = os.environ.get("HARMONIC_FARM_REQUESTS")
        if requests:
            task = ":".join(workflow.split(":")[1:3])
            name = hashlib.sha256(workflow.encode("utf-8")).hexdigest()[:32]
            (Path(requests) / f"{name}.json").write_text(
                json.dumps({"task": task, "workflow_id": workflow}), encoding="utf-8"
            )
        # ...then start_workflow(USE_EXISTING, memo=...): only a creation writes it.
        if workflow in workflows and not workflows[workflow].get("_old"):
            workflows[workflow].setdefault("farm_run", os.environ.get("HARMONIC_FARM_RUN"))
    farm_state.write_text(json.dumps(workflows), encoding="utf-8")
    print(printed, end="", flush=True)
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
    farm_state = tmp_path / "farm workflows.json"
    farm_state.write_text("{}", encoding="utf-8")
    farm_cancels = tmp_path / "farm cancels.jsonl"
    environment["UV_STUB_FARM"] = str(farm_state)
    environment["UV_STUB_FARM_CANCELS"] = str(farm_cancels)

    return {
        "pwsh": pwsh,
        "worktree": worktree,
        "pool": pool,
        "log_directory": log_directory,
        "invocation": invocation,
        "syncs": syncs,
        "tools": tools,
        "environment": environment,
        "farm_state": farm_state,
        "farm_cancels": farm_cancels,
    }


def _command(
    fixture: dict[str, object], targets: str, *, tag: str = "test",
    display_name: str = DISPLAY_NAME,
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
        *([f"-DisplayName:{display_name}"] if display_name.startswith("-")
          else ["-DisplayName", display_name]),
    ]


@pytest.mark.parametrize(
    "label",
    [None, "", " \t", "x" * 161,
     pytest.param("\U0001f680" * 161, id="supplementary161"),
     pytest.param("\u03a9" * 80 + "\U0001f680" * 81, id="mixed161"),
     "a\tb", "a\x01b", "a\x1fb", "a\x7fb", "a\rb", "a\nb", "a\u0085b", "a\u2028b", "a\u2029b", "a\u202eb"],
)
def test_launch_requires_valid_display_name_before_creating_records(tmp_path, label):
    fixture = _launcher_fixture(tmp_path)
    command = _command(fixture, "part:pen_rod")
    if label is None:
        command = command[:-2]
    else:
        command[-1] = label
    environment = dict(fixture["environment"])
    environment["HARMONIC_FARM_DISPLAY_NAME"] = "Inherited label is not a launcher argument"
    result = _run_launcher(fixture, command, environment)
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert "DisplayName" in result.stdout + result.stderr
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not log_directory.exists() or list(log_directory.iterdir()) == []


@pytest.mark.parametrize("label", ["x", "x" * 160,
    pytest.param("\U0001f680" * 160, id="supplementary160"),
    pytest.param("\u03a9" * 80 + "\U0001f680" * 80, id="mixed160"),
    "  Review Ω: gear train  ", "Review \U0001f680: gear train", "مراجعة שלום", "Review 👩\u200d🔧: gear\u200ctrain", "-review", "--executor", "-DisplayName"])
def test_launch_preserves_boundary_display_names_and_overrides_environment(tmp_path, label):
    fixture = _launcher_fixture(tmp_path)
    environment = dict(fixture["environment"])
    environment["HARMONIC_FARM_DISPLAY_NAME"] = "Inherited label"
    result = _run_launcher(
        fixture, _command(fixture, "part:pen_rod", display_name=label), environment,
        creationflags=subprocess.CREATE_NO_WINDOW if not label.isascii() else 0,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    record = _record(_only(Path(fixture["log_directory"]), "*.run.json"))
    finished = _record(Path(record["done"]))
    invocation = json.loads(Path(fixture["invocation"]).read_text(encoding="utf-8"))
    assert record["display_name"] == finished["display_name"] == label
    assert invocation["environment"]["HARMONIC_FARM_DISPLAY_NAME"] == label
    assert invocation["argv"].count(f"--display-name={label}") == 1
    assert "--display-name" not in invocation["argv"]


@pytest.mark.parametrize("codepoint", [0, 0xD800, 0xDFFF])
def test_launch_rejects_untransportable_display_name_before_creating_records(tmp_path, codepoint):
    fixture = _launcher_fixture(tmp_path)
    # Construct NUL and lone surrogates within PowerShell rather than relying
    # on native argv encoding to carry them to the script's validator.
    command = _command(fixture, "part:pen_rod")
    parameters = "; ".join(
        name.removeprefix("-") + " = '" + value.replace("'", "''") + "'"
        for name, value in zip(command[5:-2:2], command[6:-2:2])
    )
    script = (
        "$ErrorActionPreference = 'Stop'; $parameters = @{ "
        + parameters
        + f"; DisplayName = ('a' + [char]{codepoint} + 'b')"
        + " }; try { & '"
        + str(LAUNCHER).replace("'", "''")
        + "' @parameters } catch { Write-Error $_ -ErrorAction Continue; exit 2 }"
    )
    result = _run_launcher(
        fixture, [*command[:3], "-Command", script], fixture["environment"]
    )
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert "DisplayName" in result.stdout + result.stderr
    assert not Path(fixture["invocation"]).exists()
    log_directory = Path(fixture["log_directory"])
    assert not log_directory.exists() or list(log_directory.iterdir()) == []


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
    fixture: dict[str, object],
    command: list[str],
    environment: dict[str, str],
    *,
    creationflags: int = 0,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the launcher to exit; only the hang guard can end the wait early."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=HANG_GUARD_S,
            creationflags=creationflags,
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
    assert running["display_name"] == DISPLAY_NAME
    assert finished["display_name"] == DISPLAY_NAME
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
        f"--display-name={DISPLAY_NAME}",
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
        "HARMONIC_FARM_DISPLAY_NAME": DISPLAY_NAME,
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


def test_launch_defaults_to_the_agent_scratchpad(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    scratchpad = tmp_path / "agent scratchpad"
    omp_local = tmp_path / ".omp" / "agent" / "sessions" / "session-id" / "local"
    omp_local.mkdir(parents=True)
    environment = dict(fixture["environment"])
    environment["HARMONIC_AGENT_SCRATCHPAD"] = str(scratchpad)
    environment["OMPCODE"] = "1"

    command = _command(fixture, "part:pen_rod")
    log_directory = command.index("-LogDirectory")
    del command[log_directory : log_directory + 2]
    result = _run_launcher(fixture, command, environment, cwd=omp_local)

    assert result.returncode == 0, (result.stdout, result.stderr)
    finished = json.loads(result.stdout.splitlines()[-1])
    expected_directory = scratchpad / "harmonic-analyzer" / "farm-runs"
    assert Path(finished["log"]).parent == expected_directory
    assert Path(finished["outputs"]) == Path(finished["log"]).with_suffix(".out")
    assert (Path(finished["outputs"]) / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"

    status_result = _run_launcher(
        fixture,
        [
            str(fixture["pwsh"]),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(LAUNCHER),
            "-Status",
            "-RunId",
            finished["run_id"],
        ],
        environment,
    )
    assert status_result.returncode == 0, (
        status_result.stdout,
        status_result.stderr,
    )
    assert json.loads(status_result.stdout.splitlines()[-1])["state"] == "succeeded"


def test_launch_defaults_to_omp_local_working_directory(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    scratchpad = tmp_path / ".omp" / "agent" / "sessions" / "session-id" / "local"
    scratchpad.mkdir(parents=True)
    environment = dict(fixture["environment"])
    environment.pop("HARMONIC_AGENT_SCRATCHPAD", None)
    environment["OMPCODE"] = "1"
    environment["LOCALAPPDATA"] = str(tmp_path / "local app data")

    command = _command(fixture, "part:pen_rod")
    log_directory = command.index("-LogDirectory")
    del command[log_directory : log_directory + 2]
    result = _run_launcher(fixture, command, environment, cwd=scratchpad)

    assert result.returncode == 0, (result.stdout, result.stderr)
    finished = json.loads(result.stdout.splitlines()[-1])
    expected_directory = scratchpad / "harmonic-analyzer" / "farm-runs"
    assert Path(finished["log"]).parent == expected_directory
    assert Path(finished["outputs"]) == Path(finished["log"]).with_suffix(".out")
    assert (Path(finished["outputs"]) / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"

    status_result = _run_launcher(
        fixture,
        [
            str(fixture["pwsh"]),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(LAUNCHER),
            "-LogDirectory",
            str(expected_directory),
            "-Status",
            "-RunId",
            finished["run_id"],
        ],
        environment,
    )
    assert status_result.returncode == 0, (
        status_result.stdout,
        status_result.stderr,
    )
    assert json.loads(status_result.stdout.splitlines()[-1])["state"] == "succeeded"


def test_agent_scratchpad_snapshot_supports_windows_long_paths(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path, submodules=True)
    worktree = Path(fixture["worktree"])
    scratchpad = tmp_path / "agent scratchpad"
    default_directory = scratchpad / "harmonic-analyzer" / "farm-runs"
    snapshot_root = default_directory / "snapshots" / ("0" * 12)
    # Target a 261-character snapshot path while keeping the fixture source short.
    relative_length = max(15, 261 - len(str(snapshot_root)) - 1)
    payload_length = relative_length - 15
    relative = Path("nested") / ("payload-" + "x" * payload_length)
    tracked_file = worktree / relative
    snapshot_file = snapshot_root / relative
    if len(str(tracked_file)) >= 260:
        pytest.skip(
            "pytest temporary root leaves no short source path for the long-path probe"
        )
    assert len(str(tracked_file)) < 260
    assert len(str(snapshot_file)) > 260

    tracked_file.parent.mkdir(parents=True)
    tracked_file.write_text("long tracked path\n", encoding="utf-8")
    _git(worktree, "add", "--", relative.as_posix())
    _git(worktree, "commit", "-q", "-m", "add long tracked path")
    _git(worktree, "update-ref", "refs/remotes/origin/main", "HEAD")

    environment = dict(fixture["environment"])
    environment["HARMONIC_AGENT_SCRATCHPAD"] = str(scratchpad)
    command = _command(fixture, "part:pen_rod")
    log_directory_argument = command.index("-LogDirectory")
    del command[log_directory_argument : log_directory_argument + 2]

    result = _run_launcher(fixture, command, environment)

    assert result.returncode == 0, (result.stdout, result.stderr)
    finished = json.loads(result.stdout.splitlines()[-1])
    assert Path(finished["log"]).parent == default_directory
    assert finished["snapshot_removed"] is True
    assert finished["cleanup_errors"] == []
    assert (Path(finished["outputs"]) / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"


@pytest.mark.parametrize(
    ("working_directory", "omp_code"),
    [("local", None), ("Local", "1")],
    ids=["local-without-omp", "omp-case-mismatch"],
)
def test_launch_defaults_to_local_appdata_when_no_agent_scratchpad_is_set(
    tmp_path: Path, working_directory: str, omp_code: str | None
) -> None:
    fixture = _launcher_fixture(tmp_path)
    caller_directory = tmp_path / working_directory
    caller_directory.mkdir()
    local_app_data = tmp_path / "local app data"
    environment = dict(fixture["environment"])
    environment.pop("HARMONIC_AGENT_SCRATCHPAD", None)
    if omp_code is None:
        environment.pop("OMPCODE", None)
    else:
        environment["OMPCODE"] = omp_code
    environment["LOCALAPPDATA"] = str(local_app_data)

    command = _command(fixture, "part:pen_rod")
    log_directory = command.index("-LogDirectory")
    del command[log_directory : log_directory + 2]
    result = _run_launcher(fixture, command, environment, cwd=caller_directory)

    assert result.returncode == 0, (result.stdout, result.stderr)
    finished = json.loads(result.stdout.splitlines()[-1])
    expected_directory = local_app_data / "ha-farm" / "runs"
    assert Path(finished["log"]).parent == expected_directory
    assert Path(finished["outputs"]) == Path(finished["log"]).with_suffix(".out")


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
    # --project names the snapshot so -Cancel can tell a sync a dead launcher
    # left from anyone else's.
    assert syncs[0]["argv"] == [
        "sync",
        "--frozen",
        "--no-editable",
        "--active",
        "--project",
        first["snapshot"],
    ]
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


# --- Tracking a recorded run: -Status, -Watch, -Cancel, -List ------------------

LEAF_PEN = "leaf:part:pen_rod:" + "a" * 64 + ":5400s"
LEAF_CONE = "leaf:part:cone_gear:" + "b" * 64 + ":5400s"
LEAF_NUT = "leaf:part:wheel_axle_nut:" + "c" * 64 + ":5400s"
LEAF_SHARED = "leaf:part:crank_hub:" + "d" * 64 + ":5400s"
LEAF_FOREIGN = "leaf:part:paper_roller:" + "f" * 64 + ":5400s"
LEAF_RACED = "leaf:part:platen:" + "9" * 64 + ":5400s"
LEAF_EARLY = "leaf:part:cam_follower:" + "e" * 64 + ":5400s"

# Verbatim shapes of what build.py prints at --verbosity info (_farm._dispatch,
# the cache restore, doit's TaskError and the traceback's final exception).
DISPATCH_LINES = (
    "  --  [    2.0s +  1.9s] [cache] HIT   part:foot_screw (45719abb0031) -> skipped COM build\n"
    f"  --  [    2.0s +  1.9s] Farm workflow requested: {LEAF_CONE}\n"
    f"  --  [    2.1s +  0.1s] Farm workflow attached: {LEAF_CONE}\n"
    f"  --  [    2.2s +  0.1s] Farm workflow requested: {LEAF_PEN}\n"
    f"  --  [    2.3s +  0.1s] Farm workflow attached: {LEAF_PEN}\n"
    "  --  [   60.0s + 57.7s] [cache] HIT   part:cone_gear (bbbbbbbbbbbb) -> skipped COM build\n"
)
FAILURE_LINES = (
    "TaskError - taskid:part:pen_rod\n"
    "PythonAction Error\n"
    "Traceback (most recent call last):\n"
    '  File "dodo.py", line 2302, in _farm_build\n'
    "RuntimeError: part:pen_rod failed on swmaker000005@5 [task_failed] exit 2: boom\n"
)


def _tracking(fixture: dict[str, object], *args: str) -> list[str]:
    return [
        str(fixture["pwsh"]),
        "-NoProfile",
        "-NonInteractive",
        "-File",
        str(LAUNCHER),
        *args,
        "-LogDirectory",
        str(fixture["log_directory"]),
    ]


def _process_alive(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _start_held(
    tmp_path: Path,
    fixture: dict[str, object],
    lines: str,
    tag: str,
    extra: dict[str, str] | None = None,
) -> tuple[subprocess.Popen[str], Path, dict[str, object]]:
    """Launch with the build child printing ``lines`` and then held open."""
    release = tmp_path / f"release {tag}"
    printed = tmp_path / f"lines {tag}.txt"
    printed.write_text(lines, encoding="utf-8")
    environment = dict(fixture["environment"])
    environment["UV_STUB_RELEASE"] = str(release)
    environment["UV_STUB_RELEASE_GUARD"] = str(HANG_GUARD_S)
    environment["UV_STUB_LINES"] = str(printed)
    environment.update(extra or {})
    process = subprocess.Popen(
        _command(fixture, "part:pen_rod", tag=tag),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    log_directory = Path(fixture["log_directory"])
    last_line = lines.splitlines()[-1]

    def running() -> dict[str, object] | None:
        for path in log_directory.glob("*.run.json") if log_directory.exists() else ():
            record = _record(path)
            if record["tag"] != tag:
                continue
            log = Path(record["log"]).read_text(encoding="utf-8")
            if last_line in log and "uv-stderr" in log:
                return record
        return None

    record = _wait_for(process, running, f"{tag} build output", log_directory)
    assert record is not None and process.poll() is None, (
        process.poll(),
        _observed(log_directory),
    )
    return process, release, record


def _stub_pid(fixture: dict[str, object]) -> int:
    return int(_record(Path(fixture["invocation"]))["pid"])


def test_status_and_watch_follow_a_live_run_to_its_outcome(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    process, release, running = _start_held(tmp_path, fixture, DISPATCH_LINES, "live")
    try:
        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-Tag", "live"),
            fixture["environment"],
        )
        assert status.returncode == 0, status.stderr
        report = json.loads(status.stdout)
        assert report["run_id"] == running["run_id"]
        assert report["state"] == "running"
        assert report["launcher"] == {
            "pid": running["pid"],
            "alive": True,
            "orphaned_processes": [],
        }
        assert report["counts"] == {
            "hits": 1,
            "requested": 2,
            "succeeded": 1,
            "failed": 0,
            "in_flight": 1,
        }
        assert report["in_flight_workflows"] == [LEAF_PEN]
        assert {leaf["task"]: leaf["state"] for leaf in report["leaves"]} == {
            "part:cone_gear": "succeeded",
            "part:pen_rod": "attached",
        }
        # Before .done the outputs are still in the snapshot.
        assert Path(report["outputs"]) == Path(running["snapshot"]) / "cad" / "out"

        # Tracking is not a launch: neither an argument nor a valid inherited
        # label is needed to watch the already-recorded run.
        watch_environment = dict(fixture["environment"])
        watch_environment["HARMONIC_FARM_DISPLAY_NAME"] = "invalid\ninherited label"
        watch = subprocess.Popen(
            _tracking(
                fixture, "-Watch", "-RunId", running["run_id"], "-PollSeconds", "1"
            ),
            env=watch_environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        first = watch.stdout.readline()
        assert "watching tag=live" in first and "state=running" in first, first
        release.touch()
        rest, errors = watch.communicate(timeout=HANG_GUARD_S)
    finally:
        release.touch()
        process.communicate(timeout=HANG_GUARD_S)

    assert process.returncode == 0
    assert watch.returncode == 0, (rest, errors)
    lines = rest.splitlines()
    assert any(f"leaf part:pen_rod attached {LEAF_PEN}" in line for line in lines)
    assert any(f"leaf part:cone_gear succeeded {LEAF_CONE}" in line for line in lines)
    assert any(" end succeeded exit_code=0 " in line for line in lines), lines
    final = json.loads(lines[-1])
    assert final["state"] == "succeeded"
    assert final["outputs"] == _record(Path(running["done"]))["outputs"]


def test_watch_exits_failed_with_the_cause_of_each_task_error(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    # Codex on #1125: a local fault (Temporal connection, protocol) fails the
    # task while its workflow keeps running on the farm.
    farm_state = Path(fixture["farm_state"])
    farm_state.write_text(
        json.dumps({LEAF_PEN: {"status": "RUNNING"}}), encoding="utf-8"
    )
    printed = tmp_path / "failing lines.txt"
    printed.write_text(DISPATCH_LINES + FAILURE_LINES, encoding="utf-8")
    environment = dict(fixture["environment"])
    environment["UV_STUB_LINES"] = str(printed)
    environment["UV_STUB_EXIT"] = "2"
    launched = _run_launcher(
        fixture, _command(fixture, "part:pen_rod", tag="broken"), environment
    )
    assert launched.returncode == 2

    watch = _run_launcher(
        fixture,
        _tracking(fixture, "-Watch", "-Tag", "broken", "-PollSeconds", "1"),
        fixture["environment"],
    )

    assert watch.returncode == 20, watch.stdout
    assert f"leaf part:pen_rod failed {LEAF_PEN}" in watch.stdout
    assert (
        "error part:pen_rod: RuntimeError: part:pen_rod failed on swmaker000005@5 "
        "[task_failed] exit 2: boom"
    ) in watch.stdout
    final = json.loads(watch.stdout.splitlines()[-1])
    assert final["state"] == "failed"
    assert final["exit_code"] == 2
    assert final["task_errors"] == ["part:pen_rod"]
    assert final["in_flight_workflows"] == []
    assert final["unsettled_workflows"] == [LEAF_PEN]

    done_before = Path(final["done"]).read_bytes()

    cancel = _run_launcher(
        fixture,
        _tracking(fixture, "-Cancel", "-Tag", "broken", "-Why", "local fault"),
        fixture["environment"],
    )

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    assert "already finished: failed" in cancel.stdout
    outcomes = [
        json.loads(line) for line in cancel.stdout.splitlines() if line.startswith("{")
    ]
    assert [(o["workflow_id"], o["outcome"]) for o in outcomes] == [
        (LEAF_PEN, "cancelled")
    ]
    assert json.loads(farm_state.read_text(encoding="utf-8"))[LEAF_PEN]["status"] == (
        "CANCELED"
    )
    # The launcher's own outcome stands.
    assert Path(final["done"]).read_bytes() == done_before


def test_cancel_keeps_a_leaf_a_sibling_attached_to_mid_cancel(tmp_path: Path) -> None:
    """Codex on #1125 (81928f376): siblings were enumerated once, before the
    farm queries; one that attached after that scan lost the leaf."""
    fixture = _launcher_fixture(tmp_path)
    farm_state = Path(fixture["farm_state"])
    farm_state.write_text(
        json.dumps({LEAF_PEN: {"status": "RUNNING"}}), encoding="utf-8"
    )
    printed = tmp_path / "failing lines.txt"
    printed.write_text(DISPATCH_LINES + FAILURE_LINES, encoding="utf-8")
    environment = dict(fixture["environment"])
    environment["UV_STUB_LINES"] = str(printed)
    environment["UV_STUB_EXIT"] = "2"
    launched = _run_launcher(
        fixture, _command(fixture, "part:pen_rod", tag="broken"), environment
    )
    assert launched.returncode == 2
    # This run created LEAF_PEN. Build the sibling's record now, then take it
    # out of the directory: it appears only once -Cancel queries the farm.
    sibling = _sibling_waiting_on(fixture, LEAF_PEN)
    staged = sibling.read_text(encoding="utf-8")
    sibling.unlink()
    workflows = json.loads(farm_state.read_text(encoding="utf-8"))
    workflows[LEAF_PEN]["_attach"] = {"path": str(sibling), "record": staged}
    farm_state.write_text(json.dumps(workflows), encoding="utf-8")

    cancel = _run_launcher(
        fixture,
        _tracking(fixture, "-Cancel", "-Tag", "broken", "-Why", "local fault"),
        fixture["environment"],
    )

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    assert sibling.exists()
    outcomes = [
        json.loads(line) for line in cancel.stdout.splitlines() if line.startswith("{")
    ]
    assert [(o["workflow_id"], o["outcome"]) for o in outcomes] == [
        (LEAF_PEN, "kept-shared")
    ]
    assert json.loads(farm_state.read_text(encoding="utf-8"))[LEAF_PEN]["status"] == (
        "RUNNING"
    )
    assert not Path(fixture["farm_cancels"]).exists()


def test_cancel_takes_a_leaf_whose_sibling_finished_mid_cancel(tmp_path: Path) -> None:
    """Codex on #1125 (6c35279e1): siblings scanned before the farm queries
    kept their leaves on that cached answer, so a sibling that finished (its
    own local failure) while -Cancel asked the farm left the leaf RUNNING
    with no run waiting on it."""
    fixture = _launcher_fixture(tmp_path)
    farm_state = Path(fixture["farm_state"])
    farm_state.write_text(
        json.dumps({LEAF_PEN: {"status": "RUNNING"}}), encoding="utf-8"
    )
    printed = tmp_path / "failing lines.txt"
    printed.write_text(DISPATCH_LINES + FAILURE_LINES, encoding="utf-8")
    environment = dict(fixture["environment"])
    environment["UV_STUB_LINES"] = str(printed)
    environment["UV_STUB_EXIT"] = "2"
    launched = _run_launcher(
        fixture, _command(fixture, "part:pen_rod", tag="broken"), environment
    )
    assert launched.returncode == 2
    # The sibling waits on LEAF_PEN when -Cancel starts, and fails while
    # -Cancel queries the farm.
    sibling = _record(_sibling_waiting_on(fixture, LEAF_PEN))
    finished = {**sibling, "state": "failed", "exit_code": 2}
    workflows = json.loads(farm_state.read_text(encoding="utf-8"))
    workflows[LEAF_PEN]["_attach"] = {
        "path": sibling["done"],
        "record": json.dumps(finished),
    }
    farm_state.write_text(json.dumps(workflows), encoding="utf-8")

    cancel = _run_launcher(
        fixture,
        _tracking(fixture, "-Cancel", "-Tag", "broken", "-Why", "local fault"),
        fixture["environment"],
    )

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    outcomes = [
        json.loads(line) for line in cancel.stdout.splitlines() if line.startswith("{")
    ]
    assert [(o["workflow_id"], o["outcome"]) for o in outcomes] == [
        (LEAF_PEN, "cancelled")
    ]
    # The sibling finished before the leaf was decided, not after.
    assert Path(sibling["done"]).exists()
    assert json.loads(farm_state.read_text(encoding="utf-8"))[LEAF_PEN]["status"] == (
        "CANCELED"
    )


def _write_run_record(
    fixture: dict[str, object],
    *,
    pid: int,
    tag: str,
    workflow: str,
    argv: list[str],
    hexdigit: str,
    started: float | None = None,
) -> Path:
    """A run record as the launcher writes one, waiting on ``workflow``, whose
    launcher is ``pid``; started at ``started`` (epoch seconds), else now."""
    started = time.time() if started is None else started
    log_directory = Path(fixture["log_directory"])
    log_directory.mkdir(exist_ok=True)
    run_id = (
        time.strftime("%Y%m%dT%H%M%S000Z", time.gmtime(started)) + "-" + hexdigit * 32
    )
    log = log_directory / f"{run_id}.log"
    log.write_text(
        f"  --  [ 1.0s + 1.0s] Farm workflow attached: {workflow}\n", encoding="utf-8"
    )
    record = {
        "run_id": run_id,
        "state": "running",
        "worktree": str(fixture["worktree"]),
        "pool_home": str(fixture["pool"]),
        "commit": "0" * 40,
        "targets": ["part:crank_hub"],
        "leaf_timeout_minutes": 90,
        # The launcher's round-trip form: 100 ns ticks.
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(started))
        + f".{int(started % 1 * 1e7):07d}Z",
        "pid": pid,
        "log": str(log),
        "done": str(log_directory / f"{run_id}.done"),
        "cache_environment": {},
        "tag": tag,
        "argv": argv,
        "snapshot": str(log_directory / "snapshots" / tag),
        "outputs": str(log_directory / f"{run_id}.out"),
        "environment": str(log_directory / "envs" / tag),
    }
    path = log_directory / f"{run_id}.run.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def _sibling_waiting_on(fixture: dict[str, object], workflow: str) -> Path:
    """A live run in the same LogDirectory that is waiting on ``workflow``.

    Its launcher PID is this test process, which started before the record.
    """
    return _write_run_record(
        fixture,
        pid=os.getpid(),
        tag="sibling",
        workflow=workflow,
        argv=[],
        hexdigit="e",
    )


def test_a_tag_and_the_list_order_runs_by_their_precise_start(tmp_path: Path) -> None:
    """Codex on #1125 (4243d95d2, 81928f376): run IDs carry the start to the
    millisecond, so two launches in one millisecond were ordered by their
    random suffix, both for -Tag and for -List's newest-first order."""
    fixture = _launcher_fixture(tmp_path)
    second = float(int(time.time()) - 10)
    # Same run-id timestamp; the older one's suffix sorts last by name.
    older = _write_run_record(
        fixture,
        pid=os.getpid(),
        tag="twin",
        workflow=LEAF_NUT,
        argv=[],
        hexdigit="f",
        started=second + 0.0002,
    )
    newer = _write_run_record(
        fixture,
        pid=os.getpid(),
        tag="twin",
        workflow=LEAF_NUT,
        argv=[],
        hexdigit="1",
        started=second + 0.0007,
    )

    status = _run_launcher(
        fixture, _tracking(fixture, "-Status", "-Tag", "twin"), fixture["environment"]
    )

    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["run_id"] == _record(newer)["run_id"]

    listed = _run_launcher(
        fixture, _tracking(fixture, "-List", "-Tag", "twin"), fixture["environment"]
    )

    assert listed.returncode == 0, listed.stderr
    assert [json.loads(line)["run_id"] for line in listed.stdout.splitlines()] == [
        _record(newer)["run_id"],
        _record(older)["run_id"],
    ]


def test_a_pid_reused_after_the_record_is_not_the_launcher(tmp_path: Path) -> None:
    """Codex on #1125 (4243d95d2): a process that took a dead launcher's PID
    within a second of its record counted as the launcher, and -Cancel would
    have killed it."""
    fixture = _launcher_fixture(tmp_path)
    started = time.time()
    reused = subprocess.Popen(
        [sys.executable, "-c", SLEEPER],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _write_run_record(
            fixture,
            pid=reused.pid,
            tag="reused",
            workflow=LEAF_NUT,
            argv=["uv", "-c", "pass"],
            hexdigit="7",
            started=started,
        )
        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-Tag", "reused"),
            fixture["environment"],
        )
        # This fixture has no pending start RPC: the workflow is stably absent.
        # Still exercise both not-found queries, without the farm's 30 s grace.
        _run_launcher(
            fixture,
            _tracking(
                fixture, "-Cancel", "-Tag", "reused", "-Why", "reused pid",
                "-SettleSeconds", "0",
            ),
            fixture["environment"],
        )
        survived = reused.poll() is None
    finally:
        reused.kill()
        reused.wait(timeout=HANG_GUARD_S)

    assert status.returncode == 0, status.stderr
    report = json.loads(status.stdout)
    assert report["state"] == "launcher-died"
    assert report["launcher"]["alive"] is False
    assert survived


def test_a_dead_run_from_an_older_launcher_breaks_neither_status_nor_cancel(
    tmp_path: Path,
) -> None:
    """Live farm probe on #1125 (f90a4c357): a record from a launcher that
    predates snapshots has no `snapshot`, `outputs` or `environment`. -Status
    on it crashed, and so did -Cancel on it and every -Cancel in the same
    directory, which scans it as a sibling."""
    fixture = _launcher_fixture(tmp_path)
    exited = subprocess.Popen([sys.executable, "-c", "pass"])
    exited.wait(timeout=HANG_GUARD_S)
    old = _write_run_record(
        fixture,
        pid=exited.pid,
        tag="old-launcher",
        workflow=LEAF_NUT,
        argv=["uv", "run", "python", "build.py"],
        hexdigit="3",
    )
    record = _record(old)
    del record["snapshot"], record["outputs"], record["environment"]
    old.write_text(json.dumps(record), encoding="utf-8")
    farm_state = Path(fixture["farm_state"])
    farm_state.write_text(
        json.dumps({LEAF_PEN: {"status": "RUNNING"}}), encoding="utf-8"
    )
    printed = tmp_path / "failing lines.txt"
    printed.write_text(DISPATCH_LINES + FAILURE_LINES, encoding="utf-8")
    failing = dict(fixture["environment"])
    failing["UV_STUB_LINES"] = str(printed)
    failing["UV_STUB_EXIT"] = "2"
    launched = _run_launcher(
        fixture, _command(fixture, "part:pen_rod", tag="broken"), failing
    )
    assert launched.returncode == 2

    status = _run_launcher(
        fixture,
        _tracking(fixture, "-Status", "-Tag", "old-launcher"),
        fixture["environment"],
    )
    cancel = _run_launcher(
        fixture,
        _tracking(fixture, "-Cancel", "-Tag", "broken", "-Why", "old sibling"),
        fixture["environment"],
    )

    assert status.returncode == 0, status.stderr
    report = json.loads(status.stdout)
    assert report["state"] == "launcher-died"
    assert report["launcher"]["orphaned_processes"] == []
    assert report["outputs"] is None
    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    outcomes = [
        json.loads(line) for line in cancel.stdout.splitlines() if line.startswith("{")
    ]
    assert [(o["workflow_id"], o["outcome"]) for o in outcomes] == [
        (LEAF_PEN, "cancelled")
    ]

    cancel_old = _run_launcher(
        fixture,
        _tracking(
            fixture,
            "-Cancel",
            "-Tag",
            "old-launcher",
            "-Why",
            "old run",
            "-SettleSeconds",
            "0",
        ),
        fixture["environment"],
    )

    assert cancel_old.returncode == 0, (cancel_old.stdout, cancel_old.stderr)
    done = _record(Path(record["done"]))
    assert done["state"] == "cancelled"
    assert done["outputs"] is None
    assert done["snapshot_removed"] is None
    assert [(o["workflow_id"], o["outcome"]) for o in done["cancel"]["workflows"]] == [
        (LEAF_NUT, "not-found")
    ]


SLEEPER = "__import__('time').sleep(120)"


@pytest.mark.parametrize(
    ("recorded_code", "names", "orphaned"),
    [
        # The recorded build command: the dead launcher's own child.
        (SLEEPER, None, True),
        # Codex on #1125 (d05cb04d9): a preparation or cleanup command (git
        # worktree add/remove, submodule update, uv sync) names the snapshot...
        ("__import__('time').sleep(121)", "snapshots/reused", True),
        # ...and uv venv names the run's private staging environment.
        ("__import__('time').sleep(121)", "envs/reused.staging-reused", True),
        # A different command under the same (dead) parent PID: not the run's.
        ("__import__('time').sleep(121)", None, False),
    ],
    ids=["build", "snapshot", "staging", "other"],
)
def test_an_orphan_must_name_the_run_on_its_command_line(
    tmp_path: Path, recorded_code: str, names: str | None, orphaned: bool
) -> None:
    """A dead launcher's PID is only a ParentProcessId now: any process that
    reused it could have left children. Only a command naming the run is its."""
    fixture = _launcher_fixture(tmp_path)
    log_directory = Path(fixture["log_directory"])
    log_directory.mkdir()
    extra = [] if names is None else [str(log_directory / names)]
    started = time.time()
    parent = subprocess.Popen(
        [
            sys._base_executable,
            "-c",
            "import json, os, subprocess, sys; "
            f"child = subprocess.Popen([sys._base_executable, '-c', {SLEEPER!r}, *{extra!r}], "
            "stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, "
            "stderr=subprocess.DEVNULL); "
            "print(json.dumps([os.getpid(), child.pid]), flush=True)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        output, errors = parent.communicate(timeout=HANG_GUARD_S)
    except BaseException:
        parent.kill()
        parent.communicate(timeout=HANG_GUARD_S)
        raise
    assert parent.returncode == 0, (output, errors)
    parent_pid, child = json.loads(output)
    # These stdlib-only collaborators use the base executable, not a venv
    # redirector: the retained handles identify the actual Python processes.
    assert parent_pid == parent.pid
    assert not _process_alive(parent_pid)

    # Keep this exact sleeper's handle: cleanup must not kill a different
    # process if the sleeper exits and its numeric PID is later reused.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x100001, False, child)  # SYNCHRONIZE | TERMINATE
    assert handle, ctypes.get_last_error()
    try:
        _write_run_record(
            fixture,
            pid=parent_pid,
            tag="reused",
            workflow=LEAF_NUT,
            argv=["uv", "-c", recorded_code],
            hexdigit="7",
            started=started,
        )
        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-Tag", "reused"),
            fixture["environment"],
        )
    finally:
        try:
            # TerminateProcess may report it already exited; waiting on the
            # retained handle checks completion without reopening its PID.
            kernel32.TerminateProcess(handle, 1)
            assert kernel32.WaitForSingleObject(handle, HANG_GUARD_S * 1000) == 0
        finally:
            kernel32.CloseHandle(handle)

    assert status.returncode == 0, status.stderr
    report = json.loads(status.stdout)
    assert report["state"] == "launcher-died"
    assert (child in report["launcher"]["orphaned_processes"]) is orphaned


def test_cancel_finds_a_build_whose_launcher_and_uv_both_died(
    tmp_path: Path,
) -> None:
    """Codex on #1125 (b8a08b2b9): `uv run` does not take its python with it
    (checked: killing uv leaves both python.exe processes running), so once the
    launcher and then uv are gone, no scan from the launcher reaches the build,
    which keeps dispatching. The run's job still holds it."""
    fixture = _launcher_fixture(tmp_path)
    Path(fixture["farm_state"]).write_text(
        json.dumps(
            {LEAF_PEN: {"status": "RUNNING"}, LEAF_CONE: {"status": "COMPLETED"}}
        ),
        encoding="utf-8",
    )
    process, release, running = _start_held(tmp_path, fixture, DISPATCH_LINES, "chain")
    build = int(_record(Path(fixture["invocation"]))["pid"])
    # launcher -> uv.cmd's cmd.exe -> venv python.exe -> build. The venv
    # launcher takes its child down with it; cmd.exe, like uv.exe, does not.
    shim = int(
        subprocess.run(
            [
                "pwsh",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Process -Filter "
                f"'ProcessId={_record(Path(fixture['invocation']))['ppid']}').ParentProcessId",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )
    try:
        process.kill()
        process.wait(timeout=HANG_GUARD_S)
        process.stdout.close()
        process.stderr.close()
        # The uv between them dies too (os.kill is TerminateProcess here).
        os.kill(shim, 9)
        deadline = time.monotonic() + 10
        while _process_alive(shim) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _process_alive(shim)
        assert _process_alive(build)

        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-RunId", running["run_id"]),
            fixture["environment"],
        )
        cancel = _run_launcher(
            fixture,
            _tracking(fixture, "-Cancel", "-RunId", running["run_id"], "-Why", "chain"),
            fixture["environment"],
        )
        survived = _process_alive(build)
    finally:
        release.touch()

    assert status.returncode == 0, status.stderr
    assert build in json.loads(status.stdout)["launcher"]["orphaned_processes"]
    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    assert not survived, "the build outlived -Cancel"
    done = _record(Path(running["done"]))
    assert {w["workflow_id"]: w["outcome"] for w in done["cancel"]["workflows"]} == {
        LEAF_PEN: "cancelled"
    }


def test_a_dead_launcher_is_reported_and_its_orphaned_leaves_cancelled(
    tmp_path: Path,
) -> None:
    """2026-09-28: a launcher killed mid-run wrote no .done, its record still said
    `running`, and a watcher waiting for .done sat silent for 35 min."""
    fixture = _launcher_fixture(tmp_path)
    lines = (
        DISPATCH_LINES
        + f"  --  [   61.0s +  1.0s] Farm workflow requested: {LEAF_NUT}\n"
        + f"  --  [   61.0s +  1.0s] Farm workflow requested: {LEAF_SHARED}\n"
        + f"  --  [   61.1s +  0.1s] Farm workflow attached: {LEAF_SHARED}\n"
        + f"  --  [   61.2s +  0.1s] Farm workflow requested: {LEAF_FOREIGN}\n"
        + f"  --  [   61.3s +  0.1s] Farm workflow attached: {LEAF_FOREIGN}\n"
        + f"  --  [   61.4s +  0.1s] Farm workflow requested: {LEAF_RACED}\n"
        + f"  --  [   61.5s +  0.1s] Farm workflow attached: {LEAF_RACED}\n"
    )
    farm_state = Path(fixture["farm_state"])
    farm_state.write_text(
        json.dumps(
            {
                # The farm cannot be reached for this one on the first try.
                LEAF_PEN: {"status": "UNREACHABLE"},
                LEAF_CONE: {"status": "COMPLETED"},
                LEAF_SHARED: {"status": "RUNNING"},
                # Created by a submitter outside farm-run.ps1, and reported by
                # a farm.py too old to say so; this run attached to both.
                LEAF_FOREIGN: {"status": "RUNNING", "_old": True},
                # Codex on #1125 (79d706547): this run logged its request, its
                # start failed, and a sibling run created the workflow.
                LEAF_RACED: {"status": "RUNNING", "farm_run": "sibling-run"},
            }
        ),
        encoding="utf-8",
    )
    process, release, running = _start_held(tmp_path, fixture, lines, "orphaned")
    build = _stub_pid(fixture)
    try:
        # The harness kills the launcher alone; the build it started lives on.
        process.kill()
        # The orphan inherited the launcher's pipes, so they never reach EOF.
        process.wait(timeout=HANG_GUARD_S)
        process.stdout.close()
        process.stderr.close()
        assert _process_alive(build)
        _sibling_waiting_on(fixture, LEAF_SHARED)

        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-RunId", running["run_id"]),
            fixture["environment"],
        )
        assert status.returncode == 0, status.stderr
        report = json.loads(status.stdout)
        assert report["state"] == "launcher-died"
        assert report["launcher"]["alive"] is False
        assert build in report["launcher"]["orphaned_processes"]
        assert report["in_flight_workflows"] == [
            LEAF_PEN,
            LEAF_NUT,
            LEAF_SHARED,
            LEAF_FOREIGN,
            LEAF_RACED,
        ]

        watch = _run_launcher(
            fixture,
            _tracking(fixture, "-Watch", "-Tag", "orphaned", "-PollSeconds", "1"),
            fixture["environment"],
        )
        assert watch.returncode == 21, watch.stdout
        assert "LAUNCHER DIED" in watch.stdout

        cancel_command = _tracking(
            fixture,
            "-Cancel",
            "-Tag",
            "orphaned",
            "-Why",
            "launcher died",
            "-SettleSeconds",
            "0",
        )
        refused = _run_launcher(fixture, cancel_command, fixture["environment"])
        # A leaf it could not account for keeps the run retryable: the orphan
        # is stopped, but no .done, no cleanup, still launcher-died.
        assert refused.returncode == 1, (refused.stdout, refused.stderr)
        assert "failed to connect to the farm" in refused.stderr
        assert not _process_alive(build)
        assert not Path(running["done"]).exists()
        assert Path(running["snapshot"]).exists()
        assert not Path(fixture["farm_cancels"]).exists()
        again_status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-RunId", running["run_id"]),
            fixture["environment"],
        )
        assert json.loads(again_status.stdout)["state"] == "launcher-died"

        workflows = json.loads(farm_state.read_text(encoding="utf-8"))
        workflows[LEAF_PEN]["status"] = "RUNNING"
        farm_state.write_text(json.dumps(workflows), encoding="utf-8")
        cancel = _run_launcher(fixture, cancel_command, fixture["environment"])
    finally:
        release.touch()

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    assert not _process_alive(build)
    done = _record(Path(running["done"]))
    assert done["state"] == "cancelled"
    assert done["exit_code"] is None
    assert done["cancel"]["launcher"] == "launcher-died"
    # The refused first attempt already stopped the orphan.
    assert done["cancel"]["stopped_pids"] == []
    assert {w["workflow_id"]: w["outcome"] for w in done["cancel"]["workflows"]} == {
        LEAF_PEN: "cancelled",
        LEAF_NUT: "not-found",
        LEAF_SHARED: "kept-shared",
        LEAF_FOREIGN: "kept-foreign",
        LEAF_RACED: "kept-foreign",
    }
    cancels = [
        json.loads(line)
        for line in Path(fixture["farm_cancels"])
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [entry["argv"] for entry in cancels] == [
        [
            "cancel",
            "--why",
            f"launcher died (farm-run.ps1 -Cancel {running['run_id']})",
            LEAF_PEN,
        ]
    ]
    assert cancels[0]["VIRTUAL_ENV"] is None
    # The cleanup the dead launcher never ran: outputs kept, snapshot gone.
    assert done["outputs_preserved"] is True
    assert (Path(done["outputs"]) / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"
    assert not Path(running["snapshot"]).exists()

    # LEAF_NUT remains absent in the synchronous fixture; no start can land
    # during the production grace period on this idempotent cancellation.
    again = _run_launcher(
        fixture,
        _tracking(
            fixture, "-Cancel", "-RunId", running["run_id"], "-Why", "twice",
            "-SettleSeconds", "0",
        ),
        fixture["environment"],
    )
    assert again.returncode == 0
    assert "already finished: cancelled" in again.stdout
    watch = _run_launcher(
        fixture,
        _tracking(fixture, "-Watch", "-RunId", running["run_id"], "-PollSeconds", "1"),
        fixture["environment"],
    )
    assert watch.returncode == 22


def test_cancel_stops_a_live_launcher_and_its_build_before_cancelling_leaves(
    tmp_path: Path,
) -> None:
    fixture = _launcher_fixture(tmp_path)
    Path(fixture["farm_state"]).write_text(
        json.dumps(
            {LEAF_PEN: {"status": "RUNNING"}, LEAF_CONE: {"status": "COMPLETED"}}
        ),
        encoding="utf-8",
    )
    process, release, running = _start_held(tmp_path, fixture, DISPATCH_LINES, "live")
    build = _stub_pid(fixture)
    try:
        cancel = _run_launcher(
            fixture,
            _tracking(
                fixture, "-Cancel", "-RunId", running["run_id"], "-Why", "superseded"
            ),
            fixture["environment"],
        )
        process.communicate(timeout=HANG_GUARD_S)
    finally:
        release.touch()

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    # Killed, not finished: the launcher never reached its own terminal record.
    assert process.returncode != 0
    assert not _process_alive(build)
    done = _record(Path(running["done"]))
    assert done["state"] == "cancelled"
    assert done["cancel"]["launcher"] == "running"
    assert done["cancel"]["stopped_pids"][0] == running["pid"]
    assert build in done["cancel"]["stopped_pids"]
    assert {w["workflow_id"]: w["outcome"] for w in done["cancel"]["workflows"]} == {
        LEAF_PEN: "cancelled"
    }
    farm = json.loads(Path(fixture["farm_state"]).read_text(encoding="utf-8"))
    assert {workflow: farm[workflow]["status"] for workflow in farm} == {
        LEAF_PEN: "CANCELED",
        LEAF_CONE: "COMPLETED",
    }
    assert not Path(running["snapshot"]).exists()


def test_cancel_asks_again_about_a_leaf_the_farm_had_not_committed_yet(
    tmp_path: Path,
) -> None:
    """Codex on #1125 (1bf36d088): the request record is written before the
    start RPC, so a build killed mid-RPC names a workflow the farm reports
    absent for a moment and then runs. Not-found must not settle it early."""
    fixture = _launcher_fixture(tmp_path)
    Path(fixture["farm_state"]).write_text(
        json.dumps(
            {
                LEAF_PEN: {"status": "COMPLETED"},
                LEAF_NUT: {"status": "RUNNING", "_absent_for": 1},
            }
        ),
        encoding="utf-8",
    )
    process, release, running = _start_held(
        tmp_path, fixture, DISPATCH_LINES, "landing", {"UV_STUB_UNLOGGED": LEAF_NUT}
    )
    try:
        cancel = _run_launcher(
            fixture,
            _tracking(
                fixture,
                "-Cancel",
                "-RunId",
                running["run_id"],
                "-Why",
                "mid-rpc",
                "-SettleSeconds",
                "2",
            ),
            fixture["environment"],
        )
        process.communicate(timeout=HANG_GUARD_S)
    finally:
        release.touch()

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    assert f"not-found {LEAF_NUT}" in cancel.stdout
    done = _record(Path(running["done"]))
    assert {w["workflow_id"]: w["outcome"] for w in done["cancel"]["workflows"]} == {
        LEAF_PEN: "already-closed",
        LEAF_NUT: "cancelled",
    }
    farm = json.loads(Path(fixture["farm_state"]).read_text(encoding="utf-8"))
    assert farm[LEAF_NUT]["status"] == "CANCELED"


def test_watch_prints_a_request_record_that_sorts_ahead_of_printed_ones(
    tmp_path: Path,
) -> None:
    """Codex on #1125 (1bf36d088): request-record events are rebuilt in file
    name order each poll, so a positional cursor skipped a new one that
    sorted first and printed an old one again."""
    fixture = _launcher_fixture(tmp_path)
    process, release, running = _start_held(
        tmp_path, fixture, DISPATCH_LINES, "reorder", {"UV_STUB_UNLOGGED": LEAF_NUT}
    )
    try:
        watch = subprocess.Popen(
            _tracking(
                fixture, "-Watch", "-RunId", running["run_id"], "-PollSeconds", "1"
            ),
            env=fixture["environment"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        printed = []
        while not any(LEAF_NUT in line for line in printed):
            line = watch.stdout.readline()
            assert line, "watch ended before printing the recorded request"
            printed.append(line)
        # A dispatch the log has not caught up with, named to sort first.
        (Path(running["requests"]) / "0000.json").write_text(
            json.dumps({"task": "part:cam_follower", "workflow_id": LEAF_EARLY}),
            encoding="utf-8",
        )
        time.sleep(2.5)  # two -Watch polls
        release.touch()
        rest, errors = watch.communicate(timeout=HANG_GUARD_S)
    finally:
        release.touch()
        process.communicate(timeout=HANG_GUARD_S)

    lines = printed + rest.splitlines()
    assert watch.returncode == 0, (lines, errors)
    assert (
        sum(f"leaf part:cam_follower requested {LEAF_EARLY}" in x for x in lines) == 1
    )
    assert sum(f"requested {LEAF_NUT}" in x for x in lines) == 1, lines


def test_cancel_finds_a_leaf_whose_request_never_reached_the_log(
    tmp_path: Path,
) -> None:
    """Codex on #1125 (f90a4c357): -Cancel stops the launcher, the only copy
    of the build's output into the log, so a `Farm workflow requested` line
    still in that pipe was lost while its workflow kept running."""
    fixture = _launcher_fixture(tmp_path)
    Path(fixture["farm_state"]).write_text(
        json.dumps({LEAF_PEN: {"status": "RUNNING"}, LEAF_NUT: {"status": "RUNNING"}}),
        encoding="utf-8",
    )
    process, release, running = _start_held(
        tmp_path, fixture, DISPATCH_LINES, "unlogged", {"UV_STUB_UNLOGGED": LEAF_NUT}
    )
    try:
        assert LEAF_NUT not in Path(running["log"]).read_text(encoding="utf-8")
        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-RunId", running["run_id"]),
            fixture["environment"],
        )
        cancel = _run_launcher(
            fixture,
            _tracking(
                fixture, "-Cancel", "-RunId", running["run_id"], "-Why", "lost line"
            ),
            fixture["environment"],
        )
        process.communicate(timeout=HANG_GUARD_S)
    finally:
        release.touch()

    assert status.returncode == 0, status.stderr
    assert LEAF_NUT in json.loads(status.stdout)["in_flight_workflows"]
    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    done = _record(Path(running["done"]))
    assert {w["workflow_id"]: w["outcome"] for w in done["cancel"]["workflows"]} == {
        LEAF_PEN: "cancelled",
        LEAF_NUT: "cancelled",
    }
    farm = json.loads(Path(fixture["farm_state"]).read_text(encoding="utf-8"))
    assert farm[LEAF_NUT]["status"] == "CANCELED"


def test_cancel_keeps_outputs_the_launcher_moved_before_it_died(
    tmp_path: Path,
) -> None:
    """Codex on #1125: a launcher stopped after moving cad/out to <run-id>.out
    but before writing .done must not leave the cancelled run's outputs null."""
    fixture = _launcher_fixture(tmp_path)
    process, release, running = _start_held(tmp_path, fixture, DISPATCH_LINES, "race")
    try:
        process.kill()
        process.wait(timeout=HANG_GUARD_S)
        process.stdout.close()
        process.stderr.close()
        # The launcher's own first cleanup step, done before it was stopped.
        (Path(running["snapshot"]) / "cad" / "out").rename(running["outputs"])
        status = _run_launcher(
            fixture,
            _tracking(fixture, "-Status", "-Tag", "race"),
            fixture["environment"],
        )
        # The synchronous fixture never created these workflows; publication
        # recovery does not need the real farm's pending-start grace period.
        cancel = _run_launcher(
            fixture,
            _tracking(
                fixture, "-Cancel", "-Tag", "race", "-Why", "raced cleanup",
                "-SettleSeconds", "0",
            ),
            fixture["environment"],
        )
    finally:
        release.touch()

    assert status.returncode == 0, status.stderr
    reported = json.loads(status.stdout)
    assert reported["state"] == "launcher-died"
    assert reported["outputs"] == running["outputs"]

    assert cancel.returncode == 0, (cancel.stdout, cancel.stderr)
    done = _record(Path(running["done"]))
    assert done["state"] == "cancelled"
    assert done["outputs"] == running["outputs"]
    assert done["outputs_preserved"] is True
    assert (Path(done["outputs"]) / "reports" / "stub-output.txt").read_text(
        encoding="utf-8"
    ) == "built\n"
    assert not Path(running["snapshot"]).exists()


def test_list_filters_runs_by_tag_and_state_newest_first(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    assert (
        _run_launcher(
            fixture,
            _command(fixture, "part:pen_rod", tag="alpha"),
            fixture["environment"],
        ).returncode
        == 0
    )
    failing = dict(fixture["environment"])
    failing["UV_STUB_EXIT"] = "2"
    assert (
        _run_launcher(
            fixture, _command(fixture, "part:pen_rod", tag="beta"), failing
        ).returncode
        == 2
    )

    def listed(*args: str) -> list[dict[str, object]]:
        result = _run_launcher(
            fixture, _tracking(fixture, "-List", *args), fixture["environment"]
        )
        assert result.returncode == 0, result.stderr
        return [json.loads(line) for line in result.stdout.splitlines()]

    assert [(run["tag"], run["state"]) for run in listed()] == [
        ("beta", "failed"),
        ("alpha", "succeeded"),
    ]
    assert [run["tag"] for run in listed("-Tag", "alpha")] == ["alpha"]
    assert [run["tag"] for run in listed("-State", "failed")] == ["beta"]
    assert listed("-State", "running") == []


@pytest.mark.parametrize(
    ("args", "diagnostic"),
    [
        (("-Status",), "-Status needs -RunId or -Tag"),
        (("-Watch", "-Tag", "nothing"), "no run tagged 'nothing'"),
    ],
)
def test_tracking_refuses_an_unselected_or_unknown_run(
    tmp_path: Path, args: tuple[str, ...], diagnostic: str
) -> None:
    fixture = _launcher_fixture(tmp_path)
    Path(fixture["log_directory"]).mkdir()

    result = _run_launcher(fixture, _tracking(fixture, *args), fixture["environment"])

    assert result.returncode == 2
    assert diagnostic in result.stderr


def test_tracking_resolves_a_drive_root_log_directory(tmp_path: Path) -> None:
    fixture = _launcher_fixture(tmp_path)
    fixture["log_directory"] = Path(tmp_path.anchor)

    result = _run_launcher(
        fixture, _tracking(fixture, "-Status"), fixture["environment"]
    )

    # Resolution must succeed before the read-only selector validation, without
    # creating files at the drive root or starting a farm build.
    assert result.returncode == 2
    assert "-Status needs -RunId or -Tag" in result.stderr

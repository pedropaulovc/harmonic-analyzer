"""Real-process admission and failure behavior, with no farm or SolidWorks."""

import json
import os
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _local_check

# Hang guards only: no assertion measures elapsed time. Every ordering below is
# proven by a pipe or file event, so a saturated host can only slow the test.
HANG_GUARD_S = 300


@pytest.fixture
def check_env(tmp_path, monkeypatch):
    # Never contend with the enclosing recipe gate or another developer's run.
    monkeypatch.delenv("HARMONIC_LOCAL_CHECK_LOCK", raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "host"))
    monkeypatch.setenv("HARMONIC_LOCAL_CHECK_CPU_SLOTS", "1")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "")
    monkeypatch.setenv("HARMONIC_VERBOSITY", "error")
    return os.environ.copy()


def _start(cmd, cwd, env):
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8",
    )
    lines = queue.Queue()
    errors = queue.Queue()
    proc.stderr_lines = queue.Queue()

    def drain():
        for line in proc.stdout:
            lines.put(line.strip())
        lines.put("<exited>")

    def drain_errors():
        # wait() cannot complete if the child fills an unread stderr pipe.
        # Keep diagnostics separate from stdout's readiness protocol.
        chunks = []
        for line in proc.stderr:
            chunks.append(line)
            proc.stderr_lines.put(line)
        proc.stderr_lines.put(None)
        errors.put("".join(chunks))

    proc._capture_readers = (
        threading.Thread(target=drain, name="local-check-stdout", daemon=True),
        threading.Thread(target=drain_errors, name="local-check-stderr", daemon=True),
    )
    for reader in proc._capture_readers:
        reader.start()
    return proc, lines, errors


def _await_refusal(proc, lines):
    """Block until a contender reports a refused admission pass."""
    # The runner logs its first refused pass at once. Unlike a sub-second
    # silence window, this cannot pass before the contender has even started.
    while True:
        line = proc.stderr_lines.get(timeout=HANG_GUARD_S)
        assert line is not None, "contender exited before reporting a refusal"
        assert " admitted " not in line, f"contender admitted while slots were held: {line}"
        if "waiting for CPU slots" in line:
            break
    # Readiness is printed only after admission, so it must still be absent.
    with pytest.raises(queue.Empty):
        lines.get_nowait()


def _stop(proc):
    proc.stdin.close()
    try:
        proc.wait(timeout=HANG_GUARD_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=HANG_GUARD_S)
    # A process exit does not mean its readers have consumed EOF yet.
    # Join before closing either stream, including when a reader started late.
    deadline = time.monotonic() + HANG_GUARD_S
    for reader in proc._capture_readers:
        reader.join(timeout=max(0, deadline - time.monotonic()))
    assert not any(reader.is_alive() for reader in proc._capture_readers), (
        "local-check capture readers did not stop after process exit"
    )
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        stream.close()


def test_released_check_completes_with_stderr_larger_than_pipe_capacity(tmp_path, check_env):
    """Completion must drain stderr without mixing it into readiness lines."""
    script = tmp_path / "noisy_check.py"
    script.write_text(
        "import os, sys\n"
        "print(os.getpid(), flush=True)\n"
        "sys.stdin.read(1)\n"
        "sys.stderr.write('teardown stderr\\n' * 131072)\n"
        "sys.stderr.flush()\n"
        "raise SystemExit(7)\n",
        encoding="utf-8",
    )
    proc, lines, errors = _start(
        _local_check.command([sys.executable, str(script)], "check:noisy"),
        tmp_path, check_env,
    )
    try:
        int(lines.get(timeout=HANG_GUARD_S))
        proc.stdin.write("x")
        proc.stdin.flush()
        assert proc.wait(timeout=HANG_GUARD_S) == 7, errors.get(timeout=HANG_GUARD_S)
        assert errors.get(timeout=HANG_GUARD_S).endswith("teardown stderr\n" * 131072)
    finally:
        _stop(proc)


def test_separate_checkouts_share_admission_until_running_check_exits(tmp_path, check_env):
    commands = []
    for name in ("checkout-a", "checkout-b"):
        checkout = tmp_path / name
        checkout.mkdir()
        # Each checkout has its own runner; only the host lock is shared.
        runner = checkout / "_local_check.py"
        shutil.copyfile(_local_check.__file__, runner)
        script = checkout / "check.py"
        script.write_text(
            "import os, sys\nprint(os.getpid(), flush=True)\n"
            "sys.stdin.read(1)\n", encoding="utf-8",
        )
        commands.append(([sys.executable, str(runner), "check:fixture", str(script)], checkout))
    check_env["HARMONIC_VERBOSITY"] = "info"
    check_env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(_local_check.__file__).parent), check_env.get("PYTHONPATH", "")]
    )
    first, first_lines, first_errors = _start(*commands[0], check_env)
    second = None
    try:
        # Windows venv executables may redirect to a different interpreter PID.
        first_pid = int(first_lines.get(timeout=HANG_GUARD_S))
        second, second_lines, second_errors = _start(*commands[1], check_env)
        _await_refusal(second, second_lines)
        first.stdin.write("x")
        first.stdin.flush()
        assert first.wait(timeout=HANG_GUARD_S) == 0, first_errors.get(timeout=HANG_GUARD_S)
        assert int(second_lines.get(timeout=HANG_GUARD_S)) != first_pid
        second.stdin.write("x")
        second.stdin.flush()
        assert second.wait(timeout=HANG_GUARD_S) == 0, second_errors.get(timeout=HANG_GUARD_S)
    finally:
        _stop(first)
        if second is not None:
            _stop(second)


def test_killed_check_releases_admission(tmp_path, check_env):
    script = tmp_path / "hold.py"
    script.write_text("import os, sys\nprint(os.getpid(), flush=True)\nsys.stdin.read(1)\n", encoding="utf-8")
    cmd = _local_check.command([sys.executable, str(script)], "check:fixture")
    proc, lines, _ = _start(cmd, tmp_path, check_env)
    try:
        owner_pid = int(lines.get(timeout=HANG_GUARD_S))
        os.kill(owner_pid, signal.SIGTERM)
        proc.wait(timeout=HANG_GUARD_S)
        result = subprocess.run(cmd, cwd=tmp_path, env=check_env, input="x", capture_output=True, text=True, timeout=HANG_GUARD_S)
        assert result.returncode == 0, result.stderr
        assert int(result.stdout.strip()) != owner_pid
    finally:
        _stop(proc)


@pytest.mark.parametrize("mode", ["script", "module"])
def test_failure_preserves_exit_status_and_does_not_stamp_success(tmp_path, check_env, monkeypatch, mode):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import dodo

    script = tmp_path / "failing_check.py"
    script.write_text(
        "import json, pathlib, sys\n"
        "pathlib.Path('received.json').write_text(json.dumps(sys.argv[1:]))\n"
        "raise SystemExit(7)\n", encoding="utf-8",
    )
    args = [str(script)] if mode == "script" else ["-m", "failing_check"]
    monkeypatch.setattr(dodo, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(dodo, "LOGS", tmp_path / "logs")
    stamp = tmp_path / "check.ok"
    with pytest.raises(RuntimeError):
        dodo._run_stamped([sys.executable, *args, "two words"], "check fixture", str(stamp), "check:fixture")
    assert not stamp.exists()
    assert json.loads((tmp_path / "received.json").read_text()) == ["two words"]
    result = subprocess.run(
        _local_check.command([sys.executable, *args], "check:fixture"),
        cwd=tmp_path, env=check_env, capture_output=True, text=True, timeout=HANG_GUARD_S,
    )
    assert result.returncode == 7, result.stderr


def test_successful_check_keeps_top_level_span_depth(tmp_path, check_env, monkeypatch):
    """Farm log attribution requires process-root spans to stay at depth zero."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    import dodo

    script = tmp_path / "traced_check.py"
    script.write_text(
        "import json, pathlib\n"
        "from opentelemetry import trace\n"
        "from opentelemetry.sdk.trace.export import SimpleSpanProcessor\n"
        "from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter\n"
        "import _telemetry\n"
        "exporter = InMemorySpanExporter()\n"
        "trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))\n"
        "with _telemetry.span('operation'):\n"
        "    pass\n"
        "span = exporter.get_finished_spans()[0]\n"
        "pathlib.Path('trace.json').write_text(json.dumps({\n"
        "    'depth': span.attributes['harmonic.depth'],\n"
        "    'parent': None if span.parent is None else span.parent.span_id,\n"
        "}))\n"
        "raise SystemExit(0)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dodo, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(dodo, "LOGS", tmp_path / "logs")
    stamp = tmp_path / "check.ok"
    dodo._run_stamped([sys.executable, str(script)], "check fixture", str(stamp), "check:fixture")
    assert stamp.is_file()
    assert json.loads((tmp_path / "trace.json").read_text()) == {"depth": 0, "parent": None}


@pytest.mark.parametrize("option_source", ["environment", "configuration"])
def test_serial_pytest_cannot_inherit_unbudgeted_workers(tmp_path, check_env, option_source):
    """Pytest environment/config defaults must not turn one slot into a pool."""
    check_env["PYTEST_ADDOPTS"] = "-n auto" if option_source == "environment" else ""
    check_env["PYTEST_XDIST_AUTO_NUM_WORKERS"] = "2"
    inherited = "--numprocesses=2" if option_source == "configuration" else ""
    (tmp_path / "pytest.ini").write_text(
        f"[pytest]\naddopts = {inherited}\n", encoding="utf-8",
    )
    worker_test = tmp_path / "test_serial.py"
    worker_test.write_text(
        "def test_serial(worker_id, request):\n"
        "    assert worker_id == 'master'\n"
        "    assert request.config.option.numprocesses == 0\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        _local_check.command(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "--", str(worker_test)],
            "check:serial",
        ),
        cwd=tmp_path, env=check_env, capture_output=True, text=True, timeout=HANG_GUARD_S,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("worker_args", [["-n", "8"], ["--numprocesses=auto"]])
def test_parallel_pytest_shares_remaining_slots_with_small_checks(tmp_path, check_env, worker_args):
    """Real xdist workers consume only free slots; small checks run alongside."""
    check_env["HARMONIC_LOCAL_CHECK_CPU_SLOTS"] = "3"
    # Explicit host capacity also governs auto when interpreter CPU counts differ.
    check_env["PYTHON_CPU_COUNT"] = "2"
    check_env["PYTEST_ADDOPTS"] = "-n auto"
    check_env["HARMONIC_VERBOSITY"] = "info"
    hold = tmp_path / "hold.py"
    hold.write_text(
        "import os, sys\nprint(os.getpid(), flush=True)\nsys.stdin.read(1)\n",
        encoding="utf-8",
    )
    worker_test = tmp_path / "test_workers.py"
    worker_test.write_text(
        "import os, pathlib, time, pytest\n"
        "@pytest.fixture(scope='session')\n"
        "def hold_worker(worker_id):\n"
        "    ready = pathlib.Path('.' + worker_id)\n"
        "    ready.write_text(os.environ['PYTEST_XDIST_WORKER_COUNT'])\n"
        "    ready.replace(worker_id)\n"
        f"    deadline = time.monotonic() + {HANG_GUARD_S}\n"
        "    while not pathlib.Path('release').exists():\n"
        "        assert time.monotonic() < deadline, 'worker release timed out'\n"
        "        time.sleep(0.05)\n"
        "@pytest.mark.parametrize('number', range(4))\n"
        "def test_work(hold_worker, number):\n"
        "    assert pathlib.Path('release').exists()\n",
        encoding="utf-8",
    )
    cmd = _local_check.command([sys.executable, str(hold)], "check:small")
    small, small_lines, small_errors = _start(cmd, tmp_path, check_env)
    parallel = None
    waiting = None
    blocker = None
    try:
        int(small_lines.get(timeout=HANG_GUARD_S))
        blocker, blocker_lines, blocker_errors = _start(cmd, tmp_path, check_env)
        int(blocker_lines.get(timeout=HANG_GUARD_S))
        parallel, parallel_lines, parallel_errors = _start(
            _local_check.command(
                [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                 *worker_args, str(worker_test)],
                "check:parallel",
            ),
            tmp_path, check_env,
        )
        # One free slot must not strand a long suite at one worker after
        # these short checks finish. Wait for a useful worker batch instead.
        _await_refusal(parallel, parallel_lines)
        assert not list(tmp_path.glob("gw*"))
        blocker.stdin.write("x")
        blocker.stdin.flush()
        assert blocker.wait(timeout=HANG_GUARD_S) == 0, blocker_errors.get(timeout=HANG_GUARD_S)
        deadline = time.monotonic() + HANG_GUARD_S
        while len(list(tmp_path.glob("gw*"))) < 2:
            assert parallel.poll() is None, parallel_errors.get(timeout=HANG_GUARD_S)
            assert time.monotonic() < deadline, "two admitted workers did not start"
            time.sleep(0.05)
        assert {p.name: p.read_text() for p in tmp_path.glob("gw*")} == {"gw0": "2", "gw1": "2"}
        waiting, waiting_lines, _ = _start(cmd, tmp_path, check_env)
        _await_refusal(waiting, waiting_lines)
        small.stdin.write("x")
        small.stdin.flush()
        assert small.wait(timeout=HANG_GUARD_S) == 0, small_errors.get(timeout=HANG_GUARD_S)
        int(waiting_lines.get(timeout=HANG_GUARD_S))
        # The small successor starts while the two xdist workers remain alive.
        assert parallel.poll() is None
        (tmp_path / "release").touch()
        assert parallel.wait(timeout=HANG_GUARD_S) == 0, parallel_errors.get(timeout=HANG_GUARD_S)
    finally:
        (tmp_path / "release").touch()
        for proc in (small, parallel, waiting, blocker):
            if proc is not None:
                _stop(proc)

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

from filelock import FileLock, Timeout
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _local_check


@pytest.fixture
def check_env(tmp_path, monkeypatch):
    # Never contend with the enclosing recipe gate or another developer's run.
    monkeypatch.delenv("HARMONIC_LOCAL_CHECK_LOCK", raising=False)
    monkeypatch.setenv("PROGRAMDATA", str(tmp_path / "host"))
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

    def drain():
        for line in proc.stdout:
            lines.put(line.strip())
        lines.put("<exited>")

    threading.Thread(target=drain, daemon=True).start()
    return proc, lines


def _stop(proc):
    proc.stdin.close()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        stream.close()


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
    check_env["PYTHONPATH"] = os.pathsep.join(
        [str(Path(_local_check.__file__).parent), check_env.get("PYTHONPATH", "")]
    )
    first, first_lines = _start(*commands[0], check_env)
    second = None
    try:
        # Windows venv executables may redirect to a different interpreter PID.
        first_pid = int(first_lines.get(timeout=30))
        with pytest.raises(Timeout):
            FileLock(_local_check.lock_path()).acquire(timeout=0)
        second, second_lines = _start(*commands[1], check_env)
        with pytest.raises(queue.Empty):
            second_lines.get(timeout=0.5)
        first.stdin.write("x")
        first.stdin.flush()
        assert first.wait(timeout=30) == 0, first.stderr.read()
        assert int(second_lines.get(timeout=30)) != first_pid
        second.stdin.write("x")
        second.stdin.flush()
        assert second.wait(timeout=30) == 0, second.stderr.read()
    finally:
        _stop(first)
        if second is not None:
            _stop(second)


def test_killed_check_releases_admission(tmp_path, check_env):
    script = tmp_path / "hold.py"
    script.write_text("import os, sys\nprint(os.getpid(), flush=True)\nsys.stdin.read(1)\n", encoding="utf-8")
    cmd = _local_check.command([sys.executable, str(script)], "check:fixture")
    proc, lines = _start(cmd, tmp_path, check_env)
    try:
        owner_pid = int(lines.get(timeout=30))
        os.kill(owner_pid, signal.SIGTERM)
        proc.wait(timeout=30)
        with FileLock(_local_check.lock_path()).acquire(timeout=1):
            pass
        result = subprocess.run(cmd, cwd=tmp_path, env=check_env, input="x", capture_output=True, text=True, timeout=30)
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
        cwd=tmp_path, env=check_env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 7, result.stderr
    with FileLock(_local_check.lock_path()).acquire(timeout=1):
        pass


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

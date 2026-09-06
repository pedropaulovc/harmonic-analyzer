"""Real subprocess controls for pytest-only local telemetry isolation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_explicit_telemetry_directory_overrides_default(monkeypatch, tmp_path):
    import _telemetry

    target = tmp_path / "explicit-capture"
    monkeypatch.setenv("HARMONIC_TELEMETRY_DIR", str(target))
    assert _telemetry._telemetry_dir() == target
    assert target.is_dir()


def _mini_repo(tmp_path):
    scripts = tmp_path / "cad" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "cad" / "scripts" / "_telemetry.py", scripts)
    return scripts


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_pytest_collection_fixture_and_child_are_isolated_before_import(tmp_path):
    scripts = _mini_repo(tmp_path)
    shutil.copy2(REPO_ROOT / "conftest.py", tmp_path)
    test = scripts / "test_collection_capture.py"
    test.write_text(
        """import json, os, subprocess, sys
from pathlib import Path
import _telemetry as t
with t.span("mock.collection"):
    t.error("mock collection failure")

def test_child():
    assert t._resolve_otlp_endpoint() is None
    assert all(type(p).__name__ == "SimpleSpanProcessor" for p in t._span_processors)
    assert not os.environ.get("TRACEPARENT")
    assert not os.environ.get("TRACESTATE")
    for signal in ("", "_TRACES", "_LOGS", "_METRICS"):
        assert os.environ["OTEL_EXPORTER_OTLP" + signal + "_ENDPOINT"] == ""
    with t.span("mock.test"):
        t.warn("mock test warning")
    child = "import _telemetry as t\\nwith t.span('mock.child'):\\n t.error('mock child failure')\\nt.shutdown()"
    result = subprocess.run([sys.executable, "-c", child], check=True)
    Path("capture-path.txt").write_text(os.environ["HARMONIC_TELEMETRY_DIR"])
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(scripts)
    env["HARMONIC_TELEMETRY_DIR"] = str(tmp_path / "production-override")
    env["TRACEPARENT"] = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    env["TRACESTATE"] = "production=parent"
    # An explicit production endpoint must be disabled, not just the default
    # dashboard probe. A real export here rejects the child assertions.
    for signal in ("", "_TRACES", "_LOGS", "_METRICS"):
        env["OTEL_EXPORTER_OTLP" + signal + "_ENDPOINT"] = "http://127.0.0.1:9"
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(test)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    capture = Path((tmp_path / "capture-path.txt").read_text())
    assert capture.parent == tmp_path / "cad" / "out" / "reports" / "pytest-telemetry"
    assert not (tmp_path / "production-override").exists()
    assert not (tmp_path / "cad" / "out" / "reports" / "telemetry").exists()
    spans = _records(capture / "traces.jsonl")
    assert {row["name"] for row in spans} == {
        "mock.collection",
        "mock.test",
        "mock.child",
    }
    assert all(row["parent_id"] is None for row in spans)
    logs = _records(capture / "logs.jsonl")
    assert {row["body"] for row in logs} == {
        "mock collection failure",
        "mock test warning",
        "mock child failure",
    }
    assert str(capture) in run.stdout


@pytest.mark.parametrize("destination", ["default", "explicit"])
def test_non_pytest_subprocess_keeps_default_or_explicit_capture(tmp_path, destination):
    scripts = _mini_repo(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(scripts)
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
    env.pop("HARMONIC_TELEMETRY_DIR", None)
    expected = tmp_path / "cad" / "out" / "reports" / "telemetry"
    if destination == "explicit":
        expected = tmp_path / "chosen-capture"
        env["HARMONIC_TELEMETRY_DIR"] = str(expected)
    run = subprocess.run(
        [
            sys.executable,
            "-c",
            "import _telemetry as t\nwith t.span('real-operation'):\n t.info('real log')\nt.shutdown()",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert run.returncode == 0, run.stderr
    assert [row["name"] for row in _records(expected / "traces.jsonl")] == [
        "real-operation"
    ]
    assert [row["body"] for row in _records(expected / "logs.jsonl")] == ["real log"]
    assert not (tmp_path / "cad" / "out" / "reports" / "pytest-telemetry").exists()


def test_real_telemetry_self_runner_enters_pytest_before_application_import(tmp_path):
    scripts = _mini_repo(tmp_path)
    shutil.copy2(REPO_ROOT / "conftest.py", tmp_path)
    script = scripts / "test_telemetry.py"
    shutil.copy2(REPO_ROOT / "cad" / "scripts" / script.name, script)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(scripts)
    env["PYTEST_ADDOPTS"] = "-k test_clean_span_is_ok"
    env.pop("HARMONIC_TELEMETRY_DIR", None)
    env["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://127.0.0.1:9"
    run = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert not (tmp_path / "cad" / "out" / "reports" / "telemetry").exists()
    (capture,) = (tmp_path / "cad" / "out" / "reports" / "pytest-telemetry").iterdir()
    assert [row["name"] for row in _records(capture / "traces.jsonl")] == ["fine"]
    assert [row["body"] for row in _records(capture / "logs.jsonl")] == [
        "did the thing"
    ]

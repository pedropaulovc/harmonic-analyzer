"""The root conftest isolates a test session from the machine it runs on.

Its environment settings are made when conftest is imported, before collection
imports any product module, and its watchdog exit refusal keeps a firing
watchdog from ending pytest itself.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_CREDENTIALS = (
    "HARMONIC_CACHE_SAS",
    "AZURE_CLIENT_SECRET",
    "AZURE_STORAGE_KEY",
)
_OTLP_ENDPOINTS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
)


def test_conftest_import_scrubs_an_inherited_build_environment(tmp_path):
    """A shell or farm leaf's settings are gone the moment conftest is imported."""
    live_pool_config = tmp_path / "pool-config.json"
    live_pool_config.write_text("{}", encoding="utf-8")
    environment = {
        **os.environ,
        "HARMONIC_REMOTE_CACHE_MODE": "rw",
        "HARMONIC_EXECUTOR": "farm",
        "HARMONIC_FARM_RUN": "run-from-the-build",
        "HARMONIC_FARM_COMMIT": "0" * 40,
        "SOLIDWORKS_POOL_CONFIG": str(live_pool_config),
        "OTEL_RESOURCE_ATTRIBUTES": "farm.worker=w@1,farm.execution=wf/run/1",
        "HARMONIC_SW_AUTOSTART": "1",
        "HARMONIC_TELEMETRY_DIR": str(tmp_path / "live-telemetry"),
        **{name: "inherited-secret" for name in _CREDENTIALS},
        **{name: "http://127.0.0.1:9" for name in _OTLP_ENDPOINTS},
    }
    child = (
        "import json, os, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import conftest\n"
        "print(json.dumps({'scratch': conftest._SCRATCH.name,"
        " 'env': dict(os.environ)}))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", child, str(REPO_ROOT)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=environment,
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    report = json.loads(done.stdout.strip().splitlines()[-1])
    scratch, env = Path(report["scratch"]), report["env"]

    assert env["HARMONIC_REMOTE_CACHE_MODE"] == "off"
    assert not [
        name
        for name in env
        if name == "HARMONIC_EXECUTOR" or name.startswith("HARMONIC_FARM_")
    ]
    assert Path(env["SOLIDWORKS_POOL_CONFIG"]).parent == scratch
    assert env["OTEL_RESOURCE_ATTRIBUTES"] == "farm.worker=w@1"
    assert env["HARMONIC_SW_AUTOSTART"] == "0"
    assert not [name for name in _CREDENTIALS if name in env]
    assert {name: env[name] for name in _OTLP_ENDPOINTS} == dict.fromkeys(
        _OTLP_ENDPOINTS, ""
    )
    assert Path(env["HARMONIC_TELEMETRY_DIR"]) == scratch / "telemetry"


def test_this_session_captures_telemetry_in_scratch():
    telemetry = Path(os.environ["HARMONIC_TELEMETRY_DIR"])
    assert not telemetry.is_relative_to(REPO_ROOT)


def test_a_default_watchdog_exit_is_refused_instead_of_ending_pytest(
    solidworks_launch_refusals,
):
    watchdog = sys.modules["_watchdog"]
    # Fail cleanly, never by exiting, if either half of the protection regressed.
    assert watchdog._hard_exit is not os._exit
    assert watchdog.Watchdog.__init__.__kwdefaults__["exit_fn"] is None
    crashes: set[int] = set()
    dog = watchdog.Watchdog(
        crash_pids=lambda: set(crashes),
        hung_probe=lambda: False,
        dialog_probe=lambda: None,
        activity=lambda: 0.0,
        clock=lambda: 0.0,
    )
    crashes.add(4242)
    with pytest.raises(RuntimeError, match=r"_watchdog\._hard_exit"):
        dog.tick()
    assert len(solidworks_launch_refusals) == 1
    solidworks_launch_refusals.clear()

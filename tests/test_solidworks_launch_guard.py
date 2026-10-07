"""Known host-hazard refusals for trusted tests (not sandbox coverage).

Destructive transports are harmless recorders BEFORE guard installation, so a
deleted/refusing-branch mutation fails without reaching the host. Unrelated
subprocess/COM and real scratch OTel capture retain their genuine behavior.
"""

import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import conftest as safety

BLOCKED = "SolidWorks launch blocked"
MISSING_SHORTCUT = r"X:\launch-guard-test\never-exists\SOLIDWORKS Design.lnk"
TEST_CLSID = "{11111111-2222-3333-4444-555555555555}"
COM_ROUTES = [
    ("win32com.client", "Dispatch"),
    ("win32com.client", "DispatchEx"),
    ("win32com.client", "GetObject"),
    ("win32com.client", "GetActiveObject"),
    ("win32com.client.dynamic", "Dispatch"),
    ("win32com.client.dynamic", "DumbDispatch"),
    ("win32com.client.gencache", "EnsureDispatch"),
    ("pythoncom", "CoCreateInstance"),
    ("pythoncom", "CoCreateInstanceEx"),
    ("pythoncom", "GetActiveObject"),
    ("pythoncom", "Connect"),
    ("comtypes", "CoCreateInstance"),
    ("comtypes", "GetActiveObject"),
    ("comtypes.client", "CreateObject"),
    ("comtypes.client", "CoGetObject"),
    ("comtypes.client", "GetActiveObject"),
]


@pytest.fixture
def launch_boundary(monkeypatch, solidworks_launch_refusals):
    attempts = []

    def harmless_init(self, args, *rest, **kwargs):
        self._child_created = False
        attempts.append(("Popen", args))
        raise AssertionError("unguarded call reached harmless Popen transport")

    monkeypatch.setattr(subprocess.Popen, "__init__", harmless_init)
    monkeypatch.setattr(os, "system", lambda command: attempts.append(("system", command)))
    if hasattr(os, "startfile"):
        monkeypatch.setattr(
            os, "startfile", lambda *args, **kwargs: attempts.append(("startfile", args))
        )
    safety._install_launch_guard()
    yield attempts
    assert attempts == [], f"guard let a destructive transport through: {attempts}"


@pytest.fixture
def com_boundary(monkeypatch, solidworks_launch_refusals):
    """Exercise the actual installer with harmless COM/launch transports."""
    modules = {}
    calls = []

    def transport(module_name, attribute):
        def harmless(*args, **kwargs):
            calls.append((module_name, attribute, args, kwargs))
            return "unrelated COM result"

        return harmless

    for module_name, attribute in COM_ROUTES:
        module = modules.setdefault(module_name, SimpleNamespace())
        setattr(module, attribute, transport(module_name, attribute))
    for module_name in (
        "solidworks_mcp.adapters.sw_recovery",
        "solidworks_mcp.adapters.sw_install",
    ):
        modules[module_name] = SimpleNamespace()
        for attribute in safety._LAUNCH_ENTRY_POINTS[module_name]:
            setattr(modules[module_name], attribute, transport(module_name, attribute))
    real_import = importlib.import_module

    def isolated_import(name):
        return modules[name] if name in modules else real_import(name)

    monkeypatch.setattr(safety, "_solidworks_class_ids", lambda: {TEST_CLSID.lower()})
    with monkeypatch.context() as imports:
        imports.setattr(importlib, "import_module", isolated_import)
        safety._install_activation_guard()
    return SimpleNamespace(modules=modules, calls=calls)


def _expect_blocked(refusals, call):
    # Every destructive guard probe has an inert transport beneath the refusal.
    with pytest.raises(RuntimeError, match=BLOCKED):
        call()
    assert len(refusals) == 1
    refusals.clear()


def test_shortcut_child_is_refused(solidworks_launch_refusals, launch_boundary):
    """The SolidworksMCP-python launch shape: a child that os.startfile's a .lnk."""
    argv = [
        sys.executable,
        "-I",
        "-c",
        "import os, sys; os.startfile(sys.argv[1])",
        MISSING_SHORTCUT,
    ]
    _expect_blocked(
        solidworks_launch_refusals, lambda: subprocess.run(argv, check=False)
    )


def test_connector_launch_is_refused(solidworks_launch_refusals, launch_boundary):
    command = r'"X:\never-exists\CATSTART.exe" -run "SWXDesktopLauncher.exe"'
    _expect_blocked(solidworks_launch_refusals, lambda: subprocess.Popen(command))


def test_taskkill_of_solidworks_is_refused(solidworks_launch_refusals, launch_boundary):
    # Even a guard regression cannot run taskkill: Popen's transport is inert.
    argv = ["taskkill", "/F", "/IM", "sldworks-launch-guard-test.exe"]
    _expect_blocked(
        solidworks_launch_refusals, lambda: subprocess.run(argv, check=False)
    )


def test_os_system_is_refused(solidworks_launch_refusals, launch_boundary):
    # echo, not start: were the guard broken, nothing opens.
    command = f"echo {MISSING_SHORTCUT}"
    _expect_blocked(solidworks_launch_refusals, lambda: os.system(command))


@pytest.mark.skipif(not hasattr(os, "startfile"), reason="os.startfile is Windows-only")
def test_in_process_startfile_is_refused(solidworks_launch_refusals, launch_boundary):
    # os.startfile's transport was made harmless before installing the guard.
    _expect_blocked(solidworks_launch_refusals, lambda: os.startfile(MISSING_SHORTCUT))


def test_unrelated_subprocess_passes(solidworks_launch_refusals):
    result = subprocess.run(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "ok"
    assert solidworks_launch_refusals == []


def _require_refuser(module, attribute, name):
    # Never reach a real COM activation or launch, even on a guard regression.
    assert getattr(module, attribute).__name__ == name, (module, attribute)


@pytest.mark.parametrize(
    "module_name,attribute",
    COM_ROUTES,
)
def test_com_activation_of_solidworks_is_refused(
    solidworks_launch_refusals, com_boundary, module_name, attribute
):
    """Refuse both activation and attachment, without a real COM transport."""
    module = com_boundary.modules[module_name]
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: getattr(module, attribute)("SldWorks.Application"),
    )
    assert com_boundary.calls == []


@pytest.mark.parametrize("module_name,attribute", COM_ROUTES)
def test_com_activation_or_attachment_by_class_id_is_refused(
    solidworks_launch_refusals, com_boundary, module_name, attribute
):
    module = com_boundary.modules[module_name]
    _expect_blocked(
        solidworks_launch_refusals,
        lambda: getattr(module, attribute)(TEST_CLSID),
    )
    assert com_boundary.calls == []


@pytest.mark.parametrize("module_name,attribute", COM_ROUTES)
def test_unrelated_com_arguments_are_forwarded(
    solidworks_launch_refusals, com_boundary, module_name, attribute
):
    module = com_boundary.modules[module_name]
    assert getattr(module, attribute)("Other.Application", context=17) == (
        "unrelated COM result"
    )
    assert com_boundary.calls == [
        (module_name, attribute, ("Other.Application",), {"context": 17})
    ]
    assert solidworks_launch_refusals == []


@pytest.mark.skipif(sys.platform != "win32", reason="pywin32 is Windows-only")
def test_unrelated_com_activation_passes(solidworks_launch_refusals):
    import win32com.client

    _require_refuser(win32com.client, "Dispatch", "refuse_solidworks_activation")
    dictionary = win32com.client.Dispatch("Scripting.Dictionary")
    dictionary.Add("k", "v")
    assert dictionary.Count == 1
    assert solidworks_launch_refusals == []


@pytest.mark.parametrize(
    "module_name,attribute,args",
    [
        ("solidworks_mcp.adapters.sw_recovery", "start_solidworks", ()),
        ("solidworks_mcp.adapters.sw_recovery", "stop_solidworks", ()),
        ("solidworks_mcp.adapters.sw_recovery", "kill_connector_processes", ()),
        ("solidworks_mcp.adapters.sw_recovery", "recover_solidworks", ()),
        (
            "solidworks_mcp.adapters.sw_install",
            "launch_via_platform_shortcut",
            (MISSING_SHORTCUT,),
        ),
    ],
)
def test_solidworks_mcp_launch_entry_points_are_refused(
    solidworks_launch_refusals, com_boundary, module_name, attribute, args
):
    module = com_boundary.modules[module_name]
    _require_refuser(module, attribute, "refuse_solidworks_launch")
    _expect_blocked(
        solidworks_launch_refusals, lambda: getattr(module, attribute)(*args)
    )
    assert com_boundary.calls == []


def test_autostart_is_off_unless_a_test_opts_in():
    assert os.environ.get("HARMONIC_SW_AUTOSTART") == "0"


def test_swallowed_autostart_launch_still_fails_the_test(
    solidworks_launch_refusals, monkeypatch
):
    """``_sw_lifecycle.ensure_ready`` swallows every exception.

    With autostart forced on and SolidWorks reported down it reaches
    ``start_solidworks``; the refusal it swallows must still be recorded, so the
    autouse teardown check fails the test.
    """
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[1] / "cad" / "scripts")
    )
    import _sw_lifecycle
    from solidworks_mcp.adapters import sw_recovery
    from solidworks_mcp.adapters.sw_recovery import SolidWorksState

    attempts = []
    monkeypatch.setattr(sw_recovery, "start_solidworks", lambda: attempts.append("start"))
    monkeypatch.setattr(
        sw_recovery,
        "start_solidworks",
        safety._refuse_launch("solidworks_mcp.adapters.sw_recovery", "start_solidworks"),
    )
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "1")
    monkeypatch.setattr(
        sw_recovery, "detect_state", lambda: SolidWorksState.NOT_RUNNING
    )

    assert _sw_lifecycle.ensure_ready() == "error"
    assert attempts == []
    assert len(solidworks_launch_refusals) == 1
    assert "start_solidworks" in solidworks_launch_refusals[0]
    solidworks_launch_refusals.clear()


def test_watchdog_hard_exit_is_refused(solidworks_launch_refusals, monkeypatch):
    import _watchdog

    attempts = []
    monkeypatch.setattr(os, "_exit", attempts.append)
    _expect_blocked(
        solidworks_launch_refusals, lambda: _watchdog._hard_exit(_watchdog.EXIT_CRASH)
    )
    assert attempts == []


def test_existing_watchdog_uses_the_reinstalled_exit_guard(
    solidworks_launch_refusals, monkeypatch
):
    import _watchdog

    attempts = []
    monkeypatch.setattr(os, "_exit", attempts.append)
    # A restored captured-default mutation must still be harmless. Load the
    # tested constructor only AFTER its underlying exit has become a recorder.
    spec = importlib.util.spec_from_file_location("_guarded_watchdog_test", _watchdog.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules, "_watchdog", module)
    monkeypatch.setattr(module, "_hard_exit", attempts.append)
    monkeypatch.setattr(module, "_abort", lambda *_args, **_fields: None)
    dog = module.Watchdog(
        op_timeout=1,
        crash_pids=lambda: set(),
        hung_probe=lambda: False,
        dialog_probe=lambda: None,
        activity=lambda: 0,
        clock=lambda: 10,
    )
    safety._install_watchdog_guard()
    _expect_blocked(solidworks_launch_refusals, dog.tick)
    assert attempts == []


def test_swallowed_watchdog_refusal_fails_autouse_teardown(
    solidworks_launch_refusals, monkeypatch
):
    import _watchdog

    attempts = []
    monkeypatch.setattr(os, "_exit", attempts.append)
    teardown = safety._no_swallowed_solidworks_launch.__wrapped__(None)
    next(teardown)
    try:
        _watchdog._hard_exit(_watchdog.EXIT_CRASH)
    except RuntimeError:
        pass
    with pytest.raises(pytest.fail.Exception, match="attempt.*refused"):
        next(teardown)
    assert attempts == []
    assert solidworks_launch_refusals == []


def test_swallowed_collection_refusal_is_not_cleared_by_test_setup(
    solidworks_launch_refusals, com_boundary
):
    try:
        com_boundary.modules["win32com.client"].GetActiveObject("SldWorks.Application")
    except RuntimeError:
        pass
    with pytest.raises(pytest.UsageError, match="refused during collection"):
        safety.pytest_collection_finish(None)
    assert com_boundary.calls == []
    assert solidworks_launch_refusals == []


def test_collection_displaces_inherited_hazards_before_product_imports(monkeypatch):
    expected = {
        "HARMONIC_REMOTE_CACHE_MODE": "off",
        "HARMONIC_EXECUTOR": "local",
        "HARMONIC_SW_AUTOSTART": "0",
        "HARMONIC_CACHE_SAS": "",
        "HARMONIC_FARM_COMMIT": "",
        "HARMONIC_FARM_REQUESTS": "",
        "HARMONIC_FARM_RUN": "",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "",
    }
    scratch_names = (
        "HARMONIC_BUILDGRAPH_CACHE",
        "HARMONIC_COM_LOCK",
        "SOLIDWORKS_POOL_CONFIG",
        "HARMONIC_TELEMETRY_DIR",
    )
    for name in (*expected, *scratch_names):
        monkeypatch.setenv(name, "inherited-live-setting")
    monkeypatch.setenv("NOSW_GUARD", "1")
    spec = importlib.util.spec_from_file_location("_isolated_root_guard", safety.__file__)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    imported = []

    def product_import(name):
        imported.append(name)
        for key, value in expected.items():
            assert os.environ[key] == value, (name, key)
        for key in scratch_names:
            assert Path(os.environ[key]).is_relative_to(Path(module._scratch.name))
        return SimpleNamespace()

    try:
        spec.loader.exec_module(module)
        monkeypatch.setattr(module, "_solidworks_class_ids", lambda: set())
        with monkeypatch.context() as transports:
            # Isolate only the boundaries reached by the real guard installer.
            transports.setattr(subprocess.Popen, "__init__", lambda *_a, **_k: None)
            transports.setattr(os, "system", lambda *_a, **_k: None)
            if hasattr(os, "startfile"):
                transports.setattr(os, "startfile", lambda *_a, **_k: None)
            transports.setattr(importlib, "import_module", product_import)
            cleanups = []
            module.pytest_configure(SimpleNamespace(add_cleanup=cleanups.append))
        assert "_watchdog" in imported
        assert "win32com.client" in imported
        assert cleanups
        assert not Path(os.environ["SOLIDWORKS_POOL_CONFIG"]).exists()
    finally:
        if hasattr(module, "_scratch"):
            module._scratch.cleanup()


def test_real_telemetry_capture_uses_the_scratch_directory(monkeypatch, tmp_path):
    import _telemetry

    baseline = os.environ["HARMONIC_TELEMETRY_DIR"]
    capture = tmp_path / "telemetry"
    monkeypatch.setenv("HARMONIC_TELEMETRY_DIR", str(capture))
    try:
        _telemetry.configure(console=False, force=True)
        with _telemetry.span("launch-guard.scratch-capture"):
            _telemetry.info("launch-guard scratch log")
        _telemetry.shutdown()
        traces = [
            json.loads(line) for line in (capture / "traces.jsonl").read_text().splitlines()
        ]
        logs = [
            json.loads(line) for line in (capture / "logs.jsonl").read_text().splitlines()
        ]
        assert any(row["name"] == "launch-guard.scratch-capture" for row in traces)
        assert any(row["body"] == "launch-guard scratch log" for row in logs)
        assert _telemetry._telemetry_dir() == capture
    finally:
        monkeypatch.setenv("HARMONIC_TELEMETRY_DIR", baseline)
        _telemetry.configure(force=True)


def test_scratch_cleanup_closes_capture_once_before_removing_files(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(safety, "_scratch_cleaned", False)
    monkeypatch.setattr(
        safety,
        "_scratch",
        SimpleNamespace(name=str(tmp_path), cleanup=lambda: events.append("cleanup")),
    )
    monkeypatch.setitem(
        sys.modules, "_telemetry", SimpleNamespace(shutdown=lambda: events.append("shutdown"))
    )

    safety._cleanup_host_scratch()
    safety._cleanup_host_scratch()

    assert events == ["shutdown", "cleanup"]


def test_scratch_cleanup_still_removes_files_when_capture_shutdown_raises(
    monkeypatch, tmp_path
):
    events = []

    def shutdown():
        events.append("shutdown")
        raise RuntimeError("capture shutdown failed")

    monkeypatch.setattr(safety, "_scratch_cleaned", False)
    monkeypatch.setattr(
        safety,
        "_scratch",
        SimpleNamespace(name=str(tmp_path), cleanup=lambda: events.append("cleanup")),
    )
    monkeypatch.setitem(sys.modules, "_telemetry", SimpleNamespace(shutdown=shutdown))

    with pytest.raises(RuntimeError, match="capture shutdown failed"):
        safety._cleanup_host_scratch()
    safety._cleanup_host_scratch()

    assert events == ["shutdown", "cleanup"]

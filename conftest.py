"""Contain known host hazards in trusted repository tests, not a sandbox.

This does not contain plugins loaded before this file, arbitrary native/network
operations, or the vendored suite. ``NOSW_GUARD=0`` deliberately opts out of
the SolidWorks/process-exit refusals; it is not a safe-default test run.
"""

import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path, PureWindowsPath

import pytest

# Apply before any product import/default capture, including pytest_configure's
# adapter imports. Never inherit an operator's live farm/cache/exporter settings.
_scratch = tempfile.TemporaryDirectory(prefix="harmonic-tests-")
_INERT_ENVIRONMENT = {
    "HARMONIC_BUILDGRAPH_CACHE": str(Path(_scratch.name) / "buildgraph"),
    "HARMONIC_REMOTE_CACHE_MODE": "off",
    "HARMONIC_EXECUTOR": "local",
    "HARMONIC_SW_AUTOSTART": "0",
    "HARMONIC_COM_LOCK": str(Path(_scratch.name) / "com-seat.lock"),
    "HARMONIC_CACHE_SAS": "",
    "SOLIDWORKS_POOL_CONFIG": str(Path(_scratch.name) / "no-farm-credentials.json"),
    "HARMONIC_FARM_COMMIT": "",
    "HARMONIC_FARM_REQUESTS": "",
    "HARMONIC_FARM_RUN": "",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": "",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT": "",
    "HARMONIC_TELEMETRY_DIR": str(Path(_scratch.name) / "telemetry"),
}
os.environ.update(_INERT_ENVIRONMENT)


# A test process never starts (or kills) SolidWorks. On amet a start takes the
# licence farm worker w6 shares; on a worker it takes the seat from the build.
# NOSW_GUARD=0 turns this off for deliberate operator work, matching the shared
# sitecustomize guard agents load with PYTHONPATH.
_LAUNCH_MARKERS = (
    "startfile",
    ".lnk",
    "sldworks",
    "swxdesktop",
    "3dexperiencelauncher",
    "catstart",
)
_READ_ONLY_PROGRAMS = frozenset({"tasklist", "tasklist.exe"})
_refused: list[str] = []


class SolidWorksLaunchBlocked(RuntimeError):
    """A test tried to start, attach to, kill SolidWorks, or hard-exit Python."""


def _guard_disabled() -> bool:
    return os.environ.get("NOSW_GUARD", "1").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }


def _refuse(route, detail):
    stack = "".join(traceback.format_stack(limit=25)[:-2])
    test = os.environ.get("PYTEST_CURRENT_TEST", "<no test>")
    message = (
        f"SolidWorks launch blocked in {test} via {route}: {str(detail)[:300]}\n"
        f"Caller stack:\n{stack}"
    )
    _refused.append(message)
    raise SolidWorksLaunchBlocked(message)


def _program(args):
    if isinstance(args, (list, tuple)):
        return PureWindowsPath(str(args[0])).name.lower() if args else ""
    words = str(args).split()
    return PureWindowsPath(words[0].strip('"')).name.lower() if words else ""


def _launches_solidworks(args, executable=None):
    if _program(args) in _READ_ONLY_PROGRAMS:
        return False
    parts = args if isinstance(args, (list, tuple)) else [args]
    text = " ".join(str(part) for part in [*parts, executable] if part is not None)
    return any(marker in text.lower() for marker in _LAUNCH_MARKERS)


def _install_launch_guard():
    original_init = subprocess.Popen.__init__

    def guarded_init(self, args, *rest, **kwargs):
        if _launches_solidworks(args, kwargs.get("executable")):
            _refuse("subprocess.Popen", args)
        original_init(self, args, *rest, **kwargs)

    subprocess.Popen.__init__ = guarded_init

    if hasattr(os, "startfile"):

        def refuse_startfile(path, *args, **kwargs):
            _refuse("os.startfile", path)

        os.startfile = refuse_startfile

    original_system = os.system

    def guarded_system(command):
        if _launches_solidworks(command):
            _refuse("os.system", command)
        return original_system(command)

    os.system = guarded_system


# COM activation/active-instance attachment and SolidworksMCP lifecycle entry
# points bypass Popen. Attaching can mutate the user's live seat just as starting
# one can steal it, so both are refused for SolidWorks only, collection included.
_COM_ACTIVATORS = {
    "win32com.client": ("Dispatch", "DispatchEx", "GetObject", "GetActiveObject"),
    "win32com.client.dynamic": ("Dispatch", "DumbDispatch"),
    "win32com.client.gencache": ("EnsureDispatch",),
    "pythoncom": (
        "CoCreateInstance",
        "CoCreateInstanceEx",
        "GetActiveObject",
        "Connect",
    ),
    "comtypes": ("CoCreateInstance", "GetActiveObject"),
    "comtypes.client": ("CreateObject", "CoGetObject", "GetActiveObject"),
}
_LAUNCH_ENTRY_POINTS = {
    "solidworks_mcp.adapters.sw_recovery": (
        "start_solidworks",
        "stop_solidworks",
        "kill_connector_processes",
        "recover_solidworks",
    ),
    "solidworks_mcp.adapters.sw_install": ("launch_via_platform_shortcut",),
}


def _solidworks_class_ids():
    """The CLSID ``SldWorks.Application`` resolves to on this machine, if any.

    A caller may activate the class by CLSID instead of ProgID.
    """
    try:
        import winreg
    except ImportError:
        return set()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT, r"SldWorks.Application\CLSID"
        ) as key:
            return {str(winreg.QueryValue(key, None)).lower()}
    except OSError:
        return set()


def _names_solidworks(args, kwargs, class_ids):
    text = " ".join(str(part) for part in (*args, *kwargs.values())).lower()
    return "sldworks" in text or any(clsid in text for clsid in class_ids)


def _refuse_com_activation(module_name, attribute, original, class_ids):
    def refuse_solidworks_activation(*args, **kwargs):
        if _names_solidworks(args, kwargs, class_ids):
            _refuse(f"{module_name}.{attribute}", args)
        return original(*args, **kwargs)

    return refuse_solidworks_activation


def _refuse_launch(module_name, attribute):
    def refuse_solidworks_launch(*args, **kwargs):
        _refuse(f"{module_name}.{attribute}", args)

    return refuse_solidworks_launch


def _install_activation_guard():
    import importlib

    class_ids = _solidworks_class_ids()
    for module_name, attributes in _COM_ACTIVATORS.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for attribute in attributes:
            original = getattr(module, attribute, None)
            if original is None:
                continue
            setattr(
                module,
                attribute,
                _refuse_com_activation(module_name, attribute, original, class_ids),
            )
    for module_name, attributes in _LAUNCH_ENTRY_POINTS.items():
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        for attribute in attributes:
            setattr(module, attribute, _refuse_launch(module_name, attribute))


def _refuse_watchdog_exit(code):
    _refuse("_watchdog._hard_exit", f"exit {code}")


def _install_watchdog_guard():
    import importlib

    # The graph normally adds this script directory. Install before collection
    # even when a root-only selection never imports dodo.
    scripts = str(Path(__file__).resolve().parent / "cad" / "scripts")
    sys.path.insert(0, scripts)
    try:
        watchdog = importlib.import_module("_watchdog")
    finally:
        sys.path.remove(scripts)
    watchdog._hard_exit = _refuse_watchdog_exit
    return watchdog


_scratch_cleaned = False


def _retire_scratch_facts():
    """Detach only an existing store owned by this session's scratch."""
    graph = sys.modules.get("_buildgraph")
    if graph is None:
        return
    store = graph._FACTS
    location = store._path
    if location is None and store._entries is None:
        # A cold store has no captured path. Use only the explicit override;
        # cleanup must not activate a default/home-backed store.
        setting = os.environ.get(graph._FACTS_ENV, "")
        if setting and setting.lower() not in {"off", "0", "false", "no"}:
            location = Path(setting)
    if location is not None and location.resolve().is_relative_to(
        Path(_scratch.name).resolve()
    ):
        store.close()


def _cleanup_host_scratch():
    """Retire owned facts and capture before removing session scratch."""
    global _scratch_cleaned
    if _scratch_cleaned:
        return
    telemetry = sys.modules.get("_telemetry")
    try:
        _retire_scratch_facts()
    finally:
        try:
            if telemetry is not None:
                telemetry.shutdown()
        finally:
            _scratch.cleanup()
            _scratch_cleaned = True


def pytest_configure(config):
    """Install process/COM/exit refusals before collecting product modules.

    Real telemetry and build-graph storage use session scratch. Even explicit
    inherited cache paths and signal-specific exporters have already been
    displaced by the collection-time environment above.
    """
    # Also clean up when collection aborts before session fixtures can run.
    config.add_cleanup(_cleanup_host_scratch)
    if not _guard_disabled():
        _install_launch_guard()
        _install_watchdog_guard()
        _install_activation_guard()


def pytest_collection_finish(session):
    if _refused:
        attempts = "\n".join(_refused)
        _refused.clear()
        raise pytest.UsageError(
            f"SolidWorks/process-exit attempt(s) refused during collection:\n{attempts}"
        )


@pytest.fixture(scope="session", autouse=True)
def _host_safety_scratch():
    """Own and retire collection's scratch stores and real JSONL exporters."""
    yield Path(_scratch.name)
    _cleanup_host_scratch()


@pytest.fixture(autouse=True)
def _known_host_environment(_host_safety_scratch):
    """Reapply the baseline; behavioral tests can explicitly override it."""
    patches = pytest.MonkeyPatch()
    for name, value in _INERT_ENVIRONMENT.items():
        patches.setenv(name, value)
    if not _guard_disabled():
        patches.setattr(sys.modules["_watchdog"], "_hard_exit", _refuse_watchdog_exit)
    try:
        yield
    finally:
        patches.undo()


@pytest.fixture
def solidworks_launch_refusals():
    """The refusals recorded so far in this test; a guard test clears them."""
    if _guard_disabled():
        pytest.skip("NOSW_GUARD=0: the SolidWorks launch guard is off")
    return _refused


@pytest.fixture(autouse=True)
def _no_swallowed_solidworks_launch(_known_host_environment):
    """Fail even when product code or a watchdog thread swallowed a refusal."""
    _refused.clear()
    yield
    if _refused:
        attempts = "\n".join(_refused)
        _refused.clear()
        pytest.fail(f"SolidWorks launch attempt(s) refused:\n{attempts}", pytrace=False)



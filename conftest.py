"""Suite-wide test isolation for the whole repository (``cad/scripts`` and ``tests``)."""

import os
import subprocess
import tempfile
import traceback
from pathlib import Path, PureWindowsPath

import pytest

# Set these before any product import: collection can configure exporters and
# choose cache/farm backends, before an autouse fixture has a chance to run.
_test_scratch = tempfile.TemporaryDirectory(prefix="harmonic-tests-")
os.environ["HARMONIC_BUILDGRAPH_CACHE"] = "off"
os.environ["HARMONIC_REMOTE_CACHE_MODE"] = "off"
os.environ["HARMONIC_EXECUTOR"] = "local"
os.environ["HARMONIC_SW_AUTOSTART"] = "0"
os.environ["SOLIDWORKS_POOL_CONFIG"] = str(
    Path(_test_scratch.name) / "no-pool-config.json"
)
os.environ["HARMONIC_TELEMETRY_DIR"] = str(
    Path(_test_scratch.name) / "telemetry"
)
os.environ["OTEL_RESOURCE_ATTRIBUTES"] = ",".join(
    entry
    for entry in os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "").split(",")
    if entry.partition("=")[0].strip() != "farm.execution"
)
for _name in (
    "HARMONIC_CACHE_SAS",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_CERTIFICATE_PATH",
    "AZURE_CLIENT_CERTIFICATE_PASSWORD",
    "AZURE_FEDERATED_TOKEN_FILE",
    "AZURE_STORAGE_CONNECTION_STRING",
    "AZURE_STORAGE_KEY",
    "AZURE_STORAGE_SAS_TOKEN",
    "HARMONIC_FARM_COMMIT",
    "HARMONIC_FARM_RUN",
    "HARMONIC_FARM_REQUESTS",
):
    os.environ.pop(_name, None)
for _name in (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
):
    os.environ[_name] = ""

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
    """A test tried to start or kill SolidWorks."""


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


# COM activation and the SolidworksMCP launch entry points. The process guard
# above cannot see these: ``SldWorks.Application``'s LocalServer32 is
# SLDWORKS.exe itself, so a Dispatch starts SolidWorks without any Popen, and
# ``sw_recovery``'s connector launch only reaches Popen after a registry walk
# a test can fake. Each is replaced for the whole session, collection included.
_COM_ACTIVATORS = {
    "win32com.client": ("Dispatch", "DispatchEx", "GetObject", "GetActiveObject"),
    "win32com.client.dynamic": ("Dispatch", "DumbDispatch"),
    "win32com.client.gencache": ("EnsureDispatch",),
    "pythoncom": ("CoCreateInstance", "CoCreateInstanceEx", "GetActiveObject", "connect"),
    "comtypes": ("CoCreateInstance",),
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
    _refuse("_watchdog._hard_exit", code)


def _install_watchdog_guard():
    import sys

    scripts = str(Path(__file__).parent / "cad" / "scripts")
    sys.path.insert(0, scripts)
    try:
        import _watchdog
    finally:
        sys.path.remove(scripts)
    _watchdog._hard_exit = _refuse_watchdog_exit


def pytest_configure(config):
    """Isolate the test session from the machine it runs on.

    Disable remote cache and farm execution and redirect telemetry before
    product imports. Syntax facts are disabled so patched analyzers cannot
    contaminate the machine-wide build-graph store.

    Refuse every SolidWorks start from this process: ``subprocess`` argv naming
    ``os.startfile``, a ``.lnk`` or a SolidWorks/3DEXPERIENCE launcher image
    (``tasklist`` still reads the process table), in-process ``os.startfile``,
    and ``os.system``; COM activation of ``SldWorks.Application``; and the
    SolidworksMCP start/stop/launch entry points. A refusal raises with the
    caller's stack and fails the test even if the code under test swallowed it.
    """
    if not _guard_disabled():
        _install_launch_guard()
        _install_activation_guard()
    _install_watchdog_guard()


@pytest.fixture
def solidworks_launch_refusals():
    """The refusals recorded so far in this test; a guard test clears them."""
    if _guard_disabled():
        pytest.skip("NOSW_GUARD=0: the SolidWorks launch guard is off")
    return _refused


@pytest.fixture(autouse=True)
def _no_swallowed_solidworks_launch():
    """Fail a test whose code caught a refused launch instead of surfacing it."""
    _refused.clear()
    yield
    if _refused:
        attempts = "\n".join(_refused)
        _refused.clear()
        pytest.fail(f"SolidWorks launch attempt(s) refused:\n{attempts}", pytrace=False)


@pytest.fixture(autouse=True)
def _solidworks_autostart_off(monkeypatch):
    """Keep dodo's autostart and recovery paths off unless a test opts in.

    ``HARMONIC_SW_AUTOSTART`` defaults to on, so a test that reaches
    ``dodo._sw_ensure_once`` or ``dodo._exec_com`` without patching them would
    otherwise try to start or recover SolidWorks. A test that exercises that
    logic sets the variable itself and patches the lifecycle calls it reaches.
    """
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")


@pytest.fixture(autouse=True)
def _watchdog_exit_off(monkeypatch):
    """Reapply the exit tripwire after a preceding test reloaded the module."""
    import _watchdog

    monkeypatch.setattr(_watchdog, "_hard_exit", _refuse_watchdog_exit)

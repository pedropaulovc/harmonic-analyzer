"""Suite-wide test isolation for the whole repository (``cad/scripts`` and ``tests``)."""

import os
import subprocess
import tempfile
import traceback
from pathlib import Path, PureWindowsPath

import pytest

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
    "win32com.client": ("Dispatch", "DispatchEx", "GetObject"),
    "win32com.client.dynamic": ("Dispatch", "DumbDispatch"),
    "win32com.client.gencache": ("EnsureDispatch",),
    "pythoncom": ("CoCreateInstance", "CoCreateInstanceEx"),
    "comtypes": ("CoCreateInstance",),
    "comtypes.client": ("CreateObject", "CoGetObject"),
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


def pytest_configure(config):
    """Isolate the test session from the machine it runs on.

    Point the machine-wide build-graph syntax-facts store at a throwaway
    directory. ``_buildgraph`` persists parse results in ``%LOCALAPPDATA%`` so
    real graph loads skip re-parsing unchanged sources. A test may patch
    analyzer internals; were its results saved to the real store they would be
    served, under a genuine content key, to every later build on this machine.
    Tests therefore never read or write the real store. An explicit setting
    (``off`` or a path) is respected.

    The farm's critical-path duration ledger (``_farm_order``) is redirected
    the same way, for the same reason.

    Refuse every SolidWorks start from this process: ``subprocess`` argv naming
    ``os.startfile``, a ``.lnk`` or a SolidWorks/3DEXPERIENCE launcher image
    (``tasklist`` still reads the process table), in-process ``os.startfile``,
    and ``os.system``; COM activation of ``SldWorks.Application``; and the
    SolidworksMCP start/stop/launch entry points. A refusal raises with the
    caller's stack and fails the test even if the code under test swallowed it.
    """
    if "HARMONIC_BUILDGRAPH_CACHE" not in os.environ:
        os.environ["HARMONIC_BUILDGRAPH_CACHE"] = tempfile.mkdtemp(
            prefix="buildgraph-facts-"
        )
    # The farm's critical-path ledger is machine-wide too: a test leaf that
    # "succeeds" in milliseconds must not teach real runs to submit it last.
    if "HARMONIC_FARM_DURATIONS" not in os.environ:
        os.environ["HARMONIC_FARM_DURATIONS"] = str(
            Path(tempfile.mkdtemp(prefix="farm-durations-")) / "farm-durations.json"
        )
    if not _guard_disabled():
        _install_launch_guard()
        _install_activation_guard()


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

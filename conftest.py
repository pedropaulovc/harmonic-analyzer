"""Suite-wide test isolation for the whole repository (``cad/scripts`` and ``tests``)."""

import functools
import os
import re
import shlex
import subprocess
import sys
import tempfile
import traceback
from importlib.machinery import SourceFileLoader
from pathlib import PureWindowsPath

import pytest

# A test process never starts (or kills) SolidWorks. On amet a start takes the
# licence farm worker w15 shares; on a worker it takes the seat from the build.
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
# A child running one of these opens SolidWorks itself, past every in-process
# guard: the scripts bind the seat (and start it when none answers) whatever
# HARMONIC_SW_AUTOSTART says. dodo's COM tasks launch exactly this shape,
# `python cad/scripts/build_<stem>.py`; on 2026-10-11 such a child (from orphaned
# `doit -n` workers) started sldworks.exe on the licence w15 shares.
_COM_SCRIPT = re.compile(
    r"[\\/]cad[\\/]scripts[\\/]"
    r"(?:(?:build|draw)_[^\\/]+|verify|export_models|package_native"
    r"|release_seat_documents)\.py$",
    re.IGNORECASE,
)
# Programs that run a script named in their arguments. Anything else (git
# hash-object, a linter) only reads the file.
_SCRIPT_RUNNERS = re.compile(
    r"(?:pythonw?[\d.]*|py|uvx?|cmd|powershell|pwsh)(?:\.exe)?", re.IGNORECASE
)
# ctypes symbols that start a process or open a document (a part opens SolidWorks).
_NATIVE_LAUNCHERS = frozenset(
    {
        "CreateProcessA",
        "CreateProcessW",
        "CreateProcessAsUserA",
        "CreateProcessAsUserW",
        "CreateProcessWithLogonW",
        "CreateProcessWithTokenW",
        "ShellExecuteA",
        "ShellExecuteW",
        "ShellExecuteExA",
        "ShellExecuteExW",
        "WinExec",
    }
)
_REAL_POPEN = subprocess.Popen
_REAL_RUN = subprocess.run
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
        "A test must never start SolidWorks or a COM build script on the machine "
        "running it: inject a fake runner, adapter or subprocess instead "
        "(NOSW_GUARD=0 only for deliberate operator work).\n"
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


def _text(part):
    return (
        os.fsdecode(part) if isinstance(part, (str, bytes, os.PathLike)) else str(part)
    )


def _com_script(args, cwd=None):
    """The COM build script ``args`` would run, resolved against ``cwd``, if any.

    Only a script the program executes counts: the program itself, or an
    argument of an interpreter or shell.
    """
    if isinstance(args, (list, tuple)):
        tokens = [_text(part) for part in args]
    else:
        try:
            tokens = shlex.split(_text(args), posix=False)
        except ValueError:  # an unbalanced quote: CreateProcess still runs it
            tokens = _text(args).split()
    tokens = [token.strip("\"'") for token in tokens]
    if not tokens:
        return None
    if not _SCRIPT_RUNNERS.fullmatch(PureWindowsPath(tokens[0]).name):
        tokens = tokens[:1]
    base = _text(cwd) if cwd else os.getcwd()
    for token in tokens:
        path = os.path.normpath(os.path.join(base, token))
        if _COM_SCRIPT.search(path):
            return path
    return None


def _acts_on_host(args, executable=None, cwd=None):
    return _launches_solidworks(args, executable) or _com_script(args, cwd)


def _refuse_create_process(module_name, original):
    # ``_winapi`` and ``win32process`` share CreateProcess' positional layout:
    # (application, command line, ..., current directory at index 7, ...).
    def guarded_create_process(application, command_line, *rest, **kwargs):
        cwd = rest[5] if len(rest) > 5 else None
        if _acts_on_host(command_line or "", application, cwd):
            _refuse(f"{module_name}.CreateProcess", command_line or application)
        return original(application, command_line, *rest, **kwargs)

    return guarded_create_process


def _audit(event, args):
    """Refuse what the patched Python entry points cannot see.

    ``nt.spawn*``/``nt.exec*``/``nt.system``/``nt.startfile`` called directly,
    and a ctypes binding of a native process or shell launcher.
    """
    if event == "ctypes.dlsym":
        if args[1] in _NATIVE_LAUNCHERS:
            _refuse("ctypes", args[1])
    elif event == "os.startfile":
        _refuse("os.startfile", args[0])
    elif event in ("os.spawn", "os.exec"):
        argv = args[2] if event == "os.spawn" else args[1]
        if _acts_on_host(list(argv)):
            _refuse(event, argv)
    elif event == "os.system":
        if _acts_on_host(args[0]):
            _refuse(event, args[0])


def _install_launch_guard():
    original_init = subprocess.Popen.__init__

    def guarded_init(self, args, *rest, **kwargs):
        if _acts_on_host(args, kwargs.get("executable"), kwargs.get("cwd")):
            _refuse("subprocess.Popen", args)
        original_init(self, args, *rest, **kwargs)

    subprocess.Popen.__init__ = guarded_init

    if hasattr(os, "startfile"):

        def refuse_startfile(path, *args, **kwargs):
            _refuse("os.startfile", path)

        os.startfile = refuse_startfile

    original_system = os.system

    def guarded_system(command):
        if _acts_on_host(command):
            _refuse("os.system", command)
        return original_system(command)

    os.system = guarded_system

    if sys.platform == "win32":
        import _winapi

        _winapi.CreateProcess = _refuse_create_process("_winapi", _winapi.CreateProcess)
    sys.addaudithook(_audit)


# COM activation and the SolidworksMCP launch entry points. The process guard
# above cannot see these: ``SldWorks.Application``'s LocalServer32 is
# SLDWORKS.exe itself, so a Dispatch starts SolidWorks without any Popen, and
# ``sw_recovery``'s connector launch only reaches Popen after a registry walk
# a test can fake. Each is replaced for the whole session, collection included.
_COM_ACTIVATORS = {
    "win32com.client": ("Dispatch", "DispatchEx", "GetObject", "GetActiveObject"),
    "win32com.client.dynamic": ("Dispatch", "DumbDispatch"),
    "win32com.client.gencache": ("EnsureDispatch",),
    "pythoncom": ("CoCreateInstance", "CoCreateInstanceEx", "GetActiveObject"),
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
    # Opening a part or STEP file starts SolidWorks through its file association.
    "win32api": ("ShellExecute", "WinExec"),
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
    try:
        import win32process
    except ImportError:
        return
    win32process.CreateProcess = _refuse_create_process(
        "win32process", win32process.CreateProcess
    )


# dodo's COM chokepoints. Tests load dodo both by ``import dodo`` and as fresh
# ``spec_from_file_location`` copies, so every load of a ``dodo.py`` is guarded
# as it finishes executing. Collaborator identity, not the call, decides: a
# test that fakes ``_run_subprocess`` or dodo's ``subprocess.run``/``Popen`` is
# already hermetic and keeps exercising the real ``_exec_com``.
def _runs_real_subprocess(module):
    runner = getattr(module, "subprocess", None)
    return (
        getattr(runner, "Popen", None) is _REAL_POPEN
        and getattr(runner, "run", None) is _REAL_RUN
    )


def _guard_dodo(module):
    run_subprocess = getattr(module, "_run_subprocess", None)
    exec_com = getattr(module, "_exec_com", None)
    if run_subprocess is None or exec_com is None:
        return

    @functools.wraps(run_subprocess)
    def refuse_com_subprocess(cmd, label, log_stem=None, *, task=None):
        if _runs_real_subprocess(module) and _com_script(cmd):
            _refuse("dodo._run_subprocess", f"{label}: {cmd}")
        return run_subprocess(cmd, label, log_stem, task=task)

    @functools.wraps(exec_com)
    def refuse_com_task(cmd, label, log_stem=None, *, task=None):
        if module._run_subprocess is refuse_com_subprocess and _runs_real_subprocess(
            module
        ):
            _refuse("dodo._exec_com", f"{label}: {cmd}")
        return exec_com(cmd, label, log_stem, task=task)

    module._run_subprocess = refuse_com_subprocess
    module._exec_com = refuse_com_task


def _install_dodo_guard():
    original_exec_module = SourceFileLoader.exec_module

    def exec_module(self, module):
        original_exec_module(self, module)
        if os.path.basename(self.path).lower() == "dodo.py":
            _guard_dodo(module)

    SourceFileLoader.exec_module = exec_module
    if "dodo" in sys.modules:
        _guard_dodo(sys.modules["dodo"])


def pytest_configure(config):
    """Isolate the test session from the machine it runs on.

    Point the machine-wide build-graph syntax-facts store at a throwaway
    directory. ``_buildgraph`` persists parse results in ``%LOCALAPPDATA%`` so
    real graph loads skip re-parsing unchanged sources. A test may patch
    analyzer internals; were its results saved to the real store they would be
    served, under a genuine content key, to every later build on this machine.
    Tests therefore never read or write the real store. An explicit setting
    (``off`` or a path) is respected.

    Refuse every SolidWorks start from this process: ``subprocess`` argv
    (down to ``_winapi``/``win32process`` ``CreateProcess``) naming
    ``os.startfile``, a ``.lnk``, a SolidWorks/3DEXPERIENCE launcher image or a
    COM build script under ``cad/scripts`` (``tasklist`` still reads the process
    table); in-process ``os.startfile``, ``os.system``, ``os.spawn*``/``exec*``,
    ``ShellExecute`` and ctypes process launchers; COM activation of, or binding
    to, ``SldWorks.Application``; the SolidworksMCP start/stop/launch entry
    points; and dodo's ``_exec_com``/``_run_subprocess`` with a real runner. A
    refusal raises with the caller's stack and fails the test even if the code
    under test swallowed it.
    """
    if "HARMONIC_BUILDGRAPH_CACHE" not in os.environ:
        os.environ["HARMONIC_BUILDGRAPH_CACHE"] = tempfile.mkdtemp(
            prefix="buildgraph-facts-"
        )
    if not _guard_disabled():
        _install_launch_guard()
        _install_activation_guard()
        _install_dodo_guard()


@pytest.fixture
def solidworks_launch_refusals():
    """The refusals recorded so far in this test; a guard test clears them."""
    if _guard_disabled():
        pytest.skip("NOSW_GUARD=0: the SolidWorks launch guard is off")
    return _refused


@pytest.fixture(autouse=True)
def _no_swallowed_solidworks_launch():
    """Fail a test whose code caught a refused launch instead of surfacing it.

    A refusal recorded outside any test body (collection, a wider-scoped
    fixture, an earlier teardown) fails the next test rather than vanishing.
    """
    earlier = list(_refused)
    _refused.clear()
    if earlier:
        attempts = "\n".join(earlier)
        pytest.fail(
            f"SolidWorks launch attempt(s) refused before this test:\n{attempts}",
            pytrace=False,
        )
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

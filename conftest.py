"""Suite-wide test isolation for the whole repository (``cad/scripts`` and ``tests``)."""

import os
import subprocess
import tempfile
import traceback
from pathlib import PureWindowsPath

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


def pytest_configure(config):
    """Isolate the test session from the machine it runs on.

    Point the machine-wide build-graph syntax-facts store at a throwaway
    directory. ``_buildgraph`` persists parse results in ``%LOCALAPPDATA%`` so
    real graph loads skip re-parsing unchanged sources. A test may patch
    analyzer internals; were its results saved to the real store they would be
    served, under a genuine content key, to every later build on this machine.
    Tests therefore never read or write the real store. An explicit setting
    (``off`` or a path) is respected.

    Refuse every SolidWorks start from this process: ``subprocess`` argv naming
    ``os.startfile``, a ``.lnk`` or a SolidWorks/3DEXPERIENCE launcher image
    (``tasklist`` still reads the process table), in-process ``os.startfile``,
    and ``os.system``. A refusal raises with the caller's stack and fails the
    test even if the code under test swallowed it.
    """
    if "HARMONIC_BUILDGRAPH_CACHE" not in os.environ:
        os.environ["HARMONIC_BUILDGRAPH_CACHE"] = tempfile.mkdtemp(
            prefix="buildgraph-facts-"
        )
    if not _guard_disabled():
        _install_launch_guard()


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

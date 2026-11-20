"""Suite-wide test isolation for the whole repository (``cad/scripts`` and ``tests``)."""

import importlib
import importlib.util
import os
import subprocess
import sys
import tempfile
import traceback
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

# Isolate the session's environment before anything imports product code:
# collection imports test modules (and through them dodo, _artifact_cache,
# _telemetry, _farm), which read these at import or first use, before any
# autouse fixture runs. Every child a test starts inherits the same settings.
# Tests of these variables set them explicitly with monkeypatch.
_SCRATCH = tempfile.TemporaryDirectory(
    prefix="harmonic-tests-", ignore_cleanup_errors=True
)
# Never pull from or publish to the shared remote cache (the default mode is rw).
os.environ["HARMONIC_REMOTE_CACHE_MODE"] = "off"
# Never reach the real build farm: no inherited executor or farm run identity,
# and a pool configuration path that does not exist.
for _name in [*os.environ]:
    if _name == "HARMONIC_EXECUTOR" or _name.startswith("HARMONIC_FARM_"):
        del os.environ[_name]
os.environ["SOLIDWORKS_POOL_CONFIG"] = str(Path(_SCRATCH.name) / "no-pool-config.json")
# The pool marks a farm leaf's process with ``farm.execution``; a test never is one.
_attributes = os.environ.get("OTEL_RESOURCE_ATTRIBUTES")
if _attributes is not None:
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = ",".join(
        entry
        for entry in _attributes.split(",")
        if entry.partition("=")[0].strip() != "farm.execution"
    )
os.environ["HARMONIC_SW_AUTOSTART"] = "0"
# No credentials for the cache or any other Azure resource.
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
):
    os.environ.pop(_name, None)
# Export no telemetry (an empty endpoint disables its signal), and capture the
# JSONL files in scratch rather than the checkout's cad/out/reports/telemetry.
for _name in (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
):
    os.environ[_name] = ""
os.environ["HARMONIC_TELEMETRY_DIR"] = str(Path(_SCRATCH.name) / "telemetry")

# A test process never starts (or kills) SolidWorks. On amet a start takes the
# licence farm worker w15 shares; on a worker it takes the seat from the build.
# NOSW_GUARD=0 turns this off for deliberate operator work, matching the shared
# sitecustomize guard agents load with PYTHONPATH.
#
# What counts as a start lives in one module, shared with the guard every
# Python child of this session loads through ``sitecustomize``: a child
# (``python -m doit``, ``build.py``, a git diff helper) is past every patch in
# this process. On 2026-10-11 orphaned ``doit -n`` workers ran a COM build
# script that started sldworks.exe on the licence w15 shares.
_CHILD_GUARD_DIR = Path(__file__).resolve().parent / "tests" / "_child_guard"


def _load_shared_guard():
    # A worker already loaded this module through sitecustomize. Keep that same
    # module so its installed wrappers and audit hooks see the pytest handoff.
    existing = sys.modules.get("harmonic_solidworks_guard")
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(
        "harmonic_solidworks_guard", _CHILD_GUARD_DIR / "harmonic_solidworks_guard.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_guard = _load_shared_guard()
_refused: list[str] = []
# The log this session's guarded children record their refusals in, and how
# much of it has been reported.
_child_log: str | None = None
_child_log_read = 0
_parent_child_log: str | None = None


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
        "A test must never start SolidWorks or a COM build on the machine "
        "running it: inject a fake runner, adapter or subprocess instead "
        "(NOSW_GUARD=0 only for deliberate operator work).\n"
        f"Caller stack:\n{stack}"
    )
    _refused.append(message)
    raise SolidWorksLaunchBlocked(message)


def _install_launch_guard():
    original_init = subprocess.Popen.__init__

    def guarded_init(self, args, *rest, **kwargs):
        if _guard.launches_solidworks(args, kwargs.get("executable")):
            _refuse("subprocess.Popen", args)
        original_init(self, args, *rest, **kwargs)

    subprocess.Popen.__init__ = guarded_init

    if hasattr(os, "startfile"):

        def refuse_startfile(path, *args, **kwargs):
            _refuse("os.startfile", path)

        os.startfile = refuse_startfile

    original_system = os.system

    def guarded_system(command):
        if _guard.launches_solidworks(command):
            _refuse("os.system", command)
        return original_system(command)

    os.system = guarded_system
    # Below these: ``nt.spawn*``/``exec*``/``system``/``startfile``, the shell
    # ``cmd /c`` line Popen and os.system compose, and a ctypes binding of a
    # native process or shell launcher.
    sys.addaudithook(_guard.make_audit_hook(_refuse))


def _install_activation_guard():
    """Every entry point in the shared tables, for the session.

    COM activation, the native process creators (``_winapi``/``win32process``
    ``CreateProcess``, below ``Popen``), shell command runners and the launch
    entry points refused outright. The process guard above cannot see most of
    these: ``SldWorks.Application``'s LocalServer32 is SLDWORKS.exe itself, so
    a Dispatch starts SolidWorks without any Popen. Collection is covered too.
    """
    class_ids = _guard.launcher_class_ids()
    # The vendored adapter imports only from cad/scripts; append it so its
    # launch entry points are bound here, before any test imports them. A
    # private nested project (a copy of this conftest) has no adapter to guard.
    scripts = Path(__file__).resolve().parent / "cad" / "scripts"
    if scripts.is_dir() and str(scripts) not in sys.path:
        sys.path.append(str(scripts))
    for module_name in _guard.GUARDED_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            if module_name.startswith("solidworks_mcp.") and scripts.is_dir():
                raise
            continue
        _guard.guard_module(module_name, module, _refuse, class_ids)


def _guard_child_processes(config):
    """Give a worker its own log; its nested descendants keep that same log."""
    global _child_log, _child_log_read
    if hasattr(config, "workerinput") or not os.environ.get(_guard.MARKER):
        handle, path = tempfile.mkstemp(prefix="solidworks-refusals-", suffix=".log")
        os.close(handle)
        os.environ[_guard.MARKER] = path
    _child_log = os.environ[_guard.MARKER]
    _child_log_read = os.path.getsize(_child_log)
    entries = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    if str(_CHILD_GUARD_DIR) not in entries:
        os.environ["PYTHONPATH"] = os.pathsep.join(
            [str(_CHILD_GUARD_DIR), *filter(None, entries)]
        )


def _child_refusals():
    """Refusals guarded children recorded since the last call."""
    global _child_log_read
    if _child_log is None:
        return []
    try:
        with open(_child_log, encoding="utf-8") as log:
            log.seek(_child_log_read)
            text = log.read()
            _child_log_read = log.tell()
    except OSError:
        return []
    return [text] if text else []


# dodo's COM chokepoint. Tests load dodo both by ``import dodo`` and as fresh
# ``spec_from_file_location`` copies, so every load of a ``dodo.py`` is guarded
# as it finishes executing. Collaborator identity, not the call, decides: a
# test that fakes ``_run_subprocess`` or dodo's ``subprocess.run``/``Popen`` is
# already hermetic and keeps exercising the real ``_exec_com``.
def _install_dodo_guard():
    original_exec_module = SourceFileLoader.exec_module

    def exec_module(self, module):
        original_exec_module(self, module)
        if os.path.basename(self.path).lower() == "dodo.py":
            _guard._guard_dodo(module, _refuse)

    SourceFileLoader.exec_module = exec_module
    if "dodo" in sys.modules:
        _guard._guard_dodo(sys.modules["dodo"], _refuse)


def _memoize_doit_plugin_entry_points():
    """Scan installed entry points once per session for doit's plugin lookups.

    Every in-process ``DoitMain`` asks ``importlib.metadata`` for each plugin
    category, and each ask reads the metadata of every installed distribution.
    Tests build many doit mains (``tests/test_farm_mode.py`` alone made 1,298
    such scans), and the installed distributions cannot change mid-session.
    The result is keyed by the exact query, so each group is still answered by
    the real lookup the first time.
    """
    try:
        import doit.plugin
    except ImportError:
        return
    lookup = doit.plugin.entry_points_impl()
    answers = {}

    def entry_points(**query):
        key = tuple(sorted(query.items()))
        if key not in answers:
            answers[key] = lookup(**query)
        return answers[key]

    doit.plugin.entry_points_impl = lambda: entry_points


def _refuse_watchdog_exit(code):
    _refuse(
        "_watchdog._hard_exit",
        f"exit {code}: inject exit_fn or patch _watchdog._hard_exit",
    )


def _install_watchdog_exit_guard():
    """Replace the watchdog's one hard exit for the session, collection included.

    ``_watchdog._hard_exit`` is ``os._exit``: a deadline or a default-exit
    ``Watchdog`` firing in a test would end pytest itself, with no report. Its
    refusal is recorded like a launch, so it fails the test even when it fires
    on a watchdog thread. Tests that exercise an exit patch ``_hard_exit`` or
    inject ``exit_fn`` themselves. Importing the module here makes every later
    ``import _watchdog`` in this process return the guarded one.
    """
    scripts = Path(__file__).resolve().parent / "cad" / "scripts"
    if not (scripts / "_watchdog.py").is_file():
        return  # A private nested project (a copy of this conftest) has none.
    if "_watchdog" not in sys.modules:
        sys.path.insert(0, str(scripts))
        try:
            importlib.import_module("_watchdog")
        finally:
            sys.path.remove(str(scripts))
    sys.modules["_watchdog"]._hard_exit = _refuse_watchdog_exit


def pytest_configure(config):
    """Isolate the test session from the machine it runs on.

    Point the machine-wide build-graph syntax-facts store at a throwaway
    directory. ``_buildgraph`` persists parse results in ``%LOCALAPPDATA%`` so
    real graph loads skip re-parsing unchanged sources. A test may patch
    analyzer internals; were its results saved to the real store they would be
    served, under a genuine content key, to every later build on this machine.
    Tests therefore never read or write the real store. An explicit setting
    (``off`` or a path) is respected.

    Refuse every SolidWorks start from this process, as
    ``tests/_child_guard/harmonic_solidworks_guard.py`` defines it: a process
    (``subprocess`` down to ``_winapi``/``win32process`` ``CreateProcess``,
    ``os.system``, ``os.spawn*``/``exec*``, ``win32pipe.popen``) whose command
    line names SolidWorks or its launchers, is a shell-open helper or is a
    shell told to open something (``tasklist`` still reads the process
    table); ``os.startfile``, ``ShellExecute(Ex)``, ``WinExec``, services,
    other-user processes and ctypes process launchers; COM activation of, or
    binding to, SolidWorks, a SolidWorks document or a launcher class; the
    SolidworksMCP start/stop/launch entry points; and dodo's ``_exec_com``
    with a real runner. A refusal raises with the caller's stack and fails the
    test even if the code under test swallowed it. Every Python child loads
    the same refusals through ``tests/_child_guard/sitecustomize.py`` and
    exits on one, which fails the test that started it. On every platform,
    and whatever ``NOSW_GUARD`` says, the watchdog's hard exit is refused the
    same way instead of ending pytest.
    """
    _memoize_doit_plugin_entry_points()
    if "HARMONIC_BUILDGRAPH_CACHE" not in os.environ:
        os.environ["HARMONIC_BUILDGRAPH_CACHE"] = tempfile.mkdtemp(
            prefix="buildgraph-facts-"
        )
    # The OpenTelemetry SDK drops every span and log record when this is set,
    # and _telemetry builds its global providers once, on first use. Telemetry
    # tests read real records from in-memory exporters, so a shell exporting
    # it must not reach that first use or the children that inherit it.
    os.environ.pop("OTEL_SDK_DISABLED", None)
    # SolidWorks runs only on Windows; elsewhere there is nothing to start.
    if sys.platform == "win32" and not _guard_disabled():
        global _parent_child_log
        _parent_child_log = (
            None if hasattr(config, "workerinput") else os.environ.get(_guard.MARKER)
        )
        # Inherited hooks must raise/record in this pytest host, not terminate
        # the worker. Fresh Python descendants still use the hard-exit handler.
        _guard._pytest_refuse = _refuse
        _guard_child_processes(config)
        _install_launch_guard()
        _install_activation_guard()
        _install_dodo_guard()
    _install_watchdog_exit_guard()


def pytest_unconfigure(config):
    _SCRATCH.cleanup()


@pytest.fixture
def solidworks_launch_refusals():
    """The refusals recorded so far in this test; a guard test clears them."""
    if _guard_disabled():
        pytest.skip("NOSW_GUARD=0: the SolidWorks launch guard is off")
    return _refused


@pytest.fixture
def solidworks_child_refusals():
    """Take the refusals guarded children recorded; a guard test consumes them."""
    if _guard_disabled():
        pytest.skip("NOSW_GUARD=0: the SolidWorks launch guard is off")
    return _child_refusals


def _take_refusals():
    taken = [*_refused, *_child_refusals()]
    _refused.clear()
    return taken


def _publish_nested_refusals(refusals, config):
    """Keep unconsumed refusals visible to the pytest session that launched us."""
    global _child_log_read
    if not refusals:
        return
    if hasattr(config, "workerinput"):
        # Return evidence through xdist, never through a sibling/controller log.
        config.workeroutput.setdefault("solidworks_refusals", []).extend(refusals)
    elif _parent_child_log is not None:
        with open(_parent_child_log, "a", encoding="utf-8") as log:
            log.write("\n".join(refusals) + "\n")
            if _parent_child_log == _child_log:
                _child_log_read = log.tell()


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    # A crashed worker has no workeroutput. Publish completed workers' evidence
    # immediately: maxfail can finish the session before the final node exits.
    _publish_nested_refusals(
        getattr(node, "workeroutput", {}).get("solidworks_refusals", []), node.config
    )


def pytest_sessionfinish(session, exitstatus):
    # Collection can abort before any autouse fixture gets to enforce the guard.
    _publish_nested_refusals(_take_refusals(), session.config)


@pytest.fixture(autouse=True)
def _no_swallowed_solidworks_launch(request):
    """Fail a test whose code caught a refused launch instead of surfacing it.

    A child's refusal counts too, whatever its exit code did to the test. A
    refusal recorded outside any test body (collection, a wider-scoped
    fixture, an earlier teardown) fails the next test rather than vanishing.
    """
    earlier = _take_refusals()
    if earlier:
        _publish_nested_refusals(earlier, request.config)
        attempts = "\n".join(earlier)
        pytest.fail(
            f"SolidWorks launch attempt(s) refused before this test:\n{attempts}",
            pytrace=False,
        )
    yield
    refused = _take_refusals()
    if refused:
        _publish_nested_refusals(refused, request.config)
        attempts = "\n".join(refused)
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
def _cache_refresh_isolated(monkeypatch):
    """Build refreshes must not change the synthetic graphs exercised by checks.

    check:* subprocesses inherit their build's carrier, but a test's fake tasks
    and cache modes are independent invocations. Tests of refresh set it explicitly.
    """
    monkeypatch.delenv("HARMONIC_CACHE_REFRESH", raising=False)


@pytest.fixture(autouse=True)
def _farm_run_isolated(monkeypatch):
    """A farm build's identity must not reach the tests its check:* gates run.

    ``farm_build.py _build`` exports the run's executor, commit, display name,
    leaf timeout, run id and run directory, and the producer adds the build id
    and admitted leaves; every check:* subprocess inherits them. A test that
    dispatches a fake leaf would then use the real budget in its workflow ID and
    record that fake leaf in the real run's directory, where ``farm_build.py
    cancel`` can never close it. Tests of these variables set them explicitly.
    """
    for name in list(os.environ):
        if name == "HARMONIC_EXECUTOR" or name.startswith("HARMONIC_FARM_"):
            monkeypatch.delenv(name)


@pytest.fixture
def saved_native_bytes():
    """Build the observed native DisplayLists envelope for parser-backed tests."""
    import struct
    import zlib

    def native(*flags):
        records = []
        for index, flag in enumerate(flags or (1,)):
            path = rf"C:\parts\part-{index}.SLDPRT".encode("utf-16le")
            records.append(
                b"\xff\xfe\xff"
                + bytes([len(path) // 2])
                + path
                + b"\x00" * 8
                + struct.pack("<IdI", 6, 1000.0, flag)
            )
        data = b"".join(records)
        compressor = zlib.compressobj(wbits=-15)
        payload = compressor.compress(data) + compressor.flush()
        name = b"Contents/DisplayLists"
        swapped = bytes(((byte << 4) & 0xF0) | (byte >> 4) for byte in name)
        return (
            bytes.fromhex("140006000800")
            + b"\x00" * 4
            + struct.pack("<4I", zlib.crc32(data), len(payload), len(data), len(name))
            + swapped
            + payload
        )

    return native

"""The doit graph load (dodo import + task generation) is one ``doit.load`` span on
the ``build-infra`` resource, emitted once whichever entry point loads the graph
(``python -m doit`` or ``build.py``), and never fails the load."""

import importlib.util
import runpy
import sys
import types
from pathlib import Path

import pytest
from doit.cmd_base import DodoTaskLoader, NamespaceTaskLoader

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

import _doit_load  # noqa: E402
import build  # noqa: E402


class _Span:
    def __init__(self, name, start_time, attributes):
        self.name, self.start_time, self.attributes = name, start_time, attributes
        self.status = self.end_time = None
        self.exceptions = []

    def set_status(self, status):
        self.status = status

    def record_exception(self, exc):
        self.exceptions.append(exc)

    def end(self, end_time=None):
        self.end_time = end_time


def _fake_telemetry(monkeypatch):
    spans, services = [], []

    def start_span(name, context, start_time, attributes):
        spans.append(_Span(name, start_time, attributes))
        spans[-1].context = context
        return spans[-1]

    tracer = types.SimpleNamespace(start_span=start_span)

    def get_tracer(service=None):
        services.append(service)
        return tracer

    module = types.SimpleNamespace(
        get_tracer=get_tracer,
        BUILD_INFRA_SERVICE="build-infra",
        _parent_context_from_env=lambda: "leaf-trace",
    )
    monkeypatch.setitem(sys.modules, "_telemetry", module)
    return spans, services


_STAMPED = (
    "import time\n"
    "_started = time.time_ns()\n"
    "import _doit_load\n"
    "_DOIT_LOAD = _doit_load.LoadStamp(_started)\n"
    "_doit_load.watch_import(_DOIT_LOAD)\n"
    "_doit_load.install()\n"
)
_TASKS = (
    "def task_one():\n    return {'actions': None}\n"
    "def task_two():\n    return {'actions': None}\n"
)


@pytest.fixture
def graph(tmp_path, monkeypatch):
    """A stamped dodo file under a unique module name, with doit's loader
    unwrapped for the test and get_module's chdir/sys.path edits undone after."""
    monkeypatch.setattr(DodoTaskLoader, "load_tasks", NamespaceTaskLoader.load_tasks)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))

    def write(source=_STAMPED + _TASKS):
        # doit imports the dodo file by module name, so a plain ``dodo.py`` would
        # resolve to the repo's own ``dodo`` once another test has imported it.
        dodo = tmp_path / f"dodo_{tmp_path.name}.py"
        dodo.write_text(source, encoding="utf-8")
        monkeypatch.delitem(sys.modules, dodo.stem, raising=False)
        return dodo

    return write


def _load(dodo, targets, command_name="run"):
    loader = DodoTaskLoader()
    loader.cmd_names = []
    loader.config = {}
    loader.setup({"dodoFile": str(dodo), "cwdPath": None, "seek_file": False})
    loader.load_doit_config()
    command = types.SimpleNamespace(execute_tasks=True, get_name=lambda: command_name)
    return loader.load_tasks(command, targets)


def test_graph_load_is_one_back_dated_build_infra_span(graph, monkeypatch):
    spans, services = _fake_telemetry(monkeypatch)

    tasks = _load(graph(), ["one"])

    assert [t.name for t in tasks] == ["one", "two"]
    (span,) = spans
    assert span.name == "doit.load"
    assert services == ["build-infra"]
    assert span.start_time <= span.end_time
    assert span.attributes["doit.command"] == "run"
    assert span.attributes["doit.targets"] == "one"
    assert span.attributes["doit.tasks"] == 2
    assert span.attributes["label"] == "one"
    assert span.context == "leaf-trace"


def test_python_dash_m_doit_emits_the_span(graph, monkeypatch):
    """The documented entry, ``uv run python -m doit``, bypasses build.py."""
    spans, _ = _fake_telemetry(monkeypatch)
    dodo = graph()
    monkeypatch.setattr(sys, "argv", ["doit", "list", "-f", str(dodo)])

    with pytest.raises(SystemExit) as done:
        runpy.run_module("doit", run_name="__main__", alter_sys=False)

    assert done.value.code == 0
    assert [s.name for s in spans] == ["doit.load"]
    assert spans[0].attributes["doit.command"] == "list"
    assert spans[0].attributes["doit.tasks"] == 2


def test_build_py_emits_the_span_exactly_once(graph, monkeypatch):
    # main() writes HARMONIC_EXECUTOR; registering it here restores it after.
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    spans, _ = _fake_telemetry(monkeypatch)
    dodo = graph()

    assert build.main(["--executor", "local", "list", "-f", str(dodo)]) == 0

    assert [s.name for s in spans] == ["doit.load"]
    assert spans[0].attributes["doit.command"] == "list"


def test_a_generator_that_raises_still_writes_one_error_span(graph, monkeypatch):
    """Codex on #863: a failing ``task_*`` left the wrapper before ``record``,
    so the load that failed was exactly the one missing from the trace."""
    spans, _ = _fake_telemetry(monkeypatch)
    dodo = graph(_STAMPED + "def task_boom():\n    raise RuntimeError('bad graph')\n")

    with pytest.raises(RuntimeError, match="bad graph"):
        _load(dodo, ["boom"])

    (span,) = spans
    assert span.name == "doit.load"
    assert not span.status.is_ok
    assert "bad graph" in span.status.description
    assert [str(exc) for exc in span.exceptions] == ["bad graph"]
    assert span.end_time is not None and span.start_time <= span.end_time
    assert "doit.tasks" not in span.attributes and "label" not in span.attributes


def test_a_dodo_that_fails_to_import_still_writes_one_error_span(graph, monkeypatch):
    """Codex on #863: an exception in dodo's own module body (a helper import,
    a module-level computation) unwinds inside doit's ``setup``, before
    ``load_tasks``, so only the import watch can write that load's span."""
    spans, _ = _fake_telemetry(monkeypatch)
    dodo = graph(_STAMPED + "raise RuntimeError('bad import')\n" + _TASKS)

    with pytest.raises(RuntimeError, match="bad import"):
        _load(dodo, ["one"])

    (span,) = spans
    assert span.name == "doit.load"
    assert span.attributes["doit.command"] == "import"
    assert not span.status.is_ok and "bad import" in span.status.description
    assert [str(exc) for exc in span.exceptions] == ["bad import"]
    assert _watch_tools() == []  # the watch is released


def test_python_dash_m_doit_records_a_failed_import(graph, monkeypatch):
    spans, _ = _fake_telemetry(monkeypatch)
    dodo = graph(_STAMPED + "import no_such_helper_module\n" + _TASKS)
    monkeypatch.setattr(sys, "argv", ["doit", "list", "-f", str(dodo)])

    with pytest.raises(SystemExit) as done:
        runpy.run_module("doit", run_name="__main__", alter_sys=False)

    assert done.value.code != 0
    (span,) = spans
    assert not span.status.is_ok and "no_such_helper_module" in span.status.description


def test_a_successful_load_releases_the_import_watch(graph, monkeypatch):
    _fake_telemetry(monkeypatch)

    _load(graph(), ["one"])

    assert _watch_tools() == []


def _watch_tools():
    return [i for i in range(6) if sys.monitoring.get_tool(i) == "harmonic-doit-load"]


def test_an_import_without_a_load_releases_the_import_watch(graph, monkeypatch):
    """dodo imported directly (a test, a helper script) never reaches
    ``load_tasks``: the module's own return still disarms the global event."""
    _fake_telemetry(monkeypatch)
    dodo = graph()
    spec = importlib.util.spec_from_file_location("dodo_import_only", dodo)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert _watch_tools() == []


def test_install_is_idempotent(graph, monkeypatch):
    spans, _ = _fake_telemetry(monkeypatch)
    _doit_load.install()
    _doit_load.install()

    _load(graph(), ["one"])

    assert len(spans) == 1


def test_a_cached_dodo_loaded_again_reports_no_stale_load(graph, monkeypatch):
    spans, _ = _fake_telemetry(monkeypatch)
    dodo = graph()
    _load(dodo, ["one"])

    _load(dodo, ["one"])  # same process: get_module returns the cached module

    assert len(spans) == 1


def test_an_unstamped_dodo_loads_untouched(graph, monkeypatch):
    spans, _ = _fake_telemetry(monkeypatch)
    _doit_load.install()

    assert len(_load(graph(_TASKS), ["one"])) == 2
    assert spans == []


def test_a_target_that_names_no_task_carries_no_label(graph, monkeypatch):
    spans, _ = _fake_telemetry(monkeypatch)

    _load(graph(), ["all"])

    assert "label" not in spans[0].attributes


def test_a_multi_target_load_carries_no_single_label(graph, monkeypatch):
    spans, _ = _fake_telemetry(monkeypatch)

    _load(graph(), ["one", "two"])

    assert "label" not in spans[0].attributes
    assert spans[0].attributes["doit.targets"] == "one two"


def test_telemetry_failure_never_fails_the_load(graph, monkeypatch):
    def broken(service=None):
        raise RuntimeError("exporter down")

    monkeypatch.setitem(
        sys.modules,
        "_telemetry",
        types.SimpleNamespace(get_tracer=broken, BUILD_INFRA_SERVICE="build-infra"),
    )

    assert len(_load(graph(), [])) == 2


def test_the_repo_dodo_carries_the_stamp():
    """The real dodo stamps its namespace under the name the wrapper reads."""
    source = (REPO_ROOT / "dodo.py").read_text(encoding="utf-8")
    assert f"{_doit_load.STAMP_NAME} = _doit_load.LoadStamp(" in source
    assert "_doit_load.install()" in source

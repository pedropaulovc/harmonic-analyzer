"""``build.py`` records the doit graph load (dodo import + task generation) as a
``doit.load`` span on the ``build-infra`` resource, and never fails the load."""

import sys
import types
from pathlib import Path

from doit.cmd_base import DodoTaskLoader, ModuleTaskLoader
from doit.doit_cmd import DoitMain

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import build  # noqa: E402


class _Span:
    def __init__(self, name, start_time, attributes):
        self.name, self.start_time, self.attributes = name, start_time, attributes
        self.status = self.end_time = None

    def set_status(self, status):
        self.status = status

    def end(self, end_time=None):
        self.end_time = end_time


def _fake_telemetry(monkeypatch, spans, services):
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


def _dodo(tmp_path: Path) -> Path:
    # doit imports the dodo file by module name, so a plain ``dodo.py`` would
    # resolve to the repo's own ``dodo`` once another test has imported it.
    dodo = tmp_path / f"dodo_{tmp_path.name}.py"
    dodo.write_text(
        "def task_one():\n    return {'actions': None}\n"
        "def task_two():\n    return {'actions': None}\n",
        encoding="utf-8",
    )
    return dodo


def _load(tmp_path, monkeypatch, targets):
    # get_module chdirs and prepends to sys.path; undo both after the test.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    dodo = _dodo(tmp_path)
    monkeypatch.delitem(sys.modules, dodo.stem, raising=False)
    loader = build._TimedDodoTaskLoader()
    loader.cmd_names = []
    loader.config = {}
    loader.setup(
        {"dodoFile": str(dodo), "cwdPath": None, "seek_file": False}
    )
    loader.load_doit_config()
    command = types.SimpleNamespace(execute_tasks=True, get_name=lambda: "run")
    return loader.load_tasks(command, targets)


def test_graph_load_is_one_back_dated_build_infra_span(tmp_path, monkeypatch):
    spans, services = [], []
    _fake_telemetry(monkeypatch, spans, services)

    tasks = _load(tmp_path, monkeypatch, ["one"])

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


def test_a_target_that_names_no_task_carries_no_label(tmp_path, monkeypatch):
    spans, services = [], []
    _fake_telemetry(monkeypatch, spans, services)

    _load(tmp_path, monkeypatch, ["all"])

    assert "label" not in spans[0].attributes


def test_a_multi_target_load_carries_no_single_label(tmp_path, monkeypatch):
    spans, services = [], []
    _fake_telemetry(monkeypatch, spans, services)

    _load(tmp_path, monkeypatch, ["one", "two"])

    assert "label" not in spans[0].attributes
    assert spans[0].attributes["doit.targets"] == "one two"


def test_telemetry_failure_never_fails_the_load(tmp_path, monkeypatch):
    def broken(service=None):
        raise RuntimeError("exporter down")

    monkeypatch.setitem(
        sys.modules,
        "_telemetry",
        types.SimpleNamespace(get_tracer=broken, BUILD_INFRA_SERVICE="build-infra"),
    )

    assert len(_load(tmp_path, monkeypatch, [])) == 2


def test_main_times_only_doits_default_loader(monkeypatch):
    # main() writes HARMONIC_EXECUTOR; registering it here restores it after.
    monkeypatch.setenv("HARMONIC_EXECUTOR", "local")
    seen = []

    class Recording(DoitMain):
        def run(self, args):
            seen.append(self.task_loader)
            return 0

    monkeypatch.setattr(build, "DoitMain", Recording)
    assert build.main(["--executor", "local", "list"]) == 0
    assert isinstance(seen[-1], build._TimedDodoTaskLoader)
    assert isinstance(seen[-1], DodoTaskLoader)

    explicit = ModuleTaskLoader({})

    class Explicit(Recording):
        def __init__(self):
            super().__init__(task_loader=explicit)

    monkeypatch.setattr(build, "DoitMain", Explicit)
    assert build.main(["--executor", "local", "list"]) == 0
    assert seen[-1] is explicit

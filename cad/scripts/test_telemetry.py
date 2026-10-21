r"""Tests for the OpenTelemetry observability spine (cad/scripts/_telemetry.py).

Pure python, NO SolidWorks: spans + logs are captured by attaching in-memory
exporters to the configured providers, so the assertions read the real OTel
records the pipeline would emit. Covers the four things the spine promises:
severity-levelled logs, no-gap spans (exceptions recorded + status ERROR),
log<->trace correlation, and cross-process trace-context propagation.

    python cad/scripts/test_telemetry.py     # or: pytest cad/scripts/test_telemetry.py
"""

from __future__ import annotations

import asyncio
import builtins
import importlib.util
import inspect
import json
import logging
import os
import socket
import subprocess
import sys
import time
import types
from pathlib import Path
from typing import cast

import pytest
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggerProvider as SdkLoggerProvider
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF
from opentelemetry.trace import NonRecordingSpan

sys.path.insert(0, str(Path(__file__).resolve().parent))

_OTLP_ENV_NAMES = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_TIMEOUT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
    "OTEL_EXPORTER_OTLP_TRACES_TIMEOUT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
    "OTEL_EXPORTER_OTLP_LOGS_TIMEOUT",
)
_original_otlp_environment = {name: os.environ.get(name) for name in _OTLP_ENV_NAMES}
try:
    for _name in _OTLP_ENV_NAMES:
        os.environ.pop(_name, None)
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
    import _telemetry  # noqa: E402
finally:
    for _name in _OTLP_ENV_NAMES:
        os.environ.pop(_name, None)
    os.environ.update(
        {
            name: value
            for name, value in _original_otlp_environment.items()
            if value is not None
        }
    )


def _exporter_of(processor):
    """Return the exporter across supported OTel batch-processor layouts."""
    batch_processor = getattr(processor, "_batch_processor", None)
    if batch_processor is not None:
        return batch_processor._exporter
    span_exporter = getattr(processor, "span_exporter", None)
    if span_exporter is not None:
        return span_exporter
    return processor._exporter


@pytest.fixture(autouse=True)
def deterministic_otlp_environment(monkeypatch):
    """Keep every test offline, then restore a clean provider and caller env."""
    for name in _OTLP_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    yield

    monkeypatch.undo()
    _telemetry.shutdown()
    restored = {name: os.environ.get(name) for name in _OTLP_ENV_NAMES}
    try:
        for name in _OTLP_ENV_NAMES:
            os.environ.pop(name, None)
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""
        _telemetry.configure(force=True)
    finally:
        for name in _OTLP_ENV_NAMES:
            os.environ.pop(name, None)
        os.environ.update(
            {name: value for name, value in restored.items() if value is not None}
        )


@pytest.fixture
def capture():
    """Attach in-memory exporters to the spine's live providers.

    The providers are the process-global ones installed at import (OTel forbids
    replacing a set provider, so we add to the same ones the handlers emit to);
    each test reads a fresh exporter, so it only sees its own records.
    """
    _telemetry.configure()

    spans = InMemorySpanExporter()
    processor = SimpleSpanProcessor(spans)
    cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider()).add_span_processor(
        processor
    )
    # Auxiliary per-resource providers (build-infra) are built lazily from
    # ``_span_processors``, so register there too -- and drop any already built -- or
    # a test would see nothing from spans emitted under another resource.
    _telemetry._span_processors.append(processor)
    _telemetry._aux_providers.clear()

    logs = InMemoryLogRecordExporter()
    log_processor = SimpleLogRecordProcessor(logs)
    cast(SdkLoggerProvider, get_logger_provider()).add_log_record_processor(
        log_processor
    )
    # Likewise for the per-resource logger providers a routed record lands on.
    _telemetry._log_processors.append(log_processor)
    _telemetry._aux_logger_providers.clear()
    yield spans, logs

    _telemetry._span_processors.remove(processor)
    _telemetry._aux_providers.clear()
    _telemetry._log_processors.remove(log_processor)
    _telemetry._aux_logger_providers.clear()


def test_logs_split_into_severity_levels(capture):
    _, logs = capture
    _telemetry.debug("chatter")
    _telemetry.info("neutral")
    _telemetry.success("passed")
    _telemetry.warn("careful")
    _telemetry.error("broke")

    seen = {r.log_record.severity_text for r in logs.get_finished_logs()}
    assert {"DEBUG", "INFO", "SUCCESS", "WARN", "ERROR"} <= seen


def test_console_verbosity_configures_handler_and_spans(monkeypatch):
    logger = logging.getLogger(_telemetry._LOGGER_NAME)
    monkeypatch.setattr(
        _telemetry, "_resolve_otlp_endpoint", lambda signal, **kwargs: None
    )
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)

    def console_handlers():
        return [
            handler
            for handler in logger.handlers
            if isinstance(handler, logging.StreamHandler)
        ]

    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    _telemetry.configure(force=True)
    (handler,) = console_handlers()
    assert handler.level == logging.WARNING
    assert _telemetry._span_processors == []

    monkeypatch.setenv("HARMONIC_VERBOSITY", "success")
    _telemetry.configure(force=True)
    (handler,) = console_handlers()
    assert handler.level == _telemetry.SUCCESS
    assert _telemetry._span_processors == []


def test_span_records_exception_and_sets_error_status(capture):
    spans, _ = capture
    with pytest.raises(RuntimeError):
        with _telemetry.span("risky", part="cone_gear"):
            raise RuntimeError("sketch OVER-defined")

    (sp,) = [s for s in spans.get_finished_spans() if s.name == "risky"]
    assert sp.status.status_code.name == "ERROR"
    # exactly one exception event -- not double-recorded
    assert [e.name for e in sp.events] == ["exception"]
    assert sp.attributes["part"] == "cone_gear"
    # the cause rides the span itself: the exported exception event arrives in
    # App Insights with an empty message, so a failed row must explain itself
    assert sp.attributes["error.type"] == "RuntimeError"
    assert sp.attributes["error.message"] == "sketch OVER-defined"


@pytest.fixture
def nonrecording_tracer(monkeypatch):
    provider = SdkTracerProvider(sampler=ALWAYS_OFF)
    tracer = provider.get_tracer("test.nonrecording")
    monkeypatch.setattr(_telemetry, "get_tracer", lambda *args, **kwargs: tracer)
    yield
    provider.shutdown()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "outcome", [2, SystemExit(2), RuntimeError("original failure")]
)
def test_nonrecording_span_preserves_body_outcome(
    nonrecording_tracer, asynchronous, outcome
):
    depth = _telemetry._depth.get()
    parent = _telemetry.trace.get_current_span()

    def body(sp):
        assert isinstance(sp, NonRecordingSpan)
        assert not sp.is_recording()
        if isinstance(outcome, BaseException):
            raise outcome
        # Like prechips_traveler.main(), mark ERROR and return the CLI's code.
        sp.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, "exit 2"))
        return outcome

    def synchronous():
        with _telemetry.span("nonrecording") as sp:
            return body(sp)

    async def asynchronous_body():
        async with _telemetry.aspan("nonrecording") as sp:
            return body(sp)

    def invoke():
        return asyncio.run(asynchronous_body()) if asynchronous else synchronous()

    if isinstance(outcome, BaseException):
        with pytest.raises(type(outcome)) as caught:
            invoke()
        assert caught.value is outcome
    else:
        assert invoke() == outcome
    assert _telemetry._depth.get() == depth
    assert _telemetry.trace.get_current_span() is parent


@pytest.mark.parametrize("code", [2, 3, 4])
def test_prechips_check_nonrecording_span_preserves_exit_code(
    nonrecording_tracer, monkeypatch, tmp_path, code
):
    import prechips_traveler as wrapper

    directory = tmp_path / "traveler"
    monkeypatch.setattr(wrapper._telemetry, "set_service", lambda *args: None)
    monkeypatch.setattr(
        wrapper.telemetry,
        "configure",
        lambda *args: types.SimpleNamespace(trace_provider=None, log_provider=None),
    )
    monkeypatch.setattr(
        wrapper._telemetry, "capture_external_telemetry", lambda *args: None
    )
    monkeypatch.setattr(wrapper._process_plans, "traveler_dir", lambda *args: directory)
    monkeypatch.setattr(
        wrapper._process_plans,
        "bind_shop",
        lambda *args, **kwargs: tuple(
            tmp_path / name for name in ("inventory", "policy", "data")
        ),
    )
    monkeypatch.setattr(
        wrapper._process_plans,
        "bind_plan",
        lambda *args, **kwargs: tmp_path / "plan.toml",
    )
    monkeypatch.setattr(wrapper.kernel, "discover_kernel", lambda: "stub-kernel")
    calls = []

    def cli(argv):
        calls.append(argv)
        return code

    monkeypatch.setattr(wrapper.cli, "main", cli)
    # Keep the real wrapper and telemetry context managers: existing wrapper
    # unit tests replace spans and cannot detect a cleanup masking the CLI exit.
    with pytest.raises(SystemExit) as caught:
        raise SystemExit(
            wrapper.main(["ch_rocker_arm", "--out", str(tmp_path), "--check"])
        )
    assert caught.value.code == code
    assert calls[0][0] == "check"


def _log_from_a_named_caller(message: str) -> None:
    _telemetry.info(message)


def _record_named(logs, body: str):
    return next(
        r.log_record for r in logs.get_finished_logs() if r.log_record.body == body
    )


def test_log_records_name_the_code_that_logged_them(capture, tmp_path):
    """App Insights maps a dark stretch of a build span to code through the
    ``code.*`` attributes of the record that ends it -- so they must name the
    caller, not the helper that happened to hold the logging call, nor
    ``_check``'s pass-through ``log`` / ``check`` aliases, nor the span context
    manager that logs a failure on the caller's behalf."""
    _, logs = capture
    _log_from_a_named_caller("direct")
    rec = _record_named(logs, "direct")
    assert rec.attributes["code.function.name"] == "_log_from_a_named_caller"
    assert Path(rec.attributes["code.file.path"]).name == "test_telemetry.py"

    shim = tmp_path / "_check.py"
    shim.write_text(
        "import _telemetry\n"
        "def log(message):\n"
        "    _telemetry.progress(message)\n"
        "def check(label, result):\n"
        "    _telemetry.success(label)\n"
        "    return result\n",
        encoding="utf-8",
    )
    spec = importlib.util.spec_from_file_location("_telemetry_test_check_shim", shim)
    assert spec is not None and spec.loader is not None
    check_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_module)

    def build_step():
        check_module.log("through log")
        check_module.check("through check", None)

    build_step()
    for body in ("through log", "through check"):
        assert (
            _record_named(logs, body).attributes["code.function.name"] == "build_step"
        )

    def failing_step():
        with _telemetry.span("step"):
            raise ValueError("boom")

    with pytest.raises(ValueError):
        failing_step()
    rec = _record_named(logs, "step failed: boom")
    assert rec.attributes["code.function.name"] == "failing_step"


def test_clean_span_is_ok(capture):
    spans, _ = capture
    with _telemetry.span("fine"):
        _telemetry.success("did the thing")
    (sp,) = [s for s in spans.get_finished_spans() if s.name == "fine"]
    assert sp.status.status_code.name == "OK"


def test_explicit_error_status_survives_clean_exit(capture):
    """run_build sets ERROR on the root span then returns (a clean exit) when a
    build fails; span() must NOT overwrite that with OK -- it only fills OK when
    the status is still UNSET."""
    spans, _ = capture
    with _telemetry.span("failed_build") as sp:
        sp.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, "build failed"))
        # no exception raised -- the with-block exits normally, as run_build does
    (done,) = [s for s in spans.get_finished_spans() if s.name == "failed_build"]
    assert done.status.status_code.name == "ERROR"
    # no exception was recorded, so the status description is the only cause
    assert done.attributes["error.type"] == "_OTHER"
    assert done.attributes["error.message"] == "build failed"


def test_standalone_build_failure_root_carries_its_cause(capture, monkeypatch):
    """``run_build`` run standalone catches the build's exception, records it on
    the ``build.<target>`` root, marks it ERROR and exits the session cleanly --
    the root must still say WHY, as a raising span does."""
    spans, _ = capture
    monkeypatch.delenv("TRACEPARENT", raising=False)
    monkeypatch.delenv("TRACESTATE", raising=False)
    with _telemetry.build_session("cone_gear") as root:
        assert root is not None
        try:
            raise RuntimeError("tooth pattern failed: no seed feature")
        except RuntimeError as exc:
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
    (done,) = [s for s in spans.get_finished_spans() if s.name == "build.cone_gear"]
    assert done.status.status_code.name == "ERROR"
    assert done.attributes["error.type"] == "RuntimeError"
    assert done.attributes["error.message"] == "tooth pattern failed: no seed feature"


def test_a_cause_stamped_by_the_code_is_not_overwritten(capture):
    spans, _ = capture
    with _telemetry.span("gate") as sp:
        sp.set_attributes({"error.type": "GateRefusal", "error.message": "3 stray DOF"})
        sp.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, "gate refused"))
    (done,) = [s for s in spans.get_finished_spans() if s.name == "gate"]
    assert done.attributes["error.type"] == "GateRefusal"
    assert done.attributes["error.message"] == "3 stray DOF"


def test_logs_correlate_to_active_span(capture):
    spans, logs = capture
    with _telemetry.span("parent"):
        _telemetry.info("inside the span")

    (sp,) = [s for s in spans.get_finished_spans() if s.name == "parent"]
    rec = next(
        r.log_record
        for r in logs.get_finished_logs()
        if r.log_record.body == "inside the span"
    )
    assert rec.trace_id == sp.context.trace_id
    assert rec.span_id == sp.context.span_id


def test_nested_spans_share_one_trace(capture):
    spans, _ = capture
    with _telemetry.run_pipeline_span("build"):
        with _telemetry.span("child_a"):
            with _telemetry.span("grandchild"):
                pass
        with _telemetry.span("child_b"):
            pass
    traces = {s.context.trace_id for s in spans.get_finished_spans()}
    assert len(traces) == 1  # no gaps: every span hangs off the one root trace


def test_attribute_names_the_log_farm_selects_on_are_pinned_here(capture):
    """CONSUMER: solidworks-pool ``farm.py logs`` (``_logs_labels_block``), which
    reads a RUNNING leaf's lines out of the workspace these spans feed:

        | extend depth = toint(todynamic(Attributes)['harmonic.depth'])
        | extend label = tostring(todynamic(Attributes).label)
        | where depth == 0 and isnotempty(label)

    Rename either key here, or stop emitting 0 at a process's top level, and
    that query matches nothing: every farm leaf becomes unattributable, its
    lines arrive with no leaf name, and the command can only fall back to
    guessing from the worker. No test in the pool repo can red on a rename in
    this file -- it builds the attribute names by hand, because it has no
    other choice -- so the pin belongs here, on the producing side.

    ``harmonic.depth`` is per-PROCESS, not per-trace: a leaf's trace holds
    depth-0 spans from the doit parent (``task <label>``) AND from the build
    subprocess it spawned (``proc.startup``, ``sw.connect``, ``<kind>.build``).
    The pool resolves the leaf only because it also requires exactly one
    DISTINCT label among those depth-0 spans, and the subprocess ones carry
    none. Two rules, then: do not rename or flatten these keys, and never put
    ``label`` on a span opened at the top level of a build subprocess. The
    depth half of the second rule is pinned by
    ``test_build_session_continues_injected_parent_without_duplicate``.

    The depth-1 assertion is load-bearing, not decoration: ``label`` is reused
    at depth >= 1 for DIMENSION names (``blank_od``), and the measured ratio in
    one build window was 1443 depth-1 labels against 309 depth-0 leaf labels.
    ``depth == 0`` is what stops the pool from filing a leaf's output under a
    sketch dimension, so a change that flattens depth is as damaging as a
    rename.
    """
    spans, _ = capture
    with _telemetry.span("task part:cone_gear", label="part:cone_gear"):
        with _telemetry.span("sketch.circle", label="blank_od"):
            pass

    finished = {s.name: s for s in spans.get_finished_spans()}
    root = finished["task part:cone_gear"]
    child = finished["sketch.circle"]
    assert root.attributes["harmonic.depth"] == 0
    assert root.attributes["label"] == "part:cone_gear"
    assert child.attributes["harmonic.depth"] == 1
    assert child.attributes["label"] == "blank_od"


def test_traced_decorator_wraps_sync_and_async(capture):
    spans, _ = capture

    @_telemetry.traced("op.async", label_param="label")
    async def afn(label):
        return label

    @_telemetry.traced("op.sync")
    def sfn():
        return 1

    assert asyncio.run(afn("widget")) == "widget"
    assert sfn() == 1

    a = [s for s in spans.get_finished_spans() if s.name == "op.async"][-1]
    s = [s for s in spans.get_finished_spans() if s.name == "op.sync"][-1]
    assert a.attributes["label"] == "widget"  # label_param copied onto the span
    assert a.status.status_code.name == "OK"
    assert s.status.status_code.name == "OK"


def test_traced_decorator_records_failure(capture):
    spans, _ = capture

    @_telemetry.traced("op.boom")
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        boom()
    sp = [s for s in spans.get_finished_spans() if s.name == "op.boom"][-1]
    assert sp.status.status_code.name == "ERROR"


def test_build_session_standalone_opens_root(capture, monkeypatch):
    """No injected parent -> a local pipeline.part.build root, so the build's
    operation spans are never unparented."""
    spans, _ = capture
    monkeypatch.delenv("TRACEPARENT", raising=False)
    monkeypatch.delenv("TRACESTATE", raising=False)
    with _telemetry.build_session("cone_gear") as root:
        assert root is not None
        with _telemetry.span("op"):
            pass
    rootspan = [s for s in spans.get_finished_spans() if s.name == "build.cone_gear"][
        -1
    ]
    op = [s for s in spans.get_finished_spans() if s.name == "op"][-1]
    assert rootspan.attributes["label"] == "cone_gear"
    assert op.parent.span_id == rootspan.context.span_id


def test_build_session_continues_injected_parent_without_duplicate(
    capture, monkeypatch
):
    """Under the doit spine (a parent TRACEPARENT is injected) build_session
    yields None and the operation spans attach straight to the injected trace --
    no second pipeline.part.build layer duplicating the doit task span."""
    spans, _ = capture
    monkeypatch.delenv("TRACEPARENT", raising=False)
    with _telemetry.span("part:cone_gear"):
        env = _telemetry.inject_env()
    monkeypatch.setenv("TRACEPARENT", env["TRACEPARENT"])
    if env.get("TRACESTATE"):
        monkeypatch.setenv("TRACESTATE", env["TRACESTATE"])

    with _telemetry.build_session("build_dt_cone_gear") as root:
        assert root is None  # no duplicate root layer
        with _telemetry.span("op"):
            pass

    task = [s for s in spans.get_finished_spans() if s.name == "part:cone_gear"][-1]
    op = [s for s in spans.get_finished_spans() if s.name == "op"][-1]
    assert op.context.trace_id == task.context.trace_id
    assert op.parent.trace_id == task.context.trace_id
    # `harmonic.depth` is per-PROCESS, not per-trace: a span opened at the top
    # level of a continued session reads 0 even though the trace already has a
    # depth-0 span (the doit task) in the parent process. That is what the pool
    # query relies on -- it selects depth == 0 AND a non-empty `label`, and
    # resolves a leaf only when the trace holds exactly ONE distinct label. So
    # a subprocess top-level span must never carry `label`; this assertion is
    # here so the depth half of that rule cannot change unnoticed.
    assert op.attributes["harmonic.depth"] == 0


def test_cross_process_trace_propagation(tmp_path):
    """A child process started with :func:`inject_env` continues the parent's
    trace -- the doit-spine -> build-subprocess boundary is gapless."""
    child = (
        "import _telemetry as t, sys\n"
        "with t.run_pipeline_span('child'):\n"
        "    sp = t.trace.get_current_span()\n"
        "    sys.stdout.write(format(sp.get_span_context().trace_id, '032x'))\n"
    )
    _telemetry.configure()
    with _telemetry.run_pipeline_span("parent"):
        parent_trace = format(
            _telemetry.trace.get_current_span().get_span_context().trace_id, "032x"
        )
        env = _telemetry.inject_env()
        assert "TRACEPARENT" in env
        out = subprocess.run(
            [sys.executable, "-c", child],
            env=env,
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
        )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == parent_trace


def test_build_infra_spans_carry_their_own_resource(capture):
    """The COM seat queue and the artefact cache are not a pipeline STAGE, so their
    spans are attributed to a ``build-infra`` resource instead of this process's --
    two resources from one process, which takes a second provider (a resource is
    fixed at provider creation). Only the resource differs: the span still nests
    normally and rides the same exporters."""
    spans, _ = capture
    with _telemetry.span("task part:cone_gear"):
        with _telemetry.span(
            "com.seat.wait part:cone_gear", service=_telemetry.BUILD_INFRA_SERVICE
        ) as seat:
            seat_trace = seat.get_span_context().trace_id

    finished = {s.name: s for s in spans.get_finished_spans()}
    task, wait = (
        finished["task part:cone_gear"],
        finished["com.seat.wait part:cone_gear"],
    )
    assert wait.resource.attributes["service.name"] == "build-infra"
    assert task.resource.attributes["service.name"] == _telemetry._service_name
    assert wait.resource.attributes["service.namespace"] == "harmonic-analyzer"
    # Provider ≠ context: the infra span still parents under the task span.
    assert seat_trace == task.context.trace_id
    assert wait.parent.span_id == task.context.span_id


def test_logs_take_the_resource_of_the_span_they_are_written_under(capture):
    """A ``[cache]`` line written under ``cache.probe`` must land on the same
    ``build-infra`` resource as that span, not on the process's own (76.9k doit
    parent rows were filed under the umbrella resource). A record outside any
    such span keeps the process resource unless it names one explicitly, and
    the routing key never leaks into the exported attributes."""
    _, logs = capture
    infra = _telemetry.BUILD_INFRA_SERVICE
    with _telemetry.span("task part:cone_gear"):
        _telemetry.info("stage line")
        with _telemetry.span("cache.probe part:cone_gear", service=infra):
            _telemetry.info("[cache] miss")
    _telemetry.info("[com.seat] released", service=infra)
    _telemetry.info("plain line")

    records = {
        str(r.log_record.body): r for r in logs.get_finished_logs()
    }
    service = {
        body: rec.resource.attributes["service.name"] for body, rec in records.items()
    }
    assert service["[cache] miss"] == infra
    assert service["[com.seat] released"] == infra
    assert service["stage line"] == _telemetry._service_name
    assert service["plain line"] == _telemetry._service_name
    for rec in records.values():
        assert _telemetry._SERVICE_RECORD_ATTR not in (rec.log_record.attributes or {})


def test_every_resource_identifies_the_machine(capture):
    """Azure Monitor derives ``cloud_RoleInstance`` from ``service.instance.id``, so
    a resource without it makes a multi-worker build farm unattributable -- every
    worker's spans land in one anonymous bucket. Both resources a process can emit
    under (its stage and ``build-infra``) must carry it."""
    spans, _ = capture
    with _telemetry.span("task part:cone_gear"):
        with _telemetry.span(
            "com.seat.wait part:cone_gear", service=_telemetry.BUILD_INFRA_SERVICE
        ):
            pass

    finished = {s.name: s for s in spans.get_finished_spans()}
    for name in ("task part:cone_gear", "com.seat.wait part:cone_gear"):
        instance = finished[name].resource.attributes.get("service.instance.id")
        assert instance, f"{name} has no service.instance.id"


@pytest.mark.parametrize("service", [None, _telemetry.BUILD_INFRA_SERVICE])
def test_farm_identity_does_not_short_circuit_provider_force_flush(monkeypatch, service):
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "farm.execution=flush-execution")
    _telemetry.configure(console=False, force=True)
    provider = (
        _telemetry.trace.get_tracer_provider()
        if service is None
        else _telemetry._provider_for_service(service)
    )
    exporter = InMemorySpanExporter()
    processor = BatchSpanProcessor(exporter, schedule_delay_millis=600000)
    provider.add_span_processor(processor)
    try:
        with provider.get_tracer("flush-proof").start_as_current_span("buffered"):
            pass
        assert not exporter.get_finished_spans()
        assert provider.force_flush(timeout_millis=2000) is True
        finished = exporter.get_finished_spans()
        assert len(finished) == 1
        assert finished[0].name == "buffered"
        assert finished[0].attributes["farm.execution"] == "flush-execution"
    finally:
        processor.shutdown()


@pytest.mark.parametrize("service", [None, _telemetry.BUILD_INFRA_SERVICE])
def test_farm_resource_identity_reaches_exported_records(monkeypatch, request, service):
    identity = {
        "farm.workflow_id": "leaf:build:part:example:key:3600s",
        "farm.run_id": "temporal-run",
        "farm.attempt": "2",
        "farm.execution": "execution",
        "farm.worker": "worker@slot",
    }
    monkeypatch.setenv(
        "OTEL_RESOURCE_ATTRIBUTES",
        ",".join(f"{key}={value}" for key, value in identity.items())
        + ",microsoft.applicationId=route-only,unrelated.resource=not-record-data",
    )
    _telemetry.configure(console=False, force=True)
    spans, logs = request.getfixturevalue("capture")
    with _telemetry.span("identity", service=service) as active:
        _telemetry.info("inside")
        active_context = active.get_span_context()
    _telemetry.info("outside", service=service)

    finished = spans.get_finished_spans()
    assert len(finished) == 1
    exported = finished[0]
    assert {key: exported.attributes[key] for key in identity} == identity
    records = {str(r.log_record.body): r for r in logs.get_finished_logs()}
    assert set(records) == {"inside", "outside"}
    for record in records.values():
        assert {key: record.log_record.attributes[key] for key in identity} == identity
        assert {key: record.resource.attributes[key] for key in identity} == identity
        assert "microsoft.applicationId" not in record.log_record.attributes
        assert "unrelated.resource" not in record.log_record.attributes
    assert "microsoft.applicationId" not in exported.attributes
    assert "unrelated.resource" not in exported.attributes
    assert records["inside"].log_record.trace_id == active_context.trace_id
    assert records["inside"].log_record.span_id == active_context.span_id
    assert records["outside"].log_record.span_id == 0
    expected_service = service or _telemetry._service_name
    assert exported.resource.attributes["service.name"] == expected_service
    assert all(
        record.resource.attributes["service.name"] == expected_service
        for record in records.values()
    )


def test_farm_identity_preserves_explicit_record_attributes(monkeypatch, request):
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "farm.attempt=2,farm.worker=provider")
    _telemetry.configure(console=False, force=True)
    spans, logs = request.getfixturevalue("capture")
    with _telemetry.span("explicit", **{"farm.attempt": 7, "farm.worker": "caller"}):
        _telemetry.get_logger().info(
            "explicit", extra={"farm.attempt": 9, "farm.worker": "log-caller"}
        )
    attrs = spans.get_finished_spans()[0].attributes
    assert attrs["farm.attempt"] == 7
    assert attrs["farm.worker"] == "caller"
    attrs = logs.get_finished_logs()[0].log_record.attributes
    assert attrs["farm.attempt"] == 9
    assert attrs["farm.worker"] == "log-caller"


def test_farm_identity_snapshots_each_provider_and_refreshes_on_configure(monkeypatch):
    def capture_providers():
        spans = InMemorySpanExporter()
        logs = InMemoryLogRecordExporter()
        span_processor = SimpleSpanProcessor(spans)
        log_processor = SimpleLogRecordProcessor(logs)
        _telemetry.trace.get_tracer_provider().add_span_processor(span_processor)
        get_logger_provider().add_log_record_processor(log_processor)
        _telemetry._span_processors.append(span_processor)
        _telemetry._log_processors.append(log_processor)
        return spans, logs

    def emit(label):
        with _telemetry.span(label):
            _telemetry.info(label)
            with _telemetry.span(label + "-aux", service=_telemetry.BUILD_INFRA_SERVICE):
                _telemetry.info(label + "-aux")
        _telemetry.info(label + "-plain")
        _telemetry.info(label + "-routed", service=_telemetry.BUILD_INFRA_SERVICE)

    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "farm.execution=old")
    _telemetry.configure(console=False, force=True)
    spans, logs = capture_providers()
    emit("warm")  # Build both auxiliary caches before the environment changes.
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "farm.execution=new")
    emit("cached")
    assert len(spans.get_finished_spans()) == 4
    assert len(logs.get_finished_logs()) == 8
    for span in spans.get_finished_spans():
        assert span.attributes["farm.execution"] == "old"
    for record in logs.get_finished_logs():
        assert record.log_record.attributes["farm.execution"] == "old"

    _telemetry.configure(console=False, force=True)
    spans, logs = capture_providers()
    emit("fresh")
    assert len(spans.get_finished_spans()) == 2
    assert len(logs.get_finished_logs()) == 4
    for span in spans.get_finished_spans():
        assert span.attributes["farm.execution"] == "new"
        assert span.resource.attributes["farm.execution"] == "new"
    for record in logs.get_finished_logs():
        assert record.log_record.attributes["farm.execution"] == "new"
        assert record.resource.attributes["farm.execution"] == "new"

    monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES")
    _telemetry.configure(console=False, force=True)
    spans, logs = capture_providers()
    emit("local")
    assert len(spans.get_finished_spans()) == 2
    assert len(logs.get_finished_logs()) == 4
    for span in spans.get_finished_spans():
        assert not (set(_telemetry._FARM_IDENTITY_KEYS) & set(span.attributes))
    for record in logs.get_finished_logs():
        assert not (
            set(_telemetry._FARM_IDENTITY_KEYS) & set(record.log_record.attributes)
        )


def test_instance_id_prefers_explicit_env_then_worker_identity(monkeypatch):
    """Resolution order, most specific first: an operator's
    ``OTEL_SERVICE_INSTANCE_ID``, then the farm worker identity (two workers can
    share a hostname pattern but never an instance id), then the hostname, which is
    what a developer workstation wants. ``OTEL_RESOURCE_ATTRIBUTES`` is merged by the
    SDK itself, so an instance id declared there must not be overridden here."""
    monkeypatch.delenv("OTEL_SERVICE_INSTANCE_ID", raising=False)
    monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES", raising=False)
    monkeypatch.setenv("HARMONIC_WORKER_ID", "swmaker000005@5")
    assert _telemetry._resolve_instance_id() == "swmaker000005@5"

    monkeypatch.setenv("OTEL_SERVICE_INSTANCE_ID", "operator-choice")
    assert _telemetry._resolve_instance_id() == "operator-choice"

    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "service.instance.id=from-env")
    assert _telemetry._resolve_instance_id() is None

    monkeypatch.delenv("OTEL_RESOURCE_ATTRIBUTES")
    monkeypatch.delenv("OTEL_SERVICE_INSTANCE_ID")
    monkeypatch.delenv("HARMONIC_WORKER_ID")
    assert _telemetry._resolve_instance_id() == socket.gethostname()


def test_instance_id_yields_only_to_an_exact_resource_attribute_key(monkeypatch):
    """``OTEL_RESOURCE_ATTRIBUTES`` entries are matched by exact key, not by
    substring: a neighbouring ``service.instance.identifier`` neither declares the
    instance id nor may suppress it, or every span loses its worker attribution."""
    monkeypatch.delenv("OTEL_SERVICE_INSTANCE_ID", raising=False)
    monkeypatch.setenv("HARMONIC_WORKER_ID", "swmaker000004@4")

    monkeypatch.setenv(
        "OTEL_RESOURCE_ATTRIBUTES", "service.instance.identifier=legacy,host.name=a"
    )
    assert _telemetry._resolve_instance_id() == "swmaker000004@4"

    monkeypatch.setenv(
        "OTEL_RESOURCE_ATTRIBUTES", "host.name=a, service.instance.id=from-env"
    )
    assert _telemetry._resolve_instance_id() is None


def test_process_startup_is_billed_to_the_parent_trace(capture, monkeypatch):
    """The spawn + interpreter + import region between a parent launching a process
    and that process's first span is DARK -- ~2-5 s per COM task. ``inject_env``
    stamps the launch instant and the child draws it as ``proc.startup``
    (``proc.launch`` + ``proc.import``), back-dated via OTel's creation-time
    ``start_time`` -- the sanctioned way to record an interval already past."""
    spans, _ = capture
    now = time.time_ns()
    monkeypatch.setattr(_telemetry, "_startup_recorded", False)
    monkeypatch.setattr(
        _telemetry, "_IMPORT_NS", now - int(1.5e9)
    )  # imported 1.5 s ago
    monkeypatch.setenv(_telemetry.SPAWN_ENV, str(now - int(4.0e9)))  # spawned 4 s ago

    with _telemetry.span("task part:cone_gear"):
        _telemetry.record_process_startup()
        _telemetry.record_process_startup()  # once per process, not once per call

    finished = [s for s in spans.get_finished_spans() if s.name.startswith("proc.")]
    assert [s.name for s in finished] == ["proc.launch", "proc.import", "proc.startup"]
    by_name = {s.name: s for s in finished}
    dur = lambda s: (s.end_time - s.start_time) / 1e9  # noqa: E731
    assert 3.9 < dur(by_name["proc.startup"]) < 4.2, "must span back to the spawn"
    assert 2.4 < dur(by_name["proc.launch"]) < 2.6, "spawn -> _telemetry import"
    assert 1.4 < dur(by_name["proc.import"]) < 1.6, "_telemetry import -> first span"
    assert by_name["proc.launch"].end_time == by_name["proc.import"].start_time
    task = [s for s in spans.get_finished_spans() if s.name == "task part:cone_gear"][0]
    assert by_name["proc.startup"].parent.span_id == task.context.span_id


def test_process_startup_ignores_a_missing_or_stale_stamp(capture, monkeypatch):
    """No stamp = a standalone run, nothing to bill. A stamp from another era is a
    stale value inherited through an intermediate process, not our parent's."""
    spans, _ = capture
    monkeypatch.delenv(_telemetry.SPAWN_ENV, raising=False)
    monkeypatch.setattr(_telemetry, "_startup_recorded", False)
    _telemetry.record_process_startup()

    monkeypatch.setattr(_telemetry, "_startup_recorded", False)
    monkeypatch.setenv(_telemetry.SPAWN_ENV, str(time.time_ns() - int(2e9 * 3600)))
    _telemetry.record_process_startup()

    assert not [s for s in spans.get_finished_spans() if s.name.startswith("proc.")]


def test_otlp_export_is_batched_off_the_critical_path():
    """OTLP export runs on a background thread, so a build subprocess never pays an
    export on the COM seat; console + file capture stay SIMPLE (live console, and a
    .jsonl that cannot lose a record to a queue). Flushing is what makes the batch
    trade safe -- ``shutdown()`` covers both signals and runs on both exit paths."""
    span_proc, log_proc = (
        _telemetry._otlp_span_processor(),
        _telemetry._otlp_log_processor(),
    )
    try:
        assert type(span_proc).__name__ == "BatchSpanProcessor"
        assert type(log_proc).__name__ == "BatchLogRecordProcessor"
    finally:
        for processor in (span_proc, log_proc):
            if processor is not None:
                processor.shutdown()

    simple = [
        p
        for p in _telemetry._span_processors
        if type(p).__name__ == "SimpleSpanProcessor"
    ]
    assert simple, "console/file capture must stay on Simple processors"


@pytest.mark.parametrize(
    ("protocol", "module_fragment"),
    [
        ("http/protobuf", ".proto.http."),
        ("grpc", ".proto.grpc."),
    ],
)
def test_otlp_export_honors_standard_transport_env(
    monkeypatch, protocol, module_fragment
):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", protocol)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", protocol)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_PROTOCOL", protocol)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://127.0.0.1:4317")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://127.0.0.1:4318")
    span_processor = _telemetry._otlp_span_processor()
    log_processor = _telemetry._otlp_log_processor()
    processors = (span_processor, log_processor)
    try:
        assert span_processor is not None
        assert log_processor is not None
        exporters = [
            _exporter_of(span_processor),
            _exporter_of(log_processor),
        ]
        assert all(
            module_fragment in type(exporter).__module__ for exporter in exporters
        )
    finally:
        for processor in processors:
            if processor is not None:
                processor.shutdown()


@pytest.mark.parametrize("signal", ("traces", "logs"))
def test_otlp_export_honors_signal_specific_timeout(monkeypatch, signal):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "30000")
    monkeypatch.setenv(f"OTEL_EXPORTER_OTLP_{signal.upper()}_TIMEOUT", "17000")
    monkeypatch.setenv(
        f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT", "http://127.0.0.1:4317"
    )
    if signal == "traces":
        processor = _telemetry._otlp_span_processor()
    else:
        processor = _telemetry._otlp_log_processor()
    exporter = _exporter_of(processor)
    try:
        assert exporter._timeout == 17.0
    finally:
        processor.shutdown()


def test_otlp_export_timeout_fallback_and_global_precedence(monkeypatch):
    assert _telemetry._otlp_export_timeout("traces") == 1.0

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TIMEOUT", "30000")
    assert _telemetry._otlp_export_timeout("traces") == 30.0

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", " ")
    assert _telemetry._otlp_export_timeout("traces") == 30.0


@pytest.mark.parametrize("invalid_timeout", ("-1", "0", "1.5", "invalid"))
def test_invalid_otlp_export_timeout_warns_and_falls_back(
    monkeypatch, capsys, invalid_timeout
):
    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)
    _telemetry.configure(force=True)
    capsys.readouterr()
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_TIMEOUT", invalid_timeout)

    assert _telemetry._otlp_export_timeout("traces") == 1.0
    assert (
        "Ignoring invalid OTEL_EXPORTER_OTLP_TRACES_TIMEOUT" in capsys.readouterr().err
    )


def test_empty_signal_protocol_falls_back_to_global_transport(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "")

    assert _telemetry._otlp_protocol("traces") == "grpc"


def test_unsupported_otlp_protocol_warns_in_production_console(monkeypatch, capsys):
    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")
    for name in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)

    _telemetry.configure(force=True)
    console = capsys.readouterr().err
    assert "!!" in console
    assert "unsupported protocol" in console
    assert "http/json" in console
    assert "OTLP trace export is disabled" in console
    assert "OTLP log export is disabled" in console


def test_missing_otlp_exporter_warns_in_production_console(monkeypatch, capsys):
    monkeypatch.delenv("HARMONIC_VERBOSITY", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "")
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)
    original_import = builtins.__import__

    def import_without_grpc_trace(name, *args, **kwargs):
        if name == "opentelemetry.exporter.otlp.proto.grpc.trace_exporter":
            raise ImportError("simulated missing gRPC exporter")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_grpc_trace)
    _telemetry.configure(force=True)
    console = capsys.readouterr().err
    assert "!!" in console
    assert "simulated missing gRPC exporter" in console


@pytest.mark.parametrize(
    ("protocol", "port", "path"),
    [("http/protobuf", 18890, "/v1/traces"), ("grpc", 18889, "")],
)
def test_default_otlp_endpoint_matches_transport_and_uses_literal_address(
    monkeypatch, protocol, port, path
):
    """The local collector exposes separate HTTP and gRPC ports. Probe the port
    for the selected transport without paying Windows' slow localhost fallback."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", protocol)
    assert not any(
        "localhost" in endpoint
        for endpoints in _telemetry._DEFAULT_OTLP_ENDPOINTS.values()
        for endpoint in endpoints
    )

    monkeypatch.setattr(_telemetry, "_endpoint_listening", lambda e, timeout=0.15: True)
    assert (
        _telemetry._resolve_otlp_endpoint("traces") == f"http://127.0.0.1:{port}{path}"
    )

    v6_only = lambda e, timeout=0.15: e.startswith("http://[::1]")  # noqa: E731
    monkeypatch.setattr(_telemetry, "_endpoint_listening", v6_only)
    assert _telemetry._resolve_otlp_endpoint("traces") == f"http://[::1]:{port}{path}"

    monkeypatch.setattr(
        _telemetry, "_endpoint_listening", lambda e, timeout=0.15: False
    )
    assert _telemetry._resolve_otlp_endpoint("traces") is None
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    global_endpoint = "http://collector:4318"
    if protocol == "http/protobuf":
        global_endpoint += "/v1/traces"
    assert _telemetry._resolve_otlp_endpoint("traces") == global_endpoint
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://traces:4317")
    assert _telemetry._resolve_otlp_endpoint("traces") == "http://traces:4317"


def test_schemeless_local_grpc_endpoint_is_normalized(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "127.0.0.1:4317")
    monkeypatch.setattr(
        _telemetry, "_endpoint_listening", lambda endpoint, timeout=0.15: True
    )

    assert _telemetry._resolve_otlp_endpoint("traces") == "http://127.0.0.1:4317"


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://localhost:4317",
        "http://127.0.0.2:4317",
        "http://0.0.0.0:4317",
        "http://[::ffff:127.0.0.1]:4317",
    ),
)
def test_explicit_local_grpc_endpoint_is_probed(monkeypatch, endpoint):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", endpoint)
    probed = []
    pending = []

    def unavailable(candidate, timeout=0.15):
        probed.append(candidate)
        return False

    monkeypatch.setattr(_telemetry, "_endpoint_listening", unavailable)

    assert _telemetry._resolve_otlp_endpoint("traces", pending_warnings=pending) is None
    assert probed == [endpoint]
    assert "OTLP trace export is disabled for protocol 'grpc'" in pending[0]
    assert "configured local endpoint is unavailable" in pending[0]


@pytest.mark.parametrize(
    "endpoint", ("http://localhost:notaport", "http://127.0.0.1:99999")
)
def test_invalid_local_grpc_port_disables_signal(monkeypatch, endpoint):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", endpoint)
    pending = []

    assert _telemetry._resolve_otlp_endpoint("traces", pending_warnings=pending) is None
    assert "OTLP trace export is disabled for protocol 'grpc'" in pending[0]
    assert "configured local endpoint is unavailable" in pending[0]


def test_schemeless_remote_grpc_endpoint_keeps_stock_secure_target(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "collector:4317")
    pending = []

    assert (
        _telemetry._resolve_otlp_endpoint("traces", pending_warnings=pending)
        == "collector:4317"
    )
    assert pending == []


def test_configure_pins_endpoint_protocol_pair(monkeypatch):
    for name in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
        "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setattr(
        _telemetry, "_endpoint_listening", lambda endpoint, timeout=0.15: True
    )
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)
    monkeypatch.setattr(_telemetry, "_otlp_span_processor", lambda **kwargs: None)
    monkeypatch.setattr(_telemetry, "_otlp_log_processor", lambda **kwargs: None)

    _telemetry.configure(console=False, force=True)
    assert os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] == (
        "http://127.0.0.1:18889"
    )
    assert os.environ["OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"] == ("http://127.0.0.1:18889")
    assert os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] == "grpc"
    assert os.environ["OTEL_EXPORTER_OTLP_LOGS_PROTOCOL"] == "grpc"

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    assert _telemetry._otlp_protocol("traces") == "grpc"
    assert _telemetry._resolve_otlp_endpoint("traces") == "http://127.0.0.1:18889"


def test_configure_rewrites_signal_endpoint_to_normalized_value(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "127.0.0.1:4317")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "")
    monkeypatch.setattr(
        _telemetry, "_endpoint_listening", lambda endpoint, timeout=0.15: True
    )
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)
    monkeypatch.setattr(_telemetry, "_otlp_span_processor", lambda **kwargs: None)

    _telemetry.configure(console=False, force=True)

    assert os.environ["OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] == ("http://127.0.0.1:4317")
    assert os.environ["OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"] == "grpc"


def test_configure_probes_each_default_protocol_once(monkeypatch):
    for name in (
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_PROTOCOL",
        "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    monkeypatch.setattr(_telemetry, "_telemetry_dir", lambda: None)
    probed = []

    def unavailable(endpoint, timeout=0.15):
        probed.append(endpoint)
        return False

    monkeypatch.setattr(_telemetry, "_endpoint_listening", unavailable)
    _telemetry.configure(console=False, force=True)
    assert probed == list(_telemetry._DEFAULT_OTLP_ENDPOINTS["http/protobuf"])


def test_signal_protocol_selects_its_own_local_collector_port(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL", "grpc")
    monkeypatch.setattr(_telemetry, "_endpoint_listening", lambda e, timeout=0.15: True)

    assert _telemetry._resolve_otlp_endpoint("traces") == "http://127.0.0.1:18889"
    assert _telemetry._resolve_otlp_endpoint("logs") == "http://127.0.0.1:18890/v1/logs"


def test_empty_signal_endpoint_disables_only_that_signal(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", raising=False)

    assert _telemetry._resolve_otlp_endpoint("traces") is None
    assert _telemetry._resolve_otlp_endpoint("logs") == "http://collector:4318/v1/logs"


def test_event_records_span_event_on_current_span(capture):
    """``event()`` attaches a point-in-time event (with attrs) to the active span --
    the idiomatic home for a cache hit/miss or a mate flip, vs a standalone log."""
    spans, _ = capture
    with _telemetry.span("op"):
        _telemetry.event("cache.miss", label="part:cone_gear", key="deadbeef")
    (sp,) = [s for s in spans.get_finished_spans() if s.name == "op"]
    hit = [e for e in sp.events if e.name == "cache.miss"]
    assert hit and hit[0].attributes["label"] == "part:cone_gear"
    assert hit[0].attributes["key"] == "deadbeef"


def test_event_without_active_span_is_noop():
    """A bare ``event()`` with no span in scope must be a silent no-op, so callers
    never have to guard (telemetry must never break the caller)."""
    _telemetry.event("orphan", foo="bar")  # must not raise


def test_annotate_sets_attributes_on_current_span(capture):
    """``annotate()`` is the per-item alternative to child spans: sub-step
    timings land as attributes of the span already open, not as new spans."""
    spans, _ = capture
    with _telemetry.span("dim.display_precision"):
        _telemetry.annotate(lookup_ms=12.5, set_ms=3.0, note=("a", 1))
    (sp,) = [s for s in spans.get_finished_spans() if s.name == "dim.display_precision"]
    assert sp.attributes["lookup_ms"] == 12.5
    assert sp.attributes["set_ms"] == 3.0
    assert sp.attributes["note"] == repr(("a", 1))
    assert len(spans.get_finished_spans()) == 1


def test_annotate_without_active_span_is_noop():
    """Like ``event()``, a bare ``annotate()`` must never raise."""
    _telemetry.annotate(orphan=True)


def test_sequential_root_spans_do_not_nest(capture):
    """Two spans opened one after the other are SIBLINGS, each timing only its own
    stretch -- the shape dodo relies on to split a COM task's queueing
    (``com.seat.wait <label>``) from its work (``task <label>``): neither duration
    contains the other, and no timestamp surgery is involved."""
    spans, _ = capture
    with _telemetry.span("com.seat.wait part:cone_gear", label="part:cone_gear"):
        time.sleep(0.2)
    with _telemetry.span("task part:cone_gear", label="part:cone_gear"):
        pass

    finished = {s.name: s for s in spans.get_finished_spans()}
    wait, task = (
        finished["com.seat.wait part:cone_gear"],
        finished["task part:cone_gear"],
    )
    assert task.parent is None and wait.parent is None, (
        "the wait must not parent the task"
    )
    assert (wait.end_time - wait.start_time) / 1e9 >= 0.2
    # The ordering is the real invariant, and it is deterministic. An upper bound on
    # the task span's own duration would only measure how busy the host is -- a
    # descheduled process would fail it while the topology was perfectly correct
    # (codex #424).
    assert task.start_time >= wait.end_time, "the task must start once the seat is held"
    assert wait.end_time <= task.start_time, (
        "no overlap: the wait cannot leak into work"
    )


def test_every_traced_adapter_method_is_a_coroutine_on_the_real_adapter():
    """A renamed or removed adapter method would silently fall out of the trace
    (``instrument_adapter`` skips names it cannot find), re-opening the dark time
    the list exists to close."""
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter

    missing = sorted(
        name
        for name in _telemetry.ADAPTER_TRACED_METHODS
        if not inspect.iscoroutinefunction(getattr(PyWin32Adapter, name, None))
    )
    assert missing == []


def _fake_adapter_class():
    from solidworks_mcp.adapters.base import AdapterResult, AdapterResultStatus

    class FakeAdapter:
        async def create_plane(self, name, offset_mm=0.0):
            return AdapterResult(
                status=AdapterResultStatus.SUCCESS, data=(name, offset_mm)
            )

        async def create_axis(self, *args, **kwargs):
            return AdapterResult(status=AdapterResultStatus.ERROR, error="no such edge")

        async def open_model(self, path):
            raise OSError(f"cannot open {path}")

        async def add_line(self, *args):
            return AdapterResult(status=AdapterResultStatus.SUCCESS)

    return FakeAdapter


def test_instrumented_adapter_calls_are_spans_and_stay_transparent(capture):
    spans, _ = capture
    cls = _fake_adapter_class()
    assert _telemetry.instrument_adapter(cls) == 3
    assert _telemetry.instrument_adapter(cls) == 0, "a second pass must not double-wrap"
    adapter = cls()

    async def drive():
        with _telemetry.span("part.build"):
            ok = await adapter.create_plane("Tooth Plane", offset_mm=2.5)
            probe = await adapter.create_axis("candidate")
            await adapter.add_line(0, 0, 1, 1)
            with pytest.raises(OSError, match="cannot open"):
                await adapter.open_model(Path("C:/models/cone_gear.SLDPRT"))
        return ok, probe

    ok, probe = asyncio.run(drive())
    assert ok.data == ("Tooth Plane", 2.5)
    assert probe.error == "no such edge"

    finished = {s.name: s for s in spans.get_finished_spans()}
    build = finished["part.build"]
    plane = finished["adapter.create_plane"]
    axis = finished["adapter.create_axis"]
    opened = finished["adapter.open_model"]
    assert "adapter.add_line" not in finished, "per-entity sketch calls stay unspanned"
    assert {plane.parent.span_id, axis.parent.span_id, opened.parent.span_id} == {
        build.context.span_id
    }
    assert plane.attributes["arg"] == "Tooth Plane"
    assert plane.status.status_code.name == "OK"
    # a returned failure is a probe outcome, recorded but not an ERROR span
    assert axis.status.status_code.name == "OK"
    assert axis.attributes["adapter.status"] == "error"
    assert axis.attributes["error.message"] == "no such edge"
    # a raised one propagates unchanged and fails the span; a path arg is its name
    assert opened.status.status_code.name == "ERROR"
    assert opened.attributes["arg"] == "cone_gear.SLDPRT"
    assert opened.attributes["error.type"] == "OSError"
    assert "label" not in plane.attributes, "label at depth 0 is the farm's leaf key"


@pytest.mark.parametrize("outcome", ["success", "returned_error", "raised_error"])
def test_assembly_instrumentation_preserves_parameters_and_outcomes(
    capture, monkeypatch, outcome
):
    from solidworks_mcp.adapters.base import (
        AdapterResult,
        AdapterResultStatus,
        InsertComponentParameters,
    )

    spans, _ = capture
    params = InsertComponentParameters(
        file_path="C:/models/drive-train.SLDASM",
        position=[1.0, 2.0, 3.0],
        rotation=[0.0, 0.0, 90.0],
        configuration="drawing",
    )
    created = AdapterResult(status=AdapterResultStatus.SUCCESS, data=object())
    inserted = AdapterResult(
        status=(
            AdapterResultStatus.ERROR
            if outcome == "returned_error"
            else AdapterResultStatus.SUCCESS
        ),
        data={"name": "drive-train-1", "configuration": "installed", "fixed": False},
        error="component unavailable" if outcome == "returned_error" else None,
    )
    failure = OSError("native component insertion failed")
    calls = []
    loaded = object()
    component = object()

    def preload(adapter, path):
        calls.append(("preload", adapter, path))
        return loaded

    def transform(adapter, comp, name, array):
        calls.append(("transform", adapter, comp, name, array))
        if outcome != "success":
            raise failure
        return array

    def activate(adapter):
        # Like the SDK's best-effort helper, a normal return proves only that
        # the attempt ended, not that activation succeeded.
        calls.append(("activate", adapter))

    assembly = types.SimpleNamespace(
        _preload_component_file=preload,
        _apply_component_transform=transform,
        _activate_assembly=activate,
    )
    monkeypatch.setitem(sys.modules, _telemetry._INSERT_COMPONENT_MODULE, assembly)

    class AssemblyAdapter:
        async def create_assembly(self, name=None):
            calls.append(("create", name))
            return created

        async def insert_component(self, params):
            calls.append(("insert", params))
            assert assembly._preload_component_file(self, params.file_path) is loaded
            try:
                assert (
                    assembly._apply_component_transform(
                        self, component, "drive-train-1", params.position
                    )
                    is params.position
                )
            except OSError:
                if outcome == "returned_error":
                    return inserted
                raise
            assembly._activate_assembly(self)
            return inserted

    signature = inspect.signature(AssemblyAdapter.insert_component)
    assert _telemetry.instrument_adapter(AssemblyAdapter) == 2
    assert inspect.signature(AssemblyAdapter.insert_component) == signature
    monkeypatch.setitem(
        sys.modules,
        _telemetry._ADAPTER_MODULE,
        types.SimpleNamespace(PyWin32Adapter=AssemblyAdapter),
    )
    _telemetry._instrument_loaded_adapter()
    wrapped_helpers = vars(assembly).copy()
    _telemetry._instrument_loaded_adapter()
    assert vars(assembly) == wrapped_helpers, "loaded helpers must not double-wrap"
    adapter = AssemblyAdapter()

    async def drive():
        with _telemetry.span("assembly.build"):
            assert await adapter.create_assembly(name="Harmonic") is created
            if outcome == "raised_error":
                with pytest.raises(OSError) as raised:
                    await adapter.insert_component(params=params)
                assert raised.value is failure
            else:
                assert await adapter.insert_component(params=params) is inserted

    asyncio.run(drive())
    assert calls[0] == ("create", "Harmonic")
    assert calls[1][0] == "insert" and calls[1][1] is params
    assert calls[2] == ("preload", adapter, params.file_path)
    assert calls[3] == (
        "transform",
        adapter,
        component,
        "drive-train-1",
        params.position,
    )
    assert len(calls) == (5 if outcome == "success" else 4)
    # The same helpers outside insertion keep their behavior but add no spans.
    assert assembly._preload_component_file(adapter, "outside") is loaded
    assembly._activate_assembly(adapter)
    finished = {span.name: span for span in spans.get_finished_spans()}
    expected = {
        "assembly.build",
        "adapter.create_assembly",
        "adapter.insert_component",
        "adapter.insert_component.preload",
        "adapter.insert_component.transform",
    }
    if outcome == "success":
        expected.add("adapter.insert_component.activate_attempt")
    assert set(finished) == expected
    insertion = finished["adapter.insert_component"]
    assert insertion.parent.span_id == finished["assembly.build"].context.span_id
    assert insertion.attributes["source_file"] == "drive-train.SLDASM"
    assert insertion.attributes["requested_configuration"] == "drawing"
    for name in expected - {
        "assembly.build",
        "adapter.create_assembly",
        "adapter.insert_component",
    }:
        assert finished[name].parent.span_id == insertion.context.span_id
    transform_span = finished["adapter.insert_component.transform"]
    assert transform_span.status.status_code.name == (
        "OK" if outcome == "success" else "ERROR"
    )
    if outcome == "raised_error":
        assert insertion.status.status_code.name == "ERROR"
        assert insertion.attributes["error.type"] == "OSError"
        assert insertion.attributes["error.message"] == str(failure)
    else:
        assert insertion.status.status_code.name == "OK"
        assert insertion.attributes["actual_configuration"] == "installed"
        assert insertion.attributes["fixed_state"] == "floating"
        if outcome == "returned_error":
            assert insertion.attributes["adapter.status"] == "error"
            assert insertion.attributes["error.message"] == inserted.error


@pytest.mark.parametrize("failure_type", [OSError, asyncio.CancelledError])
def test_insert_component_helper_context_is_nested_and_task_local(
    capture, monkeypatch, failure_type
):
    spans, _ = capture
    calls = []
    failure = failure_type("inner transform failed")

    class BrokenMetadata(dict):
        def get(self, key, default=None):
            raise RuntimeError("result metadata unavailable")

    result = types.SimpleNamespace(
        status="success", is_success=True, data=BrokenMetadata()
    )

    def preload(adapter, path):
        calls.append((adapter.label, "preload", path))
        return path

    def transform(adapter, component, name, array):
        calls.append((adapter.label, "transform"))
        raise failure

    def activate(adapter):
        calls.append((adapter.label, "activate"))

    assembly = types.SimpleNamespace(
        _preload_component_file=preload,
        _apply_component_transform=transform,
        _activate_assembly=activate,
    )

    class Adapter:
        def __init__(self, label):
            self.label = label

        async def insert_component(self, params):
            if self.label == "inner":
                assembly._apply_component_transform(self, object(), "inner-1", [])
            self.started.set()
            await self.release.wait()
            assert (
                assembly._preload_component_file(self, "outer source") == "outer source"
            )
            # A different adapter's unrelated work must not inherit this scope.
            assembly._preload_component_file(self.peer, "foreign adapter")
            with pytest.raises(failure_type) as raised:
                await self.peer.insert_component(
                    types.SimpleNamespace(file_path="inner.SLDASM", configuration="")
                )
            assert raised.value is failure
            # The inner failure must restore the outer insertion's context.
            assembly._activate_assembly(self)
            return result

    monkeypatch.setitem(sys.modules, _telemetry._INSERT_COMPONENT_MODULE, assembly)
    monkeypatch.setitem(
        sys.modules,
        _telemetry._ADAPTER_MODULE,
        types.SimpleNamespace(PyWin32Adapter=Adapter),
    )
    _telemetry._instrument_loaded_adapter()

    async def drive():
        outer = Adapter("outer")
        outer.peer = Adapter("inner")
        outer.started = asyncio.Event()
        outer.release = asyncio.Event()
        with _telemetry.span("assembly.build"):
            pending = asyncio.create_task(
                outer.insert_component(
                    types.SimpleNamespace(file_path="outer.SLDASM", configuration="")
                )
            )
            await outer.started.wait()
            # This task predates the insertion context, even while it is active.
            assert assembly._preload_component_file(outer, "concurrent") == "concurrent"
            outer.release.set()
            assert await pending is result
            assembly._activate_assembly(outer)
            assembly._activate_assembly(outer.peer)

    asyncio.run(drive())
    finished = spans.get_finished_spans()
    insertions = {
        item.attributes["source_file"]: item
        for item in finished
        if item.name == "adapter.insert_component"
    }
    outer_span = insertions["outer.SLDASM"]
    inner_span = insertions["inner.SLDASM"]
    assert inner_span.parent.span_id == outer_span.context.span_id
    assert outer_span.status.status_code.name == "OK"
    assert inner_span.status.status_code.name == "ERROR"
    children = {
        item.name: item
        for item in finished
        if item.name.startswith("adapter.insert_component.")
    }
    assert set(children) == {
        "adapter.insert_component.preload",
        "adapter.insert_component.transform",
        "adapter.insert_component.activate_attempt",
    }
    assert len(finished) == 6, (
        "unrelated and post-insertion helpers must stay unspanned"
    )
    assert children["adapter.insert_component.preload"].parent.span_id == (
        outer_span.context.span_id
    )
    assert children["adapter.insert_component.transform"].parent.span_id == (
        inner_span.context.span_id
    )
    assert (
        children["adapter.insert_component.transform"].status.status_code.name
        == "ERROR"
    )
    assert children["adapter.insert_component.activate_attempt"].parent.span_id == (
        outer_span.context.span_id
    )
    assert calls == [
        ("outer", "preload", "concurrent"),
        ("outer", "preload", "outer source"),
        ("inner", "preload", "foreign adapter"),
        ("inner", "transform"),
        ("outer", "activate"),
        ("outer", "activate"),
        ("inner", "activate"),
    ]


def test_insert_component_descendant_scope_is_foreign_and_revoked(capture, monkeypatch):
    spans, _ = capture
    calls = []
    result = types.SimpleNamespace(
        status="success", is_success=True, data={"fixed": "unsupported"}
    )

    def preload(adapter, path):
        calls.append(path)

    def activate(adapter):
        calls.append("descendant after return")

    assembly = types.SimpleNamespace(
        _preload_component_file=preload, _activate_assembly=activate
    )
    monkeypatch.setitem(sys.modules, _telemetry._INSERT_COMPONENT_MODULE, assembly)

    class Adapter:
        async def insert_component(self, params):
            async def descendant():
                # This task inherits the active scope but is not its owner.
                assembly._preload_component_file(self, "descendant during insertion")
                self.entered.set()
                await self.after_return.wait()
                assembly._activate_assembly(self)

            self.child = asyncio.create_task(descendant())
            await self.entered.wait()
            await asyncio.to_thread(
                assembly._preload_component_file, self, "foreign thread"
            )
            assembly._preload_component_file(self, "owner during insertion")
            return result

    monkeypatch.setitem(
        sys.modules,
        _telemetry._ADAPTER_MODULE,
        types.SimpleNamespace(PyWin32Adapter=Adapter),
    )
    _telemetry._instrument_loaded_adapter()

    async def drive():
        adapter = Adapter()
        adapter.entered = asyncio.Event()
        adapter.after_return = asyncio.Event()
        assert (
            await adapter.insert_component(
                types.SimpleNamespace(file_path="component.SLDASM", configuration="")
            )
            is result
        )
        adapter.after_return.set()
        await adapter.child

    asyncio.run(drive())
    finished = spans.get_finished_spans()
    assert {item.name for item in finished} == {
        "adapter.insert_component",
        "adapter.insert_component.preload",
    }
    assert len(finished) == 2
    preload_span, insertion = finished
    assert preload_span.parent.span_id == insertion.context.span_id
    assert insertion.start_time <= preload_span.start_time
    assert preload_span.end_time <= insertion.end_time
    assert "fixed_state" not in insertion.attributes
    assert calls == [
        "descendant during insertion",
        "foreign thread",
        "owner during insertion",
        "descendant after return",
    ]


@pytest.mark.parametrize("outcome", ["success", "preload_error", "transform_error"])
def test_real_sdk_insertion_helper_spans_preserve_native_boundary_results(
    capture, monkeypatch, tmp_path, outcome
):
    from solidworks_mcp.adapters.base import (
        InsertComponentParameters,
        SolidWorksAdapter,
    )
    from solidworks_mcp.adapters.pywin32_adapter import PyWin32Adapter
    from solidworks_mcp.adapters.solidworks import assembly

    spans, _ = capture
    events = []
    source = tmp_path / ("source-" + "x" * 120 + ".SLDASM")
    source.write_bytes(b"offline COM-boundary fixture")
    requested = "requested-" + "r" * 150
    actual = "resolved-" + "a" * 150
    params = InsertComponentParameters(
        file_path=str(source),
        position=[12.5, -30.0, 4.0],
        rotation=[0.0, 0.0, 90.0],
        configuration=requested,
    )

    class Component:
        Name2 = "source-1"
        ReferencedConfiguration = actual
        IsFixed = True

        def SetTransformAndSolve3(self, transform, update_box):
            events.append(("solve3", update_box))
            if outcome == "transform_error":
                return False
            values = list(transform.ArrayData)
            # A native solver's observed outcome need not equal the target.
            values[9] += 0.001
            self.Transform2 = types.SimpleNamespace(ArrayData=values)
            return True

        def SetTransformAndSolve2(self, transform):
            events.append(("solve2",))
            return False

    component = Component()

    class Model:
        @property
        def Extension(self):
            return self

        def SelectByID2(self, *args):
            events.append(("select", args[0]))
            return True

        def AddComponent5(self, *args):
            events.append(("insert", args))
            return component

        def UnfixComponent(self):
            events.append(("float",))
            component.IsFixed = False

        def FixComponent(self):
            events.append(("fix",))
            component.IsFixed = True

        def EditRebuild3(self):
            events.append(("rebuild",))
            return True

        def GetTitle(self):
            return "assembly.SLDASM"

    model = Model()

    class App:
        def DocumentVisible(self, visible, doc_type):
            events.append(("visible", visible, doc_type))

        def OpenDoc6(self, *args):
            events.append(("open", args))
            return (None if outcome == "preload_error" else model, 0, 0)

        def GetOpenDocumentByName(self, path):
            events.append(("lookup", path))
            return None

        def GetMathUtility(self):
            return self

        def CreateTransform(self, values):
            return types.SimpleNamespace(ArrayData=list(values))

        def ActivateDoc3(self, *args):
            events.append(("activate", args))
            raise OSError("best-effort activation failed")

    class OfflineAdapter(PyWin32Adapter):
        # Use the real mixin entry and COM-operation/error/metrics machinery,
        # without constructing a live COM session.
        insert_component = assembly.SolidWorksAssemblyMixin.insert_component

        def __init__(self):
            SolidWorksAdapter.__init__(self)
            self.currentModel = model
            self.swApp = App()

    # Only binding/marshalling and COM objects are doubled; the insertion,
    # preload, transform, activation and readback implementations stay real.
    monkeypatch.setattr(assembly, "_flag_feature_methods", lambda obj, *args: obj)
    monkeypatch.setattr(assembly, "double_array", tuple)
    monkeypatch.setattr(assembly, "null_callout", lambda: None)
    for name in (
        "_preload_component_file",
        "_apply_component_transform",
        "_activate_assembly",
    ):
        # Restore the module's original functions when the test ends.
        monkeypatch.setattr(assembly, name, getattr(assembly, name))
    monkeypatch.setitem(
        sys.modules,
        _telemetry._ADAPTER_MODULE,
        types.SimpleNamespace(PyWin32Adapter=OfflineAdapter),
    )
    _telemetry._instrument_loaded_adapter()
    adapter = OfflineAdapter()
    result = asyncio.run(adapter.insert_component(params=params))
    finished = spans.get_finished_spans()
    insertion = next(
        item for item in finished if item.name == "adapter.insert_component"
    )
    children = [
        item for item in finished if item.name.startswith("adapter.insert_component.")
    ]
    phases = ["preload"]
    if outcome != "preload_error":
        phases.append("transform")
    if outcome == "success":
        phases.append("activate_attempt")
    assert [item.name for item in children] == [
        f"adapter.insert_component.{phase}" for phase in phases
    ]
    for child in children:
        assert child.parent.span_id == insertion.context.span_id
        assert insertion.start_time <= child.start_time <= child.end_time
        assert child.end_time <= insertion.end_time
    assert all(
        first.end_time <= second.start_time
        for first, second in zip(children, children[1:])
    )
    assert insertion.attributes["source_file"] == source.name[:120]
    assert insertion.attributes["requested_configuration"] == requested[:120]
    assert ("visible", False, 2) in events and ("visible", True, 2) in events
    assert adapter.get_metrics()["operations_count"] == 1
    assert insertion.status.status_code.name == "OK"
    if outcome == "success":
        assert result.is_success
        assert result.data["name"] == component.Name2
        assert result.data["file_path"] == str(source.resolve())
        assert result.data["configuration"] == actual
        assert result.data["position"] == pytest.approx([13.5, -30.0, 4.0])
        assert result.data["rotation"] == params.rotation
        assert result.data["fixed"] is True
        assert component.Transform2.ArrayData[:9] == pytest.approx(
            [0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        )
        assert insertion.attributes["actual_configuration"] == actual[:120]
        assert insertion.attributes["fixed_state"] == "fixed"
        assert all(child.status.status_code.name == "OK" for child in children)
        assert ("float",) in events and ("fix",) in events and ("rebuild",) in events
        assert any(event[0] == "activate" for event in events)
    else:
        assert not result.is_success
        assert insertion.attributes["adapter.status"] == "error"
        assert insertion.attributes["error.message"] == result.error
        assert children[-1].status.status_code.name == "ERROR"
        assert "actual_configuration" not in insertion.attributes
        assert "fixed_state" not in insertion.attributes
        assert adapter.get_metrics()["errors_count"] == 1
        if outcome == "preload_error":
            assert not any(event[0] == "insert" for event in events)
        else:
            assert ("solve2",) in events and component.IsFixed is True
            assert not any(event[0] == "rebuild" for event in events)
        assert not any(event[0] == "activate" for event in events)


@pytest.mark.parametrize(
    "outcome",
    [
        "success",
        "topology_exception",
        "topology_issues",
        "band_exception",
        "not_rebuilt",
    ],
)
def test_saved_cone_topology_spans_preserve_audit_and_restore(
    capture, monkeypatch, outcome
):
    import _cone_gear_readback as readback

    spans, _ = capture
    monkeypatch.setattr(readback, "CONFIGS", (("T006", 6), ("T012", 12)))
    calls = []
    adapter = types.SimpleNamespace(active="initial")

    async def activate(configuration):
        adapter.active = configuration
        calls.append(("activate", configuration))
        return types.SimpleNamespace(
            is_success=True,
            data={
                "rebuilt": not (outcome == "not_rebuilt" and configuration == "T012")
            },
            error=None,
        )

    async def topology(current_adapter, configuration, teeth, *, phase, measure_roots):
        assert current_adapter is adapter and adapter.active == configuration
        assert phase == "reopened post-activation-rebuild" and measure_roots
        calls.append(("topology", configuration))
        if configuration == "T012" and outcome == "topology_exception":
            raise OSError("native topology unreadable")
        issues = (
            ("pattern is suppressed",)
            if configuration == "T012" and outcome == "topology_issues"
            else ()
        )
        return float(teeth), f"{configuration} observation", issues

    def bands(current_adapter, configuration, teeth):
        assert current_adapter is adapter and adapter.active == configuration
        assert teeth == int(configuration[1:])
        calls.append(("bands", configuration))
        if configuration == "T012" and outcome == "band_exception":
            raise ValueError("native tolerance drift")

    adapter.set_active_configuration = activate
    monkeypatch.setattr(readback, "_configuration_topology", topology)
    monkeypatch.setattr(readback, "_assert_configuration_bands", bands)
    with _telemetry.span("part.build"):
        if outcome == "success":
            assert asyncio.run(
                readback.assert_saved_configuration_topology(adapter, phase="reopened")
            ) == {"T006": 6.0, "T012": 12.0}
        else:
            with pytest.raises(RuntimeError) as raised:
                asyncio.run(
                    readback.assert_saved_configuration_topology(
                        adapter, phase="reopened"
                    )
                )
            cause = {
                "topology_exception": "native topology unreadable",
                "topology_issues": "pattern is suppressed",
                "band_exception": "native tolerance drift",
                "not_rebuilt": "set_active_configuration returned rebuilt=False",
            }[outcome]
            assert cause in str(raised.value)

    expected = [("activate", "T012")]
    if outcome != "not_rebuilt":
        expected.append(("topology", "T012"))
        if outcome != "topology_exception":
            expected.append(("bands", "T012"))
    expected.extend(
        [
            ("activate", "T006"),
            ("topology", "T006"),
            ("bands", "T006"),
            ("activate", "T012"),
        ]
    )
    assert calls == expected
    assert adapter.active == "T012", "failure must not skip the established restore"
    finished = spans.get_finished_spans()
    (saved,) = [span for span in finished if span.name == "cone.saved_topology"]
    children = [span for span in finished if span.name == "cone.configuration_topology"]
    assert len(children) == (1 if outcome == "not_rebuilt" else 2)
    assert len(finished) == len(children) + 2, "no per-feature or per-band span flood"
    assert saved.attributes["phase"] == "reopened"
    assert saved.attributes["configuration_count"] == 2
    assert saved.attributes["configurations_attempted"] == 2
    assert saved.attributes["configurations_completed"] == (
        2 if outcome in {"success", "topology_issues"} else 1
    )
    expected_failures = {
        "success": 0,
        "topology_exception": 1,
        "topology_issues": 1,
        "band_exception": 1,
        "not_rebuilt": 2,  # Both activation and the final restore refuse rebuilding.
    }
    assert saved.attributes["failure_count"] == expected_failures[outcome]
    assert saved.status.status_code.name == ("OK" if outcome == "success" else "ERROR")
    if outcome != "success":
        assert saved.attributes["error.type"] == "RuntimeError"
        assert cause in saved.attributes["error.message"]
    if outcome == "not_rebuilt":
        assert (
            "restore T012: set_active_configuration returned rebuilt=False"
            in saved.attributes["error.message"]
        )
    for child in children:
        assert child.parent.span_id == saved.context.span_id
        assert child.attributes["phase"] == "reopened"
        assert child.attributes["measure_roots"] is True
        if child.attributes["configuration"] == "T006" or outcome == "success":
            assert child.status.status_code.name == "OK"
            assert child.attributes["band_check_count"] == 3
        else:
            assert child.status.status_code.name == "ERROR"
            assert cause in child.attributes["error.message"]


@pytest.mark.parametrize("sketch_fails", [False, True])
def test_cone_topology_timings_preserve_results_and_partial_failure(
    capture, monkeypatch, sketch_fails
):
    import _cone_gear_readback as readback

    spans, _ = capture
    configurations = (("T006", 6), ("T012", 12))
    monkeypatch.setattr(readback, "CONFIGS", configurations)
    monkeypatch.setattr(readback, "CONFIGURATION_TEETH", (6, 12))
    ticks = iter(range(20))
    monkeypatch.setattr(
        readback, "time", types.SimpleNamespace(perf_counter=lambda: next(ticks))
    )
    monkeypatch.setattr(readback, "_early_bound", lambda value, _interface: value)
    profile = types.SimpleNamespace(
        native_segments=lambda **kwargs: ("first", "second"),
        gap_area_error_bound_mm2=0.0,
    )
    monkeypatch.setattr(readback, "stock_form_profile", lambda _teeth: profile)
    monkeypatch.setattr(readback, "_expected_configuration_volume", lambda _teeth: 12.0)
    monkeypatch.setattr(readback, "BORE_DIA_BAND", (0.0, 0.0))
    monkeypatch.setattr(readback, "WEB_EXCEPTIONS_MM", {})
    monkeypatch.setattr(readback, "MACHINED_WEB_TARGET_MM", 0.5)
    monkeypatch.setattr(readback, "floor_radius_min_mm", lambda _teeth: 5.0)
    monkeypatch.setattr(readback, "floor_radius_max_mm", lambda _teeth: 5.5)
    monkeypatch.setattr(readback, "bore_dia_mm", lambda _teeth: 4.0)
    monkeypatch.setattr(
        readback, "_native_root_envelope_mm", lambda _body, *, teeth: (5.0, 5.5, teeth)
    )
    definition_reads = []
    monkeypatch.setattr(
        readback,
        "_configuration_definition_state",
        lambda _adapter, configuration, *, phase: definition_reads.append(
            (configuration, phase)
        ),
    )
    failure = OSError("sketch segments unavailable")

    def segments():
        if sketch_fails:
            raise failure
        return ("first", "second")

    sketch = types.SimpleNamespace(GetSketchSegments=segments)

    class Feature:
        def __init__(self, teeth):
            self.teeth = teeth

        def IsSuppressed2(self, _which, _names):
            return (self.teeth != 12,)

        def GetErrorCode2(self):
            return 0, False

        def GetDefinition(self):
            return types.SimpleNamespace(TotalInstances=12)

        def GetSpecificFeature2(self):
            return sketch

    features = {
        name: Feature(teeth)
        for _configuration, teeth in configurations
        for name in readback.tooth_features(teeth)
    }
    active = types.SimpleNamespace(
        Name="T012", NeedsRebuild=False, AddRebuildSaveMark=True
    )
    selection = object()
    model = types.SimpleNamespace(
        ConfigurationManager=types.SimpleNamespace(ActiveConfiguration=active),
        FeatureByName=features.get,
        GetBodies2=lambda _kind, _hidden: (
            types.SimpleNamespace(GetFaceCount=lambda: 28),
        ),
        selection=selection,
    )
    mass_reads = []

    async def mass():
        mass_reads.append("mass")
        return types.SimpleNamespace(
            is_success=True, data=types.SimpleNamespace(volume=12.0), error=None
        )

    adapter = types.SimpleNamespace(currentModel=model, get_mass_properties=mass)

    async def audit():
        with _telemetry.span("cone.configuration_topology"):
            return await readback._configuration_topology(
                adapter, "T012", 12, phase="saved", measure_roots=True
            )

    if sketch_fails:
        with pytest.raises(OSError) as raised:
            asyncio.run(audit())
        assert raised.value is failure
    else:
        volume, observation, issues = asyncio.run(audit())
        assert volume == 12.0 and issues == ()
        assert "T012: active=T012" in observation
    assert adapter.currentModel is model and model.selection is selection
    assert active.Name == "T012"
    (span,) = spans.get_finished_spans()
    assert span.attributes["feature_audit_count"] == 6
    assert span.attributes["feature_audit_s"] == 1.0
    assert span.attributes["sketch_read_s"] == 1.0
    if sketch_fails:
        assert span.status.status_code.name == "ERROR"
        assert span.attributes["error.type"] == "OSError"
        assert span.attributes["error.message"] == str(failure)
        assert mass_reads == [] and definition_reads == []
        assert span.attributes["definition_state_count"] == 0
        assert "root_envelope_s" not in span.attributes
        assert "definition_state_s" not in span.attributes
    else:
        assert span.status.status_code.name == "OK"
        assert mass_reads == ["mass"] and definition_reads == [("T012", "saved")]
        assert span.attributes["sketch_entity_count"] == 2
        assert span.attributes["root_edge_count"] == 12
        assert span.attributes["root_envelope_s"] == 1.0
        assert span.attributes["definition_state_count"] == 1
        assert span.attributes["definition_state_s"] == 1.0


@pytest.mark.parametrize(
    "outcome",
    [
        "scaled", "unscaled", "false_create", "bind_error",
        "scale_error", "invalid_scale", "two_views", "false_factory",
    ],
)
def test_place_view_observation_preserves_native_behavior(capture, monkeypatch, outcome):
    from solidworks_mcp.adapters.solidworks import drawing
    from solidworks_mcp.adapters.solidworks.drawing import place_view as imported_alias

    spans, _ = capture
    calls = []
    raw_view = object()
    failure = OSError("native port failed")

    class View:
        @property
        def ScaleRatio(self):
            raise AssertionError("placement must not read the scale back")

        @ScaleRatio.setter
        def ScaleRatio(self, value):
            calls.append(("scale", value))
            if outcome == "scale_error":
                raise failure

    bound_view = View()

    class Document:
        def CreateDrawViewFromModelView3(self, *args):
            calls.append(("create", args))
            return None if outcome == "false_create" else raw_view

    document = Document()

    def ddoc(adapter):
        calls.append(("ddoc",))
        return document

    def bind(view, interface):
        calls.append(("bind", view, interface))
        if outcome == "bind_error":
            raise failure
        return bound_view

    def doubles(values):
        calls.append(("double_array", values))
        return tuple(values)

    class Adapter:
        def _attempt(self, operation, default=None):
            try:
                return operation()
            except Exception:
                return default

    monkeypatch.setattr(drawing, "_ddoc", ddoc)
    monkeypatch.setattr(drawing._sw_type_info, "early_bound_or_flag", bind)
    monkeypatch.setattr(drawing, "double_array", doubles)
    monkeypatch.setattr(drawing, "_place_view_context", None)
    adapter = Adapter()
    scale = None if outcome == "unscaled" else (1, 2)
    if outcome == "invalid_scale":
        scale = ()  # Existing _attempt must still swallow the indexing failure.

    def place():
        return imported_alias(
            adapter, "C:/models/part.SLDPRT", "*Front", 0.1, 0.2, scale=scale
        )

    expected_create = [
        ("ddoc",),
        ("create", ("C:/models/part.SLDPRT", "*Front", 0.1, 0.2, 0.0)),
    ]
    expected = expected_create.copy()
    if outcome != "false_create":
        expected.append(("bind", raw_view, "IView"))
    if outcome in {"scaled", "scale_error", "two_views", "false_factory"}:
        expected.extend([("double_array", [1.0, 2.0]), ("scale", (1.0, 2.0))])

    def invoke():
        if outcome == "false_create":
            with pytest.raises(RuntimeError) as raised:
                place()
            assert str(raised.value) == (
                "CreateDrawViewFromModelView3 failed for '*Front' "
                "(model='C:/models/part.SLDPRT')"
            )
        elif outcome == "bind_error":
            with pytest.raises(OSError) as raised:
                place()
            assert raised.value is failure
        else:
            assert place() is bound_view
        assert calls == expected
        calls.clear()

    # The same pre-imported alias behaves identically before/after installation.
    invoke()
    assert spans.get_finished_spans() == ()
    _telemetry._instrument_loaded_adapter()
    if outcome == "false_factory":
        class FalseFactory:
            def __bool__(self):
                return False

            def __call__(self, name, attributes):
                return _telemetry._place_view_span(name, attributes)

        drawing.set_place_view_context(FalseFactory())
    assert calls == [], "registration must not touch native ports"
    with _telemetry.span("drawing.build"):
        invoke()
    finished = {s.name: s for s in spans.get_finished_spans()}
    suffix = " [part.SLDPRT *Front x=0.1 y=0.2]"
    assert f"drawing.place_view{suffix}" in finished
    parent = finished[f"drawing.place_view{suffix}"]
    assert parent.attributes["phase_kind"] == "placement"
    assert parent.parent.span_id == finished["drawing.build"].context.span_id
    assert parent.attributes["source_file"] == "part.SLDPRT"
    assert parent.attributes["orientation"] == "*Front"
    assert parent.attributes["scale_request"] == (
        "specified" if scale is not None else "omitted"
    )
    phases = ["create"]
    if outcome != "false_create":
        phases.append("bind")
    if outcome not in {"unscaled", "false_create", "bind_error"}:
        phases.append("scale")
    assert {name for name in finished if name.startswith("drawing.place_view.")} == {
        f"drawing.place_view.{phase}{suffix}" for phase in phases
    }
    for phase in phases:
        child = finished[f"drawing.place_view.{phase}{suffix}"]
        assert child.parent.span_id == parent.context.span_id
    failed_phase = {"false_create": "create", "bind_error": "bind"}.get(outcome)
    assert parent.status.status_code.name == ("ERROR" if failed_phase else "OK")
    if failed_phase:
        failed = finished[f"drawing.place_view.{failed_phase}{suffix}"]
        assert failed.status.status_code.name == "ERROR"
        assert failed.attributes["error.type"] == (
            "RuntimeError" if outcome == "false_create" else "OSError"
        )
        assert failed.attributes["error.message"] == parent.attributes["error.message"]
    if "scale" in phases:
        attempted = finished[f"drawing.place_view.scale{suffix}"]
        assert attempted.status.status_code.name == "OK"
        assert attempted.attributes["phase_kind"] == "native_scale_attempt"
    count = len(spans.get_finished_spans())
    drawing.set_place_view_context(None)
    invoke()
    assert len(spans.get_finished_spans()) == count
    _telemetry._instrument_loaded_adapter()
    invoke()
    assert len(spans.get_finished_spans()) > count
    if outcome == "two_views":
        assert imported_alias(
            adapter, "C:/models/part.SLDPRT", "*Front", 0.3, 0.4, scale=scale
        ) is bound_view
        assert calls == [
            ("ddoc",),
            ("create", ("C:/models/part.SLDPRT", "*Front", 0.3, 0.4, 0.0)),
            ("bind", raw_view, "IView"),
            ("double_array", [1.0, 2.0]),
            ("scale", (1.0, 2.0)),
        ]
        names = {s.name for s in spans.get_finished_spans()}
        second = " [part.SLDPRT *Front x=0.3 y=0.4]"
        for phase in ("", ".create", ".bind", ".scale"):
            assert f"drawing.place_view{phase}{suffix}" in names
            assert f"drawing.place_view{phase}{second}" in names


def test_build_session_instruments_only_an_already_loaded_adapter(capture, monkeypatch):
    """``run_build`` imports the adapter before it opens the session; a process
    that never did must not be made to import the COM stack."""
    monkeypatch.delenv("TRACEPARENT", raising=False)
    monkeypatch.delitem(sys.modules, _telemetry._ADAPTER_MODULE, raising=False)
    monkeypatch.delitem(sys.modules, _telemetry._INSERT_COMPONENT_MODULE, raising=False)
    monkeypatch.delitem(sys.modules, _telemetry._FEATURES_MODULE, raising=False)
    monkeypatch.delitem(sys.modules, _telemetry._DRAWING_MODULE, raising=False)
    original_import = builtins.__import__
    attempted_sdk_imports = []

    def reject_sdk_import(name, *args, **kwargs):
        if name.startswith("solidworks_mcp"):
            attempted_sdk_imports.append(name)
            raise AssertionError(f"offline telemetry imported {name}")
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as offline:
        offline.setattr(builtins, "__import__", reject_sdk_import)
        with _telemetry.build_session("offline"):
            pass
    assert attempted_sdk_imports == [], (
        "suppression must not hide an SDK import attempt"
    )
    assert _telemetry._ADAPTER_MODULE not in sys.modules
    assert _telemetry._INSERT_COMPONENT_MODULE not in sys.modules

    cls = _fake_adapter_class()
    monkeypatch.setitem(
        sys.modules,
        _telemetry._ADAPTER_MODULE,
        types.SimpleNamespace(PyWin32Adapter=cls),
    )
    with _telemetry.build_session("cone_gear"):
        pass
    assert getattr(cls.create_plane, "_harmonic_traced", False)


def test_export_save_as_is_visible_during_long_com_call(capture, tmp_path):
    """The multi-minute assembly SaveAs3 call must not be an opaque trace gap."""
    import export_models

    class Doc:
        def SaveAs3(self, path, _version, _options):
            Path(path).write_bytes(b"export")
            return 0

    spans, logs = capture
    out = tmp_path / "machine.STEP"
    assert export_models._save_as(Doc(), out) == 0

    (span,) = [
        item for item in spans.get_finished_spans() if item.name == "export.save_as"
    ]
    assert span.attributes["output"] == str(out)
    assert span.attributes["format"] == "step"
    assert span.attributes["save.rc"] == 0
    assert any(
        record.log_record.body == "SaveAs3 starting -> machine.STEP"
        for record in logs.get_finished_logs()
    )


def test_set_service_relabels_resource_fallback_only():
    """``set_service`` swaps this process's resource ``service.name`` (the Aspire
    "resource" column) -- fallback-only by default (won't clobber a non-default
    label), overridable with force -- and stamps the shared namespace."""
    original = _telemetry._service_name
    try:
        # Hermetic precondition: force back to the default label first, so the
        # fallback path below is actually exercised regardless of any
        # OTEL_SERVICE_NAME the invoking process already set. Under
        # `doit check:telemetry`, dodo sets the per-stage name ('check-telemetry'),
        # which is non-default and would otherwise make the fallback-only
        # set_service("assembly-build") a no-op and fail this test.
        _telemetry.set_service(_telemetry._DEFAULT_SERVICE_NAME, force=True)
        # default -> stage: fallback takes effect and the LIVE resource swaps.
        _telemetry.set_service("assembly-build")
        exp = InMemorySpanExporter()
        cast(
            SdkTracerProvider, _telemetry.trace.get_tracer_provider()
        ).add_span_processor(SimpleSpanProcessor(exp))
        with _telemetry.span("op"):
            pass
        (sp,) = [s for s in exp.get_finished_spans() if s.name == "op"]
        assert sp.resource.attributes["service.name"] == "assembly-build"
        assert (
            sp.resource.attributes["service.namespace"] == _telemetry._SERVICE_NAMESPACE
        )
        # fallback-only: a non-forced call does NOT override an already-set label.
        _telemetry.set_service("part-build")
        assert _telemetry._service_name == "assembly-build"
        # force overrides regardless.
        _telemetry.set_service("verify-kinematics", force=True)
        assert _telemetry._service_name == "verify-kinematics"
    finally:
        _telemetry.set_service(original, force=True)


# --------------------------------------------------------------------------- #
# Atomic JSONL appends. Every COM subprocess appends to the SAME traces.jsonl /
# logs.jsonl, so a record must cross the process boundary whole -- a spliced line
# breaks the rg/jq debugging workflow AGENTS.md relies on.
# --------------------------------------------------------------------------- #

_APPEND_WORKER = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import _telemetry

target, worker, count, pad = Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
w = _telemetry._AtomicJsonlWriter(target)
for i in range(count):
    w.write(json.dumps({"worker": worker, "i": i, "pad": "x" * pad}) + "\n")
# Report accepted-but-lost records, so the parent can tell a WRITER bug (records
# vanish while dropped == 0) from best-effort I/O loss (dropped accounts for them).
Path(str(target) + ".dropped.%d" % worker).write_text(str(w.dropped), encoding="utf-8")
w.close()
"""


def test_concurrent_appends_never_splice_a_record(tmp_path):
    """8 processes x 250 oversized records land as 2000 intact, unique JSON lines."""
    workers, per_worker, pad = 8, 250, 20_000  # pad >> the 8 KB default buffer
    target = tmp_path / "traces.jsonl"
    script = tmp_path / "append_worker.py"
    script.write_text(_APPEND_WORKER, encoding="utf-8")
    scripts_dir = str(Path(__file__).resolve().parent)

    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                scripts_dir,
                str(target),
                str(w),
                str(per_worker),
                str(pad),
            ],
        )
        for w in range(workers)
    ]
    for proc in procs:
        assert proc.wait(timeout=180) == 0

    # Diagnose before asserting. This test failed ONCE in ~16 local runs and the
    # bare "expected 2000, got N" told us nothing about why, so classify every
    # line first and put the classification in the failure message. A recurrence
    # should be explicable from the message alone: splicing (unparseable /
    # wrong-length pad) is a real defect in _AtomicJsonlWriter; whole records
    # simply MISSING points instead at a short write, which `write` accepts as a
    # lost record by design rather than retrying into someone else's append.
    lines = target.read_text(encoding="utf-8").splitlines()
    seen: set[tuple[int, int]] = set()
    unparseable, wrong_pad = 0, 0
    for line in lines:
        try:
            record = json.loads(line)
        except Exception:  # noqa: BLE001 - counting damage, not handling it
            unparseable += 1
            continue
        if len(record.get("pad", "")) != pad:
            wrong_pad += 1
            continue
        seen.add((record["worker"], record["i"]))

    expected = {(w, i) for w in range(workers) for i in range(per_worker)}
    missing = expected - seen
    dropped = sum(
        int(Path(f"{target}.dropped.{w}").read_text(encoding="utf-8") or 0)
        for w in range(workers)
    )
    diagnosis = (
        f"lines={len(lines)} (attempted {workers * per_worker}), "
        f"unparseable={unparseable}, wrong_pad={wrong_pad}, "
        f"missing={len(missing)}, dropped_by_writer={dropped}, "
        f"duplicated={len(lines) - len(seen)}"
    )

    # THE guarantee: a record is never spliced into another, and never appears twice.
    assert unparseable == 0 and wrong_pad == 0, f"records were spliced -- {diagnosis}"
    assert len(lines) == len(seen), f"records were duplicated -- {diagnosis}"

    # Completeness is asserted only up to records the writer ADMITS it lost.
    # `write` deliberately drops a record on a short write or I/O error rather
    # than raising (capture is best-effort and never fatal), so demanding all
    # 2,000 survive would let an explicitly accepted loss fail this mandatory
    # gate (Codex P1). Instead require the accounting to balance: every attempted
    # record is either on disk or counted in `dropped`. A writer bug -- records
    # vanishing with nothing admitted -- still fails, which is the case worth
    # catching.
    assert len(missing) == dropped, diagnosis


_BUFFERED_WORKER = r"""
import json, sys
from pathlib import Path
target, worker, count, pad = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
f = target.open("a", encoding="utf-8")          # the pre-fix buffered path
for i in range(count):
    f.write(json.dumps({"worker": worker, "i": i, "pad": "x" * pad}) + "\n")
f.close()
"""


@pytest.mark.skipif(
    os.environ.get("HARMONIC_TELEMETRY_RACE_REPRO") != "1" or sys.platform != "win32",
    reason=(
        "opt-in AND Windows-only: asserts a RACE reproduces, so it cannot gate "
        "check:telemetry. Run with HARMONIC_TELEMETRY_RACE_REPRO=1 on Windows. "
        "Compared against '1' exactly, so setting it to 0/false to DISABLE the "
        "repro cannot accidentally switch it on and turn the gate red. The "
        "platform guard is not belt-and-braces: on POSIX `open(path, 'a')` uses "
        "O_APPEND, whose appends ARE atomic, so the buffered writers this test "
        "deliberately breaks produce all 2,000 records intact and the assertion "
        "below fails on a correct system (Codex P1, reproduced on Linux). The "
        "corruption it reproduces is a Windows behaviour, so the control only "
        "means anything on Windows."
    ),
)
def test_buffered_appends_do_corrupt_under_the_same_stress(tmp_path):
    """Opt-in repro for WHY the atomic writer exists. NOT a gating test.

    This asserts that a race *reproduces*, which is inherently nondeterministic:
    nothing forces the workers to overlap, so a lucky scheduler or a fast enough
    filesystem can let all 2,000 records through intact and fail this assertion
    even though ``_AtomicJsonlWriter`` is perfectly correct (Codex P2). A
    mandatory gate must never be able to go red that way -- the repo's rule is
    that there are no flaky tests, only broken ones -- so it is gated behind
    ``HARMONIC_TELEMETRY_RACE_REPRO=1`` and kept as executable documentation of
    the measurement, not as a check.

    **Windows only, and that is the point.** CPython's ``open(path, "a")`` maps
    to ``O_APPEND`` on POSIX, where the kernel places each write, so the
    buffered path is already safe there and this control correctly finds all
    2,000 records intact (Codex reproduced exactly that on Linux). On Windows
    there is no ``O_APPEND``: append mode is emulated by seeking to
    end-of-file and writing, so two processes pick the same offset and both
    splice records AND overwrite each other. Measured on this repo's seat with
    8 x 250 x 20 KB records: 1516 of 2000 lines survived, 18 structurally
    malformed.

    So the bug -- and the value of ``_AtomicJsonlWriter`` -- is Windows-specific.
    The POSIX branch of the writer is an explicit spelling of what CPython
    already does, kept so the class does not depend on that implementation
    detail. Without this control, "the buffered path is broken" would be a claim
    with no repro, and the atomic test above would prove only that SOMETHING
    passes, not that it fixed anything.
    """
    workers, per_worker, pad = 8, 250, 20_000
    target = tmp_path / "traces.jsonl"
    script = tmp_path / "buffered_worker.py"
    script.write_text(_BUFFERED_WORKER, encoding="utf-8")

    procs = [
        subprocess.Popen(
            [
                sys.executable,
                str(script),
                str(target),
                str(w),
                str(per_worker),
                str(pad),
            ],
        )
        for w in range(workers)
    ]
    for proc in procs:
        assert proc.wait(timeout=180) == 0

    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    intact = 0
    for line in lines:
        try:
            json.loads(line)
            intact += 1
        except Exception:  # noqa: BLE001 - counting damage, not handling it
            pass
    assert intact < workers * per_worker, (
        "buffered concurrent appends survived intact -- if this ever passes "
        "cleanly, the platform changed and _AtomicJsonlWriter may be redundant"
    )


def test_short_append_is_never_retried_with_a_second_append(tmp_path, monkeypatch):
    """One record = one append operation, even when the write comes up short.

    Finishing a short write with a SECOND append of the SUFFIX is worse than
    losing the record: another process can append in between, giving
    ``prefix + their record + suffix`` and destroying two records instead of
    truncating one (Codex P2). So the record itself gets exactly one append
    attempt, and no exception either way. The lone newline that follows is not
    a retry -- it carries no record bytes; see the orphan-termination test.
    """
    record = '{"hello": "world"}\n'
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    try:
        calls: list[bytes] = []

        def short(payload: bytes) -> int:
            calls.append(payload)
            return 3  # short: only 3 of the bytes land

        monkeypatch.setattr(writer, "_raw_write", short)
        assert writer.write(record) == len(record)  # must not raise
        # The loss must be COUNTED -- the stress test's accounting assertion
        # silently degrades back to a strict count if this stops incrementing.
        assert writer.dropped == 1
    finally:
        writer.close()
    assert calls[0] == record.encode()
    # The record is never re-attempted; only its orphaned line gets closed.
    assert calls[1:] == [b"\n"], f"record was split across {len(calls)} appends"


def test_a_failing_append_never_propagates_into_pipeline_work(tmp_path, monkeypatch):
    """An I/O error during capture drops the record; it does not fail the build."""
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    try:

        def explode(_payload: bytes) -> int:
            raise OSError("disk full")

        monkeypatch.setattr(writer, "_raw_write", explode)
        assert writer.write('{"hello": "world"}\n') == 19  # swallowed
        assert writer.dropped == 1  # swallowed, but not invisible
    finally:
        writer.close()


def test_a_partial_write_retires_the_writer_instead_of_corrupting_the_next(tmp_path):
    """A short append leaves an unterminated prefix that the NEXT append lands on.

    The record itself is unrecoverable -- retrying the suffix is the splice this
    class exists to prevent -- so the writer goes quiet. One trailing line is
    damaged instead of every record after it.
    """
    target = tmp_path / "traces.jsonl"
    writer = _telemetry._AtomicJsonlWriter(target)
    calls = []

    def short_once(payload):
        calls.append(payload)
        return len(payload) - 3  # a genuine positive-length short write

    writer._raw_write = short_once
    writer.write('{"name":"a"}\n')
    # The record is NOT finished with a second append -- the only follow-up is
    # the lone newline that closes the line it orphaned.
    assert calls == [b'{"name":"a"}\n', b"\n"]

    writer.write('{"name":"b"}\n')
    writer.write('{"name":"c"}\n')
    assert len(calls) == 2, "retired writer must not append after a short write"
    assert writer.dropped == 3


def test_a_partial_write_closes_the_line_it_orphaned(tmp_path):
    """The orphan gets a newline so a PEER's next record stays parsable.

    Not a contradiction of "never retry": a suffix landing after a peer's record
    splices prefix+their-record+suffix and destroys two records, but peers'
    records already end in a newline, so a lone newline can only ever add a
    blank line -- which every reader skips. Win the race and the peer's record
    survives intact; lose it and the damage is what it would have been anyway.
    """
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    appends = []

    def short_once(payload):
        appends.append(payload)
        return len(payload) - 3 if len(appends) == 1 else len(payload)

    writer._raw_write = short_once
    writer.write('{"name":"a"}\n')
    assert appends[-1] == b"\n", "orphaned prefix must be terminated"


def test_a_zero_length_write_orphans_nothing_so_adds_no_newline(tmp_path):
    """No bytes landed, so no line is open -- a newline there would be litter."""
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    appends = []

    def wrote_nothing(payload):
        appends.append(payload)
        return 0

    writer._raw_write = wrote_nothing
    writer.write('{"name":"a"}\n')
    assert appends == [b'{"name":"a"}\n']
    assert writer.dropped == 1


def test_a_failing_repair_never_escapes_the_writer(tmp_path):
    """The newline is best-effort like every other append here."""
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    state = {"n": 0}

    def short_then_raise(payload):
        state["n"] += 1
        if state["n"] == 1:
            return len(payload) - 3
        raise OSError("disk gone")

    writer._raw_write = short_then_raise
    writer.write('{"name":"a"}\n')  # must not raise
    assert writer.dropped == 1


def test_shutdown_reports_once_even_though_atexit_shuts_down_again(tmp_path, capsys):
    """OTel providers keep their interpreter-exit callbacks, so an explicit
    shutdown() is followed by a second one at atexit. Two identical warnings
    would read as two separate failures."""
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    writer.dropped = 2
    _telemetry._close_jsonl_writer(writer, "span")
    _telemetry._close_jsonl_writer(writer, "span")
    assert capsys.readouterr().err.count("dropped 2 span record(s)") == 1


def test_shutdown_reports_dropped_records_to_stderr(tmp_path, capsys):
    """A silent drop must be announced once, at the only safe moment.

    Without this the counter would be test-only instrumentation and a short
    .jsonl would be indistinguishable from a writer bug. It goes straight to
    stderr rather than through this module's logging, which would re-enter the
    exporter being shut down.
    """
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    writer.dropped = 3
    _telemetry._close_jsonl_writer(writer, "span")
    err = capsys.readouterr().err
    assert "dropped 3 span record(s)" in err
    assert "incomplete" in err


def test_shutdown_is_silent_when_nothing_was_dropped(tmp_path, capsys):
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    _telemetry._close_jsonl_writer(writer, "span")
    assert "dropped" not in capsys.readouterr().err


def test_jsonl_stream_falls_back_when_the_atomic_path_is_unavailable(
    tmp_path, monkeypatch
):
    """Capture must never go dark: an unusable atomic writer degrades to buffered."""

    def boom(_path):
        raise RuntimeError("no win32 extensions here")

    monkeypatch.setattr(_telemetry, "_AtomicJsonlWriter", boom)
    stream = _telemetry._jsonl_stream(tmp_path / "logs.jsonl")
    try:
        stream.write('{"fallback": true}\n')
    finally:
        stream.close()
    assert json.loads((tmp_path / "logs.jsonl").read_text(encoding="utf-8")) == {
        "fallback": True
    }


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

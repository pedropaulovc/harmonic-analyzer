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
import json
import subprocess
import sys
import time
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
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _telemetry  # noqa: E402


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
    cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider()).add_span_processor(processor)
    # Auxiliary per-resource providers (build-infra) are built lazily from
    # ``_span_processors``, so register there too -- and drop any already built -- or
    # a test would see nothing from spans emitted under another resource.
    _telemetry._span_processors.append(processor)
    _telemetry._aux_providers.clear()

    logs = InMemoryLogRecordExporter()
    cast(SdkLoggerProvider, get_logger_provider()).add_log_record_processor(SimpleLogRecordProcessor(logs))
    yield spans, logs

    _telemetry._span_processors.remove(processor)
    _telemetry._aux_providers.clear()


def test_logs_split_into_severity_levels(capture):
    _, logs = capture
    _telemetry.debug("chatter")
    _telemetry.info("neutral")
    _telemetry.success("passed")
    _telemetry.warn("careful")
    _telemetry.error("broke")

    seen = {r.log_record.severity_text for r in logs.get_finished_logs()}
    assert {"DEBUG", "INFO", "SUCCESS", "WARN", "ERROR"} <= seen


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
    rootspan = [s for s in spans.get_finished_spans() if s.name == "build.cone_gear"][-1]
    op = [s for s in spans.get_finished_spans() if s.name == "op"][-1]
    assert rootspan.attributes["label"] == "cone_gear"
    assert op.parent.span_id == rootspan.context.span_id


def test_build_session_continues_injected_parent_without_duplicate(capture, monkeypatch):
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

    with _telemetry.build_session("build_cone_gear") as root:
        assert root is None  # no duplicate root layer
        with _telemetry.span("op"):
            pass

    task = [s for s in spans.get_finished_spans() if s.name == "part:cone_gear"][-1]
    op = [s for s in spans.get_finished_spans() if s.name == "op"][-1]
    assert op.context.trace_id == task.context.trace_id
    assert op.parent.trace_id == task.context.trace_id


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
        with _telemetry.span("com.seat.wait part:cone_gear",
                             service=_telemetry.BUILD_INFRA_SERVICE) as seat:
            seat_trace = seat.get_span_context().trace_id

    finished = {s.name: s for s in spans.get_finished_spans()}
    task, wait = finished["task part:cone_gear"], finished["com.seat.wait part:cone_gear"]
    assert wait.resource.attributes["service.name"] == "build-infra"
    assert task.resource.attributes["service.name"] == _telemetry._service_name
    assert wait.resource.attributes["service.namespace"] == "harmonic-analyzer"
    # Provider ≠ context: the infra span still parents under the task span.
    assert seat_trace == task.context.trace_id
    assert wait.parent.span_id == task.context.span_id


def test_process_startup_is_billed_to_the_parent_trace(capture, monkeypatch):
    """The spawn + interpreter + import region between a parent launching a process
    and that process's first span is DARK -- ~2-5 s per COM task. ``inject_env``
    stamps the launch instant and the child draws it as ``proc.startup``
    (``proc.launch`` + ``proc.import``), back-dated via OTel's creation-time
    ``start_time`` -- the sanctioned way to record an interval already past."""
    spans, _ = capture
    now = time.time_ns()
    monkeypatch.setattr(_telemetry, "_startup_recorded", False)
    monkeypatch.setattr(_telemetry, "_IMPORT_NS", now - int(1.5e9))  # imported 1.5 s ago
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
    span_proc, log_proc = _telemetry._otlp_span_processor(), _telemetry._otlp_log_processor()
    try:
        assert type(span_proc).__name__ == "BatchSpanProcessor"
        assert type(log_proc).__name__ == "BatchLogRecordProcessor"
    finally:
        for processor in (span_proc, log_proc):
            if processor is not None:
                processor.shutdown()

    simple = [p for p in _telemetry._span_processors
              if type(p).__name__ == "SimpleSpanProcessor"]
    assert simple, "console/file capture must stay on Simple processors"


def test_default_otlp_endpoint_is_a_literal_address_never_localhost(monkeypatch):
    """Measured: the first OTLP POST to ``localhost`` cost 2.05 s vs 0.003 s to
    ``127.0.0.1`` -- Windows tries ``::1`` first and the dashboard is IPv4, so every
    process ate a failed connect (per process, holding the seat). Defaults are literal
    addresses, IPv4 first, with the v6 loopback as a fallback so a v6-only dashboard
    still exports."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert not any("localhost" in e for e in _telemetry._DEFAULT_OTLP_ENDPOINTS)

    monkeypatch.setattr(_telemetry, "_endpoint_listening", lambda e, timeout=0.15: True)
    assert _telemetry._resolve_otlp_endpoint() == "http://127.0.0.1:18890"

    v6_only = lambda e, timeout=0.15: e.startswith("http://[::1]")  # noqa: E731
    monkeypatch.setattr(_telemetry, "_endpoint_listening", v6_only)
    assert _telemetry._resolve_otlp_endpoint() == "http://[::1]:18890"

    monkeypatch.setattr(_telemetry, "_endpoint_listening", lambda e, timeout=0.15: False)
    assert _telemetry._resolve_otlp_endpoint() is None, "nothing listening: export nowhere"

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    assert _telemetry._resolve_otlp_endpoint() == "http://collector:4318", "env wins"


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
    wait, task = finished["com.seat.wait part:cone_gear"], finished["task part:cone_gear"]
    assert task.parent is None and wait.parent is None, "the wait must not parent the task"
    assert (wait.end_time - wait.start_time) / 1e9 >= 0.2
    # The ordering is the real invariant, and it is deterministic. An upper bound on
    # the task span's own duration would only measure how busy the host is -- a
    # descheduled process would fail it while the topology was perfectly correct
    # (codex #424).
    assert task.start_time >= wait.end_time, "the task must start once the seat is held"
    assert wait.end_time <= task.start_time, "no overlap: the wait cannot leak into work"


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
        cast(SdkTracerProvider, _telemetry.trace.get_tracer_provider()).add_span_processor(
            SimpleSpanProcessor(exp)
        )
        with _telemetry.span("op"):
            pass
        (sp,) = [s for s in exp.get_finished_spans() if s.name == "op"]
        assert sp.resource.attributes["service.name"] == "assembly-build"
        assert sp.resource.attributes["service.namespace"] == _telemetry._SERVICE_NAMESPACE
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
            [sys.executable, str(script), scripts_dir, str(target),
             str(w), str(per_worker), str(pad)],
        )
        for w in range(workers)
    ]
    for proc in procs:
        assert proc.wait(timeout=180) == 0

    lines = target.read_text(encoding="utf-8").splitlines()
    assert len(lines) == workers * per_worker, (
        f"expected {workers * per_worker} lines, got {len(lines)}"
    )
    seen = set()
    for n, line in enumerate(lines):
        record = json.loads(line)  # a spliced record raises here
        assert len(record["pad"]) == pad, f"line {n} truncated"
        seen.add((record["worker"], record["i"]))
    assert seen == {(w, i) for w in range(workers) for i in range(per_worker)}


_BUFFERED_WORKER = r"""
import json, sys
from pathlib import Path
target, worker, count, pad = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
f = target.open("a", encoding="utf-8")          # the pre-fix buffered path
for i in range(count):
    f.write(json.dumps({"worker": worker, "i": i, "pad": "x" * pad}) + "\n")
f.close()
"""


def test_buffered_appends_do_corrupt_under_the_same_stress(tmp_path):
    """Positive control for the fix above -- pin WHY the atomic writer exists.

    Python's ``open(path, "a")`` is not an append-only kernel handle on Windows:
    each process picks its own end-of-file offset, so concurrent writers both
    splice records AND overwrite each other. Measured on this repo's seat with
    8 x 250 x 20 KB records: 1516 of 2000 lines survived, 18 structurally
    malformed. Without this control, "the buffered path is broken" would be a
    claim with no repro -- and the atomic test above would prove only that
    SOMETHING passes, not that it fixed anything.
    """
    workers, per_worker, pad = 8, 250, 20_000
    target = tmp_path / "traces.jsonl"
    script = tmp_path / "buffered_worker.py"
    script.write_text(_BUFFERED_WORKER, encoding="utf-8")

    procs = [
        subprocess.Popen(
            [sys.executable, str(script), str(target),
             str(w), str(per_worker), str(pad)],
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


def test_short_append_raises_rather_than_writing_half_a_record(tmp_path, monkeypatch):
    """A partial write is the malformed JSONL this exists to prevent -- fail loud."""
    writer = _telemetry._AtomicJsonlWriter(tmp_path / "traces.jsonl")
    try:
        if writer._handle is not None:
            import win32file

            monkeypatch.setattr(win32file, "WriteFile", lambda *a, **k: (0, 3))
        else:
            monkeypatch.setattr(_telemetry.os, "write", lambda *a, **k: 3)
        with pytest.raises(OSError, match="short telemetry append"):
            writer.write('{"hello": "world"}\n')
    finally:
        writer.close()


def test_jsonl_stream_falls_back_when_the_atomic_path_is_unavailable(tmp_path, monkeypatch):
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

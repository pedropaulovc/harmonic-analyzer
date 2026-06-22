r"""Tests for the OpenTelemetry observability spine (cad/scripts/_telemetry.py).

Pure python, NO SolidWorks: spans + logs are captured by attaching in-memory
exporters to the configured providers, so the assertions read the real OTel
records the pipeline would emit. Covers the four things the spine promises:
severity-levelled logs, no-gap spans (exceptions recorded + status ERROR),
log<->trace correlation, and cross-process trace-context propagation.

    python cad/scripts/test_telemetry.py     # or: pytest cad/scripts/test_telemetry.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs.export import (
    InMemoryLogRecordExporter,
    SimpleLogRecordProcessor,
)
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
    _telemetry.trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(spans))

    logs = InMemoryLogRecordExporter()
    get_logger_provider().add_log_record_processor(SimpleLogRecordProcessor(logs))
    return spans, logs


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
            env={**env, "HARMONIC_OTEL_QUIET": "1"},
            cwd=str(Path(__file__).resolve().parent),
            capture_output=True,
            text=True,
        )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == parent_trace


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))

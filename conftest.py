"""Isolate pytest telemetry before test modules (and their imports) are collected.

Keep full local traces/logs per invocation, including ordinary child processes.
Tests must not append mock operations to production evidence or publish them to
the configured production dashboard. This explicit pytest bootstrap owns the
policy; application telemetry has no pytest detection or test-only drop mode.
"""

import os
from pathlib import Path
import tempfile


_CAPTURE_ROOT = (
    Path(__file__).resolve().parent / "cad" / "out" / "reports" / "pytest-telemetry"
)
_CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
_CAPTURE_DIR = Path(tempfile.mkdtemp(prefix="run-", dir=_CAPTURE_ROOT))
os.environ["HARMONIC_TELEMETRY_DIR"] = str(_CAPTURE_DIR)
for _signal in ("", "_TRACES", "_LOGS", "_METRICS"):
    os.environ[f"OTEL_EXPORTER_OTLP{_signal}_ENDPOINT"] = ""
for _context in ("TRACEPARENT", "TRACESTATE"):
    os.environ.pop(_context, None)


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(f"Pytest telemetry retained: {_CAPTURE_DIR}")

"""Isolate pytest telemetry before test modules (and their imports) are collected.

Keep full local traces/logs per invocation, including ordinary child processes.
Tests must not append mock operations to production evidence or publish them to
the configured production dashboard. This explicit pytest bootstrap owns the
policy; application telemetry has no pytest detection or test-only drop mode.
"""

import os
from pathlib import Path
import sys
import tempfile


_NATIVE_OUTPUT_ROOTS = tuple(
    (Path(__file__).resolve().parent / "cad" / "out" / kind).resolve()
    for kind in ("sldprt", "sldasm", "slddrw")
)


def _guard_native_outputs(event, args):
    """Catch accidental Python fixture writes; not a COM/OS security sandbox.

    CPython audit events cover pathlib, builtins/io.open, os.open, and normal
    rename/delete/copy routes. Install before collection, independently of mocked
    application path constants. Tests may read live CAD or copy it OUT, but must
    write fixtures beneath their own tmp_path. Native diagnostic programs do not
    load conftest and are unaffected.
    https://docs.python.org/3/library/audit_events.html
    """
    if event == "open":
        if not args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return
        candidates = args[:1]
    elif event in ("os.rename", "os.link", "os.symlink", "shutil.move"):
        candidates = args[:2]
    elif event in ("os.remove", "os.rmdir", "os.truncate", "shutil.rmtree"):
        candidates = args[:1]
    elif event in ("shutil.copyfile", "shutil.copytree"):
        candidates = args[1:2]
    else:
        return
    for candidate in candidates:
        if not isinstance(candidate, (str, bytes, os.PathLike)):
            continue
        path = Path(os.fsdecode(candidate)).resolve()
        if any(
            path.is_relative_to(root) or root.is_relative_to(path)
            for root in _NATIVE_OUTPUT_ROOTS
        ):
            raise PermissionError(f"pytest native output guard: {event} would mutate {path}")


sys.addaudithook(_guard_native_outputs)


_CAPTURE_ROOT = (
    Path(__file__).resolve().parent / "cad" / "out" / "reports" / "pytest-telemetry"
)
_CAPTURE_ROOT.mkdir(parents=True, exist_ok=True)
_CAPTURE_DIR = Path(tempfile.mkdtemp(prefix="run-", dir=_CAPTURE_ROOT))
os.environ["HARMONIC_TELEMETRY_DIR"] = str(_CAPTURE_DIR)
for _signal in ("", "_TRACES", "_LOGS", "_METRICS"):
    os.environ[f"OTEL_EXPORTER_OTLP{_signal}_ENDPOINT"] = ""
# The spawn timestamp belongs to the same production parent as its trace context.
# Keeping it after detaching that context emits an unrelated proc.startup root
# inside whichever test first opens a pipeline/build session.
for _context in ("TRACEPARENT", "TRACESTATE", "HARMONIC_SPAWN_NS"):
    os.environ.pop(_context, None)


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(f"Pytest telemetry retained: {_CAPTURE_DIR}")

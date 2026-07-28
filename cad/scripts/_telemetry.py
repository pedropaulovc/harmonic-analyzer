"""OpenTelemetry observability spine for the harmonic-analyzer pipeline.

This module replaces the ad-hoc ``print()``-prefix logging convention that used
to thread through every build script (``  OK  `` / ``  ..  `` / ``  -- `` /
``  !! WARN`` / ``FAIL``) with structured OpenTelemetry signals, while keeping
the console output just as readable as before.

What you get, **preconfigured on import** (zero env, no collector):

* **Console logging, split by severity.** A human-friendly stream handler prints
  one line per log record to stderr, the severity rendered as the old glyph
  prefix (``..`` DEBUG, ``--`` INFO, ``OK`` SUCCESS, ``!!`` WARN, ``xx`` ERROR),
  carried on a ``[total +step]`` wall-clock stamp. The same records are bridged
  into OpenTelemetry's logs SDK at the matching ``SeverityNumber`` and tagged
  with the active span's trace/span id, so logs and traces correlate.
* **Console tracing.** Every span prints a compact, depth-indented boundary line
  on completion (``⟩ name 1.23s OK``) so the trace tree is visible inline.
* **No-gap spans.** :func:`span` / :func:`aspan` record exceptions on the active
  span and set its status to ERROR before re-raising, so a failure is never a
  silent hole in the trace — and :func:`run_pipeline_span` opens a root span that
  spans an entire process invocation, so every child has a parent.
* **Structured capture (best-effort).** Full span/log JSON is also written under
  ``cad/out/reports/telemetry/`` for post-hoc querying; failures there never
  break a build (same discipline as the cache ``.jsonl`` log).

Drop-in for the old helpers: ``progress()`` == the old ``log()``, ``success()``
== the ``  OK  `` lines, ``warn()`` / ``error()`` == the ``!!`` / ``FAIL`` lines.
``_common`` re-exports these so the 173 scripts importing ``log``/``check`` are
instrumented without touching their call sites.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import inspect
import logging
import os
import socket
import sys
import time
import urllib.parse
from collections.abc import AsyncGenerator, Generator, Mapping
from pathlib import Path
from typing import IO, Any, cast

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry._logs import get_logger_provider, set_logger_provider
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    ConsoleLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import Span, Status, StatusCode

# --------------------------------------------------------------------------- #
# Severity model. The build pipeline always thought in five levels; we keep    #
# them and add SUCCESS (the ``  OK  `` lines) as a first-class one between INFO #
# and WARNING so a passing gate reads differently from chatty progress.        #
# --------------------------------------------------------------------------- #

SUCCESS = 25  # between logging.INFO (20) and logging.WARNING (30)
logging.addLevelName(SUCCESS, "SUCCESS")

# severity -> the glyph prefix the build console has always used.
_GLYPH = {
    logging.DEBUG: "..",
    logging.INFO: "--",
    SUCCESS: "OK",
    logging.WARNING: "!!",
    logging.ERROR: "xx",
    logging.CRITICAL: "XX",
}

_SERVICE_NAME = "harmonic-analyzer"
_LOGGER_NAME = "harmonic"

# The OTLP/Aspire "resource" column groups spans by SERVICE. A whole pipeline run
# spans several distinct roles -- building a part, mating an assembly, running the
# kinematic gates, exporting, cutting a release -- so labelling every process the
# same "harmonic-analyzer" wastes that column. Instead each process advertises its
# PIPELINE STAGE as ``service.name`` (part-build / assembly-build / verify-* /
# export / release), under the shared ``service.namespace`` umbrella, so the
# resource column reads as the subsystem doing the work. The stage is taken from
# ``OTEL_SERVICE_NAME`` (the standard OTel env var) -- dodo sets it per subprocess
# (see ``_stage_name`` in dodo.py) so a child is labelled the moment it imports;
# a standalone script self-labels via :func:`set_service`. Absent either, it falls
# back to the umbrella name.
_SERVICE_NAMESPACE = "harmonic-analyzer"
_DEFAULT_SERVICE_NAME = "harmonic-analyzer"

# The doit PARENT process drives two different things: the pipeline's tasks, and the
# machinery that decides whether a task runs at all (the COM seat queue, the remote
# artefact cache). Those belong to no pipeline STAGE -- they are build infrastructure,
# and lumping them under the umbrella ``harmonic-analyzer`` resource left the Aspire
# resource column unable to answer "how much of this build was queueing and transfers?".
# They are emitted through a SECOND provider whose resource says so; see
# :func:`_provider_for_service`. A resource is fixed per provider, so a process that
# emits under two resources needs two providers -- they share this process's span
# PROCESSORS, so there is still one console stream and one traces.jsonl handle.
BUILD_INFRA_SERVICE = "build-infra"

# Wall-clock (not monotonic -- it must be comparable across processes, exactly like an
# OTel timestamp) of this module's import, and the env var a parent stamps with its own
# clock right before spawning a child. Together they light up the otherwise DARK region
# between "the parent launched a subprocess" and "the subprocess opened its first span":
# process creation + interpreter boot + the import graph, measured at ~2-5 s per COM
# task on this seat. See :func:`record_process_startup`.
_IMPORT_NS = time.time_ns()
SPAWN_ENV = "HARMONIC_SPAWN_NS"


def _resolve_service_name() -> str:
    return os.environ.get("OTEL_SERVICE_NAME") or _DEFAULT_SERVICE_NAME


_service_name = _resolve_service_name()

# Project default: ship OTLP to a local **.NET Aspire dashboard** (standalone
# image's OTLP/HTTP port) with zero env. So `doit ...` / a build script lights up
# the dashboard's traces+logs the moment it's running -- no OTEL_* exports needed.
# Override or disable with OTEL_EXPORTER_OTLP_ENDPOINT (set it empty to turn off).
#
# By LITERAL ADDRESS, never the name "localhost". Measured on this seat: the first
# OTLP POST to ``http://localhost:18890`` cost 2.05 s, and to
# ``http://127.0.0.1:18890`` 0.003 s -- Windows resolves ``localhost`` to ``::1``
# first, the dashboard listens on IPv4, so every process paid a ~2 s failed connect
# before falling back (twice: once for spans, once for logs). That is per PROCESS,
# and a build subprocess pays it holding the COM seat. IPv4 is tried first because
# that is what the Aspire container publishes; the IPv6 loopback is kept as a
# fallback so a v6-only dashboard still gets export rather than silence.
_OTLP_PORT = 18890
_DEFAULT_OTLP_ENDPOINTS = (f"http://127.0.0.1:{_OTLP_PORT}", f"http://[::1]:{_OTLP_PORT}")


def _endpoint_listening(endpoint: str, timeout: float = 0.15) -> bool:
    """True if something is accepting TCP on ``endpoint``'s host:port.

    A cheap reachability probe so the DEFAULT endpoint is used only when the
    Aspire dashboard is actually up: without it a build with no dashboard would
    pay per-span OTLP export retries (a headless/CI build must never slow down
    just because telemetry has nowhere to go). An explicit env endpoint skips the
    probe -- if you set it, you mean it.
    """
    try:
        parsed = urllib.parse.urlsplit(endpoint)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_otlp_endpoint() -> str | None:
    """The OTLP base endpoint to export to, or ``None`` to export nowhere.

    Precedence: an explicit ``OTEL_EXPORTER_OTLP_ENDPOINT`` always wins (empty
    string disables export); otherwise fall back to the local Aspire dashboard
    default -- IPv4 loopback first, then IPv6 -- but only when it is actually
    listening, and by literal address so no name resolution can stall the first
    export (see :data:`_DEFAULT_OTLP_ENDPOINTS`).
    """
    env = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if env is not None:
        return env or None
    return next((e for e in _DEFAULT_OTLP_ENDPOINTS if _endpoint_listening(e)), None)

_T0 = time.perf_counter()
_LAST_TICK = _T0

# Monotonic timestamp of the last telemetry ACTIVITY -- a span boundary or a log
# record. This is the per-operation heartbeat the COM watchdog (_watchdog.py)
# keys its idle timeout on: the instrumentation already brackets every COM
# operation (the @traced helpers, the gate spans, the severity logs), so "no
# activity" is a faithful proxy for "stuck inside one COM call".
_last_activity = time.monotonic()
_last_activity_op = "process-start"


def _touch_activity(op: str | None = None) -> None:
    global _last_activity, _last_activity_op
    _last_activity = time.monotonic()
    if op:
        _last_activity_op = op


def last_activity() -> float:
    """Monotonic time of the last span boundary or log record (see _watchdog)."""
    return _last_activity


def last_activity_op() -> str:
    """What the last activity WAS (``span-start <name>`` / ``span-end <name>`` /
    ``log <message head>``). When the watchdog aborts on idle timeout this names
    the operation the pipeline was last seen in -- i.e. the COM call it is
    almost certainly wedged inside -- so the abort is traceable without
    scrollback archaeology."""
    return _last_activity_op


class _ActivityFilter(logging.Filter):
    """Logger-level filter: every record pokes the watchdog heartbeat.

    EXCEPT records the watchdog emits about itself (``watchdog_signal=True``
    field): its periodic hung-window warn would otherwise reset the very idle
    clock the op timeout reads, so a permanently wedged SolidWorks would be
    warned about every 5 min forever and never aborted (codex #344 P1).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "watchdog_signal", False):
            _touch_activity(f"log {str(record.msg)[:80]}")
        return True

# Span nesting depth for the compact console tracer, so the boundary lines
# indent into a tree and a missing parent is visible at a glance.
_depth: contextvars.ContextVar[int] = contextvars.ContextVar("_telemetry_depth", default=0)

_configured = False
# Span processors of the CURRENT configuration, shared with every auxiliary provider
# (one per extra resource this process emits under) so they all land on the same
# console stream / traces.jsonl / OTLP exporter instead of duplicating handles.
_span_processors: list[Any] = []
_aux_providers: dict[str, Any] = {}


def _stamp() -> str:
    """``[total +step]`` wall-clock prefix; step = time since the last record."""
    global _LAST_TICK
    now = time.perf_counter()
    prefix = f"[{now - _T0:7.1f}s +{now - _LAST_TICK:5.1f}s]"
    _LAST_TICK = now
    return prefix


class _FriendlyFormatter(logging.Formatter):
    """Render a record as the historical ``  <glyph>  [stamp] message`` line."""

    def format(self, record: logging.LogRecord) -> str:
        glyph = _GLYPH.get(record.levelno, "..")
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return f"  {glyph}  {_stamp()} {message}"


def _compact_span(span: ReadableSpan) -> str:
    """One depth-indented line per finished span: ``⟩ name 1.23s OK [attrs]``."""
    depth_raw = (span.attributes or {}).get("harmonic.depth", 0)
    depth = int(depth_raw) if isinstance(depth_raw, (int, float, str)) else 0
    dur = (span.end_time - span.start_time) / 1e9 if span.end_time and span.start_time else 0.0
    status = span.status.status_code.name if span.status else "UNSET"
    mark = {"OK": "OK", "ERROR": "xx", "UNSET": "--"}.get(status, status)
    indent = "  " * depth
    extra = ""
    if span.attributes:
        shown = {
            k: v for k, v in span.attributes.items() if not k.startswith("harmonic.")
        }
        if shown:
            extra = "  " + " ".join(f"{k}={v}" for k, v in shown.items())
    return f"  ⟩  {indent}{span.name} {dur:6.2f}s {mark}{extra}\n"


def _telemetry_dir() -> Path | None:
    """``cad/out/reports/telemetry`` if it can be created, else ``None``.

    Best-effort, exactly like the cache ``.jsonl`` log: telemetry capture must
    never be the reason a build fails.
    """
    try:
        out = Path(__file__).resolve().parents[1] / "out" / "reports" / "telemetry"
        out.mkdir(parents=True, exist_ok=True)
        return out
    except Exception:  # noqa: BLE001 - capture is best-effort, never fatal
        return None


class _AtomicJsonlWriter:
    """Append one JSONL record per kernel write, so concurrent processes interleave
    whole records instead of splicing them.

    Every COM subprocess appends to the SAME ``traces.jsonl``/``logs.jsonl``, and
    under ``-n N`` a dozen of them are open at once. A buffered ``TextIOWrapper``
    picks its write offset in user space, so two processes flushing a >4 KB record
    can land the tail of one inside the other -- observed as malformed lines that
    break the ``rg``/``jq`` workflow AGENTS.md points at for debugging.

    Opening the file APPEND-ONLY hands end-of-file placement to the kernel for
    every write, which is what makes a single write indivisible: on Windows that
    is ``FILE_APPEND_DATA`` **alone** (0x0004 -- OR-ing in ``FILE_WRITE_DATA``
    silently loses the guarantee). No cross-process lock on the telemetry hot path.

    The defect is Windows-specific, which is where this project runs: Windows has
    no ``O_APPEND``, so CPython emulates append mode by seeking to end-of-file and
    writing, and concurrent writers race on that offset. The ``O_APPEND`` branch
    below exists only so the SolidWorks-free telemetry tests stay meaningful in a
    Linux review sandbox -- CPython's ``"a"`` already does exactly that there.

    Writing is best-effort and never raises -- see ``write``.
    """

    def __init__(self, path: Path):
        self._handle: Any | None = None
        self._fd: int | None = None
        # Records this writer accepted but could not put on disk (short write or
        # I/O error). Capture is best-effort, so losing one must not raise -- but
        # the loss must not be INVISIBLE either, or "the file is short" and "the
        # writer is broken" become indistinguishable (Codex P1).
        self.dropped = 0
        self._retired = False
        if os.name == "nt":
            import win32con
            import win32file

            _FILE_APPEND_DATA = 0x0004
            self._handle = win32file.CreateFile(
                str(path),
                _FILE_APPEND_DATA,
                win32con.FILE_SHARE_READ
                | win32con.FILE_SHARE_WRITE
                | win32con.FILE_SHARE_DELETE,
                None,
                win32con.OPEN_ALWAYS,
                win32con.FILE_ATTRIBUTE_NORMAL,
                None,
            )
            return
        self._fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o666)

    def _raw_write(self, payload: bytes) -> int:
        if self._handle is not None:
            import win32file

            _, written = win32file.WriteFile(self._handle, payload)
            return int(written)
        assert self._fd is not None
        return os.write(self._fd, payload)

    def write(self, value: str) -> int:
        """Append one record with EXACTLY ONE append operation, best-effort.

        Two hard rules, both learned from review:

        **Never raise.** This runs synchronously inside ``SimpleSpanProcessor`` /
        ``SimpleLogRecordProcessor``, on the calling thread, every time a span
        ends or a log is emitted. AGENTS.md makes file capture best-effort
        ("telemetry capture must never be the reason a build fails"), so a
        low-disk or I/O error here must not abort real pipeline work.

        **Never retry.** A short write must NOT be finished with a second append.
        The whole guarantee of this class is one record = one kernel append; a
        follow-up append can land after some other process's record, producing
        ``prefix + their record + suffix`` and destroying TWO records instead of
        leaving one truncated. So a short write is accepted as a lost record and
        nothing further is written. (Under ``FILE_APPEND_DATA`` on a local file
        this needs a disk already failing mid-write, at which point the capture
        is doomed either way -- but the failure must stay contained.)

        **A PARTIAL write retires the writer.** A short write leaves an
        unterminated prefix at EOF, so the next append -- from this process or
        any other -- lands on the same line and corrupts that record too. Since
        the prefix cannot be repaired (padding it is another racy append, and
        retrying is the splice this class exists to prevent), the writer goes
        quiet instead: every later record is counted as dropped and nothing more
        is written. The damage stays one trailing line rather than cascading, and
        a short write means the disk is already failing, so there is nothing left
        to capture anyway.

        A lost record is COUNTED in :attr:`dropped` rather than logged --
        routing it through ``_telemetry``'s own logging would re-enter this
        exporter -- so the loss is still observable to anyone who asks.
        """
        if self._retired:
            self.dropped += 1
            return len(value)
        payload = value.encode("utf-8")
        try:
            if self._raw_write(payload) != len(payload):  # exactly once
                self.dropped += 1
                self._retired = True
        except Exception:  # noqa: BLE001 - capture is best-effort, never fatal
            self.dropped += 1
        return len(value)

    def flush(self) -> None:
        # The record is already in the kernel's hands. Do NOT FlushFileBuffers /
        # fsync per span -- that would put a disk round-trip on the COM seat.
        return

    def close(self) -> None:
        if self._handle is not None:
            import win32file

            win32file.CloseHandle(self._handle)
            self._handle = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None


def _jsonl_stream(path: Path) -> IO[str]:
    """Atomic-append writer for ``path``, falling back to a buffered append.

    Capture must never be the reason a build fails (or goes dark), so a seat
    without the Win32 extensions still gets its JSONL -- just without the
    interleaving guarantee.
    """
    try:
        return cast(IO[str], _AtomicJsonlWriter(path))
    except Exception:  # noqa: BLE001 - capture is best-effort, never fatal
        return path.open("a", encoding="utf-8")


def _close_jsonl_writer(out: Any, what: str) -> None:
    """Close an atomic writer, reporting anything it silently dropped.

    ``_AtomicJsonlWriter.write`` swallows a failed append so capture can never
    fail a build, but a silent drop would leave ``traces.jsonl`` quietly short
    with no way to tell that from a writer bug. Shutdown is the one moment it is
    safe to say so: straight to stderr, NOT through this module's own logging,
    which would re-enter the exporter being shut down.

    Reports at most ONCE. A COM build calls ``shutdown()`` explicitly, but the
    providers keep their default interpreter-exit callbacks, so each exporter is
    shut down again at ``atexit`` -- without the latch the same warning would
    print twice and read as two separate failures.
    """
    with contextlib.suppress(Exception):
        dropped = int(getattr(out, "dropped", 0) or 0)
        if dropped and not getattr(out, "_reported", False):
            out._reported = True
            sys.stderr.write(
                f"  !!  telemetry capture dropped {dropped} {what} record(s) "
                f"(disk or I/O failure); the .jsonl is incomplete\n"
            )
    with contextlib.suppress(Exception):
        out.close()


class _JsonlSpanExporter(ConsoleSpanExporter):
    """``ConsoleSpanExporter`` that closes its atomic writer on shutdown."""

    def shutdown(self) -> None:
        _close_jsonl_writer(self.out, "span")


class _JsonlLogRecordExporter(ConsoleLogRecordExporter):
    """``ConsoleLogRecordExporter`` that closes its atomic writer on shutdown."""

    def shutdown(self) -> None:
        _close_jsonl_writer(self.out, "log")


class _LiveStderr:
    """A write proxy that always targets the CURRENT ``sys.stderr``.

    The console handlers bind to this once (at ``configure`` time), but every
    write resolves ``sys.stderr`` afresh -- so when a caller swaps the stream
    AFTER import (e.g. ``cut_release``'s release-log ``_Tee``, installed once the
    run is under way), telemetry logs + span lines follow into the tee and land
    in the uploaded ``*-release.log``. A plain ``StreamHandler(stream=sys.stderr)``
    would capture the original object and bypass the tee, dropping the very
    progress/summary lines the old ``print()`` calls used to leave there.
    """

    def write(self, s: str) -> int:
        return sys.stderr.write(s)

    def flush(self) -> None:
        with contextlib.suppress(Exception):
            sys.stderr.flush()


# --------------------------------------------------------------------------- #
# OTLP export is BATCHED (console + .jsonl stay Simple).                       #
#                                                                              #
# Measured on this seat with the Aspire dashboard listening: the FIRST span     #
# export in a process costs ~2.0 s and the first log record another ~2.0 s      #
# (HTTP client construction, TLS/urllib3 import, connection setup); every       #
# subsequent one costs ~1 ms. With OTLP disabled both are ~0 ms. Under a        #
# SimpleSpanProcessor that ~4 s is paid ON the calling thread -- in a build     #
# subprocess, while it HOLDS the COM seat, once per process. Across ~110 COM    #
# tasks that is minutes of a full build spent inside a telemetry client.        #
#                                                                              #
# A Batch processor hands export to a background thread, so the cost leaves the #
# critical path entirely. The trade is that queued records are lost if the      #
# process dies without flushing -- covered on both exit paths we have:          #
# ``_common.run_build`` calls :func:`shutdown` after the build session closes,  #
# and the watchdog flushes before its ``os._exit``. Console and file capture    #
# deliberately stay on Simple processors: the console must stay live and        #
# ``traces.jsonl``/``logs.jsonl`` must never lose a record to a queue.          #
# --------------------------------------------------------------------------- #


def _otlp_span_processor():
    """``BatchSpanProcessor`` around the OTLP span exporter, or ``None``."""
    with contextlib.suppress(Exception):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        return BatchSpanProcessor(OTLPSpanExporter())
    return None


def _otlp_log_processor():
    """``BatchLogRecordProcessor`` around the OTLP log exporter, or ``None``."""
    with contextlib.suppress(Exception):
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        return BatchLogRecordProcessor(OTLPLogExporter())
    return None


def configure(*, console: bool = True, force: bool = False) -> None:
    """Wire up the trace + log providers. Idempotent; safe to call from import.

    ``console`` toggles the human-readable stderr stream (and the compact span
    tracer). File capture under ``cad/out/reports/telemetry`` is always attempted
    (best-effort).
    """
    global _configured
    if _configured and not force:
        return
    _configured = True

    if force:
        # OTel installs the global trace/log providers behind a one-shot ``Once``
        # guard: a second ``set_*_provider`` merely warns ("Overriding ... not
        # allowed") and keeps the FIRST provider. A forced reconfigure exists to
        # SWAP the resource (``set_service`` relabelling this process's stage after
        # import), so reset those guards or the rebuilt providers would be installed
        # nowhere and the relabel would silently no-op. Private-API + best-effort: if
        # OTel's internals move we simply keep the existing resource (telemetry must
        # never break a build), and the primary path -- dodo setting OTEL_SERVICE_NAME
        # in the child env BEFORE import, so the FIRST configure is already correct --
        # never needs this at all.
        with contextlib.suppress(Exception):
            trace._TRACER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]
        with contextlib.suppress(Exception):
            from opentelemetry._logs import _internal as _logs_internal

            _logs_internal._LOGGER_PROVIDER_SET_ONCE._done = False  # type: ignore[attr-defined]

    want_console = console

    # Resolve the OTLP target ONCE (probes the Aspire default if no env is set)
    # and pin it into the environment so the OTLP exporters read it AND every
    # build subprocess inherits the same decision via inject_env -- the parent
    # pays the reachability probe, children don't re-probe.
    otlp_endpoint = _resolve_otlp_endpoint()
    if otlp_endpoint:
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", otlp_endpoint)

    resource = Resource.create(
        {
            "service.name": _service_name,
            "service.namespace": _SERVICE_NAMESPACE,
            "service.version": os.environ.get("HARMONIC_VERSION", "dev"),
        }
    )

    # ---- traces -------------------------------------------------------- #
    # Built ONCE and kept, because the build-infra provider (a second resource in this
    # same process) reuses these exact processor objects rather than opening its own
    # console stream and traces.jsonl handle.
    global _span_processors
    _span_processors = []
    if want_console:
        _span_processors.append(
            SimpleSpanProcessor(
                ConsoleSpanExporter(
                    # _LiveStderr is a write/flush proxy (duck-typed IO) that
                    # re-resolves sys.stderr per write; the stub wants a concrete IO.
                    out=cast(IO[str], _LiveStderr()),
                    formatter=_compact_span,
                )
            )
        )
    tdir = _telemetry_dir()
    if tdir is not None:
        with contextlib.suppress(Exception):
            traces = _jsonl_stream(tdir / "traces.jsonl")
            _span_processors.append(
                SimpleSpanProcessor(
                    _JsonlSpanExporter(
                        out=traces, formatter=lambda s: s.to_json(indent=None) + "\n"
                    )
                )
            )
    if otlp_endpoint:
        processor = _otlp_span_processor()
        if processor is not None:
            _span_processors.append(processor)

    tracer_provider = TracerProvider(resource=resource)
    for processor in _span_processors:
        tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)
    # A relabelled process must not keep serving spans from providers built on the OLD
    # resource, so the auxiliary ones are rebuilt lazily against the new processors.
    _aux_providers.clear()

    # ---- logs ---------------------------------------------------------- #
    logger_provider = LoggerProvider(resource=resource)
    if tdir is not None:
        with contextlib.suppress(Exception):
            logs = _jsonl_stream(tdir / "logs.jsonl")
            logger_provider.add_log_record_processor(
                SimpleLogRecordProcessor(
                    _JsonlLogRecordExporter(
                        out=logs, formatter=lambda r: r.to_json(indent=None) + "\n"
                    )
                )
            )
    if otlp_endpoint:
        processor = _otlp_log_processor()
        if processor is not None:
            logger_provider.add_log_record_processor(processor)
    set_logger_provider(logger_provider)

    pylog = logging.getLogger(_LOGGER_NAME)
    pylog.setLevel(logging.DEBUG)
    pylog.handlers.clear()
    pylog.filters.clear()
    pylog.addFilter(_ActivityFilter())
    pylog.propagate = False
    # Bridge into OTel's logs SDK: carries SeverityNumber + the active span's
    # trace/span id onto every record, so logs and traces correlate.
    pylog.addHandler(LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider))
    if want_console:
        stream = logging.StreamHandler(stream=_LiveStderr())
        stream.setFormatter(_FriendlyFormatter())
        stream.setLevel(logging.DEBUG)
        pylog.addHandler(stream)


def get_logger() -> logging.Logger:
    configure()
    return logging.getLogger(_LOGGER_NAME)


def _provider_for_service(service: str):
    """A ``TracerProvider`` whose resource names ``service``, built lazily and cached.

    An OTel resource is fixed at provider creation, so a process that wants to emit
    some spans under a DIFFERENT ``service.name`` than its own stage needs a second
    provider -- there is no per-span resource. It shares this process's span
    processors (:data:`_span_processors`), so its spans ride the same console stream,
    ``traces.jsonl`` and OTLP exporter; only the resource differs. Context
    propagation is provider-independent, so a span from here still parents/nests
    exactly as usual."""
    configure()
    provider = _aux_providers.get(service)
    if provider is None:
        provider = TracerProvider(
            # No atexit hook: this provider does not OWN its processors (they are the
            # primary provider's), and letting it shut them down at exit would re-close
            # every exporter -- one "Exporter already shutdown" per extra resource.
            shutdown_on_exit=False,
            resource=Resource.create(
                {
                    "service.name": service,
                    "service.namespace": _SERVICE_NAMESPACE,
                    "service.version": os.environ.get("HARMONIC_VERSION", "dev"),
                }
            )
        )
        for processor in _span_processors:
            provider.add_span_processor(processor)
        _aux_providers[service] = provider
    return provider


def get_tracer(name: str = _SERVICE_NAME, *, service: str | None = None):
    """Tracer for this process's own resource, or for ``service`` (see
    :func:`_provider_for_service`) when spans must be attributed elsewhere."""
    configure()
    if service is None or service == _service_name:
        return trace.get_tracer(name)
    return _provider_for_service(service).get_tracer(name)


def set_service(name: str, *, force: bool = False) -> None:
    """Relabel this process's telemetry resource (``service.name``) to ``name``.

    The OTel ``Resource`` is fixed when the providers are created, so changing the
    service name REBUILDS them (``configure(force=True)``). Call it BEFORE the first
    span so every span in the process carries the new resource.

    FALLBACK-ONLY by default: it does nothing once the process already carries a
    NON-default label -- so a child that inherited a precise ``OTEL_SERVICE_NAME``
    from dodo (``_stage_name``) keeps it, and a coarse self-derived fallback from
    ``run_build`` never clobbers it. Pass ``force=True`` to relabel unconditionally.
    No-op when ``name`` is empty or already active. Best-effort: a reconfigure
    failure never propagates (telemetry must not break a build)."""
    global _service_name
    if not name or name == _service_name:
        return
    if not force and _service_name != _DEFAULT_SERVICE_NAME:
        return
    _service_name = name
    os.environ["OTEL_SERVICE_NAME"] = name
    with contextlib.suppress(Exception):
        configure(force=True)


# --------------------------------------------------------------------------- #
# Severity-levelled log helpers. Each emits one structured record (bridged to  #
# OTel + printed to the console) at its level. ``progress`` and ``success``    #
# keep the names the build scripts read most naturally.                        #
# --------------------------------------------------------------------------- #

def _extra(fields: Mapping[str, Any]) -> dict[str, Any] | None:
    """Flatten caller fields into log-record attributes (OTel attribute values
    must be primitives, so non-primitives are stringified)."""
    if not fields:
        return None
    safe: dict[str, Any] = {}
    for key, value in fields.items():
        safe[key] = value if isinstance(value, (str, bool, int, float)) else repr(value)
    return safe


def debug(message: str, **fields: Any) -> None:
    get_logger().debug(message, extra=_extra(fields))


def info(message: str, **fields: Any) -> None:
    get_logger().info(message, extra=_extra(fields))


def success(message: str, **fields: Any) -> None:
    get_logger().log(SUCCESS, message, extra=_extra(fields))


def warn(message: str, **fields: Any) -> None:
    get_logger().warning(message, extra=_extra(fields))


def error(message: str, *, exc_info: bool = False, **fields: Any) -> None:
    get_logger().error(message, exc_info=exc_info, extra=_extra(fields))


# Historical aliases so ``_common`` (and anything importing from it) stays a
# drop-in: ``progress`` == the old ``log()``, ``ok`` == a passing ``  OK  ``.
progress = debug
ok = success


def event(name: str, **attributes: Any) -> None:
    """Record a point-in-time OTel span EVENT on the CURRENT span (best-effort).

    Prefer this over a standalone log record for a moment that belongs to a span's
    timeline -- a cache hit/miss, a mate flip-recovery, a driver re-engagement --
    so the trace timeline shows *when within the span* it happened and carries its
    structured attributes, instead of the fact living only in a correlated but
    separate log stream. No-op when no span is recording, so a caller never has to
    guard; and swallows any error, since telemetry must never break a build."""
    with contextlib.suppress(Exception):
        span = trace.get_current_span()
        if span is not None and span.get_span_context().is_valid:
            span.add_event(name, attributes=_extra(attributes) or {})


def _enter_span(name: str, attributes: Mapping[str, Any] | None,
                service: str | None = None) -> tuple[Span, Any, int]:
    _touch_activity(f"span-start {name}")
    tracer = get_tracer(service=service)
    depth = _depth.get()
    attrs = {"harmonic.depth": depth}
    if attributes:
        attrs.update({k: v for k, v in attributes.items() if v is not None})
    # We own exception recording + status in ``_exit_span``; disable the
    # context manager's built-in handling so the exception isn't recorded twice.
    cm = tracer.start_as_current_span(
        name,
        attributes=attrs,
        record_exception=False,
        set_status_on_exception=False,
    )
    span = cm.__enter__()
    token = _depth.set(depth + 1)
    return span, (cm, token), depth


def _exit_span(handle: Any, exc: BaseException | None) -> None:
    cm, token = handle
    _depth.reset(token)
    span = trace.get_current_span()
    _touch_activity(f"span-end {getattr(span, 'name', '?')}")
    if exc is not None:
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
        error(f"{span.name if isinstance(span, ReadableSpan) else 'span'} failed: {exc}")
    elif cast(ReadableSpan, span).status.status_code is StatusCode.UNSET:
        # get_current_span() is typed Span (mutable, has set_status); only
        # ReadableSpan exposes .status -- the live SDK span is both.
        span.set_status(Status(StatusCode.OK))
    cm.__exit__(type(exc) if exc else None, exc, exc.__traceback__ if exc else None)


@contextlib.contextmanager
def span(name: str, /, *, service: str | None = None,
         **attributes: Any) -> Generator[Span, None, None]:
    """Span context manager that leaves no gaps.

    On a clean exit the span status is set OK; on an exception it records the
    exception, marks the span ERROR, emits an ERROR log, then re-raises — so a
    failure is always attributable to a span rather than vanishing.

    ``service`` attributes the span to another resource than this process's stage
    (:data:`BUILD_INFRA_SERVICE` for the COM seat queue and the artefact cache); it
    changes only the resource, never the parent/child shape.
    """
    sp, handle, _ = _enter_span(name, attributes, service)
    try:
        yield sp
    except BaseException as exc:  # noqa: BLE001 - recorded then re-raised
        _exit_span(handle, exc)
        raise
    else:
        _exit_span(handle, None)


@contextlib.asynccontextmanager
async def aspan(name: str, /, **attributes: Any) -> AsyncGenerator[Span, None]:
    """Async sibling of :func:`span` for ``async with`` build steps."""
    sp, handle, _ = _enter_span(name, attributes)
    try:
        yield sp
    except BaseException as exc:  # noqa: BLE001 - recorded then re-raised
        _exit_span(handle, exc)
        raise
    else:
        _exit_span(handle, None)


def traced(name: str, *, label_param: str | None = None):
    """Decorator that runs the wrapped function inside a span named ``name``.

    Works on both sync and async functions. ``label_param`` names a parameter
    whose value is copied onto the span as a ``label`` attribute (so e.g.
    ``define_circle(..., label="blank_od")`` traces as ``sketch.circle
    label=blank_od``). This is how the per-operation ``_common`` helpers turn a
    build into a tree of operation spans instead of one monolithic ``build`` span.
    """

    def deco(fn):
        sig = inspect.signature(fn) if label_param else None

        def _attrs(args, kwargs) -> dict[str, Any]:
            if sig is None:
                return {}
            try:
                bound = sig.bind_partial(*args, **kwargs)
                if label_param in bound.arguments:
                    return {"label": bound.arguments[label_param]}
            except Exception:  # noqa: BLE001 - tracing must never break the call
                pass
            return {}

        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def awrap(*args, **kwargs):
                async with aspan(name, **_attrs(args, kwargs)):
                    return await fn(*args, **kwargs)
            return awrap

        @functools.wraps(fn)
        def wrap(*args, **kwargs):
            with span(name, **_attrs(args, kwargs)):
                return fn(*args, **kwargs)
        return wrap

    return deco


@contextlib.contextmanager
def build_session(label: str, /, **attributes: Any) -> Generator[Span | None, None, None]:
    """Root context for a build *process* (``_common.run_build``).

    Under the doit spine a parent trace context is injected (``TRACEPARENT``), so
    this CONTINUES that trace: the build's operation spans attach directly to the
    doit task span and we yield ``None`` — no second ``build.<target>`` layer
    duplicating the task. Run standalone (no parent), it opens a local
    ``build.<target>`` root (``label`` is the part/assembly target, so a standalone
    trace title says WHICH part) so nothing is unparented, and yields that span so
    the caller can mark it ERROR on failure.
    """
    configure()
    parent = _parent_context_from_env()
    if parent is not None:
        token = otel_context.attach(parent)
        try:
            # Inside the attached parent context, so this process's spawn + import
            # cost is billed to the REMOTE task span that paid for it -- and before
            # any local span is opened, since a back-dated startup span parented
            # under a span that started later reads as a malformed waterfall.
            record_process_startup()
            yield None
        finally:
            otel_context.detach(token)
    else:
        record_process_startup()
        with span(f"build.{label}", label=label, **attributes) as root:
            yield root


_startup_recorded = False
# A stamp older than this is not our parent's -- it is a stale value inherited through
# some intermediate process -- so it is ignored rather than drawn as an absurd span.
_STARTUP_SANITY_S = 3600.0


def record_process_startup() -> None:
    """Account for the DARK region between a parent spawning this process and the
    first span this process opens: process creation, interpreter boot, and the whole
    import graph. Measured at ~2-5 s per COM task on the SolidWorks seat -- so a
    ``task part:<stem>`` span that read 36 s had ~5 s of it unexplained, sitting
    between the task span's start and ``sw.connect``.

    Emitted as ``proc.startup`` with two children -- ``proc.launch`` (spawn +
    interpreter, up to the moment THIS module was imported) and ``proc.import`` (the
    rest of the import graph and the entry preamble) -- so the split between "Windows
    made a process" and "python read our code" is visible rather than inferred.

    The timestamps are all in the past, which is precisely the case OTel's
    creation-time ``start_time`` argument exists for ("SHOULD only be set when span
    creation time has already passed"): nothing here mutates a live span. Call it
    once the parent's trace context is attached, so the spans land in the parent's
    trace; a second call, or a process no parent stamped (a standalone run), is a
    no-op. Best-effort -- never raises."""
    global _startup_recorded
    if _startup_recorded:
        return
    _startup_recorded = True
    with contextlib.suppress(Exception):
        raw = os.environ.get(SPAWN_ENV)
        if not raw:
            return
        spawn_ns = int(raw)
        now = time.time_ns()
        if not 0 < now - spawn_ns < _STARTUP_SANITY_S * 1e9:
            return  # clock skew, or a stale value inherited from a grandparent
        tracer = get_tracer()
        depth = _depth.get()
        parent = tracer.start_span(
            "proc.startup", start_time=spawn_ns,
            attributes={"harmonic.depth": depth, "pid": os.getpid()})
        parent.set_status(Status(StatusCode.OK))
        child_ctx = trace.set_span_in_context(parent)
        for name, start, end in (("proc.launch", spawn_ns, _IMPORT_NS),
                                 ("proc.import", _IMPORT_NS, now)):
            child = tracer.start_span(name, context=child_ctx, start_time=start,
                                      attributes={"harmonic.depth": depth + 1})
            child.set_status(Status(StatusCode.OK))
            child.end(end_time=end)
        parent.end(end_time=now)


def inject_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a copy of ``env`` (default ``os.environ``) with the active span's
    W3C trace context injected (``TRACEPARENT`` / ``TRACESTATE``), ready to hand
    to a subprocess so its root span continues this trace instead of starting a
    detached one. Best-effort: returns the env unchanged if injection fails.

    Also stamps :data:`SPAWN_ENV` with the launch instant, so the child can bill its
    own spawn + import cost to the trace (:func:`record_process_startup`) instead of
    leaving a dark gap before its first span. Stamped HERE, the one chokepoint every
    subprocess launch already goes through, so a new launcher gets it for free."""
    out = dict(env if env is not None else os.environ)
    out[SPAWN_ENV] = str(time.time_ns())
    with contextlib.suppress(Exception):
        carrier: dict[str, str] = {}
        inject(carrier)
        # propagators emit lowercase header names; subprocess env convention is
        # the upper-case TRACEPARENT/TRACESTATE pair.
        if "traceparent" in carrier:
            out["TRACEPARENT"] = carrier["traceparent"]
        if carrier.get("tracestate"):
            out["TRACESTATE"] = carrier["tracestate"]
    return out


def _parent_context_from_env() -> Any | None:
    """Extract a remote parent context from ``TRACEPARENT`` if a parent process
    injected one (see :func:`inject_env`); ``None`` when running standalone."""
    traceparent = os.environ.get("TRACEPARENT")
    if not traceparent:
        return None
    with contextlib.suppress(Exception):
        carrier = {"traceparent": traceparent}
        if os.environ.get("TRACESTATE"):
            carrier["tracestate"] = os.environ["TRACESTATE"]
        return extract(carrier)
    return None


@contextlib.contextmanager
def run_pipeline_span(stage: str, /, **attributes: Any) -> Generator[Span, None, None]:
    """Root span for a whole process invocation (a build script, a doit action,
    a verify suite). Opening this first guarantees every later span has a parent
    — the outermost wrapper that closes the last gap in the trace.

    If a parent process injected a trace context into the environment (the doit
    spine does, via :func:`inject_env`), the root span continues that remote
    trace, so the doit task and the build subprocess it spawns share one
    end-to-end trace with no gap at the process boundary."""
    configure()
    parent = _parent_context_from_env()
    token = otel_context.attach(parent) if parent is not None else None
    try:
        # Before the pipeline span: ``proc.startup`` is back-dated to the spawn
        # instant, which precedes this span's start, so nesting it here would make a
        # child that begins before its parent (codex #424).
        record_process_startup()
        with span(f"pipeline.{stage}", **attributes) as sp:
            yield sp
    finally:
        if token is not None:
            otel_context.detach(token)


def shutdown() -> None:
    """Flush + close providers (force-flush exporters). Best-effort.

    Covers BOTH signals: OTLP export is batched (see the block above
    :func:`_otlp_span_processor`), so anything still queued -- spans AND log records
    -- is only delivered because this runs. It is the reason the batch trade is safe:
    ``_common.run_build`` calls this after the build session closes, and the watchdog
    calls it before ``os._exit``.

    The auxiliary per-resource providers (build-infra) are deliberately NOT shut down:
    they hold the primary provider's processors, not their own, so this one call
    already closes every exporter -- and shutting them down too would just re-close
    each exporter and log "Exporter already shutdown" for every extra resource."""
    with contextlib.suppress(Exception):
        trace.get_tracer_provider().shutdown()  # type: ignore[attr-defined]
    with contextlib.suppress(Exception):
        get_logger_provider().shutdown()  # type: ignore[attr-defined]


# Preconfigure on import: a script that merely ``import _telemetry`` (directly
# or transitively through ``_common``) gets console logging + tracing with no
# setup call. Mirrors "preconfigure console logging".
configure()

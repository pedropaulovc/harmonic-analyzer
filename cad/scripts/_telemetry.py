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
import threading
import time
import urllib.parse
from collections.abc import AsyncGenerator, Generator, Mapping
from pathlib import Path
from typing import IO, Any, cast

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
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


def _resolve_service_name() -> str:
    return os.environ.get("OTEL_SERVICE_NAME") or _DEFAULT_SERVICE_NAME


_service_name = _resolve_service_name()

# Project default: ship OTLP to a local **.NET Aspire dashboard** (standalone
# image's OTLP/HTTP port) with zero env. So `doit ...` / a build script lights up
# the dashboard's traces+logs the moment it's running -- no OTEL_* exports needed.
# Override or disable with OTEL_EXPORTER_OTLP_ENDPOINT (set it empty to turn off).
_DEFAULT_OTLP_ENDPOINT = "http://localhost:18890"


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
    default, but only when it is actually listening.
    """
    env = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if env is not None:
        return env or None
    return (
        _DEFAULT_OTLP_ENDPOINT if _endpoint_listening(_DEFAULT_OTLP_ENDPOINT) else None
    )


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
_depth: contextvars.ContextVar[int] = contextvars.ContextVar(
    "_telemetry_depth", default=0
)

_configured = False
_tracer_provider: TracerProvider | None = None
_logger_provider: LoggerProvider | None = None
_shutdown_provider_ids: set[int] = set()
_shutdown_lock = threading.Lock()


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
    dur = (
        (span.end_time - span.start_time) / 1e9
        if span.end_time and span.start_time
        else 0.0
    )
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


def configure(*, console: bool = True, force: bool = False) -> None:
    """Wire up the trace + log providers. Idempotent; safe to call from import.

    ``console`` toggles the human-readable stderr stream (and the compact span
    tracer). File capture under ``cad/out/reports/telemetry`` is always attempted
    (best-effort).
    """
    global _configured, _logger_provider, _tracer_provider
    if _configured and not force:
        return

    # A forced resource swap replaces both process-global providers. Drain the
    # old pair first: otherwise their exporter threads and JSONL handles survive
    # until interpreter shutdown, and short-lived ``set_service(force=True)``
    # callers can lose the records queued immediately before the swap.
    if force:
        _shutdown_current_providers()
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
    tracer_provider = TracerProvider(resource=resource)
    if want_console:
        tracer_provider.add_span_processor(
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
            traces = (tdir / "traces.jsonl").open("a", encoding="utf-8")
            tracer_provider.add_span_processor(
                SimpleSpanProcessor(
                    ConsoleSpanExporter(
                        out=traces, formatter=lambda s: s.to_json(indent=None) + "\n"
                    )
                )
            )
    # OTLP export to the resolved endpoint (Aspire dashboard by default, see
    # _resolve_otlp_endpoint). Keep the human console and local JSONL processors
    # synchronous, but batch the network exporter: one synchronous HTTP request
    # at the first log AND first span otherwise adds ~4 s to every short-lived
    # build process when Aspire is listening. ``run_build`` closes its root span
    # before calling shutdown(), which drains this queue without losing the tail.
    if otlp_endpoint:
        with contextlib.suppress(Exception):
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)
    _tracer_provider = tracer_provider

    # ---- logs ---------------------------------------------------------- #
    logger_provider = LoggerProvider(resource=resource)
    if tdir is not None:
        with contextlib.suppress(Exception):
            logs = (tdir / "logs.jsonl").open("a", encoding="utf-8")
            logger_provider.add_log_record_processor(
                SimpleLogRecordProcessor(
                    ConsoleLogRecordExporter(
                        out=logs, formatter=lambda r: r.to_json(indent=None) + "\n"
                    )
                )
            )
    if otlp_endpoint:
        with contextlib.suppress(Exception):
            from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                OTLPLogExporter,
            )

            logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(OTLPLogExporter())
            )
    set_logger_provider(logger_provider)
    _logger_provider = logger_provider

    pylog = logging.getLogger(_LOGGER_NAME)
    pylog.setLevel(logging.DEBUG)
    pylog.handlers.clear()
    pylog.filters.clear()
    pylog.addFilter(_ActivityFilter())
    pylog.propagate = False
    # Bridge into OTel's logs SDK: carries SeverityNumber + the active span's
    # trace/span id onto every record, so logs and traces correlate.
    pylog.addHandler(
        LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)
    )
    if want_console:
        stream = logging.StreamHandler(stream=_LiveStderr())
        stream.setFormatter(_FriendlyFormatter())
        stream.setLevel(logging.DEBUG)
        pylog.addHandler(stream)


def get_logger() -> logging.Logger:
    configure()
    return logging.getLogger(_LOGGER_NAME)


def get_tracer(name: str = _SERVICE_NAME):
    configure()
    return trace.get_tracer(name)


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


def _enter_span(
    name: str, attributes: Mapping[str, Any] | None
) -> tuple[Span, Any, int]:
    _touch_activity(f"span-start {name}")
    tracer = get_tracer()
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
        error(
            f"{span.name if isinstance(span, ReadableSpan) else 'span'} failed: {exc}"
        )
    elif cast(ReadableSpan, span).status.status_code is StatusCode.UNSET:
        # get_current_span() is typed Span (mutable, has set_status); only
        # ReadableSpan exposes .status -- the live SDK span is both.
        span.set_status(Status(StatusCode.OK))
    cm.__exit__(type(exc) if exc else None, exc, exc.__traceback__ if exc else None)


@contextlib.contextmanager
def span(name: str, /, **attributes: Any) -> Generator[Span, None, None]:
    """Span context manager that leaves no gaps.

    On a clean exit the span status is set OK; on an exception it records the
    exception, marks the span ERROR, emits an ERROR log, then re-raises — so a
    failure is always attributable to a span rather than vanishing.
    """
    sp, handle, _ = _enter_span(name, attributes)
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
def build_session(
    label: str, /, **attributes: Any
) -> Generator[Span | None, None, None]:
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
            yield None
        finally:
            otel_context.detach(token)
    else:
        with span(f"build.{label}", label=label, **attributes) as root:
            yield root


def inject_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a copy of ``env`` (default ``os.environ``) with the active span's
    W3C trace context injected (``TRACEPARENT`` / ``TRACESTATE``), ready to hand
    to a subprocess so its root span continues this trace instead of starting a
    detached one. Best-effort: returns the env unchanged if injection fails."""
    out = dict(env if env is not None else os.environ)
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
        with span(f"pipeline.{stage}", **attributes) as sp:
            yield sp
    finally:
        if token is not None:
            otel_context.detach(token)


def _shutdown_provider(provider: TracerProvider | LoggerProvider) -> None:
    with contextlib.suppress(Exception):
        provider.shutdown()


def _shutdown_current_providers() -> None:
    """Drain the current trace/log providers once, in parallel.

    Traces and logs have independent OTLP/HTTP exporters. Letting one provider
    finish before starting the other serializes their network latency at every
    process exit; two threads overlap those independent drains. Provider-level
    shutdown already force-flushes batch processors and unregisters each SDK
    provider's own atexit hook.
    """
    providers = [
        provider for provider in (_tracer_provider, _logger_provider) if provider
    ]
    with _shutdown_lock:
        pending = [
            provider
            for provider in providers
            if id(provider) not in _shutdown_provider_ids
        ]
        _shutdown_provider_ids.update(id(provider) for provider in pending)

    if not pending:
        return
    if len(pending) == 1:
        _shutdown_provider(pending[0])
        return

    workers = [
        threading.Thread(
            target=_shutdown_provider,
            args=(provider,),
            name=f"otel-shutdown-{type(provider).__name__}",
        )
        for provider in pending
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()


def shutdown() -> None:
    """Flush + close both signal providers exactly once. Best-effort."""
    _shutdown_current_providers()


# Preconfigure on import: a script that merely ``import _telemetry`` (directly
# or transitively through ``_common``) gets console logging + tracing with no
# setup call. Mirrors "preconfigure console logging".
configure()

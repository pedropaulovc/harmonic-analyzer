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
import sys
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import (
    ConsoleLogRecordExporter,
    SimpleLogRecordProcessor,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    ReadableSpan,
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

_T0 = time.perf_counter()
_LAST_TICK = _T0

# Span nesting depth for the compact console tracer, so the boundary lines
# indent into a tree and a missing parent is visible at a glance.
_depth: contextvars.ContextVar[int] = contextvars.ContextVar("_telemetry_depth", default=0)

_configured = False


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
    depth = int((span.attributes or {}).get("harmonic.depth", 0))
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
    tracer); set ``HARMONIC_OTEL_QUIET=1`` to suppress them in CI scrapes. File
    capture under ``cad/out/reports/telemetry`` is always attempted (best-effort).
    """
    global _configured
    if _configured and not force:
        return
    _configured = True

    quiet = os.environ.get("HARMONIC_OTEL_QUIET") == "1"
    want_console = console and not quiet

    resource = Resource.create(
        {
            "service.name": _SERVICE_NAME,
            "service.version": os.environ.get("HARMONIC_VERSION", "dev"),
        }
    )

    # ---- traces -------------------------------------------------------- #
    tracer_provider = TracerProvider(resource=resource)
    if want_console:
        tracer_provider.add_span_processor(
            SimpleSpanProcessor(
                ConsoleSpanExporter(out=_LiveStderr(), formatter=_compact_span)
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
    trace.set_tracer_provider(tracer_provider)

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
    set_logger_provider(logger_provider)

    pylog = logging.getLogger(_LOGGER_NAME)
    pylog.setLevel(logging.DEBUG)
    pylog.handlers.clear()
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


def get_tracer(name: str = _SERVICE_NAME):
    configure()
    return trace.get_tracer(name)


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


def _enter_span(name: str, attributes: Mapping[str, Any] | None) -> tuple[Span, Any, int]:
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
    if exc is not None:
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))
        error(f"{span.name if isinstance(span, ReadableSpan) else 'span'} failed: {exc}")
    elif span.status.status_code is StatusCode.UNSET:
        span.set_status(Status(StatusCode.OK))
    cm.__exit__(type(exc) if exc else None, exc, exc.__traceback__ if exc else None)


@contextlib.contextmanager
def span(name: str, /, **attributes: Any) -> Iterator[Span]:
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
async def aspan(name: str, /, **attributes: Any) -> Any:
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
def build_session(label: str, /, **attributes: Any) -> Iterator[Span | None]:
    """Root context for a build *process* (``_common.run_build``).

    Under the doit spine a parent trace context is injected (``TRACEPARENT``), so
    this CONTINUES that trace: the build's operation spans attach directly to the
    doit task span and we yield ``None`` — no second ``pipeline.part.build`` layer
    duplicating the task. Run standalone (no parent), it opens a local
    ``pipeline.part.build`` root so nothing is unparented, and yields that span so
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
        with span("pipeline.part.build", label=label, **attributes) as root:
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
def run_pipeline_span(stage: str, /, **attributes: Any) -> Iterator[Span]:
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


def shutdown() -> None:
    """Flush + close providers (force-flush exporters). Best-effort."""
    with contextlib.suppress(Exception):
        trace.get_tracer_provider().shutdown()  # type: ignore[attr-defined]


# Preconfigure on import: a script that merely ``import _telemetry`` (directly
# or transitively through ``_common``) gets console logging + tracing with no
# setup call. Mirrors "preconfigure console logging".
configure()

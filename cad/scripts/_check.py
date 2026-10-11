"""Adapter result checks and progress logging.

Separate module so edits affect only recipes that use this scope.
"""

from __future__ import annotations

from typing import Any

import _telemetry  # observability spine: console logging + tracing, preconfigured


def log(message: str) -> None:
    """Timestamped progress line, now an OpenTelemetry DEBUG record.

    Kept as a thin alias over :func:`_telemetry.progress` so the ~170 scripts
    importing ``log`` from here are instrumented unchanged: the record is
    bridged into OTel (correlated to the active span) and rendered to the
    console with the historical ``  ..  [stamp] message`` styling.
    """
    _telemetry.progress(message)


def check(label: str, result: Any) -> Any:
    """Raise when an adapter result is not success; return ``result.data``.

    A failure raises inside the active span, where :func:`_telemetry.span`
    records it (ERROR status + exception event); success emits an OTel SUCCESS
    record (the historical ``  OK  `` line).
    """
    if not result.is_success:
        raise RuntimeError(f"{label} failed: {result.error}")
    _telemetry.success(label)
    return result.data

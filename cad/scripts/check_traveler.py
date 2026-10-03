"""Run the real pinned prechips traveler with CAD-gate exit semantics.

A shop/process error is advisory here, not approval to machine. Bad input is a
broken CAD/consumer contract and remains fatal. Reports retain original verdicts.
"""

from __future__ import annotations

import logging
import sys

from prechips import cli, telemetry

import _telemetry


class _AdvisoryFindings(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Keep the ✗ glyph and structured error verdict; only gate log severity
        # changes. BadInput has no finding status and must stay an error.
        if getattr(record, "status", None) == "error":
            record.levelno = logging.WARNING
            record.levelname = "WARNING"
        return True


def main(argv: list[str] | None = None) -> int:
    tracing = telemetry.configure("traveler")
    _telemetry.capture_external_spans(tracing.trace_provider)
    advisory = _AdvisoryFindings()
    tracing.logger.addFilter(advisory)
    try:
        code = cli.main(["traveler", *(sys.argv[1:] if argv is None else argv)])
    finally:
        tracing.logger.removeFilter(advisory)
    if code == 2:
        _telemetry.warn(
            "Traveler has machining blockers; CAD gate is advisory. "
            "Read report.json and traveler.html before machining."
        )
    return 0 if code in (0, 2, 4) else code


if __name__ == "__main__":
    raise SystemExit(main())

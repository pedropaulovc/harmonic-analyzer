"""Record or replay one build's COM conversation.

``record <script> --log P [--summary P] [--out-root DIR] [--callers MODE]``
    Run a build script against the live seat exactly as ``python <script>``
    would (``run_build``: connect, discard, template pin, teardown), recording
    its build window into ``P``. ``--summary`` writes the recording's facts as
    JSON for dodo. ``--out-root`` redirects the outputs (side-by-side
    diagnostic runs only; dodo's part builds never pass it). ``--callers``
    keeps the Python caller of every call (``full``), none (``divergence``: a
    replay names its own at a divergence) or none at all (``off``). Exits with
    the build's own exit code, or 92 when the recorder itself failed: the
    recording is unusable and dodo re-runs the build once unrecorded.

``replay <script> --log P --scratch DIR --result P [--base-outputs DIR] [--capture-dir DIR]``
    Run the script with SolidWorks absent, serving the log: no live COM, no
    write outside DIR (bar the temporary and telemetry directories), no
    connection beyond loopback, no OTLP export. ``--base-outputs`` compares the
    Python-written outputs with that output root, file by file. Exits 0 for a
    no-op verdict, 91 for any other verdict, 1 for an infrastructure failure.

``diff <a> <b> [--result P]``
    Request divergence and per-member response differences between two logs
    (JSON on stdout); exit 0 when the recipe requests are identical.

dodo records every part build through ``record`` and evaluates the shadow
replay through ``replay`` and ``diff`` (``_replay_shadow``). Nothing here is
imported by a recipe; ``--help`` imports neither pywin32 nor the build modules.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SUMMARY_SCHEMA = 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="com_replay.py",
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="run a build on the live seat, recorded")
    record.add_argument("script", type=Path)
    record.add_argument("--log", type=Path, required=True)
    record.add_argument("--summary", type=Path, help="write the recording's facts")
    record.add_argument("--out-root", type=Path, help="redirect the build's outputs")
    record.add_argument(
        "--callers",
        choices=("off", "divergence", "full"),
        help="Python caller capture per recorded call (default: the engine's)",
    )

    replay = sub.add_parser("replay", help="replay a log with SolidWorks absent")
    replay.add_argument("script", type=Path)
    replay.add_argument("--log", type=Path, required=True)
    replay.add_argument("--scratch", type=Path, required=True)
    replay.add_argument("--result", type=Path, required=True)
    replay.add_argument(
        "--base-outputs",
        type=Path,
        help="output root the Python-written outputs are compared with",
    )
    replay.add_argument(
        "--capture-dir",
        type=Path,
        help="SolidWorks-written files of the log (default: beside the log)",
    )

    diff = sub.add_parser("diff", help="request/response comparison of two logs")
    diff.add_argument("base", type=Path)
    diff.add_argument("new", type=Path)
    diff.add_argument("--result", type=Path)
    return parser


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def _offline_telemetry() -> None:
    """A replay exports no OTLP: the sandbox refuses non-loopback sockets, and
    a replay is not a build. Spans and logs still reach the local files."""
    for name in list(os.environ):
        if name.startswith("OTEL_EXPORTER_OTLP_") and name.endswith("_ENDPOINT"):
            del os.environ[name]
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = ""


def _summary(
    conversation: Any,
    timing: dict[str, Any] | None,
    faults: list[dict[str, str]],
    exit_code: int,
) -> dict[str, Any]:
    """What dodo publishes and measures about one recorded build."""
    timing = timing or {}
    trailer = timing.get("trailer") or {}
    calls = trailer.get("calls")
    inert = trailer.get("inert_calls")
    audit = trailer.get("escape_audit") or {}
    return {
        "schema": SUMMARY_SCHEMA,
        "exit_code": exit_code,
        "rc": timing.get("rc"),
        "faults": faults,
        "engine": conversation.sha256_file(conversation.ENGINE_FILE),
        "script": timing.get("script"),
        "sw_revision": timing.get("sw_revision"),
        # The process inputs a replay must reproduce (check_inputs pins them).
        "environment": {
            key: os.environ.get(key) for key in conversation.ENVIRONMENT_KEYS
        },
        "complete": trailer.get("status") == "complete" and not faults,
        "outcome": trailer.get("outcome"),
        "calls": calls,
        "inert_calls": inert,
        "recipe_requests": calls - inert
        if isinstance(calls, int) and isinstance(inert, int)
        else None,
        "callers": trailer.get("callers"),
        "clock_seconds": trailer.get("clock_seconds"),
        "window_seconds": trailer.get("window_seconds"),
        "escape_audit_seconds": audit.get("seconds"),
        "script_seconds": timing.get("script_seconds"),
        "capture_bytes": trailer.get("capture_bytes"),
        "capture_stored_bytes": trailer.get("capture_stored_bytes"),
    }


def _record(args: argparse.Namespace, script: Path) -> int:
    # _telemetry is imported only once the build is over: until the script
    # imports it, this process is the build process, timed and labelled as one.
    import _com_conversation as conversation

    timing: dict[str, Any] | None = None
    propagated = False
    try:
        timing = conversation.record_build(
            script,
            args.log.resolve(),
            out_root=args.out_root.resolve() if args.out_root else None,
            callers=conversation.CallerCapture(args.callers)
            if args.callers
            else conversation.DEFAULT_CALLERS,
        )
    except conversation.RecordFault:
        propagated = True
    faults = conversation.record_faults()
    import _telemetry

    rc = timing["rc"] if timing is not None else 1
    exit_code = conversation.EXIT_RECORD_FAULT if faults else int(rc)
    if faults:
        first = faults[0]
        _telemetry.warn(
            f"[com-replay] recording fault in {first['where']} "
            f"({first['type']}: {first['message']}); this recording is unusable "
            f"and the build is re-run unrecorded (exit {exit_code})",
            where=first["where"],
            fault_type=first["type"],
            fault_count=len(faults),
        )
    if args.summary is not None:
        try:
            _write_json(args.summary, _summary(conversation, timing, faults, exit_code))
        except OSError as exc:
            # No summary means dodo publishes nothing; the build itself stands.
            _telemetry.warn(f"[com-replay] summary not written: {exc}")
    if propagated:
        # The fault unwound run_build before its own flush.
        _telemetry.shutdown()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "record":
        # The build's process as unrecorded but for the recorder: its streams
        # are left as they are (run_build reconfigures them itself), and only
        # the engine is loaded before the script runs.
        return _record(args, args.script.resolve())
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    if args.command == "replay":
        _offline_telemetry()

    import _com_conversation as conversation

    if args.command == "diff":
        payload = conversation.compare_conversations(args.base, args.new)
        if args.result is not None:
            _write_json(args.result, payload)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if payload["request_divergence"] is None:
            return 0
        return conversation.EXIT_REPLAY_NOT_NOOP

    script = args.script.resolve()

    import _telemetry

    # Telemetry creates cad/out/reports/telemetry on first use: do it before the
    # replay's audit hook starts refusing writes outside the scratch root.
    _telemetry.info(f"com_replay replay {script.name} <- {args.log}")
    result = conversation.replay_build(
        script,
        args.log.resolve(),
        args.scratch.resolve(),
        args.base_outputs.resolve() if args.base_outputs else None,
        capture_dir=args.capture_dir.resolve() if args.capture_dir else None,
    )
    _write_json(args.result, result.to_json())
    inert = result.details.get("inert") or {}
    summary = (
        f"replay {script.name}: {result.verdict.value} "
        f"({result.served}/{result.recorded} recipe requests served, inert "
        f"{inert.get('served', 0)}/{inert.get('recorded', 0)} served "
        f"{inert.get('unserved', 0)} unrecorded, {result.seconds:.2f}s)"
    )
    if result.verdict is conversation.Verdict.NOOP:
        _telemetry.success(summary)
    else:
        _telemetry.warn(f"{summary}: {result.details.get('reason')}")
    _telemetry.shutdown()
    if result.verdict is conversation.Verdict.NOOP:
        return 0
    return conversation.EXIT_REPLAY_NOT_NOOP


if __name__ == "__main__":
    sys.exit(main())

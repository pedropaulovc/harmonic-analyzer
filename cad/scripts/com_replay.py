"""Record or replay one build's COM conversation (EXPERIMENT BRANCH ONLY).

Branch ``experiment/com-replay-20261110``: never merge. Engine and design notes:
``_com_conversation.py``; the native benchmark that drives this CLI:
``diagnostics/benchmark_replay_noop.py``.

``record <script> --out-root DIR [--log P] [--timing P]``
    Run a part build script against the live seat (normal ``run_build``:
    connect, discard, template pin, teardown) with its outputs redirected to
    ``DIR``. With ``--log`` the build window is recorded; without it the window
    is only timed. Exits with the build's own exit code.

``replay <script> --log P --base-outputs DIR --scratch DIR --result P``
    Run the script with SolidWorks absent, serving the log. Exits 0 for a
    no-op verdict, 91 for any other verdict, 1 for an infrastructure failure.

``diff <a> <b> [--result P]``
    Request divergence and per-member response differences between two logs
    (JSON on stdout); exit 0 when the recipe requests are identical.

Nothing here is imported by a recipe; ``--help`` imports neither pywin32 nor
the build modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="com_replay.py",
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="run a build on the live seat")
    record.add_argument("script", type=Path)
    record.add_argument("--out-root", type=Path, required=True)
    record.add_argument("--log", type=Path, help="record the build window here")
    record.add_argument("--timing", type=Path, help="write window/script timing JSON")

    replay = sub.add_parser("replay", help="replay a log with SolidWorks absent")
    replay.add_argument("script", type=Path)
    replay.add_argument("--log", type=Path, required=True)
    replay.add_argument("--base-outputs", type=Path, required=True)
    replay.add_argument("--scratch", type=Path, required=True)
    replay.add_argument("--result", type=Path, required=True)
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    import _com_conversation as conversation
    import _telemetry

    if args.command == "diff":
        payload = conversation.compare_conversations(args.base, args.new)
        if args.result is not None:
            _write_json(args.result, payload)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        if payload["request_divergence"] is None:
            return 0
        return conversation.EXIT_REPLAY_NOT_NOOP

    script = args.script.resolve()
    if args.command == "record":
        _telemetry.info(f"com_replay record {script.name} -> {args.out_root}")
        timing = conversation.record_build(
            script, args.out_root.resolve(), args.log.resolve() if args.log else None
        )
        if args.timing is not None:
            _write_json(args.timing, timing)
        return int(timing["rc"])

    # Telemetry creates cad/out/reports/telemetry on first use: do it before the
    # replay's audit hook starts refusing writes outside the scratch root.
    _telemetry.info(f"com_replay replay {script.name} <- {args.log}")
    result = conversation.replay_build(
        script,
        args.log.resolve(),
        args.scratch.resolve(),
        args.base_outputs.resolve(),
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

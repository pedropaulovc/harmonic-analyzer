"""Run pinned prechips on generated HA inputs with strict exit propagation.

The default traveler command requires complete HTML/PNG outputs after exit 0.
``--check`` validates inputs in isolated scratch output, without verifying
traveler completeness or modifying a full traveler generation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from prechips import cli, kernel, telemetry

import _telemetry
import _process_plans


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stem")
    parser.add_argument("--out", type=Path, default=_process_plans.CAD_OUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate inputs in .check scratch; preserve the full traveler outputs",
    )
    args = parser.parse_args(argv)
    verb = "check" if args.check else "traveler"
    _telemetry.set_service("prechips-traveler")
    tracing = telemetry.configure(verb)
    _telemetry.capture_external_telemetry(tracing.trace_provider, tracing.log_provider)
    with _telemetry.run_pipeline_span("prechips_traveler", stem=args.stem) as root:
        directory = _process_plans.traveler_dir(args.stem, args.out)
        if args.check:
            directory /= ".check"
        try:
            with _telemetry.span("prechips.bind", stem=args.stem):
                # A failed bind or consumer run must not retain an old certificate.
                (directory / "report.json").unlink(missing_ok=True)
                if not args.check:
                    (directory / "traveler.html").unlink(missing_ok=True)
                if args.check:
                    inventory, policy, cutting_data = _process_plans.bind_shop(
                        args.out, directory=directory / "_shop"
                    )
                    plan = _process_plans.bind_plan(
                        args.stem, args.out, destination=directory / "plan.toml"
                    )
                else:
                    inventory, policy, cutting_data = _process_plans.bind_shop(args.out)
                    plan = _process_plans.bind_plan(args.stem, args.out)
        except _process_plans.PlanBindError as exc:
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(f"prechips: {exc}")
            return 3
        _telemetry.info(f"prechips kernel: {kernel.discover_kernel()}")
        code = cli.main(
            [
                verb,
                str(plan),
                "--inventory",
                str(inventory),
                "--policy",
                str(policy),
                "--cutting-data",
                str(cutting_data),
                "--out",
                str(directory),
            ]
        )
        if code != 0:
            exc = RuntimeError(f"prechips {verb} exited with code {code}")
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(str(exc))
        elif not args.check:
            try:
                with _telemetry.span("prechips.verify", stem=args.stem):
                    _process_plans.bind_traveler_html(args.stem, args.out)
                    _process_plans.verify_traveler(args.stem, args.out)
            except _process_plans.TravelerIncomplete as exc:
                root.record_exception(exc)
                root.set_status(
                    _telemetry.Status(_telemetry.StatusCode.ERROR, str(exc))
                )
                _telemetry.error(f"prechips: {exc}")
                return 1
        return code


if __name__ == "__main__":
    raise SystemExit(main())

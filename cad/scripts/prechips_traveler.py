"""Run pinned prechips on generated HA inputs with strict exit propagation.

The default traveler command requires complete HTML/PNG outputs after exit 0.
``--check`` validates inputs only, without verifying traveler completeness.
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
        help="validate inputs only; do not produce or verify traveler HTML/PNGs",
    )
    args = parser.parse_args(argv)
    verb = "check" if args.check else "traveler"
    _telemetry.set_service("prechips-traveler")
    tracing = telemetry.configure(verb)
    _telemetry.capture_external_telemetry(tracing.trace_provider, tracing.log_provider)
    try:
        inventory, policy, cutting_data = _process_plans.bind_shop(args.out)
        plan = _process_plans.bind_plan(args.stem, args.out)
    except _process_plans.PlanBindError as exc:
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
            str(_process_plans.traveler_dir(args.stem, args.out)),
        ]
    )
    if code == 0 and not args.check:
        try:
            _process_plans.verify_traveler(args.stem, args.out)
        except _process_plans.TravelerIncomplete as exc:
            _telemetry.error(f"prechips: {exc}")
            return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())

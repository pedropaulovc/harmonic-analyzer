"""Render one enrolled part's travelers with the installed prechips CLI.

Runs ``python -m prechips traveler cad/process/<stem>/plan.toml --profile P
--out cad/out/travelers/<stem>/<file>`` once per ``_process_plans.TRAVELER_PROFILES``
entry: ``traveler.html`` under the strict ``pro`` profile, then
``traveler-hobby.html`` under ``hobby`` (with its setup pictures). Only exit 0
from both is success. Every previous traveler is removed first, and a refusal
from either run removes both files and returns that run's exit code, so a
refusal never leaves stale or half-paired HTML behind.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import _telemetry
import _process_plans


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stem")
    parser.add_argument("--out", type=Path, default=_process_plans.CAD_OUT)
    args = parser.parse_args(argv)
    _telemetry.set_service("prechips-traveler")
    with _telemetry.run_pipeline_span("prechips_traveler", stem=args.stem) as root:
        plan = _process_plans.plan_path(args.stem)
        paths = _process_plans.traveler_paths(args.stem, args.out)
        for path in paths:
            path.unlink(missing_ok=True)
        if not plan.is_file():
            exc = FileNotFoundError(f"{args.stem}: no process plan at {plan}")
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(f"prechips: {exc}")
            return 2
        paths[0].parent.mkdir(parents=True, exist_ok=True)
        for profile, html in zip(_process_plans.TRAVELER_PROFILES.values(), paths, strict=True):
            cmd = [
                sys.executable, "-m", "prechips", "traveler", str(plan),
                "--profile", profile, "--out", str(html),
            ]
            with _telemetry.span("prechips.traveler", stem=args.stem, profile=profile):
                code = subprocess.run(cmd, env=_telemetry.inject_env(), check=False).returncode
            if code != 0:
                for path in paths:
                    path.unlink(missing_ok=True)
                exc = RuntimeError(f"prechips traveler --profile {profile} exited with code {code}")
                root.record_exception(exc)
                root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
                _telemetry.error(f"{args.stem}: {exc}")
                return code
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

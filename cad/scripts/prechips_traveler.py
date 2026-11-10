"""Render one enrolled part's traveler with the installed prechips CLI.

Runs ``python -m prechips traveler cad/process/<stem>/plan.toml --profile pro
--out cad/out/travelers/<stem>/traveler.html`` and returns its exit code. Only
exit 0 is success; prechips writes nothing on refusal, and any previous
traveler is removed first so a refusal never leaves stale HTML behind. The
build always uses the strict built-in ``pro`` profile; ``--profile`` exists for
offline smoke runs of this wrapper.
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
    parser.add_argument("--profile", default="pro", help="prechips profile (default: pro)")
    args = parser.parse_args(argv)
    _telemetry.set_service("prechips-traveler")
    with _telemetry.run_pipeline_span("prechips_traveler", stem=args.stem) as root:
        plan = _process_plans.plan_path(args.stem)
        html = _process_plans.traveler_html(args.stem, args.out)
        html.unlink(missing_ok=True)
        if not plan.is_file():
            exc = FileNotFoundError(f"{args.stem}: no process plan at {plan}")
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(f"prechips: {exc}")
            return 2
        html.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, "-m", "prechips", "traveler", str(plan),
            "--profile", args.profile, "--out", str(html),
        ]
        with _telemetry.span("prechips.traveler", stem=args.stem):
            code = subprocess.run(cmd, env=_telemetry.inject_env(), check=False).returncode
        if code != 0:
            html.unlink(missing_ok=True)
            exc = RuntimeError(f"prechips traveler exited with code {code}")
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(f"{args.stem}: {exc}")
        return code


if __name__ == "__main__":
    raise SystemExit(main())

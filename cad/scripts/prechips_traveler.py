"""Render one enrolled part's travelers with the latest prechips release.

prechips is not an HA dependency while it stabilises (owner ruling 2026-11-11,
#2502): a locked prechips made every release change ``uv.lock`` and re-key
every machinist review. The wrapper runs it outside the project environment
with uv's tool runner, from PyPI:

1. ``uv tool run --from prechips@latest python -c <print version>`` resolves
   the newest release. ``@latest`` revalidates uv's cached index and ignores a
   ``uv tool install``-ed copy; a bare ``--from prechips`` would reuse either.
   The version is printed once and recorded on the spans as
   ``prechips.version``, so a sheet can be traced to its generator.
2. ``uv tool run --from prechips==<version> prechips traveler
   cad/process/<stem>/plan.toml --profile P --out cad/out/travelers/<stem>/<file>``
   runs once per ``_process_plans.TRAVELER_PROFILES`` entry, pinned to that
   version so both sheets come from the release just printed:
   ``traveler.html`` under the strict ``pro`` profile, then
   ``traveler-hobby.html`` under ``hobby`` (with its setup pictures).

Only exit 0 from both runs is success. Every previous traveler is removed
first, and a refusal from either run removes both files and returns that run's
exit code, so a refusal never leaves stale or half-paired HTML behind. A
missing ``uv`` or an unreachable PyPI fails with exit 1 before any sheet is
written.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

import _telemetry
import _process_plans

PACKAGE = "prechips"
_VERSION_PROBE = f"import importlib.metadata as m; print(m.version({PACKAGE!r}))"


def _uv() -> str:
    """The uv executable: the one running this process under ``uv run``, else PATH."""
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        raise RuntimeError("uv was not found on PATH; prechips runs with `uv tool run`")
    return uv


def latest_version(uv: str) -> str:
    """The newest prechips release on PyPI, resolved by ``uv tool run``."""
    cmd = [uv, "tool", "run", "--from", f"{PACKAGE}@latest", "python", "-c", _VERSION_PROBE]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    version = result.stdout.strip()
    if result.returncode != 0 or not version:
        raise RuntimeError(
            f"could not resolve the latest {PACKAGE} from PyPI with `uv tool run` "
            f"(exit {result.returncode}; network access to PyPI is required): "
            + (result.stderr.strip() or "no version printed")
        )
    return version


def traveler_command(uv: str, version: str, plan: Path, profile: str, html: Path) -> list[str]:
    return [
        uv, "tool", "run", "--from", f"{PACKAGE}=={version}", PACKAGE, "traveler",
        str(plan), "--profile", profile, "--out", str(html),
    ]


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
        try:
            uv = _uv()
            with _telemetry.span("prechips.resolve", stem=args.stem):
                version = latest_version(uv)
        except RuntimeError as exc:
            root.record_exception(exc)
            root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
            _telemetry.error(f"{args.stem}: {exc}")
            return 1
        root.set_attribute("prechips.version", version)
        print(f"{args.stem}: prechips {version} (latest PyPI release)", flush=True)
        paths[0].parent.mkdir(parents=True, exist_ok=True)
        for profile, html in zip(_process_plans.TRAVELER_PROFILES.values(), paths, strict=True):
            cmd = traveler_command(uv, version, plan, profile, html)
            with _telemetry.span("prechips.traveler", stem=args.stem, profile=profile) as sp:
                sp.set_attribute("prechips.version", version)
                code = subprocess.run(cmd, env=_telemetry.inject_env(), check=False).returncode
            if code != 0:
                for path in paths:
                    path.unlink(missing_ok=True)
                exc = RuntimeError(
                    f"prechips {version} traveler --profile {profile} exited with code {code}"
                )
                root.record_exception(exc)
                root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
                _telemetry.error(f"{args.stem}: {exc}")
                return code
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

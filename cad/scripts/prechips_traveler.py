"""Render one enrolled part's travelers with the latest prechips release.

prechips is not an HA dependency while it stabilises (owner ruling 2026-11-11,
#2502): a locked prechips made every release change ``uv.lock`` and re-key
every machinist review. The wrapper runs it outside the project environment
with uv's tool runner, from PyPI:

1. ``uv tool run --from prechips@latest python -c <print version>`` resolves
   the newest release. ``@latest`` revalidates uv's cached index and ignores a
   ``uv tool install``-ed copy; a bare ``--from prechips`` would reuse either.
   The version is logged once and recorded on the spans as
   ``prechips.version``, so a sheet can be traced to its generator.
2. ``uv tool run --from prechips==<version> prechips traveler
   cad/process/<stem>/plan.toml --profile P --out cad/out/travelers/<stem>/<file>``
   runs once per ``_process_plans.TRAVELER_PROFILES`` entry, pinned to that
   version so both sheets come from the release just logged:
   ``traveler.html`` under the strict ``pro`` profile, then
   ``traveler-hobby.html`` under ``hobby`` (with its setup pictures).

Only exit 0 from both runs is success. Every previous traveler is removed
first, and a refusal from either run removes both files and returns that run's
exit code (2 for a prechips refusal), so a refusal never leaves stale or
half-paired HTML behind. uv's own failures exit 1 instead: a missing ``uv`` or
an unreachable PyPI before any sheet is written, and a render whose ``uv tool
run`` failed before prechips ran (stderr carries uv's ``error:`` or ``×``
diagnostic, never prechips' ``prechips:`` prefix), so an infrastructure
failure is never read as a plan or shop-data refusal.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
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
    result = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )
    version = result.stdout.strip()
    if result.returncode != 0 or not version:
        raise RuntimeError(
            f"could not resolve the latest {PACKAGE} from PyPI with `uv tool run` "
            f"(exit {result.returncode}; network access to PyPI is required): "
            + (result.stderr.strip() or "no version printed")
        )
    return version


def uv_error(stderr: str) -> str | None:
    """uv's own diagnostic in a failed ``uv tool run``'s stderr, if any: uv
    prefixes its errors with ``error:`` (fetch, parse, install) or ``×``
    (resolution), while prechips prefixes its refusals with ``prechips:``."""
    for line in stderr.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("error:", "×")):
            return stripped
    return None


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
        _telemetry.info(f"{args.stem}: prechips {version} (latest PyPI release)", prechips_version=version)
        paths[0].parent.mkdir(parents=True, exist_ok=True)
        for profile, html in zip(_process_plans.TRAVELER_PROFILES.values(), paths, strict=True):
            cmd = traveler_command(uv, version, plan, profile, html)
            with _telemetry.span("prechips.traveler", stem=args.stem, profile=profile) as sp:
                sp.set_attribute("prechips.version", version)
                result = subprocess.run(
                    cmd, env=_telemetry.inject_env(), stderr=subprocess.PIPE,
                    encoding="utf-8", errors="replace", check=False,
                )
            code, stderr = result.returncode, result.stderr or ""
            # prechips' own refusal text still reaches the operator.
            sys.stderr.write(stderr)
            if code != 0:
                for path in paths:
                    path.unlink(missing_ok=True)
                diagnostic = uv_error(stderr)
                if diagnostic is not None:
                    exc = RuntimeError(
                        f"uv could not run prechips {version} for --profile {profile} "
                        f"(`uv tool run` exited {code}; not a prechips refusal): {diagnostic}"
                    )
                    code = 1
                else:
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

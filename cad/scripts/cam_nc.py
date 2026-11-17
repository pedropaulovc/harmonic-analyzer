"""Post one enrolled part's NC programs from its CAM recipe with headless FreeCAD.

``python cad/scripts/cam_nc.py <stem> [--out cad/out]``

1. Reads the part's exported feature bundle (``cad/out/features/<stem>/``:
   ``features.toml`` and the STEP it binds), ``cad/process/<stem>/plan.toml``
   and ``cad/process/shop.toml``, and has the recipe
   (``cad/process/<stem>/cam.py``) derive every number it needs from them.
2. Writes that context, the recipe's path and its programs to a JSON job spec
   in a fresh staging directory and runs ``freecadcmd`` on
   ``_freecad_cam_runtime.py``. FreeCAD imports the STEP, builds one CAM Job
   per program and posts each with its ``grbl`` post into the staging
   directory.
3. Checks every posted file against the recipe's ``expectations`` (``_gcode``):
   depths, hole positions, slot cutter-centre bounds, pass positions, steps
   and directions, spindle speeds, no rapid below the stock top and no feed
   move above it.
4. Moves the checked programs into ``cad/out/nc/<stem>/``, prints each
   program's cutting / air-at-feed / rapid minutes and writes them to
   ``cycle_times.json``, then writes ``manifest.json``: the SHA-256 of every
   input and output, the FreeCAD version and the post used.

Exit 0 only when every program posted and every check passed. Any failure
removes every output and exits 1, so a stale or unchecked program is never
left beside a manifest. FreeCAD (1.1 or later) is ``$HARMONIC_FREECAD`` or the
newest discovered install; the task fails loud when there is none.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
import uuid
from pathlib import Path
from typing import Any

import _cam_programs
import _gcode
import _process_plans
import _telemetry
from export_features import bundle_paths

FREECAD_ENV = "HARMONIC_FREECAD"
RESULT_MARKER = "FREECAD_CAM_RESULT "
STAGING_DIR = ".staging"
# The base bar's nine programs build and post in about 20 s; a hung FreeCAD
# must not hold the task forever.
FREECAD_TIMEOUT_S = 900


class FreeCadError(RuntimeError):
    """FreeCAD did not build and post the programs."""


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _version(path: str) -> tuple[int, ...]:
    match = re.search(r"FreeCAD (\d+)\.(\d+)", path)
    return (int(match.group(1)), int(match.group(2))) if match else (-1,)


def resolve_freecadcmd() -> Path:
    """``$HARMONIC_FREECAD`` (the ``freecadcmd`` executable) wins; otherwise the
    newest ``FreeCAD <version>`` install under the per-user or machine-wide
    Windows program directories, then ``freecadcmd`` on PATH."""
    override = os.environ.get(FREECAD_ENV)
    if override:
        if not Path(override).is_file():
            raise FreeCadError(f"freecadcmd not found at {override} (${FREECAD_ENV})")
        return Path(override)
    roots = [os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")]
    found = [
        exe
        for root in roots if root
        for exe in glob.glob(os.path.join(root, "Programs", "FreeCAD *", "bin", "freecadcmd.exe"))
        + glob.glob(os.path.join(root, "FreeCAD *", "bin", "freecadcmd.exe"))
    ]
    if found:
        return Path(max(found, key=_version))
    which = shutil.which("freecadcmd")
    if which:
        return Path(which)
    raise FreeCadError(f"no FreeCAD found; install FreeCAD 1.1 or set ${FREECAD_ENV} to freecadcmd")


def parse_result(output: str) -> dict[str, Any]:
    """The runtime's single result line. Its absence is a failure, never success:
    freecadcmd exits 0 even when its script raised."""
    lines = [line for line in output.splitlines() if line.startswith(RESULT_MARKER)]
    if len(lines) != 1:
        raise FreeCadError(f"FreeCAD printed {len(lines)} result lines (output tail: {output[-1500:]!r})")
    result = json.loads(lines[0].removeprefix(RESULT_MARKER))
    if "error" in result:
        raise FreeCadError(f"FreeCAD CAM failed:\n{result['error']}")
    return result


def run_freecad(recipe: Path, ctx: dict[str, Any], programs, staging: Path, freecadcmd: Path) -> dict[str, Any]:
    """Build and post ``programs`` in freecadcmd into ``staging``; return the
    runtime's result (posted files, FreeCAD version, post script). The full
    console output is kept in ``staging/freecadcmd.log``."""
    spec = staging / "spec.json"
    spec.write_text(json.dumps({
        "recipe": str(Path(recipe).resolve()),
        "ctx": ctx,
        "programs": [[name, list(keys)] for name, keys in programs],
        "out_dir": str(staging.resolve()),
        "marker": RESULT_MARKER,
    }), encoding="utf-8")
    completed = subprocess.run(
        [str(freecadcmd), str(_cam_programs.RUNTIME_PATH)],
        env={**os.environ, _cam_programs.SPEC_ENV: str(spec.resolve())},
        cwd=staging, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=FREECAD_TIMEOUT_S, check=False,
    )
    output = completed.stdout + completed.stderr
    (staging / "freecadcmd.log").write_text(output, encoding="utf-8")
    return parse_result(output)


def verify(expectations, directory: Path) -> list[_gcode.Finding]:
    """Run every expectation against its posted program."""
    findings: list[_gcode.Finding] = []
    programs: dict[str, _gcode.Program] = {}
    for program, check, kwargs in expectations:
        if program not in programs:
            programs[program] = _gcode.read_program(directory / f"{program}.nc")
        findings += getattr(_gcode, f"check_{check}")(programs[program], **kwargs)
    return findings


def cycle_times(expectations, directory: Path, rapid_mm_min: float = _gcode.RAPID_MM_MIN) -> dict[str, _gcode.CycleTime]:
    """Each program's cycle time, split at the stock top its ``air_feed``
    expectation names (every program must have exactly one)."""
    tops: dict[str, list[float]] = {}
    for program, check, kwargs in expectations:
        tops.setdefault(program, [])
        if check == "air_feed":
            tops[program].append(kwargs["z_top"])
    missing = sorted(name for name, found in tops.items() if len(found) != 1)
    if missing:
        raise ValueError(f"programs {missing} need exactly one air_feed expectation (their stock top)")
    return {
        name: _gcode.cycle_time(_gcode.read_program(directory / f"{name}.nc"), rapid_mm_min, found[0])
        for name, found in tops.items()
    }


def time_table(times: dict[str, _gcode.CycleTime]) -> str:
    rows = [(name, t.cutting, t.air, t.rapid, t.total) for name, t in times.items()]
    rows.append(("total", *(sum(row[i] for row in rows) for i in range(1, 5))))
    width = max(len(row[0]) for row in rows)
    lines = [f"{'program':<{width}}  cutting  air@feed    rapid    total  (min)"]
    lines += [f"{name:<{width}}  {c:7.2f}  {a:8.2f}  {r:7.2f}  {t:7.2f}" for name, c, a, r, t in rows]
    return "\n".join(lines)


def _load_toml(path: Path) -> dict[str, Any]:
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def _remove_outputs(directory: Path) -> None:
    """Every program, the cycle times and the manifest, whatever the recipe now
    declares: a broken or renamed recipe must not leave a previous run's NC behind."""
    for path in (*directory.glob("*.nc"), directory / _cam_programs.CYCLE_TIMES_NAME, directory / _cam_programs.MANIFEST_NAME):
        path.unlink(missing_ok=True)


def _fail(root, stem: str, exc: Exception, directory: Path) -> int:
    _remove_outputs(directory)
    root.record_exception(exc)
    root.set_status(_telemetry.Status(_telemetry.StatusCode.ERROR, str(exc)))
    _telemetry.error(f"{stem}: {exc}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stem", choices=_cam_programs.CAM_STEMS)
    parser.add_argument("--out", type=Path, default=_cam_programs.CAD_OUT)
    args = parser.parse_args(argv)
    _telemetry.set_service("cam-nc")
    stem = args.stem
    with _telemetry.run_pipeline_span("cam_nc", stem=stem) as root:
        directory = _cam_programs.nc_dir(stem, args.out)
        _remove_outputs(directory)
        # FreeCAD posts into a fresh staging directory; files reach ``directory``
        # only after every check passed.
        staging_root = directory / STAGING_DIR
        shutil.rmtree(staging_root, ignore_errors=True)
        staging = staging_root / uuid.uuid4().hex
        staging.mkdir(parents=True)
        recipe_path = _cam_programs.recipe_path(stem)
        features_path, step_path = bundle_paths(stem, args.out)
        plan_path = _process_plans.plan_path(stem)
        inputs = {
            "features": features_path, "step": step_path, "plan": plan_path,
            "shop": _process_plans.SHOP_PATH, "recipe": recipe_path, "runtime": _cam_programs.RUNTIME_PATH,
        }
        try:
            recipe = _cam_programs.load_recipe(stem)
            programs = [directory / f"{name}.nc" for name, _ops in recipe.PROGRAMS]
            times_path = directory / _cam_programs.CYCLE_TIMES_NAME
            manifest_path = directory / _cam_programs.MANIFEST_NAME
            missing = [str(p) for p in inputs.values() if not Path(p).is_file()]
            if missing:
                raise FileNotFoundError(f"missing inputs {missing}; run package:features:{stem} first")
            features = _load_toml(features_path)
            if features["step_sha256"] != sha256(step_path):
                raise ValueError(f"{step_path.name} does not match features.toml step_sha256")
            with _telemetry.span("cam.context", stem=stem):
                ctx = recipe.context(features, _load_toml(plan_path), _load_toml(_process_plans.SHOP_PATH), str(step_path.resolve()))
            with _telemetry.span("cam.freecad", stem=stem) as span:
                freecadcmd = resolve_freecadcmd()
                result = run_freecad(recipe_path, ctx, recipe.PROGRAMS, staging, freecadcmd)
                span.set_attribute("freecad.version", result["freecad_version"])
            posted = {Path(f).resolve() for f in result["files"]}
            expected = {(staging / p.name).resolve() for p in programs}
            if posted != expected:
                raise RuntimeError(f"FreeCAD posted {sorted(map(str, posted))}, expected {sorted(map(str, expected))}")
            with _telemetry.span("cam.verify", stem=stem) as span:
                checks = recipe.expectations(ctx)
                findings = verify(checks, staging)
                span.set_attribute("cam.checks", len(checks))
                span.set_attribute("cam.findings", len(findings))
            if findings:
                raise RuntimeError("posted G-code failed its checks:\n  " + "\n  ".join(map(str, findings)))
            times = cycle_times(checks, staging)
            for path in programs:
                os.replace(staging / path.name, path)
            times_path.write_text(json.dumps({
                "rapid_mm_min": _gcode.RAPID_MM_MIN,
                "programs": {name: {"cutting_min": t.cutting, "air_feed_min": t.air, "rapid_min": t.rapid, "total_min": t.total}
                             for name, t in times.items()},
                "total_min": sum(t.total for t in times.values()),
            }, indent=2) + "\n", encoding="utf-8")
            manifest = {
                "stem": stem,
                "freecad_version": result["freecad_version"],
                "post": {"file": Path(result["post"]).name, "sha256": sha256(Path(result["post"]))},
                "inputs": {name: {"path": Path(p).name, "sha256": sha256(Path(p))} for name, p in inputs.items()},
                "programs": {p.name: sha256(p) for p in programs},
                "cycle_times": sha256(times_path),
                "checks": len(checks),
            }
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 -- every failure must remove every output
            return _fail(root, stem, exc, directory)
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
        print(time_table(times), flush=True)
        _telemetry.info(f"{stem}: posted {len(programs)} programs, {len(checks)} checks passed (FreeCAD {result['freecad_version']})")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

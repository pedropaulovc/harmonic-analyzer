"""Post one enrolled part's NC programs from its CAM recipe with headless FreeCAD.

``python cad/scripts/cam_nc.py <stem> [--out cad/out]``

1. Reads the part's exported feature bundle (``cad/out/features/<stem>/``:
   ``features.toml`` and the STEP it binds), ``cad/process/<stem>/plan.toml``
   and the shop directory ``cad/process/shop/`` (merged), and has the recipe
   (``cad/process/<stem>/cam.py``) derive every number it needs from them.
   A family plan's recipe posts for every part at once: it is given each
   part's features, its reading of the plan (``_process_plans.part_view``)
   and its STEP path, each as a dict by the part's id in the plan.
2. Writes that context, the recipe's path and its programs to a JSON job spec
   in a fresh staging directory and runs ``freecadcmd`` on
   ``_freecad_cam_runtime.py``. FreeCAD imports the STEP, builds one CAM Job
   per program section (one tool; a section per hand-set spindle speed) and
   posts each program with its ``grbl`` post into the staging directory,
   joining sections at an operator comment and ``M0``.
3. Checks every posted file against the recipe's ``expectations`` (``_gcode``):
   depths, hole positions, slot cutter-centre bounds, pass positions, steps
   and directions, spindle speeds, no rapid below the stock top and no feed
   move above it.
4. Moves the checked programs into ``cad/out/nc/<stem>/``, logs each
   program's cutting / air-at-feed / rapid minutes and writes them to
   ``cycle_times.json``, then writes ``manifest.json``: the SHA-256 of every
   input and output, the FreeCAD version and the post file FreeCAD loaded.
   freecadcmd's console output stays in ``freecadcmd.log`` beside them.

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
import _shop_equipment
import _telemetry

FREECAD_ENV = "HARMONIC_FREECAD"
RESULT_MARKER = "FREECAD_CAM_RESULT "
STAGING_DIR = ".staging"
# The base bar's nine programs build and post in about 20 s; a hung FreeCAD
# must not hold the task forever.
FREECAD_TIMEOUT_S = 900
# The runtime uses FreeCAD 1.1's CAM API (Path.Tool.toolbit, Path.Post.Processor).
MIN_FREECAD = (1, 1)
# freecadcmd's console output, rewritten every run and kept after a failure.
LOG_NAME = "freecadcmd.log"


class FreeCadError(RuntimeError):
    """FreeCAD did not build and post the programs."""


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _path_version(path: str) -> tuple[int, ...]:
    match = re.search(r"FreeCAD (\d+)\.(\d+)", path)
    return (int(match.group(1)), int(match.group(2))) if match else (-1,)


def freecad_version(freecadcmd: Path) -> tuple[int, int]:
    """(major, minor) that ``freecadcmd --version`` reports ("FreeCAD 1.1.4 ...")."""
    try:
        out = subprocess.run([str(freecadcmd), "--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FreeCadError(f"{freecadcmd} --version failed: {exc}") from exc
    match = re.search(r"FreeCAD (\d+)\.(\d+)", out.stdout + out.stderr)
    if not match:
        raise FreeCadError(f"{freecadcmd} --version printed no FreeCAD version")
    return int(match.group(1)), int(match.group(2))


def resolve_freecadcmd() -> Path:
    """``$HARMONIC_FREECAD`` (the ``freecadcmd`` executable) wins; otherwise the
    newest ``FreeCAD <version>`` install under the per-user or machine-wide
    Windows program directories, then ``freecadcmd`` on PATH. The one chosen
    must report FreeCAD 1.1 or later: the runtime uses 1.1's CAM API."""
    override = os.environ.get(FREECAD_ENV)
    if override:
        if not Path(override).is_file():
            raise FreeCadError(f"freecadcmd not found at {override} (${FREECAD_ENV})")
        chosen = Path(override)
    else:
        roots = [os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", "")]
        found = [
            exe
            for root in roots if root
            for exe in glob.glob(os.path.join(root, "Programs", "FreeCAD *", "bin", "freecadcmd.exe"))
            + glob.glob(os.path.join(root, "FreeCAD *", "bin", "freecadcmd.exe"))
        ]
        which = shutil.which("freecadcmd")
        if found:
            chosen = Path(max(found, key=_path_version))
        elif which:
            chosen = Path(which)
        else:
            raise FreeCadError(f"no FreeCAD found; install FreeCAD 1.1 or set ${FREECAD_ENV} to freecadcmd")
    version = freecad_version(chosen)
    if version < MIN_FREECAD:
        raise FreeCadError(f"{chosen} is FreeCAD {version[0]}.{version[1]}; the CAM runtime needs {MIN_FREECAD[0]}.{MIN_FREECAD[1]}+")
    return chosen


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


def run_freecad(recipe: Path, ctx: dict[str, Any], programs, staging: Path, freecadcmd: Path, log: Path) -> dict[str, Any]:
    """Build and post ``programs`` in freecadcmd into ``staging``; return the
    runtime's result (posted files, FreeCAD version, post script). The full
    console output goes to ``log``, which outlives the staging directory."""
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
    log.write_text(output, encoding="utf-8")
    try:
        return parse_result(output)
    except FreeCadError as exc:
        raise FreeCadError(f"{exc}\n(full freecadcmd output: {log})") from exc


def _program(directory: Path, name: str, cache: dict[str, _gcode.Program]) -> _gcode.Program:
    """The posted program ``name``, or with ``NAME@k`` its ``k``-th tool section."""
    file, _, section = name.partition("@")
    if file not in cache:
        cache[file] = _gcode.read_program(directory / f"{file}.nc")
    return cache[file].tool_section(int(section)) if section else cache[file]


# Posted files known to pass a cutter over a vise jaw with less air than the
# shop floor (cad/config/shop-equipment cnc.jaw-clearance), by file name, each
# naming its issue. verify reports their jaw_clearance findings as known (a
# warning) instead of failing on them, and fails when a listed file no longer
# falls under the floor: its owner empties its entry once fixed. Nothing else
# exempts a file from the floor.
KNOWN_JAW_CLEARANCE_VIOLATIONS: dict[str, str] = {
    "CL01_face_b.nc": "#3607 (ch_channel_lever: 0.521 mm over the moving jaw); not to be run until fixed",
    "PG15_height.nc": "#3607 (pd_platen_guide: 0.521 mm over the fixed jaw); not to be run until fixed",
}


def jaw_clearance_min_mm() -> float:
    """The shop's least air between a cutter and a jaw or clamp it passes over."""
    return float(_shop_equipment.load()["cnc"]["jaw-clearance"]["jaw_clearance_min_mm"])


def verify(expectations, directory: Path, known: dict[str, str] | None = None) -> list[_gcode.Finding]:
    """Run every expectation against its posted program or tool section.

    Every ``keep_out`` check runs with the shop's jaw-clearance floor; a
    recipe's own ``clearance`` may raise it, not lower it. A listed file's
    (``known``, by default :data:`KNOWN_JAW_CLEARANCE_VIOLATIONS`)
    ``jaw_clearance`` findings are logged as known, not returned; a listed file
    the expectations check with no such finding is a finding itself."""
    known = KNOWN_JAW_CLEARANCE_VIOLATIONS if known is None else known
    floor = jaw_clearance_min_mm()
    findings: list[_gcode.Finding] = []
    cache: dict[str, _gcode.Program] = {}
    floored: set[str] = set()
    for program, check, kwargs in expectations:
        if check == "keep_out":
            own = kwargs.get("clearance", floor)
            if own < floor:
                raise ValueError(f"{program}: keep_out clearance {own} is under the shop floor {floor} mm")
            kwargs = {**kwargs, "clearance": own}
            floored.add(f"{program.partition('@')[0]}.nc")
        findings += getattr(_gcode, f"check_{check}")(_program(directory, program, cache), **kwargs)
    kept: list[_gcode.Finding] = []
    violating: set[str] = set()
    for finding in findings:
        file = finding.program.partition("@")[0]
        if finding.check == "jaw_clearance" and file in known:
            violating.add(file)
            _telemetry.warn(f"known jaw-clearance violation ({known[file]}): {finding}")
        else:
            kept.append(finding)
    for file in sorted((floored & known.keys()) - violating):
        kept.append(_gcode.Finding(
            file, "jaw_clearance",
            f"listed in cam_nc.KNOWN_JAW_CLEARANCE_VIOLATIONS ({known[file]}) but clears the floor: remove its entry",
        ))
    return kept


def cycle_times(expectations, directory: Path, rapid_mm_min: float = _gcode.RAPID_MM_MIN) -> dict[str, _gcode.CycleTime]:
    """Each posted file's cycle time, split at the stock top its ``air_feed``
    expectation names: exactly one for the whole file, or exactly one per tool
    section (``NAME@k``) of a file whose stock top drops between tools."""
    tops: dict[str, dict[str, list[float]]] = {}
    for program, check, kwargs in expectations:
        file, _, section = program.partition("@")
        found = tops.setdefault(file, {}).setdefault(section, [])
        if check == "air_feed":
            found.append(kwargs["z_top"])
    times = {}
    for file, by_section in tops.items():
        nc = _gcode.read_program(directory / f"{file}.nc")
        sections = nc.tool_sections()
        whole = by_section.get("", [])
        split = {key: found for key, found in by_section.items() if key}
        if len(whole) == 1 and not any(split.values()):
            times[file] = _gcode.cycle_time(nc, rapid_mm_min, whole[0])
        elif not whole and sorted(split) == sorted(str(k) for k in range(len(sections))) and all(len(f) == 1 for f in split.values()):
            parts = [_gcode.cycle_time(sections[int(key)], rapid_mm_min, found[0]) for key, found in split.items()]
            times[file] = _gcode.CycleTime(*(sum(getattr(p, field) for p in parts) for field in ("cutting", "air", "rapid")))
        else:
            raise ValueError(f"{file} needs exactly one air_feed expectation (its stock top), or one per tool section")
    return times


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
        inputs = _cam_programs.cam_inputs(stem, args.out)
        recipe_path, plan_path = inputs["recipe"], inputs["plan"]
        try:
            recipe = _cam_programs.load_recipe(stem)
            programs = [directory / f"{name}.nc" for name, _ops in recipe.PROGRAMS]
            times_path = directory / _cam_programs.CYCLE_TIMES_NAME
            manifest_path = directory / _cam_programs.MANIFEST_NAME
            missing = [str(p) for p in inputs.values() if not Path(p).is_file()]
            if missing:
                parts = " ".join(_process_plans.part_stems(stem))
                raise FileNotFoundError(f"missing inputs {missing}; run package:manifest:<part> (or fetch_features.py {parts}) first")
            plan = _load_toml(plan_path)
            family = _process_plans.family_parts(stem)
            bundles = {
                part_id: (inputs[f"features/{part}"], inputs[f"step/{part}"])
                for part_id, part in family.items()
            } or {"": (inputs["features"], inputs["step"])}
            features, steps = {}, {}
            for part_id, (features_path, step_path) in bundles.items():
                features[part_id] = _load_toml(features_path)
                if features[part_id]["step_sha256"] != sha256(step_path):
                    raise ValueError(f"{step_path.name} does not match its features.toml step_sha256")
                steps[part_id] = str(step_path.resolve())
            with _telemetry.span("cam.context", stem=stem):
                if family:
                    views = {part_id: _process_plans.part_view(plan, part_id) for part_id in family}
                    ctx = recipe.context(features, views, _process_plans.load_shop(), steps)
                else:
                    ctx = recipe.context(features[""], plan, _process_plans.load_shop(), steps[""])
            with _telemetry.span("cam.freecad", stem=stem) as span:
                freecadcmd = resolve_freecadcmd()
                result = run_freecad(recipe_path, ctx, recipe.PROGRAMS, staging, freecadcmd, directory / LOG_NAME)
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
            # Operator stops are not machine time; their counts go beside it.
            stops = {name: _gcode.read_program(staging / f"{name}.nc") for name in times}
            for path in programs:
                os.replace(staging / path.name, path)
            times_path.write_text(json.dumps({
                "rapid_mm_min": _gcode.RAPID_MM_MIN,
                "programs": {name: {"cutting_min": t.cutting, "air_feed_min": t.air, "rapid_min": t.rapid, "total_min": t.total,
                                    "tool_changes": len(stops[name].tool_changes), "pauses": len(stops[name].pauses)}
                             for name, t in times.items()},
                "total_min": sum(t.total for t in times.values()),
            }, indent=2) + "\n", encoding="utf-8")
            manifest = {
                "stem": stem,
                "freecad_version": result["freecad_version"],
                "post": {"file": result["post"], "sha256": sha256(Path(result["post"]))},
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
        for line in time_table(times).splitlines():
            _telemetry.info(line)
        _telemetry.info(f"{stem}: posted {len(programs)} programs, {len(checks)} checks passed (FreeCAD {result['freecad_version']})")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

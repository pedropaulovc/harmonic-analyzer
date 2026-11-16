"""Post one enrolled part's NC programs from its Fusion CAM recipe.

``python cad/scripts/fusion_cam.py <stem> [--out cad/out]``

1. Reads the part's exported feature bundle (``cad/out/features/<stem>/``:
   ``features.toml`` and the STEP it binds), ``cad/process/<stem>/plan.toml``
   and ``cad/process/shop.toml``, and has the recipe
   (``cad/process/<stem>/cam.py``) derive every number it needs from them.
2. Sends ``_fusion_cam_runtime.py``, the recipe and that context to a running
   Autodesk Fusion through its local MCP server (``_fusion_mcp``). Fusion
   imports the STEP into a new, unsaved document, builds the setups and
   toolpaths, posts one file per recipe program with the recipe's library post
   into a fresh staging directory, and closes the document without saving, on
   failure too.
3. Checks every posted file against the recipe's ``expectations`` (``_gcode``):
   depths, hole positions, slot cutter-centre bounds, pass positions, steps
   and directions, spindle speeds, and no rapid below the stock top.
4. Moves the checked programs into ``cad/out/nc/<stem>/`` and writes
   ``manifest.json`` beside them: the SHA-256 of every input and output, the
   Fusion version and the post used.

Exit 0 only when every program posted and every check passed. Any failure
removes every output and exits 1, so a stale or unchecked program is never
left beside a manifest. Fusion must be running with Preferences > General >
API > Fusion MCP Server enabled and no command dialog open.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import tomllib
import uuid
from pathlib import Path
from typing import Any

import _cam_programs
import _gcode
import _process_plans
import _telemetry
from _fusion_mcp import FusionError, FusionSession
from export_features import bundle_paths

# Fusion's MCP script runner silently skips a script containing any line longer
# than about 4096 characters: it reports success and prints nothing (Fusion
# 2704, measured 2026-11-16: 4000 ran, 4500 did not). The sources and context
# therefore travel as base64 in short lines, and compose_script refuses a long one.
MAX_SCRIPT_LINE = 4000
_CHUNK = 76
RESULT_MARKER = "FUSION_CAM_RESULT "
STAGING_DIR = ".staging"
_SCRIPT = '''
import base64
import json
import sys
import types

PAYLOAD = json.loads(base64.b64decode("".join([
{payload}
])).decode("utf-8"))


def _module(name, source):
    module = types.ModuleType(name)
    exec(compile(source, name + ".py", "exec"), module.__dict__)
    sys.modules[name] = module
    return module


def run(_context: str):
    import adsk.core
    app = adsk.core.Application.get()
    opened = app.documents.count
    try:
        rt = _module("_fusion_cam_runtime", PAYLOAD["runtime"])
        recipe = _module("cam_recipe", PAYLOAD["recipe"])
        ctx = PAYLOAD["ctx"]
        built = recipe.build(ctx, rt)
        post = rt.library_post(built["cam"], ctx["post"])
        files = [
            rt.post(built["cam"], [built["ops"][key] for key in keys], name, post, PAYLOAD["out_dir"], ctx["comment"])
            for name, keys in PAYLOAD["programs"]
        ]
        print(MARKER + json.dumps({{"fusion_version": app.version, "post": post, "files": files}}))
    finally:
        if app.documents.count > opened:
            app.activeDocument.close(False)


MARKER = {marker!r}
'''


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compose_script(recipe: Path, ctx: dict[str, Any], programs, out_dir: Path) -> str:
    payload = json.dumps({
        "runtime": _cam_programs.RUNTIME_PATH.read_text(encoding="utf-8"),
        "recipe": recipe.read_text(encoding="utf-8"),
        "ctx": ctx,
        "programs": [[name, list(keys)] for name, keys in programs],
        "out_dir": str(out_dir.resolve()),
    })
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    lines = ",\n".join(f'    "{encoded[i:i + _CHUNK]}"' for i in range(0, len(encoded), _CHUNK))
    script = _SCRIPT.format(payload=lines, marker=RESULT_MARKER)
    longest = max(len(line) for line in script.splitlines())
    if longest > MAX_SCRIPT_LINE:
        raise ValueError(f"script line of {longest} characters; Fusion would skip it silently")
    return script


def parse_result(output: str) -> dict[str, Any]:
    """The script's single result line. Its absence is a failure, never success:
    Fusion reports success with empty output for a script it did not run."""
    lines = [line for line in output.splitlines() if line.startswith(RESULT_MARKER)]
    if len(lines) != 1:
        raise FusionError(f"Fusion returned no result line (output: {output[-500:]!r})")
    return json.loads(lines[0].removeprefix(RESULT_MARKER))


def verify(expectations, directory: Path) -> list[_gcode.Finding]:
    """Run every expectation against its posted program."""
    findings: list[_gcode.Finding] = []
    programs: dict[str, _gcode.Program] = {}
    for program, check, kwargs in expectations:
        if program not in programs:
            programs[program] = _gcode.read_program(directory / f"{program}.nc")
        findings += getattr(_gcode, f"check_{check}")(programs[program], **kwargs)
    return findings


def _load_toml(path: Path) -> dict[str, Any]:
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def _remove_outputs(directory: Path) -> None:
    """Every program and the manifest, whatever the recipe now declares: a
    broken or renamed recipe must not leave a previous run's NC behind."""
    for path in (*directory.glob("*.nc"), directory / _cam_programs.MANIFEST_NAME):
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
    _telemetry.set_service("fusion-cam")
    stem = args.stem
    with _telemetry.run_pipeline_span("fusion_cam", stem=stem) as root:
        directory = _cam_programs.nc_dir(stem, args.out)
        _remove_outputs(directory)
        # Fusion posts into a fresh staging directory; files reach ``directory``
        # only after every check passed. A Fusion script still running after a
        # client timeout can therefore never drop unchecked files beside the
        # manifest, only into its own abandoned staging directory.
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
            outputs = (
                *(directory / f"{name}.nc" for name, _ops in recipe.PROGRAMS),
                directory / _cam_programs.MANIFEST_NAME,
            )
            missing = [str(p) for p in inputs.values() if not Path(p).is_file()]
            if missing:
                raise FileNotFoundError(f"missing inputs {missing}; run package:features:{stem} first")
            features = _load_toml(features_path)
            if features["step_sha256"] != sha256(step_path):
                raise ValueError(f"{step_path.name} does not match features.toml step_sha256")
            with _telemetry.span("cam.context", stem=stem):
                ctx = recipe.context(features, _load_toml(plan_path), _load_toml(_process_plans.SHOP_PATH), str(step_path.resolve()))
            with _telemetry.span("cam.fusion", stem=stem) as span:
                session = FusionSession()
                session.require_idle()
                reply = session.run_script(compose_script(recipe_path, ctx, recipe.PROGRAMS, staging))
                result = parse_result(reply)
                span.set_attribute("fusion.version", result["fusion_version"])
            posted = {Path(f).resolve() for f in result["files"]}
            expected = {(staging / p.name).resolve() for p in outputs[:-1]}
            if posted != expected:
                raise RuntimeError(f"Fusion posted {sorted(map(str, posted))}, expected {sorted(map(str, expected))}")
            with _telemetry.span("cam.verify", stem=stem) as span:
                checks = recipe.expectations(ctx)
                findings = verify(checks, staging)
                span.set_attribute("cam.checks", len(checks))
                span.set_attribute("cam.findings", len(findings))
            if findings:
                raise RuntimeError("posted G-code failed its checks:\n  " + "\n  ".join(map(str, findings)))
            for path in outputs[:-1]:
                os.replace(staging / path.name, path)
            manifest = {
                "stem": stem,
                "fusion_version": result["fusion_version"],
                "post": {"file": Path(result["post"]).name, "sha256": sha256(Path(result["post"]))},
                "inputs": {name: {"path": Path(p).name, "sha256": sha256(Path(p))} for name, p in inputs.items()},
                "programs": {p.name: sha256(p) for p in outputs[:-1]},
                "checks": len(checks),
            }
            outputs[-1].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 -- every failure must remove every output
            return _fail(root, stem, exc, directory)
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)
        _telemetry.info(f"{stem}: posted {len(outputs) - 1} programs, {len(checks)} checks passed (Fusion {result['fusion_version']})")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

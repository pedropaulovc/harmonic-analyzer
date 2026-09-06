"""Collect ABBA timings for pinned part-drawing recipes using current helpers.

Run with --baseline REF --candidate REF and one or more drawing registry names.
Only recipe Python comes from those revisions; imported helpers, specifications,
configuration, project templates and built source parts come from the current checkout. Timings
exclude loading recipes, closing documents and checking input fingerprints.
One ABBA block supports an observed paired timing difference, not a generalized
fleet speedup or conflict/failure probability estimate.

This runner supports trusted repository recipes using the OUTPUTS contract.
It redirects outputs before evaluating defaults and aliases, rejects direct
save/write calls, and checks produced artifacts. It is not a Python sandbox.
Assembly drawings require a dependency snapshot and are not supported here.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

import _telemetry  # noqa: E402
from _common import _early_bound, run_build  # noqa: E402
from _drawing_common import DrawingOutputs  # noqa: E402
from _drawing_registry import DRAWINGS_BY_NAME  # noqa: E402
from diagnostics.probe_drawing_attachments import file_digest  # noqa: E402

_OUTPUT_NAMES = {"OUTPUTS", "SLDDRW", "PDF", "PNG"}
_ORDER = ("baseline", "candidate", "candidate", "baseline")


def revision(ref):
    return subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    ).stdout.strip()


def redirected_tree(code, filename):
    """Replace the recipe's output assignments before any code executes."""
    tree = ast.parse(code, filename)
    declarations = 0
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        names = {
            part.id
            for target in targets
            for part in ast.walk(target)
            if isinstance(part, ast.Name)
        }
        if not names & _OUTPUT_NAMES:
            continue
        if not names <= _OUTPUT_NAMES:
            raise ValueError(f"mixed output declaration cannot be isolated: {names}")
        if len(targets) != 1:
            raise ValueError("chained output declarations cannot be isolated")
        target = targets[0]
        if not isinstance(target, ast.Name) and not (
            isinstance(target, (ast.Tuple, ast.List))
            and all(isinstance(part, ast.Name) for part in target.elts)
        ):
            raise ValueError("output declaration requires a name or flat name sequence")
        if node.value is None:
            raise ValueError("output declaration requires an assigned value")
        if "OUTPUTS" in names:
            declarations += 1
        if isinstance(target, ast.Name):
            value = ast.Subscript(
                ast.Name("_benchmark_paths", ast.Load()),
                ast.Constant(target.id),
                ast.Load(),
            )
        else:
            value = ast.Tuple(
                [
                    ast.Subscript(
                        ast.Name("_benchmark_paths", ast.Load()),
                        ast.Constant(part.id),
                        ast.Load(),
                    )
                    for part in target.elts
                ],
                ast.Load(),
            )
        node.value = ast.copy_location(value, node.value)
    if declarations != 1:
        raise ValueError(
            "benchmark requires exactly one module-level OUTPUTS declaration"
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "outputs":
            raise ValueError(
                "recipe bypasses OUTPUTS through a registry outputs mapping"
            )
        if not isinstance(node, ast.Call):
            continue
        name = (
            node.func.id
            if isinstance(node.func, ast.Name)
            else node.func.attr
            if isinstance(node.func, ast.Attribute)
            else ""
        )
        if name in {
            "Save",
            "Save3",
            "SaveAs",
            "SaveAs2",
            "SaveAs3",
            "save_drawing",
            "save_model",
            "write_text",
            "write_bytes",
            "open",
        }:
            raise ValueError(f"recipe bypasses managed drawing outputs: {name}")
    return ast.fix_missing_locations(tree)


def recipe_source(commit, target):
    return subprocess.run(
        ["git", "show", f"{commit}:cad/scripts/draw_{target}.py"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    ).stdout


def load_recipe(commit, target, directory):
    code = recipe_source(commit, target)
    source_path = directory / "recipe-source.py"
    tree = redirected_tree(code, str(source_path))
    source_path.write_text(code, encoding="utf-8")
    stem = DRAWINGS_BY_NAME[target].artifact_stem
    basename = f"{stem}-{directory.parent.name}-{directory.name}"
    outputs = DrawingOutputs(
        slddrw=directory / f"{basename}.SLDDRW",
        pdf=directory / f"{basename}.pdf",
        png=directory / f"{basename}.png",
    )
    module = types.ModuleType(
        f"benchmark_{target}_{directory.parent.name}_{directory.name}"
    )
    module.__file__ = str(source_path)
    module._benchmark_paths = {
        "OUTPUTS": outputs,
        "SLDDRW": outputs.slddrw,
        "PDF": outputs.pdf,
        "PNG": outputs.png,
    }
    sys.modules[module.__name__] = module
    exec(compile(tree, str(source_path), "exec"), module.__dict__)
    if module.OUTPUTS != outputs:
        raise RuntimeError("recipe rebound OUTPUTS after its redirected declaration")
    if Path(module.SOURCE).suffix.upper() != ".SLDPRT":
        raise ValueError(
            "benchmark supports part drawings only; assemblies need dependency snapshots"
        )
    return module


def helper_fingerprints():
    """Capture helper, config and project-template content, including dirty files."""
    files = set((ROOT / "cad/scripts").glob("*.py"))
    files.update((ROOT / "cad/config").rglob("*.yaml"))
    files.update((ROOT / "SolidworksMCP-python/src").rglob("*.py"))
    files.update(path for path in (ROOT / "cad/templates").rglob("*") if path.is_file())
    return {str(path.relative_to(ROOT)): file_digest(path) for path in sorted(files)}


def check_fingerprints(expected, actual, label):
    changed = sorted(
        key
        for key in expected.keys() | actual.keys()
        if expected.get(key) != actual.get(key)
    )
    if changed:
        raise RuntimeError(f"{label} changed during benchmark: {changed}")


def validate_artifacts(artifacts, outputs):
    expected = {"drawing": outputs.slddrw, "pdf": outputs.pdf, "png": outputs.png}
    if set(artifacts) != set(expected):
        raise RuntimeError(f"benchmark outputs incomplete: {artifacts}")
    for kind, path in artifacts.items():
        actual = Path(path).resolve()
        if actual != expected[kind].resolve():
            raise RuntimeError(f"unexpected benchmark {kind} path: {actual}")
        if not actual.is_file() or actual.stat().st_size == 0:
            raise RuntimeError(f"missing or empty benchmark artifact: {actual}")
    return {kind: str(path) for kind, path in artifacts.items()}


def close_documents(adapter):
    app = _early_bound(adapter.swApp, "ISldWorks")
    if not app.CloseAllDocuments(True) or app.GetFirstDocument() is not None:
        raise RuntimeError("SolidWorks documents did not close before benchmark trial")
    adapter.currentModel = None


async def benchmark(adapter, targets, baseline, candidate, output_root):
    output_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="abba-", dir=output_root))
    helper_inputs = helper_fingerprints()
    report = {
        "baseline": baseline,
        "candidate": candidate,
        "helper_revision": revision("HEAD"),
        "helper_fingerprints": helper_inputs,
        "order": _ORDER,
        "status": "running",
        "trials": [],
        "scope": "pinned part-drawing recipes with current helpers/specifications/built parts",
        "timing_scope": "observed paired recipe timings; not generalized fleet speedup or conflict probability",
    }
    report_path = run_dir / "measurements.json"

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    _telemetry.info(f"drawing recipe benchmark report: {report_path}")
    try:
        for target in targets:
            source = None
            source_hash = None
            for index, variant in enumerate(_ORDER):
                trial = {
                    "target": target,
                    "variant": variant,
                    "index": index,
                    "status": "running",
                }
                report["trials"].append(trial)
                checkpoint()
                started = None
                try:
                    check_fingerprints(
                        helper_inputs,
                        helper_fingerprints(),
                        "helpers/configuration/resources",
                    )
                    directory = run_dir / f"{target}-{index}-{variant}"
                    directory.mkdir()
                    module = load_recipe(
                        baseline if variant == "baseline" else candidate,
                        target,
                        directory,
                    )
                    current_source = Path(module.SOURCE).resolve(strict=True)
                    if source is None:
                        source, source_hash = (
                            current_source,
                            file_digest(current_source),
                        )
                    if source != current_source or source_hash != file_digest(
                        current_source
                    ):
                        raise RuntimeError(
                            f"{target}: recipe source part changed between trials"
                        )
                    trial.update(
                        source=str(source),
                        source_sha256=source_hash,
                        recipe_sha256=file_digest(directory / "recipe-source.py"),
                    )
                    close_documents(adapter)
                    started = time.perf_counter()
                    with _telemetry.span(
                        "drawing.recipe_benchmark",
                        target=target,
                        variant=variant,
                        index=index,
                    ):
                        artifacts = await module.build(adapter)
                    trial["seconds"] = round(time.perf_counter() - started, 6)
                    started = None
                    trial["artifacts"] = validate_artifacts(artifacts, module.OUTPUTS)
                    check_fingerprints(
                        helper_inputs,
                        helper_fingerprints(),
                        "helpers/configuration/resources",
                    )
                    if source_hash != file_digest(source):
                        raise RuntimeError(
                            f"{target}: source part changed during trial"
                        )
                    trial["status"] = "passed"
                except Exception as error:
                    trial.update(status="failed", error=str(error))
                    raise
                finally:
                    if started is not None:
                        trial["seconds"] = round(time.perf_counter() - started, 6)
                    checkpoint()
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        checkpoint()
    return {"measurements": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", choices=sorted(DRAWINGS_BY_NAME))
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/drawing-benchmarks"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    baseline, candidate = revision(args.baseline), revision(args.candidate)
    report_root = args.report_root.resolve()
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                *args.targets,
                "--baseline",
                baseline,
                "--candidate",
                candidate,
                "--report-root",
                str(report_root),
                "--worker",
            ],
            "drawing recipe A/B benchmark",
            log_stem="drawing-recipe-benchmark",
            com=True,
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError(
            "drawing benchmark worker requires the pipeline COM seat lock"
        )
    return run_build(
        lambda adapter: benchmark(
            adapter, args.targets, baseline, candidate, report_root
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())

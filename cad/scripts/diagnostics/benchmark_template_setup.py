"""Blank-sheet setup-only ABBA: current/prepared/prepared/current defaults.

No part is opened and no model views, dimensions or layout are created. Only
one-time preparation saves a DRWDOT; the four trial drawings are never saved
or exported. This measures setup, not end-to-end drawing speed or persistence.
Full-recipe acceptance in benchmark_template_defaults.py remains unchanged.
Requires reviewed frozen source and an exclusive existing-SolidWorks seat.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics import benchmark_template_defaults as defaults  # noqa: E402
from diagnostics._owned_native_documents import DocumentKind  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402


@contextmanager
def timed(row, key):
    started = time.perf_counter()
    try:
        yield
    finally:
        row[key] = time.perf_counter() - started


def blank_drawing_witness(adapter):
    """GetViews returns one array per sheet, with its sheet-view first."""
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if int(model.GetType()) != 3 or str(model.GetPathName()) != "":
        raise RuntimeError("setup trial must leave an unsaved drawing")
    drawing = _early_bound(model, "IDrawingDoc")
    sheets = tuple(drawing.GetViews() or ())
    if len(sheets) != 1 or len(tuple(sheets[0] or ())) != 1:
        raise RuntimeError("setup trial needs exactly one sheet and no model views")
    return {"kind": 3, "path": "", "sheet_count": 1, "model_view_count": 0}


async def setup_trial(adapter, spec, prepared, directory, row, checkpoint):
    if row["variant"] not in {"baseline", "candidate"}:
        raise ValueError("unknown setup-only variant")
    started = time.perf_counter()
    row.update(status="running", phase="setup")
    checkpoint()
    try:
        # The planned path establishes ownership only; this blank trial is never
        # saved. Native document inventory checks remain outside the inner timer.
        with adapter.ownership.creating_document(
            DocumentKind.DRAWING, directory / "unsaved.SLDDRW"
        ):
            with (
                timed(row, "setup_seconds"),
                _telemetry.span(
                    "diagnostic.template.setup_only", variant=row["variant"]
                ),
            ):
                if row["variant"] == "baseline":
                    defaults.common.new_project_drawing(
                        adapter, scale=spec.scale, decimals=spec.decimals
                    )
                if row["variant"] == "candidate":
                    defaults.inherited_drawing(adapter, Path(prepared["path"]), spec)
        row["phase"] = "defaults_witness"
        checkpoint()
        with timed(row, "witness_seconds"):
            row["blank"] = blank_drawing_witness(adapter)
            row["defaults"] = defaults.defaults_snapshot(adapter, spec)
            defaults.compare_exact(
                defaults.defaults_semantics(prepared["before"]),
                defaults.defaults_semantics(row["defaults"]),
                "setup-only complete inherited defaults",
            )
        row["status"] = "passed"
    except Exception as error:
        row.update(status="failed", error=repr(error), failed_phase=row["phase"])
        raise
    finally:
        row["phase"] = "cleanup"
        checkpoint()
        try:
            with timed(row, "cleanup_seconds"):
                await adapter.close_owned_documents()
        except Exception as error:
            row.update(status="failed", cleanup_error=repr(error))
            raise
        finally:
            row["phase"] = "finished"
            row["trial_elapsed_seconds"] = time.perf_counter() - started
            checkpoint()


async def benchmark(adapter, spec, report_root):
    report_root.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="template-setup-abba-", dir=report_root))
    adapter.ownership.register_directory(run_dir)
    original = defaults.common.PROJECT_DRWDOT.resolve(strict=True)
    adapter.ownership.register_source(original)
    immutable = defaults.immutable_hashes([original])
    inputs = defaults.runtime_fingerprints()
    report = {
        "status": "running",
        "scope": "blank_sheet_setup_only",
        "revision": defaults.recipes.revision("HEAD"),
        "spec": asdict(spec),
        "order": defaults.ORDER,
        "runtime_inputs": inputs,
        "immutable_inputs": immutable,
        "preparation": {},
        "trials": [],
        "timing_scope": "one-time template preparation includes its save/default checks/cleanup; each trial times only its inner setup helper, then defaults witness and cleanup separately; input/ownership guards are outside those inner timings",
        "claim_scope": "observed blank setup timings only; not end-to-end speedup, saved drawing equivalence or conflict probability",
    }
    report_path = run_dir / "measurements.json"

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    checkpoint()
    try:
        template_dir = run_dir / "template"
        template_dir.mkdir()
        adapter.ownership.register_directory(template_dir)
        prepared = await defaults.prepare_template(
            adapter, spec, template_dir, report["preparation"]
        )
        immutable[prepared["path"]] = prepared["sha256"]
        checkpoint()
        for index, variant in enumerate(defaults.ORDER):
            directory = run_dir / f"{index}-{variant}"
            directory.mkdir()
            adapter.ownership.register_directory(directory)
            row = {"index": index, "variant": variant, "status": "running"}
            report["trials"].append(row)
            checkpoint()
            try:
                if defaults.immutable_changes(immutable):
                    raise RuntimeError("setup-only template input changed before trial")
                defaults.recipes.check_fingerprints(
                    inputs, defaults.runtime_fingerprints(), "setup-only runtime inputs"
                )
                await setup_trial(adapter, spec, prepared, directory, row, checkpoint)
                row["immutable_changes_after_cleanup"] = defaults.immutable_changes(
                    immutable
                )
                if row["immutable_changes_after_cleanup"]:
                    raise RuntimeError("setup-only template input changed during trial")
                defaults.recipes.check_fingerprints(
                    inputs, defaults.runtime_fingerprints(), "setup-only runtime inputs"
                )
            except Exception as error:
                row.update(status="failed", trial_error=repr(error))
                raise
            finally:
                checkpoint()
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        report["immutable_input_changes"] = defaults.immutable_changes(immutable)
        if report["immutable_input_changes"]:
            report["status"] = "failed"
        checkpoint()
        if report["immutable_input_changes"]:
            raise RuntimeError("setup-only immutable templates changed; see report")
    return {"measurements": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scale", nargs=2, type=float, default=(2.0, 1.0))
    parser.add_argument("--decimals", type=int, choices=(2, 3), default=2)
    parser.add_argument(
        "--report-root", type=Path, default=ROOT / "cad/out/reports/template-defaults"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    spec = defaults.TemplateSpec(tuple(args.scale), args.decimals)
    require_owned_diagnostic_environment()
    if args.worker:
        from diagnostics._owned_native_documents import run_copy_diagnostic

        return run_copy_diagnostic(
            lambda adapter: benchmark(adapter, spec, args.report_root.resolve())
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--scale",
            *map(str, spec.scale),
            "--decimals",
            str(spec.decimals),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "blank drawing template setup ABBA",
        log_stem="template-setup-abba",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Owned normal/canonical blank pairs for every registered recipe TemplateSpec.

One prepared base per precision, shared by all requested scales. Each pair uses
the production factory, exact raw/default/viewport/printed checks and one owned
native save/cold reopen. No part opens, production outputs, fallback or retries.
Blank linked expressions are checked; populated model-title acceptance remains
the existing full-recipe pilot/fleet gate, not a claim of this control.
"""

import argparse
from dataclasses import asdict
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _buildgraph import module_deps_of  # noqa: E402
from _drawing_registry import DRAWINGS  # noqa: E402
from diagnostics import probe_prepared_template_cache as cache  # noqa: E402
from diagnostics._recipe_template_factory import DrawingFactory, RecipeTemplateFactory  # noqa: E402


def registered_specs():
    return tuple(
        sorted(
            {
                importlib.import_module(row.script.stem).TEMPLATE_SPEC
                for row in DRAWINGS
            },
            key=lambda spec: (spec.decimals, spec.scale),
        )
    )


def runtime_inputs(adapter, specs):
    entries = {Path(__file__).resolve(), *(row.script.resolve() for row in DRAWINGS)}
    sources = set(entries)
    for entry in entries:
        sources.update(Path(path) for path in module_deps_of(entry))
    return {
        "specs": [asdict(spec) for spec in specs],
        "base_inputs": {
            str(precision): cache.runtime_inputs(
                adapter, cache.prepared.TemplateSpec(decimals=precision)
            )
            for precision in sorted({spec.decimals for spec in specs})
        },
        "diagnostic_and_recipe_sources": {
            path.relative_to(ROOT).as_posix(): cache.prepared._sha(path)
            for path in sorted(sources)
        },
    }


async def probe(adapter, report_root, expected_pid):
    cache.require_environment(expected_pid)
    if int(adapter.swApp.GetProcessID()) != expected_pid:
        raise RuntimeError("canonical-scale native PID differs from approved PID")
    specs = registered_specs()
    if not specs:
        raise RuntimeError("canonical-scale control needs registered recipe specs")
    pinned = runtime_inputs(adapter, specs)
    original = cache.sheet_setup.PROJECT_DRWDOT.resolve(strict=True)
    original_hash = cache.prepared._sha(original)
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(
        tempfile.mkdtemp(prefix="canonical-template-scales-", dir=report_root)
    )
    adapter.ownership.register_directory(directory)
    adapter.ownership.register_source(original)
    report_path = directory / "measurements.json"
    controller = RecipeTemplateFactory(DrawingFactory.PREPARED)
    report = {
        "status": "running",
        "phase": "starting",
        "expected_pid": expected_pid,
        "revision": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "source_template": {"path": str(original), "sha256": original_hash},
        "runtime_inputs": pinned,
        "specs": [asdict(spec) for spec in specs],
        "preparations": [],
        "pairs": [],
        "guards": [],
        "scope": "all registered blank scales; exact normal/canonical raw/default/viewport/printed and saved cold comparisons; not populated title or full recipe acceptance",
        "timing_scope": "per-base accessor, per-instance factory, witness, viewport, print/save/cold and full control elapsed are separate; no end-to-end recipe speedup claim",
    }
    entries, native_files, errors = {}, {}, []
    started = time.perf_counter()

    def checkpoint():
        report_path.write_text(
            json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
        )

    def guard(phase):
        row = {"phase": phase}
        report["guards"].append(row)
        try:
            with cache.timed(row, "seconds"):
                if (
                    runtime_inputs(adapter, specs) != pinned
                    or registered_specs() != specs
                ):
                    raise RuntimeError(
                        "canonical-scale frozen runtime or recipe specs changed"
                    )
                if cache.prepared._sha(original) != original_hash:
                    raise RuntimeError("canonical-scale original template changed")
                row["native_files"] = {
                    path: cache.prepared._sha(path) for path in native_files
                }
                if row["native_files"] != native_files:
                    raise RuntimeError("canonical-scale saved blank bytes changed")
                failures = controller.final_guards()
                if failures:
                    raise ExceptionGroup(
                        "canonical-scale cached artifact guard failed", failures
                    )
                adapter.ownership.inventory()
            row["status"] = "passed"
        except Exception as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            checkpoint()

    async def run_trial(spec, variant, parent, entry=None, normal=None):
        target = parent / variant
        target.mkdir()
        adapter.ownership.register_directory(target)
        row = {"variant": variant}
        report["pairs"][-1][variant] = row
        try:
            await cache.trial(
                adapter,
                spec,
                entry,
                target,
                row,
                normal["defaults"] if normal else None,
                checkpoint,
                printed_format=cache.PrintedFormat.COMPARE,
                printed_expected=normal["printed"] if normal else None,
                viewport=cache.Viewport.CAPTURED,
                captured_viewport=normal["viewport"] if normal else None,
                round_trip=cache.RoundTrip.SAVE_REOPEN,
            )
            if normal:
                row["paired_cold_comparison"] = "running"
                cache.compare_defaults(
                    normal["cold"]["defaults"], row["cold"]["defaults"]
                )
                cache.compare_printed(normal["cold"]["printed"], row["cold"]["printed"])
                row["paired_cold_comparison"] = "passed"
            return row
        except Exception as error:
            if row.get("paired_cold_comparison") == "running":
                row.update(
                    status="failed", paired_cold_comparison="failed", error=repr(error)
                )
            raise
        finally:
            cold = row.get("cold", {})
            if "sha256_before" in cold:
                native_files[cold["saved_path"]] = cold["sha256_before"]
            checkpoint()

    checkpoint()
    try:
        for index, spec in enumerate(specs):
            report["phase"] = f"pair_{index}"
            pair_dir = (
                directory
                / f"{index:02d}-{spec.scale[0]:g}-{spec.scale[1]:g}-d{spec.decimals}"
            )
            pair_dir.mkdir()
            report["pairs"].append({"spec": asdict(spec), "status": "running"})
            guard(f"before_pair_{index}")
            normal = await run_trial(spec, "normal", pair_dir)
            guard(f"after_normal_{index}")
            if spec.decimals not in entries:
                row = {
                    "precision": spec.decimals,
                    "accessors": [],
                    "operation_scopes": [],
                }
                report["preparations"].append(row)
                entries[spec.decimals] = await controller._prepare(
                    adapter, spec, directory / "cache" / str(spec.decimals), row
                )
                if entries[spec.decimals].spec != cache.prepared.canonical_spec(spec):
                    raise RuntimeError(
                        "canonical-scale preparation returned a noncanonical base"
                    )
            entry = entries[spec.decimals]
            report["pairs"][-1]["base_key"] = entry.key
            await run_trial(spec, "canonical", pair_dir, entry, normal)
            guard(f"after_pair_{index}")
            report["pairs"][-1]["status"] = "passed"
            checkpoint()
    except Exception as error:
        report["error"] = repr(error)
        if report["pairs"] and report["pairs"][-1]["status"] == "running":
            report["pairs"][-1].update(status="failed", error=repr(error))
        errors.append(error)
    finally:
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            report["cleanup_error"] = repr(error)
            errors.append(error)
        try:
            guard("finally")
        except Exception as error:
            report["final_guard_error"] = repr(error)
            errors.append(error)
        report.update(
            status="failed" if errors else "passed",
            phase="finished",
            elapsed_seconds=time.perf_counter() - started,
        )
        checkpoint()
    if errors:
        raise ExceptionGroup("canonical-scale owned comparison failed", errors)
    return {
        "measurements": str(report_path),
        "ownership": str(directory / "ownership.json"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-pid", type=int, required=True)
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    cache.require_environment(args.expected_pid)
    if args.worker:
        return cache.ownership.run_copy_diagnostic(
            lambda adapter: probe(
                adapter, args.report_root.resolve(), args.expected_pid
            )
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--expected-pid",
            str(args.expected_pid),
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "canonical prepared-template scale pairs",
        log_stem="canonical-template-scales",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

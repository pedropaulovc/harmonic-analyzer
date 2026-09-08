"""Locate rack drawing operations that dirty or save a referenced part.

Every trial copies the supplied baseline into its new evidence directory. The
recipe stops BEFORE datum creation: these partial drawings omit datum/FCF,
surface-finish and notes/finalization, and are not manufacturing acceptance.
No explicit part save is requested; drawing saves may write their reference.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "cad/scripts")]
MODES = ("full", "import", "views", "callout", "precision")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class PreparationBoundary(Exception):
    """The diagnostic has reached its declared partial-recipe boundary."""


def manufacturing_state(dimension, early_bound, read_member):
    """Read nominal and tolerance using the same accessors as _drawing_marks."""
    tolerance = early_bound(dimension.Tolerance, "IDimensionTolerance")
    if tolerance is None:
        raise RuntimeError("BoreDia has no tolerance interface")
    state = {
        "system_value_m": float(read_member(dimension, "SystemValue")),
        "tolerance_type": int(tolerance.Type),
        "tolerance_min_m": float(tolerance.GetMinValue()),
        "tolerance_max_m": float(tolerance.GetMaxValue()),
    }
    if not all(math.isfinite(state[key]) for key in (
        "system_value_m", "tolerance_min_m", "tolerance_max_m"
    )):
        raise RuntimeError("BoreDia has non-finite nominal or tolerance")
    if state["tolerance_min_m"] > state["tolerance_max_m"]:
        raise RuntimeError("BoreDia tolerance limits are reversed")
    return state


def assert_manufacturing_preserved(expected, actual):
    if expected != actual:
        raise RuntimeError(f"BoreDia nominal/tolerance changed: {expected!r} -> {actual!r}")


def validate_bore_observation(dimensions, phase):
    """Never accept vacuous identity/tolerance checks after model-item import."""
    expected_counts = {"before_import": 0, "imported": 1}
    if phase not in expected_counts:
        raise ValueError(f"unknown drawing dimension observation phase: {phase!r}")
    if len(dimensions) != expected_counts[phase]:
        raise RuntimeError(
            f"BoreDia observation {phase}: expected {expected_counts[phase]} "
            f"drawing dimensions, found {len(dimensions)}"
        )


def instrument_attempt(original_attempt, checkpoint):
    """Observe named mutators without recursively observing readback getters."""
    def observed(operation, *positional, **keywords):
        names = set(getattr(getattr(operation, "__code__", None), "co_names", ()))
        mutations = names.intersection({"SetText", "SetPrecision3", "SetPosition", "EditRebuild3"})
        if not mutations:
            return original_attempt(operation, *positional, **keywords)
        label = "+".join(sorted(mutations))
        checkpoint(f"before:COM:{label}")
        result = operation()
        checkpoint(f"after:COM:{label}")
        if mutations.intersection({"SetPosition", "EditRebuild3"}) and result is not True:
            raise RuntimeError(f"{label} rejected: {result!r}")
        if "SetPrecision3" in mutations and (type(result) is not int or result != 0):
            raise RuntimeError(f"SetPrecision3 rejected or partly applied: {result!r}")
        # SetText is documented void; text is captured in the next readback.
        return result
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=MODES, default="full")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    baseline = args.baseline.resolve(strict=True)
    output = args.output.resolve()
    reports = (ROOT / "cad/out/reports").resolve()
    if not baseline.is_file() or baseline.name != "rack-pinion.SLDPRT":
        raise ValueError("baseline must be an existing rack-pinion.SLDPRT")
    if not baseline.is_relative_to(ROOT / "cad/out"):
        raise ValueError("baseline must belong to this checkout's cad/out")
    if not output.is_relative_to(reports) or output == reports or output.exists():
        raise ValueError("choose a new child directory under this checkout's reports")
    if Path(sys.prefix).resolve() != ROOT / ".venv":
        raise RuntimeError("use this checkout's own uv environment")
    if os.environ.get("HARMONIC_SW_AUTOSTART") != "0":
        raise RuntimeError("attach-only mode required")
    if not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID"):
        raise RuntimeError("explicit inventoried SolidWorks PID required")
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise RuntimeError("disable remote cache transfers")

    from _common import _early_bound, _read_member
    import _drawing_common as common
    from _drawing_marks import _named_dimension
    import draw_rack_pinion as recipe
    from diagnostics._owned_native_session import run_owned_diagnostic

    async def probe(adapter):
        app = adapter.swApp
        if app.GetDocuments() or app.ActiveDoc is not None:
            raise RuntimeError("requires an empty seat; no documents closed")
        output.mkdir(parents=True)
        source = output / "rack-pinion.SLDPRT"
        baseline_hash = digest(baseline)
        shutil.copyfile(baseline, source)
        if digest(source) != baseline_hash or digest(baseline) != baseline_hash:
            raise RuntimeError("baseline copy was not byte-identical")
        receipt = output / "receipt.json"
        started = time.perf_counter()
        report = {
            "kind": "vm2-rack-reference-save-cause", "mode": args.mode,
            "baseline": str(baseline), "baseline_sha256": baseline_hash,
            "source": str(source), "source_sha256_initial": digest(source),
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "adapter": subprocess.check_output(["git", "-C", "SolidworksMCP-python", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "probe_sha256": digest(__file__), "recipe_sha256": digest(recipe.__file__),
            "helper_sha256": digest(common.__file__),
            "pid": int(app.GetProcessID()), "revision": str(app.RevisionNumber()),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "scope": "partial diagnostic, no datum or manufacturing acceptance",
            "status": "running", "checkpoints": [], "exports": [],
        }
        source_model = None
        draw = None
        source_dimension = None
        initial_manufacturing = None
        known_draw_annotations = []
        annotation_phase = "before_import"
        saved_hash = baseline_hash

        def flush():
            receipt.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        def display_state(raw):
            display = _early_bound(raw, "IDisplayDimension")
            dim = _early_bound(display.GetDimension2(0), "IDimension")
            if dim is None:
                raise RuntimeError("display dimension has no source dimension")
            return {
                "full_name": str(_read_member(dim, "FullName")),
                "manufacturing": manufacturing_state(dim, _early_bound, _read_member),
                "text_above": str(display.GetText(3)),
                "text_below": str(display.GetText(4)),
                "primary_precision": int(display.GetPrimaryPrecision2()),
                "same_as_source_dimension": int(app.IsSame(dim, source_dimension)),
            }

        def checkpoint(label):
            nonlocal saved_hash, source_dimension, initial_manufacturing
            row = {"label": label, "utc": datetime.now(timezone.utc).isoformat(),
                   "source_sha256": digest(source)}
            report["checkpoints"].append(row)
            flush()
            if source_model is not None:
                row["source_dirty_before_readback"] = bool(source_model.GetSaveFlag())
                display, source_dimension = _named_dimension(
                    SimpleNamespace(currentModel=source_model), "BoreProfile", "BoreDia"
                )
                row["source_dimension"] = display_state(display)
                row["drawing_dimensions"] = [
                    display_state(_early_bound(ann, "IAnnotation").GetSpecificAnnotation())
                    for ann in known_draw_annotations
                    if common.dimension_name(adapter, ann) == "BoreDia"
                ]
                row["source_dirty_after_readback"] = bool(source_model.GetSaveFlag())
                row["dimension_observation_phase"] = annotation_phase
                flush()
                validate_bore_observation(row["drawing_dimensions"], annotation_phase)
                if row["source_dirty_before_readback"] != row["source_dirty_after_readback"]:
                    raise RuntimeError("readback instrumentation changed the source dirty flag")
                actual = row["source_dimension"]["manufacturing"]
                if initial_manufacturing is None:
                    initial_manufacturing = dict(actual)
                    report["source_manufacturing_initial"] = initial_manufacturing
                assert_manufacturing_preserved(initial_manufacturing, actual)
                for dimension in row["drawing_dimensions"]:
                    assert_manufacturing_preserved(initial_manufacturing, dimension["manufacturing"])
                    if dimension["same_as_source_dimension"] != 1:
                        raise RuntimeError("drawing BoreDia is not the source model dimension")
            if draw is not None:
                row["drawing_dirty"] = bool(draw.GetSaveFlag())
            if row["source_sha256"] != saved_hash:
                snapshot = output / f"source-change-{len(report['checkpoints']):03d}.SLDPRT"
                shutil.copyfile(source, snapshot)
                if digest(snapshot) != row["source_sha256"] or digest(source) != row["source_sha256"]:
                    raise RuntimeError("source changed during byte snapshot")
                row["source_change_copy"] = str(snapshot)
                saved_hash = row["source_sha256"]
            if digest(baseline) != baseline_hash:
                raise RuntimeError("baseline bytes changed")
            flush()

        def wrap(label, operation, *, remember=False):
            def observed(*positional, **keywords):
                nonlocal annotation_phase
                checkpoint(f"before:{label}")
                result = operation(*positional, **keywords)
                if remember:
                    known_draw_annotations[:] = list(result or ())
                    annotation_phase = "imported"
                checkpoint(f"after:{label}")
                return result
            return observed

        def omitted(label):
            def skip(*_positional, **_keywords):
                checkpoint(f"omitted:{label}")
            return skip

        def boundary(*_positional, **_keywords):
            report["preparation_boundary"] = "before_import" if args.mode == "views" else "before_datum"
            checkpoint(report["preparation_boundary"])
            raise PreparationBoundary()

        original_open = adapter.open_model
        original_attempt = adapter._attempt
        observed_attempt = instrument_attempt(original_attempt, checkpoint)

        async def observed_open(path):
            nonlocal source_model
            checkpoint("before:open_model")
            result = await original_open(path)
            source_model = _early_bound(adapter.currentModel, "IModelDoc2")
            if source_model is None or Path(str(source_model.GetPathName())).resolve() != source:
                raise RuntimeError("open did not return this trial's source")
            checkpoint("after:open_model")
            return result

        original_new = recipe.new_project_drawing

        def observed_new(*positional, **keywords):
            nonlocal draw
            checkpoint("before:new_project_drawing")
            result = original_new(*positional, **keywords)
            draw = _early_bound(result[0], "IModelDoc2")
            checkpoint("after:new_project_drawing")
            return result

        flush()
        try:
            with ExitStack() as patches:
                patches.enter_context(patch.object(recipe, "SOURCE", source))
                patches.enter_context(patch.object(adapter, "open_model", observed_open))
                patches.enter_context(patch.object(adapter, "_attempt", observed_attempt))
                patches.enter_context(patch.object(recipe, "new_project_drawing", observed_new))
                patches.enter_context(patch.object(recipe, "add_native_axis_datum", boundary))
                for owner, name in (
                    (recipe, "place_view"), (recipe, "set_hidden_lines_removed"),
                    (recipe, "auto_center_marks"), (common, "insert_marked_dimensions"),
                    (common, "delete_unnamed_imports"), (common, "curate_dimensions"),
                ):
                    patches.enter_context(patch.object(owner, name, wrap(
                        name, getattr(owner, name), remember=name in ("insert_marked_dimensions", "delete_unnamed_imports", "curate_dimensions")
                    )))
                if args.mode == "views":
                    patches.enter_context(patch.object(recipe, "curate_view_dimensions", boundary))
                for name, modes in (
                    ("set_dimension_callouts", ("full", "callout")),
                    ("set_dimension_precision", ("full", "precision")),
                ):
                    operation = wrap(name, getattr(recipe, name)) if args.mode in modes else omitted(name)
                    patches.enter_context(patch.object(recipe, name, operation))
                try:
                    await recipe.build(adapter)
                except PreparationBoundary:
                    pass
                else:
                    raise RuntimeError("recipe escaped the diagnostic boundary")
            checkpoint("before:drawing_rebuild")
            draw.ClearSelection2(True)
            if not draw.EditRebuild3():
                raise RuntimeError("drawing rebuild rejected")
            checkpoint("after:drawing_rebuild")
            for extension in ("SLDDRW", "pdf"):
                target = output / f"partial.{extension}"
                checkpoint(f"before:SaveAs3:{extension}")
                code = draw.SaveAs3(str(target), 0, 0)
                report["exports"].append({"path": str(target), "return": code})
                checkpoint(f"after:SaveAs3:{extension}")
                if type(code) is not int or code != 0 or not target.is_file():
                    raise RuntimeError(f"SaveAs3 rejected {extension}: {code!r}")
                report["exports"][-1]["sha256"] = digest(target)
            checkpoint("before:close")
            allowed = {source, output / "partial.SLDDRW"}
            documents = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
            targets = [(Path(str(doc.GetPathName())).resolve(), str(doc.GetTitle()), int(doc.GetType())) for doc in documents]
            if {row[0] for row in targets} != allowed or len(targets) != 2:
                raise RuntimeError("unexpected document inventory; nothing closed")
            if any(not row[1] for row in targets) or len({row[1].casefold() for row in targets}) != 2:
                raise RuntimeError("ambiguous titles; nothing closed")
            report["closed_without_explicit_save"] = []
            for path, title, _kind in sorted(targets, key=lambda row: row[2] != 3):
                current = [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]
                pairs = {(Path(str(doc.GetPathName())).resolve(), str(doc.GetTitle())) for doc in current}
                if not pairs.issubset({(row[0], row[1]) for row in targets}):
                    raise RuntimeError("foreign document appeared during closure")
                if (path, title) in pairs:
                    app.CloseDoc(title)
                    report["closed_without_explicit_save"].append(str(path))
                    flush()
            if app.GetDocuments() or app.ActiveDoc is not None:
                raise RuntimeError("closure did not return an empty inventory")
            source_model = draw = None
            checkpoint("after:close")
            report["status"] = "observed_and_closed"
            report["source_sha256_final"] = digest(source)
        except Exception as error:
            report.update(status="failed", error=repr(error))
            raise
        finally:
            report["elapsed_s"] = time.perf_counter() - started
            report["ended_utc"] = datetime.now(timezone.utc).isoformat()
            report["baseline_sha256_final"] = digest(baseline)
            flush()
        return {"receipt": str(receipt), "sha256": digest(receipt)}

    if args.worker:
        return run_owned_diagnostic(probe)
    import dodo
    with dodo._com_seat("VM2 rack source-save probe"):
        dodo._exec([
            sys.executable, str(Path(__file__).resolve()), str(baseline), str(output),
            "--mode", args.mode, "--worker",
        ], "VM2 rack source-save probe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

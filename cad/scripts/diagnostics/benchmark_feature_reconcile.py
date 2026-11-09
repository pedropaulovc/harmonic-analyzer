"""Experimental keyed cylinder reconciliation. --help and plan require no COM."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from typing import Any

# Deliberately no native imports until after argument parsing and seat guard.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _feature_reconcile import DIMENSIONS, FEATURES, plan, recipe

PREFIX = "experiment.feature_reconcile"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "out" / "reports" / "feature-reconcile"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


class Benchmark:
    def __init__(self, adapter: Any, out: Path):
        self.adapter = adapter
        self.out = out
        self.phases: list[dict[str, Any]] = []

    @contextmanager
    def phase(self, name: str, case: str, **attributes: Any):
        import _telemetry
        start = time.perf_counter()
        with _telemetry.span(f"{PREFIX}.{name}", case=case, **attributes) as span:
            ctx = span.get_span_context()
            row = {"phase": name, "case": case, "trace_id": f"{ctx.trace_id:032x}",
                   "span_id": f"{ctx.span_id:016x}", "status": "error"}
            try:
                yield
                row["status"] = "ok"
            finally:
                row["seconds"] = time.perf_counter() - start
                self.phases.append(row)

    def model(self):
        from _com import _early_bound
        return _early_bound(self.adapter.currentModel, "IModelDoc2")

    def feature(self, item):
        import _telemetry
        from _com import _early_bound
        raw = _early_bound(self.model(), "IPartDoc").FeatureByName(item["name"])
        if raw is None:
            raise RuntimeError(f"Missing keyed feature {item['key']}: expected name={item['name']!r}")
        feature = _early_bound(raw, "IFeature")
        observed = {
            "key": item["key"], "actual_name": str(feature.Name),
            "raw_type": str(feature.GetTypeName2()),
        }
        # SDK GetTypeName2 explicitly requires GetTypeName only for ICE.
        # Retain the raw answer even if querying the underlying kind fails.
        _telemetry.event(f"{PREFIX}.feature_type_raw", **observed)
        observed["effective_type"] = (
            str(feature.GetTypeName()) if observed["raw_type"] == "ICE"
            else observed["raw_type"]
        )
        _telemetry.event(f"{PREFIX}.feature_type", **observed)
        mismatch = observed["actual_name"] != item["name"]
        if item["key"] == "body":
            # The first solid extrusion is a base feature, not an added boss.
            # Native Boss/Extrusion labels alone cannot establish that contract.
            mismatch |= observed["effective_type"] not in {"Boss", "Extrusion"}
            if not mismatch:
                definition = feature.GetDefinition()
                if definition is None:
                    raise RuntimeError(f"Missing extrusion definition: expected={item!r}, observed={observed!r}")
                definition = _early_bound(definition, "IExtrudeFeatureData2")
                observed.update({
                    "is_boss": bool(definition.IsBossFeature()),
                    "is_base": bool(feature.IsBase2()),
                    "is_thin": bool(definition.IsThinFeature()),
                    "both_directions": bool(definition.BothDirections),
                    "reverse_direction": bool(definition.ReverseDirection),
                    "forward_end_condition": int(definition.GetEndCondition(True)),
                    "forward_depth_m": float(definition.GetDepth(True)),
                })
                definition = None  # Never retain feature-data objects across reopen.
                _telemetry.event(f"{PREFIX}.extrusion_definition", **observed)
                mismatch |= (
                    not observed["is_base"] or observed["is_thin"]
                    or observed["both_directions"] or observed["reverse_direction"]
                    or observed["forward_end_condition"] != 0  # swEndCondBlind
                    or not math.isfinite(observed["forward_depth_m"])
                    or observed["forward_depth_m"] <= 0
                )
        else:
            mismatch |= observed["effective_type"] != item["type"]
        if mismatch:
            raise RuntimeError(f"Native feature contract mismatch: expected={item!r}, observed={observed!r}")
        return feature

    def dimension(self, key):
        from _com import _early_bound
        raw = self.model().Parameter(DIMENSIONS[key])
        if raw is None:
            raise RuntimeError(f"Missing keyed dimension {key}: {DIMENSIONS[key]}")
        return _early_bound(raw, "IDimension")

    def refs(self):
        ext = self.model().Extension
        result = {}
        for item in FEATURES:
            reference = ext.GetPersistReference3(self.feature(item))
            if not reference:
                raise RuntimeError(f"Missing persistent reference: {item['key']}")
            result[item["key"]] = base64.b64encode(bytes(int(x) & 255 for x in reference)).decode("ascii")
        return result

    def validate(self, spec, refs):
        """Identical native gates for baseline, clean, incremental and no-op."""
        from _com import _early_bound
        import pythoncom
        from win32com.client import VARIANT
        model = self.model()
        params = spec["parameters_mm"]
        values = {}
        for key, expected in params.items():
            actual = self.dimension(key).GetSystemValue3(1, None)  # swThisConfiguration
            if not isinstance(actual, (tuple, list)) or len(actual) != 1:
                raise RuntimeError(f"Unexpected dimension readback {key}: {actual!r}")
            value = float(actual[0]) * 1000
            if not math.isfinite(value) or abs(value - expected) > 1e-7:
                raise RuntimeError(f"Dimension {key}: {value} != {expected} mm")
            values[key] = value
        identity = {}
        ext = _early_bound(model.Extension, "IModelDocExtension")
        for item in FEATURES:
            native = self.feature(item)
            reference = VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_UI1,
                base64.b64decode(refs[item["key"]], validate=True),
            )
            answer = ext.GetObjectByPersistReference3(reference)
            if not isinstance(answer, (tuple, list)) or len(answer) != 2:
                raise RuntimeError(f"Unexpected reference resolution: {answer!r}")
            resolved, state = answer
            # SDK compare-selected-objects example: 1=same, 0=different, -1=unknown.
            if int(state) != 0 or resolved is None or int(self.adapter.swApp.IsSame(resolved, native)) != 1:
                raise RuntimeError(f"Feature identity lost: {item['key']}, state={state}")
            identity[item["key"]] = True
        part = _early_bound(model, "IPartDoc")
        bodies = part.GetBodies2(0, False) or ()  # swSolidBody
        if len(bodies) != 1:
            raise RuntimeError(f"Expected exactly one solid body, got {len(bodies)}")
        body = _early_bound(bodies[0], "IBody2")
        bounds = []
        for axis in range(3):
            points = []
            for sign in (-1, 1):
                direction = [float(sign) if i == axis else 0.0 for i in range(3)]
                answer = body.GetExtremePoint(*direction)
                if not isinstance(answer, (tuple, list)) or len(answer) != 4 or not answer[0]:
                    raise RuntimeError(f"GetExtremePoint failed: {answer!r}")
                points.append(float(answer[axis + 1]) * 1000)
            bounds.append(points)
        radius = params["diameter"] / 2
        expected_bounds = [[-radius, radius], [-radius, radius], [0.0, params["depth"]]]
        for actual_pair, expected_pair in zip(bounds, expected_bounds, strict=True):
            for actual, expected in zip(actual_pair, expected_pair, strict=True):
                if not math.isfinite(actual) or abs(actual - expected) > 1e-6:
                    raise RuntimeError(f"Exact native bounds mismatch: {bounds} != {expected_bounds}")
        model.ClearSelection2(True)
        mass = ext.CreateMassProperty2()
        if mass is None:
            raise RuntimeError("CreateMassProperty2 returned null")
        mass = _early_bound(mass, "IMassProperty2")
        volume = float(mass.Volume) * 1e9  # m^3 -> mm^3; no adapter implicit rebuild
        expected_volume = math.pi * radius**2 * params["depth"]
        if not math.isfinite(volume) or abs(volume - expected_volume) > expected_volume * 1e-7:
            raise RuntimeError(f"Volume {volume} != {expected_volume} mm^3")
        return {"dimensions_mm": values, "bounds_mm": bounds, "volume_mm3": volume,
                "feature_identity": identity}

    def close(self):
        model = self.model()
        path = model.GetPathName()
        self.adapter.swApp.CloseDoc(model.GetTitle())
        self.adapter.currentModel = None
        if path and self.adapter.swApp.GetOpenDocumentByName(path) is not None:
            raise RuntimeError(f"Document did not close: {path}")

    async def open(self, path):
        # Do not use adapter.open_model here: it accepts a non-null document
        # even with native error bits. Read every native output, fail closed.
        answer = self.adapter.swApp.OpenDoc6(str(path), 1, 1, "", 0, 0)
        if not isinstance(answer, (tuple, list)) or len(answer) != 3:
            raise RuntimeError(f"Unexpected OpenDoc6 readback: {answer!r}")
        document, errors, warnings = answer
        if document is None or errors or warnings:
            raise RuntimeError(f"OpenDoc6 failed/warned: errors={errors}, warnings={warnings}, path={path}")
        self.adapter.currentModel = document
        actual = Path(self.model().GetPathName()).resolve()
        if actual != path.resolve():
            raise RuntimeError(f"Opened wrong document: {actual} != {path}")

    def save(self, path):
        from _com import _early_bound
        self.model().ClearSelection2(True)
        ext = _early_bound(self.model().Extension, "IModelDocExtension")
        # Silent | AvoidRebuildOnSave: rebuild is an explicitly timed phase.
        answer = ext.SaveAs(str(path), 0, 1 | 8, None, 0, 0)
        if not isinstance(answer, (tuple, list)) or len(answer) != 3:
            raise RuntimeError(f"Unexpected SaveAs readback: {answer!r}")
        ok, errors, warnings = answer
        if not ok or errors or warnings or not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"SaveAs failed/warned: ok={ok}, errors={errors}, warnings={warnings}, path={path}")

    async def create(self, spec):
        from _check import check
        from _dimensions import name_dimensions
        from _feature_tree import name_last_feature
        from _sketch import SketchDims, ensure_fully_defined
        from _sketch_circle import define_circle
        from solidworks_mcp.adapters.base import ExtrusionParameters
        check("create cylinder", await self.adapter.create_part())
        dims = SketchDims()
        check("create profile", await self.adapter.create_sketch("Front"))
        await define_circle(self.adapter, 0.0, 0.0, spec["parameters_mm"]["diameter"] / 2,
                            "reconcile diameter", dims=dims, names=(None, None, "Diameter"))
        await ensure_fully_defined(self.adapter, "reconcile profile")
        check("exit profile", await self.adapter.exit_sketch())
        name_last_feature(self.adapter, "ReconcileProfile")
        dims.apply(self.adapter, "ReconcileProfile")
        check("extrude cylinder", await self.adapter.create_extrusion(ExtrusionParameters(depth=spec["parameters_mm"]["depth"])))
        name_last_feature(self.adapter, "ReconcileBody")
        name_dimensions(self.adapter, "ReconcileBody", ["Depth"])

    async def operation(self, case, mode, spec, source=None, manifest=None):
        path = self.out / f"{case}.SLDPRT"
        started = time.perf_counter()
        decision = None
        with self.phase("open_copy", case, mode=mode):
            if mode != "clean":
                if digest(source) != manifest["native_sha256"]:
                    raise RuntimeError("Baseline bytes no longer match persisted manifest")
                shutil.copyfile(source, path)
                await self.open(path)
        with self.phase("diff", case):
            decision = plan(manifest["recipe"], spec) if manifest else None
            if decision and decision.decision == "full_build":
                raise RuntimeError("Structural plan must be handled before native mutation")
        dimensions = []
        with self.phase("baseline_validation", case, skipped=mode != "incremental"):
            if mode == "incremental":
                # Validate *all* input contracts and resolve all dimensions
                # before timing the first mutation.
                self.validate(manifest["recipe"], manifest["feature_references"])
                dimensions = [(self.dimension(key), value) for key, value in decision.edits]
        with self.phase("edit", case, skipped=mode == "noop", mode=mode):
            if mode == "clean":
                await self.create(spec)
            elif mode == "incremental":
                for dimension, value in dimensions:
                    status = dimension.SetSystemValue3(value / 1000, 1, None)
                    if int(status) != 0:  # swSetValue_Successful
                        raise RuntimeError(f"SetSystemValue3 failed: {status}")
                # No live dimension handles across the close/reopen proof.
                dimensions.clear()
                dimension = None
            elif not decision or decision.decision != "noop":
                raise RuntimeError(f"Expected no-op plan, got {decision}")
        with self.phase("rebuild", case, skipped=mode == "noop"):
            if mode != "noop" and not self.model().EditRebuild3():
                raise RuntimeError("EditRebuild3 failed")
        with self.phase("validation_before_save", case):
            refs = self.refs() if mode == "clean" else manifest["feature_references"]
            before = self.validate(spec, refs)
        with self.phase("save", case, skipped=mode == "noop"):
            if mode != "noop":
                self.save(path)
            saved_hash = digest(path)
        with self.phase("close_before_reopen", case):
            self.close()
        with self.phase("reopen", case):
            await self.open(path)
        with self.phase("validation_after_reopen", case):
            after = self.validate(spec, refs)
        with self.phase("close_after_reopen", case):
            self.close()
        with self.phase("readback_integrity", case):
            if digest(path) != saved_hash:
                raise RuntimeError("Readback changed saved native bytes")
            if mode == "noop" and saved_hash != manifest["native_sha256"]:
                raise RuntimeError("No-op mutated native bytes")
        return {"case": case, "mode": mode, "seconds": time.perf_counter() - started,
                "decision": asdict(decision) if decision else {"decision": "clean"},
                "before_save": before, "after_reopen": after, "path": path.name,
                "native_sha256": saved_hash, "feature_references": refs}

    async def render(self, row):
        """Capture a saved trial outside all timed operation rows; never save it."""
        import _telemetry
        from _check import check
        from PIL import Image

        native = self.out / row["path"]
        image_path = self.out / f"visual-{row['mode']}.png"
        original_hash = digest(native)
        with _telemetry.span(f"{PREFIX}.render", mode=row["mode"], timed_trial=False):
            await self.open(native)
            try:
                # export_image may fall back to an existence-based SaveAs capture.
                # Remove our prior image so stale bytes cannot masquerade as proof.
                image_path.unlink(missing_ok=True)
                check(f"render {row['mode']}", await self.adapter.export_image({
                    "file_path": str(image_path),
                    "format_type": "png",
                    "width": 1600,
                    "height": 1000,
                    "view_orientation": "isometric",
                }))
                with Image.open(image_path) as image:
                    dimensions = list(image.size)
                    if image.format != "PNG" or min(dimensions) <= 0:
                        raise RuntimeError(f"Invalid PNG proof: {image_path}")
                    image.verify()
            finally:
                self.close()
            if digest(native) != original_hash:
                raise RuntimeError(f"Rendering changed native bytes: {native}")
        return {"mode": row["mode"], "native_file": native.name,
                "native_sha256": original_hash, "image_file": image_path.name,
                "image_sha256": digest(image_path), "image_dimensions": dimensions,
                "orientation": "isometric", "included_in_trial_timings": False}


async def benchmark(adapter, out, trials):
    import _telemetry
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SpanProcessor

    out.mkdir(parents=True, exist_ok=True)
    raw = out / "spans.jsonl"
    raw.write_text("", encoding="utf-8")

    class RetainedSpans(SpanProcessor):
        def __init__(self):
            self.count = 0
            self.error = None
            self.completed = []

        def on_end(self, span):
            if not span.name.startswith(PREFIX):
                return
            self.completed.append(span)
            self.count += 1
            # Retain real completed SDK spans, but serialize/write only when
            # the enclosing benchmark ends (also on exceptions). Dedicated
            # evidence IO must not inflate the operation timing rows.
            if span.name == PREFIX:
                try:
                    with raw.open("w", encoding="utf-8") as stream:
                        for completed in self.completed:
                            stream.write(completed.to_json(indent=None) + "\n")
                except Exception as exc:
                    self.error = exc
                    raise

    retained = RetainedSpans()
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        raise RuntimeError("A real OTel SDK provider is required")
    provider.add_span_processor(retained)
    harness = Benchmark(adapter, out)
    base_spec = recipe()
    target = recipe(24.0, 15.0)
    write_json(out / "target-recipe.json", target)
    with _telemetry.span(PREFIX, trials=trials) as root:
        root_context = root.get_span_context()
        if not root_context.is_valid or not root.is_recording():
            raise RuntimeError("Benchmark requires recording OTel spans")
        initial = await harness.operation("baseline", "clean", base_spec)
        manifest = {"schema": 1, "recipe": base_spec, "native_file": initial["path"],
                    "native_sha256": initial["native_sha256"], "feature_references": initial["feature_references"]}
        manifest_path = out / "baseline-manifest.json"
        write_json(manifest_path, manifest)
        # Exercise persisted—not in-memory—recipe and reference readback.
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        structural_spec = recipe()
        structural_spec["features"][1]["operation"] = "through_all"
        original_hash = digest(out / manifest["native_file"])
        with harness.phase("diff", "structural_refusal"):
            structural = plan(manifest["recipe"], structural_spec)
            if structural.decision != "full_build" or structural.edits:
                raise RuntimeError("Structural edit was not refused before mutation")
        if digest(out / manifest["native_file"]) != original_hash:
            raise RuntimeError("Structural refusal changed baseline")
        results = []
        orders = []
        for trial in range(trials):
            order = ("clean", "incremental") if trial % 2 == 0 else ("incremental", "clean")
            orders.append(list(order) + ["noop"])
            pair = {}
            for mode in order:
                pair[mode] = await harness.operation(f"trial-{trial + 1}-{mode}", mode, target,
                    out / manifest["native_file"], manifest)
                results.append(pair[mode])
            # Native analytical gates above are identical; compare observed geometry too.
            clean = pair["clean"]["after_reopen"]
            incremental = pair["incremental"]["after_reopen"]
            for key in DIMENSIONS:
                if abs(clean["dimensions_mm"][key] - incremental["dimensions_mm"][key]) > 1e-7:
                    raise RuntimeError(f"Clean/incremental dimension {key} differs")
            for clean_pair, incremental_pair in zip(clean["bounds_mm"], incremental["bounds_mm"], strict=True):
                if any(abs(a - b) > 1e-6 for a, b in zip(clean_pair, incremental_pair, strict=True)):
                    raise RuntimeError("Clean/incremental exact extents differ")
            if not math.isclose(clean["volume_mm3"], incremental["volume_mm3"], rel_tol=1e-9):
                raise RuntimeError("Clean/incremental volume differs")
            edited = pair["incremental"]
            noop_manifest = {"recipe": target, "native_sha256": edited["native_sha256"],
                             "feature_references": edited["feature_references"]}
            results.append(await harness.operation(f"trial-{trial + 1}-noop", "noop", target,
                out / edited["path"], noop_manifest))
        if digest(out / manifest["native_file"]) != original_hash:
            raise RuntimeError("Trials mutated exact baseline")
        # Rendering is visual evidence, not part of any measured trial.
        visual_proof = [await harness.render(pair[mode]) for mode in ("clean", "incremental")]
    if retained.error or retained.count < len(harness.phases) + 1:
        raise RuntimeError(f"Incomplete retained OTel evidence: {retained.count}, {retained.error}")
    report = {"schema": 1, "experimental_limits": "Only an origin-centred Front-plane circle and positive-Z blind extrusion; no arbitrary topology reconciliation.",
              "trace_id": f"{root_context.trace_id:032x}", "trials": trials, "orders": orders,
              "initial_baseline": initial, "structural_decision": asdict(structural),
              "results": results, "phases": harness.phases, "raw_spans": raw.name,
              "retained_span_count": retained.count,
              "visual_proof": visual_proof,
              "median_seconds": {mode: statistics.median(row["seconds"] for row in results if row["mode"] == mode)
                                 for mode in ("clean", "incremental", "noop")},
              "timing_note": "Warm-seat native operation wall times, including baseline prevalidation and validation/save/readback; baseline cost separate. Phase spans separate prevalidation, edit, rebuild, validations, save, reopen and closes. Excludes process/connect/farm/cache overhead and post-trial visual renders. No-op skips mutation/rebuild/save, not validation."}
    write_json(out / "report.json", report)
    return {"report": str(out / "report.json"), "spans": str(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("benchmark", help="Run on an admitted, locked farm seat only")
    run.add_argument("--out", type=Path, default=DEFAULT_OUT)
    run.add_argument("--trials", type=int, default=3)
    diff = sub.add_parser("plan", help="Diff a persisted baseline manifest against a recipe JSON without COM")
    diff.add_argument("manifest", type=Path)
    diff.add_argument("recipe", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        before = json.loads(args.manifest.read_text(encoding="utf-8"))
        after = json.loads(args.recipe.read_text(encoding="utf-8"))
        print(json.dumps(asdict(plan(before["recipe"], after)), indent=2))
        return 0
    if args.trials < 3:
        parser.error("--trials must be at least 3")
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("Use the canonical verify:feature_reconcile task; no standalone COM launch")
    if args.out.resolve() != DEFAULT_OUT.resolve():
        parser.error("--out must be the canonical declared diagnostic output directory")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _session import run_build
    return run_build(lambda adapter: benchmark(adapter, args.out.resolve(), args.trials))


if __name__ == "__main__":
    raise SystemExit(main())

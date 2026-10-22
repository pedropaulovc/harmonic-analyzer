"""Private frozen-input SupplierReference discriminator; never saves native files.

One admitted verify leaf runs five fixed disposable-document cases: an isolated
linear positive control, the incident riser screw, that screw with only angular
argument order reversed, the incident flange nut, and that nut with only the two
independent diameter-origin anchors omitted. Those anchors are diagnostic
variables, not a proposed production change. Native failures are report data;
setup/ownership/cleanup failures remain fatal. No retries or inference toggles
are added. The unchanged fully-defined guard is executed before the diagnostic
boundary, so no failed production sketch is accepted or published.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import socket
import sys
from unittest.mock import patch

from _com import _early_bound
from _paths import CAD_ROOT, PART_TEMPLATE
import _sketch
import _supplier_screw_reference as reference
from diagnostics._owned_native_session import (
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)
import build_ch_rocker_arm_tl_vn_oblique_riser_screw as riser
import build_ch_rocker_arm_tl_vn_oblique_leadscrew_nut as nut

ROOT = CAD_ROOT.parent
OUT = CAD_ROOT / "out"
REPORT = OUT / "reports" / "supplier-sketch-probe" / "result.json"
BASE = "6d68291fd1f03c420551c1a70bd29afc11ce4dcb"
NATIVE_MUTATIONS = {
    "AddDimension", "AddDimension2", "AddHorizontalDimension2",
    "AddVerticalDimension2", "SetSystemValue3", "SetSystemValue2",
}
SOURCE_PATHS = (
    "cad/scripts/_supplier_screw_reference.py", "cad/scripts/_sketch.py",
    "cad/scripts/build_ch_rocker_arm_tl_vn_oblique_riser_screw.py",
    "cad/scripts/ch_rocker_arm_tl_vn_oblique_riser_screw_spec.py",
    "cad/scripts/build_ch_rocker_arm_tl_vn_oblique_leadscrew_nut.py",
    "cad/scripts/ch_rocker_arm_tl_vn_oblique_leadscrew_nut_spec.py",
    "cad/templates/harmonic-analyzer.PRTDOT",
    "SolidworksMCP-python/src/solidworks_mcp/adapters/solidworks/sketch.py",
    "SolidworksMCP-python/src/solidworks_mcp/adapters/pywin32_adapter.py",
    "SolidworksMCP-python/src/solidworks_mcp/adapters/_generated/sldworks_2026.py",
)


class ProbeBoundary(Exception):
    """Stop immediately after the original strict sketch guard, before save."""


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observe(callback):
    try:
        return callback()
    except Exception as error:
        return {"unavailable": f"{type(error).__name__}: {error}"}


def documents(app):
    raw = app.GetDocuments()
    docs = [] if raw is None else list(raw)
    if len(docs) != int(app.GetDocumentCount()):
        raise RuntimeError("native document inventory count disagrees")
    return [_early_bound(doc, "IModelDoc2") for doc in docs]


def output_inventory():
    if not OUT.exists():
        return {}
    ignored = {"reports/telemetry", "reports/supplier-sketch-probe"}
    return {
        path.relative_to(OUT).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in OUT.rglob("*")
        if path.is_file() and not any(
            path.relative_to(OUT).as_posix().startswith(prefix + "/")
            for prefix in ignored
        )
    }


class Recorder:
    def __init__(self, adapter, report):
        self.adapter = adapter
        self.app = adapter.swApp
        self.report = report
        self.case = None
        self.owned = []
        self.active = False
        self.native_depth = 0
        self.reverse_angle = False
        self.original_attempt = adapter._attempt
        self.originals = {}

    def point(self, raw, active_sketch):
        point = _early_bound(raw, "ISketchPoint")
        owner = point.GetSketch()
        return {
            "id": list(point.GetID()),
            "xyz_m": [float(point.X), float(point.Y), float(point.Z)],
            "status": int(point.Status),
            "owner_is_active": int(self.app.IsSame(owner, active_sketch)),
        }

    def describe_dimension(self, raw):
        display = _early_bound(raw, "IDisplayDimension")
        native = _early_bound(display.GetDimension2(0), "IDimension")
        if native is None:
            raise RuntimeError("returned display dimension has no IDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        return {
            "display_type": int(display.Type2),
            "parameter_type": int(native.GetType()),
            "driven_state": int(native.DrivenState),
            "system_value": float(native.SystemValue),
            "attachment_types": annotation.GetAttachedEntityTypes(),
        }

    def selection(self):
        model = self.adapter.currentModel
        if model is None:
            return []
        model = _early_bound(model, "IModelDoc2")
        manager = _early_bound(model.SelectionManager, "ISelectionMgr")
        count = int(manager.GetSelectedObjectCount2(-1))
        if count > 16:
            raise RuntimeError("selection exceeds fixed diagnostic bound")
        selected = []
        for index in range(1, count + 1):
            raw = manager.GetSelectedObject6(index, -1)
            matches = []
            for name, entity in self.adapter._sketch_entities.items():
                if not name.startswith("Line_"):
                    continue
                if int(self.app.IsSame(raw, entity)) == 1:
                    matches.append(name)
                line = _early_bound(entity, "ISketchLine")
                for suffix, point in (("start", line.GetStartPoint2()), ("end", line.GetEndPoint2())):
                    if int(self.app.IsSame(raw, point)) == 1:
                        matches.append(f"{name}.{suffix}")
            origin = getattr(self.adapter, "_sketch_origin_point", None)
            if origin is not None and int(self.app.IsSame(raw, origin)) == 1:
                matches.append("origin")
            selected.append({
                "index": index,
                "type": int(manager.GetSelectedObjectType3(index, -1)),
                "matches_by_native_identity": matches,
            })
        return selected

    def snapshot(self):
        model = self.adapter.currentModel
        if model is None:
            return {"active_sketch": None}
        model = _early_bound(model, "IModelDoc2")
        raw_sketch = model.GetActiveSketch2()
        if raw_sketch is None:
            return {"active_sketch": None, "title": model.GetTitle()}
        sketch = _early_bound(raw_sketch, "ISketch")
        result = _sketch._sketch_relation_snapshot(self.adapter, self.case["name"])
        points = []
        lines = {}
        dims = {}
        for name, entity in self.adapter._sketch_entities.items():
            if name.startswith("Line_"):
                line = _early_bound(entity, "ISketchLine")
                row = {}
                for suffix, raw in (("start", line.GetStartPoint2()), ("end", line.GetEndPoint2())):
                    row[suffix] = self.point(raw, sketch)
                    points.append((f"{name}.{suffix}", raw, row[suffix]["xyz_m"]))
                segment = _early_bound(entity, "ISketchSegment")
                row["construction"] = bool(segment.ConstructionGeometry)
                row["status"] = int(segment.Status)
                lines[name] = row
            elif name.startswith("Dimension_"):
                dims[name] = observe(lambda entity=entity: self.describe_dimension(entity))
        equal_coordinates = []
        for index, (name, point, xyz) in enumerate(points):
            for other_name, other_point, other_xyz in points[index + 1:]:
                if all(abs(a - b) < 1e-10 for a, b in zip(xyz, other_xyz, strict=True)):
                    equal_coordinates.append({
                        "first": name, "second": other_name,
                        "is_same": int(self.app.IsSame(point, other_point)),
                    })
        result.update(lines=lines, dimensions=dims, equal_coordinate_points=equal_coordinates)
        return result

    def native_attempt(self, operation, *args, **kwargs):
        names = set(getattr(getattr(operation, "__code__", None), "co_names", ()))
        names &= NATIVE_MUTATIONS
        if not self.active or not names or self.native_depth:
            return self.original_attempt(operation, *args, **kwargs)
        event = {"kind": "native", "members": sorted(names), "selection_before": observe(self.selection)}
        self.case["events"].append(event)

        def invoke():
            self.native_depth += 1
            try:
                value = operation()
                event["return_python_type"] = type(value).__name__
                if value is None or type(value) in (bool, int, float, str):
                    event["return"] = value
                else:
                    event["returned_dimension"] = observe(lambda: self.describe_dimension(value))
                return value
            except Exception as error:
                event["native_error"] = f"{type(error).__name__}: {error}"
                raise
            finally:
                self.native_depth -= 1
        result = self.original_attempt(invoke, *args, **kwargs)
        event["after"] = observe(self.snapshot)
        return result

    def install(self, stack):
        stack.enter_context(patch.object(self.adapter, "_attempt", self.native_attempt))
        original_create = self.adapter.create_part

        async def create_part(*args, **kwargs):
            before = documents(self.app)
            result = None
            try:
                result = await original_create(*args, **kwargs)
                return result
            finally:
                created = [
                    model for model in documents(self.app)
                    if not any(int(self.app.IsSame(model, old)) == 1 for old in before)
                ]
                for model in created:
                    if str(model.GetPathName()) != "":
                        raise RuntimeError("disposable part unexpectedly has a saved path")
                    self.owned.append(model)
                if len(created) != 1:
                    raise RuntimeError(f"create_part produced {len(created)} new documents, expected one")
        stack.enter_context(patch.object(self.adapter, "create_part", create_part))
        for method in ("add_line", "add_sketch_constraint", "add_sketch_dimension", "create_sketch", "exit_sketch"):
            original = getattr(self.adapter, method)
            self.originals[method] = original

            async def observed(*args, _name=method, _original=original, **kwargs):
                if not self.active:
                    return await _original(*args, **kwargs)
                actual = args
                if self.reverse_angle and _name == "add_sketch_dimension" and args[2] == "angular":
                    actual = (args[1], args[0], *args[2:])
                event = {
                    "kind": "adapter", "method": _name,
                    "requested": args, "actual": actual,
                    "before": observe(self.snapshot),
                }
                self.case["events"].append(event)
                try:
                    result = await _original(*actual, **kwargs)
                    event["result"] = {"is_success": bool(result.is_success), "data": str(result.data), "error": str(result.error)}
                    return result
                except Exception as error:
                    event["error"] = f"{type(error).__name__}: {error}"
                    raise
                finally:
                    event["after"] = observe(self.snapshot)
            stack.enter_context(patch.object(self.adapter, method, observed))

    async def references(self, adapter, dimensions, *, starts=None, planes=None):
        self.active = True
        original_guard = reference.ensure_fully_defined

        async def guard(*args, **kwargs):
            self.case["before_strict_guard"] = observe(self.snapshot)
            await original_guard(*args, **kwargs)
            raise ProbeBoundary()
        try:
            with patch.object(reference, "ensure_fully_defined", guard):
                await reference.add_supplier_reference_sketch(adapter, dimensions, starts=starts, planes=planes)
        except ProbeBoundary:
            self.case["guard"] = "passed"
        except RuntimeError as error:
            self.case["guard"] = "refused"
            self.case["guard_error"] = str(error)
        finally:
            self.case["final"] = observe(self.snapshot)
            self.active = False

    async def saver(self, adapter, _name, _suppressed, **settings):
        await self.references(adapter, **settings)
        return {}

    async def nut_boundary(self, *args, **kwargs):
        await self.references(*args, **kwargs)
        raise ProbeBoundary()

    def close_owned(self):
        opened = documents(self.app)
        if any(not any(int(self.app.IsSame(doc, owned)) == 1 for owned in self.owned) for doc in opened):
            raise RuntimeError("foreign native document appeared; refusing broad cleanup")
        for model in reversed(self.owned):
            if not any(int(self.app.IsSame(doc, model)) == 1 for doc in documents(self.app)):
                continue
            title = str(model.GetTitle())
            if not title or str(model.GetPathName()) != "":
                raise RuntimeError("owned disposable document identity changed before cleanup")
            self.app.CloseDoc(title)  # VT_VOID; document inventory is the success channel.
            if any(int(self.app.IsSame(doc, model)) == 1 for doc in documents(self.app)):
                raise RuntimeError(f"owned document failed to close: {title}")
        self.owned.clear()
        self.adapter.currentModel = None
        self.adapter.currentSketch = None
        self.adapter.currentSketchManager = None
        self.adapter._reset_sketch_entity_registry()
        if documents(self.app):
            raise RuntimeError("native document inventory not empty after owned cleanup")


async def probe(adapter):
    app = _early_bound(adapter.swApp, "ISldWorks")
    if documents(app):
        raise RuntimeError("owned diagnostic requires an EMPTY initial document inventory")
    if app.UserControl is not True:
        raise RuntimeError("refusing last-document cleanup on a background-owned SolidWorks server")
    default_template = str(app.GetUserPreferenceStringValue(8))
    if not default_template or digest(default_template) != digest(PART_TEMPLATE):
        raise RuntimeError("seat default part template bytes differ from frozen production PRTDOT")
    toggles = {key: app.GetUserPreferenceToggle(key) for key in (9, 95, 249, 10, 372, 520)}
    expected = {9: True, 95: True, 249: True, 10: False, 372: False, 520: False}
    if any(type(toggles[key]) is not bool or toggles[key] != expected[key] for key in expected):
        raise RuntimeError(f"seat preferences do not match production automation baseline: {toggles!r}")
    source_hashes = {name: digest(ROOT / name) for name in SOURCE_PATHS}
    report = {
        "schema": "harmonic-analyzer/supplier-sketch-probe@1", "frozen_base": BASE,
        "started_utc": datetime.now(UTC).isoformat(), "host": socket.gethostname(),
        "pid": int(app.GetProcessID()), "revision": str(app.RevisionNumber()),
        "frame": [int(app.FrameWidth), int(app.FrameHeight)],
        "default_template": default_template, "preference_toggles": toggles,
        "source_sha256": source_hashes, "cases": [],
        "publication": "private diagnostic JSON only; no native saves or production cache keys",
    }
    before_outputs = output_inventory()
    recorder = Recorder(adapter, report)
    fatal = None
    try:
        with ExitStack() as stack:
            recorder.install(stack)
            stack.enter_context(patch.object(riser, "save_supplier_reference_part", recorder.saver))
            stack.enter_context(patch.object(nut, "add_supplier_reference_sketch", recorder.nut_boundary))
            for name, recipe, reverse, sparse in (
                ("P_isolated_horizontal", None, False, False),
                ("A_riser_incident", riser, False, False),
                ("B_riser_ray_first_only", riser, True, False),
                ("C_nut_incident", nut, False, False),
                ("D_nut_no_redundant_diameter_anchors_only", nut, False, True),
            ):
                recorder.case = {"name": name, "events": []}
                report["cases"].append(recorder.case)
                recorder.reverse_angle = reverse
                with ExitStack() as case_stack:
                    if sparse:
                        anchor = reference._anchor

                        async def sparse_anchor(adapter, dims, entity, start, label):
                            if label in {"SupplierBodyDiameter", "SupplierFlangeDiameter"}:
                                recorder.case.setdefault("omitted_origin_anchors", []).append(label)
                                return
                            await anchor(adapter, dims, entity, start, label)
                        case_stack.enter_context(patch.object(reference, "_anchor", sparse_anchor))
                    try:
                        if recipe is None:
                            created = await adapter.create_part()
                            if not created.is_success:
                                raise RuntimeError(f"positive-control part creation failed: {created.error}")
                            await recorder.references(adapter, (("PositiveLength", 5.0, "horizontal"),), starts={"PositiveLength": (20.0, 20.0)})
                        else:
                            try:
                                await recipe.build(adapter)
                            except ProbeBoundary:
                                pass
                        if "guard" not in recorder.case:
                            raise RuntimeError(f"{name}: recipe never reached the declared sketch guard")
                    finally:
                        recorder.close_owned()
                print("SUPPLIER_PROBE_CASE " + json.dumps({key: value for key, value in recorder.case.items() if key not in {"events", "final", "before_strict_guard"}}, default=str), flush=True)
        if report["cases"][0]["guard"] != "passed":
            raise RuntimeError("isolated linear positive control did not pass strict fully-defined guard")
    except Exception as error:
        fatal = error
        report["fatal"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            recorder.close_owned()
        except Exception as error:
            fatal = error
            report["cleanup_error"] = f"{type(error).__name__}: {error}"
            report["fatal"] = report["cleanup_error"]
        report["final_document_count"] = observe(lambda: int(app.GetDocumentCount()))
        report["final_pid"] = observe(lambda: int(app.GetProcessID()))
        report["final_toggles"] = observe(
            lambda: {key: app.GetUserPreferenceToggle(key) for key in expected}
        )
        report["source_preserved"] = source_hashes == {name: digest(ROOT / name) for name in SOURCE_PATHS}
        report["unexpected_output_changes"] = sorted(set(before_outputs.items()) ^ set(output_inventory().items()))
        report["finished_utc"] = datetime.now(UTC).isoformat()
        if report["final_document_count"] != 0 or report["final_pid"] != report["pid"] or report["final_toggles"] != toggles or not report["source_preserved"] or report["unexpected_output_changes"]:
            fatal = RuntimeError("diagnostic ownership/source/preferences/output invariant failed")
            report["fatal"] = str(fatal)
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
        print("SUPPLIER_PROBE_SUMMARY " + json.dumps({"report": str(REPORT), "cases": [{"name": case["name"], "guard": case.get("guard"), "error": case.get("guard_error")} for case in report["cases"]], "fatal": report.get("fatal")}), flush=True)
    if fatal is not None:
        raise fatal
    return {"report": str(REPORT)}


if __name__ == "__main__":
    require_owned_diagnostic_environment()
    sys.exit(run_owned_diagnostic(probe))

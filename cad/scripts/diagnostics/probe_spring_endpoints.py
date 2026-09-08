"""Read named spring definitions and evaluated endpoints on one owned bytecopy.

No selection, edits, rebuild, redraw, save or export. A captured report proves
the documented getters returned data, not that the spring is one connected wire.
Direct helix endpoints are not exposed by the documented IHelixFeatureData API.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, _iter_features, check  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics import _raw_edge_curve as raw  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics._owned_native_documents import DocumentState, run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics.probe_spring_mesh_gap import SOURCE_SHA256, digest  # noqa: E402
from solidworks_mcp.adapters.com_variant import double_array  # noqa: E402

ADAPTER_REVISION = "25bc99b1ae39d8c0e004867e9b5c0f2068f2abc2"
FEATURES = {
    "Helix/Spiral1": "Helix", "HelixBaseProfile": "ProfileFeature",
    "WireProfile": "ProfileFeature", "CoilBody": "Sweep",
}


def native_same(app, first, second, row, key):
    if first is None or second is None:
        raise RuntimeError(f"{key}: null native identity operand")
    row[key] = app.IsSame(first, second)
    raw.integer(row[key], 0, 1, key)
    return row[key]


def current(adapter, model, path, row):
    adapter.ownership.assert_current_owned()
    for label, actual in (("current", adapter.currentModel), ("active", adapter.swApp.ActiveDoc),
                          ("named", adapter.swApp.GetOpenDocumentByName(str(path)))):
        if native_same(adapter.swApp, model, actual, row, label) != 1:
            raise RuntimeError(f"{label}: owned spring native identity changed")
    row["path"] = model.GetPathName()
    row["title"] = model.GetTitle()
    row["kind"] = model.GetType()
    row["dirty"] = model.GetSaveFlag()
    raw.integer(row["kind"], 1, 1, "part document type")
    raw.boolean(row["dirty"], "source dirty flag")
    if (type(row["path"]) is not str or Path(row["path"]).resolve() != path
            or type(row["title"]) is not str or not row["title"]):
        raise RuntimeError("wrong native source-copy path/title")
    return DocumentState.DIRTY if row["dirty"] else DocumentState.CLEAN


def object_array(value, row, key, interface, maximum):
    row[key] = {"return_type": type(value).__name__,
                "count": len(value) if isinstance(value, (tuple, list)) else None}
    if value is None:
        row[key]["result"] = None
    values = raw.sequence(value, label=key, maximum=maximum)
    if any(item is None for item in values):
        raise RuntimeError(f"{key}: null native array member")
    return [_early_bound(item, interface) for item in values]


def required_interface(value, row, key, interface):
    row[key] = "null" if value is None else "returned"
    if value is None:
        raise RuntimeError(f"{key}: native interface unavailable")
    return _early_bound(value, interface)


def features(adapter, row):
    found, inventory = {}, []
    row["inventory"] = inventory
    for index, feature in enumerate(_iter_features(adapter)):
        if index >= 256:
            raise RuntimeError("spring feature traversal exceeded 256 entries")
        entry = {"index": index}
        inventory.append(entry)
        entry["name"] = feature.Name
        entry["kind"] = feature.GetTypeName2()
        if type(entry["name"]) is not str or type(entry["kind"]) is not str:
            raise RuntimeError("feature name/type is not native text")
        name = entry["name"]
        if name not in FEATURES:
            continue
        if name in found or entry["kind"] != FEATURES[name]:
            raise RuntimeError(f"ambiguous or wrong-type named feature: {name}")
        if native_same(adapter.swApp, feature, feature, entry, "self_identity") != 1:
            raise RuntimeError(f"named feature self-identity failed: {name}")
        found[name] = feature
    if found.keys() != FEATURES.keys():
        raise RuntimeError(f"missing exact spring features: {sorted(FEATURES.keys() - found.keys())}")
    return found


def helix(feature, row):
    definition = required_interface(feature.GetDefinition(), row, "GetDefinition", "IHelixFeatureData")
    for name in ("DefinedBy", "Height", "Pitch", "Revolution", "StartingAngle",
                 "Clockwise", "ReverseDirection", "VariablePitch", "Taper", "TaperAngle", "TaperOutward"):
        row[name] = getattr(definition, name)
    raw.integer(row["DefinedBy"], 0, 3, "helix definition")
    for name in ("Height", "Pitch", "Revolution", "StartingAngle", "TaperAngle"):
        raw.numbers((row[name],), 1, name)
    for name in ("Clockwise", "ReverseDirection", "VariablePitch", "Taper", "TaperOutward"):
        raw.boolean(row[name], name)
    row["direct_endpoints"] = "not measured: documented IHelixFeatureData has no endpoint getter"


def profile(adapter, feature, row):
    sketch = required_interface(feature.GetSpecificFeature2(), row, "GetSpecificFeature2", "ISketch")
    transform = required_interface(sketch.ModelToSketchTransform, row, "ModelToSketchTransform", "IMathTransform")
    row["model_to_sketch"] = transform.ArrayData
    raw.numbers(row["model_to_sketch"], 16, "model-to-sketch transform")
    segments = object_array(sketch.GetSketchSegments(), row, "GetSketchSegments", "ISketchSegment", 1)
    curve = required_interface(segments[0].GetCurve(), row, "GetCurve", "ICurve")
    row["identity"] = curve.Identity()
    row["is_circle"] = curve.IsCircle()
    raw.integer(row["identity"], 3002, 3002, "profile circle identity")
    if row["is_circle"] is not True:
        raise RuntimeError("named profile did not return a native circle")
    row["circle_sketch_space"] = curve.CircleParams
    raw.numbers(row["circle_sketch_space"], 7, "profile circle")
    # Official Evaluate Curves Defined in Sketch Space example: invert the
    # model-to-sketch transform, then transform a new math point. No edit mode.
    inverse = required_interface(transform.Inverse(), row, "Inverse", "IMathTransform")
    row["sketch_to_model"] = inverse.ArrayData
    raw.numbers(row["sketch_to_model"], 16, "sketch-to-model transform")
    utility = required_interface(adapter.swApp.GetMathUtility(), row, "GetMathUtility", "IMathUtility")
    point = required_interface(utility.CreatePoint(double_array(row["circle_sketch_space"][:3])),
                               row, "CreatePoint", "IMathPoint")
    transformed = required_interface(point.MultiplyTransform(inverse), row, "MultiplyTransform", "IMathPoint")
    row["circle_center_model_space"] = transformed.ArrayData
    raw.numbers(row["circle_center_model_space"], 3, "native transformed profile center")


def solid_bodies(adapter, model, row):
    bodies = object_array(_early_bound(model, "IPartDoc").GetBodies2(0, False),
                          row, "GetBodies2_all_solids", "IBody2", 16)
    row["bodies"] = entries = []
    for index, body in enumerate(bodies):
        entry = {"index": index}
        entries.append(entry)
        entry["name"] = body.Name
        entry["kind"] = body.GetType()
        raw.integer(entry["kind"], 0, 0, "solid body type")
        if type(entry["name"]) is not str or not entry["name"]:
            raise RuntimeError("body name is not native text")
        entry["identity_to_bank"] = [adapter.swApp.IsSame(body, other) for other in bodies]
        for value in entry["identity_to_bank"]:
            raw.integer(value, 0, 1, "body identity")
        if entry["identity_to_bank"] != [int(index == other) for other in range(len(bodies))]:
            raise RuntimeError("all-solid inventory contains substituted or duplicate native bodies")
        entry["approximate_box"] = body.GetBodyBox()
        raw.numbers(entry["approximate_box"], 6, "approximate body box")
    return bodies


def edge_endpoint(edge, row):
    curve = required_interface(edge.GetCurve(), row, "GetCurve", "ICurve")
    row["identity"] = curve.Identity()
    row["is_circle"] = curve.IsCircle()
    raw.integer(row["identity"], 3001, 3009, "curve identity")
    raw.boolean(row["is_circle"], "curve circle predicate")
    trim = required_interface(edge.GetCurveParams3(), row, "GetCurveParams3", "ICurveParamData")
    for name in ("CurveType", "CurveTag", "Sense", "UMinValue", "UMaxValue", "StartPoint", "EndPoint"):
        row[name] = getattr(trim, name)
    raw.integer(row["CurveType"], 3001, 3009, "trim curve type")
    raw.integer(row["CurveTag"], -2147483648, 2147483647, "trim curve tag")
    raw.boolean(row["Sense"], "trim sense")
    raw.numbers((row["UMinValue"], row["UMaxValue"]), 2, "edge parameter interval")
    raw.numbers(row["StartPoint"], 3, "native start point")
    raw.numbers(row["EndPoint"], 3, "native end point")
    if row["UMinValue"] >= row["UMaxValue"]:
        raise RuntimeError("edge parameter interval is not increasing")
    if row["is_circle"]:
        row["circle_model_space"] = curve.CircleParams
        raw.numbers(row["circle_model_space"], 7, "native circle parameters")


def coil_faces(adapter, feature, bodies, row, checkpoint):
    faces = object_array(feature.GetFaces(), row, "GetFaces", "IFace2", 64)
    row["faces"] = entries = []
    total_edges = 0
    for index, face in enumerate(faces):
        entry = {"index": index}
        entries.append(entry)
        body = required_interface(face.GetBody(), entry, "GetBody", "IBody2")
        entry["body_identity"] = [adapter.swApp.IsSame(body, item) for item in bodies]
        for value in entry["body_identity"]:
            raw.integer(value, 0, 1, "face body identity")
        if sum(entry["body_identity"]) != 1:
            raise RuntimeError("CoilBody face does not belong to one enumerated solid body")
        surface = required_interface(face.GetSurface(), entry, "GetSurface", "ISurface")
        entry["surface_identity"] = surface.Identity()
        raw.integer(entry["surface_identity"], 4001, 4010, "surface identity")
        if entry["surface_identity"] == 4001:
            entry["plane_model_space"] = surface.PlaneParams
            raw.numbers(entry["plane_model_space"], 6, "native plane parameters")
        edges = object_array(face.GetEdges(), entry, "GetEdges", "IEdge", 64)
        total_edges += len(edges)
        if total_edges > 256:
            raise RuntimeError("CoilBody endpoint read budget exceeded 256 face-edge occurrences")
        entry["edges"] = edge_rows = []
        for edge in edges:
            edge_row = {}
            edge_rows.append(edge_row)
            try:
                edge_endpoint(edge, edge_row)
            except BaseException as error:
                edge_row["error"] = repr(error)
                raise
            finally:
                checkpoint()


def runtime():
    adapter = pilot.adapter_fingerprints()
    package = ROOT / "SolidworksMCP-python/src/solidworks_mcp"
    if Path(adapter["package_path"]).resolve() != package.resolve():
        raise RuntimeError("imported adapter originates outside this runtime checkout")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT / "SolidworksMCP-python",
                              check=True, capture_output=True, text=True).stdout.strip()
    if revision != ADAPTER_REVISION:
        raise RuntimeError("spring probe requires the reviewed adapter revision")
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=normal"],
                           cwd=ROOT, check=True, capture_output=True, text=True).stdout
    if dirty:
        raise RuntimeError("spring probe runtime must be a clean frozen checkout")
    return {"revision": pilot.benchmark.revision("HEAD"), "helpers": pilot.helper_fingerprints(),
            "adapter": adapter, "adapter_revision": revision, "executable": sys.executable}


async def probe(adapter, source, candidate, report_root):
    frozen = runtime()
    if candidate != frozen["revision"]:
        raise RuntimeError("spring probe candidate differs from current runtime")
    directory = Path(tempfile.mkdtemp(prefix="spring-endpoints-", dir=report_root))
    copied = directory / f"spring-{directory.name}.SLDPRT"
    token = source.with_name(f".{source.stem}.execution")
    path = directory / "endpoints.json"
    report = {"status": "running", "source": str(source), "copy": str(copied),
              "expected_source_sha256": SOURCE_SHA256, "runtime": frozen, "groups": {},
              "secondary_errors": [], "scope": "readback only; no geometry acceptance or save/export"}
    primary = None
    secondary = []
    model = None
    started = time.perf_counter()

    def checkpoint():
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def attempt(label, operation):
        try:
            operation()
        except BaseException as error:
            report["secondary_errors"].append({"phase": label, "error": repr(error)})
            secondary.append(error)

    def hashes(label):
        bank = report.setdefault("hashes", {}).setdefault(label, {})
        failures = []
        for key, read in ((str(source), lambda: digest(source)),
                          (str(copied), lambda: digest(copied)),
                          ("execution_token", lambda: token.read_text(encoding="utf-8"))):
            try:
                bank[key] = read()
                if bank[key].strip() != SOURCE_SHA256:
                    raise RuntimeError(f"{label}: original/copy/token changed: {key}")
            except BaseException as error:
                bank.setdefault("errors", []).append({"path": key, "error": repr(error)})
                failures.append(error)
        if failures:
            raise BaseExceptionGroup(f"{label}: spring input identity failures", failures)

    def group(name, operation):
        row = report["groups"][name] = {"status": "reading"}
        begin = time.perf_counter()
        try:
            if current(adapter, model, copied, row.setdefault("before", {})) is not DocumentState.CLEAN:
                raise RuntimeError("read-only spring copy was dirty before a getter group")
            checkpoint()
            with _telemetry.span("diagnostic.spring.read", group=name):
                value = operation(row)
            row["status"] = "captured"
            return value
        except BaseException as error:
            row.update(status="failed", error=repr(error))
            raise
        finally:
            def after():
                if current(adapter, model, copied, row.setdefault("after", {})) is not DocumentState.CLEAN:
                    raise RuntimeError(f"{name}: getter group changed source dirty state")
            attempt(f"{name}.after", after)
            row["seconds"] = time.perf_counter() - begin
            attempt(f"{name}.checkpoint", checkpoint)

    try:
        adapter.ownership.register_directory(directory)
        adapter.ownership.register_source(source)
        adapter.ownership.register_source(token)
        if digest(source) != SOURCE_SHA256 or token.read_text(encoding="utf-8").strip() != SOURCE_SHA256:
            raise RuntimeError("original source/token differ from the retained spring")
        shutil.copy2(source, copied)
        hashes("before_open")
        checkpoint()
        _telemetry.info("owned spring endpoint receipt", report=str(path))
        check("open owned spring copy", await adapter.open_model(str(copied)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        named = group("features", lambda row: features(adapter, row))
        bodies = group("solid_bodies", lambda row: solid_bodies(adapter, model, row))
        # Independent read groups retain useful evidence if one API is unsupported.
        for name, operation in (
            ("helix", lambda row: helix(named["Helix/Spiral1"], row)),
            ("base_profile", lambda row: profile(adapter, named["HelixBaseProfile"], row)),
            ("wire_profile", lambda row: profile(adapter, named["WireProfile"], row)),
            ("coil_faces", lambda row: coil_faces(adapter, named["CoilBody"], bodies, row,
                                                 lambda: attempt("edge_checkpoint", checkpoint))),
        ):
            try:
                group(name, operation)
            except Exception as error:
                if primary is None:
                    primary = error
                else:
                    secondary.append(error)
                report.setdefault("read_errors", []).append({"group": name, "error": repr(error)})
        hashes("before_close")
    except BaseException as error:
        if primary is None or not isinstance(error, Exception):
            if primary is not None:
                secondary.append(primary)
            primary = error
        else:
            secondary.append(error)
        report["error"] = repr(error)
    finally:
        if primary is not None:
            adapter.ownership.failure = repr(primary)
        try:
            await adapter.close_owned_documents()
        except BaseException as error:
            report["cleanup_error"] = repr(error)
            secondary.append(error)
        attempt("final_hashes", lambda: hashes("after_close"))
        def runtime_guard():
            report["runtime_final"] = runtime()
            if report["runtime_final"] != frozen:
                raise RuntimeError("frozen native probe inputs changed")
        attempt("runtime_final", runtime_guard)
        attempt("ownership_final", adapter.ownership.checkpoint)
        report.update(status="failed" if primary is not None or secondary else "captured",
                      seconds=time.perf_counter() - started,
                      errors=[repr(error) for error in ([primary] if primary is not None else []) + secondary])
        attempt("final_checkpoint", checkpoint)
    if primary is not None:
        for error in secondary:
            primary.add_note(f"secondary spring diagnostic failure: {error!r}")
        raise primary
    if secondary:
        raise BaseExceptionGroup("spring readback/final guard failures", secondary)
    return {"report": str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    pid = os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "")
    if not pid.isdecimal() or int(pid) <= 0:
        raise RuntimeError("spring probe requires an explicitly confirmed current native PID")
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise RuntimeError("spring probe requires remote cache off")
    source = args.source.resolve(strict=True)
    if source.name != "channel-spring-installed.SLDPRT" or digest(source) != SOURCE_SHA256:
        raise RuntimeError("spring probe requires the exact named, pinned source")
    if source.with_name(f".{source.stem}.execution").read_text(encoding="utf-8").strip() != SOURCE_SHA256:
        raise RuntimeError("spring probe requires the pinned source execution token")
    candidate = pilot.benchmark.revision(args.candidate)
    if runtime()["revision"] != candidate:
        raise RuntimeError("candidate must be the exact current frozen runtime")
    if not args.worker:
        import dodo
        dodo._run([sys.executable, str(Path(__file__).resolve()), "--worker", "--source", str(source),
                   "--candidate", candidate, "--report-root", str(args.report_root.resolve())],
                  "owned spring endpoint readback", com=True, log_stem="spring-endpoints")
        return 0
    args.report_root.mkdir(parents=True, exist_ok=True)
    return run_copy_diagnostic(lambda adapter: probe(adapter, source, candidate, args.report_root.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())

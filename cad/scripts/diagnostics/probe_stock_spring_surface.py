"""Compare supplier and replica native swept-wire surfaces without saving either.

    uv run python cad/scripts/diagnostics/probe_stock_spring_surface.py

Six measured baseline interference-boundary witnesses are retained in the FREE
catalogue end frame. They are test queries, NOT placement offsets or corrections.
The replica queries translate with counter_spring_stock_geom.end_centers_mm at
counter_spring_spec.INSTALLED_LENGTH_MM. Rebuilds are intentionally UNSAVED.
Native curve distance minus nominal wire radius is an envelope diagnostic, not
an exact swept-surface or contact-interference calculation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import dodo
import _telemetry
import counter_spring_spec
import counter_spring_stock_geom as stock
from _common import _early_bound, _read_member, check, run_build

ROOT = Path(__file__).resolve().parents[3]

# Measured on the baseline boundary at installed L=351.4494413474412 mm,
# then translated by -48.72472067372061 mm in X to the FREE catalogue frame.
# Provenance: supplier positive-control experiment, 2026-09-14. These fixed
# witnesses reproduce a surface discrepancy; they do not define spring geometry.
FREE_WITNESSES_MM = (
    ("x-", (127.00144346556274, -0.0236548002502412, 0.7960869821921452)),
    ("x+", (126.99853369774812, 0.01676424819688153, 0.6362944515688995)),
    ("y-", (126.99280700831807, -0.16396893442355104, 0.7261832624069542)),
    ("y+", (126.99861990954597, 4.592272314124347e-13, 0.6367293410175097)),
    ("z-", (126.99305976344422, 0.15693872641667556, 0.7060408559913891)),
    ("z+", (126.99280700831872, -0.16396893441592203, 0.7261832624065296)),
)
SWEEP_PROPERTIES = (
    "AlignWithEndFaces", "AdvancedSmoothing", "CircularProfile",
    "CircularProfileDiameter", "Direction", "EndTangencyType", "MaintainTangency",
    "Merge", "MergeSmoothFaces", "PathAlignmentType", "StartTangencyType",
    "TangentPropagation", "TwistControlType", "FeatureScope", "AutoSelect", "ThinFeature",
)
HELIX_PROPERTIES = (
    "Clockwise", "DefinedBy", "Height", "Pitch", "ReverseDirection",
    "Revolution", "StartingAngle", "VariablePitch",
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def feature(part, name):
    raw = part.FeatureByName(name)
    if raw is None:
        raise RuntimeError("missing native feature " + name)
    return _early_bound(raw, "IFeature")


def evaluation(curve, parameter):
    data = [float(value) for value in curve.Evaluate2(parameter, 1)]
    if len(data) != 7 or struct.unpack("<II", struct.pack("<d", data[-1]))[0] != 1:
        raise RuntimeError(f"ICurve.Evaluate2 failed: {data}")
    return {"point_mm": [value * 1000 for value in data[:3]],
            "derivative_m_per_parameter": data[3:6]}


def sketch_point(raw):
    point = _early_bound(raw, "ISketchPoint")
    return [float(_read_member(point, key)) * 1000 for key in ("X", "Y", "Z")]


@_telemetry.traced("diagnostic.stock_spring_surface", label_param="kind")
def snapshot(doc, kind, phase, queries):
    # Every invocation acquires fresh topology; none survives ForceRebuild3.
    part = _early_bound(doc, "IPartDoc")
    sweep_name, helix_name, profile_name = (
        ("Sweep3", "Helix/Spiral4", "Sketch38") if kind == "vendor"
        else ("LoopPos", "LoopHelixPos", "ProfileLoopPos")
    )
    sweep_data = _early_bound(feature(part, sweep_name).GetDefinition(), "ISweepFeatureData")
    helix_feature = feature(part, helix_name)
    helix_data = _early_bound(helix_feature.GetDefinition(), "IHelixFeatureData")
    sketch = _early_bound(feature(part, profile_name).GetSpecificFeature2(), "ISketch")
    row = {
        "kind": kind, "phase": phase, "save_flag": bool(doc.GetSaveFlag()),
        "sweep_name": sweep_name, "helix_name": helix_name, "profile_name": profile_name,
        "sweep_settings": {key: _read_member(sweep_data, key) for key in SWEEP_PROPERTIES},
        "helix_settings": {key: _read_member(helix_data, key) for key in HELIX_PROPERTIES},
        "profile_model_to_sketch": list(_read_member(_read_member(sketch, "ModelToSketchTransform"), "ArrayData")),
        "actual_profile_segments": [], "points": [],
    }
    for raw in sketch.GetSketchSegments() or []:
        segment = _early_bound(raw, "ISketchSegment")
        segment_type = int(segment.GetType())
        record = {"segment_type": segment_type}
        if segment_type == 1:  # swSketchARC, including circles
            arc = _early_bound(segment, "ISketchArc")
            record.update({
                "radius_mm": float(arc.GetRadius()) * 1000,
                "diameter_mm": float(arc.GetRadius()) * 2000,
                "center_sketch_mm": sketch_point(arc.GetCenterPoint2()),
                "start_sketch_mm": sketch_point(arc.GetStartPoint2()),
                "end_sketch_mm": sketch_point(arc.GetEndPoint2()),
            })
        row["actual_profile_segments"].append(record)

    reference = _early_bound(helix_feature.GetSpecificFeature2(), "IReferenceCurve")
    # REQUIRED ownership: retain the segment list while its ICurves are queried.
    # Letting these owning IEdges go out of scope broke the supplier control.
    segments = list(reference.GetSegments() or [])
    curves = []
    for index, raw in enumerate(segments):
        curve = _early_bound(_early_bound(raw, "IEdge").GetCurve(), "ICurve")
        end = curve.GetEndParams()
        if len(end) != 5 or not end[0]:
            raise RuntimeError(f"GetEndParams failed: {end}")
        low, high = sorted((float(end[1]), float(end[2])))
        curves.append((index, curve, low, high))
    if not curves:
        raise RuntimeError("no native helix curves: " + helix_name)
    row["helix_endpoints"] = [
        {"segment": index, "u_min": low, "u_max": high,
         "start": evaluation(curve, low), "end": evaluation(curve, high)}
        for index, curve, low, high in curves
    ]
    faces = []
    bodies = list(part.GetBodies2(0, False) or [])
    for body_index, raw_body in enumerate(bodies):
        for face_index, raw in enumerate(_early_bound(raw_body, "IBody2").GetFaces() or []):
            face = _early_bound(raw, "IFace2")
            owner = face.GetFeature()
            if owner is not None and str(_read_member(_early_bound(owner, "IFeature"), "Name")) == sweep_name:
                faces.append((body_index, face_index, face))
    if not faces:
        raise RuntimeError("no faces owned by " + sweep_name)

    def curve_nearest(point):
        candidates = []
        for index, curve, low, high in curves:
            hit = curve.GetClosestPointOn(*(value / 1000 for value in point))
            if hit is None or len(hit) != 5:
                raise RuntimeError("native helix nearest query failed")
            parameter = float(hit[3])
            for parameter in [low, high] + ([parameter] if low <= parameter <= high else []):
                value = evaluation(curve, parameter)
                candidates.append({"segment": index, "u": parameter, **value,
                                   "distance_mm": math.dist(point, value["point_mm"])})
        return min(candidates, key=lambda value: value["distance_mm"])

    for label, point in queries:
        surface = []
        for body_index, face_index, face in faces:
            hit = face.GetClosestPointOn(*(value / 1000 for value in point))
            if hit is None or len(hit) != 5:
                raise RuntimeError("native sweep-face nearest query failed")
            nearest = [float(value) * 1000 for value in hit[:3]]
            surface.append({"body_index": body_index, "face_index": face_index,
                            "point_mm": nearest, "distance_mm": math.dist(point, nearest)})
        surface.sort(key=lambda value: value["distance_mm"])
        native = curve_nearest(point)
        surface_native = curve_nearest(surface[0]["point_mm"])
        row["points"].append({
            "label": label, "query_local_mm": point,
            "nearest_native_helix": native,
            "query_native_curve_distance_minus_wire_radius_mm": native["distance_mm"] - stock.WIRE_RADIUS_MM,
            "nearest_native_sweep_faces": surface[:3],
            "nearest_surface_point_to_native_helix": surface_native,
            "nearest_surface_native_radius_excess_mm": surface_native["distance_mm"] - stock.WIRE_RADIUS_MM,
        })
    return row


async def probe(adapter, paths, output):
    length = counter_spring_spec.INSTALLED_LENGTH_MM
    free_eye = stock.end_centers_mm(stock.FREE_LENGTH_MM)[1]
    installed_eye = stock.end_centers_mm(length)[1]
    translation = [installed - free for installed, free in zip(installed_eye, free_eye, strict=True)]
    report = {
        "status": "started", "snapshots": [],
        "nominal_wire_radius_mm": stock.WIRE_RADIUS_MM,
        "witness_scope": "Measured baseline boundary queries, not placement offsets or design dimensions",
        "free_frame_witnesses_mm": FREE_WITNESSES_MM,
        "translation": {"installed_length_mm": length, "free_length_mm": stock.FREE_LENGTH_MM,
                        "free_to_replica_positive_end_mm": translation,
                        "authority": "counter_spring_stock_geom.end_centers_mm(counter_spring_spec.INSTALLED_LENGTH_MM)"},
        "input_sha256_before": {str(path): digest(path) for path in paths.values()},
        "input_sha256_after": {}, "rebuild_returns": {}, "comparisons": [],
    }
    owned = []
    try:
        for kind, path in paths.items():
            check("open " + kind, await adapter.open_model(str(path)))
            doc = _early_bound(adapter.currentModel, "IModelDoc2")
            title = str(doc.GetTitle())
            owned.append(title)
            queries = [(label, [value + (translation[index] if kind == "replica" else 0)
                                for index, value in enumerate(point)])
                       for label, point in FREE_WITNESSES_MM]
            report["snapshots"].append(snapshot(doc, kind, "as_opened", queries))
            # Do not save: the input-byte guard below is part of this experiment.
            report["rebuild_returns"][kind] = bool(doc.ForceRebuild3(False))
            report["snapshots"].append(snapshot(doc, kind, "after_unsaved_rebuild", queries))
            adapter.swApp.CloseDoc(title)
            owned.remove(title)
            adapter.currentModel = None
        for phase in ("as_opened", "after_unsaved_rebuild"):
            replica = next(row for row in report["snapshots"] if row["kind"] == "replica" and row["phase"] == phase)
            vendor = next(row for row in report["snapshots"] if row["kind"] == "vendor" and row["phase"] == phase)
            comparison = {
                "phase": phase,
                "sweep_setting_differences": {
                    key: {"replica": value, "vendor": vendor["sweep_settings"][key]}
                    for key, value in replica["sweep_settings"].items()
                    if value != vendor["sweep_settings"][key]
                }, "points": [],
            }
            for rp, vp in zip(replica["points"], vendor["points"], strict=True):
                replica_hit = rp["nearest_native_sweep_faces"][0]
                vendor_hit = vp["nearest_native_sweep_faces"][0]
                aligned = [value + shift for value, shift in zip(vendor_hit["point_mm"], translation, strict=True)]
                comparison["points"].append({
                    "label": rp["label"],
                    "query_to_replica_surface_mm": replica_hit["distance_mm"],
                    "translated_query_to_vendor_surface_mm": vendor_hit["distance_mm"],
                    "nearest_surface_points_separation_after_translation_mm": math.dist(replica_hit["point_mm"], aligned),
                    "vendor_surface_native_radius_excess_mm": vp["nearest_surface_native_radius_excess_mm"],
                    "replica_surface_native_radius_excess_mm": rp["nearest_surface_native_radius_excess_mm"],
                })
            report["comparisons"].append(comparison)
        report["status"] = "completed"
        return {"report": str(output)}
    except BaseException:
        report["status"] = "failed"
        report["error"] = traceback.format_exc()
        raise
    finally:
        try:
            for title in owned:
                adapter.swApp.CloseDoc(title)
        finally:
            report["input_sha256_after"] = {str(path): digest(path) for path in paths.values()}
            changed = report["input_sha256_before"] != report["input_sha256_after"]
            if changed:
                report["status"] = "failed"
                report["input_integrity_error"] = "Input file bytes changed during probe"
            output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            if changed:
                raise RuntimeError(report["input_integrity_error"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor", type=Path, default=ROOT / "cad/references/mcmaster/1330K524.SLDPRT")
    parser.add_argument("--replica", type=Path, default=ROOT / "cad/out/sldprt/counter-spring.SLDPRT")
    parser.add_argument("--output", type=Path, default=ROOT / "cad/out/reports/stock-spring-surface.json")
    args = parser.parse_args()
    paths = {"replica": args.replica.resolve(strict=True), "vendor": args.vendor.resolve(strict=True)}
    output = args.output.resolve()
    if output in paths.values():
        raise ValueError("report must not overwrite an input model")
    output.parent.mkdir(parents=True, exist_ok=True)
    with dodo._com_seat("probe-stock-spring-surface"):
        return run_build(lambda adapter: probe(adapter, paths, output))


if __name__ == "__main__":
    raise SystemExit(main())

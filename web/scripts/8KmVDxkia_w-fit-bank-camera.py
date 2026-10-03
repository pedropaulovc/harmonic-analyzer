#!/usr/bin/env python3
"""Fit the Synthesis bank close-up using physical terminal bevels, never annotations.

Run with the existing calibration Python environment. ``measure-fit`` decodes only
native FIT exposures; ``fit`` uses only those measured pixels and the parent's
actual-native world receipt. Freeze the resulting camera before ``measure-check``
or ``check``. CHECK pixels never select intrinsics, camera branches or source/native
feature associations. This producer does not modify generated source tracks.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

WEB = Path(__file__).resolve().parents[1]
VIDEO_ID = "8KmVDxkia_w"
LOCAL_POINT = [0.14524006843566895, 0.029294639825820923, 0.0]
# Each rectangle contains one physically identified bright terminal bevel. Its
# upper edge is localized independently of the colored explanatory annotations.
# Rectangle coordinates are original 1920x1080 pixels, not display pixels.
FIT_RECTS = {
    2541: {
        1: [797, 185, 22, 42], 2: [822, 207, 22, 44],
        3: [849, 221, 23, 46], 4: [876, 243, 23, 45],
        5: [898, 259, 21, 43], 6: [926, 282, 24, 47],
        7: [957, 300, 20, 53], 8: [977, 321, 22, 44],
        9: [1005, 343, 23, 46], 11: [1057, 388, 24, 44],
        12: [1084, 410, 21, 43], 13: [1109, 428, 24, 46],
        14: [1140, 452, 23, 46], 15: [1170, 479, 24, 46],
        16: [1196, 505, 23, 44], 17: [1223, 524, 23, 49],
        18: [1249, 548, 24, 45],
    },
    2589: {
        1: [780, 294, 21, 41], 2: [801, 335, 21, 45],
        3: [827, 365, 22, 44], 4: [854, 399, 20, 44],
        5: [872, 427, 21, 43], 6: [901, 457, 22, 46],
        8: [951, 495, 22, 42], 9: [979, 513, 22, 45],
        11: [1034, 536, 21, 39], 12: [1063, 538, 19, 40],
        13: [1090, 535, 23, 47], 14: [1122, 542, 22, 44],
        15: [1156, 545, 22, 45],
    },
}


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, packet):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(packet, indent=2, allow_nan=False) + "\n")


def source_metadata(video):
    authority = load(WEB / f"content/{VIDEO_ID}.automatic-motion-evidence.json")
    source = authority["source"]
    if digest(video) != source["sha256"]:
        raise ValueError("Original source video hash differs")
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp", "-of", "json", str(video),
    ]))
    pts = [int(row["best_effort_timestamp"]) for row in probe["frames"]]
    if len(pts) != source["decodedFrameCount"] or pts != [i * 1001 for i in range(len(pts))]:
        raise ValueError("Original native PTS sequence differs")
    return source, authority["model"]


def observe_bevel(image, rect):
    x, y, width, height = rect
    crop = image[y:y + height, x:x + width]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    saturation = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 1]
    mask = np.uint8((gray > 185) & (saturation < 70)) * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    candidates = [i for i in range(1, count) if 90 < stats[i, 4] < 700
                  and 6 <= stats[i, 2] <= 26 and 15 <= stats[i, 3] <= 50]
    if len(candidates) != 1:
        raise ValueError(f"Bevel rectangle is not uniquely observed: {rect}/{len(candidates)}")
    label = candidates[0]
    sx, sy, sw, sh, area = stats[label]
    _, xx = np.where(labels[sy:sy + 3, sx:sx + sw] == label)
    return [float(x + sx + np.mean(xx)), float(y + sy)], {
        "componentBoundsPixels": [int(x + sx), int(y + sy), int(sw), int(sh)],
        "componentAreaPixels": int(area), "grayThreshold": 185,
        "maximumSaturation": 69, "upperEdgeLocalizationRows": 3,
    }


def measure(video, output, rectangles, role):
    source, model = source_metadata(video)
    cap = cv2.VideoCapture(str(video))
    if abs(cap.get(cv2.CAP_PROP_FPS) - 24000 / 1001) > 1e-9:
        raise ValueError("Source decoder FPS differs")
    rows = []
    for index, stations in rectangles.items():
        index = int(index)
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok or image.shape != (1080, 1920, 3):
            raise ValueError(f"Missing original native source image {index}")
        identity = {"frameIndex": index, "nativePts": index * 1001,
                    "sourceSha256": source["sha256"], "width": 1920, "height": 1080,
                    "pixelFormat": "bgr8", "sha256Bgr8": hashlib.sha256(image.tobytes()).hexdigest()}
        for station, rect in stations.items():
            station = int(station)
            pixel, localization = observe_bevel(image, rect)
            rows.append({"role": role, "physicalStationIndex": station,
                         "harmonicNumber": 20 - station,
                         "partPath": f"harmonic-analyzer/channel/rocker-arm-{station + 1}",
                         "sourceImage": identity, "timeSeconds": index * 1001 / 24000,
                         "pixel": pixel, "uncertaintyPx": 6, "rectSourcePixels": rect,
                         "method": "physical-gray-bevel-upper-edge",
                         "measurementEvidence": localization})
    cap.release()
    packet = {"schemaVersion": 1, "videoId": VIDEO_ID, "source": source, "model": model,
              "feature": {"id": "rocker-terminal-bevel-upper-edge-midpoint",
                          "partLocalMetres": LOCAL_POINT,
                          "nativeGeometryEvidence": "Released raw GLB rocker-arm POSITION accessor88: upper edge of terminal bevel at x0.14524006843566895/y0.029294639825820923, z endpoints +/−0.00125m. Midpoint is a chosen visible-feature association, subject to actual native surface inspection; not the missing lower-rocker face bores or connecting-rod head.",
                          "sourceAssociation": "Count physical terminal strips far H20 to nearest H1 in native station order. FIT rectangles exclude annotation-covered strips. No explanatory curve/label pixels, interpolated source pixels or old H20 boundary/H1 joint CHECK pixels enter this objective.",
                          "uncertaintyMeaning": "Blur/threshold/edge midpoint and visible-face localization; geometry association uncertainty is separate and remains unqualified."},
              "rows": rows,
              "acceptance": {"cameraGeometryOrGpuAccepted": False}}
    save(output, packet)
    print(json.dumps({"output": str(output), "role": role, "measurementCount": len(rows),
                      "nativeExposures": sorted({r["sourceImage"]["frameIndex"] for r in rows})}))


def world_rows(receipt):
    result = {}
    for frame in receipt["rows"]:
        if abs(frame["timeSeconds"] - frame["frameIndex"] * 1001 / 24000) > 1e-9:
            raise ValueError("Actual-native receipt frame clock differs")
        for point in frame["worldPoints"]:
            key = (frame["frameIndex"], point["physicalStationIndex"])
            if (key in result or point["partPath"] != f"harmonic-analyzer/channel/rocker-arm-{key[1] + 1}"
                    or point["partLocalMetres"] != LOCAL_POINT):
                raise ValueError("Duplicate or misassociated actual-native world point")
            xyz = np.array(point["worldMetres"], dtype=float)
            if xyz.shape != (3,) or not np.all(np.isfinite(xyz)):
                raise ValueError("Invalid actual-native world point")
            result[key] = xyz
    return result


def joined(packet, receipt, role):
    for frame in receipt["rows"]:
        provenance = frame["snapshot"]["modelProvenance"]
        if (provenance["sourceSha256"] != packet["model"]["sha256"]
                or provenance["sourceCommit"] != packet["model"]["sourceCommit"]
                or provenance["identity"] != "matched"
                or frame["snapshot"]["videoId"] != VIDEO_ID
                or frame["capture"]["viewId"] != "main"
                or frame["capture"]["presentation"] != "native"
                or frame["capture"]["imagePlaneWarp"] is not None):
            raise ValueError("Actual-native receipt model/source/view association differs")
    worlds = world_rows(receipt)
    rows = [row for row in packet["rows"] if row["role"] == role]
    xyz = np.array([worlds[(row["sourceImage"]["frameIndex"], row["physicalStationIndex"])] for row in rows])
    pixels = np.array([row["pixel"] for row in rows], dtype=float)
    return rows, xyz, pixels


def projection_module():
    spec = importlib.util.spec_from_file_location("source_camera_solver", WEB / "scripts/fit-source.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def camera_parameters(camera):
    world_to_cv = np.diag([1., -1., -1.]) @ Rotation.from_quat(camera["quaternion"]).as_matrix().T
    position = np.array(camera["positionMetres"])
    return np.r_[Rotation.from_matrix(world_to_cv).as_rotvec(), -world_to_cv @ position,
                 math.log(1080 / (2 * math.tan(math.radians(camera["verticalFovDegrees"]) / 2)))]


def metrics(errors):
    return {"count": len(errors), "rmsPx": float(np.sqrt(np.mean(errors ** 2))),
            "medianPx": float(np.median(errors)), "maxPx": float(np.max(errors))}


def fit(evidence, native, output):
    packet, receipt = load(evidence), load(native)
    if {r["role"] for r in packet["rows"]} != {"fit"}:
        raise ValueError("Camera optimization accepts a FIT-only source packet")
    rows, xyz, pixels = joined(packet, receipt, "fit")
    solver = projection_module()
    minimum_focal = 1080 / (2 * math.tan(math.radians(120) / 2))
    maximum_focal = 1080 / (2 * math.tan(math.radians(3) / 2))
    lower = np.r_[[-np.inf] * 6, math.log(minimum_focal)]
    upper = np.r_[[np.inf] * 6, math.log(maximum_focal)]

    def residual(parameters):
        projected, depths = solver.project(parameters, xyz, 1920, 1080)
        return np.r_[(projected - pixels).ravel(), np.minimum(depths - .001, 0) * 1920]

    candidates = []
    # Same FIT-only PnP initialization and pinhole bounds as fit-source.py. The
    # bounded moving-bank point set is new; this is not the rejected whole-scene
    # guide/foot/hanger camera family, and CHECK cannot select among candidates.
    for focal in (768., 1344., 1920., 3456., 5760.):
        intrinsic = np.array([[focal, 0., 960.], [0., focal, 540.], [0., 0., 1.]])
        for flag in (cv2.SOLVEPNP_ITERATIVE, cv2.SOLVEPNP_SQPNP):
            try:
                ok, rotation, translation = cv2.solvePnP(xyz, pixels, intrinsic, None, flags=flag)
            except cv2.error:
                continue
            if not ok:
                continue
            result = least_squares(residual, np.r_[rotation.ravel(), translation.ravel(), math.log(focal)],
                                   bounds=(lower, upper), max_nfev=1200)
            _, depths = solver.project(result.x, xyz, 1920, 1080)
            if result.success and np.all(depths > .001):
                candidates.append(result)
    if not candidates:
        raise ValueError("No converged positive-depth FIT camera")
    best = min(candidates, key=lambda result: result.cost)
    parameters = best.x
    rotation = Rotation.from_rotvec(parameters[:3]).as_matrix()
    camera = {"positionMetres": (-rotation.T @ parameters[3:6]).tolist(),
              "quaternion": Rotation.from_matrix(rotation.T @ np.diag([1., -1., -1.])).as_quat().tolist(),
              "verticalFovDegrees": math.degrees(2 * math.atan(540 / math.exp(parameters[6]))),
              "principalPointViewportPixels": [960., 540.]}
    predictions, _ = solver.project(parameters, xyz, 1920, 1080)
    errors = np.linalg.norm(predictions - pixels, axis=1)
    baseline = receipt["rows"][0]["snapshot"]["camera"]
    old, _ = solver.project(camera_parameters(baseline), xyz, 1920, 1080)
    native_pixels = {(frame["frameIndex"], point["physicalStationIndex"]): point["native"]["sourcePixels"]
                     for frame in receipt["rows"] for point in frame["worldPoints"]}
    gpu_old = np.array([native_pixels[(r["sourceImage"]["frameIndex"], r["physicalStationIndex"])] for r in rows])
    before = np.linalg.norm(gpu_old - pixels, axis=1)
    candidate = {"schemaVersion": 1, "videoId": VIDEO_ID, "source": packet["source"],
                 "model": packet["model"], "camera": camera,
                 "cameraInterpolation": "held",
                 "application": {"shotId": "rocker-bank", "viewId": "main",
                                 "presentation": "native", "rectSourcePixels": [0, 0, 1920, 1080],
                                 "startSeconds": 105.939166667, "endSeconds": 124.457666667},
                 "fitIntervalSeconds": [min(r["timeSeconds"] for r in rows), max(r["timeSeconds"] for r in rows)],
                 "sourceEvidence": {"path": str(Path(evidence).resolve().relative_to(WEB.parent)), "sha256": digest(evidence)},
                 "nativeFitReceipt": {"sha256": digest(native), "baseCommit": receipt["baseCommit"],
                                      "captureAuthority": receipt["qualification"],
                                      "projectionPositiveControlMaxPx": float(np.max(np.linalg.norm(gpu_old - old, axis=1)))},
                 "fitMetrics": {"before": metrics(before), "after": metrics(errors),
                                "beforeMethod": "actual-native-GPU-depth-off-landmark-projection",
                                "afterMethod": "shared-source-solver-CPU-pinhole-projection"},
                 "fitRows": [{"frameIndex": r["sourceImage"]["frameIndex"],
                              "physicalStationIndex": r["physicalStationIndex"],
                              "observedPixel": r["pixel"], "predictedPixel": p.tolist(),
                              "errorPx": float(e)} for r, p, e in zip(rows, predictions, errors)],
                 "identifiability": {"worldPointRank": int(np.linalg.matrix_rank(xyz - xyz.mean(axis=0))),
                                     "focalAtSearchBoundary": bool(abs(parameters[6] - lower[6]) < 1e-5 or abs(parameters[6] - upper[6]) < 1e-5),
                                     "cameraAuthority": "chosen-source-FIT-pinhole; square pixels; centered principal point; no warp/lens fit",
                                     "hiddenPhysicalState": "Existing coherent bank +1 branch/static phases remain chosen, unchanged; folded cosine does not recover sign or historical setup."},
                 "interpretation": "Bounded physically associated terminal-bevel camera FIT. Held across the same original close-up; unmeasured margins hold the nearest camera, never transfer across a cut. Actual native GPU surfaces, independent source CHECK and continuous normal-route playback remain separately required. No source geometry/camera/stage pass from CPU projection.",
                 "acceptance": {"independentCheckEvaluated": False, "cameraGeometryOrGpuAccepted": False}}
    save(output, candidate)
    print(json.dumps({"output": str(output), "camera": camera, "fitMetrics": candidate["fitMetrics"],
                      "identifiability": candidate["identifiability"]}))


def check(candidate_path, evidence, native, output):
    candidate, packet, receipt = load(candidate_path), load(evidence), load(native)
    if {r["role"] for r in packet["rows"]} != {"check"}:
        raise ValueError("Independent evaluation requires CHECK-only source measurements")
    rows, xyz, pixels = joined(packet, receipt, "check")
    fit_keys = {(r["frameIndex"], r["physicalStationIndex"]) for r in candidate["fitRows"]}
    fit_exposures = {key[0] for key in fit_keys}
    if any(r["sourceImage"]["frameIndex"] in fit_exposures for r in rows):
        raise ValueError("New bank camera CHECK exposures are not held out")
    motion_evidence = load(WEB / f"content/{VIDEO_ID}.automatic-motion-evidence.json")
    annotation_fit = {r["sourceImage"]["frameIndex"] for r in motion_evidence["annotations"] if r["role"] == "fit"}
    metal_check = {r["sourceImage"]["frameIndex"] for r in motion_evidence["physicalMetalCHECK"]}
    exposures = {r["sourceImage"]["frameIndex"] for r in rows}
    if exposures & annotation_fit or not exposures <= metal_check:
        raise ValueError("Bank camera controls must retain original H20 exposure holdout")
    solver = projection_module()
    predictions, depths = solver.project(camera_parameters(candidate["camera"]), xyz, 1920, 1080)
    errors = np.linalg.norm(predictions - pixels, axis=1)
    old, _ = solver.project(camera_parameters(receipt["rows"][0]["snapshot"]["camera"]), xyz, 1920, 1080)
    native_pixels = {(frame["frameIndex"], point["physicalStationIndex"]): point["native"]["sourcePixels"]
                     for frame in receipt["rows"] for point in frame["worldPoints"]}
    gpu_old = np.array([native_pixels[(r["sourceImage"]["frameIndex"], r["physicalStationIndex"])] for r in rows])
    report = {"schemaVersion": 1, "videoId": VIDEO_ID, "frozenCameraSha256": digest(candidate_path),
              "checkEvidenceSha256": digest(evidence), "nativeReceiptSha256": digest(native),
              "holdout": f"{len(rows)} new physical bevel-feature controls at {len(exposures)} original H20-metal-CHECK exposures, disjoint from both this camera FIT and original annotation/cadence FIT; original H20 and H1 pixels/features/roles are unchanged",
              "projectionPositiveControlMaxPx": float(np.max(np.linalg.norm(gpu_old - old, axis=1))),
              "checkMetrics": {"before": metrics(np.linalg.norm(gpu_old - pixels, axis=1)), "after": metrics(errors),
                               "beforeMethod": "actual-native-GPU-depth-off-landmark-projection",
                               "afterMethod": "shared-source-solver-CPU-pinhole-projection"},
              "rows": [{"frameIndex": r["sourceImage"]["frameIndex"],
                        "physicalStationIndex": r["physicalStationIndex"],
                        "observedPixel": r["pixel"], "predictedPixel": p.tolist(),
                        "errorPx": float(e), "uncertaintyPx": r["uncertaintyPx"],
                        "positiveDepth": bool(d > 0)} for r, p, e, d in zip(rows, predictions, errors, depths)],
              "acceptance": {"cameraGeometryOrGpuAccepted": False}}
    save(output, report)
    print(json.dumps(report["checkMetrics"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("measure-fit", "fit", "measure-check", "check"))
    parser.add_argument("--source-video", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--native-receipt", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--check-rectangles", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "measure-fit":
        measure(args.source_video, args.output, FIT_RECTS, "fit")
    elif args.command == "measure-check":
        measure(args.source_video, args.output, load(args.check_rectangles), "check")
    elif args.command == "fit":
        fit(args.evidence, args.native_receipt, args.output)
    else:
        check(args.candidate, args.evidence, args.native_receipt, args.output)


if __name__ == "__main__":
    main()

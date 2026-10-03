#!/usr/bin/env python3
"""Continue Analysis's existing coherent bank using new original-source FIT only.

Run in the existing private calibration venv. Original footage and the frozen
source-only cap-corner extractor are read-only inputs, never publication assets.
The camera, twenty phases/amplitudes, hidden setup and chosen signed gauge stay
unchanged. Every eighth new exposure is withheld from the final coherent fit.
Nineteen are exposure-held-out; frame3710's corners are feature/pixel-held-out
because its chromatic centroid was inspected in an earlier source-only prototype.
Physical corner pixels are measured only after the candidate numbers are frozen.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import minimize_scalar

WEB = Path(__file__).resolve().parents[1]
VIDEO_ID = "6dW6VYXp9HM"
FIRST, LAST = 3569, 3730
VIDEO_SHA = "5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52"
CORNER_SHA = "8677361f3485f900b2102fa91f09a4db055723161b42ca73c28d41ea6ed1bd6c"
PRIVATE = WEB / f".vite/verification-output/{VIDEO_ID}-fidelity-20261003"
OUTPUT = WEB / f"content/{VIDEO_ID}.bank-continuation.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def is_check(index):
    # Fixed for this producer before decoding; frame3710's earlier prototype
    # centroid inspection is declared separately, not called exposure-disjoint.
    return index > FIRST and (index - FIRST - 1) % 8 == 4


def cap_pixels(image, rectangles):
    """Source-only chromatic centroid proxy; white graphic cannot contribute.

    Fixed station ROIs are inherited from original FIT, not projected positions.
    The new rule is explicit, rather than claiming to reproduce an unavailable
    historical centroid producer byte-for-byte. Its endpoint difference from
    the retained FIT method is reported, not silently erased.
    """
    points = []
    for station in range(20, 0, -1):
        x, y, width, height = rectangles[station]
        crop = image[y:y + height, x:x + width].astype(np.int16)
        chroma = crop[:, :, 2] - crop[:, :, 0]
        weight = np.where((crop[:, :, 1] > 120) & (chroma > 50), chroma, 0)
        mass = int(weight.sum())
        if not mass:
            raise ValueError(f"Original chromatic cap unavailable at station{station}")
        yy, xx = np.indices(weight.shape)
        points.append({"sourceStation": station,
                       "pixel": [float((weight * xx).sum() / mass + x),
                                 float((weight * yy).sum() / mass + y)],
                       "chromaMass": mass, "searchRectSourcePixels": [x, y, width, height],
                       "uncertaintyPx": 8,
                       "qualification": "Chromatic region-centroid FIT proxy, not a measured geometric cap centre; source localization and method-transfer discrepancy remain diagnostic."})
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--corner-extractor", type=Path, required=True)
    args = parser.parse_args()
    if digest(args.video) != VIDEO_SHA or digest(args.corner_extractor) != CORNER_SHA:
        raise ValueError("Original video or frozen source-only CHECK extractor identity differs")
    motion_path = WEB / f"scripts/{VIDEO_ID}-extract-automatic-motion.py"
    controls_path = WEB / f"content/{VIDEO_ID}.motion-controls.json"
    previous_path = WEB / f"content/{VIDEO_ID}.automatic-motion.json"
    observations_path = WEB / f"content/{VIDEO_ID}.observations.json"
    motion = module(motion_path, "analysis_original_projection")
    controls, previous = load(controls_path), load(previous_path)
    observations = load(observations_path)
    identities = {row["sourceImage"]["frameIndex"]: row["sourceImage"]
                  for row in observations["frames"] if row.get("sourceImage")}
    shot = next(row for row in observations["shots"] if row["id"] == "analysis-22")
    if previous["frames"][-1]["frameIndex"] != FIRST or shot["endSeconds"] != 124.49103333333333:
        raise ValueError("Existing endpoint or real outgoing cut differs")
    projection = motion.Projection(controls["nativeRest"], controls["frozenCandidate"], controls["nativeLandmarkAnchors"])
    rectangles = {point["sourceStation"]: point["searchRectSourcePixels"]
                  for point in controls["sourceFits"]["frames"][-1]["physicalFaceCentroids"]}
    phases = np.asarray(previous["fixedInput"]["phases"])
    harmonics = np.arange(20, 0, -1) * np.pi / 40
    old_turns = previous["frames"][-1]["crankTurns"]

    def predict(turns):
        angles = motion.rocker(np.asarray(turns).reshape(-1, 1) * harmonics + phases, projection.channel)
        return projection.centres(angles), angles

    # Dense one-dimensional initial search, not a second mechanical clock or
    # twenty independently fitted station phases. Bounds retain the chosen
    # original gauge. Both forward and return motion are permitted; no caption
    # or graphic curve is used as a final input observation.
    grid = np.linspace(0, 8, 161)
    grid_pixels, _ = predict(grid)
    old_pixels = predict([old_turns])[0][0]
    capture = cv2.VideoCapture(str(args.video))
    capture.set(cv2.CAP_PROP_POS_FRAMES, FIRST)
    frames, source_fits, held_images, fitted_pixels = [], [], {}, []
    try:
        for index in range(FIRST, LAST + 1):
            ok, image = capture.read()
            if not ok:
                raise ValueError(f"Original source decode unavailable: {index}")
            identity = {"frameIndex": index, "width": image.shape[1], "height": image.shape[0],
                        "pixelFormat": "bgr8", "sha256Bgr8": hashlib.sha256(image.tobytes()).hexdigest(),
                        "sourceSha256": VIDEO_SHA}
            if index in identities and identity != identities[index]:
                raise ValueError(f"Retained native BGR8 exposure differs: {index}")
            row = {"frameIndex": index, "timeSeconds": index * 1001 / 30000,
                   "sourceImage": copy.deepcopy(identity)}
            if is_check(index):
                held_images[index] = image.copy()
                role = "feature-held-out-CHECK" if index == 3710 else "exposure-held-out-CHECK"
                row.update({"role": role, "crankTurns": None})
            else:
                points = cap_pixels(image, rectangles)
                target = np.asarray([point["pixel"] for point in points])
                if index == FIRST:
                    turns = old_turns  # The actual merged boundary is never refitted.
                else:
                    seed = grid[np.argmin(np.mean((grid_pixels - target) ** 2, axis=(1, 2)))]
                    fit = minimize_scalar(lambda value: float(np.mean((predict([value])[0][0] - target) ** 2)),
                                          bounds=(max(0, seed - 0.1), min(8, seed + 0.1)), method="bounded",
                                          options={"xatol": 1e-10})
                    if not fit.success or fit.x < 1e-7 or fit.x > 8 - 1e-7:
                        raise ValueError(f"Unresolved chosen drive at FIT exposure{index}")
                    turns = float(fit.x)
                row.update({"role": "retained-boundary" if index == FIRST else "FIT", "crankTurns": turns})
                source_fits.append({"frameIndex": index, "sourceImage": identity, "points": points})
                fitted_pixels.append(target)
            frames.append(row)
    finally:
        capture.release()
    fit_rows = [row for row in frames if row["crankTurns"] is not None]
    fit_times = [row["timeSeconds"] for row in fit_rows]
    for row in frames:
        if row["crankTurns"] is None:
            row["crankTurns"] = float(np.interp(row["timeSeconds"], fit_times,
                                               [item["crankTurns"] for item in fit_rows]))
    candidate = {"schemaVersion": 1, "kind": "source-fit-coherent-bank-continuation", "videoId": VIDEO_ID,
                 "interval": {"startSeconds": frames[0]["timeSeconds"], "endSeconds": frames[-1]["timeSeconds"],
                              "firstNativeFrameIndex": FIRST, "lastNativeFrameIndex": LAST,
                              "nativeFrameCount": len(frames), "shotId": "analysis-22", "viewId": "bar-bank",
                              "presentation": "horizontal-mirror", "cutEndSeconds": shot["endSeconds"]},
                 "authority": {"videoSha256": VIDEO_SHA,
                               "nativeModelSha256": previous["authority"]["nativeModelSha256"],
                               "previousMotion": {"path": str(previous_path.relative_to(WEB.parent)), "sha256": digest(previous_path)},
                               "controls": {"path": str(controls_path.relative_to(WEB.parent)), "sha256": digest(controls_path)},
                               "producer": {"path": str(Path(__file__).relative_to(WEB.parent)), "sha256": digest(Path(__file__))},
                               "cornerExtractor": {"privatePath": str(args.corner_extractor), "sha256": CORNER_SHA},
                               "cameraUnchanged": controls["frozenCandidate"]["nativeCameraRecord"],
                               "method": "FIT chromatic pixels alone fit one effective crank per eligible actual source exposure with the existing projection/closure; phases, amplitudes, camera and hidden setup are immutable. All20 CHECK exposures receive linear interpolation of neighbouring FIT inputs and never enter the final coherent optimizer. Physical corner pixels never enter any seed, objective or ranking. Frame3710's centroid was previously inspected in a separate exploratory prototype; its corners are feature/pixel-held-out, not investigation-wide exposure-disjoint.",
                               "physicalShaftSignAndHome": "unobservable; original positive effective gauge retained, not historically recovered"},
                 "fixedInput": previous["fixedInput"], "frames": frames,
                 "holdout": {"kind": "mixed-exposure-and-feature-pixel", "rule": "index>3569 and (index-3570)%8==4",
                             "FITFrameIndices": [row["frameIndex"] for row in fit_rows if row["role"] == "FIT"],
                             "CHECKFrameIndices": list(held_images),
                             "exposureHeldOutFrameIndices": [index for index in held_images if index != 3710],
                             "featurePixelHeldOutFrameIndices": [3710],
                             "exploratoryCentroidFITOverlapFrameIndices": [3710],
                             "boundaryFrameIndex": FIRST,
                             "candidateFrozenBeforeCHECKCornerPixels": True},
                 "integration": {"scope": "analysis-22/bar-bank/horizontal-mirror only; preserve exact merged input through119.08563333333333, then new measured FIT continuation until124.45766666666667; hold last new input only until the unchanged124.49103333333333 cut. Do not transfer into analysis-23, its inset or later139.80633333333333 transition.",
                                 "interpolation": "linear cumulative crankTurns in actual source seconds; all twenty phases/amplitudes/setup stay fixed",
                                 "sourceSpatialFidelityAccepted": False, "GPUQualification": "UNEXECUTED"}}
    # Freeze the deployable numbers before importing/inspecting CHECK features.
    save(OUTPUT, candidate)
    frozen_sha = digest(OUTPUT)
    save(PRIVATE / "continuation-fit-pixels.json", {"frames": source_fits})
    actual = np.asarray(fitted_pixels)
    new_fit = predict([row["crankTurns"] for row in fit_rows])[0]
    endpoint_original = np.asarray([[point["pixel"][0], point["pixel"][1]] for point in
                                    reversed(controls["sourceFits"]["frames"][-1]["physicalFaceCentroids"])])
    report = {"frozenCandidateSha256": frozen_sha,
              "FIT": {"framesIncludingRetainedBoundary": len(fit_rows),
                      "oldHoldEuclideanPx": motion.summarize(np.linalg.norm(actual - old_pixels, axis=2).ravel()),
                      "newEuclideanPx": motion.summarize(np.linalg.norm(actual - new_fit, axis=2).ravel()),
                      "retainedEndpointMethodTransferPx": motion.summarize(np.linalg.norm(actual[0] - endpoint_original, axis=1))},
              "CHECK": {"frames": len(held_images), "measured": [], "unresolved": []},
              "qualification": "CPU predicted feature positions only, not native GPU pixels or whole visible mesh agreement. No acceptance tolerance weakened. Chromatic FIT proxies retain method and localization uncertainty; CHECK source-null corners remain unresolved."}
    corner = module(args.corner_extractor, "frozen_source_corner_measurement")
    native_anchors = {item["id"]: item for item in controls["nativeLandmarkAnchors"]}
    anchors = {(station, side): {
        "nativePartPath": native_anchors[f"station-{station}-{side}"]["partPath"],
        "nativeLocalVertexMetres": native_anchors[f"station-{station}-{side}"]["partLocalMetres"]}
        for station in range(1, 21) for side in ("upper-left", "upper-right")}
    for row in frames:
        if not row["role"].endswith("-CHECK"):
            continue
        image = held_images[row["frameIndex"]]
        beta = predict([row["crankTurns"]])[1][0]
        old_beta = predict([old_turns])[1][0]
        cv2.imwrite(str(PRIVATE / f"source-CHECK-{row['frameIndex']}.png"), image)
        for station in range(1, 21):
            x, y, width, height = rectangles[station]
            measurement = corner.measure(image, [x - 6, y, width + 12, height])
            for point in measurement["points"]:
                result = {"frameIndex": row["frameIndex"], "timeSeconds": row["timeSeconds"],
                          "sourceImage": row["sourceImage"], "sourceStation": station, **point,
                          "usedInFit": False, "holdoutKind": row["role"]}
                if point["status"] != "measured":
                    report["CHECK"]["unresolved"].append(result)
                    continue
                anchor = anchors[(station, point["corner"])]
                j = 20 - station
                new = projection.point(beta[j], j, anchor["nativeLocalVertexMetres"])
                old = projection.point(old_beta[j], j, anchor["nativeLocalVertexMetres"])
                result.update({"nativePartPath": anchor["nativePartPath"],
                               "nativeLocalVertexMetres": anchor["nativeLocalVertexMetres"],
                               "newPredictedPixel": new.tolist(), "oldPredictedPixel": old.tolist(),
                               "newEuclideanPx": float(np.linalg.norm(new - point["pixel"])),
                               "oldEuclideanPx": float(np.linalg.norm(old - point["pixel"]))})
                report["CHECK"]["measured"].append(result)
    if digest(OUTPUT) != frozen_sha:
        raise ValueError("CHECK evaluation modified the frozen candidate")
    for field in ("oldEuclideanPx", "newEuclideanPx"):
        report["CHECK"][field] = motion.summarize([row[field] for row in report["CHECK"]["measured"]])
    report["CHECK"]["holdoutGroups"] = {}
    for kind in ("exposure-held-out-CHECK", "feature-held-out-CHECK"):
        measured = [row for row in report["CHECK"]["measured"] if row["holdoutKind"] == kind]
        unresolved = [row for row in report["CHECK"]["unresolved"] if row["holdoutKind"] == kind]
        report["CHECK"]["holdoutGroups"][kind] = {
            "measured": len(measured), "unresolved": len(unresolved),
            **{field: motion.summarize([row[field] for row in measured])
               for field in ("oldEuclideanPx", "newEuclideanPx")}}
    save(PRIVATE / "continuation-independent-CHECK.json", report)
    print(json.dumps({"output": str(OUTPUT), "sha256": frozen_sha,
                      "FIT": report["FIT"], "CHECK": {key: value if key not in ("measured", "unresolved") else len(value)
                                                        for key, value in report["CHECK"].items()}}, indent=2), flush=True)


if __name__ == "__main__":
    main()

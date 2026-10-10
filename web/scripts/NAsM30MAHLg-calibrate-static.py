#!/usr/bin/env python3
"""Track independently measured Intro rigid features in retained lossless source frames.

This produces nonpublishable historical diagnostic evidence, not GPU acceptance.
Source frames and framehash-all.txt must already exist; the helper never decodes
or redistributes video. Require --historical-diagnostic and --output /tmp/...json.
Full mechanism input deliberately stays null.
Output must be a new file; .gz retains the deterministic pretty-JSON encoding.
"""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

WEB = Path(__file__).resolve().parents[1]


spec = importlib.util.spec_from_file_location("static_output_common", WEB / "scripts/compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def camera_parameters(camera, height):
    world_to_cv = (
        np.diag([1, -1, -1]) @ Rotation.from_quat(camera["quaternion"]).as_matrix().T
    )
    position = np.array(camera["positionMetres"])
    focal = height / (2 * math.tan(math.radians(camera["verticalFovDegrees"]) / 2))
    return np.r_[
        Rotation.from_matrix(world_to_cv).as_rotvec(),
        -world_to_cv @ position,
        math.log(focal),
    ]


def track_feature(source, target, pixel, patch_radius=10, search_radius=12):
    x, y = np.rint(pixel).astype(int)
    h, w = source.shape
    if (
        not patch_radius + search_radius <= x < w - patch_radius - search_radius
        or not patch_radius + search_radius <= y < h - patch_radius - search_radius
    ):
        return None
    patch = source[
        y - patch_radius : y + patch_radius + 1, x - patch_radius : x + patch_radius + 1
    ]
    region = target[
        y - patch_radius - search_radius : y + patch_radius + search_radius + 1,
        x - patch_radius - search_radius : x + patch_radius + search_radius + 1,
    ]
    values = cv2.matchTemplate(region, patch, cv2.TM_CCOEFF_NORMED)
    _, correlation, _, peak = cv2.minMaxLoc(values)
    dx, dy = peak[0] - search_radius, peak[1] - search_radius
    target_patch = target[
        y + dy - patch_radius : y + dy + patch_radius + 1,
        x + dx - patch_radius : x + dx + patch_radius + 1,
    ]
    if (
        correlation < 0.78
        or np.std(target_patch) < 2.0
        or abs(dx) >= search_radius
        or abs(dy) >= search_radius
    ):
        return None
    return (
        [float(pixel[0] + dx), float(pixel[1] + dy)],
        float(correlation),
        float(np.std(target_patch)),
    )


def fit_candidate(frame, points, initial, fit_source):
    fitting = [landmark for landmark in frame["landmarks"] if landmark["role"] == "fit"]
    checks = [
        landmark for landmark in frame["landmarks"] if landmark["role"] == "check"
    ]
    if len(fitting) < 6 or len(checks) < 2:
        return None
    xyz = np.array([points[landmark["anchorId"]] for landmark in fitting])
    pixels = np.array([landmark["pixel"] for landmark in fitting])

    def residual(p):
        xy, depth = fit_source.project(p, xyz, 1920, 1080)
        return np.r_[(xy - pixels).ravel(), np.minimum(depth - 0.001, 0) * 1920]

    bounds = (
        np.r_[[-np.inf] * 6, math.log(1080 / (2 * math.tan(math.radians(120) / 2)))],
        np.r_[[np.inf] * 6, math.log(1080 / (2 * math.tan(math.radians(3) / 2)))],
    )
    result = least_squares(residual, initial, bounds=bounds, max_nfev=300)
    if not result.success:
        return None
    p = result.x
    fit_xy, fit_depth = fit_source.project(p, xyz, 1920, 1080)
    check_xy, check_depth = fit_source.project(
        p, np.array([points[landmark["anchorId"]] for landmark in checks]), 1920, 1080
    )
    fit_errors = np.linalg.norm(fit_xy - pixels, axis=1)
    check_errors = np.linalg.norm(
        check_xy - np.array([landmark["pixel"] for landmark in checks]), axis=1
    )
    world_to_cv = Rotation.from_rotvec(p[:3]).as_matrix()
    camera = {
        "positionMetres": (-world_to_cv.T @ p[3:6]).tolist(),
        "quaternion": Rotation.from_matrix(world_to_cv.T @ np.diag([1, -1, -1]))
        .as_quat()
        .tolist(),
        "verticalFovDegrees": math.degrees(2 * math.atan(1080 / (2 * math.exp(p[6])))),
        "fitRmsPx": float(np.sqrt(np.mean(fit_errors**2))),
        "fitMaxPx": float(fit_errors.max()),
        "heldOutMaxPx": float(check_errors.max()),
        "thresholdPx": 38.4,
        "status": "passed"
        if max(fit_errors.max(), check_errors.max()) <= 38.4
        and min(fit_depth.min(), check_depth.min()) > 0
        else "failed",
        "projection": "pinhole; independent source landmarks; square pixels; image-centre principal point",
        "coordinateConvention": "camera-to-CAD-world; quaternion xyzw; looks along local -Z with local +Y up",
        "viewportSourcePixels": [0, 0, 1920, 1080],
        "presentation": "native",
        "checkErrors": [
            {
                "anchorId": landmark["anchorId"],
                "observedPixel": landmark["pixel"],
                "projectedPixel": xy.tolist(),
                "errorPx": float(e),
            }
            for landmark, xy, e in zip(checks, check_xy, check_errors)
        ],
        "identifiability": "Noncoplanar fixed-feature visible-match candidate. Source lens remains a family; no GPU acceptance or hidden-mechanism inference.",
    }
    return camera


def run(evidence, frames, inventory, *, historical_diagnostic=False):
    if historical_diagnostic is not True:
        raise ValueError("Static calibration requires historical_diagnostic=True")
    current = Path(__file__).resolve().parents[1] / "content/v39-source"
    if any(Path(path).resolve().is_relative_to(current.resolve()) for path in (evidence, frames, inventory)):
        raise ValueError("Historical diagnostics cannot consume current source namespace inputs")
    evidence = Path(evidence)
    fit_path = Path(__file__).with_name("fit-source.py")
    spec = importlib.util.spec_from_file_location("intro_fit_source", fit_path)
    fit_source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fit_source)
    obs = fit_source.common.load_historical_observations("NAsM30MAHLg")
    if (
        obs.get("kind") == "current-source-observations"
        or obs.get("freshSourceRecord") is not None
        or obs.get("identityDerivative", {}).get("kind") != "materialized-canonical-native-identity-derivative"
        or obs.get("model", {}).get("sha256") != "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d"
        or obs.get("model", {}).get("sourceCommit") != "1268c23d4a8fc741147c5e09d8d1e45247a71945"
        or obs.get("source", {}).get("videoId") != "NAsM30MAHLg"
        or obs.get("source", {}).get("sha256") != "595b0ec7b1e1a0b3523d72d33f6e0950bd97dda5ab7032bf91c3e5b9fb7d225d"
    ):
        raise ValueError("Static diagnostics require the original historical source/model tuple")
    candidate = json.loads((evidence / "codex-fixed-fit-result.json").read_text())
    seeds = candidate["candidateFrame"]["landmarks"]
    anchors = candidate["candidateAnchors"]
    physical_ids = {
        anchor["id"] for anchor in anchors if anchor["kind"] == "physical-feature"
    }
    seeds = [seed for seed in seeds if seed["anchorId"] in physical_ids]
    inv = json.loads(Path(inventory).read_text())
    points = fit_source.world_points({**obs, "anchors": anchors}, inv)
    initial = camera_parameters(candidate["cameras"][0], 1080)
    source_bgr = cv2.imread(str(Path(frames) / "00809.png"))
    if source_bgr is None:
        raise ValueError("Missing retained t27 lossless source")
    source = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2GRAY)
    shot_ids = {
        "machine-title-fade",
        "presenter-first",
        "history-entry-fade",
        "presenter-history-first",
        "presenter-history-second",
        "endcard-entry-crossfade",
    }
    hashes = {
        int(row.split(",")[2]): row.split(",")[5].strip()
        for row in (evidence / "framehash-all.txt").read_text().splitlines()
        if row and not row.startswith("#")
    }
    output = []
    missing = []
    cache = {}
    for frame in obs["frames"]:
        if frame["shotId"] not in shot_ids:
            continue
        idx = frame["decodedFrameIndex"]
        if idx not in cache:
            target_bgr = cv2.imread(str(Path(frames) / f"{idx:05d}.png"))
            if target_bgr is None:
                cache[idx] = None
            else:
                digest = hashlib.sha256(
                    np.ascontiguousarray(target_bgr).tobytes()
                ).hexdigest()
                if digest != hashes[idx]:
                    raise ValueError(
                        f"{idx}: lossless source hash differs from original framehash"
                    )
                target = cv2.cvtColor(target_bgr, cv2.COLOR_BGR2GRAY)
                tracked = []
                unavailable = []
                for seed in seeds:
                    result = track_feature(source, target, seed["pixel"])
                    if result is None:
                        unavailable.append(
                            {
                                "anchorId": seed["anchorId"],
                                "reason": "No isolated source patch: low contrast, occlusion, or seed correlation below .78; no copied/projected pixel.",
                            }
                        )
                        continue
                    pixel, correlation, contrast = result
                    landmark = {
                        "anchorId": seed["anchorId"],
                        "role": seed["role"],
                        "pixel": pixel,
                        "status": "observed",
                        "method": "template-match",
                        "uncertaintyPx": max(seed["uncertaintyPx"], 2),
                        "trackingEvidence": {
                            "seedDecodedFrameIndex": 809,
                            "seedTimeSeconds": 27,
                            "seedPatchCorrelation": correlation,
                            "targetPatchLumaStd": contrast,
                            "searchRadiusPx": 12,
                            "sourceSha256Bgr8": digest,
                        },
                    }
                    tracked.append(landmark)
                candidate_frame = {**frame, "landmarks": tracked}
                camera = fit_candidate(candidate_frame, points, initial, fit_source)
                cache[idx] = {
                    "landmarks": tracked,
                    "unavailable": unavailable,
                    "camera": camera,
                }
        result = cache[idx]
        if result is None:
            missing.append(
                {
                    "timeSeconds": frame["timeSeconds"],
                    "decodedFrameIndex": idx,
                    "reason": "Lossless retained frame missing; original not redecoded",
                }
            )
        else:
            output.append(
                {
                    "timeSeconds": frame["timeSeconds"],
                    "decodedFrameIndex": idx,
                    "shotId": frame["shotId"],
                    **result,
                }
            )
    cameras = [f["camera"] for f in output if f["camera"]]
    summary = {
        "requestedViewSamples": len(output) + len(missing),
        "measuredViewSamples": len(output),
        "candidateCameraCount": len(cameras),
        "passedCameraCount": sum(c["status"] == "passed" for c in cameras),
        "failedCameraCount": sum(c["status"] == "failed" for c in cameras),
        "heldOutMaxPx": max((c["heldOutMaxPx"] for c in cameras), default=None),
        "fitMaxPx": max((c["fitMaxPx"] for c in cameras), default=None),
        "gpuAcceptedViewSamples": 0,
        "fullMechanismInputsAssigned": 0,
    }
    return {
        "kind": "historical-source-track-receipt",
        "historicalDiagnostic": True,
        "publishable": False,
        "productionIntegrated": False,
        "source": obs["source"],
        "model": obs["model"],
        "anchors": anchors,
        "frames": output,
        "missing": missing,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-diagnostic", action="store_true", required=True)
    parser.add_argument("--evidence", default="/tmp/harmonic-web-reference/evidence/NAsM30MAHLg")
    parser.add_argument("--frames", default="/tmp/nasframes")
    parser.add_argument("--inventory", default="/tmp/harmonic-web-model/model-inventory.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = common.fresh.check_namespace(args.output, historical_diagnostic=True, output=True)
    except ValueError as error:
        parser.error(str(error))
    packet = run(args.evidence, args.frames, args.inventory, historical_diagnostic=args.historical_diagnostic)
    contents = json.dumps(packet, indent=2) + "\n"
    if output.suffix == ".gz":
        contents = common.fresh.encode_observation_bytes(contents.encode("utf-8"))
    common.fresh.write_output(
        output, contents, declared_path=args.output,
        historical_diagnostic=args.historical_diagnostic)
    print(json.dumps(packet["summary"]))


if __name__ == "__main__":
    main()

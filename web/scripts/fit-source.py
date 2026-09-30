#!/usr/bin/env python3
"""Fit genuinely observed source pixels to CAD landmarks; never use check pixels to fit.

Requires numpy, scipy, opencv-python-headless (source-fit-requirements.txt).
Example: python web/scripts/fit-source.py web/content/XPQwKRt4Y2k.observations.json
  --inventory /tmp/harmonic-web-model/model-inventory.json --output /tmp/spin-fitted.json
The inventory supplies named part-local-to-world matrices. Output is numeric data only.
Exit 0 means all measured fits pass, NOT that whole-video coverage is complete.
--require-complete additionally fails on missing camera/mechanism evidence.
"""

import argparse
import copy
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation


def finite_vector(value, size, label):
    if (
        not isinstance(value, list)
        or len(value) != size
        or not all(
            isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x)
            for x in value
        )
    ):
        raise ValueError(f"{label}: expected {size} finite numbers")
    return np.array(value, dtype=float)


SETUP_KEYS = (
    "meanLineAngleRad",
    "platenOffsetM",
    "wireFixtureOffsetM",
    "coneSwingRad",
    "pinionCamRad",
    "heldChannelTurns",
    "driveCrankOffsetTurns",
)


def needs_machine(classification, shot):
    """Mirror of verify-reference.mjs sourceNeedsMachine and timeline.ts requiresMachine.

    Only an explicit shot-census exemption removes the physical-match requirement;
    transition/photograph classifications alone never do.
    """
    if classification == "machine":
        return True
    if classification == "non-machine":
        return shot.get("hasCorrespondingMachine") is True
    return shot.get("hasCorrespondingMachine") is not False


def validate_input(value, label):
    """Every observed input names every setup coordinate; nothing is defaulted for footage."""
    if not isinstance(value, dict):
        raise TypeError(f"{label}: mechanism input must be an object")
    finite_vector([value.get("crankTurns")], 1, f"{label}/crankTurns")
    amplitudes = finite_vector(value.get("amplitudes"), 20, f"{label}/amplitudes")
    if np.any(np.abs(amplitudes) > 1):
        raise ValueError(f"{label}: amplitude outside [-1,1]")
    finite_vector(value.get("phases"), 20, f"{label}/phases")
    if value.get("gearing") not in ("small-large", "medium-medium", "large-small"):
        raise ValueError(f"{label}: unknown gearing")
    if finite_vector([value.get("magnification")], 1, f"{label}/magnification")[0] <= 0:
        raise ValueError(f"{label}: magnification must be positive")
    setup = value.get("setup")
    if not isinstance(setup, dict):
        raise TypeError(f"{label}: missing physical setup")
    for key in SETUP_KEYS:
        finite_vector([setup.get(key)], 1, f"{label}/setup.{key}")
    if "counterHeightM" not in setup:
        raise ValueError(
            f"{label}: setup.counterHeightM must be explicit (finite or null)"
        )
    if setup["counterHeightM"] is not None:
        finite_vector([setup["counterHeightM"]], 1, f"{label}/setup.counterHeightM")


def world_points(observations, inventory):
    if observations["model"]["sha256"] != inventory["sha256"]:
        raise ValueError("Model hash differs from landmark inventory")
    parts = {item["path"]: item for item in inventory["inventory"]}
    points = {}
    for anchor in observations["anchors"]:
        key = anchor["id"]
        if key in points:
            raise ValueError(f"Duplicate anchor {key}")
        if not anchor.get("correspondenceEvidence"):
            raise ValueError(f"{key}: missing source-to-CAD correspondence evidence")
        if "worldMetres" in anchor:
            if "partLocalMetres" in anchor:
                raise ValueError(f"{key}: specify local OR world coordinates")
            point = finite_vector(anchor["worldMetres"], 3, key)
            if anchor.get("partPath") not in parts:
                raise ValueError(f"{key}: unknown named CAD part")
        else:
            part = parts.get(anchor.get("partPath"))
            if part is None:
                raise ValueError(f"{key}: unknown named CAD part")
            matrix = np.array(part["world"], dtype=float).reshape(4, 4, order="F")
            local = finite_vector(anchor["partLocalMetres"], 3, key)
            point = (matrix @ np.r_[local, 1])[:3]
        points[key] = point
    return points


def validate(observations):
    if observations.get("schemaVersion") != 1:
        raise ValueError("Only observation schemaVersion 1 is supported")
    source = observations["source"]
    width, height = source["width"], source["height"]
    if width <= 0 or height <= 0 or source["durationSeconds"] <= 0:
        raise ValueError("Source dimensions and duration must be positive")
    shots = observations["shots"]
    end = 0.0
    for shot in shots:
        if abs(shot["startSeconds"] - end) > 1e-6 or shot["endSeconds"] <= end:
            raise ValueError(
                "Shots must cover source contiguously with half-open intervals"
            )
        end = shot["endSeconds"]
    if abs(end - source["durationSeconds"]) > 1e-6:
        raise ValueError("Shot census does not reach source end")
    shot_by_id = {shot["id"]: shot for shot in shots}
    if len(shot_by_id) != len(shots):
        raise ValueError("Duplicate shot ID")
    ids = {anchor["id"] for anchor in observations["anchors"]}
    times = set()
    for frame in observations["frames"]:
        t = frame["timeSeconds"]
        if not 0 <= t < source["durationSeconds"] or t in times:
            raise ValueError(f"Invalid/duplicate source sample {t}")
        times.add(t)
        if abs(frame["decodedTimeSeconds"] - t) > 0.5:
            raise ValueError(f"{t}: decoded source clock skew exceeds 0.5 s")
        shot = shot_by_id[frame["shotId"]]
        if not shot["startSeconds"] <= t < shot["endSeconds"]:
            raise ValueError(f"{t}: sample outside named shot")
        if frame["classification"] != shot["classification"]:
            raise ValueError(f"{t}: source classification differs from shot")
        if frame["mechanicalState"].get("input") is not None:
            validate_input(frame["mechanicalState"]["input"], f"{t}/input")
        views = {}
        for view in frame.get("views", []):
            view_id = view["id"]
            if view_id in views:
                raise ValueError(f"{t}: duplicate source viewport {view_id}")
            rect = finite_vector(view["rectSourcePixels"], 4, f"{t}/{view_id}/rect")
            if (
                min(rect[2:]) <= 0
                or min(rect[:2]) < 0
                or rect[0] + rect[2] > width
                or rect[1] + rect[3] > height
            ):
                raise ValueError(f"{t}/{view_id}: viewport outside source image")
            views[view_id] = rect
            if view["mechanicalState"].get("input") is not None:
                validate_input(view["mechanicalState"]["input"], f"{t}/{view_id}/input")
        seen = set()
        for landmark in frame["landmarks"]:
            key = landmark["anchorId"]
            view_id = landmark.get("viewId")
            occurrence = (view_id, key)
            if key not in ids or occurrence in seen:
                raise ValueError(f"{t}: unknown/duplicate landmark {key}")
            if views and view_id not in views:
                raise ValueError(f"{t}/{key}: missing or unknown source viewport")
            if not views and view_id is not None:
                raise ValueError(f"{t}/{key}: viewport ID without viewport declaration")
            seen.add(occurrence)
            if landmark["status"] != "observed" or landmark["role"] not in (
                "fit",
                "check",
            ):
                raise ValueError(
                    f"{t}/{key}: only observed fit/check pixels are allowed"
                )
            pixel = finite_vector(landmark["pixel"], 2, f"{t}/{key}")
            if not 0 <= pixel[0] < width or not 0 <= pixel[1] < height:
                raise ValueError(f"{t}/{key}: source pixel outside image")
            if views:
                rect = views[view_id]
                if (
                    not rect[0] <= pixel[0] < rect[0] + rect[2]
                    or not rect[1] <= pixel[1] < rect[1] + rect[3]
                ):
                    raise ValueError(
                        f"{t}/{view_id}/{key}: landmark outside its source viewport"
                    )
    required = set(range(math.ceil(source["durationSeconds"])))
    missing = sorted(required - times)
    if missing:
        raise ValueError(f"Missing integer-second source census: {missing}")
    missing_boundaries = [
        shot["startSeconds"] for shot in shots if shot["startSeconds"] not in times
    ]
    if missing_boundaries:
        raise ValueError(f"Missing shot/change samples: {missing_boundaries}")


def project(parameters, points, width, height):
    camera_points = (
        points @ Rotation.from_rotvec(parameters[:3]).as_matrix().T + parameters[3:6]
    )
    focal = math.exp(parameters[6])
    xy = camera_points[:, :2] / camera_points[:, 2, None]
    principal_point = (
        parameters[7:9] if len(parameters) == 9 else [width / 2, height / 2]
    )
    return xy * focal + principal_point, camera_points[:, 2]


def fit_camera(frame, points, width, height, threshold_px=None, camera_fit=None):
    fit = [landmark for landmark in frame["landmarks"] if landmark["role"] == "fit"]
    check = [landmark for landmark in frame["landmarks"] if landmark["role"] == "check"]
    missing_pose = set(frame.get("anchorPoseMissing", []))
    selected_missing = sorted(
        {landmark["anchorId"] for landmark in fit + check} & missing_pose
    )
    if selected_missing:
        return None, "Moving CAD/source anchor pose is missing: " + ", ".join(
            selected_missing
        )
    options = frame.get("cameraFit", {}) if camera_fit is None else camera_fit
    fit_principal_point = options.get("fitPrincipalPoint", False)
    fixed_fov = options.get("verticalFovDegrees")
    if (fit_principal_point or fixed_fov is not None) and not options.get("evidence"):
        raise ValueError(
            "Non-default camera intrinsics require explicit independent source evidence/hypothesis"
        )
    if fixed_fov is not None and not 0 < fixed_fov < 180:
        raise ValueError("Known vertical FOV must be between 0 and 180 degrees")
    fixed_focal = (
        height / (2 * math.tan(math.radians(fixed_fov) / 2))
        if fixed_fov is not None
        else None
    )
    if len(fit) < 6 or len(check) < 2:
        return (
            None,
            f"Need >=6 fitting and >=2 held-out landmarks; observed {len(fit)}/{len(check)}",
        )
    xyz = np.array([points[landmark["anchorId"]] for landmark in fit])
    pixels = np.array([landmark["pixel"] for landmark in fit], dtype=float)
    weights = np.array(
        [landmark.get("fitWeight", 1.0) for landmark in fit], dtype=float
    )
    if np.any(~np.isfinite(weights)) or np.any(weights <= 0):
        raise ValueError("fitWeight must be a finite positive objective weight")
    root_weights = np.sqrt(weights)[:, None]
    geometry_rank = np.linalg.matrix_rank(xyz - xyz.mean(axis=0), tol=1e-6)
    if geometry_rank < 2:
        return (
            None,
            "Fitting landmarks are collinear: visible camera pose cannot be constrained",
        )
    minimum_focal = height / (2 * math.tan(math.radians(120) / 2))
    maximum_focal = height / (2 * math.tan(math.radians(3) / 2))
    lower = np.r_[[-np.inf] * 6, math.log(minimum_focal)]
    upper = np.r_[[np.inf] * 6, math.log(maximum_focal)]
    if fit_principal_point:
        lower = np.r_[lower, [-np.inf, -np.inf]]
        upper = np.r_[upper, [np.inf, np.inf]]
    if fixed_focal is not None:
        lower, upper = np.delete(lower, 6), np.delete(upper, 6)

    def unpack(variable):
        return (
            np.r_[variable[:6], math.log(fixed_focal), variable[6:]]
            if fixed_focal is not None
            else variable
        )

    best = None
    best_parameters = None
    # Select initialisation/solution using FIT pixels only; checks cannot rescue a bad fit.
    initialisations = []
    centroid = xyz.mean(axis=0)
    pixel_centroid = pixels.mean(axis=0)
    pixel_span = max(float(np.ptp(pixels[:, 1])), 20.0)
    world_span = max(float(np.ptp(xyz[:, 1])), 0.01)
    initial_focals = (
        (fixed_focal,)
        if fixed_focal is not None
        else (width * 0.4, width * 0.7, width, width * 1.8, width * 3)
    )
    for initial_focal in initial_focals:
        intrinsic = np.array(
            [[initial_focal, 0, width / 2], [0, initial_focal, height / 2], [0, 0, 1]]
        )
        for flag in (cv2.SOLVEPNP_ITERATIVE, cv2.SOLVEPNP_SQPNP):
            try:
                ok, rotation, translation = cv2.solvePnP(
                    xyz, pixels, intrinsic, None, flags=flag
                )
            except cv2.error:
                continue
            if ok:
                initialisations.append(
                    np.r_[
                        rotation.ravel(), translation.ravel(), math.log(initial_focal)
                    ]
                )
        # Nearly planar museum front views can make PnP initialise the reflected,
        # negative-depth branch. Independent positive-depth geometric starts use
        # only the fitting set's spread, never held-out/source-camera guesses.
        depth = max(
            initial_focal * world_span / pixel_span,
            np.linalg.norm(xyz - centroid, axis=1).max() * 2,
        )
        for yaw in (0, math.pi / 2, math.pi, -math.pi / 2):
            rotation = np.diag([-1, -1, 1]) @ Rotation.from_euler("y", yaw).as_matrix()
            translation = (
                np.r_[
                    (pixel_centroid - [width / 2, height / 2]) / initial_focal * depth,
                    depth,
                ]
                - rotation @ centroid
            )
            initialisations.append(
                np.r_[
                    Rotation.from_matrix(rotation).as_rotvec(),
                    translation,
                    math.log(initial_focal),
                ]
            )

    def residual(variable):
        predicted, depths = project(unpack(variable), xyz, width, height)
        return np.r_[
            ((predicted - pixels) * root_weights).ravel(),
            np.minimum(depths - 0.001, 0) * width,
        ]

    for initial in initialisations:
        if fit_principal_point:
            initial = np.r_[initial, width / 2, height / 2]
        if fixed_focal is not None:
            initial = np.delete(initial, 6)
        result = least_squares(residual, initial, bounds=(lower, upper), max_nfev=1200)
        parameters = unpack(result.x)
        _, candidate_depths = project(parameters, xyz, width, height)
        if (
            result.success
            and np.all(candidate_depths > 0.001)
            and (best is None or result.cost < best.cost)
        ):
            best = result
            best_parameters = parameters
    if best is None:
        return None, "Camera optimiser failed to converge"
    parameters = best_parameters
    predicted, depths = project(parameters, xyz, width, height)
    if np.any(depths <= 0):
        return None, "Fitting solution places CAD points behind the camera"
    fit_errors = np.linalg.norm(predicted - pixels, axis=1)
    check_xyz = np.array([points[landmark["anchorId"]] for landmark in check])
    check_predicted, check_depths = project(parameters, check_xyz, width, height)
    check_errors = np.linalg.norm(
        check_predicted - np.array([landmark["pixel"] for landmark in check]), axis=1
    )
    world_to_camera = Rotation.from_rotvec(parameters[:3]).as_matrix()
    camera_to_world = world_to_camera.T @ np.diag([1, -1, -1])
    position = -world_to_camera.T @ parameters[3:6]
    threshold = width * 0.02 if threshold_px is None else threshold_px
    status = (
        "passed"
        if np.all(check_errors <= threshold)
        and np.all(check_depths > 0)
        and np.all(fit_errors <= threshold)
        else "failed"
    )
    return {
        "positionMetres": position.tolist(),
        "quaternion": Rotation.from_matrix(camera_to_world).as_quat().tolist(),
        "verticalFovDegrees": math.degrees(
            2 * math.atan(height / (2 * math.exp(parameters[6])))
        ),
        "principalPointViewportPixels": parameters[7:9].tolist()
        if fit_principal_point
        else [width / 2, height / 2],
        "intrinsicsEvidence": options.get(
            "evidence",
            "Square pixels and image-centre principal point; focal fitted only to fitting landmarks.",
        ),
        "intrinsicsIdentifiability": "Coplanar fit: FOV/depth may be non-unique; only observed visible landmark match is established."
        if geometry_rank == 2 and fixed_fov is None
        else "Known source FOV"
        if fixed_fov is not None
        else "Noncoplanar source fit",
        "intrinsicsAtSearchBoundary": bool(
            fixed_fov is None
            and (
                abs(parameters[6] - math.log(minimum_focal)) < 1e-5
                or abs(parameters[6] - math.log(maximum_focal)) < 1e-5
            )
        ),
        "fitRmsPx": float(np.sqrt(np.mean(fit_errors**2))),
        "fitMaxPx": float(fit_errors.max()),
        "fitWeights": [
            {"anchorId": landmark["anchorId"], "weight": float(weight)}
            for landmark, weight in zip(fit, weights)
        ],
        "heldOutMaxPx": float(check_errors.max()),
        "thresholdPx": threshold,
        "status": status,
        "projection": "pinhole; square pixels; centre or explicitly fitted principal point; no fitted lens distortion",
        "coordinateConvention": "camera-to-CAD-world; quaternion xyzw; looks along local -Z with local +Y up",
        "checkErrors": [
            {
                "anchorId": landmark["anchorId"],
                "observedPixel": landmark["pixel"],
                "projectedPixel": prediction.tolist(),
                "errorPx": float(error),
            }
            for landmark, prediction, error in zip(check, check_predicted, check_errors)
        ],
    }, None


def run(observations, inventory):
    validate(observations)
    points = world_points(observations, inventory)
    fitted = copy.deepcopy(observations)
    shots = {shot["id"]: shot for shot in observations["shots"]}
    required_frames = []
    measured, failures, missing = [], [], []
    for frame in fitted["frames"]:
        frame["camera"] = None
        shot = shots[frame["shotId"]]
        if not needs_machine(frame["classification"], shot):
            continue
        targets = frame.get("views") or [
            {
                "id": None,
                "rectSourcePixels": [
                    0,
                    0,
                    observations["source"]["width"],
                    observations["source"]["height"],
                ],
                "mechanicalState": frame["mechanicalState"],
            }
        ]
        for view in targets:
            required_frames.append(view)
            x, y, width, height = view["rectSourcePixels"]
            presentation = view.get("presentation", "native")
            if presentation not in ("native", "horizontal-mirror"):
                raise ValueError(f"Unknown source presentation {presentation}")
            landmarks = [
                {
                    **landmark,
                    "pixel": [landmark["pixel"][0] - x, landmark["pixel"][1] - y],
                }
                for landmark in frame["landmarks"]
                if landmark.get("viewId") == view["id"]
            ]
            if presentation == "horizontal-mirror":
                for landmark in landmarks:
                    landmark["pixel"][0] = width - 1 - landmark["pixel"][0]
            posed_points = dict(points)
            parts = {part["path"]: part for part in inventory["inventory"]}
            part_overrides = view.get("partOverrides", [])
            for anchor in observations["anchors"]:
                candidates = [
                    override
                    for override in part_overrides
                    if anchor["partPath"] == override["partPath"]
                    or anchor["partPath"].startswith(override["partPath"] + "/")
                ]
                if not candidates:
                    continue
                accumulated = np.eye(4)
                for override in sorted(
                    candidates, key=lambda item: len(item["partPath"])
                ):
                    if override["partPath"] not in parts:
                        raise ValueError(
                            f"Unknown source part override {override['partPath']}"
                        )
                    if override.get("visibility") == "hidden":
                        if any(
                            landmark["anchorId"] == anchor["id"]
                            for landmark in landmarks
                        ):
                            raise ValueError(
                                f"Observed landmark {anchor['id']} belongs to hidden source part"
                            )
                        continue
                    rest = np.array(parts[override["partPath"]]["world"]).reshape(
                        4, 4, order="F"
                    )
                    current = accumulated @ rest
                    transformed = current.copy()
                    if "worldQuaternion" in override:
                        quaternion = finite_vector(
                            override["worldQuaternion"], 4, "part override quaternion"
                        )
                        if abs(float(np.linalg.norm(quaternion)) - 1) > 0.001:
                            raise ValueError(
                                "Part override quaternion must have unit length"
                            )
                        transformed[:3, :3] = Rotation.from_quat(quaternion).as_matrix()
                    if "worldPositionMetres" in override:
                        transformed[:3, 3] = finite_vector(
                            override["worldPositionMetres"], 3, "part override position"
                        )
                    accumulated = transformed @ np.linalg.inv(current) @ accumulated
                posed_points[anchor["id"]] = (
                    accumulated @ np.r_[points[anchor["id"]], 1]
                )[:3]
            overrides = view.get(
                "anchorWorldMetres", frame.get("anchorWorldMetres", {})
            )
            if overrides and not view.get(
                "anchorPoseEvidence", frame.get("anchorPoseEvidence")
            ):
                raise ValueError(
                    f"{frame['timeSeconds']}: posed CAD points require independent pose evidence"
                )
            for key, value in overrides.items():
                if key not in points:
                    raise ValueError(f"Unknown posed anchor {key}")
                posed_points[key] = finite_vector(value, 3, key)
            camera, reason = fit_camera(
                {
                    "landmarks": landmarks,
                    "anchorPoseMissing": view.get(
                        "anchorPoseMissing", frame.get("anchorPoseMissing", [])
                    ),
                },
                posed_points,
                width,
                height,
                observations["source"]["width"] * 0.02,
                view.get("cameraFit", frame.get("cameraFit", {})),
            )
            view["camera"] = camera
            if view["id"] is None:
                frame["camera"] = camera
            if reason:
                view["cameraUnobservableReason"] = reason
                if view["id"] is None:
                    frame["cameraUnobservableReason"] = reason
                missing.append(
                    {
                        "timeSeconds": frame["timeSeconds"],
                        "viewId": view["id"],
                        "reason": reason,
                    }
                )
            else:
                camera["viewportSourcePixels"] = [x, y, width, height]
                camera["presentation"] = presentation
                for error in camera["checkErrors"]:
                    if presentation == "horizontal-mirror":
                        error["observedPixel"][0] = (
                            width - 1 - error["observedPixel"][0]
                        )
                        error["projectedPixel"][0] = (
                            width - 1 - error["projectedPixel"][0]
                        )
                    error["observedPixel"] = [
                        error["observedPixel"][0] + x,
                        error["observedPixel"][1] + y,
                    ]
                    error["projectedPixel"] = [
                        error["projectedPixel"][0] + x,
                        error["projectedPixel"][1] + y,
                    ]
                measured.append(
                    {
                        "timeSeconds": frame["timeSeconds"],
                        "viewId": view["id"],
                        **camera,
                    }
                )
                if camera["status"] != "passed":
                    failures.append(frame["timeSeconds"])
    # A required view is matchable only with a complete measured input, never a status label alone.
    mechanism_missing = [
        view
        for view in required_frames
        if view["mechanicalState"]["status"] != "observed"
        or view["mechanicalState"].get("visiblePoseCompleteness") == "partial"
        or view["mechanicalState"].get("input") is None
    ]
    no_machine_source = not required_frames and all(
        not needs_machine(frame["classification"], shots[frame["shotId"]])
        for frame in fitted["frames"]
    )
    complete = (
        (bool(measured) or no_machine_source)
        and not failures
        and not missing
        and not mechanism_missing
        and observations["coverage"]["status"] == "complete"
    )
    report = {
        "videoId": observations["source"]["videoId"],
        "sourceSha256": observations["source"]["sha256"],
        "sampleCount": len(fitted["frames"]),
        "measuredFitCount": len(measured),
        "failedFitTimes": failures,
        "requiredMachineSampleCount": len(required_frames),
        "noCorrespondingMachineSource": no_machine_source,
        "heldOutThresholdPx": observations["source"]["width"] * 0.02,
        "fits": measured,
        "missingCameraEvidence": missing,
        "unobservedMechanismSampleCount": len(mechanism_missing),
        "coverageStatus": "complete" if complete else "blocked",
        "coverageBlockers": observations["coverage"]["blockers"],
    }
    fitted["coverage"]["status"] = report["coverageStatus"]
    fitted["fitReport"] = report
    return fitted, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    fitted, report = run(
        json.loads(args.observations.read_text()),
        json.loads(args.inventory.read_text()),
    )
    if args.output:
        args.output.write_text(json.dumps(fitted, indent=2) + "\n")
    summary = {
        key: value
        for key, value in report.items()
        if key not in ("missingCameraEvidence", "fits")
    }
    summary["fits"] = [
        {
            key: fit[key]
            for key in (
                "timeSeconds",
                "status",
                "fitRmsPx",
                "fitMaxPx",
                "heldOutMaxPx",
                "verticalFovDegrees",
                "checkErrors",
            )
        }
        for fit in report["fits"]
    ]
    summary["missingCameraEvidenceCount"] = len(report["missingCameraEvidence"])
    print(json.dumps(summary, indent=2))
    if (
        (not report["measuredFitCount"] and not report["noCorrespondingMachineSource"])
        or report["failedFitTimes"]
        or (args.require_complete and report["coverageStatus"] != "complete")
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

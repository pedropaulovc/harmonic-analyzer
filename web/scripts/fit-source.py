#!/usr/bin/env python3
"""Fit current actual-source observations to CAD landmarks, never fitting CHECK pixels.

Requires numpy, scipy, opencv-python-headless (source-fit-requirements.txt).
Example: python web/scripts/fit-source.py web/content/v39-source/XPQwKRt4Y2k.observations.json
  --inventory /tmp/current-model-inventory.json --output /tmp/spin-fitted.json
Ordinary input and output pass the shared current observation/inventory authority gate.
Inventory matrices are released native rest transforms, not solved moving-part geometry;
chosen mechanism inputs do not turn rest-projected moving anchors into pose evidence.
Only exact {kind: 'operating'} assembly descriptors are legal for REST projection.
Posed/unknown assembly descriptors and runtime-instance anchors are explicitly refused;
genuine supplied posed-view cameras use the shared validator instead.
--historical-diagnostic explicitly selects old materialized derivative diagnostics;
it cannot publish in either current or immutable historical content namespaces.
Current CPU residuals are diagnostics, never camera-candidate or GPU/source acceptance gates.
Native line CHECK scores add the unchanged final-source localization/raster bound
once, plus explicitly certified independent geometry; no extra source raster allowance.
CPU homography residuals are unsupported: bound current cameras remain candidates,
but an unsolved warped view stays unavailable; observations are never unwarped to fit.
--require-complete additionally fails on missing camera/mechanism evidence.
"""

import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

SPEC = importlib.util.spec_from_file_location("compact_source_common", Path(__file__).with_name("compact-source-common.py"))
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)


def fresh_contract():
    spec = importlib.util.spec_from_file_location(
        "fresh_source_observations", Path(__file__).with_name("fresh-source-observations.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_namespace(path, *, historical_diagnostic=False, output=False, video_id=None):
    """Diagnostics are temporary files, never a route into a published namespace."""
    path = Path(path).resolve()
    web = Path(__file__).resolve().parents[1]
    historical = (web / "content").resolve()
    current = (web / "content/v39-source").resolve()
    if path.is_relative_to(current):
        if historical_diagnostic:
            raise ValueError("Historical diagnostics cannot read or write current observations")
        if path.parent != current or not path.name.endswith(".observations.json"):
            raise ValueError("Current observations use only direct .observations.json namespace entries")
        if video_id is not None and path != current / f"{video_id}.observations.json":
            raise ValueError("Current observations must use their registered video filename")
    if (
        path.is_relative_to(historical) and not path.is_relative_to(current)
        and (output or not historical_diagnostic)
    ):
        raise ValueError("Historical content is immutable and requires explicit diagnostic input")


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


def needs_machine(frame, shot):
    """Mirror of verify-reference.mjs sourceNeedsMachine and timeline.ts requiresMachine.

    An explicit required frame cannot be exempted by classification or shot census.
    Absent that monotonic override, the existing source/shot classification rule applies.
    """
    if "sourceMachineRequirement" in frame:
        if frame["sourceMachineRequirement"] != "required":
            raise ValueError("sourceMachineRequirement must be the literal 'required'")
        return True
    classification = frame["classification"]
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


def require_rest_projection(observations):
    """Allow only ordinary operating state; never pose geometry from runtime templates."""
    for frame in observations.get("frames", []):
        for view in frame.get("views", []):
            if "sourceAssembly" in view and (
                not isinstance(view["sourceAssembly"], dict)
                or view["sourceAssembly"] != {"kind": "operating"}
            ):
                raise ValueError(
                    f"{frame.get('timeSeconds')}/{view.get('id')}: REST-only fitting refuses "
                    "unsupported/posed sourceAssembly projection; only exact operating state "
                    "is supported here. Use actual solved runtime geometry for posed views. "
                    "Supplied current camera candidates are not modified or reprojected."
                )
    for anchor in observations.get("anchors", []):
        if (
            "runtimeTemplatePartPath" in anchor
            or "@" in anchor.get("partPath", "")
        ):
            raise ValueError(
                f"{anchor.get('id')}: REST-only fitting refuses runtime-instance anchor "
                "projection; runtimeTemplatePartPath is not a posed transform."
            )


def world_points(observations, inventory):
    require_rest_projection(observations)
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
    if not isinstance(fit_principal_point, bool):
        raise ValueError("fitPrincipalPoint must be a boolean")
    fixed_principal_point = (
        finite_vector(
            options["principalPointViewportPixels"], 2, "fixed principal point"
        )
        if "principalPointViewportPixels" in options
        else None
    )
    if fit_principal_point and fixed_principal_point is not None:
        raise ValueError("Cannot fit and fix the principal point simultaneously")
    fixed_fov = options.get("verticalFovDegrees")
    if fixed_fov is not None:
        fixed_fov = finite_vector([fixed_fov], 1, "Known vertical FOV")[0]
        if not 0 < fixed_fov < 180:
            raise ValueError("Known vertical FOV must be between 0 and 180 degrees")
    if (
        fit_principal_point
        or fixed_principal_point is not None
        or fixed_fov is not None
    ):
        evidence = options.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(
                "Non-default camera intrinsics require explicit independent source evidence/hypothesis"
            )
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
        parameters = (
            np.r_[variable[:6], math.log(fixed_focal), variable[6:]]
            if fixed_focal is not None
            else variable
        )
        return (
            np.r_[parameters, fixed_principal_point]
            if fixed_principal_point is not None
            else parameters
        )

    best = None
    best_parameters = None
    # Select initialisation/solution using FIT pixels only; checks cannot rescue a bad fit.
    initialisations = []
    principal_point = (
        fixed_principal_point
        if fixed_principal_point is not None
        else np.array([width / 2, height / 2])
    )
    centroid = xyz.mean(axis=0)
    pixel_centroid = pixels.mean(axis=0)
    pixel_span = max(float(np.ptp(pixels[:, 1])), 20.0)
    world_span = max(float(np.ptp(xyz[:, 1])), 0.01)
    initial_focals = (
        (fixed_focal,)
        if fixed_focal is not None
        else tuple(
            dict.fromkeys(
                float(np.clip(candidate, minimum_focal, maximum_focal))
                for candidate in (
                    width * 0.4,
                    width * 0.7,
                    width,
                    width * 1.8,
                    width * 3,
                )
            )
        )
    )
    for initial_focal in initial_focals:
        intrinsic = np.array(
            [
                [initial_focal, 0, principal_point[0]],
                [0, initial_focal, principal_point[1]],
                [0, 0, 1],
            ]
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
                    (pixel_centroid - principal_point) / initial_focal * depth,
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
        if len(parameters) == 9
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
        "projection": "pinhole; square pixels; centre or explicitly fixed/fitted principal point; no fitted lens distortion",
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


def source_image_key(image, source, label):
    if not isinstance(image, dict):
        raise ValueError(f"{label}: missing decoded source image identity")
    pixel_format = image.get("pixelFormat")
    hash_name = {"bgr8": "sha256Bgr8", "gray8": "sha256Gray8"}.get(pixel_format)
    if (
        hash_name is None
        or ({"sha256Bgr8", "sha256Gray8"} - {hash_name}) & image.keys()
    ):
        raise ValueError(f"{label}: ambiguous or unsupported decoded pixel format")
    for name in ("frameIndex", "width", "height"):
        value = image.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < (0 if name == "frameIndex" else 1)
        ):
            raise ValueError(f"{label}: invalid {name}")
    for name in (hash_name, "sourceSha256"):
        value = image.get(name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(c not in "0123456789abcdef" for c in value)
        ):
            raise ValueError(f"{label}: invalid {name}")
    if (
        image["sourceSha256"] != source["sha256"]
        or image["width"] != source["width"]
        or image["height"] != source["height"]
    ):
        raise ValueError(f"{label}: stale or incompatible source image")
    return tuple(
        image[name]
        for name in (
            "frameIndex",
            hash_name,
            "pixelFormat",
            "width",
            "height",
            "sourceSha256",
        )
    )


def finite_evidence(value):
    if value is None:
        return True
    if isinstance(value, dict):
        return bool(value) and all(finite_evidence(item) for item in value.values())
    if isinstance(value, list):
        return bool(value) and all(finite_evidence(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return True
    return isinstance(value, (int, float)) and math.isfinite(value)


def measurement_evidence(measurement, label):
    if measurement.get("method") not in (
        "manual",
        "optical-flow",
        "image-edge",
        "template-match",
    ):
        raise ValueError(f"{label}: unknown measurement method")
    uncertainty = finite_vector([measurement.get("uncertaintyPx")], 1, label)[0]
    if uncertainty < 0:
        raise ValueError(f"{label}: negative pixel uncertainty")
    evidence = measurement.get("measurementEvidence")
    if not isinstance(evidence, (str, dict)) or not finite_evidence(evidence):
        raise ValueError(f"{label}: missing actual-image measurement evidence")
    if measurement.get("role") not in ("fit", "check"):
        raise ValueError(f"{label}: invalid measurement role")


def measurement_image_identity(measurement, image, source, label):
    evidence = measurement["measurementEvidence"]
    if not isinstance(evidence, dict):
        return
    if "sourceImage" in evidence and source_image_key(
        evidence["sourceImage"], source, label
    ) != source_image_key(image, source, label):
        raise ValueError(f"{label}: stale measurement source image")
    for format_name, digest_name in (("Bgr8", "sha256Bgr8"), ("Gray8", "sha256Gray8")):
        evidence_name = "sourceSha256" + format_name
        if evidence_name in evidence and evidence[evidence_name] != image.get(
            digest_name
        ):
            raise ValueError(f"{label}: stale measurement pixel hash")


def rig_phase_parameters(rig, phase):
    reference = rig["worldToReferenceCameraCV"]
    rotation = Rotation.from_rotvec(reference["rotationVectorRad"]).as_matrix()
    rotation = rotation @ Rotation.from_euler("y", 2 * math.pi * phase / 71).as_matrix()
    translation = np.array(reference["translationMetres"]) - rotation @ np.array(
        rig["axisPointWorldMetres"]
    )
    return np.r_[
        Rotation.from_matrix(rotation).as_rotvec(),
        translation,
        math.log(reference["focalPixels"]),
        960.0,
        540.0,
    ]


def prepare_camera_rigs(observations, points):
    """Validate the independent shared fit once, never optimise its per-view cameras."""
    source = observations["source"]
    threshold = source["width"] * 0.02
    prepared = {}
    for rig in observations.get("sourceCameraRigs", []):
        rig_id = rig.get("id")
        if not isinstance(rig_id, str) or not rig_id or rig_id in prepared:
            raise ValueError("Missing or duplicate source camera rig ID")
        if (
            rig.get("kind") != "turntable"
            or type(rig.get("phaseCount")) is not int
            or rig["phaseCount"] != 71
        ):
            raise ValueError(f"{rig_id}: expected a 71-phase turntable rig")
        if (source["width"], source["height"]) != (1920, 1080):
            raise ValueError(
                f"{rig_id}: turntable rig requires the full 1920x1080 source"
            )
        reference = rig["worldToReferenceCameraCV"]
        finite_vector(reference.get("rotationVectorRad"), 3, f"{rig_id}/rotation")
        finite_vector(reference.get("translationMetres"), 3, f"{rig_id}/translation")
        finite_vector(rig.get("axisPointWorldMetres"), 3, f"{rig_id}/axis")
        focal = finite_vector([reference.get("focalPixels")], 1, f"{rig_id}/focal")[0]
        if focal <= 0:
            raise ValueError(f"{rig_id}: focal length must be positive")
        images = {}
        for item in rig.get("phaseImages", []):
            phase = item.get("phaseIndex")
            if type(phase) is not int or not 0 <= phase < 71 or phase in images:
                raise ValueError(f"{rig_id}: invalid or duplicate phase image")
            source_image_key(item.get("sourceImage"), source, f"{rig_id}/phase{phase}")
            images[phase] = item["sourceImage"]
        if set(images) != set(range(71)):
            raise ValueError(f"{rig_id}: every phase requires an actual source image")
        if (
            len(
                {
                    source_image_key(image, source, rig_id)[1:3]
                    for image in images.values()
                }
            )
            != 71
        ):
            raise ValueError(
                f"{rig_id}: phase images do not establish 71 unique appearances"
            )
        loop = rig.get("independentLoopEvidence", {})
        if (
            loop.get("sourceSha256") != source["sha256"]
            or type(loop.get("decodedNativeFrameCount")) is not int
            or loop["decodedNativeFrameCount"] < 142
            or type(loop.get("loopNativeFrameCount")) is not int
            or loop["loopNativeFrameCount"] != 142
            or type(loop.get("uniqueImageCount")) is not int
            or loop["uniqueImageCount"] != 71
            or type(loop.get("firstLoopReferenceFrameIndex")) is not int
            or loop["firstLoopReferenceFrameIndex"] < 0
            or not isinstance(loop.get("evidence"), str)
            or not loop["evidence"].strip()
        ):
            raise ValueError(f"{rig_id}: incomplete independent numeric loop evidence")
        if images[0]["frameIndex"] != loop["firstLoopReferenceFrameIndex"] or any(
            image["frameIndex"] >= loop["decodedNativeFrameCount"]
            for image in images.values()
        ):
            raise ValueError(
                f"{rig_id}: phase image lies outside the measured native loop census"
            )
        comparison = loop.get("periodPixelComparison", {})
        period_error, adjacent_error = finite_vector(
            [
                comparison.get("nativeOffset142MedianMAD"),
                comparison.get("adjacentOffsetMedianMAD"),
            ],
            2,
            f"{rig_id}/period pixel comparison",
        )
        if not 0 <= period_error < adjacent_error:
            raise ValueError(f"{rig_id}: pixels do not distinguish the measured loop")
        source_map = {}
        for item in loop.get("sourceFrameMap", []):
            key = source_image_key(
                item.get("sourceImage"), source, f"{rig_id}/source map"
            )
            if key in source_map:
                raise ValueError(f"{rig_id}: duplicate source image registration")
            phase = item.get("referencePhaseIndex")
            if (
                type(phase) is not int
                or phase not in images
                or type(item.get("phaseAccepted")) is not bool
            ):
                raise ValueError(f"{rig_id}: invalid source image phase registration")
            ref_key = source_image_key(
                item.get("referenceSourceImage"), source, f"{rig_id}/reference map"
            )
            if ref_key != source_image_key(
                images[phase], source, f"{rig_id}/phase identity"
            ):
                raise ValueError(f"{rig_id}: stale reference phase image")
            ncc, second = finite_vector(
                [item.get("ncc"), item.get("secondBestPhaseNcc")], 2, f"{rig_id}/NCC"
            )
            if (
                not -1 <= second <= 1
                or not -1 <= ncc <= 1
                or (item["phaseAccepted"] and ncc <= second)
            ):
                raise ValueError(f"{rig_id}: ambiguous accepted source phase")
            source_map[key] = item
        if not source_map:
            raise ValueError(f"{rig_id}: missing actual-image phase registrations")
        parameters = {phase: rig_phase_parameters(rig, phase) for phase in images}
        measurements = {phase: [] for phase in images}
        seen = set()
        fit_geometry, fit_errors, check_errors = [], [], []
        positive_depths = True
        for measurement in rig.get("measurements", []):
            measurement_evidence(measurement, f"{rig_id}/measurement")
            phase, anchor = measurement.get("phaseIndex"), measurement.get("anchorId")
            if (
                type(phase) is not int
                or phase not in images
                or anchor not in points
                or (phase, anchor) in seen
            ):
                raise ValueError(f"{rig_id}: invalid or duplicate native landmark")
            measurement_image_identity(measurement, images[phase], source, rig_id)
            seen.add((phase, anchor))
            pixel = finite_vector(measurement.get("pixel"), 2, f"{rig_id}/{anchor}")
            if not 0 <= pixel[0] < 1920 or not 0 <= pixel[1] < 1080:
                raise ValueError(f"{rig_id}: measurement outside actual source image")
            prediction, depth = project(
                parameters[phase], np.array([points[anchor]]), 1920, 1080
            )
            error = float(np.linalg.norm(prediction[0] - pixel))
            positive_depths = positive_depths and bool(depth[0] > 0)
            if measurement["role"] == "fit":
                fit_errors.append(error)
                fit_geometry.append(
                    Rotation.from_euler("y", 2 * math.pi * phase / 71).apply(
                        points[anchor] - np.array(rig["axisPointWorldMetres"])
                    )
                )
            else:
                check_errors.append(error)
            measurements[phase].append(measurement)
        if (
            len(fit_geometry) < 6
            or np.linalg.matrix_rank(
                np.array(fit_geometry) - np.mean(fit_geometry, axis=0), tol=1e-6
            )
            < 2
        ):
            raise ValueError(
                f"{rig_id}: need >=6 nondegenerate global fitting measurements"
            )
        if any(
            sum(item["role"] == "check" for item in items) < 2
            for items in measurements.values()
        ):
            raise ValueError(
                f"{rig_id}: every phase needs >=2 actual held-out landmarks"
            )
        prepared[rig_id] = {
            "images": images,
            "sourceMap": source_map,
            "parameters": parameters,
            "measurements": measurements,
            "passed": positive_depths and max(fit_errors + check_errors) <= threshold,
            "proof": {
                "globalFitCount": len(fit_errors),
                "globalCheckCount": len(check_errors),
                "globalFitRmsPx": float(np.sqrt(np.mean(np.square(fit_errors)))),
                "globalFitMaxPx": max(fit_errors),
                "globalHeldOutMaxPx": max(check_errors),
            },
        }
    return prepared


def prepare_native_line_checks(observations, contexts, inventory):
    """Keep finite native line geometry separate from actual image edge observations."""
    prepared = {}
    parts = {part["path"]: part for part in inventory["inventory"]} if inventory else {}
    source = observations["source"]
    for key, (frame, view, _, _) in contexts.items():
        lines, ids = [], set()
        if (
            view.get("imagePlaneWarp") is not None
            or view.get("resolvedImagePlaneWarp") is not None
            or frame.get("imagePlaneWarp") is not None
        ):
            raise ValueError(
                f"{key}: CPU native-line candidate objective does not support image-plane homographies"
            )
        presentation = view.get("presentation", "native")
        if presentation not in ("native", "horizontal-mirror"):
            raise ValueError(
                f"{key}: unsupported CPU source presentation {presentation}"
            )
        for line in view.get("nativeLineChecks", []):
            identity, path = line.get("id"), line.get("partPath")
            if (
                not isinstance(identity, str)
                or not identity
                or identity in ids
                or path not in parts
            ):
                raise ValueError(
                    f"{key}: missing/duplicate native line ID or unknown native part"
                )
            ids.add(identity)
            local = line.get("partLocalLineMetres")
            pixels = line.get("sourceLinePixels")
            if (
                not isinstance(local, list)
                or len(local) != 2
                or not isinstance(pixels, list)
                or len(pixels) != 2
            ):
                raise ValueError(
                    "Native/source lines require exactly two independent endpoints"
                )
            local = np.array(
                [finite_vector(point, 3, "native line endpoint") for point in local]
            )
            pixels = np.array(
                [
                    finite_vector(point, 2, "observed source line endpoint")
                    for point in pixels
                ]
            )
            if (
                np.linalg.norm(local[1] - local[0]) <= 1e-9
                or np.linalg.norm(pixels[1] - pixels[0]) <= 1e-6
            ):
                raise ValueError("Native/source line segments must be nondegenerate")
            x, y, width, height = view["rectSourcePixels"]
            if np.any(pixels < [x, y]) or np.any(pixels >= [x + width, y + height]):
                raise ValueError(
                    "Actual source line segment lies outside its source viewport"
                )
            uncertainty = finite_vector(
                [line.get("uncertaintyPx")], 1, "source line uncertainty"
            )[0]
            evidence = line.get("measurementEvidence")
            if (
                uncertainty < 0
                or not isinstance(evidence, dict)
                or not finite_evidence(evidence)
            ):
                raise ValueError("Native line requires finite actual-edge evidence")
            if source_image_key(
                evidence.get("sourceImage"), source, str(key)
            ) != source_image_key(frame.get("sourceImage"), source, str(key)):
                raise ValueError("Native line edge evidence has a stale source image")
            for name in ("detector", "axisPerspectiveEvidence"):
                if (
                    not isinstance(evidence.get(name), str)
                    or not evidence[name].strip()
                ):
                    raise ValueError(
                        "Native axis requires a justified actual paired-edge measurement"
                    )
            bias = finite_vector(
                [evidence.get("axisPerspectiveBiasBoundPx")],
                1,
                "axis perspective bias bound",
            )[0]
            components = evidence.get("axisPerspectiveBiasComponents")
            if not isinstance(components, dict) or components.keys() != {
                "kind",
                "geometryBoundPx",
                "sourceLocalizationBoundPx",
                "evidence",
            }:
                raise ValueError(
                    "Native axis requires a closed explicit additive bias component certificate"
                )
            geometry, included_source = finite_vector(
                [
                    components.get("geometryBoundPx"),
                    components.get("sourceLocalizationBoundPx"),
                ],
                2,
                "axis perspective bias components",
            )
            if (
                bias < 0
                or geometry < 0
                or included_source < 0
                or components["kind"]
                not in ("independent-geometry", "includes-source-localization")
                or not isinstance(components["evidence"], str)
                or not components["evidence"].strip()
                or abs(geometry + included_source - bias) > 1e-9 * max(1, bias)
            ):
                raise ValueError(
                    "Native axis bias needs an independently evidenced additive decomposition"
                )
            bias_space = evidence.get("axisPerspectiveBiasSpace", "source-global")
            if bias_space != "source-global":
                raise ValueError(
                    "Ordinary CPU native-line axis bias must be in source-global pixels"
                )
            if components["kind"] == "independent-geometry":
                if included_source != 0:
                    raise ValueError(
                        "Independent geometry certificate cannot contain source localization"
                    )
            elif included_source != uncertainty:
                raise ValueError(
                    "Inclusive axis certificate must identify the unchanged source localization bound exactly once"
                )
            rows = evidence.get("edgeRows")
            if not isinstance(rows, list) or len(rows) < 2:
                raise ValueError(
                    "Native axis check needs actual edge pairs at >=2 source rows"
                )
            midpoints = []
            for row in rows:
                row_y, left, right, contrast = finite_vector(
                    [
                        row.get("y"),
                        row.get("left"),
                        row.get("right"),
                        row.get("contrast"),
                    ],
                    4,
                    "actual source edge pair",
                )
                if (
                    not y <= row_y < y + height
                    or not x <= left < right < x + width
                    or contrast <= 0
                ):
                    raise ValueError(
                        "Actual edge pair is unobservable or outside the source viewport"
                    )
                midpoints.append([(left + right) / 2, row_y])
            midpoints = np.array(midpoints)
            if np.ptp(midpoints[:, 1]) <= 1e-6:
                raise ValueError(
                    "Native axis evidence must span distinct actual source rows"
                )
            delta = pixels[1] - pixels[0]
            fractions = np.clip((midpoints - pixels[0]) @ delta / (delta @ delta), 0, 1)
            if np.any(
                np.linalg.norm(
                    midpoints - (pixels[0] + fractions[:, None] * delta), axis=1
                )
                > uncertainty
            ):
                raise ValueError(
                    "Source line is not supported by its independently measured edge pairs"
                )
            if (
                np.min(pixels[:, 1]) < midpoints[:, 1].min() - uncertainty
                or np.max(pixels[:, 1]) > midpoints[:, 1].max() + uncertainty
            ):
                raise ValueError(
                    "Source line extends beyond its observed edge-pair support"
                )
            world = np.array(parts[path]["world"], dtype=float).reshape(4, 4, order="F")
            accumulated = np.eye(4)
            for override in sorted(
                (
                    item
                    for item in view.get("partOverrides", [])
                    if path == item["partPath"]
                    or path.startswith(item["partPath"] + "/")
                ),
                key=lambda item: len(item["partPath"]),
            ):
                if (
                    override["partPath"] not in parts
                    or override.get("visibility") == "hidden"
                ):
                    raise ValueError(
                        "Observed native line belongs to unknown or source-hidden geometry"
                    )
                rest = np.array(parts[override["partPath"]]["world"]).reshape(
                    4, 4, order="F"
                )
                current = accumulated @ rest
                transformed = current.copy()
                if "worldQuaternion" in override:
                    quaternion = finite_vector(
                        override["worldQuaternion"], 4, "native line part quaternion"
                    )
                    if abs(float(np.linalg.norm(quaternion)) - 1) > 0.001:
                        raise ValueError(
                            "Native line part quaternion must have unit length"
                        )
                    transformed[:3, :3] = Rotation.from_quat(quaternion).as_matrix()
                if "worldPositionMetres" in override:
                    transformed[:3, 3] = finite_vector(
                        override["worldPositionMetres"], 3, "native line part position"
                    )
                accumulated = transformed @ np.linalg.inv(current) @ accumulated
            world = accumulated @ world
            world_points = (np.c_[local, np.ones(2)] @ world.T)[:, :3]
            viewport_pixels = np.vstack((pixels, midpoints)) - [x, y]
            if presentation == "horizontal-mirror":
                viewport_pixels[:, 0] = width - 1 - viewport_pixels[:, 0]
            lines.append(
                {
                    "id": identity,
                    "partPath": path,
                    "worldMetres": world_points,
                    "viewportPixels": viewport_pixels[:2],
                    "viewportObservedPixels": viewport_pixels,
                    "sourceUncertaintyPx": float(uncertainty),
                    "geometryBoundPx": float(geometry),
                    "axisPerspectiveBiasComponents": dict(components),
                    "biasBoundPx": float(bias),
                }
            )
        prepared[key] = lines
    return prepared


def native_line_candidate_residual(parameters, line, width, height):
    """Held-out CPU objective; neither these checks nor their rows fit the camera."""
    source, geometry = finite_vector(
        [line.get("sourceUncertaintyPx"), line.get("geometryBoundPx")],
        2,
        "native line independent candidate bounds",
    )
    if source < 0 or geometry < 0:
        raise ValueError("Native line candidate bounds must be nonnegative")
    predicted, depths = project(parameters, line["worldMetres"], width, height)
    delta = predicted[1] - predicted[0]
    squared_length = float(delta @ delta)
    if (
        not np.all(np.isfinite(predicted))
        or squared_length <= 1e-12
        or np.any(depths <= 0)
    ):
        raise ValueError(
            "Native line is degenerate in projection or behind the source camera"
        )
    observed = line["viewportObservedPixels"]
    fractions = (observed - predicted[0]) @ delta / squared_length
    errors = np.linalg.norm(
        observed - (predicted[0] + fractions[:, None] * delta), axis=1
    )
    covered = bool(np.all((fractions >= 0) & (fractions <= 1)))
    # Source localization already includes its frozen raster allowance. Only the
    # certified geometry component is added, never the possibly inclusive axis total.
    return predicted, errors, errors + source + geometry, covered


def evaluate_native_lines(parameters, lines, width, height, threshold):
    results = []
    for line in lines:
        predicted, errors, candidate_residual, covered = native_line_candidate_residual(
            parameters, line, width, height
        )
        observed = line["viewportPixels"]
        conservative_error = float(candidate_residual.max())
        results.append(
            {
                "id": line["id"],
                "partPath": line["partPath"],
                "observedLinePixels": observed.tolist(),
                "projectedLinePixels": predicted.tolist(),
                "observedEdgeMidpointPixels": line["viewportObservedPixels"][
                    2:
                ].tolist(),
                "endpointPerpendicularErrorsPx": errors[:2].tolist(),
                "edgeMidpointPerpendicularErrorsPx": errors[2:].tolist(),
                "perpendicularMaxPx": float(errors.max()),
                "sourceUncertaintyPx": line["sourceUncertaintyPx"],
                "geometryBoundPx": line["geometryBoundPx"],
                "axisPerspectiveBiasBoundPx": line["biasBoundPx"],
                "axisPerspectiveBiasComponents": dict(
                    line["axisPerspectiveBiasComponents"]
                ),
                "candidateOnly": True,
                "gpuAcceptanceEvaluated": False,
                "errorPx": conservative_error,
                "nativeSegmentCoversObservation": covered,
                "status": "passed"
                if covered and conservative_error <= threshold
                else "failed",
            }
        )
    return results


def camera_cv_parameters(camera, width, height):
    rotation = (
        Rotation.from_quat(camera["quaternion"]).as_matrix() @ np.diag([1, -1, -1])
    ).T
    focal = height / (2 * math.tan(math.radians(camera["verticalFovDegrees"]) / 2))
    return np.r_[
        Rotation.from_matrix(rotation).as_rotvec(),
        -rotation @ np.array(camera["positionMetres"]),
        math.log(focal),
        camera.get("principalPointViewportPixels", [width / 2, height / 2]),
    ]


def evaluate_bound_camera(
    parameters, context, threshold, evidence, parent_passed=True, native_lines=None
):
    """Reproject actual current native landmarks; inherited status is never an oracle."""
    frame, view, landmarks, points = context
    width, height = view["rectSourcePixels"][2:]
    check = [item for item in landmarks if item["role"] == "check"]
    fit = [item for item in landmarks if item["role"] == "fit"]
    missing = set(view.get("anchorPoseMissing", frame.get("anchorPoseMissing", [])))
    if missing & {item["anchorId"] for item in landmarks}:
        return None, "Moving CAD/source anchor pose is missing"
    if not check and not native_lines:
        return None, "Derived camera needs actual visible native held-out evidence"
    image = frame["sourceImage"]
    source = {
        "sha256": image["sourceSha256"],
        "width": image["width"],
        "height": image["height"],
    }
    for landmark in landmarks:
        finite_vector(landmark["pixel"], 2, "native check pixel")
        if "measurementEvidence" in landmark:
            measurement_evidence(landmark, "native landmark")
            measurement_image_identity(landmark, image, source, "native landmark")
        if "trackingEvidence" in landmark:
            if not finite_evidence(landmark["trackingEvidence"]):
                raise ValueError("Native landmark has invalid source tracking evidence")
            measurement_image_identity(
                {"measurementEvidence": landmark["trackingEvidence"]},
                image,
                source,
                "native landmark",
            )
    predicted, depths = project(
        parameters,
        np.array([points[item["anchorId"]] for item in landmarks]).reshape(-1, 3),
        width,
        height,
    )
    errors = np.linalg.norm(
        predicted - np.array([item["pixel"] for item in landmarks]).reshape(-1, 2),
        axis=1,
    )
    fit_indices = [i for i, item in enumerate(landmarks) if item["role"] == "fit"]
    check_indices = [i for i, item in enumerate(landmarks) if item["role"] == "check"]
    fit_errors, check_errors = errors[fit_indices], errors[check_indices]
    line_errors = evaluate_native_lines(
        parameters, native_lines or [], width, height, threshold
    )
    held_out_max = max(
        float(check_errors.max()) if check else 0.0,
        max((item["errorPx"] for item in line_errors), default=0.0),
    )
    rotation = Rotation.from_rotvec(parameters[:3]).as_matrix()
    return {
        "positionMetres": (-rotation.T @ parameters[3:6]).tolist(),
        "quaternion": Rotation.from_matrix(rotation.T @ np.diag([1, -1, -1]))
        .as_quat()
        .tolist(),
        "verticalFovDegrees": math.degrees(
            2 * math.atan(height / (2 * math.exp(parameters[6])))
        ),
        "principalPointViewportPixels": parameters[7:9].tolist(),
        "intrinsicsEvidence": evidence,
        "intrinsicsIdentifiability": "Independently constrained shared/source-registered camera; no per-view fitting",
        "intrinsicsAtSearchBoundary": False,
        "fitRmsPx": float(np.sqrt(np.mean(fit_errors**2))) if fit else 0.0,
        "fitMaxPx": float(fit_errors.max()) if fit else 0.0,
        "fitWeights": [],
        "heldOutMaxPx": held_out_max,
        "thresholdPx": threshold,
        "status": "passed"
        if parent_passed
        and np.all(depths > 0)
        and np.all(errors <= threshold)
        and all(item["status"] == "passed" for item in line_errors)
        else "failed",
        "projection": "pinhole; independently fixed square-pixel source camera; no fitted lens distortion",
        "coordinateConvention": "camera-to-CAD-world; quaternion xyzw; looks along local -Z with local +Y up",
        "checkErrors": [
            {
                "anchorId": landmarks[i]["anchorId"],
                "observedPixel": landmarks[i]["pixel"],
                "projectedPixel": predicted[i].tolist(),
                "errorPx": float(errors[i]),
            }
            for i in check_indices
        ],
        "nativeLineCheckErrors": line_errors,
    }, None


def resolve_camera_contexts(observations, contexts, points, inventory=None):
    """Resolve a closed graph of camera evidence before formatting source coordinates."""
    source = observations["source"]
    threshold = source["width"] * 0.02
    current = observations.get("kind") == "current-source-observations"
    rigs = {} if current else prepare_camera_rigs(observations, points)
    cpu_contexts = {
        key: context for key, context in contexts.items()
        if not current or (
            context[1].get("imagePlaneWarp") is None
            and context[1].get("resolvedImagePlaneWarp") is None
            and context[0].get("imagePlaneWarp") is None
        )
    }
    native_lines = prepare_native_line_checks(observations, cpu_contexts, inventory)
    resolved, active = {}, set()

    def rig_reference(reference):
        rig_id, phase = reference.get("rigId"), reference.get("phaseIndex")
        if (
            rig_id not in rigs
            or type(phase) is not int
            or phase not in rigs[rig_id]["images"]
        ):
            raise ValueError("Missing camera rig or invalid reference phase")
        rig = rigs[rig_id]
        return rig, phase

    def resolve(key):
        if key in resolved:
            return resolved[key]
        if key in active:
            raise ValueError(f"Source camera reference cycle at {key}")
        if key not in contexts:
            raise ValueError(f"Missing source camera parent {key}")
        active.add(key)
        context = contexts[key]
        frame, view, landmarks, posed_points = context
        width, height = view["rectSourcePixels"][2:]
        if current:
            provenance = view["cameraProvenance"]
            supplied_camera = view.get("camera")
            if key not in native_lines:
                result = (
                    copy.deepcopy(supplied_camera),
                    "CPU image-plane homography residuals are unsupported for this current view",
                )
            elif supplied_camera is not None:
                result = evaluate_bound_camera(
                    camera_cv_parameters(supplied_camera, width, height),
                    context,
                    threshold,
                    provenance["evidence"],
                    native_lines=native_lines[key],
                )
                if result[1]:
                    result = (copy.deepcopy(supplied_camera), result[1])
                else:
                    result = ({**copy.deepcopy(supplied_camera), **result[0]}, None)
                    for field in ("positionMetres", "quaternion", "verticalFovDegrees"):
                        result[0][field] = copy.deepcopy(supplied_camera[field])
            else:
                result = None
        else:
            evidence = view.get(
                "cameraEvidence", frame.get("cameraEvidence", {"kind": "direct-fit"})
            )
            kind = evidence.get("kind")
        if (current and result is None) or (not current and kind == "direct-fit"):
            result = fit_camera(
                {
                    "landmarks": landmarks,
                    "anchorPoseMissing": view.get(
                        "anchorPoseMissing", frame.get("anchorPoseMissing", [])
                    ),
                },
                posed_points,
                width,
                height,
                threshold,
                view.get("cameraFit", frame.get("cameraFit", {})),
            )
            if result[0] and native_lines[key]:
                line_errors = evaluate_native_lines(
                    camera_cv_parameters(result[0], width, height),
                    native_lines[key],
                    width,
                    height,
                    threshold,
                )
                result[0]["nativeLineCheckErrors"] = line_errors
                result[0]["heldOutMaxPx"] = max(
                    result[0]["heldOutMaxPx"],
                    max(item["errorPx"] for item in line_errors),
                )
                if any(item["status"] != "passed" for item in line_errors):
                    result[0]["status"] = "failed"
        elif current:
            pass
        elif kind == "shared-rigid-sequence":
            if view.get("cameraFit") or frame.get("cameraFit"):
                raise ValueError("Derived cameras cannot also specify cameraFit")
            rig, phase = rig_reference(evidence)
            if (
                view["rectSourcePixels"] != [0, 0, 1920, 1080]
                or view.get("presentation", "native") != "native"
            ):
                raise ValueError(
                    "Shared turntable cameras require a full native source viewport"
                )
            identity = source_image_key(frame.get("sourceImage"), source, str(key))
            registration = rig["sourceMap"].get(identity)
            if (
                not registration
                or not registration["phaseAccepted"]
                or registration["referencePhaseIndex"] != phase
            ):
                raise ValueError(
                    f"{key}: actual source image does not establish the claimed rig phase"
                )
            result = evaluate_bound_camera(
                rig["parameters"][phase],
                context,
                threshold,
                "Independent native-image 71-phase rigid turntable calibration",
                rig["passed"],
                native_lines[key],
            )
            if result[0]:
                result[0]["sharedRigValidation"] = {
                    "rigId": evidence["rigId"],
                    "phaseIndex": phase,
                    **rig["proof"],
                }
        elif kind == "source-registered":
            if view.get("cameraFit") or frame.get("cameraFit"):
                raise ValueError("Derived cameras cannot also specify cameraFit")
            own_image = source_image_key(frame.get("sourceImage"), source, str(key))
            if (
                source_image_key(evidence.get("sourceImage"), source, str(key))
                != own_image
            ):
                raise ValueError(f"{key}: stale registration source image")
            reference = evidence.get("reference", {})
            if "rigId" in reference:
                if "timeSeconds" in reference or "viewId" in reference:
                    raise ValueError("Registration must name exactly one parent")
                rig, phase = rig_reference(reference)
                parameters = rig["parameters"][phase].copy()
                parent_image, parent_passed = rig["images"][phase], rig["passed"]
                parent_rect = [0, 0, 1920, 1080]
            else:
                time = finite_vector(
                    [reference.get("timeSeconds")], 1, "reference sample"
                )[0]
                if "viewId" not in reference or not (
                    reference["viewId"] is None or isinstance(reference["viewId"], str)
                ):
                    raise ValueError(
                        "Registration requires an explicit reference view ID"
                    )
                parent_key = (time, reference["viewId"])
                parent_camera, reason = resolve(parent_key)
                if (
                    reason
                    or parent_camera is None
                    or parent_camera["status"] != "passed"
                ):
                    raise ValueError(
                        f"{key}: reference camera has not independently passed"
                    )
                parent_frame, parent_view, _, _ = contexts[parent_key]
                if parent_view.get("presentation", "native") != "native":
                    raise ValueError(
                        "Positive-scale source registration requires a native parent"
                    )
                parent_image, parent_rect = (
                    parent_frame.get("sourceImage"),
                    parent_view["rectSourcePixels"],
                )
                parameters = camera_cv_parameters(
                    parent_camera, parent_rect[2], parent_rect[3]
                )
                parent_passed = True
            if source_image_key(
                evidence.get("referenceSourceImage"), source, str(key)
            ) != source_image_key(parent_image, source, str(key)):
                raise ValueError(f"{key}: stale registration reference image")
            affine = finite_vector(
                evidence.get("sourceToViewportPixels"), 6, "source registration affine"
            )
            scale = affine[0]
            if scale <= 0 or not np.allclose(
                affine[[1, 3, 4]], [0, 0, scale], rtol=0, atol=1e-9
            ):
                raise ValueError(
                    "Source registration supports only positive uniform scale without shear/rotation"
                )
            rows, ids, source_pixels, viewport_pixels = [], set(), set(), set()
            for item in evidence.get("correspondences", []):
                measurement_evidence(item, "source registration")
                measurement_image_identity(item, frame["sourceImage"], source, str(key))
                identity = item.get("id")
                source_pixel = finite_vector(
                    item.get("sourcePixel"), 2, "registration reference pixel"
                )
                viewport_pixel = finite_vector(
                    item.get("viewportPixel"), 2, "registration observed pixel"
                )
                if (
                    not isinstance(identity, str)
                    or not identity
                    or identity in ids
                    or tuple(source_pixel) in source_pixels
                    or tuple(viewport_pixel) in viewport_pixels
                ):
                    raise ValueError(
                        "Registration fit/check correspondences must be distinct and disjoint"
                    )
                if (
                    not 0 <= source_pixel[0] < source["width"]
                    or not 0 <= source_pixel[1] < source["height"]
                    or not 0 <= viewport_pixel[0] < width
                    or not 0 <= viewport_pixel[1] < height
                ):
                    raise ValueError(
                        "Registration correspondence lies outside its actual image"
                    )
                ids.add(identity)
                source_pixels.add(tuple(source_pixel))
                viewport_pixels.add(tuple(viewport_pixel))
                prediction = scale * source_pixel + affine[[2, 5]]
                rows.append(
                    {
                        "id": identity,
                        "role": item["role"],
                        "observedPixel": viewport_pixel.tolist(),
                        "projectedPixel": prediction.tolist(),
                        "errorPx": float(np.linalg.norm(prediction - viewport_pixel)),
                    }
                )
            if any(
                sum(row["role"] == role for row in rows) < 2
                for role in ("fit", "check")
            ):
                raise ValueError(
                    "Registration requires >=2 distinct fit and >=2 disjoint actual-image check correspondences"
                )
            parameters[6] += math.log(scale)
            parameters[7:9] = (
                scale * (parameters[7:9] + parent_rect[:2]) + affine[[2, 5]]
            )
            result = evaluate_bound_camera(
                parameters,
                context,
                threshold,
                "Actual-image uniform-scale source registration of independently validated camera",
                parent_passed and all(row["errorPx"] <= threshold for row in rows),
                native_lines[key],
            )
            if result[0]:
                result[0]["registrationValidation"] = {
                    "scale": float(scale),
                    "fitMaxPx": max(
                        row["errorPx"] for row in rows if row["role"] == "fit"
                    ),
                    "heldOutMaxPx": max(
                        row["errorPx"] for row in rows if row["role"] == "check"
                    ),
                    "correspondenceErrors": rows,
                }
        else:
            raise ValueError(f"{key}: unknown camera evidence kind {kind}")
        active.remove(key)
        resolved[key] = result
        return result

    for key in contexts:
        resolve(key)
    return resolved


def _run_computation(observations, inventory):
    """Shared numeric computation; current callers supply only temporary legacy state."""
    if observations.get("kind") != "current-source-observations":
        validate(observations)
    points = world_points(observations, inventory)
    fitted = copy.deepcopy(observations)
    shots = {shot["id"]: shot for shot in observations["shots"]}
    required_frames = []
    measured, failures, missing = [], [], []
    contexts = {}
    for frame in fitted["frames"]:
        frame["camera"] = None
        shot = shots[frame["shotId"]]
        if not needs_machine(frame, shot):
            continue
        if observations.get("kind") == "current-source-observations" and not frame["views"]:
            missing.append({
                "timeSeconds": frame["timeSeconds"], "viewId": None,
                "reason": "Current source viewport layout remains unavailable",
            })
            continue
        targets = frame.get("views") or [
            {
                "presentation": frame.get("presentation", "native"),
                "imagePlaneWarp": frame.get("imagePlaneWarp"),
                "nativeLineChecks": frame.get("nativeLineChecks", []),
                "partOverrides": frame.get("partOverrides", []),
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
            contexts[(frame["timeSeconds"], view["id"])] = (
                frame,
                view,
                landmarks,
                posed_points,
            )
    cameras = resolve_camera_contexts(observations, contexts, points, inventory)
    for key, (frame, view, _, _) in contexts.items():
        camera, reason = cameras[key]
        x, y, width, height = view["rectSourcePixels"]
        presentation = view.get("presentation", "native")
        view["camera"] = camera
        if view["id"] is None:
            frame["camera"] = camera
        view.pop("cameraUnobservableReason", None)
        if view["id"] is None:
            frame.pop("cameraUnobservableReason", None)
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
                    error["observedPixel"][0] = width - 1 - error["observedPixel"][0]
                    error["projectedPixel"][0] = width - 1 - error["projectedPixel"][0]
                error["observedPixel"] = [
                    error["observedPixel"][0] + x,
                    error["observedPixel"][1] + y,
                ]
                error["projectedPixel"] = [
                    error["projectedPixel"][0] + x,
                    error["projectedPixel"][1] + y,
                ]
            for error in camera.get("nativeLineCheckErrors", []):
                for field in (
                    "observedLinePixels",
                    "observedEdgeMidpointPixels",
                    "projectedLinePixels",
                ):
                    for pixel in error[field]:
                        if presentation == "horizontal-mirror":
                            pixel[0] = width - 1 - pixel[0]
                        pixel[0] += x
                        pixel[1] += y
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
        if (
            observations.get("kind") != "current-source-observations"
            and (
                view["mechanicalState"]["status"] != "observed"
                or view["mechanicalState"].get("visiblePoseCompleteness") == "partial"
            )
        )
        or view["mechanicalState"].get("input") is None
    ]
    no_machine_source = not required_frames and all(
        not needs_machine(frame, shots[frame["shotId"]]) for frame in fitted["frames"]
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
        "candidateOnly": True,
        "gpuAcceptanceEvaluated": False,
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


def run(observations, inventory, *, historical_diagnostic=False):
    """Validate authority before computing; never materialize a fake derivative identity."""
    require_rest_projection(observations)
    if historical_diagnostic:
        if observations.get("identityDerivative", {}).get("kind") != "materialized-canonical-native-identity-derivative":
            raise ValueError("Historical diagnostics require a materialized canonical-native derivative")
        if observations.get("kind") == "current-source-observations":
            raise ValueError("Current observations cannot enter the historical diagnostic path")
        fitted, report = _run_computation(observations, inventory)
        report["historicalDiagnostic"] = True
        return fitted, report
    if inventory is None:
        raise ValueError("Current camera fitting requires the actual registered native inventory")
    contract = fresh_contract()
    contract.validate_observations(observations, inventory=inventory)
    adapted = copy.deepcopy(observations)
    for frame in adapted["frames"]:
        frame["mechanicalState"] = {"status": "unobservable", "input": None}
        for view in frame["views"]:
            if view["camera"] is None:
                view.pop("cameraMeasurement", None)
            view["mechanicalState"] = {
                "status": "chosen-feasible" if view["input"] is not None else "unobservable",
                "input": copy.deepcopy(view["input"]),
            }
    fitted, report = _run_computation(adapted, inventory)
    blockers = fitted["coverage"]["blockers"]
    for frame in fitted["frames"]:
        frame.pop("mechanicalState")
        frame.pop("camera", None)
        frame.pop("cameraUnobservableReason", None)
        for view in frame["views"]:
            view.pop("mechanicalState")
            reason = view.pop("cameraUnobservableReason", None)
            if view["camera"] is not None and "cameraMeasurement" not in view:
                view["cameraMeasurement"] = {
                    "model": copy.deepcopy(fitted["model"]),
                    "nativeIdentity": copy.deepcopy(fitted["nativeIdentity"]),
                    "sourceImage": copy.deepcopy(frame["sourceImage"]),
                    "evidence": "Current CAD/source FIT-only camera solution, checked against disjoint actual-source CHECK pixels.",
                }
                view["cameraProvenance"] = {
                    **view["cameraProvenance"],
                    "kind": "source-fit",
                    "evidence": (
                        view["cameraProvenance"]["evidence"]
                        + " Current camera solved from this exposure's FIT pixels only; "
                        "CHECK residuals are diagnostics, not stage qualification."
                    ),
                }
            if view["camera"] is None:
                view.pop("cameraMeasurement", None)
                reason = reason or "No solved current source camera"
            else:
                # Missing residual evidence does not invalidate a bound current camera candidate.
                reason = None
            if view["input"] is None:
                reason = "; ".join(filter(None, (reason, "No current complete mechanism input")))
            if reason:
                view.setdefault("unavailable", []).append({"reason": reason})
                blocker = f"{frame['timeSeconds']}/{view['id']}: {reason}"
                if blocker not in blockers:
                    blockers.append(blocker)
    fitted["coverage"]["status"] = report["coverageStatus"] = (
        "blocked" if blockers else observations["coverage"]["status"]
    )
    report["coverageBlockers"] = blockers
    contract.validate_observations(fitted, inventory=inventory)
    return fitted, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument(
        "--historical-diagnostic", action="store_true",
        help="Run the old materialized-derivative diagnostic, never current publication",
    )
    args = parser.parse_args()
    check_namespace(args.observations, historical_diagnostic=args.historical_diagnostic)
    observations = common.read_observations(args.observations)
    check_namespace(
        args.observations, historical_diagnostic=args.historical_diagnostic,
        video_id=observations["source"]["videoId"],
    )
    if args.output:
        check_namespace(
            args.output, historical_diagnostic=args.historical_diagnostic,
            output=True, video_id=observations["source"]["videoId"],
        )
    fitted, report = run(
        observations, json.loads(args.inventory.read_text()),
        historical_diagnostic=args.historical_diagnostic,
    )
    if args.output:
        common.write_observations(args.output, fitted)
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
                "nativeLineCheckErrors",
            )
            if key in fit
        }
        for fit in report["fits"]
    ]
    summary["missingCameraEvidenceCount"] = len(report["missingCameraEvidence"])
    print(json.dumps(summary, indent=2))
    if (
        args.historical_diagnostic
        and (
            (not report["measuredFitCount"] and not report["noCorrespondingMachineSource"])
            or report["failedFitTimes"]
        )
    ) or (args.require_complete and report["coverageStatus"] != "complete"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Produce a CHOSEN integration gauge from actual native crank point projection.

uv run --no-project --python web/.vite/calibration-venv/bin/python \
    web/scripts/6dW6VYXp9HM-visible-crank-gauge.py

The default model is the immutable raw cache at
web/.vite/model-source/<MECHANISM_DATA.provenance.modelSha256>.glb.
For an original raw GLB elsewhere, append --model /path/to/raw-native.glb.
The compressed public model is never an input to this gauge.

Source winding/tempo remain measured in the separate visible-crank packet. Native
sign and first-phase offset here are chosen under the EXISTING unqualified main
analysis16 camera; they are not historical shaft sign/home or camera calibration.
Actual native mechanics, released rest matrices and Three projection establish
which choice projects clockwise. Source images and full numerical execution
receipts stay private. The generic generator reads only the numeric gauge JSON.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np
from scipy.optimize import minimize_scalar

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
VIDEO_ID = "6dW6VYXp9HM"
SOURCE = WEB / f"content/canonical-native/{VIDEO_ID}.visible-crank-motion.json"
CONTROLS = WEB / f"content/canonical-native/{VIDEO_ID}.motion-controls.json"
NATIVE_DATA = WEB / "src/mechanics-data.ts"
OUTPUT = WEB / f"content/canonical-native/{VIDEO_ID}.visible-crank-gauge.json"
PRIVATE = WEB / f".vite/verification-output/{VIDEO_ID}-visible-crank-gauge"
CAMERA = {
    "positionMetres": [-0.5447613584304803, 0.16357081791578632, -0.07001628230473755],
    "quaternion": [-0.056508222022049706, -0.7048452460249034, -0.056508222022049706, 0.7048452460249035],
    "verticalFovDegrees": 30.0,
}
MATH_PATHS = ("src/mechanics.ts", "src/mechanics-data.ts", "src/kinematics.ts", "src/magnifier.ts")
PROJECTION_PATHS = ("node_modules/three/build/three.module.js", "node_modules/three/build/three.core.js")
NATIVE_PROGRAM = """
import fs from 'node:fs';
import * as THREE from 'three';
import {MECHANISM_DATA,createMechanismInput,createMechanismPose,solveMechanism} from './src/mechanics.ts';
const req=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const camera=new THREE.PerspectiveCamera(req.camera.verticalFovDegrees,1920/1080,.005,100);
camera.position.fromArray(req.camera.positionMetres);
camera.quaternion.fromArray(req.camera.quaternion).normalize();camera.updateMatrixWorld(true);
const data=MECHANISM_DATA.renderFrames;
const pivot=new THREE.Vector3(...data.crankPivotMm).multiplyScalar(.001);
const rest=new THREE.Vector3(...data.worldMatrices['ha-harmonic-analyzer/dt-drive-train/dt-crank-handle-1'].slice(12,15));
const axis=new THREE.Vector3(...data.crankAxis),input=createMechanismInput(),pose=createMechanismPose();
Object.assign(input,req.baseInput,{amplitudes:new Float64Array(req.baseInput.amplitudes),
 phases:new Float64Array(req.baseInput.phases),setup:{...req.baseInput.setup,driveCrankOffsetTurns:req.driveOffset}});
const world=new THREE.Vector3(),pixel=new THREE.Vector3(),rows=[];
for(const turns of req.turns){
 input.crankTurns=turns;solveMechanism(input,pose);
 world.copy(rest).sub(pivot).applyAxisAngle(axis,pose.crankAngleRad).add(pivot);
 pixel.copy(world).project(camera);
 rows.push({crankTurns:turns,actualCrankAngleRad:pose.crankAngleRad,worldMetres:world.toArray(),
  pixel:[(1+pixel.x)*960,(1-pixel.y)*540],channelAnglesRad:Array.from(pose.channelAnglesRad),
  equilibriumResidualNm:pose.equilibriumResidualNm});
}
console.log(JSON.stringify({modelSha256:MECHANISM_DATA.provenance.modelSha256,
 pivotMetres:pivot.toArray(),restHandleOriginMetres:rest.toArray(),axis:axis.toArray(),rows}));
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def execute(name, turns, base_input, offset):
    request = PRIVATE / f"{name}-request.json"
    save(request, {"camera": CAMERA, "turns": turns, "baseInput": base_input, "driveOffset": offset})
    run = subprocess.run(["bun", "-e", NATIVE_PROGRAM, str(request)], cwd=WEB, capture_output=True, text=True, check=True)
    actual = json.loads(run.stdout)
    save(PRIVATE / f"{name}-actual-native.json", actual)
    return actual


def ellipse_axes(points):
    centre, diameters, degrees = cv2.fitEllipse(points.astype(np.float32))
    # fitEllipse axes have arbitrary180deg polarity. Both source/native axes
    # point minor→original image +X and major→original image +Y consistently.
    degrees = (degrees + 90) % 180 - 90
    angle = math.radians(degrees)
    rotation = np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
    return np.array(centre), np.array(diameters) / 2, degrees, rotation


def signed_area(points):
    return float(np.sum(points[:, 0] * np.roll(points[:, 1], -1)
                        - points[:, 1] * np.roll(points[:, 0], -1)) / 2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        type=Path,
        help="Original raw native GLB; defaults to the SHA-addressed raw model cache",
    )
    args = parser.parse_args()
    try:
        text = NATIVE_DATA.read_text()
        native = json.loads(text.split("export const MECHANISM_DATA = ", 1)[1].rsplit(" as const", 1)[0])
        native_model_sha256 = native["provenance"]["modelSha256"]
    except (OSError, ValueError, IndexError, KeyError) as error:
        parser.error(f"Cannot read current native raw model pin from {NATIVE_DATA}: {error}")
    model = args.model if args.model is not None else WEB / ".vite/model-source" / f"{native_model_sha256}.glb"
    model_label = f"raw-model/{native_model_sha256}.glb"
    try:
        model_sha256 = digest(model)
    except OSError as error:
        description = "required raw model cache" if args.model is None else "--model raw native GLB"
        parser.error(
            f"Cannot read {description} at {model}: {error}. "
            "From web/, run `npm run fetch-model -- /path/to/raw-native.glb` to cache the original "
            "native bytes, or supply --model /path/to/raw-native.glb. The compressed public GLB "
            "cannot replace the raw source"
        )
    if model_sha256 != native_model_sha256:
        parser.error(
            f"Raw model SHA256 {model_sha256} differs from the current native pin "
            f"{native_model_sha256}; supply the original raw GLB, not the compressed public asset"
        )
    dependencies = {str(path.relative_to(ROOT)): path for path in (Path(__file__), SOURCE, CONTROLS)}
    dependencies.update({f"web/{path}": WEB / path for path in (*MATH_PATHS, *PROJECTION_PATHS)})
    before = {label: digest(path) for label, path in dependencies.items()}
    dependencies[model_label] = model
    before[model_label] = model_sha256
    source = json.loads(SOURCE.read_text())
    controls = json.loads(CONTROLS.read_text())
    if model_sha256 != controls["frozenCandidate"]["geometryAuthority"]["originalGlbSha256"]:
        parser.error("Source static/native association and actual raw model identity differ")
    if source["authority"]["selectedNativeSign"] is not None or source["authority"]["absoluteNativeHomeTurns"] is not None:
        raise ValueError("Source authority must not identify a native gauge")
    base_input = copy.deepcopy(controls["frozenCandidate"]["frames"][0]["chosenInput"])
    if base_input["crankTurns"] != 0 or base_input["setup"]["coneSwingRad"] != 0 or base_input["setup"]["driveCrankOffsetTurns"] != 0:
        raise ValueError("Original chosen-feasible fixture no longer has zero engaged drive")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    orbit = execute("orbit-positive-control", [i / 360 for i in range(361)], base_input, 0)
    if orbit["modelSha256"] != before[model_label]:
        raise ValueError("Executed native data and actual raw model identity differ")
    points = np.array([row["pixel"] for row in orbit["rows"][:-1]])
    centre, radii, degrees, rotation = ellipse_axes(points)
    measurement = source["measurement"]
    source_angle = math.radians((measurement["rotationDegrees"] + 90) % 180 - 90)
    source_rotation = np.array([[math.cos(source_angle), -math.sin(source_angle)],
                                [math.sin(source_angle), math.cos(source_angle)]])
    first = np.array(source["frames"][0]["fitFeature"]["pixels"])
    unit = (first - np.array(measurement["centrePixels"])) @ source_rotation / (np.array(measurement["diametersPixels"]) / 2)
    source_phase = math.atan2(unit[1], unit[0])

    def offset_cost(turns):
        position = turns * 360
        i = int(position) % 360
        weight = position - int(position)
        pixel = (1 - weight) * points[i] + weight * points[(i + 1) % 360]
        normalized = (pixel - centre) @ rotation / radii
        phase = math.atan2(normalized[1], normalized[0])
        return math.remainder(phase - source_phase, 2 * math.pi) ** 2

    seed = min((i / 360 for i in range(360)), key=offset_cost)
    fitted = minimize_scalar(offset_cost, bounds=(max(0, seed - 1 / 360), min(1, seed + 1 / 360)),
                             method="bounded", options={"xatol": 1e-14})
    if not fitted.success:
        raise ValueError("Chosen normalized first-phase offset did not converge")
    offset = float(fitted.x)
    relative = np.array([row["relativeCrankTurns"] for row in source["frames"]])
    expected = source_phase + relative * 2 * math.pi
    alternatives = []
    for sign in (1, -1):
        actual = execute(f"source-sign-{sign}", (sign * relative + offset).tolist(), base_input, offset)
        pixels = np.array([row["pixel"] for row in actual["rows"]])
        normalized = (pixels - centre) @ rotation / radii
        phase = np.unwrap(np.arctan2(normalized[:, 1], normalized[:, 0]))
        phase += 2 * math.pi * round((source_phase - phase[0]) / (2 * math.pi))
        errors = np.array([math.remainder(value - target, 2 * math.pi) for value, target in zip(phase, expected)])
        cycle = execute(f"winding-sign-{sign}", [offset + sign * i / 360 for i in range(361)], base_input, offset)
        cycle_pixels = np.array([row["pixel"] for row in cycle["rows"][:-1]])
        area = signed_area(cycle_pixels)
        alternatives.append({"nativeSign": sign, "shotLocalOffsetTurns": offset,
                             "originalPixelSignedOrbitAreaPx2": area,
                             "projectedDirection": "clockwise" if area > 0 else "counterclockwise",
                             "firstNormalizedPhaseResidualRad": float(errors[0]),
                             "normalizedPhaseRmsResidualRad": float(np.sqrt(np.mean(errors ** 2))),
                             "normalizedPhaseMaximumResidualRad": float(np.max(np.abs(errors))),
                             "projectedNormalizedUnwrappedTurns": float((phase[-1] - phase[0]) / (2 * math.pi)),
                             "actualNativeInputsSolved": len(actual["rows"]),
                             "maximumEquilibriumResidualNm": max(abs(row["equilibriumResidualNm"]) for row in actual["rows"])})
    if not alternatives[0]["originalPixelSignedOrbitAreaPx2"] < 0 < alternatives[1]["originalPixelSignedOrbitAreaPx2"]:
        raise ValueError("Actual native projection did not distinguish clockwise/counterclockwise choices")
    after = {label: digest(path) for label, path in dependencies.items()}
    if before != after:
        raise ValueError("Actually executed native/projection/source/producer dependency changed")
    packet = {
        "schemaVersion": 1, "kind": "chosen-visible-crank-projection-gauge", "videoId": VIDEO_ID,
        "sourceMotion": {"path": str(SOURCE.relative_to(ROOT)), "sha256": before[str(SOURCE.relative_to(ROOT))]},
        "chosenInputSource": {"path": str(CONTROLS.relative_to(ROOT)), "sha256": before[str(CONTROLS.relative_to(ROOT))],
                              "jsonPointer": "/frozenCandidate/frames/0/chosenInput", "historicalSetupRecovered": False},
        "interval": copy.deepcopy(source["interval"]),
        "chosenGauge": {"nativeSign": -1, "shotLocalOffsetTurns": offset, "driveCrankOffsetTurns": offset,
                        "kind": "chosen-under-existing-camera", "historicalNativeSignIdentified": False,
                        "historicalNativeHomeIdentified": False, "initialBankPoseRetainedByChosenLag": True},
        "baseChosenInput": base_input,
        "cameraAssociation": {"shotId": "analysis-16", "viewId": "main", "presentation": "native",
                              "referenceSourceTimeSeconds": 80, "camera": CAMERA,
                              "kind": "existing-chosen-component-framing", "sourceNativeCameraQualified": False},
        "modelSha256": orbit["modelSha256"],
        "nativeMathSha256": {f"web/{path}": before[f"web/{path}"] for path in MATH_PATHS},
        "projectionDependenciesSha256": {f"web/{path}": before[f"web/{path}"] for path in PROJECTION_PATHS},
        "producer": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": before[str(Path(__file__).relative_to(ROOT))]},
        "nativeMetadata": {key: orbit[key] for key in ("pivotMetres", "restHandleOriginMetres", "axis")},
        "projectionEllipse": {"centrePixels": centre.tolist(), "diametersPixels": (radii * 2).tolist(), "rotationDegrees": degrees},
        "sourceEllipse": {key: measurement[key] for key in ("centrePixels", "diametersPixels", "rotationDegrees")},
        "sourceFirstNormalizedPhaseRad": source_phase, "positiveControls": alternatives,
        "qualification": {"sourceAuthorityUnchanged": True, "sourceSelectedNativeSign": None, "sourceAbsoluteNativeHomeTurns": None,
                          "stageAcceptance": False, "GPUQualification": "UNEXECUTED",
                          "phaseAxisPolarity": "Both minor axes original +X and major axes original +Y; no arbitrary180deg ellipse-axis polarity transfer.",
                          "scope": "Actual native solver and released crank rest origin rotated about released pivot/+Z, then actual Three PerspectiveCamera.project. Same rigid crank transform as scene binding; CPU point proof, not GPU surface/source-pixel reprojection qualification. Native handle origin is a motion-control proxy, not independently proven brass-collar material correspondence.",
                          "cameraGeometry": "UNACCEPTED: projected and source ellipse sizes differ materially. This chosen gauge matches projected winding and approximate normalized phase/tempo, not historical camera, native shaft sign/home or model alignment.",
                          "sourcePhase": "Within-cycle source phase/local speed remain approximate affine-ellipse observations; full source windings/cycle periods are measured. Source bottom-hold noise is not physical instantaneous angular speed."},
        "integration": {"formula": "crankTurns = -relativeCrankTurns + chosenShotLocalOffsetTurns",
                        "bankLag": "Set fixed driveCrankOffsetTurns to the same chosen offset, retaining initial chosen bank pose. Other chosen-feasible amplitudes/phases/setup stay fixed and explicitly unobserved.",
                        "scope": "analysis-16/main/native only. Hold first/last chosen input over same-shot margins; no extrapolated cadence, artificial cuts or cross-shot phase transfer."},
    }
    save(OUTPUT, packet)
    print(json.dumps({"output": str(OUTPUT.relative_to(ROOT)), "chosenGauge": packet["chosenGauge"],
                      "positiveControls": alternatives, "modelSha256": packet["modelSha256"]}))


if __name__ == "__main__":
    main()

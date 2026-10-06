#!/usr/bin/env python3
"""Fit a private historical Analysis bank-drive diagnostic.

Require --historical-diagnostic; never amend published/canonical tracks.
The immutable CHECK ledger never enters the fit. Footage/crops stay private.
The positive effective-bank gauge is NOT a measured physical crank-shaft sign or
absolute phase. The negative gauge is fitted and retained rather than suppressed.
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
from scipy.optimize import Bounds, LinearConstraint, least_squares, minimize
from scipy.sparse import lil_matrix
from scipy.spatial.transform import Rotation

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
VIDEO_ID = "6dW6VYXp9HM"
CONTROLS = WEB / f"content/canonical-native/{VIDEO_ID}.motion-controls.json"
PRIVATE = WEB / f".vite/verification-output/{VIDEO_ID}-automatic-motion"
OUTPUT = PRIVATE / "diagnostic.json"
HISTORICAL_MODEL_SHA = "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d"
HISTORICAL_COMMIT = "1268c23d4a8fc741147c5e09d8d1e45247a71945"
SOURCE_SHA = "5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52"


def private_output(path):
    output = Path(path).resolve()
    external_temp = not output.is_relative_to(WEB.resolve()) and any(
        output.is_relative_to(Path(temp)) for temp in ("/tmp", "/var/tmp"))
    if output.is_relative_to((WEB / "content").resolve()) or not (
            output.is_relative_to((WEB / ".vite/verification-output").resolve()) or external_temp):
        raise ValueError("Historical diagnostics require private .vite/verification-output or external temporary output; cannot write published content or canonical originals")
    return output


def require_historical_native(*, historical_diagnostic=False):
    if historical_diagnostic is not True:
        raise ValueError("Analysis native diagnostics require historical_diagnostic=True")
    text = (WEB / "src/mechanics-data.ts").read_text()
    native = json.loads(text.split("export const MECHANISM_DATA = ", 1)[1].rsplit(" as const", 1)[0])
    if (
            native.get("provenance", {}).get("modelSha256") != HISTORICAL_MODEL_SHA
            or native.get("provenance", {}).get("sourceCommit") != HISTORICAL_COMMIT):
        raise ValueError("Current native data cannot reuse the original historical Analysis association")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def expand_checks(packet, frames):
    anchors = {row["id"]: row for row in packet["anchors"]}
    exposures = {row["frameIndex"]: row["sourceImage"] for row in frames}
    rows = []
    for retained in packet["rows"]:
        row = copy.deepcopy(retained)
        anchor = anchors[row.pop("anchorId")]
        qualification = packet["sourceQualifications"][row.pop("sourceQualificationId")]
        row.update({key: anchor[key] for key in ("sourceStation", "corner", "nativePartPath", "nativeLocalVertexMetres")})
        row["sourceOriginal"].update(qualification)
        row["sourceOriginal"].update({key: anchor[key] for key in ("corner", "sourceLandmarkId")})
        row["sourceImage"] = exposures[row["frameIndex"]]
        if row["sourcePixel"] != row["sourceOriginal"]["pixel"]:
            raise ValueError(f"Retained CHECK source pixel differs: {row['rowId']}")
        rows.append(row)
    return {**packet, "rows": rows}


def rocker(theta, channel):
    # Same circle-intersection lifting branch as mechanics.ts solveChannel and
    # the retained Analysis reserved-margin-fit/model.py:43-44; units stay mm.
    c = channel
    lobe = theta - c["camHomeRad"]
    cx = c["camShaftMm"][0] - c["eccentricityMm"] * np.sin(lobe)
    cy = c["camShaftMm"][1] + c["eccentricityMm"] * np.cos(lobe)
    ax, ay = cx - c["pivotMm"][0], cy - c["pivotMm"][1]
    d = np.hypot(ax, ay)
    radius2 = np.dot(c["rodPinMm"], c["rodPinMm"])
    a = (radius2 - c["rodLengthMm"] ** 2 + d * d) / (2 * d)
    h = np.sqrt(radius2 - a * a)
    px, py = (a * ax + h * ay) / d, (a * ay - h * ax) / d
    return (np.arctan2(py, px) - math.atan2(*c["rodPinMm"][::-1]) + np.pi) % (2 * np.pi) - np.pi


def rotation_z(angle):
    angle = np.asarray(angle)
    result = np.zeros(angle.shape + (3, 3))
    c, s = np.cos(angle), np.sin(angle)
    result[..., 0, 0] = result[..., 1, 1] = c
    result[..., 0, 1], result[..., 1, 0], result[..., 2, 2] = -s, s, 1
    return result


class Projection:
    """Unchanged original native rest matrices and frozen mirrored FIT camera."""
    def __init__(self, native, candidate, anchors, *, historical_diagnostic=False):
        if historical_diagnostic is not True:
            raise ValueError("Historical projection requires historical_diagnostic=True")
        if (
                any(str(record.get("kind", "")).startswith(("current-", "fresh-"))
                    or record.get("freshSourceRecord") is not None for record in (native, candidate))
                or candidate.get("geometryAuthority", {}).get("originalGlbSha256") != HISTORICAL_MODEL_SHA):
            raise ValueError("Historical projection requires the original native model association")
        self.channel = native["channel"]
        self.rest = {row["partPath"]: np.array(row["restWorldMatrix"]).reshape(4, 4, order="F")
                     for row in native["rest"] if "/ch-rocker-arm-" in row["partPath"]}
        self.anchors = {a["id"]: a for a in anchors}
        self.camera = np.array(candidate["analyticMirroredCameraParameters"])
        self.camera_rotation = Rotation.from_rotvec(self.camera[:3]).as_matrix()

    def point(self, beta, index, local):
        # Exact existing cap_world convention, including native saved rest angle.
        rest = self.rest[f"ha-harmonic-analyzer/ch-channel/ch-rocker-arm-{index + 1}"]
        rest_angle = math.atan2(-rest[1, 0], -rest[0, 0])
        pivot = np.array([*np.array(self.channel["pivotMm"]) / 1000, rest[2, 3]])
        at_rest = np.asarray(local) @ rest[:3, :3].T + rest[:3, 3]
        world = np.einsum("...ij,j->...i", rotation_z(beta - rest_angle), at_rest - pivot) + pivot
        camera = (world - self.camera[3:6]) @ self.camera_rotation
        depth = -camera[..., 2]
        return np.stack((self.camera[7] * 1000 - math.exp(self.camera[6]) * camera[..., 0] / depth,
                         self.camera[8] * 1000 - math.exp(self.camera[6]) * camera[..., 1] / depth), axis=-1)

    def centres(self, beta):
        return np.stack([self.point(beta[:, j], j, self.anchors[f"station-{20-j}-cap-centre"]["partLocalMetres"])
                         for j in range(20)], axis=1)


def graph_points(image):
    # Source white graphic is a seed only, NOT a physical observation. At x=pi
    # its authored curve disagrees with its rounded frequency caption. Never
    # use its sample fit as a final drive or mix it into cap CHECK objectives.
    neutral = (image.min(axis=2) > 235) & (np.ptp(image.astype(np.int16), axis=2) < 15)
    points = []
    for x in range(230, 1740, 11):
        ys = np.flatnonzero(neutral[570:810, x]) + 570
        runs = np.split(ys, np.where(np.diff(ys) > 1)[0] + 1)
        eligible = [run for run in runs if 4 <= len(run) <= 15]
        if len(eligible) == 1:
            points.append([x, float(np.mean(eligible[0]))])
    return np.array(points)


def decode(video, frames):
    video_hash = digest(video)
    capture = cv2.VideoCapture(str(video))
    first, last = frames[0]["frameIndex"], frames[-1]["frameIndex"]
    capture.set(cv2.CAP_PROP_POS_FRAMES, first)
    rows, previous = [], 0.001
    try:
        for expected in frames:
            index = expected["frameIndex"]
            if index != first + len(rows):
                raise ValueError("Expected a continuous original native-frame interval")
            ok, image = capture.read()
            if not ok:
                raise ValueError(f"Native source frame unavailable: {index}")
            identity = expected["sourceImage"]
            if video_hash != identity["sourceSha256"] or hashlib.sha256(image.tobytes()).hexdigest() != identity["sha256Bgr8"]:
                raise ValueError(f"Original bgr8 exposure identity mismatch: {index}")
            points = graph_points(image)
            if len(points) < 100:
                raise ValueError(f"Insufficient source-graphic seed support: {index}")
            x = (points[:, 0] - 221) / (1757 - 221) * np.pi
            fit = least_squares(lambda p: 689.5 - 100.5 * np.cos(p[0] * x) - points[:, 1],
                                [max(previous, 0.001)], bounds=([0], [2.5]), loss="soft_l1", f_scale=1)
            previous = float(fit.x[0])
            rows.append({"frameIndex": index, "timeSeconds": expected["timeSeconds"],
                         "sourceImage": copy.deepcopy(identity), "graphicSeedFrequency": previous,
                         "graphicSeedPoints": points.tolist(), "graphicSeedMaximumResidualPx": float(np.max(np.abs(fit.fun)))})
    finally:
        capture.release()
    if rows[-1]["frameIndex"] != last:
        raise ValueError("Native interval decode incomplete")
    return rows


def fit_branch(projection, source_pixels, graphic_rows, candidate, sign):
    count = len(graphic_rows)
    frequency = np.array([row["graphicSeedFrequency"] for row in graphic_rows])
    seeds = sign * 2 * (frequency - frequency[0])
    # Gauge fixes the first bank drive to zero. Independent constant per-station
    # offsets remain identifiable only relative to that gauge, not shaft home.
    initial_phases = np.zeros(20)
    seed_angles = np.array([row["rockerAnglesChosenWitnessRad"] for row in candidate["frames"]])
    for j in range(20):
        alternatives = [least_squares(lambda p: rocker(seeds * (20-j) * np.pi / 40 + p[0], projection.channel) - seed_angles[:, j],
                                      [seed], bounds=([-np.pi], [np.pi])) for seed in (-0.5, 0, 0.5)]
        initial_phases[j] = min(alternatives, key=lambda fit: np.dot(fit.fun, fit.fun)).x[0]
    sparsity = lil_matrix((count * 40, 20 + count - 1), dtype=int)
    for f in range(count):
        for j in range(20):
            sparsity[f*40+j*2:f*40+j*2+2, j] = 1
            if f:
                sparsity[f*40+j*2:f*40+j*2+2, 20+f-1] = 1
    harmonics = np.arange(20, 0, -1) * np.pi / 40
    def predict(parameters):
        turns = np.r_[0, parameters[20:]]
        beta = rocker(turns[:, None] * harmonics + parameters[:20], projection.channel)
        return projection.centres(beta), beta
    def objective(parameters):
        pixels, _ = predict(parameters)
        return (pixels - source_pixels).ravel()
    # Bounded neighbourhood retains the original observed first-sweep branch.
    # It does not manufacture an off-frame turn, choose a shaft sign, or force
    # a constant speed: every following native frame has its own measured drive.
    initial = np.r_[initial_phases, seeds[1:]]
    lower = np.r_[np.full(20, -np.pi), seeds[1:] - 0.6]
    upper = np.r_[np.full(20, np.pi), seeds[1:] + 0.6]
    fit = least_squares(objective, initial, jac_sparsity=sparsity.tocsr(), bounds=(lower, upper),
                        x_scale="jac", max_nfev=2000, ftol=1e-8, xtol=1e-10, gtol=1e-10,
                        tr_options={"atol": 1e-12, "btol": 1e-12, "maxiter": 1000})
    # The narrated first sweep increases cosine frequency, with actual even-turn
    # holds. Constrain this EFFECTIVE gauge's order, not the invisible shaft sign.
    # Independent per-frame noise must not become a fabricated brief reversal.
    order = np.zeros((count - 1, 20 + count - 1))
    for f in range(count - 1):
        order[f, 20 + f] = sign
        if f:
            order[f, 20 + f - 1] = -sign
    ordered_seed = fit.x.copy()
    ordered_seed[20:] = sign * np.maximum.accumulate(np.maximum(sign * fit.x[20:], 0))
    def constrained_objective(parameters):
        pixels, _ = predict(parameters)
        residual = pixels - source_pixels
        theta = np.r_[0, parameters[20:]][:, None] * harmonics + parameters[:20]
        step = 1e-5
        upper_pixels = projection.centres(rocker(theta + step, projection.channel))
        lower_pixels = projection.centres(rocker(theta - step, projection.channel))
        derivative = (upper_pixels - lower_pixels) / (2 * step)
        local = 2 * np.sum(residual * derivative, axis=2) / residual.size
        gradient = np.r_[np.sum(local, axis=0), np.sum(local[1:] * harmonics, axis=1)]
        return float(np.mean(residual**2)), gradient
    ordered = minimize(constrained_objective, ordered_seed, jac=True, method="SLSQP",
                       bounds=Bounds(lower, upper), constraints=LinearConstraint(order, 0, np.inf),
                       options={"maxiter": 500, "ftol": 1e-10})
    fit = ordered
    pixels, beta = predict(fit.x)
    return {"sign": sign, "turns": np.r_[0, fit.x[20:]], "phases": fit.x[:20], "pixels": pixels,
            "rocker": beta, "converged": bool(fit.success), "message": fit.message,
            "fitRmsPx": float(np.sqrt(np.mean((pixels-source_pixels)**2))),
            "fitMaximumEuclideanPx": float(np.max(np.linalg.norm(pixels-source_pixels, axis=2))),
            "atDriveBounds": int(np.sum((fit.x[20:] - lower[20:] < 1e-5) | (upper[20:] - fit.x[20:] < 1e-5)))}


def summarize(values):
    values = np.asarray(values)
    return {"count": len(values), "rms": float(np.sqrt(np.mean(values**2))),
            "median": float(np.median(values)), "p95": float(np.percentile(values, 95)), "maximum": float(np.max(values))}


def checks(projection, branch, ledger, frame_lookup):
    rows, firsts = [], {}
    absolute, displacements, within = [], [], 0
    source_motion, predicted_motion = [], []
    for original in ledger["rows"]:
        if original["sourceStatus"] != "measured":
            continue
        f, j = frame_lookup[original["frameIndex"]], 20-original["sourceStation"]
        predicted = projection.point(branch["rocker"][f, j], j, original["nativeLocalVertexMetres"])
        actual = np.array(original["sourcePixel"])
        anchor = (original["sourceStation"], original["corner"])
        delta = predicted - actual
        absolute.append(float(np.linalg.norm(delta)))
        row = {"rowId": original["rowId"], "frameIndex": original["frameIndex"], "sourceImage": original["sourceImage"],
               "sourceStation": original["sourceStation"], "nativePartPath": original["nativePartPath"],
               "nativeLocalVertexMetres": original["nativeLocalVertexMetres"], "sourcePixel": original["sourcePixel"],
               "sourceUncertaintyPx": original["sourceOriginal"]["uncertaintyPx"], "predictedPixel": predicted.tolist(),
               "absoluteResidualPx": delta.tolist(), "usedInFit": False}
        if anchor not in firsts:
            firsts[anchor] = (predicted, actual, row)
        else:
            baseline_prediction, baseline_actual, baseline = firsts[anchor]
            displacement = (predicted-baseline_prediction) - (actual-baseline_actual)
            allowance = row["sourceUncertaintyPx"] + baseline["sourceUncertaintyPx"]
            displacements.append(float(np.linalg.norm(displacement)))
            source_motion.append(float(np.linalg.norm(actual-baseline_actual)))
            predicted_motion.append(float(np.linalg.norm(predicted-baseline_prediction)))
            inside = bool(np.max(np.abs(displacement)) <= allowance)
            within += inside
            row["motionControl"] = {"baselineRowId": baseline["rowId"], "baselineFrameIndex": baseline["frameIndex"],
                                    "baselineSourceImage": baseline["sourceImage"], "residualPx": displacement.tolist(),
                                    "coordinateMaxSourceLocalizationAllowancePx": allowance,
                                    "withinSourceLocalizationAllowance": inside}
        rows.append(row)
    return rows, {"measuredChecks": len(rows), "unresolvedChecksPreserved": ledger["counts"]["unresolved"],
                  "absoluteEuclideanPx": summarize(absolute), "relativeMotionEuclideanPx": summarize(displacements),
                  "sourceCheckMotionRmsPx": float(np.sqrt(np.mean(np.square(source_motion)))),
                  "nativePredictedCheckMotionRmsPx": float(np.sqrt(np.mean(np.square(predicted_motion)))),
                  "relativeMotionRmsFraction": float(np.sqrt(np.sum(np.square(displacements)) / np.sum(np.square(source_motion)))),
                  "relativeMotionWithinSourceLocalizationAllowance": within, "relativeMotionControls": len(displacements),
                  "interpretation": "Independent original corner CHECKs, never fit. Relative displacement cancels one fixed registration bias; absolute residuals remain required and are reported separately. No native/GPU qualification is claimed."}


def native_smoke(inputs, predicted, *, historical_diagnostic=False):
    if historical_diagnostic is not True:
        raise ValueError("Analysis native smoke requires historical_diagnostic=True")
    private_output(PRIVATE)
    require_historical_native(historical_diagnostic=True)
    program = """
import {readFileSync} from 'node:fs';
import {MECHANISM_DATA,createMechanismInput,createMechanismPose,solveMechanism} from './src/mechanics.ts';
const rows=JSON.parse(readFileSync(process.argv[1],'utf8')).inputs,input=createMechanismInput(),pose=createMechanismPose(),out=[];
for(const row of rows){Object.assign(input,row,{amplitudes:new Float64Array(row.amplitudes),phases:new Float64Array(row.phases),setup:{...row.setup}});
 solveMechanism(input,pose);out.push({rockerAnglesRad:Array.from(pose.rockerAnglesRad),channelAnglesRad:Array.from(pose.channelAnglesRad),crankAngleRad:pose.crankAngleRad,equilibriumResidualNm:pose.equilibriumResidualNm});}
console.log(JSON.stringify({modelSha256:MECHANISM_DATA.provenance.modelSha256,sourceCommit:MECHANISM_DATA.provenance.sourceCommit,rows:out}));
"""
    path = PRIVATE / "native-inputs.json"
    code_paths = ("src/mechanics.ts", "src/mechanics-data.ts", "src/kinematics.ts", "src/magnifier.ts")
    code_hashes = {name: digest(WEB / name) for name in code_paths}
    write_json(path, {"historicalDiagnostic": True, "publishable": False,
                      "productionIntegrated": False, "inputs": inputs})
    result = subprocess.run(["bun", "-e", program, str(path)], cwd=WEB, capture_output=True, text=True, check=True)
    if code_hashes != {name: digest(WEB / name) for name in code_paths}:
        raise ValueError("Actually executed native math changed during the smoke run")
    receipt = json.loads(result.stdout)
    if (
            receipt.get("modelSha256") != HISTORICAL_MODEL_SHA
            or receipt.get("sourceCommit") != HISTORICAL_COMMIT):
        raise ValueError("Executed native data differs from the original historical Analysis association")
    actual = receipt["rows"]
    discrepancy = float(np.max(np.abs(np.array([r["rockerAnglesRad"] for r in actual])-predicted)))
    if discrepancy > 1e-12:
        raise ValueError(f"Native rocker forward smoke disagrees: {discrepancy}")
    receipt.update({"historicalDiagnostic": True, "publishable": False, "productionIntegrated": False})
    write_json(PRIVATE / "actual-native-forward.json", receipt)
    return {"historicalDiagnostic": True, "publishable": False, "productionIntegrated": False,
            "nativeModelSha256": receipt["modelSha256"], "nativeSourceCommit": receipt["sourceCommit"],
            "status": "all-native-inputs-solved", "sourceExposures": len(actual),
            "nativeMathSha256": {f"web/{name}": value for name, value in code_hashes.items()},
            "maximumRockerForwardDifferenceRad": discrepancy,
            "maximumEquilibriumResidualNm": max(abs(r["equilibriumResidualNm"]) for r in actual),
            "GPUQualification": "UNEXECUTED", "actualCrankAngleRangeRad": [min(r["crankAngleRad"] for r in actual), max(r["crankAngleRad"] for r in actual)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-diagnostic", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--video", type=Path, default=WEB / f".vite/reference-root/videos/{VIDEO_ID}.mp4")
    parser.add_argument("--cached-decode", type=Path, help="Reuse only exact source-hash-validated native decode produced by this script")
    args = parser.parse_args()
    try:
        output = private_output(args.output)
        private_output(PRIVATE)
    except ValueError as error:
        parser.error(str(error))
    current = (WEB / "content/v39-source").resolve()
    if any(path.resolve().is_relative_to(current) for path in (CONTROLS, args.video, args.cached_decode) if path is not None):
        parser.error("Historical diagnostics cannot consume current source namespace inputs")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    controls = load(CONTROLS)
    if (
            str(controls.get("kind", "")).startswith(("current-", "fresh-"))
            or controls.get("freshSourceRecord") is not None
            or controls.get("identityDerivative", {}).get("kind") != "materialized-canonical-native-identity-derivative"
            or controls.get("videoId") != VIDEO_ID
            or controls.get("frozenCandidate", {}).get("geometryAuthority", {}).get("originalGlbSha256") != HISTORICAL_MODEL_SHA
            or any(row["sourceImage"].get("sourceSha256") != SOURCE_SHA for row in controls["sourceFits"]["frames"])):
        raise ValueError("Analysis diagnostics require the original historical source/model tuple")
    require_historical_native(historical_diagnostic=True)
    candidate, centres, native = controls["frozenCandidate"], controls["sourceFits"], controls["nativeRest"]
    ledger = expand_checks(controls["independentCornerChecks"], centres["frames"])
    if controls["lineage"]["nativeRest"]["sha256"] != candidate["geometryAuthority"]["staticNativeRestPacketSha256"]:
        raise ValueError("Immutable original native rest authority differs")
    frames = centres["frames"]
    if [r["frameIndex"] for r in frames] != [r["frameIndex"] for r in candidate["frames"]]:
        raise ValueError("Original source centre/candidate interval differs")
    if any(r["chosenInput"]["crankTurns"] != 0 or r["chosenInput"]["setup"]["coneSwingRad"] != 0 or r["chosenInput"]["setup"]["driveCrankOffsetTurns"] != 0 for r in candidate["frames"]):
        raise ValueError("Frozen candidate no longer has its declared zero bank drive")
    for source, witness in zip(frames, candidate["frames"]):
        if source["sourceImage"] != witness["sourceFrameIdentity"]["sourceImage"]:
            raise ValueError("Original source centre/candidate exposure differs")
    if args.cached_decode:
        decoded = load(args.cached_decode)
        if (
                str(decoded.get("kind", "")).startswith(("current-", "fresh-"))
                or decoded.get("freshSourceRecord") is not None):
            raise ValueError("Historical diagnostics cannot consume current source records")
        if decoded["producerSha256"] != digest(Path(__file__)) or decoded["videoSha256"] != digest(args.video):
            raise ValueError("Cached native decode producer/source identity differs")
        graphic_rows = decoded["rows"]
        if [r["sourceImage"] for r in graphic_rows] != [r["sourceImage"] for r in frames]:
            raise ValueError("Cached native exposure identities differ")
    else:
        graphic_rows = decode(args.video, frames)
        write_json(PRIVATE / "native-source-decode.json", {
            "historicalDiagnostic": True, "publishable": False, "productionIntegrated": False,
            "producerSha256": digest(Path(__file__)), "videoSha256": digest(args.video), "rows": graphic_rows})
    projection = Projection(native, candidate, controls["nativeLandmarkAnchors"], historical_diagnostic=True)
    source_pixels = np.array([[next(p["pixel"] for p in frame["physicalFaceCentroids"] if p["sourceStation"] == 20-j) for j in range(20)] for frame in frames])
    branches = [fit_branch(projection, source_pixels, graphic_rows, candidate, sign) for sign in (1, -1)]
    frame_lookup = {frame["frameIndex"]: i for i, frame in enumerate(frames)}
    branch_reports = []
    for branch in branches:
        rows, report = checks(projection, branch, ledger, frame_lookup)
        report.update({key: branch[key] for key in ("sign", "converged", "message", "fitRmsPx", "fitMaximumEuclideanPx", "atDriveBounds")})
        report["phasesRad"] = branch["phases"].tolist()
        report["crankTurns"] = branch["turns"].tolist()
        write_json(PRIVATE / f"independent-corner-checks-sign-{branch['sign']}.json", {
            "historicalDiagnostic": True, "publishable": False, "productionIntegrated": False,
            "summary": report, "rows": rows})
        branch_reports.append(report)
        print(json.dumps({k: v for k, v in report.items() if k not in ("phasesRad", "crankTurns")}), flush=True)
    chosen = branches[0]
    if not chosen["converged"] or chosen["atDriveBounds"]:
        raise ValueError("Coherent positive-gauge fit did not converge within observed first sweep")
    fixed_input = copy.deepcopy(candidate["frames"][0]["chosenInput"])
    fixed_input["phases"] = chosen["phases"].tolist()
    inputs = []
    for turns in chosen["turns"]:
        value = copy.deepcopy(fixed_input)
        value["crankTurns"] = float(turns)
        inputs.append(value)
    native_report = native_smoke(inputs, chosen["rocker"], historical_diagnostic=True)
    cadence = np.diff(chosen["turns"]) / np.diff([r["timeSeconds"] for r in frames])
    packet = {"schemaVersion": 1, "kind": "historical-source-bank-drive-diagnostic", "videoId": VIDEO_ID,
              "historicalDiagnostic": True, "publishable": False, "productionIntegrated": False,
              "interval": {"startSeconds": frames[0]["timeSeconds"], "endSeconds": frames[-1]["timeSeconds"],
                           "firstNativeFrameIndex": frames[0]["frameIndex"], "lastNativeFrameIndex": frames[-1]["frameIndex"],
                           "nativeFrameCount": len(frames), "shotId": "analysis-22", "viewId": "bar-bank", "presentation": "horizontal-mirror"},
              "authority": {"videoSha256": graphic_rows[0]["sourceImage"]["sourceSha256"],
                            "nativeModelSha256": candidate["geometryAuthority"]["originalGlbSha256"],
                            "controls": {"path": str(CONTROLS.relative_to(ROOT)), "sha256": digest(CONTROLS)},
                            "originalNumericLineage": controls["lineage"],
                            "producer": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": digest(Path(__file__))},
                            "narratedZeroAndRatio": {"path": "references/engineerguy-youtube/(34) Analysis Explaining Fourier analysis with a machine.vtt",
                                                    "zeroSeconds": [95.34, 100.999], "twoTurnsPerFrequencyUnitSeconds": [112.419, 116.979]},
                            "method": "One source-FIT effective drive per actual native exposure and twenty constant setup phases; fixed original mirrored FIT camera; least-squares on unchanged chromatic cap FIT pixels only with narrated increasing first-sweep frequency order. Independent cap corner CHECKs never enter fit, rank, seed or branch selection.",
                            "graphicRole": "Native-decoded white cosine graphic supplies a bounded first-sweep seed only. Its spatial curve is not promoted to a measured shaft phase or used as final motion authority.",
                            "physicalCrankDirection": "unobservable", "absolutePhysicalCrankPhase": "unobservable",
                            "effectiveBankGauge": "Positive first-sweep continuation, first native exposure set to zero; NOT a resolved physical shaft sign or home.",
                            "cadenceQualification": "Per-native-frame finite differences of a conditional source-FIT effective drive, not measured instantaneous physical shaft speed. Source centroid/localization and incomplete native geometry create local cadence uncertainty; actual source times and pauses are retained, no constant-RPM assumption.",
                            "amplitudesAndHiddenSetup": "Original first frozen source-FIT complete witness held fixed; not recovered historical settings. Rocker cap motion is independent of these amplitude settings."},
              "fixedInput": fixed_input,
              "stationCorrespondence": [{"sourceStation": k, "harmonic": k, "nativeStationIndex": 20-k,
                                         "nativePartPath": f"ha-harmonic-analyzer/ch-channel/ch-rocker-arm-{21-k}"} for k in range(1, 21)],
              "frames": [{"frameIndex": row["frameIndex"], "timeSeconds": row["timeSeconds"], "sourceImage": row["sourceImage"],
                          "crankTurns": float(chosen["turns"][i]), "rockerAnglesRad": chosen["rocker"][i].tolist()} for i, row in enumerate(frames)],
              "diagnostics": {"signedAlternatives": branch_reports, "nativeForwardSmoke": native_report,
                              "cadenceTurnsPerSecond": summarize(np.abs(cadence)), "minimumSignedCadenceTurnsPerSecond": float(np.min(cadence)),
                              "totalEffectiveBankTurns": float(chosen["turns"][-1]-chosen["turns"][0]),
                              "positiveGaugeChosenNotSourceSign": True,
                              "historicalRodBranchAmbiguity": controls["historicalRodBranchAmbiguity"],
                              "cameraAndGeometryQualification": "INCOMPLETE; original frozen camera/rest association retained, absolute independent residuals reported, no new GPU or full435 claim."},
              "unavailable": [{"scope": "physical crank shaft during this bank-only interval", "reason": "Shaft/handle absent; cosine bank and signed alternative fit do not uniquely establish absolute physical shaft sign/home or bank lag."},
                              {"scope": "before112.3122 and after119.08563333333333", "reason": "No coherent motion inferred outside this exact continuous204-native-frame authority interval; do not transfer cadence across editorial cuts or endpoint holds."},
                              {"scope": "original independent cap corner nulls", "count": ledger["counts"]["unresolved"], "reason": "Unresolved/annotation-occluded original source pixels remain unresolved; no fabricated CHECKs."}],
              "integration": {"interpolation": "Linear cumulative crankTurns in actual source seconds within this interval only. Fixed phases/amplitudes/setup, engaged cone. Native solveMechanism drives all20 stations via physicalChannelAngle(crankTurns-driveCrankOffsetTurns,j)+phases[j].",
                              "scope": "Historical diagnostic only; never replace production input rows or amend source cameras, observations, CHECK roles or video corpora.",
                              "stageAcceptance": False}}
    write_json(output, packet)
    print(json.dumps({"output": str(output), "totalEffectiveBankTurns": packet["diagnostics"]["totalEffectiveBankTurns"], "nativeSmoke": native_report}), flush=True)


if __name__ == "__main__":
    main()

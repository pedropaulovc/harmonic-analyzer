#!/usr/bin/env python3
"""Publish explicit v39 Analysis/Synthesis choices, not refreshed old certificates.

Run after adopt-v39-source-observations.py and the supported model import:
  python web/scripts/generate-analysis-synthesis-current-associations.py
Then run generate-analysis-synthesis-source-tracks.py. Both commands prepare the
complete pair before publishing; --video limits either command to one video.

Historical compact-track camera/input NUMBERS are newly chosen current candidates.
Their source/native fits, gauges, world receipts and GPU support are never adopted.
The current parameter domains, twenty native station owners and exact feature
associations are independently checked. Physical closure, posed feature support,
first-surface support, cameras and all source matching stages need parent execution.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
import re
from functools import lru_cache
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
spec = importlib.util.spec_from_file_location("compact_source_common", WEB / "scripts/compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
VIDEOS = ("6dW6VYXp9HM", "8KmVDxkia_w")
ANALYSIS_MODEL_SHA256 = "60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c"
MODEL_COMMIT = "81539e53f5146c06a77541415bd79da673806d96"
HISTORICAL_MODEL_SHA256 = "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d"
SOURCE_SHA = {
    "6dW6VYXp9HM": "5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52",
    "8KmVDxkia_w": "a7ac177e0c6eecdfe9b5817716eeb570c43b4590888f007c2cb6de8229ce1725",
}
HISTORICAL_DIGESTS = {
    "6dW6VYXp9HM.observations.json": "fa69d6cab6173baa7061e825e51651a8fc56bbbc66b6543c4510cd7851d64e36",
    "6dW6VYXp9HM.source-track.json": "a3898e1958ea70e145da699301b7061104ff804182e82d5902e3fb7964c602ba",
    "8KmVDxkia_w.observations.json": "3ac8e4df14487799637091859bdad58cc88a96c28a90c22ba1893772b5ee0f05",
    "8KmVDxkia_w.source-track.json": "3ed5ac6f307339e78e5bfc4ed20d397adda892de0b4d21ccafa9282b61e05d09",
    "analysis-synthesis.frozen-generation-evidence.json": "425beca33506fcb307c3892808b7871a8ee2f06b7aa90f7103fc6993e6319267",
    "6dW6VYXp9HM.automatic-motion.json": "37e00fb2569363dedf22d99cdc54229138990934497239d8b7201b97da2f0cc8",
    "6dW6VYXp9HM.motion-controls.json": "208d4a18a5c152805015e48b8be227a1825c1c03497c0e9370be109d6ca4daab",
    "6dW6VYXp9HM.bank-continuation.json": "8fc9d30edb54e43419b3c294b8a09410ec303382a47815552e75d3784f68b90b",
    "6dW6VYXp9HM.visible-crank-motion.json": "0433129092cb167a69d29b3a9712b81f5cb70701d173c97323c6045e33b827ba",
    "6dW6VYXp9HM.visible-crank-gauge.json": "6e58a2b704f81c211c31eb45a0c429521de114338e5e4c349ef74f9b509a973e",
    "8KmVDxkia_w.automatic-motion.json": "68b33f73055a49bbdbfad4e86d4f59ccc45e39b93be0b5b7fa71f3ec490dae3b",
    "8KmVDxkia_w.automatic-motion-evidence.json": "7a193758b02166ad02604274cd08b89135b2941f54301312d242efcc508e8233",
    "8KmVDxkia_w.framing-gpu-evidence-2026-10-01.json": "239cb59e799bbb42f6551b74c3b6cf1eccf66f9b0ec7c93518f743b37caf4173",
    "8KmVDxkia_w.bank-camera.json": "32f8f81c9355687839b48b3fc47ec19f3faa9c6fecd05d9a5be3260c24a27a66",
    "8KmVDxkia_w.bank-camera-fit-evidence.json": "4195ba69e2e3f7dec7c85bf91a0602857442e61a7e219d79caac50af967070e3",
    "8KmVDxkia_w.bank-camera-check.json": "2c7d67451c751cee95316ed1b5d39dd8147ef32ad125b65e372dc8ea61534c0a",
    "8KmVDxkia_w.bank-camera-check-evidence.json": "435691e429316b8dd234f6af3dbbfb9a672ee2b3e8d0af2d0914b0626e87bf88",
    "8KmVDxkia_w.camrod-sqpnp-probe-2026-10-01.json": "5a9f17e64671f84478fbdbc6de8cc620ae88932cfae78c3551dd029bc5cc1321",
    "8KmVDxkia_w.camrod-world-receipt-2026-10-01.json": "222d69eb315c39366e93cdcaacadd19a9074b153fa6f0db42d3ff5f9d2af8dbc",
    "8KmVDxkia_w.camrod-draw-epoch-world-receipt-2026-10-03.json": "af7f5ddb5add9c7bdf04ad7cdc1444faa3b3f94eff780978cd68759305d42f7d",
}
GROUPS = {
    "whole": ("/frame/", "/base/"),
    "spring": ("/channel/channel-lever-", "/channel/channel-spring-"),
    "bar": ("/channel/rocker-arm-", "/channel/amplitude-bar-"),
    "cone": ("/drive-train/cone", "/drive-train/cylinder", "/drive-train/crank"),
    "pen": ("/pen/pen-frame-", "/paper-drive/platen-"),
    "wheel": ("/magnifier/magnifying-wheel-", "/magnifier/wheel-axle-"),
    "top": ("/magnifier/magnifying-lever-", "/summing/"),
    "knife": ("/summing/",), "clamp": ("/magnifier/magnifying-clamp-",),
}
CAMERA_FIELDS = ("positionMetres", "quaternion", "verticalFovDegrees", "principalPointViewportPixels")
QUALIFICATION = {
    "inputStatus": "chosen-unmeasured-current", "cameraStatus": "chosen-unmeasured-current",
    "physicalClosure": "UNEXECUTED-current", "posedNativeFeatureSupport": "UNEXECUTED-current",
    "sourceFirstSurface": "UNEXECUTED-current", "GPUQualification": "UNEXECUTED",
    "historicalSettingsRecovered": False, "stageAcceptance": False,
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def historical(name):
    path = common.HISTORICAL_CONTENT / name
    if digest(path) != HISTORICAL_DIGESTS[name]:
        raise ValueError(f"Immutable historical lineage changed: {path}")
    return json.loads(path.read_text())


def lineage(name, pointer=None):
    result = {"path": f"web/content/{name}", "sha256": HISTORICAL_DIGESTS[name], "status": "historical-only"}
    if pointer is not None:
        result["jsonPointer"] = pointer
    return result


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def vector(value, count):
    return isinstance(value, list) and len(value) == count and all(finite(x) for x in value)


@lru_cache(maxsize=1)
def native_semantics():
    """Validate current exported datums and real renderer ownership, not old fits."""
    path = WEB / "src/mechanics-data.ts"
    match = re.search(r"export const MECHANISM_DATA = ([\s\S]+?) as const\s*$", path.read_text())
    if not match:
        raise ValueError("No supported-importer MECHANISM_DATA JSON")
    data = json.loads(match.group(1))
    model = common.current_model_identity()
    if model["sha256"] != ANALYSIS_MODEL_SHA256 or model["sourceCommit"] != MODEL_COMMIT:
        raise ValueError("Analysis/Synthesis requires the approved current v39 tuple")
    provenance = data["provenance"]
    if (provenance["modelSha256"] != model["sha256"] or provenance["sourceCommit"] != model["sourceCommit"]
            or data["harmonicNumbers"] != list(range(20, 0, -1)) or data["channel"]["count"] != 20
            or len(data["restChannels"]) != 20 or len(common.INPUT_FIELDS) != 51):
        raise ValueError("Current native station/input semantics changed")
    drive = data["driveTrain"]
    if (drive["crankRatio"] != [16, 64] or drive["cylinderTeeth"] != 120
            or len(drive["channelMeshes"]) != 20):
        raise ValueError("Current crank/channel drive semantics changed")
    for harmonic, mesh in zip(data["harmonicNumbers"], drive["channelMeshes"]):
        if (mesh["coneTeeth"] != harmonic * 6 or mesh["cylinderTeeth"] != 120
                or mesh["ratio"] != [harmonic * 6, 120]):
            raise ValueError("Source harmonic labels do not match current native gearing")
    parts = common.current_native_parts()
    bindings = common.native_motion_bindings()
    owners = []
    for index, rest in enumerate(data["restChannels"]):
        row = {"channelIndex": index, "nativeInstance": index + 1, "harmonicNumber": 20 - index, "owners": {}}
        for stem, key, motion in (
                ("rocker-arm", "rockerWorldMatrix", "rocker"), ("connecting-rod", "rodWorldMatrix", "rod"),
                ("amplitude-bar", "barWorldMatrix", "bar"), ("channel-lever", "leverWorldMatrix", "lever"),
                ("channel-spring-installed-stretch00", "springWorldMatrix", "channel-spring")):
            part = f"harmonic-analyzer/channel/{stem}-{index + 1}"
            if (part not in parts or rest[key] != parts[part]["worldMatrix"]
                    or [owner for pattern, owner in bindings if pattern.fullmatch(part)] != [motion]):
                raise ValueError(f"Current native station ownership/rest frame mismatch: {part}")
            row["owners"][motion] = part
        for stem, motion in (("cone-gear", "cone-spin"), ("cylinder-gear", "cylinder")):
            part = f"harmonic-analyzer/drive-train/{stem}-{index + 1}"
            if part not in parts or [owner for pattern, owner in bindings if pattern.fullmatch(part)] != [motion]:
                raise ValueError(f"Current harmonic drive owner is absent or ambiguous: {part}")
            row["owners"][motion] = part
        owners.append(row)
    for check in provenance["restChecks"]:
        part = parts.get(check["path"])
        if part is None or not vector(check["localPointMm"], 3):
            raise ValueError("Current native datum is absent")
        matrix = part["worldMatrix"]
        actual = [sum(matrix[k * 4 + axis] * check["localPointMm"][k] for k in range(3))
                  + 1000 * matrix[12 + axis] for axis in range(3)]
        if math.dist(actual, check["expectedMm"]) > check["toleranceMm"]:
            raise ValueError(f"Current native datum exceeds its unchanged exporter tolerance: {check['path']}")
    setup_owners = {
        "counterHeightM": ("harmonic-analyzer/summing/gooseneck-1", "gooseneck"),
        "platenOffsetM": ("harmonic-analyzer/paper-drive/platen-1", "platen"),
        "wireFixtureOffsetM": ("harmonic-analyzer/magnifier/output-fixture-1", "magnifier-fixture"),
        "coneSwingRad": ("harmonic-analyzer/drive-train/cone-swing-platform-1", "cone-swing"),
        "pinionCamRad": ("harmonic-analyzer/drive-train/pinion-cam-1", "pinion-cam"),
        "magnification": ("harmonic-analyzer/magnifier/magnifying-clamp-1", "magnifier-clamp"),
        "crankTurns": ("harmonic-analyzer/drive-train/crankshaft-1", "crank"),
    }
    for part, motion in setup_owners.values():
        if part not in parts or [owner for pattern, owner in bindings if pattern.fullmatch(part)] != [motion]:
            raise ValueError(f"Current input's native owner is absent or ambiguous: {part}")
    proof = {
        "model": model, "inputFields": list(common.INPUT_FIELDS), "fieldCount": 51,
        "stations": owners, "setupOwners": {key: {"partPath": part, "motion": motion} for key, (part, motion) in setup_owners.items()},
        "driveTrain": copy.deepcopy(drive),
        "sourceH20HalfSweepCrankEquivalentTurns": 2,
        "meanLineAngleRad": "Readout datum only; no physical spring rotation",
        "heldChannelTurns": "Cylinder-bank crank equivalent used only with disengaged cone",
        "driveCrankOffsetTurns": "Engaged bank drive = crankTurns - driveCrankOffsetTurns; no phase rewrite",
        "gearing": "small-large/medium-medium/large-small select current signed paper-feed multipliers 1/2/4",
        "amplitudes": "Physical native station order 20..1; normalized configured nominal station, not engraved stick units",
        "phases": "Twenty physical cam offsets in radians; no recovered historical phase",
        "runtimeHashes": {str(p.relative_to(ROOT)): digest(p) for p in (path, WEB / "src/mechanics.ts", WEB / "src/kinematics.ts", WEB / "src/bindings.ts")},
        "qualification": "Exact current native ownership/rest datums and parameter domains only; not dynamic closure, source camera, first surface or GPU",
    }
    return data, proof


def strict_input(value):
    data, _ = native_semantics()
    result = common.compact_input(value)
    if value != result or set(value) != {"crankTurns", "amplitudes", "phases", "gearing", "magnification", "setup"} or set(value["setup"]) != set(common.SETUP_FIELDS):
        raise ValueError("Chosen current input must name exactly all 51 fields")
    numbers = [result["crankTurns"], result["magnification"], *result["amplitudes"], *result["phases"]]
    numbers += [x for x in result["setup"].values() if x is not None]
    if not all(finite(x) for x in numbers):
        raise ValueError("Chosen current input has a nonfinite/boolean coordinate")
    low, _, high = data["magnifier"]["clampRadiusBandMm"]
    if not low / data["summing"]["anchorArmMm"] <= result["magnification"] <= high / data["summing"]["anchorArmMm"]:
        raise ValueError("Old numeric clamp candidate is outside current native travel")
    setup = result["setup"]
    if not data["magnifier"]["fixtureOffsetRangeM"][0] <= setup["wireFixtureOffsetM"] <= data["magnifier"]["fixtureOffsetRangeM"][1]:
        raise ValueError("Old numeric fixture candidate is outside current native rod travel")
    if not 0 <= setup["coneSwingRad"] <= data["setup"]["coneDisengageRad"] + 1e-12:
        raise ValueError("Old numeric cone candidate is outside current setup travel")
    if not data["setup"]["pinionEngageCamRad"] - 1e-12 <= setup["pinionCamRad"] <= 0:
        raise ValueError("Old numeric pinion candidate is outside current setup travel")
    return result


def strict_camera(value):
    result = {key: copy.deepcopy(value[key]) for key in CAMERA_FIELDS if key in value}
    if (not vector(result.get("positionMetres"), 3) or not vector(result.get("quaternion"), 4)
            or not finite(result.get("verticalFovDegrees")) or not 0 < result["verticalFovDegrees"] < 180
            or abs(sum(x*x for x in result["quaternion"]) - 1) > 1e-9
            or "principalPointViewportPixels" in result and not vector(result["principalPointViewportPixels"], 2)):
        raise ValueError("Old numeric camera is not a finite proper perspective candidate")
    return result


def family(frame, view, analysis):
    shot, vid = frame["shotId"], view["id"]
    if vid.startswith("endcard-"):
        return {"endcard-plaque": "whole", "endcard-intro": "whole", "endcard-synthesis": "whole", "endcard-bank": "bar", "endcard-analysis": "bar", "endcard-pen-inset": "pen", "endcard-spin": "whole", "endcard-rocker": "bar"}.get(vid, "pen")
    if analysis:
        n = int(shot.split("-")[-1])
        if vid == "pen-inset": return "pen"
        if vid == "bar-bank": return "bar"
        if n in (11, 12, 13, 26, 27, 28): return "spring"
        if n in (14, 15, 29, 30): return "pen"
        if n in (16, 17): return "cone"
        if n in range(18, 25): return "bar"
        return "whole"
    if vid == "upper-inset": return "spring"
    if vid == "lower-inset": return "bar"
    if vid == "main" and ("inset" in shot or "whole-spin" in shot): return "whole"
    if vid in ("outgoing", "incoming"):
        pairs = {"cam-to-rocker-fade": ("cone", "bar"), "top-overhead-fade": ("top", "spring"), "overhead-spring-fade": ("spring", "spring"), "lower-presenter-fade": ("cone", "whole")}
        if shot in pairs: return pairs[shot][vid == "incoming"]
    for names, result in ((('gear-macro', 'cone', 'gear-inset', 'crank', 'cam-rod'), 'cone'), (('rocker', 'bar-inset'), 'bar'), (('spring', 'overhead'), 'spring'), (('pen',), 'pen'), (('wheel',), 'wheel'), (('clamp',), 'clamp'), (('knife',), 'knife'), (('summing', 'magnifier', 'top-assembly'), 'top')):
        if any(name in shot for name in names): return result
    return "whole"


def fallback_choice(component, aspect):
    """Only missing/invalid choices use fresh actual current-native rest framing."""
    parts = common.current_native_parts()
    paths = sorted(path for path in parts if any(stem in path for stem in GROUPS[component]))
    if not paths:
        raise ValueError(f"No actual current native framing bodies for {component}")
    low = [min(parts[path]["worldBoundsMetres"]["min"][axis] for path in paths) for axis in range(3)]
    high = [max(parts[path]["worldBoundsMetres"]["max"][axis] for path in paths) for axis in range(3)]
    target = [(a+b)/2 for a, b in zip(low, high)]
    span = max(high[1]-low[1], (high[0]-low[0])/aspect, high[2]-low[2]) * 1.2
    distance = span / (2 * math.tan(math.radians(15)))
    camera = {"positionMetres": [target[0], target[1], target[2]-distance], "quaternion": [0., 1., 0., 0.], "verticalFovDegrees": 30.}
    data, _ = native_semantics()
    value = {"crankTurns": 0., "amplitudes": [0.]*20, "phases": [0.]*20, "gearing": "small-large", "magnification": data["magnifier"]["clampRadiusBandMm"][1]/data["summing"]["anchorArmMm"], "setup": {key: None if key == "counterHeightM" else 0. for key in common.SETUP_FIELDS}}
    return strict_camera(camera), strict_input(value), {"partPaths": paths, "worldBoundsMetres": {"min": low, "max": high}, "scope": "Chosen current rest framing only, not a source fit or improvement claim"}


def frame_key(frame):
    return [frame["shotId"], frame["timeSeconds"], frame["decodedTimeSeconds"]]


def layout(view):
    return {"id": view["id"], "rectSourcePixels": view["rectSourcePixels"], "presentation": view.get("presentation", "native"), "imagePlaneWarp": common.resolve_warp(view), "composite": common.compact_composite(view)}


def historical_anchors(video_id):
    rows = {}
    for suffix in ("observations", "source-track"):
        name = f"{video_id}.{suffix}.json"
        if historical(name)["model"]["sha256"] != HISTORICAL_MODEL_SHA256:
            raise ValueError("Original anchor evidence is not the immutable historical native model")
        for index, anchor in enumerate(historical(name)["anchors"]):
            if anchor["id"] in rows:
                previous = rows[anchor["id"]][0]
                if any(previous.get(key) != anchor.get(key) for key in ("partPath", "partLocalMetres", "worldMetres", "correspondenceEvidence")):
                    raise ValueError("Conflicting original native feature identities")
                continue
            rows[anchor["id"]] = (anchor, lineage(name, f"/anchors/{index}"))
    return rows


def decoded_frame_count(source):
    """Read recorded decode census, never duration/fps or observation-row counts.

    Original Analysis names its census decodedNativeFrameCount; Synthesis uses
    decodedFrameCount. Preserve each original JSON schema and require agreement
    if both independently recorded fields are present.
    """
    counts = [source[key] for key in ("decodedFrameCount", "decodedNativeFrameCount") if key in source]
    if not counts or any(type(count) is not int or count <= 0 for count in counts) or len(set(counts)) != 1:
        raise ValueError("Original source requires an unambiguous recorded decoded-frame census")
    return counts[0]


def validate_source(source, video_id):
    expected = historical(f"{video_id}.observations.json")["source"]
    if (source.get("videoId") != video_id or source.get("sha256") != SOURCE_SHA[video_id]
            or decoded_frame_count(source) != decoded_frame_count(expected)
            or any(source.get(key) != expected.get(key) for key in ("width", "height", "fps", "decodedFrameCount", "decodedNativeFrameCount", "lastDecodedFrameTimeSeconds", "lastDecodedTimeSeconds", "durationSeconds"))):
        raise ValueError("Original video identity/clock changed")


def validate_image(image, time, source, frame_index=None):
    index = image.get("frameIndex", frame_index)
    rate = source["fps"]["numerator"] / source["fps"]["denominator"]
    if (type(index) is not int or not 0 <= index < decoded_frame_count(source) or not finite(time)
            or abs(time-index/rate) > 1e-9 or image.get("sourceSha256") != source["sha256"]
            or image.get("width") != source["width"] or image.get("height") != source["height"]
            or image.get("pixelFormat", image.get("format")) != "bgr8"
            or not re.fullmatch(r"[0-9a-f]{64}", image.get("sha256Bgr8", ""))):
        raise ValueError("Source clock lacks its exact original PTS/BGR identity")
    if "pts" in image and image["pts"] != index * 1001:
        raise ValueError("Original exact PTS changed")


def source_clocks(video_id, source):
    """Split source event clocks from old camera/geometry-conditioned numbers."""
    if video_id == "6dW6VYXp9HM":
        name = f"{video_id}.visible-crank-motion.json"
        packet = historical(name)
        for row in packet["frames"]:
            validate_image(row["sourceImage"], row["timeSeconds"], source, row["frameIndex"])
        bank_name, continuation_name = f"{video_id}.automatic-motion.json", f"{video_id}.bank-continuation.json"
        bank, continuation = historical(bank_name), historical(continuation_name)
        bank_rows = bank["frames"][:-1] + continuation["frames"]
        for row in bank_rows:
            validate_image(row["sourceImage"], row["timeSeconds"], source, row["frameIndex"])
        if bank["frames"][-1]["sourceImage"] != continuation["frames"][0]["sourceImage"]:
            raise ValueError("Original Analysis bank boundary image/clock identity changed")
        return [{"id": "visible-main-crank", "originalEvidence": lineage(name),
                 "application": {"shotId": "analysis-16", "viewId": "main", "presentation": "native"},
                 "interval": copy.deepcopy(packet["interval"]),
                 "measurementStatus": "observed-source-cycles-approximate-within-cycle-phase",
                 "sourceMeasurement": copy.deepcopy(packet["measurement"]),
                 "relativeZero": copy.deepcopy(packet["integration"]["relativeZero"]),
                 "integration": {key: copy.deepcopy(packet["integration"][key]) for key in ("timeDomain", "interpolation")},
                 "localSpeedScope": "Source-only affine-ellipse finite differences are approximate, not exact perspective-calibrated instantaneous physical shaft speed or bottom-hold reversal",
                 "rows": [{key: copy.deepcopy(row[key]) for key in ("frameIndex", "timeSeconds", "sourceImage", "relativeCrankTurns", "localSpeedTurnsPerSecond", "fitFeature", "independentSteelControl", "screwControl", "woodGripControl")} for row in packet["frames"]],
                 "sourceSelectedNativeSign": None, "sourceAbsoluteNativeHomeTurns": None,
                 "phaseTransferToOtherShots": False,
                 "parameterScope": "Relative source ellipse phase only; retained current input sign/home/setup are explicitly chosen, not old projection proof"},
                {"id": "bank-source-exposure-clock", "originalEvidence": lineage(bank_name), "continuationEvidence": lineage(continuation_name),
                 "application": {"shotId": "analysis-22", "viewId": "bar-bank", "presentation": "horizontal-mirror"},
                 "measurementStatus": "original-source-exposure-and-holdout-clock-only",
                 "rows": [{key: copy.deepcopy(row[key]) for key in ("frameIndex", "timeSeconds", "sourceImage", "role") if key in row} for row in bank_rows],
                 "holdout": copy.deepcopy(continuation["holdout"]), "physicalCrankTrajectory": None,
                 "parameterScope": "No portable physical bank-turn clock is measured here; old geometry/camera-conditioned crank turns and cadence remain historical. Current numeric input continuation is explicitly chosen only.",
                 "sourceSelectedNativeSign": None, "sourceAbsoluteNativeHomeTurns": None, "phaseTransferToOtherShots": False}]
    motion_name, evidence_name = f"{video_id}.automatic-motion.json", f"{video_id}.automatic-motion-evidence.json"
    packet, evidence = historical(motion_name), historical(evidence_name)
    for rows in (evidence["annotations"], evidence["physicalMetalFIT"], evidence["physicalMetalCHECK"], evidence["nearestJointSource"]["rows"], evidence["lowerCrank"]["observations"]):
        for row in rows:
            validate_image(row["sourceImage"], row["timeSeconds"], source, row.get("frameIndex"))
    candidate = next(row for row in packet["bankCandidates"] if row["id"] == "bank-direction-+1")
    return [
        {"id": "bank-annotation-clock", "originalEvidence": lineage(motion_name), "sourcePixelEvidence": lineage(evidence_name),
         "application": {"shotId": "rocker-bank", "viewId": "main", "presentation": "native"},
         "interval": copy.deepcopy(packet["bankInterval"]), "measurementStatus": "observed-source-half-sweep-events",
         "events": copy.deepcopy(packet["bankMeasurement"]["sourceHigh20Extrema"]),
         "sourcePixels": {key: copy.deepcopy(evidence[key]) for key in ("annotations", "physicalMetalFIT", "physicalMetalCHECK")},
         "nearestJointSourcePixels": copy.deepcopy(evidence["nearestJointSource"]["rows"]),
         "sourceHarmonicLabels": [{"harmonicNumber": row["harmonicNumber"], "sourceStationOrdinal": row["physicalStationIndex"], "sourceEvidence": row["authority"], "nativeIndexAuthority": "Validated separately in inputSemantics; source label alone is not current native geometry proof"} for row in evidence["stationAssociations"]],
         "physicalCHECKHoldout": copy.deepcopy(packet["bankMeasurement"]["physicalCHECKHoldout"]),
         "chosenDenseClock": {"status": "chosen-approximate-source-clock", "knots": copy.deepcopy(candidate["knots"]),
             "cadenceRule": copy.deepcopy(packet["bankMeasurement"]["cadenceRule"]),
             "withinSweepFits": copy.deepcopy(packet["bankMeasurement"]["withinSweepFits"]),
             "conversion": "2 crank-equivalent turns per observed H20 half sweep, checked against current harmonic20 gearing; zero and within-sweep shape chosen",
             "nativeSign": 1, "nativeSignStatus": "chosen-not-source-identified", "historicalPhaseRecovered": False},
         "sourceSelectedNativeSign": None, "sourceAbsoluteNativeHomeTurns": None, "phaseTransferToOtherShots": False},
        {"id": "isolated-lower-crank", "originalEvidence": lineage(motion_name), "sourcePixelEvidence": lineage(evidence_name),
         "application": {"shotId": "lower-crank", "viewId": "main", "presentation": "native"},
         "intervalSeconds": copy.deepcopy(packet["lowerCrank"]["intervalSeconds"]),
         "intervalFrames": copy.deepcopy(evidence["lowerCrank"]["intervalFrames"]),
         "sourcePlaybackLabel": evidence["lowerCrank"]["sourcePlaybackLabel"],
         "timeDomain": "Published-video seconds; no2x playback-rate rescaling",
         "measurementStatus": "rough-source-ray-local-cadence-not-qualified-phase",
         "observations": copy.deepcopy(evidence["lowerCrank"]["observations"]),
         "roughTurnsPerVideoSecond": packet["lowerCrank"]["crankTurnsPerVideoSecond"],
         "phaseMatchQualified": False, "sourceSelectedNativeSign": None, "sourceAbsoluteNativeHomeTurns": None,
         "bankTransferPermitted": False, "parameterScope": "Independent bounded cut only; no lower-cut sign/cadence/home/phase enters the bank or any other shot"},
    ]


def choose_views(observations, historical_track, associations):
    old_rows = {}
    for index, frame in enumerate(historical_track["frames"]):
        for view_index, view in enumerate(frame["views"]):
            old_rows.setdefault((frame["shotId"], view["id"]), []).append((frame, view, index, view_index))
    mapped = {row["anchor"]["id"] for row in associations if row["status"] == "mapped"}
    choices = []
    for frame in common.selected_frames(observations):
        row = {"frameKey": frame_key(frame), "views": []}
        for view in common.source_views(frame, observations):
            component = family(frame, view, observations["source"]["videoId"] == VIDEOS[0])
            pool = old_rows.get((frame["shotId"], view["id"]), [])
            # Never borrow another shot, video, view identity, source pixels or image.
            selected = min(pool, key=lambda item: (abs(item[0]["decodedTimeSeconds"]-frame["decodedTimeSeconds"]), abs(item[0]["timeSeconds"]-frame["timeSeconds"]))) if pool else None
            failure, historical_choice, bounds = None, None, None
            if selected:
                old_frame, old_view, index, view_index = selected
                historical_choice = lineage(f"{observations['source']['videoId']}.source-track.json", f"/frames/{index}/views/{view_index}")
                try:
                    camera, value = strict_camera(old_view["camera"]), strict_input(old_view["input"])
                except (KeyError, TypeError, ValueError) as error:
                    failure = str(error)
            else:
                failure = "No historical numeric candidate for this exact original shot/view identity; no cross-shot/video/view borrowing"
            if failure:
                rect = view["rectSourcePixels"]
                camera, value, bounds = fallback_choice(component, rect[2]/rect[3])
            association_ids = sorted({point["anchorId"] for point in frame.get("landmarks", []) if point.get("viewId", "main") == view["id"] and point["anchorId"] in mapped})
            old_continuity = selected[1].get("cameraContinuityFamily") if selected and not failure else None
            branch = hashlib.sha256(old_continuity.encode()).hexdigest()[:16] if old_continuity else "chosen-rest"
            interpolation = "continuous-shot" if old_continuity and selected[1].get("cameraInterpolation") != "held" else "held"
            row["views"].append({"layout": layout(view), "camera": camera, "input": value,
                "componentFamily": component, "historicalNumericChoice": historical_choice,
                "selection": "new-current-native-rest-framing" if failure else "retained-numbers-newly-chosen-current",
                "fallbackReason": failure, "currentNativeFraming": bounds, "mappedAnchorIds": association_ids,
                "sameExposureNumericChoice": bool(selected and selected[0]["decodedTimeSeconds"] == frame["decodedTimeSeconds"]),
                "cameraContinuityBranch": branch, "cameraInterpolation": interpolation,
                "qualification": copy.deepcopy(QUALIFICATION),
                "sourceParameterScope": "All 51 absolute input coordinates and this camera are chosen/unmeasured current parameters; original pixels/clock are independent source observations. Same-shot numeric holds transfer no FIT/CHECK/image support."})
        choices.append(row)
    return choices


def produce_packet(video_id):
    observations = common.load_observations(video_id)
    validate_source(observations["source"], video_id)
    _, semantics = native_semantics()
    originals = historical_anchors(video_id)
    associations = []
    for anchor in observations["anchors"]:
        if anchor["id"] not in originals:
            raise ValueError(f"Current anchor lacks immutable original evidence: {anchor['id']}")
        original, original_evidence = originals[anchor["id"]]
        result = common.associate_native_anchor(original)
        if anchor != result["anchor"]:
            raise ValueError(f"Current observation anchor differs from independent native association: {anchor['id']}")
        associations.append({"originalEvidence": original_evidence, "historicalAnchor": copy.deepcopy(original), **result})
    current_path = common.CURRENT_CONTENT / f"{video_id}.observations.json"
    return {"schemaVersion": 1, "kind": "current-source-association-choices", "source": copy.deepcopy(observations["source"]),
            "model": common.current_model_identity(), "currentObservations": {"path": str(current_path.relative_to(ROOT)), "sha256": digest(current_path)},
            "qualification": copy.deepcopy(QUALIFICATION), "inputSemantics": semantics, "nativeAssociations": associations,
            "sourceClocks": source_clocks(video_id, observations["source"]),
            "choices": choose_views(observations, historical(f"{video_id}.source-track.json"), associations),
            "historicalLineage": [lineage(name) for name in HISTORICAL_DIGESTS if name.startswith(video_id) or name.startswith("analysis-synthesis.")],
            "historicalLineageScope": "Original certificates/caps/digests stay historical and unchanged. Numeric choice retention is not old native REST/camera/GPU/world support; no blanket model hash replacement."}


def validate_packet(packet, observations):
    """Refuse stale/tampered choices, source lineage, fields or native associations."""
    video_id = observations["source"]["videoId"]
    validate_source(packet["source"], video_id)
    if (packet.get("schemaVersion") != 1 or packet.get("kind") != "current-source-association-choices"
            or packet["model"] != common.current_model_identity() or packet["source"] != observations["source"]
            or packet["qualification"] != QUALIFICATION or packet["inputSemantics"] != native_semantics()[1]):
        raise ValueError("Current choice packet has stale native tuple/semantics/qualification")
    path = common.CURRENT_CONTENT / f"{video_id}.observations.json"
    if packet["currentObservations"] != {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}:
        raise ValueError("Current choice packet is not associated with these exact current observations")
    originals = historical_anchors(video_id)
    current_anchors = {anchor["id"]: anchor for anchor in observations["anchors"]}
    seen = set()
    for row in packet["nativeAssociations"]:
        anchor_id = row["anchor"]["id"]
        if anchor_id in seen or anchor_id not in originals:
            raise ValueError("Duplicate/unidentified current native feature")
        seen.add(anchor_id)
        original, evidence = originals[anchor_id]
        expected = {"originalEvidence": evidence, "historicalAnchor": original, **common.associate_native_anchor(original)}
        if row != expected or row["anchor"] != current_anchors.get(anchor_id):
            raise ValueError("Current native feature proof is not the exact independent association")
    if seen != set(current_anchors):
        raise ValueError("Current native association packet erases an original required feature")
    if packet["sourceClocks"] != source_clocks(video_id, observations["source"]):
        raise ValueError("Original source clock/pixel/holdout facts or chosen/source scope changed")
    expected_lineage = [lineage(name) for name in HISTORICAL_DIGESTS if name.startswith(video_id) or name.startswith("analysis-synthesis.")]
    if packet["historicalLineage"] != expected_lineage:
        raise ValueError("Historical certificate lineage was retagged or erased")
    for name in HISTORICAL_DIGESTS:
        if name.startswith(video_id) or name.startswith("analysis-synthesis."):
            historical(name)
    expected = choose_views(observations, historical(f"{video_id}.source-track.json"), packet["nativeAssociations"])
    if packet["choices"] != expected:
        raise ValueError("Current chosen values/layout/scope differ from explicit immutable numeric recipe")
    return packet


def load_packet(video_id, observations):
    path = common.CURRENT_CONTENT / f"{video_id}.current-associations.json"
    return validate_packet(json.loads(path.read_text()), observations)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", choices=VIDEOS)
    args = parser.parse_args()
    videos = (args.video,) if args.video else VIDEOS
    packets = [produce_packet(video_id) for video_id in videos]
    outputs = []
    for packet in packets:
        video_id = packet["source"]["videoId"]
        validate_packet(packet, common.load_observations(video_id))
        outputs.append((common.CURRENT_CONTENT / f"{video_id}.current-associations.json", json.dumps(packet, separators=(",", ":"), allow_nan=False)+"\n"))
    common.CURRENT_CONTENT.mkdir(parents=True, exist_ok=True)
    for path, content in outputs:
        path.write_text(content)
        print(f"{path.relative_to(ROOT)}: current choices; native/camera/GPU/stages unmeasured")

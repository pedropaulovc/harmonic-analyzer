#!/usr/bin/env python3
"""Prepare current Operation/Rocker choices without promoting historical support.

Run after adopt-v39-source-observations.py, before compact-operation-rocker.py.
Only original source facts and authored numeric choices are read. Raw native
association and station/setup ownership establish narrow current applicability;
old CPU closure, camera fits, fixed-contact feasibility and GPU receipts remain
historical. This producer performs no fitting, rendering or acceptance run.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "compact_source_common", Path(__file__).with_name("compact-source-common.py"))
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)
WEB = common.WEB
VIDEOS = ("jfH-NbsmvD4", "4mBuyixt22U")
CAMERA_FIELDS = ("positionMetres", "quaternion", "verticalFovDegrees", "principalPointViewportPixels")
LAYOUT_FIELDS = ("id", "rectSourcePixels", "presentation", "imagePlaneWarp", "composite")
QUALIFICATION = (
    "Explicitly chosen unobserved current native input/framing candidate. "
    "Station/channel/setup ownership is checked against authentic current parts; "
    "old-model feasibility, fixed-contact closure, fitted cameras, bank support, "
    "first-surface/material identity, GPU and source50/20/10/5 remain unmeasured.")


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def read_historical(video_id, suffix):
    path = common.HISTORICAL_CONTENT / f"{video_id}.{suffix}.json"
    raw = path.read_bytes()
    return json.loads(raw), {"path": str(path.relative_to(WEB.parent)),
                             "sha256": hashlib.sha256(raw).hexdigest(),
                             "usage": "immutable-historical-source-and-choice-lineage"}


def numeric_camera(camera):
    compact = common.compact_camera(camera)
    return {key: copy.deepcopy(compact[key]) for key in CAMERA_FIELDS if key in compact} if compact else None


def numeric_input(value):
    compact = common.compact_input(value)
    if compact != value:
        raise ValueError("Authored current input must retain the exact complete 51-field numeric contract")
    return compact


def source_layout(view):
    result = {key: copy.deepcopy(view[key]) for key in LAYOUT_FIELDS if key in view}
    warp = common.resolve_warp(view)
    if warp:
        result["imagePlaneWarp"] = warp
    return result


def ownership_proof(parts):
    """No inferred station aliases: current raw paths and live binding roles only."""
    metadata_text = (WEB / "src/mechanics-data.ts").read_text()
    metadata = json.loads(metadata_text.split("export const MECHANISM_DATA = ", 1)[1].rsplit(" as const", 1)[0])
    model = common.current_model_identity()
    provenance = metadata["provenance"]
    if (provenance.get("modelSha256") != model["sha256"]
            or provenance.get("sourceCommit") != model["sourceCommit"]
            or metadata["channel"]["count"] != 20
            or metadata["harmonicNumbers"] != list(range(20, 0, -1))):
        raise ValueError("Current mechanical metadata does not prove the authored station/input semantics")
    bindings = common.native_motion_bindings()
    roles = {}
    for path in sorted(parts):
        if parts[path]["primitiveCount"] < 1:
            raise ValueError(f"Current input owner has no genuine raw primitive: {path}")
        matches = [motion for pattern, motion in bindings if pattern.fullmatch(path)]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous native input owner: {path}")
        if matches:
            roles.setdefault(matches[0], []).append(path)
    stations = []
    indexed = (("coneGear", "drive-train", "cone-gear", "cone-spin"),
               ("cylinderGear", "drive-train", "cylinder-gear", "cylinder"),
               ("rod", "channel", "connecting-rod", "rod"),
               ("rocker", "channel", "rocker-arm", "rocker"),
               ("amplitudeBar", "channel", "amplitude-bar", "bar"),
               ("channelLever", "channel", "channel-lever", "lever"),
               ("channelSpring", "channel", "channel-spring-installed-stretch00", "channel-spring"))
    for index in range(20):
        row = {"inputIndex": index, "physicalStation": index + 1, "harmonic": 20 - index}
        for key, group, name, role in indexed:
            path = f"harmonic-analyzer/{group}/{name}-{index + 1}"
            if path not in parts or path not in roles.get(role, []):
                raise ValueError(f"Current station owner is missing or has the wrong motion: {path}/{role}")
            row[key] = path
        stations.append(row)
    setup_roles = {
        "counterHeightM": ("gooseneck", "counter-spring"),
        "meanLineAngleRad": (),
        "platenOffsetM": ("platen",),
        "wireFixtureOffsetM": ("magnifier-fixture",),
        "coneSwingRad": ("cone-swing",),
        "pinionCamRad": ("pinion-cam",),
        "heldChannelTurns": ("cylinder", "rod", "rocker"),
        "driveCrankOffsetTurns": ("crank", "cylinder", "rod", "rocker"),
    }
    owners = {}
    for field, motions in setup_roles.items():
        for motion in motions:
            if not roles.get(motion):
                raise ValueError(f"Current setup owner missing: {field}/{motion}")
        owners[field] = {"nativeParts": [path for motion in motions for path in roles[motion]],
                         "semantics": "solver readout datum only; no physical spring rotation" if not motions else "existing MechanismInput field, no new service DOF"}
    for motion in ("crank", "magnifier-clamp", "paper-sprocket", "paper-feed", "paper-knob"):
        if not roles.get(motion):
            raise ValueError(f"Current scalar input owner missing: {motion}")
    if len(roles["paper-sprocket"]) != 3:
        raise ValueError("Current gearing requires the three actual native removable sprockets")
    source_files = ["src/bindings.ts", "src/mechanics.ts", "src/kinematics.ts", "src/mechanics-data.ts"]
    return {"method": "current-raw-part-live-binding-input-ownership-v1",
            "rawNativeCensus": {"meshPartPaths": len(parts),
                               "primitiveDrawables": sum(part["primitiveCount"] for part in parts.values()),
                               "scope": "Authenticated original GLB only, not a browser/runtime drawable census"},
            "stations": stations, "setup": owners,
            "scalarInputOwners": {"crankTurns": roles["crank"],
                                  "magnification": roles["magnifier-clamp"],
                                  "gearing": roles["paper-sprocket"] + roles["paper-feed"] + roles["paper-knob"]},
            "metadataInputSemantics": {
                "harmonicNumbers": copy.deepcopy(metadata["harmonicNumbers"]),
                "channel": {key: copy.deepcopy(metadata["channel"][key]) for key in
                            ("count", "maximumStationMm", "stationDomainKind", "stationZ0Mm", "stationPitchMm")},
                "driveTrain": copy.deepcopy(metadata["driveTrain"]),
                "paperDrive": {key: copy.deepcopy(metadata["paperDrive"][key]) for key in
                               ("chainRatioFine", "reducerRatio", "feedPitchDiameterMm", "netTravelSense")},
                "setup": copy.deepcopy(metadata["setup"])},
            "contractInputs": [{"path": f"web/{name}", "sha256": hashlib.sha256((WEB / name).read_bytes()).hexdigest()} for name in source_files],
            "qualification": QUALIFICATION}


def whole_machine_baseline(parts, state):
    """A declared framing choice from genuine current geometry, not a source donor."""
    minimum = [min(part["worldBoundsMetres"]["min"][axis] for part in parts.values()) for axis in range(3)]
    maximum = [max(part["worldBoundsMetres"]["max"][axis] for part in parts.values()) for axis in range(3)]
    centre = [(a + b) / 2 for a, b in zip(minimum, maximum)]
    radius = math.dist(minimum, maximum) / 2
    # Conservative full-machine framing for narrow required panels. This is a
    # chosen camera, never a camera fit or a physical source-feature coordinate.
    distance = radius / (math.sin(math.radians(20)) * 0.25)
    return {"input": numeric_input(state),
            "camera": {"positionMetres": [centre[0], centre[1], centre[2] + distance],
                       "quaternion": [0, 0, 0, 1], "verticalFovDegrees": 40},
            "nativeBoundsMetres": {"min": minimum, "max": maximum},
            "qualification": "Explicit current whole-machine framing from actual native world bounds; no neighboring exposure, different-view or cross-cut camera/input borrowing. " + QUALIFICATION}


def catalogue(original, model, source_input):
    anchors = original["anchors"]
    if len({anchor["id"] for anchor in anchors}) != len(anchors):
        raise ValueError("Original physical-source catalogue contains duplicate identities")
    split = None
    if original["source"]["videoId"] == "jfH-NbsmvD4":
        if len(anchors) != 221 or anchors[33]["id"] != "op19m.wheel.bar.left-top":
            raise ValueError("Original Operation 33+188 genuine catalogue lineage changed")
        split = {"originalAuthored": {"count": 33, "anchorIds": [a["id"] for a in anchors[:33]], "sha256": digest(anchors[:33])},
                 "genuineFragmentDefinitions": {"count": 188, "anchorIds": [a["id"] for a in anchors[33:]], "sha256": digest(anchors[33:])}}
    associations = [common.associate_native_anchor(anchor) for anchor in anchors]
    return {"schemaVersion": 1, "kind": "current-native-source-association-catalog",
            "videoId": original["source"]["videoId"], "sourceSha256": original["source"]["sha256"],
            "model": model, "historicalSourceCatalogue": {"input": source_input,
                "usage": "unchanged original physical-feature definitions; old coordinates are historical, not current authority",
                "sha256": digest(anchors), "anchors": copy.deepcopy(anchors), "lineage": split},
            "associations": associations,
            "unavailableFeatures": [{"anchorId": row["anchor"]["id"], "reason": row["reason"]} for row in associations if row["status"] == "unavailable"],
            "qualification": QUALIFICATION}


def operation_choices(old, original, parts):
    current = {key: copy.deepcopy(old[key]) for key in (
        "sourceInputIndex", "observedDegrees", "sourceControls", "historicalReportInputs", "operation019SourceRefinement")}
    current["chosenStates"] = {key: numeric_input(value) for key, value in old["chosenStates"].items()}
    baseline_id = next(key for key, value in current["chosenStates"].items() if value is not None)
    current["baselineChoice"] = whole_machine_baseline(parts, current["chosenStates"][baseline_id])
    current["baselineChoice"]["historicalNumericChoiceRecordId"] = baseline_id
    current["authoredCameraChoices"] = []
    for frame in original["frames"]:
        number = frame.get("sourceFrameIndex", frame.get("nativeFrame", (frame.get("sourceImage") or {}).get("frameIndex")))
        if type(number) is not int or type(frame.get("decodedTimeSeconds")) not in (int, float):
            continue
        for view in common.source_views(frame, original):
            camera = numeric_camera(view.get("camera") or frame.get("camera"))
            if camera:
                current["authoredCameraChoices"].append({
                    "sourceFrameIndex": number, "decodedTimeSeconds": frame["decodedTimeSeconds"],
                    "sourceImage": copy.deepcopy(frame.get("sourceImage")),
                    "layout": source_layout(view), "camera": camera, "qualification": QUALIFICATION})
    current["fragments"] = {}
    for family, fragment in old["fragments"].items():
        frames = []
        for frame in fragment["frames"]:
            row = {key: copy.deepcopy(frame[key]) for key in ("sourceFrameIndex", "timeSeconds", "sourceImage", "sourceMeasurements") if key in frame}
            if "views" in frame:
                row["views"] = [source_layout(view) for view in frame["views"]]
            row["cameraChoices"] = [{"viewId": choice.get("viewId"), "camera": numeric_camera(choice.get("camera")),
                                     "qualification": QUALIFICATION}
                                    for choice in frame.get("fits", []) + frame.get("diagnosticFits", [])]
            frames.append(row)
        current["fragments"][family] = {"historicalPath": fragment["historicalPath"], "frames": frames}
    current["captureRequests"] = []
    for entry in old["captureRequests"]:
        old_request = entry["request"]
        request = {key: copy.deepcopy(old_request[key]) for key in ("sourceImage", "decodedTimeSeconds", "viewId", "recordId") if key in old_request}
        request["camera"] = numeric_camera(old_request.get("camera"))
        if old_request.get("input") is not None:
            request["input"] = numeric_input(old_request["input"])
        current["captureRequests"].append({"path": entry["path"], "request": request, "qualification": QUALIFICATION})
    current["correctedCaptures"] = {
        key: {"view": {"camera": numeric_camera(value["view"]["camera"])},
              "chosenInput": numeric_input(value["chosenInput"]), "qualification": QUALIFICATION}
        for key, value in old["correctedCaptures"].items()}
    historical_track, track_input = read_historical("jfH-NbsmvD4", "source-track")
    current["gapExposures"] = []
    for gap in old["gapExposures"]:
        row = copy.deepcopy(gap)
        time = gap["decodedTimeSeconds"]
        shot = next(s for s in original["shots"] if s["startSeconds"] <= time < s["endSeconds"])
        if any(f.get("sourceFrameIndex") == gap["sourceFrameIndex"] and f["shotId"] == shot["id"] for f in original["frames"]):
            row["views"] = []  # No new frame is emitted for an existing original exposure.
        else:
            matches = [f for f in historical_track["frames"] if f.get("sourceImage") == gap["sourceImage"]
                       and f.get("decodedTimeSeconds") == time and f["shotId"] == shot["id"]]
            if not matches:
                raise ValueError(f"No exact original exposure layout for gap frame{gap['sourceFrameIndex']}")
            layouts = [source_layout(view) for view in matches[0]["views"]]
            if any([source_layout(view) for view in f["views"]] != layouts for f in matches):
                raise ValueError(f"Ambiguous original gap view layout: frame{gap['sourceFrameIndex']}")
            row["views"] = layouts
            losses = []
            for frame in matches:
                for loss in frame.get("unavailable", []):
                    if loss not in losses:
                        losses.append(copy.deepcopy(loss))
            if losses:
                row["unavailable"] = losses
            row["layoutAuthority"] = {**track_input, "decodedTimeSeconds": time,
                                      "sourceImage": copy.deepcopy(gap["sourceImage"]),
                                      "usage": "exact-exposure source layout/loss only; camera/input/native support excluded"}
        current["gapExposures"].append(row)
    return current


def rocker_choices(old, proof, parts):
    states = [{"nativeFrame": row["nativeFrame"], "timeSeconds": row["timeSeconds"],
               "sourceImage": copy.deepcopy(row["sourceImage"]),
               "inputInterpretation": QUALIFICATION, "completeInput": numeric_input(row["completeInput"])}
              for row in old["states"]]
    amplitudes, phases = states[0]["completeInput"]["amplitudes"], states[0]["completeInput"]["phases"]
    if any(row["completeInput"]["amplitudes"] != amplitudes or row["completeInput"]["phases"] != phases for row in states):
        raise ValueError("Original Rocker fixed-contact amplitude/phase scenario changed")
    family = "rocker-explicit-chosen-current-v39"
    camera = {"camera": numeric_camera(old["cameraChoice"]["camera"]),
              "cameraContinuityFamily": family,
              "cameraProvenance": {"kind": "source-informed-framing", "family": family,
                  "evidence": "Historical camera numbers explicitly chosen as an unobserved current framing candidate; original FIT/CHECK and native435 receipts stay historical. " + QUALIFICATION},
              "qualification": QUALIFICATION}
    return {"states": states, "cameraChoice": camera,
            "baselineChoice": whole_machine_baseline(parts, states[0]["completeInput"]),
            "historicalReportInputs": copy.deepcopy(old["historicalReportInputs"]),
            "fixedContactScenarios": [{"id": "original-independent-held-bank-fixed-contact",
                "amplitudes": copy.deepcopy(amplitudes), "phases": copy.deepcopy(phases),
                "stateCount": len(states), "stateInputsSha256": digest([s["completeInput"] for s in states]),
                "stationOwnership": proof["stations"],
                "qualification": "Original numeric fixed-contact scenario, not an inherited current contact/branch feasibility certificate. " + QUALIFICATION}]}


def prepare_current_choices(video_id, parts, proof):
    old, seed_input = read_historical(video_id, "source-seeds")
    original, source_input = read_historical(video_id, "observations")
    current_observations = common.load_observations(video_id)
    model = common.current_model_identity()
    if original["source"] != current_observations["source"] or old["sourceSha256"] != original["source"]["sha256"]:
        raise ValueError("Current adoption changed original source identity")
    associations = catalogue(original, model, source_input)
    packet = operation_choices(old, original, parts) if video_id == "jfH-NbsmvD4" else rocker_choices(old, proof, parts)
    packet.update({"schemaVersion": 1, "kind": "current-operation-rocker-chosen-associations",
                   "videoId": video_id, "sourceSha256": old["sourceSha256"], "model": model,
                   "qualification": QUALIFICATION,
                   "currentChoiceAdoption": {"historicalSeeds": seed_input, "historicalObservations": source_input,
                       "nativeAssociationCatalogue": f"web/content/v39/{video_id}.native-association-catalog.json",
                       "inputOwnership": proof, "sourceControlPolicy": "Original pixels, roles, exact exposure identities, first-wins/provenance-only conflicts and required losses unchanged; no current native support transferred",
                       "qualification": QUALIFICATION}})
    return [(common.CURRENT_CONTENT / f"{video_id}.native-association-catalog.json", associations),
            (common.CURRENT_CONTENT / f"{video_id}.source-seeds.json", packet)]


if __name__ == "__main__":
    parts = common.current_native_parts()
    proof = ownership_proof(parts)
    outputs = [item for video_id in VIDEOS for item in prepare_current_choices(video_id, parts, proof)]
    encoded = [(path, json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n") for path, value in outputs]
    common.CURRENT_CONTENT.mkdir(parents=True, exist_ok=True)
    for path, text in encoded:
        path.write_text(text)
        print(f"{path.relative_to(WEB)}: current choices/native associations only; all source/GPU stages unmeasured")

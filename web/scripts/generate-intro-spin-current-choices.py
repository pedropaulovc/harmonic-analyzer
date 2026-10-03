#!/usr/bin/env python3
"""Produce explicit current Intro/Spin choices, native associations and prerequisites.

Parent-only command, after adopt-v39-source-observations.py:
  uv run --no-project --active python web/scripts/generate-intro-spin-current-choices.py --runtime-census web/.vite/native-v39-smoke-corrected-20261003.json
Then run generate-v39-source-tracks.py, the all-six canonical transaction.
Individual family scripts require --output for unpublished diagnostics. This producer reads
sealed original GLBs/source numeric records only: no CAD execution, source decoding,
fitting, native export, browser or GPU. It never modifies historical root content.
The required actual runtime census is a basic viewer receipt, not spring/source
eligibility. Fresh runtime462/all21-stock numeric/first-surface/camera proof remains
parent work; every current 50/20/10/5 stage stays unmeasured.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import math
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("intro_spin_source_common", HERE / "compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
native = common.native_source_association

INTRO = "NAsM30MAHLg"
SPIN = "XPQwKRt4Y2k"
CAMERA_FIELDS = ("positionMetres", "quaternion", "verticalFovDegrees", "principalPointViewportPixels")
QUALIFICATION = (
    "Original source facts plus separately proven narrow native associations and chosen/unobserved current inputs/framing. "
    "Native station/setup ownership is checked, not current posed mechanism feasibility, fitted-camera transfer, "
    "source-first-surface, all21-stock numeric/GPU, geometry/raster or 50/20/10/5-percent stage acceptance."
)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(common.WEB.parent))


def lineage(path):
    return {"path": relative(path), "sha256": digest(path), "scope": "immutable historical input; not current native qualification"}


def historical(filename):
    path = common.HISTORICAL_CONTENT / filename
    return json.loads(path.read_text()), lineage(path)


def current_camera(camera):
    value = common.compact_camera(camera)
    if value is None:
        return None
    return {key: copy.deepcopy(value[key]) for key in CAMERA_FIELDS if key in value}


def source_framings(documents):
    """Choose exact own-exposure numeric branches; never borrow frames or fits."""
    rows = {}
    authority = documents[0]["source"]
    for observations in documents:
        if (observations["source"]["videoId"] != authority["videoId"]
                or observations["source"]["sha256"] != authority["sha256"]
                or {key: observations["model"][key] for key in native.HISTORICAL_SOURCE} != native.HISTORICAL_SOURCE):
            raise ValueError("Historical framing inputs must retain their own original source/model identity")
        for frame in observations["frames"]:
            image = frame.get("sourceImage")
            if not image:
                continue
            for view in common.source_views(frame, observations):
                camera = current_camera(view.get("camera"))
                if camera is None:
                    continue
                identity = [image, view["id"], view["rectSourcePixels"],
                            view.get("presentation", "native"), common.resolve_warp(view)]
                key = native.json_digest(identity)
                # First declared own-exposure numeric branch is a chosen baseline,
                # not CHECK-driven selection or recovered source camera history.
                rows.setdefault(key, {"key": key, "sourceImage": copy.deepcopy(image), "viewId": view["id"],
                                      "rectSourcePixels": copy.deepcopy(view["rectSourcePixels"]),
                                      "presentation": view.get("presentation", "native"),
                                      "imagePlaneWarp": common.resolve_warp(view), "camera": camera,
                                      "status": "chosen-unmeasured",
                                      "qualification": "Same original source exposure/layout numeric framing selected as current unmeasured choice; old calibration/fit/status/GPU evidence not transferred."})
    return list(rows.values())


def input_semantics(model, raw):
    """Check existing current metadata/datums and real binding owners, not a solve."""
    path = common.WEB / "src/mechanics-data.ts"
    text = path.read_text()
    mech = json.loads(text.split("export const MECHANISM_DATA = ", 1)[1].rsplit(" as const", 1)[0])
    if (mech["provenance"]["modelSha256"] != model["sha256"]
            or mech["provenance"]["sourceCommit"] != model["sourceCommit"]
            or mech["harmonicNumbers"] != list(range(20, 0, -1))
            or mech["channel"]["count"] != 20):
        raise ValueError("Current chosen inputs need actual v39 station20..1 metadata")
    bindings = common.native_motion_bindings()

    def owner(part_path, motion):
        matches = [value for pattern, value in bindings if pattern.fullmatch(part_path)]
        if part_path not in raw.parts or "mesh" not in raw.parts[part_path]["node"] or matches != [motion]:
            raise ValueError(f"Current input owner {part_path} must be one actual native body bound to {motion}")
        return {"partPath": part_path, "motion": motion, "worldMatrix": raw.parts[part_path]["worldMatrix"]}

    stations = []
    for index, harmonic in enumerate(mech["harmonicNumbers"]):
        instance = index + 1
        roles = [("drive-train", "cone-gear", "cone-spin"), ("drive-train", "cylinder-gear", "cylinder"),
                 ("channel", "connecting-rod", "rod"), ("channel", "rocker-arm", "rocker"),
                 ("channel", "amplitude-bar", "bar"), ("channel", "channel-lever", "lever"),
                 ("channel", "channel-spring-installed-stretch00", "channel-spring")]
        stations.append({"inputIndex": index, "nativeInstance": instance, "harmonicNumber": harmonic,
                         "configuredStationZMm": mech["channel"]["stationZ0Mm"] + index * mech["channel"]["stationPitchMm"],
                         "roles": [owner(f"harmonic-analyzer/{group}/{name}-{instance}", motion)
                                   for group, name, motion in roles]})
    setup_owners = {
        "crankTurns": [("drive-train/crankshaft-1", "crank")],
        "gearing": [("paper-drive/transgear-knob-shaft-1", "paper-knob"), ("paper-drive/transgear-removable-1", "paper-sprocket"),
                    ("paper-drive/rack-pinion-1", "paper-feed")],
        "magnification": [("magnifier/magnifying-clamp-1", "magnifier-clamp")],
        "setup.counterHeightM": [("summing/gooseneck-1", "gooseneck"), ("summing/counter-spring-1", "counter-spring")],
        "setup.meanLineAngleRad": [],
        "setup.platenOffsetM": [("paper-drive/platen-1", "platen")],
        "setup.wireFixtureOffsetM": [("magnifier/output-fixture-1", "magnifier-fixture")],
        "setup.coneSwingRad": [("drive-train/cone-swing-platform-1", "cone-swing")],
        "setup.pinionCamRad": [("drive-train/pinion-cam-1", "pinion-cam")],
        "setup.heldChannelTurns": [("drive-train/cylinder-gear-1", "cylinder")],
        "setup.driveCrankOffsetTurns": [("drive-train/cylinder-gear-1", "cylinder")],
    }
    setup = {field: [owner("harmonic-analyzer/" + part, motion) for part, motion in rows]
             for field, rows in setup_owners.items()}
    # These are the importer's original native rest-datum bounds, not source CHECK
    # pixels or a new/relaxed calibration tolerance. Preserve each recorded bound.
    datum_rows = []
    for row in mech["provenance"]["restChecks"]:
        part = raw.parts.get(row["path"])
        if part is None:
            raise ValueError("Current station/setup datum references a missing native body")
        actual = [value * 1000 for value in native.transform(part["worldMatrix"], [value / 1000 for value in row["localPointMm"]])]
        error = math.dist(actual, row["expectedMm"])
        if error > row["toleranceMm"]:
            raise ValueError("Current input semantics disagree with an unchanged importer rest-datum bound")
        datum_rows.append({"path": row["path"], "localPointMm": row["localPointMm"], "actualMm": actual,
                           "expectedMm": row["expectedMm"], "errorMm": error, "toleranceMm": row["toleranceMm"]})
    proof = {"status": "native-ownership-and-station-semantics-checked", "stations": stations, "setupOwners": setup,
             "fieldCount": len(common.INPUT_FIELDS), "inputFields": list(common.INPUT_FIELDS),
             "semantics": "Physical station order20..1; amplitude [-1,+1] is configured nominal +/-88mm, not engraved scale. Phases are radians. meanLineAngleRad is readout only. Held/offset turns preserve explicit engaged/disengaged coupling; no hanger-release DOF is invented.",
             "codeHashes": {relative(common.WEB / name): digest(common.WEB / name) for name in
                            ("src/mechanics-data.ts", "src/mechanics.ts", "src/kinematics.ts", "src/bindings.ts")},
             "nativeRestDatums": datum_rows, "qualification": "Static imported native ownership/semantics only; actual complete-input pose, contact, collision, world arrays and GPU closure unmeasured."}
    return mech, proof


def chosen_input(value, mech):
    result = common.compact_input(value)
    if result is None:
        raise ValueError("Chosen current input must be a complete 51-field state, not unavailable")
    ratio = result["magnification"]
    band = mech["magnifier"]["clampRadiusBandMm"]
    arm = mech["summing"]["anchorArmMm"]
    lo, hi = mech["magnifier"]["fixtureOffsetRangeM"]
    setup = result["setup"]
    if (not band[0] / arm <= ratio <= band[2] / arm
            or not lo <= setup["wireFixtureOffsetM"] <= hi
            or not 0 <= setup["coneSwingRad"] <= mech["setup"]["coneDisengageRad"]
            or not mech["setup"]["pinionEngageCamRad"] <= setup["pinionCamRad"] <= 0):
        raise ValueError("Chosen current input is outside existing native setup/fixture travel")
    return result


def observed_layers(path, model, raw):
    """Bind the actual viewer receipt; never infer runtime from raw mesh count."""
    receipt = json.loads(path.read_text())
    descriptor = json.loads((common.HISTORICAL_CONTENT / "model-representation.json").read_text())
    provenance = receipt["provenance"]
    raw_count = sum(len(raw.document["meshes"][part["node"]["mesh"]]["primitives"])
                    for part in raw.parts.values() if "mesh" in part["node"])
    if (receipt.get("kind") != "actual-v39-native-viewer-binding-motion-smoke"
            or receipt.get("passed") is not True or receipt.get("availability") != "available"
            or receipt.get("loadError") is not None or receipt.get("missing") != [] or receipt.get("pageErrors") != []
            or provenance.get("sourceSha256") != model["sha256"] or provenance.get("sourceCommit") != model["sourceCommit"]
            or provenance.get("observedSha256") != descriptor["representation"]["sha256"]
            or provenance.get("expectedSha256") != descriptor["representation"]["sha256"]
            or provenance.get("observedByteLength") != descriptor["representation"]["byteLength"]
            or provenance.get("expectedByteLength") != descriptor["representation"]["byteLength"]
            or raw_count != descriptor["equivalence"]["drawableCount"] or raw_count != 460
            or receipt.get("nativeDrawableCount") != 462 or receipt.get("partCount") != 479
            or receipt.get("baseline", {}).get("rows") != 462 or receipt.get("changed", {}).get("rows") != 462
            or receipt.get("sourceAcceptance") is not False or receipt.get("normalApplicationRoute") is not False):
        raise ValueError("Runtime census must be the actual current raw460/runtime462 viewer receipt, not an old export")
    return {"rawNativePrimitiveInstances": raw_count, "rawNamedPaths": len(raw.parts),
            "requiredRuntimeDrawableCount": receipt["nativeDrawableCount"], "observedRuntimeNamedPaths": receipt["partCount"],
            "runtimeObservation": {**lineage(path), "scope": receipt["scope"], "gpu": receipt["gpu"],
                                   "sourceAcceptance": False, "normalApplicationRoute": False},
            "qualification": "Raw primitive count and actual viewer/helper-instance census are separate layers. Basic viewer smoke is not complete numeric world/spring/source eligibility."}


def associate_controls(packet):
    result = copy.deepcopy(packet)
    associations = [common.associate_native_anchor(anchor) for anchor in packet["anchors"]]
    result["anchors"] = [copy.deepcopy(row["anchor"]) for row in associations]
    losses = [row for row in associations if row["status"] == "unavailable"]
    result["nativeAssociationLosses"] = [{"anchorId": row["anchor"]["id"], "reason": row["reason"], "proof": row["proof"]} for row in losses]
    for frame in result["frames"]:
        for row in losses:
            anchor_id = row["anchor"]["id"]
            frame.setdefault("unavailable", []).append({"anchorId": anchor_id, "viewId": anchor_id.split(":", 1)[0],
                                                       "status": "unmeasured-native", "required": True, "reason": row["reason"]})
    result["sourceOnlySummary"] = copy.deepcopy(packet["summary"])
    result["summary"] = {**copy.deepcopy(packet["summary"]),
                         "unavailableObservations": sum(len(frame.get("unavailable", [])) for frame in result["frames"]),
                         "nativeAssociationUnavailableObservations": len(losses) * len(result["frames"])}
    result["qualification"] = packet["qualification"] + " " + QUALIFICATION
    return result


def nib_identity(raw, old_profile):
    """Inspect exact current stored support, not posed first-surface eligibility."""
    nib = old_profile["finiteNib"]
    part = raw.parts[nib["partPath"]]
    primitive = raw.document["meshes"][part["node"]["mesh"]]["primitives"][nib["primitiveIndex"]]
    position_signature, positions = raw.accessor(primitive["attributes"]["POSITION"])
    index_signature, indices = raw.accessor(primitive["indices"])
    if (position_signature["componentType"], position_signature["type"], position_signature["normalized"]) != (5126, "VEC3", False):
        raise ValueError("Current finite feature requires original float32 POSITION")
    points = list(struct.iter_unpack("<fff", positions))
    vertex = nib["nativeVertexIndex"]
    point = points[vertex]
    if list(point) != nib["storedPartLocalMetres"]:
        raise ValueError("Current native apex changed; no vertex/coordinate proxy may be inferred")
    code = native.COMPONENTS[index_signature["componentType"]][0]
    triangle_indices = [row[0] for row in struct.iter_unpack("<" + code, indices)]
    equivalent = [index for index, value in enumerate(points) if value == point]
    equivalent_set = set(equivalent)
    incident = [index // 3 for index in range(0, len(triangle_indices), 3)
                if equivalent_set.intersection(triangle_indices[index:index + 3])]
    return {"partPath": nib["partPath"], "primitiveIndex": nib["primitiveIndex"], "nativeVertexIndex": vertex,
            "storedPartLocalMetres": list(point), "eligibilityEpsilonMetres": nib["eligibilityEpsilonMetres"],
            "equivalence": nib["equivalence"], "currentPrimitive": raw.primitives(nib["partPath"])[nib["primitiveIndex"]],
            "exactStoredEquivalentVertexIndices": equivalent, "currentIncidentTriangleIndices": incident,
            "sourceAssociationStatus": "unavailable", "sourceAssociationReason": nib["sourceAssociationReason"],
            "qualification": "Exact current stored native apex/incident facets only. Seam indices are one support point; no posed nearest-hit, independent source feature/contact or GPU eligibility is measured."}


def intro_packets(model, mech, semantics, layers, raw):
    source = common.load_observations(INTRO)
    historical_obs, obs_lineage = historical(INTRO + ".observations.json")
    old_seed, seed_lineage = historical(INTRO + ".static-camera-seeds.json")
    old_profile, profile_lineage = historical(INTRO + ".calibration-eligibility.json")
    old_request, request_lineage = historical(INTRO + ".native-eligibility-request.json")
    old_camera_track, camera_lineage = historical(INTRO + ".source-track.json")
    if source["model"] != model or any(packet["sourceSha256"] != source["source"]["sha256"] for packet in (old_seed, old_profile)):
        raise ValueError("Intro original/current source identity differs")
    producer = HERE / "generate-intro-source-track.py"
    tree = ast.parse(producer.read_text())
    declaration = next(node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "CANDIDATES" for target in node.targets))
    originals = json.loads(ast.literal_eval(declaration.value.args[0]))
    candidates = {}
    for key, candidate in originals.items():
        candidates[key] = {**{field: copy.deepcopy(candidate[field]) for field in ("rect", "presentation", "evidencePath", "sha256")},
                           "camera": current_camera(candidate["camera"]), "input": chosen_input(candidate["input"], mech),
                           "unobservedInputFields": list(common.INPUT_FIELDS), "status": "chosen-unmeasured"}
    choices = {"schemaVersion": 1, "kind": "current-source-chosen-associations", "videoId": INTRO,
               "sourceSha256": source["source"]["sha256"], "model": model, "historicalModel": historical_obs["model"],
               "candidates": candidates, "inputSemantics": semantics, "nativeLayers": layers,
               "sourceFramings": source_framings([historical_obs, old_camera_track]),
               "historicalLineage": [obs_lineage, camera_lineage, seed_lineage, profile_lineage, request_lineage],
               "historicalCandidateNumbersSha256": native.json_digest(originals), "qualification": QUALIFICATION}
    original_frame = next(frame for frame in historical_obs["frames"] if frame.get("sourceImage") == old_seed["sourceFrame"]["sourceImage"])
    if original_frame["landmarks"] != old_seed["sourceFrame"]["landmarks"]:
        raise ValueError("Intro static seed must retain exact source controls")
    anchors = {anchor["id"]: anchor for anchor in historical_obs["anchors"]}
    support = []
    for row in old_seed["nativeSupport"]:
        anchor = anchors[row["anchorId"]]
        if (anchor["partPath"], anchor["kind"]) != (row["partPath"], row["kind"]):
            raise ValueError("Intro static native feature identity differs from its original source")
        association = common.associate_native_anchor(anchor)
        support.append({"anchorId": row["anchorId"], "status": association["status"],
                        "anchor": association["anchor"], "proof": association["proof"], "reason": association["reason"]})
    pending = {"eligible": None, "status": "unmeasured", "declaredFitPoints": sum(row["role"] == "fit" for row in old_seed["sourceFrame"]["landmarks"]),
               "declaredCheckPoints": sum(row["role"] == "check" for row in old_seed["sourceFrame"]["landmarks"]),
               "mappedNativeSupportCount": sum(row["status"] == "mapped" for row in support),
               "unavailableNativeSupport": [{"anchorId": row["anchorId"], "reason": row["reason"]} for row in support if row["status"] == "unavailable"],
               "reason": "Fresh complete current input/world arrays, native distinct support, positive depth/first surface and source camera eligibility remain required. Old RAW-rest eligibility is not transferred.",
               "qualification": QUALIFICATION}
    static = {"schemaVersion": 1, "videoId": INTRO, "sourceSha256": source["source"]["sha256"], "modelSha256": model["sha256"],
              "sourceFrame": copy.deepcopy(old_seed["sourceFrame"]), "nativeSupport": support, "calibrationEligibility": pending,
              "nativeGeometryScope": "Exact same-path unchanged local-feature association in current authored rest frames only; no chosen-input pose or current source eligibility.",
              "historicalLineage": [seed_lineage], "historicalInput": None, "currentCompleteNativeInput": None,
              "cameraApplication": "none; old RAW-rest static CPU camera is historical diagnostics only, never current fitted/framing authority",
              "sourceAcceptance": False, "GPUAcceptance": False, "qualification": QUALIFICATION}
    nib = nib_identity(raw, old_profile)
    stock_paths = [f"harmonic-analyzer/channel/channel-spring-installed-stretch00-{index}" for index in range(1, 21)] + ["harmonic-analyzer/summing/counter-spring-1"]
    if any(path not in raw.parts for path in stock_paths):
        raise ValueError("Current stock requirements must name all20 channel and actual counter bodies")
    old_raw = native.native_association().old
    stocks = []
    for path in stock_paths:
        current_primitives = raw.primitives(path)
        historical_primitives = old_raw.primitives(path) if path in old_raw.parts else None
        if len(current_primitives) != 1:
            raise ValueError("Each current swept-stock role must resolve to its own one native primitive")
        stocks.append({"partPath": path, "currentPrimitives": current_primitives,
                       "historicalPrimitiveComparison": {"historicalSource": native.HISTORICAL_SOURCE,
                                                         "historicalPrimitives": historical_primitives,
                                                         "exactPrimitiveEquality": historical_primitives == current_primitives},
                       "worldProof": "unmeasured", "gpuProof": "unmeasured",
                       "qualification": "Original typed raw storage inspection only; equality never substitutes fresh current posed/all-vertex shader proof."})
    disc_path = "harmonic-analyzer/paper-drive/transgear-pivot-spring-1"
    if disc_path not in raw.parts:
        raise ValueError("Current rigid disc-spring role must exist as actual native geometry")
    profile = {"schemaVersion": 1, "videoId": INTRO, "sourceSha256": source["source"]["sha256"], "modelSha256": model["sha256"],
               "sourceCommit": model["sourceCommit"], "calibrationSupport": copy.deepcopy(old_profile["calibrationSupport"]),
               "finiteNib": {**nib, "requiredNativeDrawableCount": layers["requiredRuntimeDrawableCount"],
                             "requiredRawPrimitiveCount": layers["rawNativePrimitiveInstances"], "requiredSpringDrawableCount": len(stocks)},
               "sourceExposure": copy.deepcopy(old_profile["sourceExposure"]), "nativeLayers": layers,
               "requiredCurrentSweptStock": stocks,
               "rigidDiscSpring": {"partPath": disc_path, "currentPrimitives": raw.primitives(disc_path),
                                   "role": "authored rigid disc; not a22nd swept stock"},
               "coincidentApexBlocker": {"status": "pending-current-qualification", "distinctPhysicalApexSupportPoints": 1,
                                         "seamEquivalentVertexCount": len(nib["exactStoredEquivalentVertexIndices"]),
                                         "reason": "Coincident declarations/seam copies cannot provide six distinct FIT features or disjoint CHECK support. v39 does not resolve that defect by provenance change; fresh actual distinct-feature mapping/positive control remains required, not declared source impossibility."},
               "eligibility": {"status": "unmeasured", "source": False, "gpu": False},
               "historicalLineage": [profile_lineage, request_lineage], "qualification": QUALIFICATION}
    request = {"schemaVersion": 1, "videoId": INTRO, "purpose": "Fresh current complete native support/first-surface eligibility; no source/GPU/stage acceptance before actual parent proof.",
               "producer": "web/scripts/NAsM30MAHLg-native-feature-eligibility.py",
               "producerStatus": "Current export/runtime modernization and actual parent execution required; historical root default/full435 contract is not current eligibility.",
               "profile": "web/content/v39/" + INTRO + ".calibration-eligibility.json",
               "nativeIdentity": {"originalRawSourceSha256": model["sha256"], "sourceCommit": model["sourceCommit"],
                                  "actualOptimizedTransportSha256": json.loads((common.HISTORICAL_CONTENT / "model-representation.json").read_text())["representation"]["sha256"],
                                  "requiredRawPrimitiveCount": layers["rawNativePrimitiveInstances"], "requiredDrawableCount": layers["requiredRuntimeDrawableCount"],
                                  "requiredSpringDrawableCount": len(stocks), "observedRuntimeLayers": layers},
               "historicalLineage": [request_lineage],
               "historicalAuthorities": {"originalStaticAuthority": copy.deepcopy(old_request["originalStaticAuthority"]), "macroAuthority": copy.deepcopy(old_request["macroAuthority"]),
                                         "qualification": "Immutable old-model authority only; no original 433/435 export or CPU receipt is retagged."},
               "chosenCurrentInputs": {key: {"packet": "web/content/v39/" + INTRO + ".source-choices.json", "pointer": "/candidates/" + key + "/input", "status": "chosen-unobserved", "fieldCount": len(common.INPUT_FIELDS)} for key in ("static", "macro")},
               "requiredCompleteNativeExport": {"status": "unavailable-until-actual-current-parent-export", "requiredRuntimeDrawableCount": 462, "requiredRawPrimitiveInstances": 460,
                                                "allCurrentSweptStock": stock_paths, "partOverrides": [],
                                                "geometry": "One complete 51-field chosen input, current mechanism solve and all462 runtime arrays with explicit raw460/helper-instance correspondence; hash-sealed actual f64 posed positions/u32 indices, byte offsets/counts/world matrices/native graph visibility.",
                                                "springProof": "Fresh all-vertex current shader/numeric proof for all20 channel stocks plus counter. Counter POSITION/NORMAL differ from old raw and require fresh classification/GPU proof; old receipts cannot qualify them.",
                                                "codeClosure": "Current actually executed immutable source snapshots and consistent codeHashes before/after export; no rewritten historical closure.",
                                                "freezeContract": "Input, mechanism, stock uniforms and every runtime drawable array must be one actual current state, not a historical all435 field relabel."},
               "rayControlContract": {"geometryAuthority": "Fresh sealed complete current runtime462 export only; camera rays never change native bodies or chosen input.",
                                      "allowedRayFields": copy.deepcopy(old_request["rayControlContract"]["allowedRayFields"]),
                                      "detachedPoseRefusal": "Any additional ray field, including matrices or partOverrides even null/empty, is refused before loading native geometry. Input changes require a fresh complete current solve and sealed runtime462 export; no transform alias/allowlist.",
                                      "cameraShapeRefusal": copy.deepcopy(old_request["rayControlContract"]["cameraShapeRefusal"]),
                                      "qualification": "Mathematical ray controls remain separate from source-feature/contact/GPU/stage acceptance."},
               "requiredNativeControls": ["Positive actual nearest current native apex ray in the complete runtime462 graph using the exact current same-primitive incident facets. Seam-equivalent indices identify one physical feature, not independent support.",
                                          "Adjacent marker body and foreground C-frame/other-body negatives remain in the complete nearest-positive-surface search and stay rejected.",
                                          "Six genuinely distinct FIT native/source features with disjoint independent CHECK support and reachable positive-depth camera; FIT alone selects camera branches.",
                                          "No changed/removed anchor becomes a guessed replacement, native alias, @crank proxy or waived source obligation."],
               "independentSourceChecks": {**copy.deepcopy(old_request["independentSourceChecks"]), "sourceFeatureAssociation": None, "currentGpuResiduals": None,
                                           "unavailableUntilMeasured": "Fresh current finite-feature mapping, source first-hit/contact/collision, all462 posed geometry/visibility and all21-stock proof, original independent source pixels, raster bounds and continuous cut-safe camera/mechanism history."},
               "acceptanceObligations": copy.deepcopy(old_request["acceptanceObligations"]), "coincidentApexBlocker": profile["coincidentApexBlocker"], "qualification": QUALIFICATION}
    return {INTRO + ".source-choices.json": choices, INTRO + ".static-camera-seeds.json": static,
            INTRO + ".calibration-eligibility.json": profile, INTRO + ".native-eligibility-request.json": request}


def spin_packets(model, mech, semantics, layers):
    source = common.load_observations(SPIN)
    old, seed_lineage = historical(SPIN + ".source-seeds.json")
    panel, panel_lineage = historical(SPIN + ".panel-source-controls.json")
    tracking, tracking_lineage = historical(SPIN + ".panel-tracking.json")
    phase_map, phase_lineage = historical(SPIN + ".source-phase-map.json")
    old_observations, observations_lineage = historical(SPIN + ".observations.json")
    old_source_track, source_track_lineage = historical(SPIN + ".track.json")
    old_camera_track, camera_lineage = historical(SPIN + ".source-track.json")
    if (source["model"] != model or panel["sourceSha256"] != source["source"]["sha256"]
            or tracking["sourceSha256"] != source["source"]["sha256"]
            or old["staticSourceFamily"]["sourceSha256"] != source["source"]["sha256"]
            or panel["profileSha256"] != tracking_lineage["sha256"]
            or panel["producerSha256"] != digest(HERE / "generate-spin-source-controls.py")
            or old["staticSourceFamily"]["independentSourcePhaseMap"]["sha256"] != phase_lineage["sha256"]):
        raise ValueError("Spin source-only evidence differs from exact original media/producer/profile")
    result = {"schemaVersion": 1, "videoId": SPIN, "sourceSha256": source["source"]["sha256"], "model": model,
              "sourcePacket": old["sourcePacket"], "inputSemantics": semantics, "nativeLayers": layers,
              "historicalModel": copy.deepcopy(old_observations["model"]),
              "historicalLineage": [observations_lineage, source_track_lineage, camera_lineage, seed_lineage, panel_lineage, tracking_lineage, phase_lineage], "qualification": QUALIFICATION,
              "candidates": {}, "views": {}, "historicalCpuDiagnostics": {},
              "sourceFramings": source_framings([old_observations, old_source_track, old_camera_track]),
              "sourceMeasurementLimits": copy.deepcopy(old["sourceMeasurementLimits"]),
              "sourceLayoutSeed": copy.deepcopy(tracking["sourceSeed"]),
              "physicalSourceCrossfades": copy.deepcopy(old["physicalSourceCrossfades"]),
              "staticMotion": copy.deepcopy(old["staticMotion"]), "staticSourceFamily": copy.deepcopy(old["staticSourceFamily"]),
              "montageSourceControls": associate_controls(old["montageSourceControls"])}
    for key, candidate in old["candidates"].items():
        value = {"packet": candidate["packet"], "sha256": candidate["sha256"],
                 "input": chosen_input(candidate["input"], mech), "unobservedInputFields": list(common.INPUT_FIELDS), "status": "chosen-unmeasured"}
        if candidate.get("camera"):
            value["camera"] = current_camera(candidate["camera"])
        result["candidates"][key] = value
    for key, seed in old["views"].items():
        value = {field: copy.deepcopy(seed[field]) for field in ("candidateId", "rectSourcePixels", "presentation", "presentationEvidence", "sourceViewportPixels") if field in seed}
        value["camera"] = current_camera(seed.get("camera"))
        value["cameraEvidence"] = {}
        result["views"][key] = value
        if seed.get("cameraEvidence"):
            result["historicalCpuDiagnostics"][key] = {"diagnostic": copy.deepcopy(seed["cameraEvidence"]),
                                                       "historicalModel": copy.deepcopy(old_observations["model"]),
                                                       "scope": "immutable old-model conditional CPU diagnostic only; no current native/camera/stage eligibility"}
    result["staticMotion"]["productionIntegrated"] = False
    result["staticMotion"]["integrationHold"] = "Current source stages and actual native/source/GPU eligibility unmeasured. Source internal-static classification is not a waiver."
    result["staticSourceFamily"]["independentSourcePhaseMap"] = {
        **copy.deepcopy(old["staticSourceFamily"]["independentSourcePhaseMap"]),
        "path": "web/content/v39/" + SPIN + ".source-phase-map.json"}
    current_panel = associate_controls(panel)
    current_panel.update({"model": model, "historicalLineage": [panel_lineage, tracking_lineage], "qualification": panel["qualification"] + " " + QUALIFICATION})
    # The independently panel-supported candidate intentionally has fewer
    # accepted tracks than the original montage packet. Preserve both original
    # pixel/failure sets separately; only exposures and the manual seed coincide.
    old_controls = old["montageSourceControls"]
    panel_frames = {frame["sourceImage"]["frameIndex"]: frame for frame in panel["frames"]}
    original_frames = {frame["sourceImage"]["frameIndex"]: frame for frame in old_controls["frames"]}
    seed_index = tracking["sourceSeed"]["frameIndex"]
    if (set(panel_frames) != set(original_frames)
            or any(frame["sourceImage"] != original_frames[index]["sourceImage"] for index, frame in panel_frames.items())
            or panel_frames[seed_index]["landmarks"] != original_frames[seed_index]["landmarks"]
            or {anchor["id"] for anchor in panel["anchors"]} != {anchor["id"] for anchor in old_controls["anchors"]}):
        raise ValueError("Spin independent panels must retain original exposures/manual pixels/native obligations")
    return {SPIN + ".source-seeds.json": result, SPIN + ".panel-source-controls.json": current_panel,
            SPIN + ".panel-tracking.json": tracking}, phase_map


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-census", required=True, type=Path, help="Actual parent current native-viewer smoke JSON; never an old full435 export")
    args = parser.parse_args()
    model = common.current_model_identity()
    raw = native.native_association().new
    mech, semantics = input_semantics(model, raw)
    layers = observed_layers(args.runtime_census, model, raw)
    packets = intro_packets(model, mech, semantics, layers, raw)
    spin, phase_map = spin_packets(model, mech, semantics, layers)
    packets.update(spin)
    # Prepare the entire family packet set before publication. Source-only phase
    # map bytes remain byte-identical so the original declaration hash stays true.
    serialized = {name: json.dumps(packet, indent=2, allow_nan=False) + "\n" for name, packet in packets.items()}
    phase_bytes = (common.HISTORICAL_CONTENT / (SPIN + ".source-phase-map.json")).read_bytes()
    if json.loads(phase_bytes) != phase_map:
        raise ValueError("Source-only phase map changed while preparing current packets")
    common.CURRENT_CONTENT.mkdir(parents=True, exist_ok=True)
    for name, contents in serialized.items():
        (common.CURRENT_CONTENT / name).write_text(contents)
    (common.CURRENT_CONTENT / (SPIN + ".source-phase-map.json")).write_bytes(phase_bytes)
    print(json.dumps({"paths": ["web/content/v39/" + name for name in [*serialized, SPIN + ".source-phase-map.json"]],
                      "nativeLayers": layers, "sourceAcceptance": False, "GPUAcceptance": False,
                      "stages": {str(stage): "unmeasured" for stage in (50, 20, 10, 5)}}))


if __name__ == "__main__":
    main()

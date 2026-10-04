#!/usr/bin/env python3
"""Generate Spin's unmeasured v39 track from explicit current associations.

Parent regeneration order:
  uv run --no-project --active python web/scripts/generate-intro-spin-current-choices.py --runtime-census web/.vite/native-v39-smoke-corrected-20261003.json
  uv run --no-project --active python web/scripts/generate-v39-source-tracks.py
Standalone --output is required for an unpublished candidate; canonical publication
is the all-six transaction only. No original video/frame is redistributed,
no hidden history is recovered, and old CPU camera/native diagnostics are never
current v39 eligibility or GPU evidence. Source-only phase/panel records retain
their exact original exposure/pixel/layout/role authority.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("compact_source_common", HERE / "compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)




def validate_seed_presentations(seeds):
    """Refuse undocumented or invalid rendering overrides before generation."""
    for view_id, seed in seeds["views"].items():
        if "presentation" not in seed:
            if "presentationEvidence" in seed:
                raise ValueError(f"Spin seed view {view_id!r}: presentationEvidence requires a presentation override.")
            continue
        presentation = seed["presentation"]
        if presentation not in ("native", "horizontal-mirror"):
            raise ValueError(
                f"Spin seed view {view_id!r}: invalid presentation {presentation!r}; "
                "expected 'native' or 'horizontal-mirror'."
            )
        evidence = seed.get("presentationEvidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(
                f"Spin seed view {view_id!r}: presentation {presentation!r} "
                "requires nonempty string presentationEvidence."
            )


def panel_source_candidate(seeds, data):
    """Validate the current association packet without transferring old geometry."""
    path = common.CURRENT_CONTENT / "XPQwKRt4Y2k.panel-source-controls.json"
    raw = path.read_bytes()
    packet = json.loads(raw)
    if (packet["videoId"] != data["source"]["videoId"]
            or packet["sourceSha256"] != data["source"]["sha256"]
            or packet["model"] != data["model"]):
        raise ValueError("Spin panel associations differ from current source/native authority")
    original = seeds["montageSourceControls"]
    panel_frames = {frame["sourceImage"]["frameIndex"]: frame for frame in packet["frames"]}
    original_frames = {frame["sourceImage"]["frameIndex"]: frame for frame in original["frames"]}
    seed_index = seeds["sourceLayoutSeed"]["frameIndex"]
    if (set(panel_frames) != set(original_frames)
            or any(frame["sourceImage"] != original_frames[index]["sourceImage"] for index, frame in panel_frames.items())
            or panel_frames[seed_index]["landmarks"] != original_frames[seed_index]["landmarks"]
            or {row["id"] for row in packet["anchors"]} != {row["id"] for row in original["anchors"]}):
        raise ValueError("Spin independent panels must retain exact exposures/manual pixels/native obligations")
    return {"evidencePath": "web/content/v39/" + path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "historicalLineage": copy.deepcopy(packet["historicalLineage"]),
            "sourceSeed": copy.deepcopy(packet["sourceSeed"]), "summary": copy.deepcopy(packet["summary"]),
            "unsupportedViews": copy.deepcopy(packet["unsupportedViews"]),
            "trackingFailures": copy.deepcopy(packet["trackingFailures"]),
            "qualification": packet["qualification"], "sourceAcceptance": False, "GPUAcceptance": False,
            "cameraOrInputApplication": "none; exact original source-only tracking remains separate from unmeasured current native/frame eligibility"}


def build_track():
    """Prepare a complete current family track without publishing any files."""
    seed_path = common.CURRENT_CONTENT / "XPQwKRt4Y2k.source-seeds.json"
    seeds = json.loads(seed_path.read_text())
    validate_seed_presentations(seeds)
    data = common.load_observations("XPQwKRt4Y2k")
    if (seeds["videoId"] != data["source"]["videoId"]
            or seeds["sourceSha256"] != data["source"]["sha256"]
            or seeds["model"] != data["model"]):
        raise ValueError("Spin current choices differ from current source/native authority")
    framings = {row["key"]: row["camera"] for row in seeds["sourceFramings"]}
    panel_candidate = panel_source_candidate(seeds, data)
    controls = seeds["montageSourceControls"]
    anchors = {anchor["id"]: anchor for anchor in data["anchors"]}
    for anchor in controls["anchors"]:
        existing = anchors.get(anchor["id"])
        if existing is None:
            data["anchors"].append(copy.deepcopy(anchor))
            anchors[anchor["id"]] = anchor
        elif any(existing.get(field) != anchor.get(field)
                 for field in ("kind", "partPath", "partLocalMetres", "worldMetres")):
            raise ValueError("Spin original source anchor has conflicting current native associations")
    source_controls = {(entry["sourceImage"]["frameIndex"], entry["sourceImage"]["sha256Bgr8"]): entry for entry in controls["frames"]}
    existing_images = set()
    for frame in data["frames"]:
        identity = frame.get("sourceImage", {})
        key = (identity.get("frameIndex"), identity.get("sha256Bgr8"))
        entry = source_controls.get(key)
        if entry:
            if entry["sourceImage"] != identity:
                raise ValueError("Spin control exposure identity differs from actual original source")
            points = {(point.get("viewId", "main"), point["anchorId"]): point for point in frame["landmarks"]}
            for point in entry["landmarks"]:
                old = points.get((point.get("viewId", "main"), point["anchorId"]))
                if old is None:
                    frame["landmarks"].append(copy.deepcopy(point))
                elif any(old.get(field) != point.get(field) for field in ("role", "pixel", "status", "uncertaintyPx")):
                    raise ValueError("Spin same-exposure source controls disagree on original role/pixel/uncertainty")
            unavailable = frame.setdefault("unavailable", [])
            for loss in entry["unavailable"]:
                if loss not in unavailable:
                    unavailable.append(copy.deepcopy(loss))
            existing_images.add(key)
    for entry in controls["frames"]:
        key = (entry["sourceImage"]["frameIndex"], entry["sourceImage"]["sha256Bgr8"])
        if key in existing_images:
            continue
        # The independently measured manual panel seed is an actual exposure,
        # not a nearest-frame donor. Its own measured catalogue supplies layout
        # only; no camera/physical state is borrowed from another source frame.
        if entry["sourceImage"]["frameIndex"] != controls["sourceSeed"]["frameIndex"]:
            raise ValueError("An extra Spin control exposure lacks its own original source layout")
        pts = entry["decodedTimeSeconds"]
        shot = next(shot for shot in data["shots"] if shot["id"] == seeds["sourceLayoutSeed"]["shotId"])
        if not shot["startSeconds"] <= pts < shot["endSeconds"]:
            raise ValueError("Spin original panel seed must remain inside its actual cut")
        views = [{"id": "endcard-" + key, "rectSourcePixels": copy.deepcopy(value["rectSourcePixels"]),
                  "presentation": "native", "camera": None}
                 for key, value in data["sourceMeasurements"]["endcardViewCatalog"].items()]
        data["frames"].append({"timeSeconds": pts, "decodedTimeSeconds": pts, "shotId": shot["id"],
                               "classification": shot["classification"], "sourceMachineRequirement": "required",
                               "sourceImage": copy.deepcopy(entry["sourceImage"]), "views": views,
                               "landmarks": copy.deepcopy(entry["landmarks"]),
                               "unavailable": copy.deepcopy(entry["unavailable"])})
    data["compactChangeTimesSeconds"] = sorted(set(data.get("compactChangeTimesSeconds", []))
                                                | {entry["decodedTimeSeconds"] for entry in controls["frames"]})
    family = seeds["staticSourceFamily"]
    phase_tracking = common.retain_phase_point_provenance(data, family)
    for amendment in seeds["staticMotion"]["shotAmendments"]:
        shot = next(shot for shot in data["shots"] if shot["id"] == amendment["id"])
        shot.update(copy.deepcopy(amendment))
        shot["internalMotionSourceEvidence"] = {
            "kind": family["kind"], "familyId": family["id"], "sourceSha256": family["sourceSha256"],
            "phaseImageFrameIndices": [entry["sourceImage"]["frameIndex"] for entry in family["phaseImages"]],
            "independentSourcePhaseMapSha256": family["independentSourcePhaseMap"]["sha256"],
        }

    def views(frame):
        result = []
        originals = common.source_views(frame, data)
        group_layers = {}
        for original in originals:
            composite = original.get("composite") or {}
            if composite.get("mode") == "crossfade":
                group_layers.setdefault(composite["groupId"], set()).add(composite["imageLayerId"])
        for original in originals:
            view_id = original["id"]
            seed = seeds["views"][view_id]
            candidate = seeds["candidates"][seed["candidateId"]]
            # Numbers may be chosen, but old fit/status fields are not current
            # camera evidence even when the source pixels remain unchanged.
            framing_key = common.native_source_association.json_digest([
                frame.get("sourceImage"), view_id, original["rectSourcePixels"],
                original.get("presentation", "native"), common.resolve_warp(original)])
            camera = common.compact_camera(framings.get(framing_key) or seed.get("camera"))
            if camera:
                camera = {key: value for key, value in camera.items()
                          if key in ("positionMetres", "quaternion", "verticalFovDegrees",
                                     "principalPointViewportPixels")}
            evidence = (
                "Original own-source numeric turntable/crop framing chosen unmeasured for v39, with a complete chosen 51-field input. "
                "Source independently constrains medium-medium gearing; hidden bank/input history is not recovered. "
                if view_id in ("whole", "closeup") else
                "Original own-photograph montage numeric framing and retained chosen 51-field playback inputs, unmeasured for v39; "
                "separate panels do not share recovered physical state/camera. "
            )
            evidence += f'Historical numeric candidate {seed["candidateId"]}; packet {candidate["packet"]} SHA256 {candidate["sha256"]}. '
            evidence += "Current native station/setup ownership is checked, not current physical/GPU closure. Original CPU FIT/CHECK diagnostics remain historical only; source-first-surface and all21-stock qualification remain unmeasured."
            if view_id == "endcard-guide":
                evidence += " Guide camera remains an explicitly chosen framing assumption without source controls."
            elif view_id == "endcard-analysis-pen-inset":
                evidence += " Own nested inset rectangle retained; old Analysis4046 numeric camera is chosen/unmeasured, not current fitted or CHECK-passing evidence."
            if "presentation" in seed:
                # A documented per-view seed declaration governs native rendering,
                # not the original source layout used for exact-exposure identity.
                evidence += " " + seed["presentationEvidence"]
            view = {"id": view_id, "rectSourcePixels": copy.deepcopy(original["rectSourcePixels"]),
                    "presentation": seed.get("presentation", original.get("presentation", "native")), "camera": camera,
                    "input": common.compact_input(candidate["input"]),
                    "provenance": common.chosen_provenance(evidence, candidate["unobservedInputFields"])}
            camera_kind = "source-informed-framing"
            camera_family = f'XPQwKRt4Y2k:v39:chosen:{view_id}:{seed["candidateId"]}'
            if view_id in ("whole", "closeup"):
                evidence += (
                    f"Original source-only phase/crop registration from {family['id']} is retained; "
                    "old native calibrated71-phase camera fit is not transferred to current geometry."
                )
            view["cameraProvenance"] = {"kind": camera_kind, "family": camera_family, "evidence": evidence}
            view["cameraContinuityFamily"] = camera_family
            composite = common.compact_composite(original)
            if composite and composite.get("groupId") in ("machine-endcard", "whole-closeup") and len(group_layers[composite["groupId"]]) > 1:
                identity = frame.get("sourceImage", {})
                measured = seeds["physicalSourceCrossfades"]["frames"].get(str(identity.get("frameIndex")))
                if measured is None or measured["sourceImage"] != identity:
                    raise ValueError("A two-image source fade must bind one joint alpha to the exact retained source exposure.")
                layer = composite["imageLayerId"]
                if layer == measured["incomingImageLayerId"]:
                    composite["opacity"] = measured["incomingAlpha"]
                elif layer == measured["outgoingImageLayerId"]:
                    composite["opacity"] = measured["outgoingAlpha"]
                else:
                    raise ValueError("Joint source fade has an unknown image layer.")
                view["provenance"]["evidence"] += (
                    " Original jointly fitted actual-source BGR alpha diagnostic with complementary two-image weights, "
                    f'bound to native frame{identity["frameIndex"]}, is reused as explicitly chosen/unmeasured current presentation opacity, '
                    "not measured current alpha or current source/native/GPU matching qualification. Original independently estimated mixed-gamma weights remain diagnostics."
                )
            if composite:
                view["composite"] = composite
                view["compositeProvenance"] = copy.deepcopy(original.get("compositeProvenance") or {
                    "kind": "chosen-unmeasured",
                    "evidence": "Original composite topology remains a source obligation. Retained numeric opacity is an unmeasured presentation candidate, not source alpha or current native/GPU qualification.",
                })
            warp = common.resolve_warp(original)
            if view_id == "endcard-analysis-pen-inset":
                width, height = seed["sourceViewportPixels"]
                x, y, target_width, target_height = view["rectSourcePixels"]
                warp = {"kind": "homography", "unwarpedViewportPixels": [width, height],
                        "renderToSourcePixels": [target_width / width, 0, x, 0, target_height / height, y, 0, 0, 1]}
            if warp:
                view["imagePlaneWarp"] = warp
            result.append(view)
        return result

    track = common.build_track(data, views, [
        "The source internally static photographed machine rotates on a turntable; source camera changes, not fictitious crank-driven animation, reproduce that motion.",
        "All closeup sweep/crossfade layers and nine nested endcard views are retained, including the guide/book photographed hardware.",
        "Every current camera is chosen/unmeasured. CPU FIT/CHECK values and old native/GPU receipts remain historical lineage, not current eligibility or stage evidence.",
        "Endcard source controls use existing independently measured source pixels and source-only optical-flow/patch checks; failures and unmeasured guide/pen-inset controls remain explicit.",
    ])
    track["cpuDiagnostics"] = copy.deepcopy(seeds["historicalCpuDiagnostics"])
    track["currentChoicePacket"] = {"path": "web/content/v39/" + seed_path.name,
                                    "sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
                                    "inputSemantics": copy.deepcopy(seeds["inputSemantics"]),
                                    "qualification": seeds["qualification"]}
    track["sourceCrossfadeDiagnostics"] = copy.deepcopy(seeds["physicalSourceCrossfades"])
    track["sourceMotionFamilies"] = [copy.deepcopy(family)]
    track["sourceMeasurementTracking"] = {"method": controls["method"], "qualification": controls["qualification"],
                                         "summary": controls["summary"], "trackingFailures": controls["trackingFailures"]}
    track["sourceMeasurementTracking"]["sourceOnlySummary"] = copy.deepcopy(controls["sourceOnlySummary"])
    track["sourceMeasurementTracking"]["nativeAssociationLosses"] = copy.deepcopy(controls["nativeAssociationLosses"])
    track["sourceMeasurementTracking"]["phasePatchReacquisition"] = phase_tracking
    track["sourceMeasurementTracking"]["panelAwareCandidate"] = panel_candidate
    track["sourceMeasurements"]["status"] = "partial"
    track["sourceMeasurements"]["blockers"].append(
        "Whole-view phase/patch reacquisitions retain actual ROI NCC, actual feature NCC and independent image-edge reference measurements. "
        "Non-reference exposures do not supply the generic manual-seed whole-view .998 / feature .97 template certificate; "
        "low-correlation fade/blur exposures and missing generic qualifications remain unavailable, not promoted or removed."
    )
    track["unsupportedSourceMeasurements"] = [
        {"startSeconds": 141.55808333333331, "endSeconds": 169.41924999999998,
         "scope": "Independent fixed/moving landmark checks for all nine photographed montage views at each retained second/change point",
         "reason": "318 actual source observations (77 CHECKs) were retained by independent seeded source-only tracking over45 source exposures;1347 failed/missing observations remain unavailable. Guide and pen-inset have no independently qualified seed controls; complete per-view/every-second CHECK coverage remains incomplete."},
        {"startSeconds": 141.55808333333331, "endSeconds": 169.41924999999998,
         "scope": "endcard-guide exact camera and native source associations",
         "reason": seeds["sourceMeasurementLimits"]["guide"]},
    ]
    return track


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Unpublished candidate path; canonical tracks use the all-six transaction")
    args = parser.parse_args()
    track = build_track()
    _, contents = common.prepare_track(track)
    path = Path(args.output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)
    display_path = path.relative_to(common.WEB.parent) if path.is_relative_to(common.WEB.parent) else path
    print(json.dumps({"path": str(display_path), "shots": len(track["shots"]),
                      "frames": len(track["frames"]), "views": sum(len(frame["views"]) for frame in track["frames"]),
                      "coverage": track["coverage"]["status"], "bytes": path.stat().st_size,
                      "stages": track["stages"]}))


if __name__ == "__main__":
    main()

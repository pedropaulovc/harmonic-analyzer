#!/usr/bin/env python3
"""Generate the approximate Spin track from retained source cameras and chosen states.

No source video/frames are redistributed, no historical hidden state is recovered,
and no CPU camera diagnostic is promoted to a current native GPU measurement.
"""
import copy
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("compact_source_common", HERE / "compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def main():
    data = common.load_observations("XPQwKRt4Y2k")
    seeds = json.loads((common.WEB / "content" / "XPQwKRt4Y2k.source-seeds.json").read_text())
    controls = seeds["montageSourceControls"]
    data["anchors"].extend(copy.deepcopy(controls["anchors"]))
    source_controls = {(entry["sourceImage"]["frameIndex"], entry["sourceImage"]["sha256Bgr8"]): entry for entry in controls["frames"]}
    for frame in data["frames"]:
        identity = frame.get("sourceImage", {})
        entry = source_controls.get((identity.get("frameIndex"), identity.get("sha256Bgr8")))
        if entry:
            frame["landmarks"].extend(copy.deepcopy(entry["landmarks"]))
            frame.setdefault("unavailable", []).extend(copy.deepcopy(entry["unavailable"]))
    original_frames = list(data["frames"])
    existing_times = {frame["timeSeconds"] for frame in data["frames"]}
    for entry in controls["frames"]:
        pts = entry["decodedTimeSeconds"]
        if pts in existing_times:
            continue
        shot = next(shot for shot in data["shots"] if shot["startSeconds"] <= pts < shot["endSeconds"])
        donors = [frame for frame in original_frames if frame["shotId"] == shot["id"]]
        donor = min(donors, key=lambda frame: abs(frame["decodedTimeSeconds"] - pts))
        frame = copy.deepcopy(donor)
        frame.update({"timeSeconds": pts, "decodedTimeSeconds": pts, "sourceImage": copy.deepcopy(entry["sourceImage"]),
                      "landmarks": copy.deepcopy(entry["landmarks"]), "unavailable": copy.deepcopy(entry["unavailable"])})
        data["frames"].append(frame)
        existing_times.add(pts)
    data["compactChangeTimesSeconds"] = [entry["decodedTimeSeconds"] for entry in controls["frames"]]
    family = seeds["staticSourceFamily"]
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
            camera = common.compact_camera(original.get("camera") or seed.get("camera"))
            evidence = (
                "Retained actual-source turntable/crop camera and complete chosen static native20 bank input. "
                "Source independently constrains medium-medium gearing; hidden bank/input history is chosen, not recovered. "
                if view_id in ("whole", "closeup") else
                "Retained independently source-referenced photographic montage view with its own complete chosen51 state; "
                "separate panels are not asserted to share physical state or camera. "
            )
            evidence += f'Candidate {seed["candidateId"]}; original numeric packet {candidate["packet"]} SHA256 {candidate["sha256"]}. '
            if view_id == "endcard-guide":
                evidence += seed["cameraEvidence"]["assumption"]
            elif view_id == "endcard-analysis-pen-inset":
                evidence += (
                    "Camera is the retained Analysis4046 all-six-source-point CPU candidate, independently CHECK-failed at89.40168039064345px "
                    "under the old2% threshold. Reframed to the source-measured nested inset rectangle by a chosen image-plane resize; "
                    "not a newly measured physical camera or passing source fit."
                )
            elif seed.get("cameraEvidence"):
                evidence += "Prior photographic/camera CHECK diagnostics are retained separately; no current GPU acceptance claimed."
            view = {"id": view_id, "rectSourcePixels": copy.deepcopy(original["rectSourcePixels"]),
                    "presentation": original.get("presentation", "native"), "camera": camera,
                    "input": common.compact_input(candidate["input"]),
                    "provenance": common.chosen_provenance(evidence, candidate["unobservedInputFields"])}
            camera_kind = "source-fit" if view_id in ("whole", "closeup") else "source-transfer"
            if view_id == "endcard-guide":
                camera_kind = "source-informed-framing"
            camera_family = f'XPQwKRt4Y2k:{view_id}:71-phase-rig' if view_id in ("whole", "closeup") else f'XPQwKRt4Y2k:{view_id}:{seed["candidateId"]}'
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
                    " Composite uses one jointly fitted actual-source BGR alpha with complementary two-image weights, "
                    f'bound to native frame{identity["frameIndex"]}. Original independently estimated mixed-gamma weights '
                    "are preserved as diagnostics; conditional source colour fit is not native GPU/source matching acceptance."
                )
            if composite:
                view["composite"] = composite
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
        "Camera FIT/CHECK values are original CPU diagnostic residuals and unmeasured at the new50/20/10/5% stages.",
        "Endcard source controls use existing independently measured source pixels and source-only optical-flow/patch checks; failures and unmeasured guide/pen-inset controls remain explicit.",
    ])
    track["cpuDiagnostics"] = {view_id: copy.deepcopy(seed.get("cameraEvidence", {})) for view_id, seed in seeds["views"].items() if seed.get("cameraEvidence")}
    track["sourceCrossfadeDiagnostics"] = copy.deepcopy(seeds["physicalSourceCrossfades"])
    track["sourceMotionFamilies"] = [copy.deepcopy(family)]
    track["sourceMeasurementTracking"] = {"method": controls["method"], "qualification": controls["qualification"],
                                         "summary": controls["summary"], "trackingFailures": controls["trackingFailures"]}
    track["unsupportedSourceMeasurements"] = [
        {"startSeconds": 141.55808333333331, "endSeconds": 169.41924999999998,
         "scope": "Independent fixed/moving landmark checks for all nine photographed montage views at each retained second/change point",
         "reason": "318 actual source observations (77 CHECKs) were retained by independent seeded source-only tracking over45 source exposures;1347 failed/missing observations remain unavailable. Guide and pen-inset have no independently qualified seed controls; complete per-view/every-second CHECK coverage remains incomplete."},
        {"startSeconds": 141.55808333333331, "endSeconds": 169.41924999999998,
         "scope": "endcard-guide exact camera and native source associations",
         "reason": seeds["sourceMeasurementLimits"]["guide"]},
    ]
    path = common.write_track(track)
    print(json.dumps({"path": str(path.relative_to(common.WEB.parent)), "shots": len(track["shots"]),
                      "frames": len(track["frames"]), "views": sum(len(frame["views"]) for frame in track["frames"]),
                      "coverage": track["coverage"]["status"], "bytes": path.stat().st_size,
                      "stages": track["stages"]}))


if __name__ == "__main__":
    main()

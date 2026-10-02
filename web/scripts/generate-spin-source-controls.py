#!/usr/bin/env python3
"""Track independently measured Spin montage or physical pixels in retained source.

This prepares private numerical observations; it never changes production tracks,
loads a native model, fits a camera, or runs a GPU/browser. Original FIT/CHECK roles
and uncertainties are retained. Failed source tracks stay unavailable.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
import math
import subprocess
from fractions import Fraction
from pathlib import Path

import cv2

WEB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("observe_source", WEB / "scripts" / "observe-source.py")
observe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observe)


def montage_controls(args):
    source = json.loads((WEB / "content" / "XPQwKRt4Y2k.observations.json").read_text())
    compact = json.loads((WEB / "content" / "XPQwKRt4Y2k.source-track.json").read_text())
    catalog = source["sourceMeasurements"]["endcardViewCatalog"]
    fps = source["source"]["fps"]["numerator"] / source["source"]["fps"]["denominator"]
    seed_index = 3452
    seed_pts = seed_index / fps
    cap = cv2.VideoCapture(str(args.reference_root / "videos" / "XPQwKRt4Y2k.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
    ok, image = cap.read()
    if not ok:
        raise ValueError("Cannot decode original independent montage source reference.")
    seed_hash = hashlib.sha256(image.tobytes()).hexdigest()
    if seed_hash != "39b3f841ad036fb82c3aa353e7e31db834df7f7adefbe9ae5788356c5000566f":
        raise ValueError("Original montage source reference pixels differ from frozen independently measured source evidence.")
    anchors, landmarks, views = [], [], []
    included = ("intro", "synthesis", "analysis", "operation-paper-0", "operation-paper-1", "operation-paper-2", "book")
    for key in included:
        entry = catalog[key]
        view_id = "endcard-" + key
        views.append({"id": view_id, "rectSourcePixels": entry["rectSourcePixels"]})
        for point in entry.get("landmarks", []):
            if point.get("status") not in ("source-locally-measured", "source-measured-coarse-junction"):
                continue
            x, y, width, height = entry["rectSourcePixels"]
            if not x <= point["pixel"][0] < x + width or not y <= point["pixel"][1] < y + height:
                continue
            anchor_id = f'{view_id}:{point["id"]}'
            coordinates = {"partLocalMetres": point["partLocalMetres"]} if point.get("partLocalMetres") is not None else {"worldMetres": point["worldMetres"]}
            kind = "virtual-section-centre" if key == "book" else "physical-feature"
            anchors.append({"id": anchor_id, "kind": kind, "partPath": point["partPath"], **coordinates,
                            "description": f'Independently source-measured montage feature {point["id"]}.',
                            "correspondenceEvidence": point.get("correspondenceEvidence") or "Retained independent source-photographic/native hardware association in original endcardViewCatalog; candidate association, not GPU acceptance.",
                            "motion": "moving" if "rocker-arm-" in point["partPath"] else "fixed"})
            landmarks.append({"anchorId": anchor_id, "viewId": view_id, "role": point["role"], "pixel": point["pixel"],
                              "status": "observed", "method": "manual", "uncertaintyPx": point["uncertaintyPx"]})
    seed = {"timeSeconds": seed_pts, "decodedTimeSeconds": seed_pts, "landmarks": landmarks, "views": views}
    kinds = {anchor["id"]: anchor["kind"] for anchor in anchors}
    desired = {frame["sourceImage"]["frameIndex"] for frame in compact["frames"] if frame.get("sourceImage") and 141.558083 <= frame["decodedTimeSeconds"] < 169.41925}
    desired.add(seed_index)
    backward, backward_failures = observe.track_direction(cap, seed_index, min(desired), seed, kinds, fps)
    forward, forward_failures = observe.track_direction(cap, seed_index, max(desired), seed, kinds, fps)
    tracked = {**backward, seed_index: landmarks, **forward}
    frames = []
    for index in sorted(desired):
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, actual = cap.read()
        if not ok:
            raise ValueError(f"Cannot decode retained source frame{index}.")
        points = tracked.get(index, [])
        frames.append({"decodedTimeSeconds": index / fps,
                       "sourceImage": {"frameIndex": index, "sha256Bgr8": hashlib.sha256(actual.tobytes()).hexdigest(),
                                       "pixelFormat": "bgr8", "width": actual.shape[1], "height": actual.shape[0], "sourceSha256": source["source"]["sha256"]},
                       "landmarks": points,
                       "unavailable": [{"anchorId": anchor["id"], "reason": "Source-only optical flow/patch control did not retain this independently measured feature."} for anchor in anchors if not any(point["anchorId"] == anchor["id"] for point in points)]})
    cap.release()
    packet = {"schemaVersion": 1, "videoId": source["source"]["videoId"], "sourceSha256": source["source"]["sha256"],
              "productionIntegrated": False, "sourceSeed": {"frameIndex": seed_index, "decodedTimeSeconds": seed_pts, "sha256Bgr8": seed_hash},
              "method": "Existing observe-source.py track_direction: original source images only, physical manual seed, forward/backward optical flow plus independent source-patch correlation, per-view source rectangle; no native projection in measurements. Alias selection uses exact sourceImage frame/hash.",
              "qualification": "Conditional source-only feature tracking, not semantic body/material proof, native raster measurement, or stage acceptance. FIT/CHECK roles unchanged; failures remain unavailable.",
              "anchors": anchors, "frames": frames, "trackingFailures": backward_failures + forward_failures,
              "unsupportedViews": ["endcard-analysis-pen-inset", "endcard-guide"],
              "summary": {"anchors": len(anchors), "sourceFrames": len(frames), "sourceSeedPoints": len(landmarks),
                          "trackedObservations": sum(len(frame["landmarks"]) for frame in frames),
                          "independentCheckObservations": sum(point["role"] == "check" for frame in frames for point in frame["landmarks"]),
                          "unavailableObservations": sum(len(frame["unavailable"]) for frame in frames)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, separators=(",", ":"), allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), **packet["summary"]}))


def physical_controls(args):
    source = json.loads((WEB / "content" / "XPQwKRt4Y2k.observations.json").read_text())
    declarations = json.loads((WEB / "content" / "XPQwKRt4Y2k.source-seeds.json").read_text())
    declaration = declarations["physicalSourceSeeds"]
    seed_path = WEB.parent / declaration["path"]
    if observe.digest(seed_path) != declaration["sha256"]:
        raise ValueError("Physical source seed file differs from its independent declaration.")
    seed_packet = json.loads(seed_path.read_text())
    video = args.reference_root / "videos" / "XPQwKRt4Y2k.mp4"
    source_hash = observe.digest(video)
    if seed_packet["schemaVersion"] != 1 or source_hash != seed_packet["sourceSha256"] or source_hash != source["source"]["sha256"]:
        raise ValueError("Original physical source or seed provenance differs.")
    # Read declared anchor motion only; native frames, cameras and inputs are not
    # measurement authorities and are never consulted by this producer.
    metadata = json.loads((WEB / "content" / "XPQwKRt4Y2k.source-track.json").read_text())
    motions = {anchor["id"]: anchor["motion"] for anchor in metadata["anchors"]}
    kinds = {anchor["id"]: anchor["kind"] for anchor in source["anchors"]}
    shots = {shot["id"]: shot for shot in source["shots"]}
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams",
         "-show_frames", "-show_entries",
         "stream=width,height,time_base,avg_frame_rate:frame=pts",
         "-of", "json", str(video)], check=True, capture_output=True).stdout)
    stream = probe["streams"][0]
    time_base = Fraction(stream["time_base"])
    rate = Fraction(stream["avg_frame_rate"])
    ticks = [int(frame["pts"]) for frame in probe["frames"]]
    times = [float(tick * time_base) for tick in ticks]
    fps = float(rate)
    # Existing APIs index a constant-rate source. Prove that clock instead of
    # treating rounded ffprobe display strings or nominal frame numbers as PTS.
    if not ticks or any(tick * time_base != Fraction(index, 1) / rate for index, tick in enumerate(ticks)):
        raise ValueError("Physical source clock is incompatible with unchanged observer APIs.")
    if (stream["width"], stream["height"]) != (1920, 1080):
        raise ValueError("Physical source dimensions differ from independently measured pixels.")

    def identity(index, image):
        return {"frameIndex": index, "sha256Bgr8": hashlib.sha256(image.tobytes()).hexdigest(),
                "pixelFormat": "bgr8", "width": image.shape[1], "height": image.shape[0],
                "sourceSha256": source_hash}

    seeds = copy.deepcopy(seed_packet["seeds"])
    cap = cv2.VideoCapture(str(video), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 2])
    cv2.setNumThreads(2)
    found, failures, seed_points = {}, [], {}
    try:
        # Validate every independent seed before running any descendant tracker.
        for seed in seeds:
            index = seed["sourceImage"]["frameIndex"]
            if type(index) is not int or not 0 <= index < len(ticks):
                raise ValueError("Physical seed has no native source exposure.")
            if seed["decodedTimestampTicks"] != ticks[index] or Fraction(seed["timeBase"]) != time_base:
                raise ValueError("Physical seed native timestamp differs.")
            seed["originalSourceClockEvidence"] = {
                field: seed[field] for field in
                ("timeSeconds", "decodedTimeSeconds", "decodedTimestampTicks", "timeBase")}
            for field in ("timeSeconds", "decodedTimeSeconds"):
                declared = seed[field]
                if declared not in (times[index], ticks[index] * float(time_base)):
                    raise ValueError("Physical seed time is not its declared native rational PTS.")
                seed[field] = times[index]
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = cap.read()
            if not ok or identity(index, image) != seed["sourceImage"]:
                raise ValueError("Physical seed BGR pixels differ from independent declaration.")
            shot = shots[seed["shotId"]]
            if not shot["startSeconds"] <= times[index] < shot["endSeconds"]:
                raise ValueError("Physical seed is outside its declared source shot.")
            view_ids = {view["id"] for view in seed["views"]}
            if len(view_ids) != 1 or not view_ids <= {"whole", "closeup"} or any(
                view["rectSourcePixels"] != [0, 0, 1920, 1080] for view in seed["views"]
            ):
                raise ValueError("Physical seeds require independently identified full-source views.")
            if view_ids != ({"closeup"} if seed["shotId"] == "closeup-sweep" else {"whole"}):
                raise ValueError("Physical seed view and shot disagree.")
            for point in seed["landmarks"]:
                anchor = point["anchorId"]
                if kinds.get(anchor) != "physical-feature" or point["method"] != "manual" or point["role"] != "check":
                    raise ValueError("Physical seeds must remain existing manual physical CHECKs.")
                if motions.get(anchor) not in ("fixed", "moving") or point["viewId"] not in view_ids:
                    raise ValueError("Physical seed lacks declared motion or source view.")
                pixel = point["pixel"]
                if len(pixel) != 2 or not all(math.isfinite(value) for value in pixel) or not (
                    0 <= pixel[0] < 1920 and 0 <= pixel[1] < 1080
                ):
                    raise ValueError("Physical seed pixel is outside its source image.")
                if point["measurementEvidence"]["sourceImage"] != seed["sourceImage"]:
                    raise ValueError("Physical point independent seed identity differs.")
                key = (times[index], point["viewId"], anchor)
                if key in seed_points:
                    raise ValueError("Duplicate independent physical seed key.")
                seed_points[key] = (seed, point)

        for seed in seeds:
            index = seed["sourceImage"]["frameIndex"]
            shot = shots[seed["shotId"]]
            boundaries = [max(0, math.ceil(shot["startSeconds"] * fps)),
                          min(len(ticks) - 1, math.ceil(shot["endSeconds"] * fps) - 1)]
            for boundary in boundaries:
                if boundary == index:
                    continue
                tracked, stopped = observe.track_direction(cap, index, boundary, seed, kinds, fps)
                for failure in stopped:
                    failure = copy.deepcopy(failure)
                    failed_index = round(failure["timeSeconds"] * fps)
                    failure["observerTimeSeconds"] = failure["timeSeconds"]
                    failure.update(timeSeconds=times[failed_index], decodedTimestampTicks=ticks[failed_index],
                                   timeBase=stream["time_base"], seedTimeSeconds=seed["timeSeconds"],
                                   seedSourceImage=seed["sourceImage"])
                    failures.append(failure)
                for target, points in tracked.items():
                    for point in points:
                        key = (point["viewId"], point["anchorId"])
                        old = found.setdefault(target, {}).get(key)
                        # Stable seed order breaks equal-distance ties; a repeated
                        # source patch retains precedence over flow, as reviewed.
                        if old is None or old["method"] == "optical-flow" and (
                            abs(times[target] - point["trackingEvidence"]["seedTimeSeconds"])
                            < abs(times[target] - old["trackingEvidence"]["seedTimeSeconds"])
                        ):
                            found[target][key] = point
            if seed["views"][0]["id"] == "whole":
                for point in seed["landmarks"]:
                    repeated, _ = observe.repeated_source_views(
                        cap, {**seed, "landmarks": [point]}, shot, source["shots"], fps, len(ticks))
                    for target, points in repeated.items():
                        for descendant in points:
                            found.setdefault(target, {})[(descendant["viewId"], descendant["anchorId"])] = descendant
        # Manual observations win globally, including against later seeds'
        # repeated patches at exactly the same exposure.
        for seed in seeds:
            for point in seed["landmarks"]:
                found.setdefault(seed["sourceImage"]["frameIndex"], {})[(point["viewId"], point["anchorId"])] = copy.deepcopy(point)

        frames = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        for index in range(max(found) + 1):
            ok, image = cap.read()
            if not ok:
                raise ValueError(f"Cannot reproduce tracked physical source frame{index}.")
            if not found.get(index):
                continue
            source_image = identity(index, image)
            points = list(found[index].values())
            for point in points:
                if point["method"] == "manual":
                    seed_key = (times[index], point["viewId"], point["anchorId"])
                else:
                    evidence = point["trackingEvidence"]
                    seed_key = (evidence["seedTimeSeconds"], point["viewId"], point["anchorId"])
                independent_seed, manual = seed_points[seed_key]
                if point["method"] == "manual" and source_image != independent_seed["sourceImage"]:
                    raise ValueError("Retained manual exposure differs from its independent seed.")
                if point["role"] != manual["role"]:
                    raise ValueError("Physical descendant changed its independent CHECK partition.")
                # Preserve the complete authored provenance, not merely its hash.
                original_evidence = copy.deepcopy(manual["measurementEvidence"])
                point["measurementEvidence"] = {
                    **original_evidence, "sourceImage": source_image,
                    "independentManualSeedSourceImage": independent_seed["sourceImage"],
                    "manualProvenance": original_evidence,
                    "sourceOnlyProducer": "Unchanged observe-source.py APIs; no native images/cameras/errors consumed."}
            frames.append({"timeSeconds": times[index], "decodedTimeSeconds": times[index],
                           "decodedTimestampTicks": ticks[index], "timeBase": stream["time_base"],
                           "sourceImage": source_image, "landmarks": points, "unavailable": []})
    finally:
        cap.release()
    points = [point for frame in frames for point in frame["landmarks"]]
    packet = {
        "schemaVersion": 1, "videoId": source["source"]["videoId"], "sourceSha256": source_hash,
        "method": "Unchanged observe-source.py shot-bounded optical flow and per-feature repeated whole-source views; closeup optical flow only. Integer native PTS/rational timebase and decoded BGR identities.",
        "qualification": "Source-only physical CHECK candidates, not semantic body/material proof, native raster measurement, or stage acceptance. Original roles/provenance and tracker losses retained.",
        "frames": frames, "manualSeeds": seeds, "trackingFailures": failures,
        "summary": {"sourceSeedPoints": sum(len(seed["landmarks"]) for seed in seeds),
                    "sourceFrames": len(frames), "trackedObservations": len(points),
                    "check": sum(point["role"] == "check" for point in points),
                    "fixed": sum(motions[point["anchorId"]] == "fixed" for point in points),
                    "moving": sum(motions[point["anchorId"]] == "moving" for point in points),
                    "trackingFailures": len(failures)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, separators=(",", ":"), allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), **packet["summary"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("montage", "physical"), default="montage")
    parser.add_argument("--reference-root", type=Path, default=Path(os.environ.get("HARMONIC_REFERENCE_ROOT", WEB / ".vite" / "reference-root")))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is None:
        args.output = WEB / ".vite" / "verification-output" / "compact-track-refinement" / f"spin-{args.scope}-source-controls.json"
    if args.scope == "physical":
        physical_controls(args)
    else:
        montage_controls(args)


if __name__ == "__main__":
    main()

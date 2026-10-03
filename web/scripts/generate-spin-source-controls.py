#!/usr/bin/env python3
"""Track actual Spin montage pixels with panel/patch support and native clocks.

CPU source-only producer; never writes generated playback tracks or changes old
source observations. A seed/flow positive is not a native feature/camera/GPU pass.
FIT/CHECK roles and uncertainties remain the original manual seed authorities.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np

WEB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("observe_source", WEB / "scripts" / "observe-source.py")
observe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observe)


def supported_patch(pixel, rect, blockers, radius):
    """The entire raw-pixel flow/patch neighbourhood must belong to this panel."""
    px, py = pixel
    x, y, width, height = rect
    if not (x <= px - radius and px + radius < x + width
            and y <= py - radius and py + radius < y + height):
        return False
    return not any(px + radius >= bx and px - radius <= bx + bw
                   and py + radius >= by and py - radius <= by + bh
                   for bx, by, bw, bh in blockers)


def panel_track(cap, seed_index, boundary_index, seed_image, points, rect, blockers, policy, times):
    """Reuse the observer's source-patch checks, with no cross-panel LK pyramid."""
    x, y, width, height = rect
    if any(type(value) is not int for value in rect):
        raise ValueError("Physical montage tracking requires an exact integer raw source panel crop")
    previous = cv2.cvtColor(seed_image[y:y + height, x:x + width], cv2.COLOR_BGR2GRAY)
    active, failures = {}, []
    radius = policy["sourceSupportRadiusPixels"]
    direction = 1 if boundary_index > seed_index else -1
    for point in points:
        if not supported_patch(point["pixel"], rect, blockers, radius):
            failures.append({"anchorId": point["anchorId"], "viewId": point["viewId"],
                             "frameIndex": seed_index, "timeSeconds": times[seed_index], "direction": direction,
                             "reason": "Independent manual seed is retained, but its full raw patch/flow support touches a panel edge or later source inset; no descendants admitted."})
            continue
        item = copy.deepcopy(point)
        item["pixel"] = [point["pixel"][0] - x, point["pixel"][1] - y]
        active[item["anchorId"]] = item
    original = {key: observe.patch(previous, point["pixel"]) for key, point in active.items()}
    tracked = {}
    cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
    ok, actual_seed = cap.read()
    if not ok or not np.array_equal(actual_seed, seed_image):
        raise ValueError("Source panel seed exposure changed before tracking")
    for index in range(seed_index + direction, boundary_index + direction, direction):
        if not active:
            break
        if direction < 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok:
            raise ValueError(f"Cannot decode required panel source frame{index}")
        current = cv2.cvtColor(image[y:y + height, x:x + width], cv2.COLOR_BGR2GRAY)
        keys = list(active)
        old = np.asarray([active[key]["pixel"] for key in keys], dtype=np.float32).reshape(-1, 1, 2)
        new, forward, _ = cv2.calcOpticalFlowPyrLK(previous, current, old, None,
                                               winSize=(policy["flowWindowPixels"],) * 2, maxLevel=policy["flowMaxLevel"])
        reverse, backward = (cv2.calcOpticalFlowPyrLK(current, previous, new, None,
                                                    winSize=(policy["flowWindowPixels"],) * 2, maxLevel=policy["flowMaxLevel"])
                             if new is not None else (None, None, None))[:2]
        for offset, key in enumerate(keys):
            item = active[key]
            valid = (new is not None and forward is not None and bool(forward[offset, 0])
                     and reverse is not None and backward is not None and bool(backward[offset, 0]))
            candidate = new[offset, 0] if new is not None else np.asarray(item["pixel"])
            source_pixel = [float(candidate[0] + x), float(candidate[1] + y)]
            error = float(np.linalg.norm(reverse[offset, 0] - old[offset, 0])) if reverse is not None else math.inf
            seed_ncc = observe.correlation(original[key], observe.patch(current, candidate))
            adjacent_ncc = observe.correlation(observe.patch(previous, old[offset, 0]), observe.patch(current, candidate))
            reason = None
            if not valid:
                reason = "Source flow lost feature"
            elif not supported_patch(source_pixel, rect, blockers, radius):
                reason = "Full source patch/flow support left its panel or touched a later inset"
            elif error > policy["maximumForwardBackwardErrorPixels"]:
                reason = "Source forward/backward inconsistency"
            elif seed_ncc < policy["minimumSeedPatchCorrelation"] or adjacent_ncc < policy["minimumAdjacentPatchCorrelation"]:
                reason = "Original seed/adjacent source patch changed"
            if reason:
                failures.append({"anchorId": key, "viewId": item["viewId"], "frameIndex": index,
                                 "timeSeconds": times[index], "direction": direction, "reason": reason})
                del active[key]
                continue
            item["pixel"] = candidate.tolist()
            item["method"] = "optical-flow"
            item["uncertaintyPx"] = max(item["uncertaintyPx"], error)
            item["trackingEvidence"] = {"seedTimeSeconds": times[seed_index],
                                        "seedFrameIndex": seed_index, "forwardBackwardErrorPx": error,
                                        "seedPatchCorrelation": seed_ncc, "adjacentPatchCorrelation": adjacent_ncc,
                                        "sourcePanelRectPixels": rect, "blockedSourceRectangles": blockers,
                                        "sourceSupportRadiusPixels": radius, "flowMaxLevel": policy["flowMaxLevel"]}
        tracked[index] = []
        for item in active.values():
            output = copy.deepcopy(item)
            output["pixel"] = [float(item["pixel"][0] + x), float(item["pixel"][1] + y)]
            tracked[index].append(output)
        previous = current
    return tracked, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path, default=Path(os.environ.get("HARMONIC_REFERENCE_ROOT", WEB / ".vite" / "reference-root")))
    parser.add_argument("--profile", type=Path, default=WEB / "content" / "XPQwKRt4Y2k.panel-tracking.json")
    parser.add_argument("--output", type=Path, default=WEB / ".vite" / "verification-output" / "compact-track-refinement" / "spin-panel-source-controls.json")
    args = parser.parse_args()
    source = json.loads((WEB / "content" / "XPQwKRt4Y2k.observations.json").read_text())
    compact = json.loads((WEB / "content" / "XPQwKRt4Y2k.source-track.json").read_text())
    profile = json.loads(args.profile.read_text())
    video = args.reference_root / "videos" / "XPQwKRt4Y2k.mp4"
    source_hash = observe.digest(video)
    if source_hash != source["source"]["sha256"] or source_hash != profile["sourceSha256"]:
        raise ValueError("Original Spin source differs from the independent manual seed authority")
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-show_frames",
                                      "-show_entries", "stream=width,height,time_base,avg_frame_rate:frame=pts", "-of", "json", str(video)],
                                     check=True, capture_output=True).stdout)
    stream = probe["streams"][0]
    time_base, rate = Fraction(stream["time_base"]), Fraction(stream["avg_frame_rate"])
    ticks = [int(frame["pts"]) for frame in probe["frames"]]
    times = [float(tick * time_base) for tick in ticks]
    if ((stream["width"], stream["height"]) != (1920, 1080)
            or rate != Fraction(source["source"]["fps"]["numerator"], source["source"]["fps"]["denominator"])
            or any(tick * time_base != Fraction(index) / rate for index, tick in enumerate(ticks))):
        raise ValueError("Spin raw source clock/dimensions differ from the original independently measured panels")
    seed_index = profile["sourceSeed"]["frameIndex"]
    shot = next(shot for shot in source["shots"] if shot["id"] == profile["sourceSeed"]["shotId"])
    if not shot["startSeconds"] <= times[seed_index] < shot["endSeconds"]:
        raise ValueError("Manual panel seed does not belong to its declared source shot")
    first = next(index for index, time in enumerate(times) if time >= shot["startSeconds"])
    last = max(index for index, time in enumerate(times) if time < shot["endSeconds"])
    catalog = source["sourceMeasurements"]["endcardViewCatalog"]
    cap = cv2.VideoCapture(str(video), cv2.CAP_FFMPEG, [cv2.CAP_PROP_N_THREADS, 2])
    cv2.setNumThreads(2)
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
        ok, image = cap.read()
        if not ok or hashlib.sha256(image.tobytes()).hexdigest() != profile["sourceSeed"]["sha256Bgr8"]:
            raise ValueError("Original manual montage seed BGR pixels differ")
        anchors, manual, tracked, failures = [], [], {}, []
        for key in profile["panels"]:
            entry = catalog[key]
            view_id = "endcard-" + key
            rect = entry["rectSourcePixels"]
            blockers = [catalog[mask]["rectSourcePixels"] for mask in profile["blockedCatalogViews"].get(key, [])]
            points = []
            for point in entry.get("landmarks", []):
                if point.get("status") not in ("source-locally-measured", "source-measured-coarse-junction"):
                    continue
                px, py = point["pixel"]
                if not rect[0] <= px < rect[0] + rect[2] or not rect[1] <= py < rect[1] + rect[3]:
                    raise ValueError("Manual seed association falls outside its own source panel")
                anchor_id = f'{view_id}:{point["id"]}'
                coordinates = {"partLocalMetres": point["partLocalMetres"]} if point.get("partLocalMetres") is not None else {"worldMetres": point["worldMetres"]}
                kind = "virtual-section-centre" if key == "book" else "physical-feature"
                anchors.append({"id": anchor_id, "kind": kind, "partPath": point["partPath"], **coordinates,
                                "description": f'Independent source panel feature {point["id"]}.',
                                "correspondenceEvidence": point.get("correspondenceEvidence") or "Original endcardViewCatalog conditional source/native association; not current native eligibility.",
                                "motion": "moving" if "rocker-arm-" in point["partPath"] else "fixed"})
                landmark = {"anchorId": anchor_id, "viewId": view_id, "role": point["role"], "pixel": copy.deepcopy(point["pixel"]),
                            "status": "observed", "method": "manual", "uncertaintyPx": point["uncertaintyPx"]}
                manual.append(landmark)
                if kind == "physical-feature":
                    points.append(landmark)
            # Virtual geometric junctions remain manual at their actual seed only;
            # they never become optical-flow features merely by repeated naming.
            for boundary in (first, last):
                rows, lost = panel_track(cap, seed_index, boundary, image, points, rect, blockers, profile["tracking"], times)
                failures.extend(lost)
                for index, landmarks in rows.items():
                    tracked.setdefault(index, []).extend(landmarks)
        tracked[seed_index] = manual
        desired = {frame["sourceImage"]["frameIndex"] for frame in compact["frames"]
                   if frame.get("sourceImage") and 141.558083 <= frame["decodedTimeSeconds"] < 169.41925}
        desired.add(seed_index)
        frames = []
        for index in sorted(desired):
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, actual = cap.read()
            if not ok:
                raise ValueError(f"Cannot decode original requested montage source frame{index}")
            identity = {"frameIndex": index, "sha256Bgr8": hashlib.sha256(actual.tobytes()).hexdigest(), "pixelFormat": "bgr8",
                        "width": actual.shape[1], "height": actual.shape[0], "sourceSha256": source_hash}
            points = tracked.get(index, [])
            present = {point["anchorId"] for point in points}
            frames.append({"timeSeconds": times[index], "decodedTimeSeconds": times[index], "decodedTimestampTicks": ticks[index],
                           "timeBase": stream["time_base"], "sourceImage": identity, "landmarks": points,
                           "unavailable": [{"anchorId": anchor["id"], "reason": "Independent source cut requires a new manual panel seed; no cross-cut tracking." if not first <= index <= last else "Panel-bound source track did not retain this feature; no projected/interpolated pixel."}
                                           for anchor in anchors if anchor["id"] not in present]})
    finally:
        cap.release()
    packet = {"schemaVersion": 1, "videoId": source["source"]["videoId"], "sourceSha256": source_hash,
              "producerSha256": observe.digest(Path(__file__)), "profileSha256": observe.digest(args.profile),
              "productionIntegrated": False, "sourceSeed": {**profile["sourceSeed"], "decodedTimeSeconds": times[seed_index],
                                                           "decodedTimestampTicks": ticks[seed_index], "timeBase": stream["time_base"]},
              "method": "Per-panel actual raw source crop; level-zero forward/backward flow and unchanged observer source-patch NCC; full neighbourhood/inset support; native rational PTS. No cameras, native images or CHECK errors used.",
              "qualification": profile["qualification"], "anchors": anchors, "frames": frames, "trackingFailures": failures,
              "unsupportedViews": profile["unsupportedViews"],
              "summary": {"anchors": len(anchors), "sourceFrames": len(frames), "sourceSeedPoints": len(manual),
                          "trackedObservations": sum(len(frame["landmarks"]) for frame in frames),
                          "independentCheckObservations": sum(point["role"] == "check" for frame in frames for point in frame["landmarks"]),
                          "unavailableObservations": sum(len(frame["unavailable"]) for frame in frames)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, separators=(",", ":"), allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), **packet["summary"]}))


if __name__ == "__main__":
    main()

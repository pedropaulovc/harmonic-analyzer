#!/usr/bin/env python3
"""Track independently measured Spin montage pixels in the actual retained source.

This prepares nonpublishable historical diagnostic observations; it never changes
production tracks, loads a native model, fits a camera, or runs a GPU/browser.
Require --historical-diagnostic. Original FIT/CHECK roles and uncertainties remain.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import cv2

WEB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("observe_source", WEB / "scripts" / "observe-source.py")
observe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observe)


def private_output(path):
    output = Path(path).resolve()
    external_temp = not output.is_relative_to(WEB.resolve().parent) and any(
        output.is_relative_to(Path(temp).resolve()) for temp in ("/tmp", "/var/tmp"))
    private = WEB.resolve() / ".vite/verification-output"
    private_escape = not output.is_relative_to(private) and any(
        parent.name == "verification-output" and parent.parent.name == ".vite"
        and parent.parent.parent.resolve() == WEB.resolve()
        for parent in Path(path).absolute().parents)
    if private_escape or output.is_relative_to((WEB / "content").resolve()) or not (
            output.is_relative_to(private) or external_temp):
        raise ValueError("Historical diagnostics require private .vite/verification-output or external temporary output; cannot write published content or canonical originals")
    return output


def build_packet(reference_root, *, historical_diagnostic=False):
    if historical_diagnostic is not True:
        raise ValueError("Spin controls require historical_diagnostic=True")
    source = observe.common.load_historical_observations("XPQwKRt4Y2k")
    compact = observe.common.load_historical_observations("XPQwKRt4Y2k", prefer_track=True)
    for record in (source, compact):
        if (
            record.get("kind") == "current-source-observations"
            or record.get("freshSourceRecord") is not None
            or record.get("identityDerivative", {}).get("kind") != "materialized-canonical-native-identity-derivative"
            or record.get("model", {}).get("sha256") != "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d"
            or record.get("model", {}).get("sourceCommit") != "1268c23d4a8fc741147c5e09d8d1e45247a71945"
            or record.get("source", {}).get("videoId") != "XPQwKRt4Y2k"
            or record.get("source", {}).get("sha256") != "52caae2e9d617934ae9eb80d6a3d2b1679b31eb9c71e9da741152e84e2d68505"
        ):
            raise ValueError("Spin diagnostics require the original historical source/model tuple")
    catalog = source["sourceMeasurements"]["endcardViewCatalog"]
    fps = source["source"]["fps"]["numerator"] / source["source"]["fps"]["denominator"]
    seed_index = 3452
    seed_pts = seed_index / fps
    cap = cv2.VideoCapture(str(Path(reference_root) / "videos" / "XPQwKRt4Y2k.mp4"))
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
    desired = {frame["sourceImage"]["frameIndex"] for frame in observe.common.selected_frames(compact) if frame.get("sourceImage") and 141.558083 <= frame["decodedTimeSeconds"] < 169.41925}
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
    packet = {"schemaVersion": 1, "kind": "historical-source-track-receipt",
              "historicalDiagnostic": True, "publishable": False,
              "videoId": source["source"]["videoId"], "sourceSha256": source["source"]["sha256"],
              "productionIntegrated": False, "sourceSeed": {"frameIndex": seed_index, "decodedTimeSeconds": seed_pts, "sha256Bgr8": seed_hash},
              "method": "Existing observe-source.py track_direction: original source images only, physical manual seed, forward/backward optical flow plus independent source-patch correlation, per-view source rectangle; no native projection in measurements. Alias selection uses exact sourceImage frame/hash.",
              "qualification": "Conditional source-only feature tracking, not semantic body/material proof, native raster measurement, or stage acceptance. FIT/CHECK roles unchanged; failures remain unavailable.",
              "anchors": anchors, "frames": frames, "trackingFailures": backward_failures + forward_failures,
              "unsupportedViews": ["endcard-analysis-pen-inset", "endcard-guide"],
              "summary": {"anchors": len(anchors), "sourceFrames": len(frames), "sourceSeedPoints": len(landmarks),
                          "trackedObservations": sum(len(frame["landmarks"]) for frame in frames),
                          "independentCheckObservations": sum(point["role"] == "check" for frame in frames for point in frame["landmarks"]),
                          "unavailableObservations": sum(len(frame["unavailable"]) for frame in frames)}}
    return packet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-diagnostic", action="store_true", required=True)
    parser.add_argument("--reference-root", type=Path, default=Path(os.environ.get("HARMONIC_REFERENCE_ROOT", WEB / ".vite" / "reference-root")))
    parser.add_argument("--output", type=Path, default=WEB / ".vite" / "verification-output" / "compact-track-refinement" / "spin-montage-source-controls.json")
    args = parser.parse_args()
    try:
        output = private_output(args.output)
    except ValueError as error:
        parser.error(str(error))
    packet = build_packet(args.reference_root, historical_diagnostic=args.historical_diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet, separators=(",", ":"), allow_nan=False) + "\n")
    print(json.dumps({"output": str(output), **packet["summary"]}))


if __name__ == "__main__":
    main()

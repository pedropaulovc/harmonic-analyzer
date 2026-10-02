#!/usr/bin/env python3
"""Regenerate Operation/Rocker playback candidates from tracked immutable inputs.

Run: python3 web/scripts/compact-operation-rocker.py
This reads authored numeric seeds/source metadata only: no model, solver,
optimizer, browser, private evidence directory, or acceptance run. Historical
report paths/digests remain provenance; source camera failures remain diagnostics.
None of these choices claim a measured error stage.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from collections import defaultdict
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("compact_source_common", Path(__file__).with_name("compact-source-common.py"))
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)
WEB = common.WEB


def input_record(path, role, raw=None):
    path = path.resolve()
    return {"path": str(path.relative_to(WEB.parent)), "role": role,
            "sha256": hashlib.sha256(path.read_bytes() if raw is None else raw).hexdigest(),
            "requiredForRegeneration": True}


def load_seeds(video_id):
    path = WEB / "content" / f"{video_id}.source-seeds.json"
    raw = path.read_bytes()
    return json.loads(raw), input_record(path, "immutable-authored-choices-and-source-evidence", raw)


def retain_generator_inputs(track, seeds, seed_input):
    track["evidence"]["generatorInputs"] = [
        input_record(WEB / "content" / f'{track["source"]["videoId"]}.observations.json',
                     "original-source-observations"),
        seed_input,
        input_record(Path(__file__), "generator"),
        input_record(Path(__file__).with_name("compact-source-common.py"), "shared-source-selector"),
        input_record(WEB / "src/bindings.ts", "native-anchor-motion-lineage"),
    ]
    track["evidence"]["historicalReportInputs"] = {
        "usage": "provenance-only", "requiredForRegeneration": False,
        "reports": copy.deepcopy(seeds["historicalReportInputs"]),
    }


def view_record(original, camera, state, evidence):
    result = {"id": original["id"], "rectSourcePixels": original["rectSourcePixels"],
              "presentation": original.get("presentation", "native"),
              "camera": common.compact_camera(camera), "input": common.compact_input(state),
              "provenance": common.chosen_provenance(evidence)}
    composite = common.compact_composite(original)
    warp = common.resolve_warp(original)
    if composite:
        result["composite"] = composite
    if warp:
        result["imagePlaneWarp"] = warp
    return result


def operation():
    data = common.load_observations("jfH-NbsmvD4")
    seeds, seed_input = load_seeds("jfH-NbsmvD4")
    index = seeds["sourceInputIndex"]
    states = seeds["chosenStates"]
    degrees = {record_id: {"unmappedObservedDegrees": items}
               for record_id, items in seeds["observedDegrees"].items()}
    canonical = defaultdict(list)
    for row in index["rows"]:
        if row["kind"] == "canonical":
            canonical[row["sourceFrameIndex"]].append(row)
    shots = {shot["id"]: shot for shot in data["shots"]}
    changes = {111.0, 112.0, 113.0, 114.0}
    for event in data.get("operations", []):
        changes.update(event.get("timeRangeSeconds", []))
        for name in ("sequence", "states"):
            for step in event.get(name, []):
                changes.update(step.get("seconds", []))
        for name in ("targets", "sourceFeatureMeasurements", "pairedMeasurements"):
            changes.update(point["timeSeconds"] for point in event.get(name, []) if "timeSeconds" in point)
    data["compactChangeTimesSeconds"] = sorted(changes)
    cameras = []
    source_by_frame = defaultdict(list)
    anchor_ids = {a["id"] for a in data["anchors"]}
    for family, fragment in seeds["fragments"].items():
        for anchor in fragment.get("anchors", []):
            if anchor["id"] not in anchor_ids:
                data["anchors"].append(copy.deepcopy(anchor))
                anchor_ids.add(anchor["id"])
        for frame in fragment.get("frames", []):
            source_by_frame[frame["sourceFrameIndex"]].append((family, frame))
            for fit in frame.get("fits", []) + frame.get("diagnosticFits", []):
                if common.compact_camera(fit.get("camera")):
                    cameras.append({"frame": frame["sourceFrameIndex"], "time": frame["timeSeconds"],
                                    "id": fit.get("viewId") or "main", "camera": fit["camera"],
                                    "family": family, "reference": f"{fragment['historicalPath']}/frame={frame['sourceFrameIndex']}"})
    # Source checks are authored image measurements, not camera.checkErrors
    # Frozen declarations preserve the original source reference before copying.
    controls = defaultdict(list)
    for exposure in seeds["sourceControls"]:
        for control in exposure["declarations"]:
            original = control["declaration"]
            controls[exposure["sourceFrameIndex"]].append(
                ({**control, "sourceImage": exposure["sourceImage"]}, original))
    actual_gaps = seeds["gapExposures"]
    # Original local-MP4 decode identities are frozen numeric inputs, not new
    # source observations. Rounded pre-cut events use the shared selector.
    for gap in actual_gaps:
        time = gap["decodedTimeSeconds"]
        shot = next(s for s in data["shots"] if s["startSeconds"] <= time < s["endSeconds"])
        if any(f.get("sourceFrameIndex") == gap["sourceFrameIndex"] and f["shotId"] == shot["id"] for f in data["frames"]):
            continue
        donor = min((f for f in data["frames"] if f["shotId"] == shot["id"]), key=lambda f: abs(f["timeSeconds"] - time))
        frame = copy.deepcopy(donor)
        frame.update({"timeSeconds": time, "decodedTimeSeconds": time, "sourceFrameIndex": gap["sourceFrameIndex"],
                      "sourceImage": gap["sourceImage"], "landmarks": [], "shotId": shot["id"],
                      "classification": shot["classification"]})
        frame.pop("unavailable", None)
        frame.pop("sourceSampleUnavailable", None)
        data["frames"].append(frame)
    requests = []
    for entry in seeds["captureRequests"]:
        request = entry["request"]
        if common.compact_camera(request.get("camera")):
            requests.append((entry["path"], request))
    corrected = seeds["correctedCaptures"]
    # Merge measurements and exact source cameras before sampling so useful
    # landmark/layout/camera keys are selected from actual source evidence.
    for frame in data["frames"]:
        number = frame.get("sourceFrameIndex")
        if not common.needs_machine(frame, data):
            continue
        originals = common.source_views(frame, data)
        by_id = {view["id"]: view for view in originals}
        source_entries = source_by_frame.get(number, [])
        for family, source_frame in source_entries:
            for source_view in source_frame.get("views", []):
                view = copy.deepcopy(source_view)
                if view["id"] == "presenter-whole" and view["rectSourcePixels"] == [0, 0, 1920, 1080]:
                    view["id"] = "main"
                by_id.setdefault(view["id"], view)
            if family == "CodexPresenter":
                regions = source_frame.get("sourceMeasurements", {}).get("sourceRegions", {})
                for fit in source_frame.get("fits", []):
                    ident = fit.get("viewId") or "main"
                    if ident == "presenter-whole":
                        ident = "main"
                    if ident not in by_id and ident.startswith("presenter-menu-"):
                        region = regions.get(ident.removeprefix("presenter-"))
                        if region and region.get("meanLuma", 0) > 0:
                            by_id[ident] = {"id": ident, "rectSourcePixels": region["rectSourcePixels"], "presentation": "native"}
            for fit in source_frame.get("fits", []) + source_frame.get("diagnosticFits", []):
                ident = fit.get("viewId") or "main"
                if family == "CodexPresenter" and ident == "presenter-whole":
                    ident = "main"
                view = by_id.get(ident)
                if view and fit.get("camera"):
                    view["camera"] = fit["camera"]
                    view["cameraContinuityFamily"] = f"{frame['shotId']}:{family}:{ident}"
                    view["cameraProvenance"] = {"kind": "source-transfer", "family": view["cameraContinuityFamily"],
                                                "evidence": f"operation-numeric-cache/{family}.json frame{number}, retained source FIT/registered camera family. Original target residuals are diagnostics; a reused/derived camera is not asserted to be independently fitted at each exposure."}
        if "main" in by_id and "presenter-whole" in by_id and by_id["main"]["rectSourcePixels"] == by_id["presenter-whole"]["rectSourcePixels"]:
            by_id.pop("presenter-whole")
        observed = {(p.get("viewId") or "main", p["anchorId"], tuple(p.get("pixel") or [])) for p in frame.get("landmarks", [])}
        for control, declaration in controls.get(number, []):
            ident = control.get("viewId") or "main"
            if control["fragment"] == "CodexPresenter" and ident == "presenter-whole":
                ident = "main"
            if ident not in by_id:
                continue
            point = {k: copy.deepcopy(declaration[k]) for k in ("anchorId", "role", "pixel", "status", "method", "uncertaintyPx", "measurementEvidence", "trackingEvidence") if k in declaration}
            point["viewId"] = ident
            key = (ident, point["anchorId"], tuple(point["pixel"]))
            if key not in observed:
                frame.setdefault("landmarks", []).append(point)
                observed.add(key)
            frame["sourceImage"] = control["sourceImage"]
        frame["views"] = list(by_id.values())
    unsupported = defaultdict(set)
    assumed = defaultdict(set)
    held_cameras = {}
    def views(frame):
        if frame.get("sourceSampleUnavailable") or not common.needs_machine(frame, data):
            return []
        number = frame.get("sourceFrameIndex", frame.get("sourceImage", {}).get("frameIndex"))
        rows = canonical.get(number, [])
        if rows and not frame.get("sourceImage"):
            frame["sourceImage"] = rows[0]["sourceIdentity"].get("actualSourceImage")
        output = []
        for original in common.source_views(frame, data):
            ident = original["id"]
            row = next((r for r in rows if (r.get("viewId") or "main") == ident), None)
            if row is None and rows:
                row = min(rows, key=lambda r: sum(abs(a-b) for a, b in zip(r["rectSourcePixels"], original["rectSourcePixels"])))
            if row is None:
                # Actual newly decoded rows reuse a chosen same-shot complete
                # state; this is an input assumption, never a measured pose.
                pool = [r for r in index["rows"] if r["kind"] == "canonical" and r["shotId"] == frame["shotId"] and r["recordId"] in states]
                row = min(pool, key=lambda r: abs(r["timeSeconds"] - frame["timeSeconds"])) if pool else None
            state = copy.deepcopy(states.get(row["recordId"])) if row else None
            camera = original.get("camera") or frame.get("camera")
            family = original.get("cameraContinuityFamily", f"{frame['shotId']}:{ident}:source-fit")
            camera_provenance = original.get("cameraProvenance")
            evidence = "Saved complete chosen51 physical candidate; hidden controls remain unobserved."
            alias = "presenter-whole" if ident == "main" else ident
            matching = [(rel, r) for rel, r in requests if r["sourceImage"]["frameIndex"] == number and
                        (r.get("viewId") or r.get("recordId", "").split(":")[-1]) in (ident, alias)]
            if matching:
                rel, request = matching[-1]
                camera, state = request["camera"], copy.deepcopy(request.get("input", state))
                family = f"{frame['shotId']}:{rel}:{ident}"
                camera_provenance = {"kind": "source-transfer", "family": family, "evidence": f"{rel} chosen capture camera used for exact source frame{number}/{ident}; retained source-fit donor, not a new per-exposure camera fit"}
            if number == 8002 and ident in corrected:
                camera, state = corrected[ident]["view"]["camera"], copy.deepcopy(corrected[ident]["chosenInput"])
                family = f"{frame['shotId']}:corrected-native8002:{ident}"
                camera_provenance = {"kind": "source-transfer", "family": family, "evidence": "Corrected joint8002 retained source-camera authority transferred to this capture; numeric counter1.1863569024618958m, not a newly fitted camera"}
            if camera is None:
                cache_key = (frame["shotId"], ident)
                if cache_key not in held_cameras:
                    shot = shots[frame["shotId"]]
                    start, end = shot["startSeconds"], shot["endSeconds"]
                    # Fragment stems span multiple cuts. Only an actual fit time
                    # inside this shot can supply an own-shot camera donor.
                    own_shot = [c for c in cameras if start <= c["time"] < end]
                    pool = [c for c in own_shot if c["id"] in (ident, alias)]
                    kind = "source-transfer"
                    basis = "Same-shot matching-view source FIT donor held; target exposure has not been independently camera-fitted"
                    if not pool:
                        pool = own_shot
                        kind = "source-informed-framing"
                        basis = "Same-shot different-view source camera used as neutral framing, not an own-view fit"
                    if not pool:
                        # Retain a stable, honestly named neutral baseline where
                        # no own-shot source fit exists; never call it an own-fit.
                        pool = [c for c in cameras if c["family"] == "CodexPresenter" and c["id"] in ("main", "presenter-whole")]
                        basis = "Neutral presenter whole-camera source-informed framing baseline borrowed across a cut; no own-shot camera fit is available"
                    if not pool:
                        held_cameras[cache_key] = (None, "No retained source camera donor or neutral presenter baseline is available", "source-informed-framing")
                    else:
                        candidate = min(pool, key=lambda c: abs(c["time"] - start))
                        held = copy.deepcopy(candidate["camera"])
                        if held.get("principalPointViewportPixels"):
                            p = held["principalPointViewportPixels"]
                            held["principalPointViewportPixels"] = [p[0] * original["rectSourcePixels"][2] / 1920, p[1] * original["rectSourcePixels"][3] / 1080]
                        for key in ("status", "fitRmsPx", "fitMaxPx", "heldOutMaxPx"):
                            held.pop(key, None)
                        held_cameras[cache_key] = (held, f"{basis}; donor {candidate['reference']} at {candidate['time']:.6f}s. Viewport resizing is chosen, not refitted.", kind)
                camera, reference, kind = held_cameras[cache_key]
                family = f"{frame['shotId']}:{ident}:held-source-camera"
                camera_provenance = {"kind": kind, "family": family, "evidence": reference}
                assumed[frame["shotId"]].add(ident)
            if not camera_provenance:
                camera_provenance = {"kind": "source-transfer", "family": family, "evidence": f"Retained source-derived camera used at frame{number}/{ident}; source registration/held calibration is not an independent target-exposure camera fit. Original CPU diagnostics remain source evidence only."}
            if state and frame["shotId"] == "operation-024":
                # Actual source111 and114 expose the same downwards handle;114
                # overlays count1, and112 shows the arm up/right. Absolute phase
                # and speed between exposures remain chosen, not observed input.
                state["crankTurns"] = max(0.0, min(1.0, (frame["timeSeconds"] - 111.0) / 3.0))
                evidence += " Source-visible one-turn111..114s; chosen linear1/3turn/s and zero absolute-phase gauge, not recovered hidden winding."
            if row:
                for degree in degrees.get(row["recordId"], {}).get("unmappedObservedDegrees", []):
                    unsupported[frame["shotId"]].add(degree["degree"] + ": " + degree["reason"])
            result = view_record(original, camera, state, evidence)
            result["cameraProvenance"] = camera_provenance
            result["cameraContinuityFamily"] = family
            output.append(result)
        return output
    track = common.build_track(data, views, ["Original source controls transfer by exact exposure/view/anchor identity; projected checkErrors are never source measurements.",
                                           "Corrected8002 three-panel authority and whole physical chosen states retained. Source-visible crank111..114s advances one chosen revolution.",
                                           "Regeneration: python3 web/scripts/compact-operation-rocker.py; no stage or GPU acceptance claimed."])
    source_blockers = []
    for shot_id, items in sorted(unsupported.items()):
        shot = shots[shot_id]
        source_blockers.append(f"{shot_id} {shot['startSeconds']:.6f}..{shot['endSeconds']:.6f}s unsupported native geometry/motion: " + " | ".join(sorted(items)))
    for shot_id, identities in sorted(assumed.items()):
        shot = shots[shot_id]
        source_blockers.append(f"{shot_id} {shot['startSeconds']:.6f}..{shot['endSeconds']:.6f}s chosen held camera requires source registration for views " + ",".join(sorted(identities)))
    source_blockers.append("operation-024111..114s: source establishes one visible turn; absolute crank phase and intermediate speed are chosen. Other hand-driven phase/yaw/disassembly inputs remain partially measured, never static-exempt.")
    track["sourceMeasurements"]["status"] = "partial"
    track["sourceMeasurements"]["blockers"].extend(source_blockers)
    for frame in track["frames"]:
        if frame["views"] and all(v["camera"] and v["input"] for v in frame["views"]):
            frame.pop("unavailable", None)
    retain_generator_inputs(track, seeds, seed_input)
    return track


def rocker():
    data = common.load_observations("4mBuyixt22U")
    seeds, seed_input = load_seeds("4mBuyixt22U")
    states = seeds["states"]
    by_frame = {row["nativeFrame"]: row for row in states}
    body_candidate = seeds["bodyCandidate"]
    # The1078 states supply the complete source-informed bank. Shared selection
    # condenses continuous exposures to seconds, cuts, fades and useful motion
    # keys; the original exposure census is diagnostic, not mandatory new cuts.

    def views(frame):
        if frame.get("sourceSampleUnavailable") or not common.needs_machine(frame, data):
            return []
        number = frame.get("nativeFrame", frame.get("sourceImage", {}).get("frameIndex"))
        row = by_frame.get(number)
        if row is None:
            row = min(states, key=lambda r: abs(r["timeSeconds"] - frame.get("retainedObservationTimeSeconds", frame["timeSeconds"])))
        frame.setdefault("sourceImage", copy.deepcopy(row["sourceImage"]))
        result = []
        for original in common.source_views(frame, data):
            notes = ("Saved CPU-feasible continuous independently actuated held-bank branch; actual source phases/station order, not ideal cosine or historical recovery.")
            view = view_record(original, body_candidate["camera"], row["completeInput"], notes)
            view["cameraContinuityFamily"] = "rocker-centered-body-profile"
            view["cameraProvenance"] = {"kind": "source-transfer", "family": "rocker-centered-body-profile",
                                        "evidence": "Single recovered-runnable/full-profile-fit.json results2 centered body-aware source camera held across all Rocker exposures/overlays; no per-exposure fit. Original cap/rim CPU strict2% failures retained, current stages unmeasured."}
            result.append(view)
        return result

    track = common.build_track(data, views, [
        "All1078 original physical samples inform the tested complete51 bank; shared compact selection retains every second, source cut/layout/fade change and useful measured motion keys. Source PTS, measured landmarks and source image hashes are copied.",
        "Centered body-aware retained camera results2 replaces the cap-compatible extreme-principal branch; capCHECK43.445px/rimCHECK38.809px remain historical CPU diagnostics, not current stage results.",
        "Continuous chosen held-bank branch was numerically feasible in the retained index; no new CPU/model/GPU execution or historical recovery claim.",
        "Regeneration: python3 web/scripts/compact-operation-rocker.py; stages50/20/10/5 are image-width errors and remain unmeasured."])
    track["sourceMeasurements"]["status"] = "partial"
    track["sourceMeasurements"]["blockers"].extend([
        "0..1015.681333s: complete native exterior/shank/side-recess correspondence and independently actuated held-bank cone visibility remain unqualified; no whole-body exemption.",
        "Centered body-aware camera preserves actual source cap/rim constraints but has not passed current native whole-body source measurement."])
    for frame in track["frames"]:
        if frame["views"]:
            frame.pop("unavailable", None)
    retain_generator_inputs(track, seeds, seed_input)
    return track


if __name__ == "__main__":
    for generate in (operation, rocker):
        track = generate()
        path = common.write_track(track)
        print(f"{path.relative_to(WEB)}: {len(track['shots'])} shots, {len(track['frames'])} samples, {path.stat().st_size} bytes; stages unmeasured")

#!/usr/bin/env python3
"""Regenerate current Operation/Rocker candidates from explicit v39 associations.

Run the current-choice adoption producer before this compact-track generator.
Original source controls, exact decoded exposures and historical receipts remain
separate from current native associations. Numeric inputs and cameras are chosen,
unobserved current candidates, not transferred old-model feasibility or FIT/GPU
support. Missing correspondence and every original source loss remain required.
Neither generator measures an image-error stage.
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
    path = common.CURRENT_CONTENT / f"{video_id}.source-seeds.json"
    raw = path.read_bytes()
    return json.loads(raw), input_record(path, "current-chosen-input-camera-associations", raw)


def require_current_choices(data, seeds):
    if seeds.get("model") != data["model"] or seeds.get("sourceSha256") != data["source"]["sha256"]:
        raise ValueError("Current choices must bind the exact current native model and original source.")
    path = common.CURRENT_CONTENT / f'{data["source"]["videoId"]}.native-association-catalog.json'
    catalogue = json.loads(path.read_text())
    if catalogue.get("model") != data["model"]:
        raise ValueError("Current native catalogue belongs to a different model.")
    associations = {row["anchor"]["id"]: row for row in catalogue["associations"]}
    if len(associations) != len(catalogue["associations"]) or set(associations) != {a["id"] for a in data["anchors"]}:
        raise ValueError("The complete original source catalogue must survive current native association.")
    for anchor in data["anchors"]:
        mapped = associations[anchor["id"]]
        expected = mapped["anchor"]
        for key in ("partPath", "partLocalMetres", "worldMetres"):
            if anchor.get(key) != expected.get(key):
                raise ValueError(f"Current native feature disagrees with its raw proof: {anchor['id']}/{key}")
        if mapped["status"] == "unavailable" and anchor.get("nativeAssociation", {}).get("status") != "unavailable":
            raise ValueError(f"Unavailable native feature was silently qualified: {anchor['id']}")


def current_camera(camera):
    """Retain numeric framing only; old fit residuals/status stay historical."""
    compact = common.compact_camera(camera)
    if compact:
        for key in ("fitRmsPx", "fitMaxPx", "heldOutMaxPx", "status"):
            compact.pop(key, None)
    return compact


def chosen_camera_provenance(family, evidence):
    return {"kind": "source-informed-framing", "family": family,
            "evidence": f"{evidence}. Explicitly chosen unobserved v39 framing; no old-model FIT, CPU, bank, first-surface or GPU support transfers."}


def retain_generator_inputs(track, seeds, seed_input):
    track["evidence"]["generatorInputs"] = [
        input_record(common.CURRENT_CONTENT / f'{track["source"]["videoId"]}.observations.json',
                     "current-observations-original-source-facts"),
        seed_input,
        input_record(Path(__file__), "generator"),
        input_record(Path(__file__).with_name("compact-source-common.py"), "shared-source-selector"),
        input_record(Path(__file__).with_name("adopt-operation-rocker-choices.py"), "current-choice-producer"),
        input_record(Path(__file__).with_name("native-source-association.py"), "raw-native-feature-association"),
        input_record(common.CURRENT_CONTENT / f'{track["source"]["videoId"]}.native-association-catalog.json',
                     "complete-source-catalogue-current-native-associations"),
        input_record(WEB / "src/bindings.ts", "native-anchor-motion-lineage"),
    ]
    track["evidence"]["historicalReportInputs"] = {
        "usage": "provenance-only", "requiredForRegeneration": False,
        "reports": copy.deepcopy(seeds["historicalReportInputs"]),
    }
    track["evidence"]["currentChoiceAdoption"] = copy.deepcopy(seeds["currentChoiceAdoption"])


def view_record(original, camera, state, evidence):
    result = {"id": original["id"], "rectSourcePixels": original["rectSourcePixels"],
              "presentation": original.get("presentation", "native"),
              "camera": current_camera(camera), "input": common.compact_input(state),
              "provenance": common.chosen_provenance(evidence)}
    composite = common.compact_composite(original)
    warp = common.resolve_warp(original)
    if composite:
        result["composite"] = composite
        result["compositeProvenance"] = copy.deepcopy(original.get("compositeProvenance") or {
            "kind": "chosen-unmeasured",
            "evidence": "Original composite topology remains a source obligation. Retained numeric opacity is an unmeasured presentation candidate, not source alpha or current native/GPU qualification.",
        })
    if warp:
        result["imagePlaneWarp"] = warp
    return result


def exposure_number(frame):
    for field in ("sourceFrameIndex", "nativeFrame", "decodedFrameIndex"):
        number = frame.get(field)
        if type(number) is int:
            return number
    return (frame.get("sourceImage") or {}).get("frameIndex")


def capture_request(frame, ident, requests):
    """Bind new capture authorities to the exact exposure, not a frame alias."""
    number = exposure_number(frame)
    alias = "presenter-whole" if ident == "main" else ident
    matching = [(rel, request) for rel, request in requests
                if request["sourceImage"]["frameIndex"] == number
                and (request.get("viewId") or request.get("recordId", "").split(":")[-1]) in (ident, alias)
                and request["sourceImage"] == frame.get("sourceImage")
                and ("decodedTimeSeconds" not in request
                     or (request["decodedTimeSeconds"] == frame.get("decodedTimeSeconds")
                         and request["sourceImage"] == frame.get("sourceImage")))]
    return matching[-1] if matching else None


def require_catalogued_landmarks(data):
    """Source observations must resolve before selection can discard anything.

    Unavailable records are intentionally not resolved here: their unknown
    identities remain required missing source data, not invented CAD anchors.
    """
    anchor_ids = {anchor["id"] for anchor in data["anchors"]}
    for frame in data["frames"]:
        for point in frame.get("landmarks", []):
            if point.get("anchorId") not in anchor_ids:
                raise ValueError(
                    f"Unresolved physical-source anchor at {frame['timeSeconds']}s/"
                    f"{point.get('viewId') or 'main'}: {point.get('anchorId')}")


def operation():
    data = common.load_observations("jfH-NbsmvD4")
    require_catalogued_landmarks(data)
    seeds, seed_input = load_seeds("jfH-NbsmvD4")
    require_current_choices(data, seeds)
    anchor_ids = {anchor["id"] for anchor in data["anchors"]}
    for exposure in seeds["sourceControls"]:
        for control in exposure["declarations"]:
            if control.get("usage") != "provenance-only" and control["declaration"]["anchorId"] not in anchor_ids:
                raise ValueError(
                    f"Unresolved physical-source control at frame{exposure['sourceFrameIndex']}/"
                    f"{control.get('viewId') or 'main'}: {control['declaration']['anchorId']}")
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
    baseline = seeds["baselineChoice"]
    authored_cameras = defaultdict(list)
    for choice in seeds["authoredCameraChoices"]:
        authored_cameras[choice["sourceFrameIndex"]].append(choice)
    source_by_frame = defaultdict(list)
    for family, fragment in seeds["fragments"].items():
        for frame in fragment.get("frames", []):
            source_by_frame[frame["sourceFrameIndex"]].append((family, frame))
    # Source checks are authored image measurements, not camera.checkErrors
    # Frozen declarations preserve the original source reference before copying.
    controls = defaultdict(list)
    for exposure in seeds["sourceControls"]:
        for control in exposure["declarations"]:
            if control.get("usage") == "provenance-only":
                continue
            original = control["declaration"]
            controls[exposure["sourceFrameIndex"]].append(
                ({**control, "sourceImage": exposure["sourceImage"]}, original))
    actual_gaps = seeds["gapExposures"]
    # Original local-MP4 decode identities are frozen source facts. Required
    # layouts/losses come only from the same original exposure, never a donor.
    for gap in actual_gaps:
        time = gap["decodedTimeSeconds"]
        shot = next(s for s in data["shots"] if s["startSeconds"] <= time < s["endSeconds"])
        if any(exposure_number(f) == gap["sourceFrameIndex"] and f["shotId"] == shot["id"] for f in data["frames"]):
            continue
        frame = {"timeSeconds": time, "decodedTimeSeconds": time,
                 "sourceFrameIndex": gap["sourceFrameIndex"], "sourceImage": copy.deepcopy(gap["sourceImage"]),
                 "landmarks": [], "shotId": shot["id"], "classification": shot["classification"],
                 "views": copy.deepcopy(gap["views"])}
        if gap.get("unavailable"):
            frame["unavailable"] = copy.deepcopy(gap["unavailable"])
        data["frames"].append(frame)
    requests = []
    for entry in seeds["captureRequests"]:
        request = entry["request"]
        if common.compact_camera(request.get("camera")):
            requests.append((entry["path"], request))
    corrected = seeds["correctedCaptures"]
    # Merge exact-exposure source controls/layouts and chosen numeric framing
    # before selection; none of these cameras carries current FIT support.
    for frame in data["frames"]:
        number = exposure_number(frame)
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
                for fit in source_frame.get("cameraChoices", []):
                    ident = fit.get("viewId") or "main"
                    if ident == "presenter-whole":
                        ident = "main"
                    if ident not in by_id and ident.startswith("presenter-menu-"):
                        region = regions.get(ident.removeprefix("presenter-"))
                        if region and region.get("meanLuma", 0) > 0:
                            by_id[ident] = {"id": ident, "rectSourcePixels": region["rectSourcePixels"], "presentation": "native"}
            for fit in source_frame.get("cameraChoices", []):
                ident = fit.get("viewId") or "main"
                if family == "CodexPresenter" and ident == "presenter-whole":
                    ident = "main"
                view = by_id.get(ident)
                if view and fit.get("camera"):
                    view["camera"] = current_camera(fit["camera"])
                    view["cameraContinuityFamily"] = f"{frame['shotId']}:{family}:{ident}:chosen-v39"
                    view["cameraProvenance"] = chosen_camera_provenance(
                        view["cameraContinuityFamily"], f"Exact original exposure frame{number}/{ident} numeric framing candidate from historical {family}")
        if "main" in by_id and "presenter-whole" in by_id and by_id["main"]["rectSourcePixels"] == by_id["presenter-whole"]["rectSourcePixels"]:
            by_id.pop("presenter-whole")
        observed = {(p.get("viewId") or "main", p["anchorId"], tuple(p.get("pixel") or [])) for p in frame.get("landmarks", [])}
        for control, declaration in controls.get(number, []):
            ident = control.get("viewId") or "main"
            if control["fragment"] == "CodexPresenter" and ident == "presenter-whole":
                ident = "main"
            if ident not in by_id:
                loss = {"anchorId": declaration["anchorId"], "viewId": ident,
                        "role": declaration.get("role"), "sourcePixels": copy.deepcopy(declaration.get("pixel")),
                        "sourceImage": copy.deepcopy(control["sourceImage"]),
                        "sourceControlReference": control.get("reference"),
                        **{key: copy.deepcopy(declaration[key]) for key in
                           ("method", "uncertaintyPx", "measurementEvidence", "trackingEvidence") if key in declaration},
                        "reason": "Original required source control has no declared exact-exposure view layout; correspondence remains unavailable.",
                        "required": True}
                if loss not in frame.setdefault("unavailable", []):
                    frame["unavailable"].append(loss)
                continue
            point = {k: copy.deepcopy(declaration[k]) for k in ("anchorId", "role", "pixel", "status", "method", "uncertaintyPx", "measurementEvidence", "trackingEvidence") if k in declaration}
            point["viewId"] = ident
            key = (ident, point["anchorId"], tuple(point["pixel"]))
            if key not in observed:
                frame.setdefault("landmarks", []).append(point)
                observed.add(key)
            if frame.get("sourceImage") is not None and frame["sourceImage"] != control["sourceImage"]:
                raise ValueError(f"Conflicting original source exposure identity at frame{number}/{ident}")
            frame["sourceImage"] = copy.deepcopy(control["sourceImage"])
        frame["views"] = list(by_id.values())
    require_catalogued_landmarks(data)
    unsupported = defaultdict(set)
    assumed = defaultdict(set)
    def views(frame):
        if frame.get("sourceSampleUnavailable") or not common.needs_machine(frame, data):
            return []
        number = exposure_number(frame)
        rows = canonical.get(number, [])
        if rows and not frame.get("sourceImage"):
            frame["sourceImage"] = rows[0]["sourceIdentity"].get("actualSourceImage")
        output = []
        for original in common.source_views(frame, data):
            ident = original["id"]
            row = next((r for r in rows if (r.get("viewId") or "main") == ident), None)
            state = copy.deepcopy(states.get(row["recordId"])) if row else copy.deepcopy(baseline["input"])
            input_missing = row is None or state is None
            camera = current_camera(original.get("camera") or frame.get("camera"))
            if camera is None:
                layout = {key: original[key] for key in
                          ("id", "rectSourcePixels", "presentation", "imagePlaneWarp", "composite") if key in original}
                warp = common.resolve_warp(original)
                if warp:
                    layout["imagePlaneWarp"] = warp
                candidates = [choice for choice in authored_cameras.get(number, [])
                              if choice["decodedTimeSeconds"] == frame["decodedTimeSeconds"]
                              and choice["layout"] == layout
                              and (choice["sourceImage"] is None or choice["sourceImage"] == frame.get("sourceImage"))]
                if candidates:
                    camera = candidates[0]["camera"]
            family = original.get("cameraContinuityFamily", f"{frame['shotId']}:{ident}:chosen-v39")
            camera_provenance = chosen_camera_provenance(
                family, f"Retained numeric candidate for original exposure frame{number}/{ident}")
            evidence = "Chosen current 51-field candidate after station/setup native ownership checks; all historical input coordinates remain unobserved, and v39 feasibility remains unmeasured."
            selected_capture = capture_request(frame, ident, requests)
            if selected_capture:
                rel, request = selected_capture
                camera, state = current_camera(request["camera"]), copy.deepcopy(request.get("input") or state)
                family = f"{frame['shotId']}:{rel}:{ident}:chosen-v39"
                camera_provenance = chosen_camera_provenance(
                    family, f"Exact original exposure frame{number}/{ident} capture-request numeric candidate; historical path {rel} is provenance only")
            if number == 8002 and ident in corrected:
                camera, state = current_camera(corrected[ident]["view"]["camera"]), copy.deepcopy(corrected[ident]["chosenInput"])
                family = f"{frame['shotId']}:chosen8002:{ident}:v39"
                camera_provenance = chosen_camera_provenance(family, "Exact frame8002 three-panel numeric candidate, including the retained counter-height choice")
            if state is None:
                state = copy.deepcopy(baseline["input"])
            if camera is None:
                camera = baseline["camera"]
                family = f"{frame['shotId']}:{ident}:explicit-unobserved-baseline-v39"
                camera_provenance = chosen_camera_provenance(
                    family, "Explicit current whole-machine baseline; no adjacent-frame, different-view or cross-cut camera donor")
                assumed[frame["shotId"]].add(ident)
            if input_missing:
                evidence += " No exact complete authored input candidate exists; the explicit current baseline or exact capture-request candidate is used, not a neighboring source-frame state."
                loss = {"viewId": ident, "sourceInputRecordId": row["recordId"] if row else None,
                        "status": "unobserved-input", "required": True,
                        "reason": "Exact original authored complete input choice is unavailable; chosen current playback does not recover source machine inputs."}
                if loss not in frame.setdefault("unavailable", []):
                    frame["unavailable"].append(loss)
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
    track = common.build_track(data, views, ["Original source controls retain exact exposure/view/anchor identity and frozen conflict-first-wins provenance; projected checkErrors are never source measurements.",
                                           "Current native associations are raw-proved independently. Frame8002 numeric panel choices and source-visible crank111..114s remain unobserved chosen candidates, not old calibration transfers.",
                                           "Regeneration: python3 web/scripts/adopt-operation-rocker-choices.py && python3 web/scripts/compact-operation-rocker.py; no stage or GPU acceptance claimed."])
    source_blockers = []
    for shot_id, items in sorted(unsupported.items()):
        shot = shots[shot_id]
        source_blockers.append(f"{shot_id} {shot['startSeconds']:.6f}..{shot['endSeconds']:.6f}s unsupported native geometry/motion: " + " | ".join(sorted(items)))
    for shot_id, identities in sorted(assumed.items()):
        shot = shots[shot_id]
        source_blockers.append(f"{shot_id} {shot['startSeconds']:.6f}..{shot['endSeconds']:.6f}s explicit unobserved baseline framing requires fresh source registration for views " + ",".join(sorted(identities)))
    source_blockers.append("operation-024111..114s: source establishes one visible turn; absolute crank phase and intermediate speed are chosen. Other hand-driven phase/yaw/disassembly inputs remain partially measured, never static-exempt.")
    track["sourceMeasurements"]["status"] = "partial"
    track["sourceMeasurements"]["blockers"].extend(source_blockers)
    refinement = seeds.get("operation019SourceRefinement")
    if refinement:
        track["evidence"]["operation019SourceRefinement"] = copy.deepcopy(refinement)
        track["sourceMeasurements"]["blockers"].append(refinement["qualification"])
    retain_generator_inputs(track, seeds, seed_input)
    return track


def rocker():
    data = common.load_observations("4mBuyixt22U")
    seeds, seed_input = load_seeds("4mBuyixt22U")
    require_current_choices(data, seeds)
    states = seeds["states"]
    fps = data["source"]["fps"]["numerator"] / data["source"]["fps"]["denominator"]
    by_frame = {row["nativeFrame"]: row for row in states}
    camera_choice = seeds["cameraChoice"]
    baseline = seeds["baselineChoice"]
    # The1078 states supply the complete source-informed bank. Shared selection
    # condenses continuous exposures to seconds, cuts, fades and useful motion
    # keys; the original exposure census is diagnostic, not mandatory new cuts.

    def views(frame):
        if frame.get("sourceSampleUnavailable") or not common.needs_machine(frame, data):
            return []
        number = exposure_number(frame)
        row = by_frame.get(number)
        # Seed timeSeconds is an authored observation label, not decoded PTS.
        # Selector aliases retain the decoded exposure even when their playback
        # time changes; only that exact frame may supply missing source pixels.
        if ("sourceImage" not in frame and row is not None
                and row["sourceImage"]["frameIndex"] == number
                and row["sourceImage"]["sourceSha256"] == data["source"]["sha256"]
                and frame.get("decodedFrameIndex", number) == number
                and round(frame["decodedTimeSeconds"] * fps) == number):
            frame["sourceImage"] = copy.deepcopy(row["sourceImage"])
        if row is None:
            row = {"completeInput": baseline["input"]}
        result = []
        for original in common.source_views(frame, data):
            notes = ("Explicitly chosen current independently actuated held-bank input after station/setup ownership checks; fixed-contact scenario and all hidden coordinates remain unobserved. Old native435 CPU bank feasibility does not transfer.")
            view = view_record(original, camera_choice["camera"], row["completeInput"], notes)
            view["cameraContinuityFamily"] = camera_choice["cameraContinuityFamily"]
            view["cameraProvenance"] = copy.deepcopy(camera_choice["cameraProvenance"])
            result.append(view)
        return result

    track = common.build_track(data, views, [
        "All1078 original authored states remain complete 51-field current input choices, not 51 replay states. Original exposure identities, measured source landmarks, FIT/CHECK roles and source image hashes remain exact.",
        "The old fixed-contact held-bank branch and camera are historical lineage only. Numeric current candidates have station/setup ownership proof, not inherited CPU closure, cap/rim fitting, bank feasibility, first-surface, material, GPU or source-stage support.",
        "Every missing exterior/shank/recess correspondence remains required. No neighboring source-frame state is borrowed when an exact input row is absent.",
        "Regeneration: python3 web/scripts/adopt-operation-rocker-choices.py && python3 web/scripts/compact-operation-rocker.py; stages50/20/10/5 remain unmeasured."])
    track["sourceMeasurements"]["status"] = "partial"
    track["sourceMeasurements"]["blockers"].extend([
        "0..1015.681333s: complete native exterior/shank/side-recess correspondence and independently actuated held-bank cone visibility remain unqualified; no whole-body exemption.",
        camera_choice["qualification"]])
    track["evidence"]["rockerCameraChoice"] = copy.deepcopy(camera_choice)
    track["evidence"]["rockerFixedContactScenarios"] = copy.deepcopy(seeds["fixedContactScenarios"])
    # Complete chosen playback inputs do not resolve the source's missing
    # exterior/material associations. Keep every selected source loss/null row.
    retain_generator_inputs(track, seeds, seed_input)
    return track


if __name__ == "__main__":
    prepared = [(track, *common.prepare_track(track)) for track in (operation(), rocker())]
    for track, path, contents in prepared:
        path.write_text(contents)
        print(f"{path.relative_to(WEB)}: {len(track['shots'])} shots, {len(track['frames'])} samples, {path.stat().st_size} bytes; stages unmeasured")

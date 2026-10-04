#!/usr/bin/env python3
"""Fit a private CURRENT462 world export with the existing camera-only fitter.

Root-only execution, after current-native-source-fit.mjs exported an independently
pinned original CPU pose. No inventory/census is invented and no canonical source
track is written. This invokes fit-source.py::fit_camera directly: original FITs
select its camera candidate; >=2 original CHECKs are scored only afterward.

python web/scripts/current-native-source-fit.py PRIVATE_PACKET
  --packet-sha256 BYTE_PIN --closure-sha256 INDEPENDENT_ORIGINAL_CPU_PIN
  --output web/.vite/verification-output/NEW_CANDIDATE.json

Exit 0: CPU camera candidate diagnostics pass only. Exit 2: explicit prerequisites
missing/refused. Exit 1: candidate residual/depth failure or malformed/pin-mismatched
packet. Lens recovery, physical-input recovery, current raster/GPU/body/first-surface,
image-plane warps, stages, and source/video acceptance are never claimed here.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("existing_source_camera_fitter", _SCRIPT / "fit-source.py")
_fitter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fitter)
RAW_SHA256 = "60a62a2edcd15012114d0234438ba54e24be5179f23751ac337cd6df205c562c"
DELIVERY_SHA256 = "81750ae4c422b973dfd647df4e22f3088933003e39ff41c54563d780eb33fa65"


def _sha(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label}: independent SHA256 required")
    return value


def _view(frame, view_id):
    if frame.get("views"):
        matches = [v for v in frame["views"] if v["id"] == view_id]
        if len(matches) != 1:
            raise ValueError("Exact original source view is missing or ambiguous")
        return matches[0]
    if view_id != "main":
        raise ValueError("Unpartitioned original source has only main view")
    return frame


def fit_current_native_packet(packet, closure_sha256):
    """Consume the pinned private export; recompute support policy from original
    observations/rows, never trust the producer's ready/count/acceptance flags."""
    _sha(closure_sha256, "Original CPU closure")
    if packet.get("schemaVersion") != 1 or packet.get("kind") != "current-native-source-camera-fit-packet":
        raise ValueError("Unsupported current-native world packet")
    model = packet["model"]
    if model.get("rawSHA256") != RAW_SHA256 or model.get("deliverySHA256") != DELIVERY_SHA256 or model.get("originalCPUClosureSHA256") != closure_sha256:
        raise ValueError("Current raw/delivery or independently pinned original CPU closure mismatch")
    for field in ("originalObservationsSHA256", "authoredFrameSHA256", "selectionSHA256", "decodedFrameSHA256"):
        _sha(packet["provenance"].get(field), field)
    original = packet["original"]
    source, frame = original["source"], original["frame"]
    binding = packet["sourceBinding"]
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
               for value in (frame.get("timeSeconds"), frame.get("decodedTimeSeconds"))):
        raise ValueError("Finite numeric original source clocks required")
    decoded_clock = binding.get("decodedTimeSeconds")
    if not (isinstance(decoded_clock, (int, float)) and not isinstance(decoded_clock, bool) and math.isfinite(decoded_clock)):
        raise ValueError("Finite numeric independent decoded clock required")
    image = frame["sourceImage"]
    _fitter.source_image_key(image, source, "Original source")
    if (binding.get("sourceImage") != image or binding.get("sourceSha256") != source["sha256"]
            or binding.get("videoId") != source["videoId"] or binding.get("frameIndex") != image["frameIndex"]
            or binding.get("timeSeconds") != frame["timeSeconds"] or binding.get("shotId") != frame["shotId"]):
        raise ValueError("World export changed original source exposure identity")
    time_base = binding.get("timeBase", "").split("/")
    if len(time_base) != 2 or any(not p.isdigit() or int(p) <= 0 for p in time_base):
        raise ValueError("Independent original PTS/time-base required")
    ticks = binding.get("decodedTimestampTicks")
    if isinstance(ticks, bool) or not isinstance(ticks, int):
        raise ValueError("Independent integer original PTS required")
    pts = ticks * int(time_base[0]) / int(time_base[1])
    if (not math.isfinite(pts) or abs(pts - binding["decodedTimeSeconds"]) > 1e-9
            or binding.get("recordedOriginalDecodedTimeSeconds") != frame["decodedTimeSeconds"]
            or abs(frame["decodedTimeSeconds"] - pts) > 0.5 or abs(frame["timeSeconds"] - pts) > 0.5):
        raise ValueError("Independent original PTS/source clock mismatch")
    view = _view(frame, binding["originalViewId"])
    rect = view["rectSourcePixels"] if frame.get("views") else [0, 0, source["width"], source["height"]]
    rect = _fitter.finite_vector(rect, 4, "Original viewport").tolist()
    x, y, width, height = rect
    if min(x, y) < 0 or min(width, height) <= 0 or x + width > source["width"] or y + height > source["height"]:
        raise ValueError("Original viewport is outside original source image")
    presentation = view.get("presentation", frame.get("presentation", "native"))
    if presentation not in ("native", "horizontal-mirror"):
        raise ValueError("Unsupported original source presentation")
    authored = packet["authored"]
    selection = authored["inputSelection"]
    if selection.get("state") not in ("chosen-unmeasured", "independently-measured") or selection.get("field") not in ("input", "chosenInput", "mechanicalState.input", "mechanicalState.chosenInput"):
        raise ValueError("Explicit unchanged input selection state required")
    if selection["field"].endswith("chosenInput") and selection["state"] != "chosen-unmeasured":
        raise ValueError("chosenInput cannot become independent source truth")
    if not isinstance(selection.get("evidence"), str) or not selection["evidence"].strip() or not isinstance(selection.get("ambiguities"), list):
        raise ValueError("Input evidence and ambiguity ledger required")
    _fitter.validate_input(authored["input"], "Exact authored current input")
    authored_frame = authored["frame"]
    if authored_frame["sourceImage"] != image or authored_frame["timeSeconds"] != frame["timeSeconds"] or authored_frame["shotId"] != frame["shotId"]:
        raise ValueError("Authored frame no longer binds exact original exposure")
    authored_views = [v for v in authored_frame.get("views", []) if v.get("originalViewId", v["id"]) == binding["originalViewId"]]
    if authored_frame.get("views") and len(authored_views) != 1:
        raise ValueError("Exact authored input viewport is ambiguous")
    authored_view = authored_views[0] if authored_views else authored_frame
    authored_provenance = authored_view.get("provenance", {})
    if (authored_provenance.get("kind") == "chosen-feasible" or authored_provenance.get("unobservedInputFields")) and selection["state"] != "chosen-unmeasured":
        raise ValueError("Authored unobserved input cannot become independent source truth")
    authored_input = (authored_view.get("mechanicalState", {}).get(selection["field"].removeprefix("mechanicalState."))
                      if selection["field"].startswith("mechanicalState.") else authored_view.get(selection["field"]))
    if authored_input != authored["input"]:
        raise ValueError("World export changed exact authored input")
    if authored_view.get("partOverrides", authored_frame.get("partOverrides", [])) != authored["partOverrides"]:
        raise ValueError("World export changed exact authored whole-part overrides")
    originals = {l["anchorId"]: l for l in frame.get("landmarks", []) if l.get("viewId", "main") == binding["originalViewId"]}
    rows = packet["rows"]
    if len(rows) != len(originals) or len({r["originalLandmark"]["anchorId"] for r in rows}) != len(rows):
        raise ValueError("Original observations were omitted or duplicated in world export")
    points, landmarks, unavailable = {}, [], []
    unique_world = set()
    for row in rows:
        landmark = row["originalLandmark"]
        if landmark != originals.get(landmark["anchorId"]):
            raise ValueError("World export changed an original role/pixel/uncertainty/observation")
        if row["status"] != "world-exported":
            unavailable.append(copy.deepcopy(row))
            continue
        if landmark.get("status") != "observed" or landmark.get("role") not in ("fit", "check"):
            raise ValueError("Unavailable/non-point source facts cannot become camera controls")
        world = _fitter.finite_vector(row["worldMetres"], 3, landmark["anchorId"])
        key = tuple(world)
        if key in unique_world:
            raise ValueError("Coincident physical point cannot count as independent FIT/CHECK support")
        unique_world.add(key)
        points[landmark["anchorId"]] = world
        l = copy.deepcopy(landmark)
        pixel = _fitter.finite_vector(l["pixel"], 2, "Original landmark pixel")
        if not x <= pixel[0] < x + width or not y <= pixel[1] < y + height:
            raise ValueError("Original landmark is outside original source viewport")
        l["pixel"] = [float(pixel[0] - x), float(pixel[1] - y)]
        if presentation == "horizontal-mirror":
            l["pixel"][0] = width - 1 - l["pixel"][0]
        landmarks.append(l)
    reasons = []
    fit_count = sum(l["role"] == "fit" for l in landmarks)
    check_count = sum(l["role"] == "check" for l in landmarks)
    if fit_count < 6 or check_count < 2:
        reasons.append(f"Need >=6 distinct original FIT and >=2 held-out CHECK; exported {fit_count}/{check_count}")
    if any(owner.get(field) is not None for owner in (view, frame, authored_view, authored_frame)
           for field in ("imagePlaneWarp", "resolvedImagePlaneWarp")):
        reasons.append("Image-plane warp requires unchanged independent source corner/interior CHECK closure; camera-only routine refuses it")
    result = {"schemaVersion": 1, "kind": "current-native-source-camera-candidate", "sourceAcceptance": False,
              "nativeAcceptance": False, "gpuAcceptance": False, "sourceBinding": copy.deepcopy(binding),
              "model": copy.deepcopy(model), "provenance": copy.deepcopy(packet["provenance"]),
              "inputSelection": copy.deepcopy(selection), "distinctFitCount": fit_count, "distinctCheckCount": check_count,
              "unavailable": unavailable, "limitations": copy.deepcopy(packet["limitations"]), "camera": None}
    if reasons:
        result.update(status="refused", reasons=reasons)
        return result
    # No whole-video validation and no second solver: existing FIT-only routine
    # is the sole camera optimizer; its geometry rank and positive-depth checks
    # remain intact. Original source-width threshold remains 38.4px at 1920px.
    candidate, error = _fitter.fit_camera({"landmarks": landmarks}, points, width, height,
                                        threshold_px=source["width"] * 0.02,
                                        camera_fit=packet["cameraInput"].get("cameraFit", {}))
    if error:
        result.update(status="refused", reasons=[error])
    else:
        result.update(status="candidate-passed" if candidate["status"] == "passed" else "candidate-failed",
                      reasons=[], camera=candidate)
    return result


def _private_output(path):
    root = (_SCRIPT.parent / ".vite" / "verification-output").resolve()
    output = path.resolve()
    if output == root or root not in output.parents:
        raise ValueError("Output must be new private web/.vite/verification-output file, never canonical source content")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--closure-sha256", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    _sha(args.packet_sha256, "Packet byte pin")
    data = args.packet.read_bytes()
    if hashlib.sha256(data).hexdigest() != args.packet_sha256:
        raise ValueError("Independently pinned private world packet bytes changed")
    result = fit_current_native_packet(json.loads(data), args.closure_sha256)
    if args.output:
        with _private_output(args.output).open("x") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    raise SystemExit(2 if result["status"] == "refused" else 0 if result["status"] == "candidate-passed" else 1)


if __name__ == "__main__":
    main()

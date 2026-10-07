#!/usr/bin/env python3
"""Prepare a nonpublishable historical Analysis diagnostic receipt.

Run with --historical-diagnostic. Source pixels/uncertainties are copied, never
projected or interpolated. This packet cannot amend current production tracks.
"""
import copy
import argparse
import importlib.util
import json
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
spec = importlib.util.spec_from_file_location("compact_source_common", WEB / "scripts/compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
BASE = WEB / "content/canonical-native/analysis-recovery-calibration-evidence"


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


def load(path):
    return json.loads(path.read_text())


def build_packet(*, historical_diagnostic=False):
    if historical_diagnostic is not True:
        raise ValueError("Analysis bank controls require historical_diagnostic=True")
    source = common.load_historical_observations("6dW6VYXp9HM")
    if (
        source.get("kind") == "current-source-observations"
        or source.get("freshSourceRecord") is not None
        or source.get("identityDerivative", {}).get("kind") != "materialized-canonical-native-identity-derivative"
        or source.get("model", {}).get("sha256") != "2280bfa641e33aea841b01b97daf0d2021f091da272ea55c06631a231e876b1d"
        or source.get("model", {}).get("sourceCommit") != "1268c23d4a8fc741147c5e09d8d1e45247a71945"
        or source.get("source", {}).get("videoId") != "6dW6VYXp9HM"
        or source.get("source", {}).get("sha256") != "5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52"
    ):
        raise ValueError("Analysis bank diagnostics require the original historical source/model tuple")
    candidate = load(BASE / "four-seed-source-fit-census/candidate.json")
    request = load(BASE / "four-seed-source-fit-census/all204-cpu-forward-request.json")
    centres = load(BASE / "fit-centres204.json")
    ledger = load(BASE / "augmented-face-frozen-check/interior-cap-check-ledger.json")
    report = load(BASE / "augmented-face-frozen-check/augmented-frozen-report.json")
    snapshots = {row["frameIndex"]: row for row in candidate["frames"]}
    request_anchors = {anchor["id"]: anchor for anchor in request["nativeLandmarkAnchors"]}
    anchors = {}
    rows = {}
    for centre_frame in centres["frames"]:
        index = centre_frame["frameIndex"]
        snapshot = snapshots[index]
        if snapshot["sourceFrameIdentity"]["sourceImage"] != centre_frame["sourceImage"]:
            raise ValueError(f"Source exposure mismatch at {index}")
        row = {"timeSeconds":centre_frame["timeSeconds"],"decodedTimeSeconds":centre_frame["timeSeconds"],
               "decodedFrameIndex":index,"sourceImage":centre_frame["sourceImage"],
               "shotId":next(shot["id"] for shot in source["shots"] if shot["startSeconds"] <= centre_frame["timeSeconds"] < shot["endSeconds"]),
               "classification":"machine","landmarks":[],"unavailable":[],
               "viewId":"bar-bank","presentation":"horizontal-mirror",
               "camera":common.compact_camera(candidate["nativeCameraRecord"]),
               "input":common.compact_input(snapshot["chosenInput"]),
               "inputProvenance":common.chosen_provenance("Latest frozen four-seed complete51 inverse witness. Source history unobserved; no new native/GPU qualification.")}
        for point in centre_frame["physicalFaceCentroids"]:
            anchor_id = f"station-{point['sourceStation']}-cap-centre"
            native = request_anchors[anchor_id]
            if native["partPath"] != point["nativePartPath"]:
                raise ValueError(f"Source/native station mismatch: {anchor_id}")
            anchors[anchor_id] = {"id":anchor_id,"kind":"physical-feature","partPath":native["partPath"],
                "partLocalMetres":native["partLocalMetres"],"motion":"moving",
                "description":"Rocker exposed cap centre; source chroma centroid is a FIT proxy, not an independently identified geometric vertex.",
                "correspondenceEvidence":"Immutable fit-centres204 physicalFaceCentroids and latest serialized native request. Source station1..20 maps native physical instance20..1; measured scalar uncertainty copied unchanged."}
            row["landmarks"].append({"anchorId":anchor_id,"viewId":"bar-bank","role":"fit",
                "pixel":point["pixel"],"status":"observed","method":"image-edge","uncertaintyPx":point["uncertaintyPx"],
                "measurementEvidence":{"sourceImage":copy.deepcopy(centre_frame["sourceImage"]),
                    "technique":"Source chroma-threshold segmentation and region centroid; FIT proxy, not geometric corner",
                    "originalMeasurement":copy.deepcopy(point),
                    "sourcePacket":".playwright-cli/analysis-recovery/fit-centres204.json",
                    "sourcePacketAuthority":copy.deepcopy(centres["authority"])}})
        rows[index] = row
    for check in ledger["rows"]:
        index = check["frameIndex"]
        row = rows[index]
        if row["sourceImage"] != check["sourceImage"] or row["decodedTimeSeconds"] != check["timeSeconds"]:
            raise ValueError(f"Independent CHECK source exposure mismatch: {check['rowId']}")
        anchor_id = f"station-{check['sourceStation']}-{check['corner']}"
        native = request_anchors[anchor_id]
        if native["partPath"] != check["nativePartPath"] or native["partLocalMetres"] != check["nativeLocalVertexMetres"]:
            raise ValueError(f"Independent CHECK native local identity mismatch: {check['rowId']}")
        anchors[anchor_id] = {"id":anchor_id,"kind":"physical-feature","partPath":check["nativePartPath"],
            "partLocalMetres":check["nativeLocalVertexMetres"],"motion":"moving",
            "description":f"Source station{check['sourceStation']} exposed cap {check['corner']} material/background boundary CHECK.",
            "correspondenceEvidence":"Independent frozen interior-cap-check-ledger/sourceOriginal. Exact native local vertex copied, not old candidate projected/world coordinates. Typed source uncertainty is coordinate-max allowance (not confidence); scalar retained unchanged. Native material correspondence remains a candidate; source pixels are independently measured."}
        original = check["sourceOriginal"]
        if check["sourceStatus"] == "measured":
            if original["pixel"] != check["sourcePixel"]:
                raise ValueError(f"CHECK pixel mismatch: {check['rowId']}")
            row["landmarks"].append({"anchorId":anchor_id,"viewId":"bar-bank","role":"check",
                "pixel":original["pixel"],"status":"observed","method":"image-edge",
                "uncertaintyPx":original["uncertaintyPx"],
                "measurementEvidence":{"sourceImage":copy.deepcopy(check["sourceImage"]),
                    "technique":"Independent source material/background brightness-step threshold edge localization",
                    "originalMeasurement":copy.deepcopy(original),
                    "sourceRowId":check["rowId"],
                    "sourcePacket":".playwright-cli/analysis-recovery/augmented-face-frozen-check/interior-cap-check-ledger.json",
                    "sourcePacketSha256":ledger["sourcePacketSha256"]}})
        else:
            row["unavailable"].append({"anchorId":anchor_id,"viewId":"bar-bank","role":"check","status":"unresolved",
                "pixel":None,"uncertaintyPx":None,"reason":original["reason"]})
    return {"schemaVersion":1,"kind":"historical-source-track-receipt","historicalDiagnostic":True,
        "publishable":False,"productionIntegrated":False,"videoId":"6dW6VYXp9HM",
        "source":source["source"],"model":source["model"],"anchors":list(anchors.values()),"frames":list(rows.values()),
        "sourceMeasurementCounts":{"sourceExposures":len(rows),"independentMeasuredChecks":ledger["counts"]["measured"],
            "unresolvedChecksPreserved":ledger["counts"]["unresolved"],"fitCentroids":sum(sum(p["role"] == "fit" for p in row["landmarks"]) for row in rows.values())},
        "stages":{str(stage):{"status":"unmeasured"} for stage in (50,20,10,5)},
        "evidence":{"checkLedger":".playwright-cli/analysis-recovery/augmented-face-frozen-check/interior-cap-check-ledger.json",
            "sourcePacketSha256":ledger["sourcePacketSha256"],"sourceProvenance":report["sourceProvenance"],
            "notes":["Historical diagnostic only; never merge into current production tracks.",
                "No old CPU projected/world coordinates, residuals, predictions or GPU claims copied as measured source pixels.",
                "Exact historical native exposure rows preserve204 source regimes and their times.",
                "For integer-second controls, copy only when sourceImage/frameIndex/hash matches. Analysis117 authored source row is frame3506 at116.983533333s; its CHECKs exist in this packet. Never interpolate CHECK pixels.",
                "Schema image-edge names source threshold/segmentation localization; unchanged original centroid/threshold recipes and exact exposure evidence remain on each point. FIT centroids remain proxies, not CHECK vertices.",
                "Known CHECK nulls remain unresolved. No source motion/control coverage outside112.3122..119.085633333s inferred."]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-diagnostic", action="store_true", required=True)
    parser.add_argument("--output", type=Path, default=WEB / ".vite/verification-output/compact-source-refinement/analysis-bank-source-controls.json")
    args = parser.parse_args()
    try:
        output = private_output(args.output)
    except ValueError as error:
        parser.error(str(error))
    packet = build_packet(historical_diagnostic=args.historical_diagnostic)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(packet,separators=(",",":"),allow_nan=False)+"\n")
    print(output)
    print(json.dumps(packet["sourceMeasurementCounts"]))


if __name__ == "__main__":
    main()

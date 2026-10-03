#!/usr/bin/env python3
"""Generate the current v39 Analysis/Synthesis compact source tracks.

Prerequisites (parent execution only): supported fetch-model import, then
  python web/scripts/adopt-v39-source-observations.py
  python web/scripts/generate-analysis-synthesis-current-associations.py
  python web/scripts/generate-analysis-synthesis-source-tracks.py
Each pair command prepares both videos before publishing; --video selects one.

Only web/content/v39 observations and explicitly validated current choice packets
are active. Root observations, old camera/input numbers and certificates are
immutable historical lineage. Retained numeric candidates are newly chosen and
unmeasured for v39, not transferred fits or native REST/world/GPU support. Original
source clocks/pixels/FIT/CHECK roles and required losses remain original facts.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
spec = importlib.util.spec_from_file_location("analysis_synthesis_current_associations", WEB / "scripts/generate-analysis-synthesis-current-associations.py")
choices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(choices)
common = choices.common
ANALYSIS_MODEL_SHA256 = choices.ANALYSIS_MODEL_SHA256
MODEL_COMMIT = choices.MODEL_COMMIT


class Generator:
    def __init__(self, video_id):
        if video_id not in choices.VIDEOS:
            raise ValueError("Analysis/Synthesis generator accepts only its two current videos")
        self.analysis = video_id == "6dW6VYXp9HM"
        self.data = common.load_observations(video_id)
        self.packet = choices.load_packet(video_id, self.data)
        self.association_path = common.CURRENT_CONTENT / f"{video_id}.current-associations.json"
        self.by_frame = {}
        for frame in self.packet["choices"]:
            key = tuple(frame["frameKey"])
            if key in self.by_frame:
                raise ValueError("Duplicate current source exposure/layout choice")
            self.by_frame[key] = frame

    def views(self, frame):
        key = tuple(choices.frame_key(frame))
        if key not in self.by_frame:
            raise ValueError(f"No explicit current choice for required source frame {key}")
        planned = self.by_frame[key]["views"]
        originals = common.source_views(frame, self.data)
        if len(planned) != len(originals) or any(row["layout"] != choices.layout(view) for row, view in zip(planned, originals)):
            raise ValueError("Current choice cannot erase, alias or replace an original required source view/layout")
        output = []
        for row, original in zip(planned, originals):
            # Only numeric perspective/input values are retained. No historical
            # camera status, residual, fit family, witness or support prose enters.
            camera, value = choices.strict_camera(row["camera"]), choices.strict_input(row["input"])
            numeric = row["historicalNumericChoice"]
            if row["fallbackReason"]:
                selection = ("Fresh current-native rest framing chosen because " + row["fallbackReason"]
                             + ". This is not an improvement, source fit, dynamic closure or rendered qualification.")
            else:
                selection = (f"Retained numeric candidate {numeric['path']}#{numeric['jsonPointer']} is newly chosen for v39. "
                             "Old FIT/native-rest/cam-rod world/GPU certificates remain historical, not current support. "
                             + ("Numbers coincide with this actual exposure; that is not a transferred source fit. "
                                if row["sameExposureNumericChoice"] else
                                "Same-shot/view numeric hold is explicitly unmeasured; no image, pixel, CHECK or clock identity is borrowed. "))
            scope = row["sourceParameterScope"]
            if self.analysis and frame["shotId"] == "analysis-22":
                scope += " Historical geometry-conditioned bank-drive numbers are chosen playback only, not a current calibrated physical crank trajectory."
            if not self.analysis and frame["shotId"] == "rocker-bank":
                scope += (" Observable H20 source half-sweep events retain published-video cadence. Dense within-sweep clock, "
                          "+1 native sense and all20 phase/home choices remain chosen. Lower-cut sign/cadence/phase never transfers here.")
            if self.analysis and frame["shotId"] == "analysis-16":
                scope += (" Source visible-crank cycles/approximate relative ellipse phase are independent observations; "
                          "native sign, absolute home, fixed setup and drive lag remain chosen, with no cross-shot phase transfer.")
            continuity = f"v39-chosen:{self.data['source']['videoId']}:{frame['shotId']}:{original['id']}:{row['cameraContinuityBranch']}"
            view = {
                "id": original["id"], "rectSourcePixels": copy.deepcopy(original["rectSourcePixels"]),
                "presentation": original.get("presentation", "native"), "camera": camera, "input": value,
                "provenance": common.chosen_provenance(selection + " " + scope),
                "cameraProvenance": {"kind": "source-informed-framing", "family": continuity,
                    "evidence": "Explicitly chosen unmeasured current camera numbers; no old fitted/matched native support. " + selection},
                "cameraContinuityFamily": continuity,
                "cameraInterpolation": row["cameraInterpolation"],
                "cameraInterpolationEvidence": "Authored current numeric camera interpolation/hold only within this unchanged source shot/view branch; the actual source camera history and current posed-feature/GPU support remain unmeasured.",
            }
            warp, composite = common.resolve_warp(original), common.compact_composite(original)
            if warp:
                view["imagePlaneWarp"] = copy.deepcopy(warp)
            if composite:
                view["composite"] = copy.deepcopy(composite)
            for field in ("sourceViewIds", "sourceViewMappingEvidence"):
                if field in original:
                    view[field] = copy.deepcopy(original[field])
            output.append(view)
        return output

    def build(self):
        track = common.build_track(self.data, self.views, [
            "Regenerate current choice packets first with python web/scripts/generate-analysis-synthesis-current-associations.py, then python web/scripts/generate-analysis-synthesis-source-tracks.py; only web/content/v39 is active.",
            "Retained refined camera/input numbers are newly chosen unmeasured current candidates after independent current native ownership, parameter-domain and exact feature association checks. Old model certificates/digests are immutable historical lineage, not current evidence.",
            "Every original source integer/shot-edge/layout interval, view, original FIT/CHECK role, localization uncertainty and required unavailable feature remains required. Unknown machine views are not excluded and no null PTS is fabricated.",
            "All50/20/10/5 stages remain unmeasured. Loading/camera/input coverage is not a source-fidelity, whole-surface, dynamic spring, normal-app or GPU acceptance result.",
        ])
        # Preserve the original source schema, including Analysis's recorded
        # decodedNativeFrameCount/lastDecodedFrameTimeSeconds rather than losing
        # those facts through the generic compact source-field projection.
        track["source"] = copy.deepcopy(self.data["source"])
        if track["model"] != common.current_model_identity():
            raise ValueError("Current source track lost its exact approved native model tuple")
        expected = {tuple(row["frameKey"]) for row in self.packet["choices"]}
        actual = {tuple(choices.frame_key(frame)) for frame in track["frames"]}
        if actual != expected:
            raise ValueError("Current compact selection erased or invented a source exposure/layout choice")
        if any(stage != {"status": "unmeasured"} for stage in track["stages"].values()):
            raise ValueError("Current chosen source candidates cannot assert a measured matching stage")
        track["evidence"]["currentAssociations"] = {
            "path": str(self.association_path.relative_to(ROOT)), "sha256": choices.digest(self.association_path),
            "currentObservations": copy.deepcopy(self.packet["currentObservations"]),
            "qualification": copy.deepcopy(self.packet["qualification"]),
            "nativeAssociationScope": "Exact original native primitive/local-feature/frame association only; no historical fit/world/GPU certificate adoption",
            "inputFieldCount": 51, "interpretation": "51 named coordinates in one chosen state, NOT 51 replay states",
        }
        track["evidence"]["historicalLineage"] = copy.deepcopy(self.packet["historicalLineage"])
        track["evidence"]["historicalLineageScope"] = self.packet["historicalLineageScope"]
        track["evidence"]["sourceClocks"] = copy.deepcopy(self.packet["sourceClocks"])
        track["sourceMeasurements"]["blockers"].extend([
            "All absolute native input coordinates, camera parameters and sign/home mappings remain chosen/unmeasured for v39; original source timing/pixels do not certify the chosen native projection.",
            "Fresh v39 physical closure/body correspondence, posed feature/first-surface support, all21 swept-stock spring GPU proof and normal-app/source-stage acceptance are still required. The transgear pivot disc is not a22nd swept spring.",
            "Original required feature losses remain required even where exact old-to-current primitive association is unavailable; no removed-node aliases or predicted source pixels are supplied.",
        ])
        if self.analysis:
            track["sourceMeasurements"]["blockers"].append(
                "Analysis original source visible-crank cycles and approximate within-cycle phase remain bounded to analysis-16. Geometry-conditioned bank drive/continuation/root-input values are retained only as chosen numeric candidates; old fixed mirrored camera/native proof does not calibrate current crank sign/home/phase or dynamic body support.")
        else:
            track["sourceMeasurements"]["blockers"].append(
                "Synthesis source H20 annotation events time the bounded bank cadence. Dense crank-equivalent interpolation and +1 native sense are chosen, not precise recovered shaft motion/home. The isolated lower-crank cut retains rough local source-ray cadence only; phase remains unqualified and cannot transfer sign/cadence/phase across the edit into the bank.")
        return track


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", choices=choices.VIDEOS)
    args = parser.parse_args()
    videos = (args.video,) if args.video else choices.VIDEOS
    tracks = [Generator(video_id).build() for video_id in videos]
    outputs = [(track, *common.prepare_track(track)) for track in tracks]
    for track, path, contents in outputs:
        path.write_text(contents)
        print(f"{path.relative_to(ROOT)}: {len(track['shots'])} shots, {len(track['frames'])} compact frames, {sum(len(frame['views']) for frame in track['frames'])} views; coverage={track['coverage']['status']}; stages unmeasured")

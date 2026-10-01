#!/usr/bin/env python3
"""Regenerate compact Analysis/Synthesis playback candidates from retained evidence.

Run from any directory with the preserved private evidence in this checkout:
  python web/scripts/generate-analysis-synthesis-source-tracks.py
This copies numeric evidence only. It loads no CAD/model/browser and does not
qualify cameras, recover historical settings, or measure any matching stage.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
spec = importlib.util.spec_from_file_location("compact_source_common", WEB / "scripts/compact-source-common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
ANALYSIS = ".playwright-cli/analysis-recovery/four-seed-source-fit-census"
SYNTHESIS = "web/.vite/verification-output/synthesis-full-source"


def load(path):
    return json.loads((ROOT / path).read_text())


def nearest(rows, time, key):
    return min(rows, key=lambda row: abs(key(row) - time))


def look_camera(target, yaw, elevation, span, aspect):
    """Proper perspective camera framing an evidence-derived component envelope.

    World Y is up; native front is negative Z. The chosen source-facing yaw,
    elevation and framing margin are explicit assumptions, not pixel fits.
    """
    fov = 30.0
    distance = span / (2 * math.tan(math.radians(fov / 2)))
    z = [math.sin(yaw) * math.cos(elevation), math.sin(elevation), -math.cos(yaw) * math.cos(elevation)]
    x = [z[2], 0, -z[0]]
    length = math.sqrt(sum(v*v for v in x))
    x = [v / length for v in x]
    y = [z[1]*x[2]-z[2]*x[1], z[2]*x[0]-z[0]*x[2], z[0]*x[1]-z[1]*x[0]]
    # Quaternion from an orthonormal camera basis, including rear/overhead views.
    m = [[x[i], y[i], z[i]] for i in range(3)]
    trace = sum(m[i][i] for i in range(3))
    if trace > 0:
        t = math.sqrt(trace + 1)*2
        q = [(m[2][1]-m[1][2])/t, (m[0][2]-m[2][0])/t, (m[1][0]-m[0][1])/t, t/4]
    else:
        i = max(range(3), key=lambda k: m[k][k]); j = (i+1)%3; k = (i+2)%3
        t = math.sqrt(1+m[i][i]-m[j][j]-m[k][k])*2
        q = [0., 0., 0., (m[k][j]-m[j][k])/t]
        q[i] = t/4; q[j] = (m[j][i]+m[i][j])/t; q[k] = (m[k][i]+m[i][k])/t
    return {"positionMetres": [target[i]+distance*z[i] for i in range(3)], "quaternion": q,
            "verticalFovDegrees": fov}


class Generator:
    def __init__(self, video_id):
        self.analysis = video_id == "6dW6VYXp9HM"
        self.data = common.load_observations(video_id, prefer_track=not self.analysis)
        self.shots = {s["id"]: s for s in self.data["shots"]}
        if self.analysis:
            self.shots["analysis-39"]["hasCorrespondingMachine"] = True
            for frame in self.data["frames"]:
                if frame["shotId"] == "analysis-39":
                    frame["sourceMachineRequirement"] = "required"
                    frame["views"] = self.analysis_endcard_layout()
            self.data["compactChangeTimesSeconds"] = [
                self.shots[name]["startSeconds"] + f*(self.shots[name]["endSeconds"]-self.shots[name]["startSeconds"])
                for name in ("analysis-03","analysis-05","analysis-07","analysis-13","analysis-15","analysis-17","analysis-19","analysis-28")
                for f in (0.25,0.5,0.75)]
        self.native = load(f"{SYNTHESIS}/source-pinhole-alternatives/actual-current-native.json")
        self.base = self.native["mechanical"][0]["chosenInput"]
        self.candidate = load(f"{ANALYSIS}/candidate.json")
        self.request = load(f"{ANALYSIS}/all204-cpu-forward-request.json")
        requested = {row["frameIndex"]: row["chosenInput"] for row in self.request["requests"] if row["kind"] == "all204-chosen-native-forward-input"}
        if any(requested[row["frameIndex"]] != row["chosenInput"] for row in self.candidate["frames"]):
            raise ValueError("Frozen Analysis candidate and serialized complete input request differ.")
        self.bank_controls = None
        if self.analysis:
            controls_spec = importlib.util.spec_from_file_location("analysis_bank_controls", WEB / "scripts/generate-analysis-bank-source-controls.py")
            controls_module = importlib.util.module_from_spec(controls_spec)
            controls_spec.loader.exec_module(controls_module)
            self.bank_controls = controls_module.build_packet()
            self.data["anchors"].extend(copy.deepcopy(self.bank_controls["anchors"]))
            controls = {row["sourceImage"]["frameIndex"]: row for row in self.bank_controls["frames"]}
            for frame in self.data["frames"]:
                index = frame.get("decodedFrameIndex")
                control = controls.get(index)
                if control is None:
                    continue
                if frame.get("sourceImage") != control["sourceImage"]:
                    raise ValueError(f"Analysis source-image identity mismatch at {index}")
                frame["landmarks"].extend(copy.deepcopy(control["landmarks"]))
                frame.setdefault("unavailable", []).extend(copy.deepcopy(control["unavailable"]))
            self.data["compactChangeTimesSeconds"].extend(row["timeSeconds"] for row in controls.values())
        self.motion = load(f"{SYNTHESIS}/native-cpu/conditional-source121-complete51-motion.json")
        self.pinhole = load(f"{SYNTHESIS}/source-pinhole-alternatives/physical-pinhole-alternatives-packet.json")
        self.donors = load("web/content/XPQwKRt4Y2k.source-seeds.json")
        self.seeds = [(f["shotId"], f["timeSeconds"], f["camera"]) for f in self.data["frames"] if common.compact_camera(f.get("camera"))]
        self.features = {}
        for f in self.data["frames"]:
            for point in f.get("sourceMeasurements", {}).get("observedFeaturePixels", []):
                self.features.setdefault(point["featureId"], []).append((f["decodedTimeSeconds"], point["pixel"][1]))
        # These semantic groups refer to actual unchanged native part bounds.
        self.groups = {
            "whole": ("/frame/", "/base/"), "spring": ("/channel/channel-lever-", "/channel/spring-"),
            "bar": ("/channel/rocker-arm-", "/channel/amplitude-bar-"),
            "cone": ("/drive-train/cone", "/drive-train/cylinder", "/drive-train/crank"),
            "pen": ("/pen/pen-frame-", "/paper-drive/platen-"),
            "wheel": ("/magnifier/magnifying-wheel-", "/magnifier/wheel-axle-"),
            "top": ("/magnifier/magnifying-lever-", "/summing/"),
            "knife": ("/summing/",), "clamp": ("/magnifier/clamp-",),
        }
        self.parts = self.native["mechanical"][0]["all435"]

    def envelope(self, family, aspect):
        parts = [p for p in self.parts if any(name in p["partPath"] for name in self.groups[family])]
        if not parts:
            raise ValueError(f"No immutable native component bounds for {family}")
        bounds = [p["rigidWorldBoundsM"] for p in parts]
        low = [min(b[0][i] for b in bounds) for i in range(3)]
        high = [max(b[1][i] for b in bounds) for i in range(3)]
        target = [(a+b)/2 for a,b in zip(low,high)]
        span = max(high[1]-low[1], (high[0]-low[0])/aspect, (high[2]-low[2])/aspect)*1.25
        return target, max(span, 0.04)

    def family(self, frame, view):
        shot, vid = frame["shotId"], view["id"]
        if vid.startswith("endcard-"):
            return {"endcard-plaque":"whole", "endcard-bank":"bar", "endcard-pen-inset":"pen", "endcard-spin":"whole", "endcard-rocker":"bar"}.get(vid, "pen")
        if self.analysis:
            n = int(shot.split("-")[-1])
            if vid == "pen-inset": return "pen"
            if n in (11,12,13,26,27,28): return "spring"
            if n in (14,15,29,30): return "pen"
            if n in (16,17): return "cone"
            if n in range(18,25): return "bar"
            return "whole"
        if vid == "upper-inset": return "spring"
        if vid == "lower-inset": return "bar"
        if vid == "main" and ("inset" in shot or "whole-spin" in shot): return "whole"
        if vid in ("outgoing", "incoming"):
            pairs = {"cam-to-rocker-fade":("cone","bar"), "top-overhead-fade":("top","spring"), "overhead-spring-fade":("spring","spring"), "lower-presenter-fade":("cone","whole")}
            if shot in pairs: return pairs[shot][vid == "incoming"]
        if "gear-macro" in shot or "cone" in shot or "gear-inset" in shot or "crank" in shot or "cam-rod" in shot: return "cone"
        if "rocker" in shot or "bar-inset" in shot: return "bar"
        if "spring" in shot or "overhead" in shot: return "spring"
        if "pen" in shot: return "pen"
        if "wheel" in shot: return "wheel"
        if "clamp" in shot: return "clamp"
        if "knife" in shot: return "knife"
        if "summing" in shot or "magnifier" in shot or "top-assembly" in shot: return "top"
        return "whole"

    def camera(self, frame, view, family):
        time, shot = frame["timeSeconds"], frame["shotId"]
        direct = common.compact_camera(view.get("camera") or (frame.get("camera") if view["id"] == "main" else None))
        if direct: return direct, "Original per-exposure source-derived camera; retained CPU FIT/CHECK status is not a stage pass."
        if self.analysis and family == "bar" and view.get("presentation") == "horizontal-mirror":
            return common.compact_camera(self.candidate["nativeCameraRecord"]), "Latest four-seed source FIT camera with its genuine horizontal mirror; independent new native/GPU qualification unexecuted."
        same = [s for s in self.seeds if s[0] == shot]
        if same: return common.compact_camera(nearest(same,time,lambda x:x[1])[2]), "Nearest same-shot source camera, held over the unmeasured exposure; not independently fitted here."
        if family == "whole" and not ("spin" in shot or "inset" in shot or shot.startswith("endcard")):
            candidates = [s for s in self.seeds if s[0] in (("analysis-06","analysis-37") if self.analysis else ("intro-machine","final-presenter-machine"))]
            if candidates and (not self.analysis or int(shot[-2:]) not in (3,4,5,7,8)):
                return common.compact_camera(nearest(candidates,time,lambda x:x[1])[2]), "Related presenter/front composition source camera held as a coarse baseline, not a matched pose."
        if not self.analysis and family == "pen" and shot == "wheel-pen":
            camera = self.pinhole["actualFrozenFitterExperiments"][0]["actualFrozenFitterCameraRecord"]
            return common.compact_camera(camera), "Exact Source6330 CPU pinhole FIT candidate; failed independent guide CHECK remains a diagnostic, not an exclusion."
        rect = view["rectSourcePixels"]; aspect = rect[2]/rect[3]
        target, span = self.envelope(family,aspect)
        yaw, elevation = 0., 0.12
        if family in ("spring","bar","cone"): yaw, elevation = -math.pi/2, 0.16
        if "overhead" in shot: elevation = math.radians(78)
        if self.analysis and family == "whole":
            # Native source edit windows bracket actual presenter-driven rotation.
            n = int(shot[-2:]); yaw = math.pi if n in (4,8) else 0.
            if n in (3,5,7):
                s = self.shots[shot]; fraction = (time-s["startSeconds"])/(s["endSeconds"]-s["startSeconds"])
                yaw = math.pi*(1-fraction if n == 5 else fraction)
        if not self.analysis and family == "whole" and ("spin" in shot or "inset" in shot):
            yaw = 2*math.pi*(time-26.61)/(60.94-26.61)
        return look_camera(target,yaw,elevation,span,aspect), f"Chosen {family} crop: immutable native component bounds, source shot/view identity and front/rear/side/overhead description. Assumed30deg focal,25% framing margin, yaw/elevation and turntable cadence where no measured camera exists; no source-pixel fit claimed."

    def input(self, frame, family):
        time = frame["decodedTimeSeconds"]
        if self.analysis:
            snapshots = self.candidate["frames"]
            first, last = snapshots[0]["sourceFrameIdentity"]["timeSeconds"], snapshots[-1]["sourceFrameIdentity"]["timeSeconds"]
            if family == "bar" and first <= time <= last:
                row = nearest(snapshots,time,lambda x:x["sourceFrameIdentity"]["timeSeconds"])
                return copy.deepcopy(row["chosenInput"]), "Latest frozen source FIT complete51 snapshot; amplitudes/phases are chosen inverse witnesses, not historical crank recovery."
            # A source-window alone is not a measured crank trajectory. Hold the
            # nearest independently source-fitted complete input outside204 rather
            # than synthesizing a cadence, cosine sweep or coefficient history.
            row = snapshots[0] if time < first else snapshots[-1]
            return copy.deepcopy(row["chosenInput"]), "Nearest endpoint complete51 source-FIT witness held outside measured204 bank exposures. Source-visible crank/coefficient trajectory in this different shot remains unmeasured; no generic cosine animation or historical input recovery claimed."
        if family in ("pen","wheel") and 264.01375 <= time <= 269.01875:
            row = nearest(self.motion["rows"],time,lambda x:x["nativePtsSeconds"])
            return copy.deepcopy(row["input"]), "Immutable Source6330..6450 conditional complete51 relative pen/wheel-motion input. Hidden collar is a chosen trajectory; absolute spoke/input history and full435 association remain unqualified."
        value = copy.deepcopy(self.base)
        # No free-running invented crank. Use retained measured feature displacement
        # as a dimensionless motion witness only in its actual photographed window.
        for feature, rows in self.features.items():
            if rows[0][0] <= time <= rows[-1][0] and ((family == "bar" and "rocker" in feature) or (family == "cone" and "cam20" in feature) or (family == "spring" and "raised-upper" in feature)):
                low, high = min(y for _,y in rows), max(y for _,y in rows)
                if high-low <= 1: continue
                point = nearest(rows,time,lambda x:x[0]); normalized = 2*(point[1]-low)/(high-low)-1
                value["amplitudes"][19] = -0.08
                value["phases"][19] = math.acos(max(-1.,min(1.,normalized)))
                value["setup"]["counterHeightM"] = None
                return value, f"Complete immutable numeric baseline plus source-observed {feature} vertical-displacement witness. Assumed harmonic1 branch/small coefficient; pixel range mapped to cosine phase, not metrically recovered source motion or station association. Other hidden settings held, no generic animation."
        return value, "Complete immutable physically exercised small-large input baseline; unmeasured source-visible motion/coefficients held rather than invented. This is a source-informed static candidate, not historical state recovery."

    @staticmethod
    def analysis_endcard_layout():
        # Visually read from original AnalysisMP4 at220s: boundaries x640/1280,
        # y540. These are this source's boxes, not copied Spin source pixels.
        views = [{"id":"endcard-intro","rectSourcePixels":[0,0,640,540],"presentation":"native"},
                 {"id":"endcard-synthesis","rectSourcePixels":[640,0,640,540],"presentation":"native"},
                 {"id":"endcard-book","rectSourcePixels":[0,540,640,540],"presentation":"native"},
                 {"id":"endcard-guide","rectSourcePixels":[640,540,640,540],"presentation":"native"},
                 {"id":"endcard-rocker","rectSourcePixels":[1280,540,640,540],"presentation":"native"}]
        views.extend({"id":f"endcard-operation-paper-{i}","rectSourcePixels":[1280,180*i,640,180],"presentation":"native"} for i in range(3))
        return views

    def donor_view(self, original, donor_id):
        donor = self.donors["views"][donor_id]
        return {"id":original["id"],"rectSourcePixels":original["rectSourcePixels"],
                "presentation":original.get("presentation",donor.get("presentation","native")),
                "camera":common.compact_camera(donor["camera"]),
                "input":common.compact_input(self.donors["candidates"][donor["candidateId"]]["input"]),
                "provenance":common.chosen_provenance(f"Photographed branch donor {donor_id}/{donor['candidateId']} from XPQwKRt4Y2k.source-seeds.json. Source boxes retained/independently inspected; camera/full input transferred as a coarse chosen candidate, NOT measured current-source pixels, history or GPU qualification. Blurred layer weights and source footage cadence unobserved.")}

    def views(self, frame):
        output = []
        for original in common.source_views(frame,self.data):
            donor_id = original["id"]
            if not self.analysis:
                donor_id = {"endcard-plaque":"endcard-intro","endcard-bank":"endcard-analysis","endcard-pen-inset":"endcard-analysis-pen-inset"}.get(donor_id, donor_id)
                if donor_id.startswith("endcard-paper-"):
                    donor_id = donor_id.replace("endcard-paper-","endcard-operation-paper-")
            if donor_id in self.donors["views"] and self.donors["views"][donor_id].get("camera"):
                output.append(self.donor_view(original,donor_id))
                continue
            family = self.family(frame,original)
            camera, camera_note = self.camera(frame,original,family)
            value, input_note = self.input(frame,family)
            view = {"id":original["id"], "rectSourcePixels":original["rectSourcePixels"],
                    "presentation":original.get("presentation","native"), "camera":camera,
                    "input":common.compact_input(value),
                    "provenance":common.chosen_provenance(camera_note+" "+input_note)}
            warp = common.resolve_warp(original)
            if warp: view["imagePlaneWarp"] = warp
            composite = common.compact_composite(original)
            if composite: view["composite"] = composite
            output.append(view)
        # Analysis source audit describes simultaneous physical views even before
        # the legacy ledger first introduced its per-view representation.
        if self.analysis and frame["shotId"] == "analysis-17" and not any(v["id"] == "bar-bank" for v in output):
            s = self.shots[frame["shotId"]]
            f = max(0.,min(1.,(frame["timeSeconds"]-s["startSeconds"])/(s["endSeconds"]-s["startSeconds"])))
            width = max(1.,1920*f)
            original = {"id":"bar-bank", "rectSourcePixels":[1920-width,0,width,1080], "presentation":"native"}
            family="bar";camera,note=self.camera(frame,original,family);value,why=self.input(frame,family)
            output.append({**original,"camera":camera,"input":common.compact_input(value),"provenance":common.chosen_provenance(note+" "+why+" Expanding insert layout inferred linearly from the independently retained shot onset/settle; rectangle is chosen, not measured.")})
        fades = {"analysis-13":("spring","pen"), "analysis-15":("pen","cone"), "analysis-28":("spring","pen")}
        if self.analysis and frame["shotId"] in fades:
            shot = self.shots[frame["shotId"]]
            fraction = (frame["timeSeconds"]-shot["startSeconds"])/(shot["endSeconds"]-shot["startSeconds"])
            output = []
            for index,family in enumerate(fades[frame["shotId"]]):
                original = {"id":("outgoing","incoming")[index], "rectSourcePixels":[0,0,1920,1080], "presentation":"native"}
                target,span = self.envelope(family,1920/1080)
                camera = look_camera(target,-math.pi/2 if family != "pen" else 0.,0.16,span,1920/1080)
                value,note = self.input(frame,family)
                output.append({**original,"camera":camera,"input":common.compact_input(value),
                    "composite":{"mode":"crossfade","groupId":frame["shotId"],"imageLayerId":original["id"],"opacity":fraction if index else 1-fraction},
                    "provenance":common.chosen_provenance(note+" Both independently filmed source perspectives retained. Camera from component bounds; linear fade weights chosen from source shot boundaries, not measured opacity.")})
        if self.analysis and frame["shotId"] == "analysis-19":
            shot = self.shots[frame["shotId"]]
            fraction = (frame["timeSeconds"]-shot["startSeconds"])/(shot["endSeconds"]-shot["startSeconds"])
            scale = max(0.02,abs(math.cos(math.pi*fraction)))
            for view in output:
                view["camera"] = common.compact_camera(self.candidate["nativeCameraRecord"])
                view["presentation"] = "horizontal-mirror" if fraction >= 0.5 else "native"
                view["imagePlaneWarp"] = {"kind":"homography","unwarpedViewportPixels":[1920,1080],
                    "renderToSourcePixels":[scale,0,960*(1-scale),0,1,0,0,0,1]}
                view["provenance"]["evidence"] += " Source page-flip modeled as chosen center-hinged width compression with mirrored endpoint;2% width floor avoids a singular edge-on homography. Perspective fold/shadow details unmeasured; no real machine rotation invented."
        return output

    def build(self):
        track = common.build_track(self.data,self.views,[
            "Regenerate with python web/scripts/generate-analysis-synthesis-source-tracks.py; requires immutable ignored source evidence; source/model hashes remain unchanged.",
            "All50/20/10/5% width stages remain unmeasured. CPU camera rejection at2% is not a blanket removal of a coarser candidate. No GPU/model/browser execution or historical source recovery.",
            "Camera/input/layout assumptions are declared per view. All retained source shots and integer/change/layout keys remain required, including nested endcards; source copyrighted artwork is not reconstructed."])
        track["source"] = copy.deepcopy(self.data["source"])
        track["evidence"]["notes"].append("Analysis endcard boxes independently inspected from retained original MP4 at220s. Donor photographed camera branches are explicitly chosen, not copied source pixels. Page-flip uses a finite chosen projective-layout baseline, not recovered editing history.")
        track["cpuDiagnostics"] = {
            "analysisFourSeed": {"source":f"{ANALYSIS}/candidate.json", "qualification":self.candidate["qualification"], "distributions":self.candidate["fullSourceRawAndNormalizedDistributions"]},
            "synthesisPinhole": {"source":f"{SYNTHESIS}/source-pinhole-alternatives/physical-pinhole-alternatives-packet.json", "finiteAttempts":self.pinhole["finiteAttemptCount"], "positiveDepthCandidates":self.pinhole["physicalPositiveDepthEscapeCount"], "sourceAccepted":False},
            "synthesisRelativeMotion": {"source":f"{SYNTHESIS}/native-cpu/conditional-source121-complete51-motion.json", "maximumConditionalRelativePenResidualPx":self.motion["maximumConditionalRelativePenResidualPx"], "sourceAccepted":False}}
        track["sourceMeasurements"] = {"status":"partial","blockers":[
            "Stage50/20/10/5 source-width errors remain unmeasured by this generator; source camera/input assumptions are not rendered source-fidelity passes.",
            "Component-envelope closeup/turntable framing is chosen where a source-fit camera is unavailable; exact source camera/temporal history remains unmeasured.",
            "Blurred montage camera/input donors and finite page-flip/linear-fade baselines remain transfers/assumptions, not independently matched current-source measurements."]}
        if self.bank_controls:
            track["sourceMeasurements"]["analysisBankControls"] = copy.deepcopy(self.bank_controls["sourceMeasurementCounts"])
            track["sourceMeasurements"]["blockers"].append("Analysis bank CHECKs cover exact204 exposures112.3122..119.085633333s;2690 original corner nulls remain unavailable. Other moving mechanism/pen/crank controls outside that window are not inferred.")
            track["evidence"]["notes"].extend(self.bank_controls["evidence"]["notes"][1:])
        else:
            track["sourceMeasurements"]["blockers"].append("Synthesis conditional relative pen/wheel trajectory and source-displacement cosine witnesses do not metrically qualify full source-visible motion or unknown station/phase associations.")
        self.camera_metadata(track)
        return track

    def camera_metadata(self, track):
        previous, epochs = {}, {}
        for frame in track["frames"]:
            for view in frame["views"]:
                evidence = view["provenance"]["evidence"]
                camera = view["camera"]
                component = self.family(frame,view)
                if evidence.startswith("Photographed branch donor"):
                    kind, branch = "source-transfer", evidence.split(" from ")[0]
                elif evidence.startswith("Latest four-seed") or frame["shotId"] == "analysis-19":
                    kind, branch = ("source-fit","analysis-four-seed-bank") if frame["shotId"] != "analysis-19" else ("source-transfer","analysis-page-flip-bank")
                elif evidence.startswith("Original per-exposure") or evidence.startswith("Exact Source6330"):
                    kind, branch = "source-fit", f"{frame['shotId']}:{view['id']}"
                elif evidence.startswith("Nearest same-shot") or evidence.startswith("Related presenter"):
                    # Each held donor is a distinct branch; never interpolate two
                    # unrelated solutions merely because source shot IDs agree.
                    fingerprint = json.dumps({k:camera[k] for k in ("positionMetres","quaternion","verticalFovDegrees")},sort_keys=True,separators=(",",":"))
                    fingerprint = hashlib.sha256(fingerprint.encode()).hexdigest()[:12]
                    kind, branch = "source-transfer", f"{frame['shotId']}:{view['id']}:held-{fingerprint}"
                else:
                    kind, branch = "source-informed-framing", f"{frame['shotId']}:{view['id']}:{component}"
                family = f"{kind}:{branch}"
                old = previous.get(family)
                if old:
                    dot = min(1.,abs(sum(a*b for a,b in zip(old["quaternion"],camera["quaternion"]))))
                    if 2*math.acos(dot) > math.radians(30):
                        epochs[family] = epochs.get(family,0)+1
                previous[family] = camera
                continuity = f"{family}:branch{epochs.get(family,0)}"
                view["cameraProvenance"] = {"kind":kind,"family":continuity,"evidence":evidence+" Camera assumptions remain unmeasured; continuity does not certify a match."}
                view["cameraContinuityFamily"] = continuity


if __name__ == "__main__":
    for video_id in ("6dW6VYXp9HM", "8KmVDxkia_w"):
        track = Generator(video_id).build()
        path = common.write_track(track)
        print(f"{path.relative_to(ROOT)}: {len(track['shots'])} shots, {len(track['frames'])} compact frames, {sum(len(f['views']) for f in track['frames'])} views; coverage={track['coverage']['status']}; stages unmeasured")

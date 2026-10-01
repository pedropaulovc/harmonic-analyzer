#!/usr/bin/env python3
"""Regenerate compact Analysis/Synthesis playback candidates from retained evidence.

Run from any directory with the preserved private evidence in this checkout:
  python web/scripts/generate-analysis-synthesis-source-tracks.py
This retains numeric evidence and chooses continuous Analysis inverse cam roots.
It loads no CAD/model/browser and does not qualify cameras, recover historical
settings, or measure any matching stage. Original frozen root choices/costs remain
immutable; alternative rod projections are predictions, never source observations.
Synthesis presenter-to-spin retains one actual machine image with openly chosen
principal-point/focal framing keys, not a second body or a measured camera fit.
Synthesis cone-overview retains a two-FIT chosen perspective-camera similarity.
Cam-rod uses a root-selected upright three-original-FIT fixed-intrinsics SQPNP
physical pose; former similarities are historical/unaccepted evidence only.
Independent qualification remains missing; CHECKs never enter camera objectives.
Synthesis wheel-macro uses only its original wheel-centre FIT and actual GPU
centre for a chosen principal-point translation; its hanger CHECK stays held out.
Analysis's stationary full-front shot holds its original frame428 CPU FIT camera
as a declared same-shot transfer. Independent focal/distance fit gauges are not
a physical trajectory; seed CPU diagnostics do not qualify held exposures/GPU.
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
        self.analysis_held_camera = self.analysis_held_camera_packet() if self.analysis else None
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
        self.analysis_snapshots, self.analysis_continuity = None, None
        if self.analysis:
            self.analysis_snapshots, self.analysis_continuity = self.continue_analysis_roots()
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
        self.presenter_reframing = None
        self.synthesis_coarse_framing = None
        self.synthesis_wheel_framing = None
        if not self.analysis:
            self.presenter_reframing = self.presenter_reframing_keys()
            self.synthesis_coarse_framing = self.synthesis_coarse_framing_packet()
            self.synthesis_wheel_framing = self.synthesis_wheel_framing_packet()
            transition = self.shots["presenter-to-spin"]
            for frame in self.data["frames"]:
                if frame["shotId"] == transition["id"]:
                    # The original sparse observations and actual source-image
                    # inspection show one body, not the legacy two-layer guess.
                    frame["views"] = [{"id":"main", "rectSourcePixels":[0,0,self.data["source"]["width"],self.data["source"]["height"]],
                                       "presentation":"native", "camera":frame.get("camera"),
                                       "mechanicalState":copy.deepcopy(frame.get("mechanicalState", {}))}]
            fps = self.data["source"]["fps"]["numerator"] / self.data["source"]["fps"]["denominator"]
            # Coverage labels are rounded decimals. Use the cut-clock cadence and
            # integer-frame tolerance from common, not a near-duplicate event key.
            # Off-cadence events and distinct native exposures remain separate.
            retained_changes = [
                round(t * fps) / fps if abs(t * fps - round(t * fps)) < 1e-6 else t
                for t in self.data.get("coverage", {}).get("changeTimesSeconds", [])
                if transition["startSeconds"] <= t < transition["endSeconds"]]
            self.data.setdefault("compactChangeTimesSeconds", []).extend(
                retained_changes + [key["decodedTimeSeconds"] for key in self.presenter_reframing["keys"]])

    def analysis_held_camera_packet(self):
        """Pin original own-shot evidence before any generated controls mutate it."""
        path = "web/content/6dW6VYXp9HM.observations.json"
        shot = self.shots["analysis-06"]
        reason = "Whole machine front held steady; presenter gestures and two explanatory text panels appear."
        if (shot["startSeconds"] != 14.2142 or shot["endSeconds"] != 33.26656666666667
                or shot["startDecodedFrameIndex"] != 426 or shot["reason"] != reason
                or shot["classification"] != "machine" or shot["visibleMachine"] is not True):
            raise ValueError("Analysis held-camera stationary source-shot evidence changed.")
        seeds = [frame for frame in self.data["frames"] if frame.get("decodedFrameIndex") == 428]
        if len(seeds) != 1:
            raise ValueError("Analysis held-camera seed must be the unique original native frame428.")
        seed = seeds[0]
        time = 14.280933333333333
        image = {"frameIndex":428,
                 "sha256Bgr8":"b4962c9cfc54a1db883f53e876fd963014fc72137dce801afebb24c933fff09b",
                 "sourceSha256":"5fc75341c088475bdcbad1764a8d99269f51bc287495063072a760a935319a52",
                 "width":1920,"height":1080,"pixelFormat":"bgr8"}
        if (seed["shotId"] != shot["id"] or seed["timeSeconds"] != time
                or seed["decodedTimeSeconds"] != time or seed["sourceImage"] != image
                or self.data["source"]["sha256"] != image["sourceSha256"]
                or [self.data["source"]["width"],self.data["source"]["height"]] != [1920,1080]):
            raise ValueError("Analysis held-camera original image/native PTS identity changed.")
        camera = seed["camera"]
        expected = {
            "positionMetres":[0.6714995433205075,3.78695830573904,-15.657471757084883],
            "quaternion":[-0.0002415678980059538,0.9944457393959518,0.10286732680589782,0.022269398689636514],
            "verticalFovDegrees":3.925928960444055,
            "principalPointViewportPixels":[960,540],
            "fitRmsPx":9.91117124441934,"fitMaxPx":16.029842785207453,
            "heldOutMaxPx":3.8007531809451782,"thresholdPx":38.4,"status":"passed",
            "intrinsicsEvidence":"Square pixels and image-centre principal point; focal fitted only to fitting landmarks.",
            "intrinsicsIdentifiability":"Noncoplanar source fit","intrinsicsAtSearchBoundary":False,
            "projection":"pinhole; square pixels; centre or explicitly fixed/fitted principal point; no fitted lens distortion",
            "coordinateConvention":"camera-to-CAD-world; quaternion xyzw; looks along local -Z with local +Y up",
            "viewportSourcePixels":[0,0,1920,1080],"presentation":"native"}
        if any(camera.get(key) != value for key,value in expected.items()):
            raise ValueError("Analysis held-camera original CPU camera/fit metadata changed.")
        fits = {"wheel.center","feed-knob.center","cross-screw-6","cross-screw-5","cross-screw-2","cross-screw-1"}
        checks = {"paperbar-clamp-outer","paperbar-clamp-inner"}
        landmarks = seed["landmarks"]
        if (len(landmarks) != 8
                or {(point["anchorId"],point["role"]) for point in landmarks}
                != {(anchor,"fit") for anchor in fits} | {(anchor,"check") for anchor in checks}
                or any(point["status"] != "observed" or point["method"] != "optical-flow"
                       or len(point["pixel"]) != 2 or not all(math.isfinite(v) for v in point["pixel"])
                       or point["uncertaintyPx"] != (3 if point["role"] == "fit" else 2)
                       for point in landmarks)):
            raise ValueError("Analysis held-camera original 6FIT/2CHECK landmark roles changed.")
        if (len(camera["fitWeights"]) != 6
                or {(row["anchorId"],row["weight"]) for row in camera["fitWeights"]} != {(anchor,1) for anchor in fits}
                or len(camera["checkErrors"]) != 2
                or {row["anchorId"] for row in camera["checkErrors"]} != checks):
            raise ValueError("Analysis held-camera FIT objective or independent CHECK diagnostics changed.")
        points = {point["anchorId"]:point for point in landmarks}
        check_errors = {"paperbar-clamp-outer":3.8007531809451782,"paperbar-clamp-inner":3.3813087840031497}
        check_projections = {"paperbar-clamp-outer":[1140.7694742063195,764.7990833195308],
                             "paperbar-clamp-inner":[1106.193085782771,764.9962318971221]}
        for row in camera["checkErrors"]:
            if (row["observedPixel"] != points[row["anchorId"]]["pixel"]
                    or row["errorPx"] != check_errors[row["anchorId"]]
                    or row["projectedPixel"] != check_projections[row["anchorId"]]):
                raise ValueError("Analysis held-camera CHECK source pixels/CPU errors changed.")
        views = common.source_views(seed,self.data)
        if (len(views) != 1 or not self.is_analysis_held_view(seed,views[0])
                or views[0].get("camera") != camera):
            raise ValueError("Analysis held-camera seed is not the original full-frame native main composition.")
        # Geometry only: original 'passed'/residuals belong to this CPU seed,
        # never to transferred exposures or a rendered matching stage.
        held = {key:copy.deepcopy(camera[key]) for key in
                ("positionMetres","quaternion","verticalFovDegrees","principalPointViewportPixels")}
        return {"status":"chosen-same-shot-hold","family":"analysis-06:main:source428-held",
                "sourceObservations":path,"shot":copy.deepcopy(shot),
                "seed":{"decodedFrameIndex":428,"decodedTimeSeconds":time,"timeSeconds":time,
                        "sourceImage":copy.deepcopy(image),"originalCpuCamera":copy.deepcopy(camera),
                        "originalLandmarks":copy.deepcopy(landmarks)},
                "camera":held,"application":{"shotId":"analysis-06","viewId":"main",
                                            "rectSourcePixels":[0,0,1920,1080],"presentation":"native",
                                            "appliedViewCount":0,"appliedExposures":[]},
                "interpretation":"Original shot evidence describes a stationary full-front machine composition; presenter gestures/text panels are not camera movement. Independent per-exposure CPU fits changed focal/distance gauge: linearly interpolating their positions and FOVs introduced unsupported magnification, not an observed physical camera trajectory. Hold the one original frame428 own-shot 6FIT/2CHECK camera across this same composition. Original camera observations, FIT/CHECK pixels and roles, source input/pose and other camera families remain unchanged. Original seed status passed is CPU-only; the hold is an authored same-shot transfer, not historical camera recovery, independent per-exposure fitting or GPU/stage qualification."}

    @staticmethod
    def is_analysis_held_view(frame, view):
        return (frame["shotId"] == "analysis-06" and view["id"] == "main"
                and view["rectSourcePixels"] == [0,0,1920,1080]
                and view.get("presentation","native") == "native"
                and not common.resolve_warp(view) and not common.compact_composite(view))

    @staticmethod
    def analysis_held_exposure(frame, view):
        image = frame.get("sourceImage")
        if not image or image.get("frameIndex") is None or frame.get("decodedTimeSeconds") is None:
            raise ValueError("Analysis held-camera application lacks retained native image/PTS identity.")
        return {"timeSeconds":frame["timeSeconds"],"decodedTimeSeconds":frame["decodedTimeSeconds"],
                "decodedFrameIndex":image["frameIndex"],"viewId":view["id"]}

    def presenter_reframing_keys(self):
        """Associate coarse inspection hints with immutable original native PTS.

        Bounds are authoring hints from the single visible front-facing body.
        They are not landmark measurements, independent pixel oracles or FITs.
        """
        transition = self.shots["presenter-to-spin"]
        donor = max((frame for frame in self.data["frames"]
                     if frame["shotId"] == "intro-machine"
                     and frame["decodedTimeSeconds"] < transition["startSeconds"]
                     and common.compact_camera(frame.get("camera"))),
                    key=lambda frame:frame["decodedTimeSeconds"])
        camera = donor["camera"]
        baseline = {name:copy.deepcopy(camera[name]) for name in
                    ("positionMetres","quaternion","verticalFovDegrees","principalPointViewportPixels")
                    if name in camera}
        hints = [(25.95,570.,930.), (26.03,467.,805.), (26.07,401.,752.),
                 (26.14,330.,678.), (26.56,65.,392.)]
        keys = []
        for nominal,left,right in hints:
            source = nearest(self.data["frames"],nominal,lambda frame:frame["decodedTimeSeconds"])
            keys.append({"nominalInspectionTimeSeconds":nominal,
                         "decodedTimeSeconds":source["decodedTimeSeconds"],
                         "sourceFrameIndex":source["sourceFrameIndex"],
                         "sourceImage":copy.deepcopy(source.get("sourceImage")),
                         "coarseDisplayBodyXBoundsPixels":[left,right]})
        return {"kind":"chosen-single-body-source-informed-framing",
                "sourceViews":["main"], "measurementStatus":"unmeasured",
                "sourceLineage":"web/content/8KmVDxkia_w.track.json",
                "sourceSha256":self.data["source"]["sha256"],
                "displayViewportPixels":[1568,882],
                "keys":keys, "baselineCamera":baseline,
                "baselineDecodedTimeSeconds":donor["decodedTimeSeconds"],
                "baselineSourceImage":copy.deepcopy(donor.get("sourceImage")),
                "coarseDisplayBodyHeightsPixels":[800.,746.],
                "chosenDisplayVerticalCentrePixels":445.,
                "chosenDisplayVerticalShiftPixels":20.,
                "interpretation":"Actual inspected source has one front-facing machine moving middle-to-left while an opaque black image boundary covers the presenter. Nominal inspection hints are attached to nearest existing original native PTS, not declared exact independent image measurements. Horizontal hints are coarse; linear height/vertical-centre interpolation and held front-camera orientation are chosen. Missing per-key original image hashes remain null. Source pixels, uncertainties and source-time tolerance are unchanged; no alpha, warp, camera yaw or geometry change."}

    def presenter_reframing_camera(self, frame):
        packet = self.presenter_reframing
        keys = packet["keys"]
        time = frame["decodedTimeSeconds"]
        first,last = keys[0],keys[-1]
        time = max(first["decodedTimeSeconds"],min(last["decodedTimeSeconds"],time))
        lower,upper = first,first
        for key in keys:
            if key["decodedTimeSeconds"] <= time:
                lower = upper = key
            else:
                upper = key
                break
        interval = upper["decodedTimeSeconds"]-lower["decodedTimeSeconds"]
        fraction = (time-lower["decodedTimeSeconds"])/interval if interval else 0.
        centre = lambda key:sum(key["coarseDisplayBodyXBoundsPixels"])/2
        x = centre(lower)+(centre(upper)-centre(lower))*fraction
        progress = (time-first["decodedTimeSeconds"])/(last["decodedTimeSeconds"]-first["decodedTimeSeconds"])
        height_start,height_end = packet["coarseDisplayBodyHeightsPixels"]
        scale = (height_start+(height_end-height_start)*progress)/height_start
        width,height = self.data["source"]["width"],self.data["source"]["height"]
        display_width,display_height = packet["displayViewportPixels"]
        origin = [centre(first)*width/display_width,
                  packet["chosenDisplayVerticalCentrePixels"]*height/display_height]
        target = [x*width/display_width,
                  origin[1]+packet["chosenDisplayVerticalShiftPixels"]*progress*height/display_height]
        camera = copy.deepcopy(packet["baselineCamera"])
        principal = camera.get("principalPointViewportPixels", [width/2,height/2])
        camera["principalPointViewportPixels"] = [target[i]+scale*(principal[i]-origin[i]) for i in range(2)]
        camera["verticalFovDegrees"] = math.degrees(2*math.atan(
            math.tan(math.radians(camera["verticalFovDegrees"]/2))/scale))
        note = "Chosen single-body presenter reframe: retained pre-transition front-camera position/quaternion, coarse actual source-body horizontal framing hints at original native PTS, and chosen height/vertical-centre interpolation. Principal-point/FOV changes are source-informed, not source FIT/CHECK residuals, independent pixel oracles, recovered camera history or stage qualification. One original main view, no outgoing/incoming duplicate bodies or invented crossfade."
        return camera,note

    @staticmethod
    def framing_gpu_sample(path, shot, time, ids, native, source, media_time, revision, statuses):
        """Read exact retained evidence; reject changed/mismatched GPU inputs."""
        raw = (ROOT / path).read_bytes()
        report = json.loads(raw)
        rows = [row for row in report["samples"]
                if row["sourceShotId"] == shot and row["timeSeconds"] == time]
        if report["videoId"] != "8KmVDxkia_w" or len(rows) != 1:
            raise ValueError(f"Ambiguous GPU framing exposure in {path}: {shot}/{time}")
        row = rows[0]
        for anchor, centre, pixel, status in zip(ids,native,source,statuses):
            measurements = [point for point in row["measurements"]
                            if point["anchorId"] == anchor and point["viewId"] == "main"]
            if len(measurements) != 1:
                raise ValueError(f"Missing/duplicate GPU framing FIT {path}/{anchor}")
            point = measurements[0]
            expected = {"role":"fit","method":"gpu-readback","status":status,
                        "nativePixels":centre,"sourcePixels":pixel,"sourceUncertaintyPx":5,
                        "captureTimeSeconds":time,"nativeMediaTime":media_time,
                        "sourceDrawRevision":revision}
            if any(point.get(name) != value for name,value in expected.items()):
                raise ValueError(f"GPU framing FIT evidence changed: {path}/{anchor}")
        return row, hashlib.sha256(raw).hexdigest()

    def synthesis_coarse_framing_packet(self):
        """Bound own-shot approximate cameras to retained exact native evidence."""
        observations_path = "web/content/8KmVDxkia_w.observations.json"
        observations = load(observations_path)
        report_path = "web/.vite/verification-output/stage50-seed-clock-repaired-native-2026-10-01/8KmVDxkia_w.json"
        width, height = 1920, 1080
        target, span = self.envelope("cone", width/height)
        baseline = look_camera(target, -math.pi/2, 0.16, span, width/height)
        baseline["principalPointViewportPixels"] = [width/2, height/2]
        native = [[1075.8, 381.], [1595.4, 519.]]
        ids = ["crank-axis-back", "cylinder-axis-back"]
        definitions = [
            ("cone-overview", 62, 1487,
             "aa922fb2440eb43a0011f320de755b0f284a51d9c8af9368bea5809d469c976d",
             [[469, 329], [1430, 704]], 62.020291, 304)]
        keys = {}
        for shot, time, index, image_hash, source, media_time, revision in definitions:
            original = next(frame for frame in observations["frames"]
                            if frame["shotId"] == shot and frame["timeSeconds"] == time)
            image = original["sourceImage"]
            if (image["frameIndex"] != index or image["sha256Bgr8"] != image_hash
                    or image["width"] != width or image["height"] != height
                    or image["sourceSha256"] != self.data["source"]["sha256"]):
                raise ValueError(f"Original two-FIT framing image identity changed for {shot}")
            gpu_row, report_hash = self.framing_gpu_sample(
                report_path,shot,time,ids,native,source,media_time,revision,["passed","passed"])
            fits = []
            for anchor, pixel, centre in zip(ids, source, native):
                landmark = next(point for point in original["landmarks"] if point["anchorId"] == anchor)
                if (landmark["role"] != "fit" or landmark["status"] != "observed"
                        or landmark["pixel"] != pixel or landmark["uncertaintyPx"] != 5):
                    raise ValueError(f"Original two-FIT framing declaration changed for {shot}/{anchor}")
                fits.append({"anchorId":anchor, "role":"fit", "sourcePixels":pixel,
                             "sourceUncertaintyPx":5, "nativePixels":copy.deepcopy(centre),
                             "method":"gpu-readback"})
            dn = [native[1][i]-native[0][i] for i in range(2)]
            ds = [source[1][i]-source[0][i] for i in range(2)]
            native_length, source_length = math.hypot(*dn), math.hypot(*ds)
            if not (math.isfinite(native_length) and native_length > 0
                    and math.isfinite(source_length) and source_length > 0):
                raise ValueError(f"Degenerate two-FIT framing vectors for {shot}")
            scale = source_length/native_length
            angle = math.atan2(dn[0]*ds[1]-dn[1]*ds[0], dn[0]*ds[0]+dn[1]*ds[1])
            if not (math.isfinite(scale) and scale > 0 and math.isfinite(angle)):
                raise ValueError(f"Nonfinite or nonpositive two-FIT framing for {shot}")
            c, s = math.cos(angle), math.sin(angle)
            principal = baseline["principalPointViewportPixels"]
            p = [native[0][i]-principal[i] for i in range(2)]
            new_principal = [source[0][0]-scale*(c*p[0]-s*p[1]),
                             source[0][1]-scale*(s*p[0]+c*p[1])]
            camera = copy.deepcopy(baseline)
            # Postmultiply by a camera-local +Z roll. In y-down viewport pixels,
            # inverse camera rotation and the Y flip yield the same +angle.
            x, y, z, w = baseline["quaternion"]
            sh, ch = math.sin(angle/2), math.cos(angle/2)
            camera["quaternion"] = [x*ch+y*sh, y*ch-x*sh, z*ch+w*sh, w*ch-z*sh]
            camera["verticalFovDegrees"] = math.degrees(2*math.atan(
                math.tan(math.radians(baseline["verticalFovDegrees"]/2))/scale))
            camera["principalPointViewportPixels"] = new_principal
            keys[shot] = {
                "timeSeconds":time, "decodedTimeSeconds":original["decodedTimeSeconds"],
                "sourceImage":copy.deepcopy(image), "viewId":"main",
                "objectiveFITs":fits,
                "originalLandmarks":copy.deepcopy(original["landmarks"]),
                "originalUnavailable":copy.deepcopy(original.get("unavailable", [])),
                "gpuEvidence":{"report":report_path, "reportSha256":report_hash,
                               "sampleSelector":{"sourceShotId":shot,"timeSeconds":time,"viewId":"main"},
                               "captureTimeSeconds":time, "nativeMediaTime":media_time,
                               "sourceDrawRevision":revision, "method":"gpu-readback"},
                "positiveFocalScale":scale, "screenRotationRadians":angle,
                "chosenCamera":camera,
                "unusableFITs":[],
                "eligibleViewCount":0, "appliedViewCount":0, "appliedSeedExposureCount":0,
                "excludedCHECKs":[],
                "qualification":"missing: qualified fitter requires 6 FIT / 2 CHECK; two-pair framing is not a source-fit camera"}
        original = next(frame for frame in observations["frames"]
                        if frame["shotId"] == "cam-rod" and frame["timeSeconds"] == 100)
        keys["cam-rod"] = self.synthesis_camrod_physical_pose({
            "timeSeconds":100,"decodedTimeSeconds":original["decodedTimeSeconds"],
            "sourceImage":copy.deepcopy(original["sourceImage"]),"viewId":"main",
            "originalLandmarks":copy.deepcopy(original["landmarks"]),
            "originalUnavailable":copy.deepcopy(original.get("unavailable", [])),
            "excludedCHECKs":["pinion-pivot-back"],
            "eligibleViewCount":0,"appliedViewCount":0,"appliedSeedExposureCount":0},observations)
        return {
            "kind":"chosen-own-shot-source-informed-camera-framing",
            "status":"source-informed-chosen-approximate",
            "sourceAcceptance":"unavailable", "historicalPose":"unobserved",
            "nativeQualification":"deferred",
            "sourceObservations":observations_path,
            "baselineGpuReport":report_path,
            "baselineGpuReportSha256":keys["cone-overview"]["gpuEvidence"]["reportSha256"],
            "viewportPixels":[width,height], "baselineCamera":baseline,
            "scope":"Only full-frame native main views of exact cone-overview and cam-rod shots, requiring the identical base fallback generated from authoritative *.track.json camera nulls. Generated *.source-track.json is not an input; former intermediate/similarity or already-chosen camera matches are unreachable and removed. Cameras are held only within their own shots, never transferred to other families.",
            "baselineFramingEquations":"Active cone-overview two-FIT stage only: s=|source1-source0|/|native1-native0|; theta=atan2(cross(dNative,dSource),dot(dNative,dSource)); p'=source0-s*R(theta)*(native0-p); FOV'=2*atan(tan(FOV/2)/s); q'=q*qLocalZ(theta). Base FOV=30deg, p=(960,540). Cam-rod now uses shots.cam-rod.physicalPoseSelection: fixed-intrinsics SQPNP proper-pose conversion, not these similarity equations; former cam-rod stages are historical/unaccepted.",
            "baselineCameraLineage":{"track":"web/content/8KmVDxkia_w.source-track.json",
                                     "revision":"f02c25713","seedTimesSeconds":[62,100],
                                     "cameraStatus":"source-informed-chosen",
                                     "verification":"external-review-claim-not-generator-asserted",
                                     "interpretation":"Reviewer verified both original main cameras equal this fallback at the cited revision; reports contain marker readbacks, not camera records."},
            "interpretation":"Cone-overview retains two original FIT/GPU pairs for chosen similarity framing. Cam-rod instead uses all three original source FITs and actual same-draw native world coordinates for a chosen fixed-intrinsics physical pose; its previous roll/focal/principal-point similarities are retained only as historical unaccepted evidence. All source pixels/declarations, native geometry/poses/bounds, inputs and clocks remain unchanged. Independent CHECKs never enter either objective or pose selection. Neither unique historical camera recovery nor GPU/50/20/10/5% acceptance is claimed.",
            "limitations":"Cone-overview similarity cannot correct parallax. Cam-rod's three-point pose has ambiguous physical branches and depends on chosen intrinsics/qualitative upright prior; sparse zero FIT residual is not qualification. Only three FIT depths are proven; complete visible geometry and source-shot continuity require root GPU/visual inspection.",
            "shots":keys}

    def synthesis_camrod_physical_pose(self, previous, observations):
        """Publish root's FIT-only upright choice from a pinned sparse probe."""
        path = "web/.vite/verification-output/synthesis-camrod-sqpnp-probe-2026-10-01.json"
        raw = (ROOT / path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != "5a9f17e64671f84478fbdbc6de8cc620ae88932cfae78c3551dd029bc5cc1321":
            raise ValueError("Chosen cam-rod physical probe artifact changed")
        probe = json.loads(raw)
        lineage = probe["lineage"]
        receipt_record = lineage["actualWorldReceipt"]
        receipt_raw = (ROOT / receipt_record["path"]).read_bytes()
        receipt_hash = hashlib.sha256(receipt_raw).hexdigest()
        if receipt_hash != receipt_record["sha256"] or receipt_hash != "222d69eb315c39366e93cdcaacadd19a9074b153fa6f0db42d3ff5f9d2af8dbc":
            raise ValueError("Chosen cam-rod actual world receipt changed")
        receipt = json.loads(receipt_raw)
        if (probe["status"] != "candidate-enumeration-only"
                or probe["selection"] != "none; retain every returned pose; CHECK not evaluated"
                or probe["chosenIntrinsics"]["verticalFovDegrees"] != 30
                or probe["chosenIntrinsics"]["principalPointViewportPixels"] != [960,540]
                or lineage["sourceImage"] != previous["sourceImage"]
                or lineage["sourceSha256"] != self.data["source"]["sha256"]
                or lineage["nativeModelSha256"] != self.native["modelSha256"]
                or lineage["nativeDenominator"] != 435
                or lineage["originalLandmarks"] != previous["originalLandmarks"]
                or lineage["sceneCurrentSourceSha256"] != hashlib.sha256((WEB / "src/scene.ts").read_bytes()).hexdigest()):
            raise ValueError("Chosen cam-rod source/native/code/intrinsics lineage differs")
        frame = next(frame for frame in self.data["frames"]
                     if frame["shotId"] == "cam-rod" and frame["timeSeconds"] == 100)
        value, _ = self.input(frame,"cone")
        if common.compact_input(value) != lineage["completeInput"]:
            raise ValueError("Chosen cam-rod world capture complete input differs from current seed")
        snapshot, capture = receipt["snapshot"], receipt["renderedLandmarks"]
        rendered = next(view for view in snapshot["views"] if view["id"] == "main")["renderedMechanism"]
        identity = receipt["frameIdentity"]
        if (identity["sourceImage"] != previous["sourceImage"] or identity["shotId"] != "cam-rod"
                or identity["viewId"] != "main" or identity["timeSeconds"] != 100
                or identity["decodedTimeSeconds"] != previous["decodedTimeSeconds"]
                or snapshot["modelProvenance"]["identity"] != "matched"
                or snapshot["modelProvenance"]["observedSha256"] != lineage["nativeModelSha256"]
                or rendered["input"] != lineage["completeInput"] or rendered["timeSeconds"] != 100
                or rendered["sourceDrawRevision"] != lineage["sourceDrawRevision"]
                or capture["status"] != "captured" or capture["timeSeconds"] != 100 or capture["viewId"] != "main"):
            raise ValueError("Chosen cam-rod same-draw world/input receipt binding differs")
        fit_ids = ["crank-axis-back","cylinder-axis-back","rocker-shaft-back"]
        for anchor, row in zip(fit_ids,probe["exactInputs"]):
            original = next(point for point in previous["originalLandmarks"] if point["anchorId"] == anchor)
            semantic = next(point for point in observations["anchors"] if point["id"] == anchor)
            marker = next(point for point in capture["landmarks"] if point["id"] == anchor)
            if (row["anchorId"] != anchor or row["sourceDeclaration"] != original
                    or original["role"] != "fit" or original["status"] != "observed"
                    or row["semanticNativeAnchor"] != semantic
                    or row["actualRenderedWorldMetres"] != marker["worldMetres"]
                    or marker["worldReason"] is not None
                    or not all(math.isfinite(v) for v in row["actualRenderedWorldMetres"])):
                raise ValueError(f"Chosen cam-rod original FIT/actual world binding differs: {anchor}")
        if len(probe["exactInputs"]) != 3 or len(probe["candidates"]) != probe["returnedPoseCount"] or probe["returnedPoseCount"] != 2:
            raise ValueError("Chosen cam-rod sparse enumeration changed")
        candidates = copy.deepcopy(probe["candidates"])
        fit_centroid = [sum(row["actualRenderedWorldMetres"][i] for row in probe["exactInputs"])/3 for i in range(3)]
        eligible = []
        for candidate in candidates:
            fits = candidate["FITs"]
            physical = (candidate["poseValidity"] == "physical-sparse-candidate"
                        and abs(candidate["properRotationDeterminant"]-1) < 1e-8
                        and abs(candidate["quaternionNorm"]-1) < 1e-8
                        and [point["anchorId"] for point in fits] == fit_ids
                        and all(math.isfinite(point["positiveDepthMetres"]) and point["positiveDepthMetres"] > 0.001 for point in fits))
            upright = abs(candidate["angularRollDegreesRelativeWorldY"]) <= 15 and candidate["upWorldYAlignment"] > 0
            back_side = candidate["camera"]["positionMetres"][2] > fit_centroid[2] and candidate["forwardWorld"][2] < 0
            if physical and upright and back_side:
                eligible.append(candidate)
            candidate["chosenPolicyDecision"] = "eligible" if physical and upright and back_side else "rejected-qualitative-upright-or-CAD-positiveZ-side-prior"
        if len(eligible) != 1 or eligible[0]["candidateId"] != "sqpnp-001":
            raise ValueError("Root-selected cam-rod upright sparse pose is no longer uniquely eligible")
        chosen = eligible[0]
        expected = {"positionMetres":[-0.119936139775151,0.1739581164103444,0.5790659466866046],
                    "quaternion":[-0.005039273586140318,-0.11877097134333389,0.021688863426512862,0.9926719776900882],
                    "verticalFovDegrees":30.,"principalPointViewportPixels":[960.,540.]}
        if chosen["camera"] != expected:
            raise ValueError("Root-selected cam-rod camera differs from pinned chosen pose")
        historical = {
            "status":"retired-unaccepted",
            "immutablePacket":{"gitRevision":"33197abb1","path":"web/content/8KmVDxkia_w.source-track.json",
                               "jsonPointer":"/evidence/synthesisCoarseFraming/shots/cam-rod"},
            "reports":[
                {"path":"web/.vite/verification-output/stage50-seed-clock-repaired-native-2026-10-01/8KmVDxkia_w.json","stage":"original-side-fallback"},
                {"path":"web/.vite/verification-output/synthesis-fit-framing-native-2026-10-01/8KmVDxkia_w.json","stage":"two-FIT-similarity"},
                {"path":"web/.vite/verification-output/synthesis-three-fit-framing-native-2026-10-01/8KmVDxkia_w.json","stage":"three-FIT-similarity",
                 "sha256":"666d3b3b388d3636b8699070ac9cf39c046f72df0106200ebbf0746fca375c02"}],
            "reportHashAuthority":"Original/two-FIT report hashes and complete old derivation are retained in immutable revision33197abb1; the three-FIT report digest was computed by root during final review. Retired reports are provenance links, not active generation dependencies or recomputed hashes.",
            "rootReportedThreeFITMaximumConservativeErrorPx":168.49,
            "rootReportedThreeFITConservativeCHECKErrorPx":118.846,
            "interpretation":"Retired two/three-FIT image-plane similarities were never qualified. Root actual source/native inspection found side-looking direction/large roll inconsistent with photographed upright composition despite smaller sparse errors. CHECK baseline/old GPU errors were inspected historically, but CHECK was excluded from all objectives and from the subsequent SQPNP enumeration/branch selection. Historical calculations are neither recomputed nor active camera guards."}
        key = {name:copy.deepcopy(previous[name]) for name in (
            "timeSeconds","decodedTimeSeconds","sourceImage","viewId","originalLandmarks",
            "originalUnavailable","excludedCHECKs","eligibleViewCount","appliedViewCount","appliedSeedExposureCount")}
        key.update({"kind":"chosen-three-original-FIT-fixed-intrinsics-physical-pose",
                    "status":"source-informed-chosen-approximate","nativeQualification":"deferred",
                    "sourceAcceptance":"unavailable","historicalPose":"unobserved",
                    "chosenCamera":copy.deepcopy(chosen["camera"]),
                    "objectiveFITs":copy.deepcopy(probe["exactInputs"]),
                    "historicalSimilarityFraming":historical,
                    "qualification":"Only3FIT/1CHECK, not qualified6FIT/2CHECK; complete-geometry depths and GPU source matching remain unverified",
                    "physicalPoseSelection":{"probe":path,"probeSha256":digest,
                        "worldReceipt":receipt_record["path"],"worldReceiptSha256":receipt_hash,
                        "lineage":copy.deepcopy(lineage),"candidates":candidates,"chosenCandidateId":"sqpnp-001",
                        "chosenQualitativeMaximumAbsoluteRollDegrees":15.,
                        "chosenCADPositiveZSidePrior":{"FITCentroidWorldMetres":fit_centroid,
                            "rule":"Camera worldZ > original-three-FIT centroid worldZ and forwardWorldZ < 0, matching original back=CAD+Z/source-right=CAD+X semantics; not an arbitrary CAD-front yaw0."},
                        "generationDependencies":"Active physical choice requires only pinned SQPNP probe/world receipt, original source semantic/FIT identity, matched native hash and unchanged complete seed input. Strict current scene.ts SHA byte gate remains: any byte change requires recapture/rebinding, including otherwise cosmetic edits; it is intentionally not waived. Retired similarity reports/committed packet are references only. Authoritative inputs come from *.track.json, never generated *.source-track.json.",
                        "reason":"Root selected only on original qualitative upright columns/no observed large roll and original back=CAD+Z semantic mapping. Both physical sparse branches fit the same three FITs; sqpnp-000's64.65deg roll conflicts with the declared chosen15deg upright/CAD-positiveZ-side prior. This prior is not measured historical roll. CHECK baseline and prior GPU errors were historically inspected, but CHECK was excluded from SQPNP enumeration objective and branch selection; candidate CHECKs were not projected/ranked before root selected001. Post-selection held-out measurements are separate evidence, not retroactive selection inputs.",
                        "depthScope":"Only three actual original FIT points; no whole-native-geometry positive-depth or GPU acceptance claim",
                        "poseConversion":"OpenCV world-to-camera R,t: position=-R^T*t; cameraToWorld=R^T*diag(1,-1,-1); quaternion xyzw. Fixed chosen FOV30, PP(960,540); native XYZ comes from the actual completed-draw Float32 marker vertex, not raster pixels or catalogue assumptions."}})
        return key

    def synthesis_coarse_camera(self, frame, view, camera, note):
        packet = self.synthesis_coarse_framing
        key = packet["shots"].get(frame["shotId"]) if packet else None
        if (key is None or view["id"] != "main"
                or view["rectSourcePixels"] != [0,0,1920,1080]
                or view.get("presentation", "native") != "native"
                or common.resolve_warp(view)):
            return camera, note
        key["eligibleViewCount"] += 1
        base = packet["baselineCamera"]
        matched = math.isclose(camera.get("verticalFovDegrees",0),base["verticalFovDegrees"],rel_tol=0.,abs_tol=1e-9)
        for name in ("positionMetres","quaternion","principalPointViewportPixels"):
            values = camera.get(name,[960.,540.]) if name == "principalPointViewportPixels" else camera.get(name,[])
            if (len(values) != len(base[name])
                    or any(not math.isclose(a,b,rel_tol=0.,abs_tol=1e-9) for a,b in zip(values,base[name]))):
                matched = False
                break
        if not matched:
            return camera, note
        key["appliedViewCount"] += 1
        if frame.get("sourceImage") == key["sourceImage"]:
            key["appliedSeedExposureCount"] += 1
        if frame["shotId"] == "cam-rod":
            return copy.deepcopy(key["chosenCamera"]), (
                "Chosen cam-rod own-shot physical SQPNP pose: three original FIT source pixels and actual same-input native world markers constrain a fixed chosen FOV30/centred-PP camera. Root selected the upright CAD+Z-facing branch using a declared15deg roll prior, never the held-out pinion CHECK. Position/forward direction now replace the visually mismatched former similarity camera; native geometry/poses/inputs/source declarations are unchanged. Only3FIT depths are proven, not complete geometry, historical camera, qualified6FIT/2CHECK or GPU/stage acceptance. Previous similarity evidence is historical/unaccepted. See evidence.synthesisCoarseFraming.shots.cam-rod.physicalPoseSelection.")
        return copy.deepcopy(key["chosenCamera"]), (
            "Chosen cone-overview two-FIT perspective framing: original source pixels and actual GPU marker centres choose local-Z roll, positive focal scale and principal point only; baseline position/forward direction and perspective depth remain unchanged. Held within this shot, not a unique historical camera, qualified source fit or GPU/stage acceptance. Independent 6FIT/2CHECK qualification is missing; no CHECK enters framing. Cam-rod's former similarities are historical/unaccepted and replaced separately by its chosen upright physical pose. See evidence.synthesisCoarseFraming. "+note)

    def synthesis_wheel_framing_packet(self):
        """Choose wheel-macro translation from its single original FIT only."""
        path = "web/content/8KmVDxkia_w.observations.json"
        observations = load(path)
        original = next(frame for frame in observations["frames"]
                        if frame["shotId"] == "wheel-macro" and frame["timeSeconds"] == 252.00175)
        image = original["sourceImage"]
        if (image["frameIndex"] != 6042
                or image["sha256Bgr8"] != "fc827f2d41c467a3a8bdfa73379f0e65e8a9988b1e47198c06a34624f97a5f91"
                or image["sourceSha256"] != self.data["source"]["sha256"]
                or image["width"] != 1920 or image["height"] != 1080):
            raise ValueError("Original wheel-macro manual seed identity changed")
        fit = next(point for point in original["landmarks"] if point["anchorId"] == "wheel-centre")
        if (fit["role"] != "fit" or fit["status"] != "observed" or fit["method"] != "manual"
                or fit["pixel"] != [1145,555] or fit["uncertaintyPx"] != 5):
            raise ValueError("Original wheel-centre manual FIT declaration changed")
        check = next(point for point in original["landmarks"] if point["anchorId"] == "wheel-hanger-screw")
        if check["role"] != "check" or check["status"] != "observed":
            raise ValueError("Original wheel hanger independent CHECK declaration changed")
        report = "web/.vite/verification-output/stage50-seed-clock-repaired-native-2026-10-01/8KmVDxkia_w.json"
        row, report_hash = self.framing_gpu_sample(
            report,"wheel-macro",252.00175,["wheel-centre"],[[959.4,547.8]],
            [[1145,555]],252.00175,689,["passed"])
        if not any(point["anchorId"] == "wheel-hanger-screw" and point["role"] == "check"
                   for point in row["measurements"]):
            raise ValueError("Original wheel GPU independent CHECK role changed")
        target, span = self.envelope("wheel",1920/1080)
        baseline = look_camera(target,0.,0.12,span,1920/1080)
        baseline["principalPointViewportPixels"] = [960.,540.]
        native = next(point["nativePixels"] for point in row["measurements"]
                      if point["anchorId"] == "wheel-centre" and point["viewId"] == "main")
        offset = [fit["pixel"][i]-native[i] for i in range(2)]
        if not all(math.isfinite(value) for value in offset):
            raise ValueError("Nonfinite chosen wheel principal-point translation")
        camera = copy.deepcopy(baseline)
        camera["principalPointViewportPixels"] = [baseline["principalPointViewportPixels"][i]+offset[i] for i in range(2)]
        return {"kind":"chosen-wheel-macro-single-FIT-principal-point-translation",
                "status":"source-informed-chosen-approximate",
                "sourceAcceptance":"unavailable","historicalPose":"unobserved","nativeQualification":"deferred",
                "shotId":"wheel-macro","viewId":"main","timeSeconds":252.00175,
                "decodedTimeSeconds":original["decodedTimeSeconds"],"sourceImage":copy.deepcopy(image),
                "sourceObservations":path,"baselineCamera":baseline,"chosenCamera":camera,
                "objectiveFIT":{"anchorId":"wheel-centre","role":"fit","sourcePixels":copy.deepcopy(fit["pixel"]),
                                "sourceUncertaintyPx":5,"nativePixels":copy.deepcopy(native),"method":"gpu-readback"},
                "principalPointTranslationPixels":offset,
                "gpuEvidence":{"report":report,"reportSha256":report_hash,
                               "sampleSelector":{"sourceShotId":"wheel-macro","timeSeconds":252.00175,"viewId":"main"},
                               "captureTimeSeconds":252.00175,"nativeMediaTime":252.00175,"sourceDrawRevision":689},
                "cameraBinding":"Root-confirmed existing frontal wheel fallback; report has marker readbacks, not camera pose.",
                "originalLandmarks":copy.deepcopy(original["landmarks"]),
                "originalUnavailable":copy.deepcopy(original.get("unavailable", [])),
                "excludedCHECKs":["wheel-hanger-screw"],"eligibleViewCount":0,"appliedViewCount":0,"appliedSeedExposureCount":0,
                "equations":"PP'=PP+(originalFIT-nativeGPUFIT); position, quaternion, FOV and perspective depth unchanged.",
                "interpretation":"Only the original manual seed frame6042 wheel-centre FIT selects translation. The later original-frame6169 source inspection supports qualitative frontal composition, not new seed pixels. Original independent hanger CHECK is never an objective/ranking/selection input and no CHECK prediction is computed. Hold this chosen translation only in wheel-macro main; no spoke phase, source-visible motion, historical camera, parallax correction or qualified6FIT/2CHECK claim. One-pair translation residual is zero by construction before rasterization."}

    def synthesis_wheel_camera(self, frame, view, camera, note):
        packet = self.synthesis_wheel_framing
        if (packet is None or frame["shotId"] != "wheel-macro" or view["id"] != "main"
                or view["rectSourcePixels"] != [0,0,1920,1080]
                or view.get("presentation","native") != "native" or common.resolve_warp(view)):
            return camera,note
        packet["eligibleViewCount"] += 1
        base = packet["baselineCamera"]
        matched = math.isclose(camera.get("verticalFovDegrees",0),base["verticalFovDegrees"],rel_tol=0.,abs_tol=1e-9)
        for name in ("positionMetres","quaternion","principalPointViewportPixels"):
            values = camera.get(name,[960.,540.]) if name == "principalPointViewportPixels" else camera.get(name,[])
            if (len(values) != len(base[name])
                    or any(not math.isclose(a,b,rel_tol=0.,abs_tol=1e-9) for a,b in zip(values,base[name]))):
                matched = False
                break
        if not matched:
            return camera,note
        packet["appliedViewCount"] += 1
        if frame.get("sourceImage") == packet["sourceImage"]:
            packet["appliedSeedExposureCount"] += 1
        return copy.deepcopy(packet["chosenCamera"]), (
            "Chosen wheel-macro single-FIT principal-point translation: original manual wheel-centre seed and actual same-exposure GPU centre choose only screen offset. Position/orientation/FOV, source inputs/pixels and geometry are unchanged; independent hanger CHECK and moving spokes are not fit inputs. Unqualified1FIT/1CHECK, source-informed/chosen only, not historical camera or rendered acceptance. See evidence.synthesisWheelFraming. "+note)

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
        if self.analysis_held_camera and self.is_analysis_held_view(frame,view):
            application = self.analysis_held_camera["application"]
            application["appliedExposures"].append(self.analysis_held_exposure(frame,view))
            application["appliedViewCount"] += 1
            return copy.deepcopy(self.analysis_held_camera["camera"]), "Original Analysis frame428 same-shot held camera. "+self.analysis_held_camera["interpretation"]
        direct = common.compact_camera(view.get("camera") or (frame.get("camera") if view["id"] == "main" else None))
        if direct: return direct, "Retained source-derived camera family at this source exposure; registration/calibration or holding does not claim an independent per-exposure fit. Original CPU FIT/CHECK diagnostics remain source evidence, not a stage pass."
        if not self.analysis and shot == "presenter-to-spin":
            return self.presenter_reframing_camera(frame)
        if self.analysis and family == "bar" and view.get("presentation") == "horizontal-mirror":
            return common.compact_camera(self.candidate["nativeCameraRecord"]), "Single latest four-seed Analysis source FIT camera held/transferred across bank exposures with its genuine horizontal mirror; no per-exposure refit or new native/GPU qualification."
        same = [s for s in self.seeds if s[0] == shot]
        if same: return common.compact_camera(nearest(same,time,lambda x:x[1])[2]), "Nearest same-shot source camera, held over the unmeasured exposure; not independently fitted here."
        if family == "whole" and not ("spin" in shot or "inset" in shot or shot.startswith("endcard")):
            candidates = [s for s in self.seeds if s[0] in (("analysis-06","analysis-37") if self.analysis else ("intro-machine","final-presenter-machine"))]
            if candidates and (not self.analysis or int(shot[-2:]) not in (3,4,5,7,8)):
                return common.compact_camera(nearest(candidates,time,lambda x:x[1])[2]), "Related presenter/front composition source camera held as a coarse baseline, not a matched pose."
        if not self.analysis and family == "pen" and shot == "wheel-pen":
            camera = self.pinhole["actualFrozenFitterExperiments"][0]["actualFrozenFitterCameraRecord"]
            return common.compact_camera(camera), "Single Exact Source6330 CPU pinhole FIT candidate held across the wheel-pen shot, not fitted at each exposure; failed independent guide CHECK remains a diagnostic, not an exclusion."
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

    def continue_analysis_roots(self):
        """Continue the latent cam branch, not the independently fitted rocker pose.

        Both genuine inverse roots retain each recorded rocker endpoint. Choosing
        the lowest rod-pixel cost independently can switch between those roots
        and force an unobserved full rocker stroke between adjacent exposures.
        Seed each channel from its first frozen choice, then take the genuine
        root nearest its preceding cam angle. This is a chosen continuity rule,
        not recovered crank direction; cumulative crank/setup inputs are retained.
        """
        path = f"{ANALYSIS}/{self.candidate['selectedDerivation']}"
        fit = load(path)
        manifest = load(f"{ANALYSIS}/frozen-census-search-manifest.json")
        ceiling = manifest["unchangedHardConstraints"]["fullKnownAdditiveCeilingPx"]
        snapshots = sorted(copy.deepcopy(self.candidate["frames"]),
                           key=lambda row: row["sourceFrameIdentity"]["timeSeconds"])
        previous, changes = None, []
        first_index = snapshots[0]["frameIndex"]
        for row in snapshots:
            value, changed = row["chosenInput"], []
            # The frozen roots are cam angles, equal to phase offsets in this
            # zero-drive packet. Do not silently reinterpret another drive.
            if value["crankTurns"] != 0 or value["setup"]["coneSwingRad"] != 0 or value["setup"]["driveCrankOffsetTurns"] != 0:
                raise ValueError("Analysis inverse-root packet no longer has its frozen zero bank drive.")
            selected = []
            for j, roots in enumerate(row["allGenuineCamRootsRad"]):
                original = row["chosenRootIndices"][j]
                if value["phases"][j] != roots[original]:
                    raise ValueError(f"Analysis frozen phase/root mismatch at {row['frameIndex']}, channel {j+1}.")
                index = original if previous is None else min(
                    range(len(roots)),
                    key=lambda k: (abs(math.remainder(roots[k]-previous[j], 2*math.pi)),
                                   k != original, k))
                selected.append(index)
                if index == original:
                    continue
                score = fit["groupScores"][(row["frameIndex"]-first_index)*20+j]
                if score["camRoots"] != roots or score["chosenRootIndex"] != original:
                    raise ValueError(f"Analysis frozen root-cost identity mismatch at {row['frameIndex']}, channel {j+1}.")
                options = score.get("allFamilyRoots")
                if options is None and row["bodyFITAvailable"]:
                    raise ValueError(f"Analysis continuation lacks frozen rod source bounds at {row['frameIndex']}, channel {j+1}.")
                rod = options[1] if options is not None else None
                # A source-disambiguated orientation is not an interchangeable
                # latent witness. Refuse rather than replace that observation.
                if rod and (rod[index]["strictOutside"] != 0
                            or rod[index]["maximumKnownPx"] > ceiling
                            or not all(rod[index]["crossSectionValid"])
                            or not (rod[index]["minimumInteriorPixelMargin"] >= 0)):
                    raise ValueError(f"Analysis continuation conflicts with frozen rod source bounds at {row['frameIndex']}, channel {j+1}.")
                def prediction(k):
                    option = rod[k]
                    return {**{key: copy.deepcopy(option[key]) for key in (
                        "rootIndex", "camAngleRad", "maximumKnownPx", "strictOutside",
                        "minimumInteriorPixelMargin")},
                        "rawSourceCostSumSquares": sum(x*x for x in option["raw"]),
                        "predictedRodAxisViewportPixels": copy.deepcopy(option["line"])}
                changed.append({"channelIndex":j, "originalRootIndex":original,
                                "continuedRootIndex":index,
                                "originalPhaseRad":value["phases"][j],
                                "continuedPhaseRad":roots[index],
                                "rockerEndpointRad":row["rockerAnglesChosenWitnessRad"][j],
                                "frozenRodPredictions": [prediction(original), prediction(index)] if rod else None,
                                "bodyFITAvailable":row["bodyFITAvailable"]})
                value["phases"][j] = roots[index]
            previous = [roots[index] for roots,index in zip(row["allGenuineCamRootsRad"],selected)]
            row["chosenRootIndices"] = selected
            if changed:
                changes.append({"frameIndex":row["frameIndex"],
                                "sourceFrameIdentity":copy.deepcopy(row["sourceFrameIdentity"]),
                                "channels":changed})
        diagnostics = {
            "kind":"chosen-inverse-root-continuation",
            "rule":"First frozen root per channel, then nearest preceding genuine cam root modulo2pi; exact distance ties retain the frozen choice. No crank/setup/amplitude or source-pixel change.",
            "frozenCandidate":f"{ANALYSIS}/candidate.json",
            "frozenCandidateSha256":hashlib.sha256((ROOT / f"{ANALYSIS}/candidate.json").read_bytes()).hexdigest(),
            "frozenRootCosts":path,
            "frozenRootCostsSha256":hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
            "frozenSourceFitCeilingPx":ceiling,
            "interpretation":"Original independent root selection and costs remain frozen. Continued latent cam/rod orientations are chosen; recorded rocker endpoints are unchanged. Rod axes are inherited static predictions, NOT observations or current native/GPU qualification. All original connecting-rod source controls remain required.",
            "sourceAcceptance":False, "historyRecovered":False,
            "currentNativeQualification":"UNEXECUTED", "changedFrames":changes}
        return snapshots, diagnostics

    def input(self, frame, family):
        time = frame["decodedTimeSeconds"]
        if self.analysis:
            snapshots = self.analysis_snapshots
            first, last = snapshots[0]["sourceFrameIdentity"]["timeSeconds"], snapshots[-1]["sourceFrameIdentity"]["timeSeconds"]
            if family == "bar" and first <= time <= last:
                row = nearest(snapshots,time,lambda x:x["sourceFrameIdentity"]["timeSeconds"])
                return copy.deepcopy(row["chosenInput"]), "Frozen source FIT rocker/amplitude snapshot with nearest-previous genuine inverse cam-root continuation seeded from the first frozen branch. Latent phase/rod orientation is chosen, not historical crank recovery; original independent root choices, rod costs and alternative predictions remain in cpuDiagnostics.analysisRootContinuity. Source pixels and CHECKs are unchanged."
            # A source-window alone is not a measured crank trajectory. Hold the
            # nearest independently source-fitted complete input outside204 rather
            # than synthesizing a cadence, cosine sweep or coefficient history.
            row = snapshots[0] if time < first else snapshots[-1]
            return copy.deepcopy(row["chosenInput"]), "Nearest endpoint complete51 source-FIT witness with the same chosen inverse cam-root continuation held outside measured204 bank exposures. Source-visible crank/coefficient trajectory in this different shot remains unmeasured; no generic cosine animation or historical input recovery claimed."
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
            camera, camera_note = self.synthesis_coarse_camera(frame,original,camera,camera_note)
            camera, camera_note = self.synthesis_wheel_camera(frame,original,camera,camera_note)
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
        if self.analysis_held_camera:
            self.analysis_held_camera["application"]["appliedViewCount"] = 0
            self.analysis_held_camera["application"]["appliedExposures"] = []
        track = common.build_track(self.data,self.views,[
            "Regenerate with python web/scripts/generate-analysis-synthesis-source-tracks.py; requires immutable ignored source evidence; source/model hashes remain unchanged.",
            "All50/20/10/5% width stages remain unmeasured. CPU camera rejection at2% is not a blanket removal of a coarser candidate. No GPU/model/browser execution or historical source recovery.",
            "Camera/input/layout assumptions are declared per view. All retained source shots and integer/change/layout keys remain required, including nested endcards; source copyrighted artwork is not reconstructed."])
        track["source"] = copy.deepcopy(self.data["source"])
        if self.analysis_held_camera:
            application = self.analysis_held_camera["application"]
            retained = []
            for frame in track["frames"]:
                for view in frame["views"]:
                    if self.is_analysis_held_view(frame,view):
                        retained.append(self.analysis_held_exposure(frame,view))
                        if view["camera"] != self.analysis_held_camera["camera"]:
                            raise ValueError("Analysis stationary main camera was overridden after holding.")
            if (not retained or application["appliedViewCount"] != len(retained)
                    or application["appliedExposures"] != retained):
                raise ValueError("Analysis held-camera application is empty or leaves retained stationary main exposures uncovered.")
            track["evidence"]["analysisStationaryFrontCamera"] = copy.deepcopy(self.analysis_held_camera)
            track["evidence"]["notes"].append(self.analysis_held_camera["interpretation"])
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
            track["cpuDiagnostics"]["analysisRootContinuity"] = self.analysis_continuity
            track["evidence"]["notes"].append("Analysis independent source FIT roots can exchange indistinguishable rocker-pose branches. Playback chooses nearest-previous genuine inverse roots; observed rocker endpoints and all source controls stay unchanged. Original per-exposure rod-cost choices remain immutable; alternative cam/rod endpoint orientations and between-exposure continuity are chosen, not recovered or source-certified.")
        else:
            for shot, key in self.synthesis_coarse_framing["shots"].items():
                if (key["eligibleViewCount"] == 0 or key["appliedViewCount"] != key["eligibleViewCount"]
                        or key["appliedSeedExposureCount"] == 0):
                    raise ValueError(f"Chosen framing missed an eligible or original seed main view: {shot}")
            if (self.synthesis_wheel_framing["eligibleViewCount"] == 0
                    or self.synthesis_wheel_framing["appliedViewCount"] != self.synthesis_wheel_framing["eligibleViewCount"]
                    or self.synthesis_wheel_framing["appliedSeedExposureCount"] == 0):
                raise ValueError("Chosen wheel framing missed an eligible or original seed main view")
            track["sourceMeasurements"]["blockers"].append("Synthesis conditional relative pen/wheel trajectory and source-displacement cosine witnesses do not metrically qualify full source-visible motion or unknown station/phase associations.")
            track["evidence"]["synthesisPresenterFraming"] = copy.deepcopy(self.presenter_reframing)
            track["evidence"]["synthesisCoarseFraming"] = copy.deepcopy(self.synthesis_coarse_framing)
            track["evidence"]["synthesisWheelFraming"] = copy.deepcopy(self.synthesis_wheel_framing)
            track["sourceMeasurements"]["blockers"].append("Wheel-macro single original FIT chooses principal-point translation only; independent wheel-hanger CHECK stays held out and moving-spoke/input controls remain unresolved. OneFIT/oneCHECK is not qualified6FIT/2CHECK camera evidence; fresh GPU qualification is deferred.")
            track["sourceMeasurements"]["blockers"].append("Cone-overview's two-FIT similarity remains chosen/unqualified. Cam-rod now uses three original FIT pixels and same-input actual native world markers for a root-selected upright fixedFOV30/centredPP SQPNP physical pose; previous camera similarities are historical/unaccepted. Its declared15deg upright branch prior is not a measured historical camera. Only3FIT depths are established, not whole geometry or GPU/stage acceptance;3FIT/1CHECK still lacks qualified6FIT/2CHECK. Pinion CHECK was never used for objective/ranking/selection and remains held out for root measurement.")
            track["sourceMeasurements"]["blockers"].append("Synthesis presenter-to-spin has one original main machine view with chosen coarse principal-point/FOV reframing. No independently measured transition FIT/CHECK landmarks or per-exposure camera fits are introduced; presenter/black graphic/formula are not native geometry.")
        self.camera_metadata(track)
        return track

    def camera_metadata(self, track):
        previous, epochs = {}, {}
        for frame in track["frames"]:
            for view in frame["views"]:
                evidence = view["provenance"]["evidence"]
                camera = view["camera"]
                component = self.family(frame,view)
                if self.analysis_held_camera and self.is_analysis_held_view(frame,view):
                    if camera != self.analysis_held_camera["camera"]:
                        raise ValueError("Analysis held-camera continuity cannot label different camera geometry.")
                    continuity = f"source-transfer:{self.analysis_held_camera['family']}:branch0"
                    view["cameraProvenance"] = {"kind":"source-transfer","family":continuity,
                                               "evidence":evidence+" Continuity holds one seed camera; it does not certify a source match."}
                    view["cameraContinuityFamily"] = continuity
                    continue
                if evidence.startswith("Photographed branch donor"):
                    kind, branch = "source-transfer", evidence.split(" from ")[0]
                elif evidence.startswith("Single latest four-seed") or frame["shotId"] == "analysis-19":
                    kind, branch = ("source-transfer","analysis-four-seed-bank") if frame["shotId"] != "analysis-19" else ("source-transfer","analysis-page-flip-bank")
                elif evidence.startswith("Single Exact Source6330"):
                    kind, branch = "source-transfer", f"{frame['shotId']}:{view['id']}:source6330-held"
                elif evidence.startswith("Retained source-derived"):
                    kind, branch = "source-transfer", f"{frame['shotId']}:{view['id']}"
                elif evidence.startswith("Nearest same-shot") or evidence.startswith("Related presenter"):
                    # Each held/calibrated donor is a distinct source-derived
                    # branch, never described as an independent exposure fit.
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

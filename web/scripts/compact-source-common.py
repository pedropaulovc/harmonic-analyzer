#!/usr/bin/env python3
"""Compact retained source observations without inventing source or GPU measurements.

Video-specific authors provide physically feasible inputs and candidate cameras. This
module only selects existing decoded-source observations and copies numeric evidence.
Coverage means playback data coverage; stage matching remains unmeasured until the
real renderer is compared with the retained source landmarks.
Exact-image aliases may contribute original observed landmarks to a selected row,
but never change its camera/input/timing. Identity/layout ambiguity is reported;
conflicting corresponding source points fail closed rather than choosing a donor.

Current publication binds content/v39-source/<ID>.observations.json.gz with
independent exact compressed-byte and original decoded-JSON-byte SHA-256 seals.
"""
from __future__ import annotations

import copy
import gzip
import json
import importlib.util
import math
import re
import subprocess
from functools import lru_cache
import hashlib
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
SETUP_FIELDS = (
    "counterHeightM", "meanLineAngleRad", "platenOffsetM", "wireFixtureOffsetM",
    "coneSwingRad", "pinionCamRad", "heldChannelTurns", "driveCrankOffsetTurns",
)
INPUT_FIELDS = ["crankTurns", "gearing", "magnification"] + [
    f"{name}[{i}]" for name in ("amplitudes", "phases") for i in range(20)
] + [f"setup.{name}" for name in SETUP_FIELDS]
CURRENT_PRODUCERS = {
    "web/scripts/fresh-source-tracks.py",
    "web/scripts/generate-analysis-synthesis-source-tracks.py",
    "web/scripts/compact-operation-rocker.py",
    "web/scripts/generate-intro-source-track.py",
    "web/scripts/compact-spin.py",
}


_FRESH_SPEC = importlib.util.spec_from_file_location(
    "fresh_source_observations", Path(__file__).with_name("fresh-source-observations.py"))
fresh = importlib.util.module_from_spec(_FRESH_SPEC)
_FRESH_SPEC.loader.exec_module(fresh)


def read_observations(path):
    """Read observation JSON; gzip corruption and JSON errors propagate."""
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def write_observations(path, data):
    """Keep canonical observations compressed; plain temporary JSON is supported."""
    path = Path(path)
    canonical = (WEB / "content" / "canonical-native").resolve()
    if path.resolve().is_relative_to(canonical) and path.name.endswith(".observations.json"):
        raise ValueError("Canonical observation output must end in .observations.json.gz")
    contents = json.dumps(data, indent=2) + "\n"
    if path.suffix == ".gz":
        with path.open("wb") as stored:
            with gzip.GzipFile(filename="", mode="wb", fileobj=stored, compresslevel=9, mtime=0) as compressed:
                compressed.write(contents.encode("utf-8"))
    else:
        path.write_text(contents, encoding="utf-8")


def load_observations(video_id):
    """Ordinary generation reads only independently measured current observations."""
    return fresh.load_observations(video_id, web_root=WEB)


def load_historical_observations(video_id, prefer_track=False):
    """Explicit immutable diagnostic input; never eligible for ordinary publication."""
    content = WEB / "content" / "canonical-native"
    track = content / f"{video_id}.track.json"
    if prefer_track and track.exists():
        return json.loads(track.read_text())
    return read_observations(content / f"{video_id}.observations.json.gz")


def load_approved_model_source():
    """Use the same strict v2 authority loader as the importer and browser."""
    loader = (WEB / "scripts/approved-model.mjs").resolve().as_uri()
    try:
        result = subprocess.run(
            ["node", "--input-type=module", "--eval",
             "const { LIVE_MODEL_SOURCE } = await import(process.argv[1]); "
             "console.log(JSON.stringify(LIVE_MODEL_SOURCE));", loader],
            capture_output=True, text=True, encoding="utf-8", check=False)
    except OSError as error:
        raise ValueError("Approved model authority unavailable; install Node and restore "
                         "web/scripts/approved-model.mjs and web/content/model-representation.json") from error
    if result.returncode:
        raise ValueError("Approved model authority missing or malformed; restore the reviewed strict v2 "
                         "web/content/model-representation.json and its validator: " + result.stderr.strip())
    return json.loads(result.stdout)


def validate_current_generation_inputs(observations, producer_path, *, additional_observations=(),
                                       executed_inputs=()):
    """Require fresh observations and uncached independently sealed live code."""
    validate_current_generation_seals(producer_path, executed_inputs=executed_inputs)
    for data in (observations, *additional_observations):
        fresh.validate_observations(data, web_root=WEB)


def validate_current_generation_seals(producer_path, *, executed_inputs=()):
    """Shared current EOL-seal census for publication and readback preflight."""
    def relative_path(path):
        path = Path(path)
        return (path.resolve().relative_to(WEB.parent.resolve()).as_posix()
                if path.is_absolute() else path.as_posix())
    producer = relative_path(producer_path)
    if producer not in CURRENT_PRODUCERS:
        raise ValueError("Current source record names an undeclared ordinary producer")
    paths = {
        producer, "web/scripts/fresh-source-tracks.py", "web/scripts/compact-source-common.py", "web/src/bindings.ts", "web/src/scene.ts",
        "web/src/mechanics.ts", "web/src/mechanics-data.ts", "web/src/magnifier.ts", "web/src/kinematics.ts",
        "web/scripts/approved-model.mjs", "web/model-representation.mjs",
        "web/content/model-representation.json",
    }
    paths.update(relative_path(path) for path in executed_inputs)
    paths.update(relative_path(path) for path in fresh.EXECUTED_INPUTS)
    manifest = json.loads((WEB / "content/canonical-native/manifest.json").read_bytes())
    if manifest.get("canonicalConsumerHashNormalization") != "CRLF-to-LF":
        raise ValueError("Current live consumer hash normalization differs")
    seals = [row for row in manifest["canonicalConsumerInputs"] if row["path"] in paths]
    if len(seals) != len(paths) or {row["path"] for row in seals} != paths:
        raise ValueError("Current live producer input seal census differs")
    for seal in seals:
        path, sha = seal["path"], seal.get("sha256")
        if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
            raise ValueError(f"Current live producer input lacks SHA: {path}")
        try:
            raw = (WEB.parent / path).read_bytes()
        except OSError as error:
            raise ValueError(f"Current live producer input unavailable: {path}") from error
        actual = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
        if actual != sha:
            raise ValueError(f"Current live producer input differs: {path}")


def historical_code_bytes(path, expected_sha256):
    """Verify a sealed historical producer snapshot, never today's renderer.

    These bytes establish only original evidence lineage. They do not qualify
    canonical geometry, current code, or a new GPU/source comparison.
    """
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("Historical code evidence requires a SHA256 seal")
    snapshot = WEB / "content/canonical-native/historical-code" / expected_sha256 / Path(path).name
    try:
        raw = snapshot.read_bytes()
    except OSError as error:
        raise ValueError(f"Historical producer snapshot unavailable: {path}") from error
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"Historical producer snapshot changed: {path}")
    return raw


def needs_machine(frame, data):
    shot = next(s for s in data["shots"] if s["id"] == frame["shotId"])
    if data.get("kind") == "current-source-observations" and frame.get("views"):
        return True
    if frame.get("sourceMachineRequirement") == "required":
        return True
    if frame["classification"] == "machine":
        return True
    if frame["classification"] == "non-machine":
        return shot.get("hasCorrespondingMachine") is True
    return shot.get("hasCorrespondingMachine") is not False


def policy_excluded_view(frame, view):
    """Same closed actual-exposure qualification as source-visibility.mjs."""
    if "sourceVisibility" not in view:
        return False
    value = view["sourceVisibility"]
    image = frame.get("sourceImage", {})
    audit = value.get("manualSourceAudit") if isinstance(value, dict) else None
    key = {"gray8": "sha256Gray8", "bgr8": "sha256Bgr8"}.get(image.get("pixelFormat"))
    rect = view.get("rectSourcePixels")
    valid = (isinstance(value, dict)
             and set(value) == {"kind", "reasonCode", "sourceImage", "rectSourcePixels", "manualSourceAudit"}
             and value["kind"] == "policy-excluded"
             and value["reasonCode"] in ("blurred-navigation-background", "text-covered-navigation-background", "unreadable-near-black-fade")
             and isinstance(audit, dict) and set(audit) == {"method", "evidence"}
             and audit["method"] == "manual-source-pixel-inspection"
             and isinstance(audit["evidence"], str) and bool(audit["evidence"].strip())
             and key is not None and set(image) == {"frameIndex", "pixelFormat", "width", "height", "sourceSha256", key}
             and type(image["frameIndex"]) is int and image["frameIndex"] >= 0
             and image["width"] == 1920 and image["height"] == 1080
             and all(isinstance(image[field], str) and re.fullmatch(r"[0-9a-f]{64}", image[field])
                     for field in ("sourceSha256", key))
             and value["sourceImage"] == image and value["rectSourcePixels"] == rect
             and isinstance(rect, list) and len(rect) == 4
             and all(type(number) in (int, float) and math.isfinite(number) for number in rect)
             and rect[0] >= 0 and rect[1] >= 0 and rect[2] > 0 and rect[3] > 0
             and rect[0] + rect[2] <= image["width"] and rect[1] + rect[3] <= image["height"]
             and not view.get("nativeLineChecks")
             and not any(point.get("viewId", "main") == view["id"] and not (
                 point.get("method") == "template-match" and "trackingEvidence" not in point
                 and isinstance(point.get("anchorId"), str) and bool(point["anchorId"].strip())
                 and point.get("status") == "observed" and point.get("role") in ("fit", "check")
                 and isinstance(point.get("pixel"), list) and len(point["pixel"]) == 2
                 and all(type(number) in (int, float) and math.isfinite(number) for number in point["pixel"])
                 and rect[0] <= point["pixel"][0] < rect[0] + rect[2]
                 and rect[1] <= point["pixel"][1] < rect[1] + rect[3]
                 and type(point.get("uncertaintyPx")) in (int, float) and math.isfinite(point["uncertaintyPx"])
                 and point["uncertaintyPx"] >= 0
                 and (not isinstance(point.get("measurementEvidence"), dict) or (
                     ("sourceImage" not in point["measurementEvidence"] or point["measurementEvidence"]["sourceImage"] == image)
                     and ("sourceSha256Bgr8" not in point["measurementEvidence"] or point["measurementEvidence"]["sourceSha256Bgr8"] == image.get("sha256Bgr8"))
                     and ("sourceSha256Gray8" not in point["measurementEvidence"] or point["measurementEvidence"]["sourceSha256Gray8"] == image.get("sha256Gray8")))))
                 for point in frame.get("landmarks", [])))
    if not valid:
        raise ValueError("Invalid actual source image/complete ROI/manual approved unreadable-ROI qualification")
    return True

def valid_source_rect(rect):
    return (isinstance(rect, list) and len(rect) == 4
            and all(type(number) in (int, float) and math.isfinite(number) for number in rect)
            and rect[0] >= 0 and rect[1] >= 0 and rect[2] > 0 and rect[3] > 0
            and rect[0] + rect[2] <= 1920 and rect[1] + rect[3] <= 1080)


def valid_source_composite(composite):
    return (composite is None or isinstance(composite, dict) and (
        set(composite) == {"mode"} and composite["mode"] == "opaque"
        or set(composite) == {"mode", "groupId", "imageLayerId", "opacity"}
        and composite["mode"] == "crossfade"
        and all(isinstance(composite[key], str) and bool(composite[key].strip())
                for key in ("groupId", "imageLayerId"))
        and type(composite["opacity"]) in (int, float) and math.isfinite(composite["opacity"])
        and 0 <= composite["opacity"] <= 1))


def zero_opacity_source_view(view):
    composite = view.get("composite")
    return (valid_source_rect(view.get("rectSourcePixels"))
            and valid_source_composite(composite) and composite is not None
            and composite["mode"] == "crossfade" and composite["opacity"] == 0)


def fully_covering_source_view(frame, view):
    """Exact existing ordered opaque unwarped rectangle support, without a visibility waiver."""
    def has_warp(candidate):
        return any(candidate.get(key) is not None for key in (
            "imagePlaneWarp", "resolvedImagePlaneWarp", "imagePlaneWarpMeasurement"))

    views = frame.get("views", [])
    index = next((index for index, candidate in enumerate(views) if candidate is view), -1)
    a, own = view.get("composite"), view.get("rectSourcePixels")
    if index < 0 or not valid_source_rect(own) or not valid_source_composite(a) or has_warp(view):
        return None
    for later in views[index + 1:]:
        b, rect = later.get("composite"), later.get("rectSourcePixels")
        if not valid_source_rect(rect) or not valid_source_composite(b) or has_warp(later):
            continue
        if b and b["mode"] == "crossfade" and (b["opacity"] != 1 or a
                and a["mode"] == "crossfade" and a["groupId"] == b["groupId"]
                and a["imageLayerId"] != b["imageLayerId"]):
            continue
        if (rect[0] <= own[0] and rect[1] <= own[1]
                and rect[0] + rect[2] >= own[0] + own[2]
                and rect[1] + rect[3] >= own[1] + own[3]):
            return later
    return None



def canonicalize_cut_clock(data):
    """Preserve cuts on their recorded native clock, not rounded decimal text."""
    if data.get("kind") == "current-source-observations":
        # Fresh annotations carry actual PTS; only selection keys may equate
        # adjacent floats at cuts. Never change evidence or infer it from fps.
        return
    fps_record = data["source"]["fps"]
    fps = fps_record["numerator"] / fps_record["denominator"]
    corrections = data.setdefault("samplingDiagnostics", {}).setdefault("cutClockCorrections", [])
    for shot in data["shots"]:
        original = shot["startSeconds"]
        index = shot.get("nativeStartFrame", shot.get("startDecodedFrameIndex"))
        candidate = index / fps if isinstance(index, int) else round(original * fps) / fps
        allowed = max(float(shot.get("boundaryUncertaintySeconds", 0)), 1 / fps) if isinstance(index, int) else 1e-6
        if abs(candidate - original) <= allowed and candidate != original:
            shot["startSeconds"] = candidate
            corrections.append({"shotId": shot["id"], "originalSeconds": original, "nativeClockSeconds": candidate,
                                "basis": "Recorded first native exposure" if isinstance(index, int) else "Sub-microsecond decimal representation of the retained native clock"})
    for first, second in zip(data["shots"], data["shots"][1:]):
        first["endSeconds"] = second["startSeconds"]


def compact_change_times(data):
    """Snap rounded event labels within their cut uncertainty to the real cut."""
    if data.get("kind") == "current-source-observations":
        authored = set(data.get("coverage", {}).get("changeTimesSeconds", []))
        previous = None
        for frame in data["frames"]:
            visibility = [(view["id"], view.get("sourceVisibility", {}).get("reasonCode")) for view in frame["views"]]
            if visibility != previous:
                authored.add(frame["timeSeconds"])
            previous = visibility
        if any("sourceAssembly" in view for frame in data["frames"] for view in frame["views"]):
            authored.update(fresh.assembly_change_times(data, web_root=WEB))
        return authored
    fps = data["source"]["fps"]["numerator"] / data["source"]["fps"]["denominator"]
    boundaries = [(shot["startSeconds"], max(float(shot.get("boundaryUncertaintySeconds", 0)), 1 / fps), shot["id"]) for shot in data["shots"]]
    result, snaps = set(), []
    changes = data.get("compactChangeTimesSeconds", [])
    for original in changes:
        if abs(original * fps - round(original * fps)) < 1e-6:
            result.add(original)
            continue
        boundary, uncertainty, shot_id = min(boundaries, key=lambda item: abs(item[0] - original))
        if abs(boundary - original) <= uncertainty:
            result.add(boundary)
            if boundary != original:
                snaps.append({"originalSeconds": original, "cutSeconds": boundary, "uncertaintySeconds": uncertainty, "shotId": shot_id})
        else:
            result.add(original)
    data.setdefault("samplingDiagnostics", {})["roundedEventSnaps"] = snaps
    return result

def retain_exact_exposure_landmarks(selected, data):
    """Union original pixels only across identical native exposures and layouts."""
    pixel_hash_fields = {"bgr8": "sha256Bgr8", "gray8": "sha256Gray8"}
    identity_fields = ("frameIndex", "sourceSha256", "pixelFormat", "width", "height")

    def identity(frame):
        image = frame.get("sourceImage")
        pts = frame.get("decodedTimeSeconds")
        pixel_format = image.get("pixelFormat") if isinstance(image, dict) else None
        hash_field = pixel_hash_fields.get(pixel_format) if isinstance(pixel_format, str) else None
        if (not isinstance(image, dict) or hash_field is None
                or any(key not in image for key in (*identity_fields, hash_field))
                or type(pts) not in (int, float) or not math.isfinite(pts)
                or type(image["frameIndex"]) is not int or image["frameIndex"] < 0
                or type(frame.get("decodedFrameIndex", image["frameIndex"])) is not int
                or frame.get("decodedFrameIndex", image["frameIndex"]) != image["frameIndex"]
                or image["sourceSha256"] != data["source"].get("sha256")
                or any(type(image[key]) is not int or image[key] <= 0
                       or image[key] != data["source"][key] for key in ("width", "height"))
                or any(not isinstance(image[key], str) or not re.fullmatch(r"[0-9a-f]{64}", image[key])
                       for key in ("sourceSha256", hash_field))):
            return None
        return (frame["shotId"], pts, *(image[key] for key in identity_fields), image[hash_field])

    layout_cache = {}

    def layout(frame):
        cache_key = id(frame)
        if cache_key in layout_cache:
            return layout_cache[cache_key]
        views = source_views(frame, data)
        if not isinstance(views, list) or any(not isinstance(view, dict) for view in views):
            layout_cache[cache_key] = None
            return None
        result = {}
        for view in views:
            view_id = view.get("id")
            rect = view.get("rectSourcePixels")
            try:
                warp = resolve_warp(view)
                composite = compact_composite(view)
            except (KeyError, TypeError, AttributeError):
                layout_cache[cache_key] = None
                return None
            if (not isinstance(view_id, str) or not view_id or view_id in result
                    or not isinstance(rect, list) or len(rect) != 4
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in rect)
                    or rect[0] < 0 or rect[1] < 0 or rect[2] <= 0 or rect[3] <= 0
                    or rect[0] + rect[2] > data["source"]["width"]
                    or rect[1] + rect[3] > data["source"]["height"]
                    or view.get("presentation", "native") not in ("native", "horizontal-mirror")
                    or ((view.get("resolvedImagePlaneWarp") or view.get("imagePlaneWarp")) and not warp)
                    or (view.get("composite") and not composite)):
                result = None
                break
            result[view_id] = {"rectSourcePixels":rect,
                               "presentation":view.get("presentation", "native"),
                               "imagePlaneWarp":warp, "composite":composite}
            if "sourceVisibility" in view:
                result[view_id]["sourceVisibility"] = copy.deepcopy(view["sourceVisibility"])
        layout_cache[cache_key] = result or None
        return layout_cache[cache_key]

    def point_key(point, views):
        view_id = point.get("viewId")
        if view_id is None:
            # Legacy unscoped points mean the single full-frame native main,
            # not an arbitrary inset/transition layer.
            if (set(views) != {"main"} or views["main"] != {
                    "rectSourcePixels":[0,0,data["source"]["width"],data["source"]["height"]],
                    "presentation":"native", "imagePlaneWarp":None, "composite":None}):
                return None
            view_id = "main"
        if view_id not in views:
            return None
        return view_id, point["anchorId"]

    groups = {}
    for frame in data["frames"]:
        key = identity(frame)
        if key is not None:
            groups.setdefault(key, []).append(frame)
    diagnostics = {"status":"exact-exposure-only", "originalAliasGroupCount":sum(len(rows) > 1 for rows in groups.values()),
                   "selectedRowsAugmented":0, "originalLandmarksRetained":0, "unavailable":[],
                   "supportedPixelFormats":list(pixel_hash_fields), "unsupportedPixelFormats":[]}
    reported_formats = set()
    for frame in [*data["frames"], *selected]:
        image = frame.get("sourceImage")
        if isinstance(image, dict) and (not isinstance(image.get("pixelFormat"), str)
                                        or image.get("pixelFormat") not in pixel_hash_fields):
            pixel_format = image.get("pixelFormat")
            format_key = json.dumps(pixel_format, sort_keys=True)
            if format_key not in reported_formats:
                reported_formats.add(format_key)
                diagnostics["unsupportedPixelFormats"].append({
                    "pixelFormat":pixel_format,
                    "reason":"Unsupported source pixel format; exact-exposure landmark aliases not copied."})
    output = []
    for frame in selected:
        aliases = groups.get(identity(frame), [])
        views = layout(frame)
        if len(aliases) > 1 and views is None:
            diagnostics["unavailable"].append({"shotId":frame["shotId"],"timeSeconds":frame["timeSeconds"],
                "reason":"Exact-image aliases have no unambiguous selected view layout; landmarks not copied."})
        if len(aliases) < 2 or views is None:
            output.append(frame)
            continue
        points = copy.deepcopy(frame.get("landmarks", []))
        known = {}
        added = 0
        # The selected row can be the original object or an equal copy. Visit
        # that declaration once, but keep unequal rows so conflicts still fail.
        seen = set()
        for alias in [frame, *aliases]:
            if id(alias) in seen:
                continue
            seen.add(id(alias))
            if alias is not frame and alias == frame:
                continue
            if layout(alias) != views:
                diagnostics["unavailable"].append({"shotId":frame["shotId"],"timeSeconds":frame["timeSeconds"],
                    "aliasTimeSeconds":alias["timeSeconds"],"reason":"Identical source image has ambiguous/different view layout; landmarks not copied."})
                continue
            for point in alias.get("landmarks", []):
                key = point_key(point, views)
                if key is None:
                    diagnostics["unavailable"].append({"shotId":frame["shotId"],"timeSeconds":frame["timeSeconds"],
                        "aliasTimeSeconds":alias["timeSeconds"],"anchorId":point["anchorId"],
                        "reason":"Original landmark view correspondence is ambiguous; landmark not copied."})
                    continue
                comparable = {**point, "viewId":key[0]}
                old = known.get(key)
                if old is not None:
                    if old != comparable:
                        raise ValueError(f"Conflicting original exact-exposure landmark for {frame['shotId']} native {frame['sourceImage']['frameIndex']} view {key[0]} anchor {key[1]}.")
                    continue
                known[key] = comparable
                if alias is frame:
                    continue
                pixel = point.get("pixel")
                if (point.get("status") != "observed" or not isinstance(pixel, list) or len(pixel) != 2
                        or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in pixel)):
                    continue
                points.append(copy.deepcopy(point))
                added += 1
        if added:
            frame = {**frame, "landmarks":points}
            diagnostics["selectedRowsAugmented"] += 1
            diagnostics["originalLandmarksRetained"] += added
        output.append(frame)
    data.setdefault("samplingDiagnostics", {})["exactExposureAliasLandmarks"] = diagnostics
    return output


def within_half_open_shot(shot, time):
    """Route only derived requested cut keys without changing source clocks.

    One representable step on either side is execution-key equivalence, not
    boundary uncertainty or a source-sampling tolerance. Actual decoded PTS
    retain strict half-open ownership, and exact authored requested keys take
    precedence over this derived-key routing.
    """
    start, end = shot["startSeconds"], shot["endSeconds"]
    if math.nextafter(start, -math.inf) <= time <= math.nextafter(start, math.inf):
        time = start
    elif math.nextafter(end, -math.inf) <= time <= math.nextafter(end, math.inf):
        time = end
    return start <= time < end


def selected_frames(data):
    """Keep seconds, exact changes, shot edges, and useful measured motion keys.

    Requested times and actual decoded PTS are distinct. A missing exact requested
    row reuses the nearest retained observation in the same shot, never projected
    landmarks or fabricated source pixels. Additional camera keys keep changing
    turntable angles below 10 degrees and observed landmark steps below 35 pixels.
    These are sampling choices, not matching tolerances or stage measurements.
    """
    canonicalize_cut_clock(data)
    frames = sorted(data["frames"], key=lambda f: f["timeSeconds"])
    duration = data["source"]["durationSeconds"]
    shot_by_id = {s["id"]: s for s in data["shots"]}
    by_shot = {s["id"]: [] for s in data["shots"]}
    authored_shots = {}
    rejected = []
    for frame in frames:
        shot = shot_by_id[frame["shotId"]]
        pts = frame.get("decodedTimeSeconds")
        if pts is not None and shot["startSeconds"] <= pts < shot["endSeconds"]:
            by_shot[frame["shotId"]].append(frame)
            time = frame["timeSeconds"]
            if shot["startSeconds"] <= time < shot["endSeconds"]:
                owner = authored_shots.setdefault(time, shot)
                if owner["id"] != shot["id"]:
                    raise ValueError("Exact authored source clock has ambiguous shot ownership")
        else:
            rejected.append({"shotId": frame["shotId"], "timeSeconds": frame["timeSeconds"], "decodedTimeSeconds": pts})
    data.setdefault("samplingDiagnostics", {})["excludedCrossCutObservations"] = rejected
    required = set(float(t) for t in range(math.floor(duration) + 1) if t < duration)
    required.update(float(t) for t in compact_change_times(data) if 0 <= t < duration)
    for shot in data["shots"]:
        required.add(float(shot["startSeconds"]))
        if shot["endSeconds"] < duration:
            required.add(float(shot["endSeconds"]))
        if shot["classification"] == "transition":
            span = shot["endSeconds"] - shot["startSeconds"]
            required.update(shot["startSeconds"] + span * fraction for fraction in (0.25, 0.5, 0.75))
    output = {}
    for time in sorted(required):
        shot = authored_shots.get(time)
        if shot is None:
            shot = next(s for s in data["shots"] if within_half_open_shot(s, time))
        pool = by_shot[shot["id"]]
        if not pool:
            # Explicitly unsupported source sampling, not a fabricated exposure.
            output[time] = {"timeSeconds": time, "decodedTimeSeconds": None,
                            "sourceSampleUnavailable": True, "shotId": shot["id"],
                            "classification": shot["classification"], "landmarks": [],
                            "views": [], "unavailable": [
                                {"reason": "No retained decoded source observation in this shot."}]}
            continue
        source = min(pool, key=lambda f: abs(f["decodedTimeSeconds"] - time))
        if abs(source["decodedTimeSeconds"] - time) > 0.5:
            output[time] = {"timeSeconds": time, "decodedTimeSeconds": None,
                            "sourceSampleUnavailable": True, "shotId": shot["id"],
                            "classification": shot["classification"], "landmarks": [],
                            "views": [], "unavailable": [
                                {"reason": "No retained same-shot decoded source observation within 0.5s."}]}
            continue
        if source["timeSeconds"] == time:
            output[time] = source
        else:
            sampled = copy.copy(source)
            sampled["timeSeconds"] = time
            sampled["retainedObservationTimeSeconds"] = source["timeSeconds"]
            output[time] = sampled
    # Original sparse manual/fit samples, layout changes, and nonlinear source
    # motion deserve keys beyond the required integer-second/change-point census.
    for shot in data["shots"]:
        pool = by_shot[shot["id"]]
        previous = None
        for frame in pool:
            time = frame["timeSeconds"]
            add = time in output or previous is None or frame is pool[-1]
            if previous is not None and not add:
                old_views = source_views(previous, data)
                new_views = source_views(frame, data)
                if [v["id"] for v in old_views] != [v["id"] for v in new_views]:
                    add = True
                elif time - previous["timeSeconds"] >= 0.125:
                    for old, new in zip(old_views, new_views):
                        if abs((old.get("composite") or {}).get("opacity", 1) - (new.get("composite") or {}).get("opacity", 1)) >= 0.25:
                            add = True
                        a, b = old.get("camera"), new.get("camera")
                        if a and b:
                            dot = min(1.0, abs(sum(x * y for x, y in zip(a["quaternion"], b["quaternion"]))))
                            if 2 * math.acos(dot) > math.radians(10):
                                add = True
                            if abs(a["verticalFovDegrees"] - b["verticalFovDegrees"]) > 0.5:
                                add = True
                        if max(abs(x-y) for x, y in zip(old["rectSourcePixels"], new["rectSourcePixels"])) > 35:
                            add = True
                    old_points = {(p.get("viewId"), p["anchorId"]): p["pixel"] for p in previous.get("landmarks", []) if p.get("pixel")}
                    for point in frame.get("landmarks", []):
                        old = old_points.get((point.get("viewId"), point["anchorId"]))
                        if old and point.get("pixel") and math.dist(old, point["pixel"]) > 35:
                            add = True
            if add:
                # A nearby incoming cut key cannot replace an outgoing exposure.
                if not any(row["shotId"] == frame["shotId"] and abs(existing - time) < 1e-6
                           for existing, row in output.items()):
                    output[time] = frame
                previous = frame
    return retain_exact_exposure_landmarks([output[t] for t in sorted(output)], data)


def compact_camera(camera):
    if not camera:
        return None
    keys = ("positionMetres", "quaternion", "verticalFovDegrees", "principalPointViewportPixels",
            "fitRmsPx", "fitMaxPx", "heldOutMaxPx", "status")
    result = {key: copy.deepcopy(camera[key]) for key in keys if key in camera}
    if not all(key in result for key in keys[:3]):
        return None
    if not all(math.isfinite(x) for x in result["positionMetres"] + result["quaternion"] + [result["verticalFovDegrees"]]):
        return None
    return result


def compact_input(value):
    if value is None:
        return None
    result = {key: copy.deepcopy(value[key]) for key in ("crankTurns", "amplitudes", "phases", "gearing", "magnification")}
    result["setup"] = {key: value["setup"][key] for key in SETUP_FIELDS}
    if len(result["amplitudes"]) != 20 or len(result["phases"]) != 20:
        raise ValueError("A chosen source input must name all twenty channel amplitudes and phases.")
    numbers = [result["crankTurns"], result["magnification"]] + result["amplitudes"] + result["phases"] + [x for x in result["setup"].values() if x is not None]
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in numbers):
        raise ValueError("A chosen source input must be complete and finite.")
    if any(abs(x) > 1 for x in result["amplitudes"]) or result["magnification"] <= 0:
        raise ValueError("Invalid source amplitude or magnification.")
    if result["gearing"] not in ("small-large", "medium-medium", "large-small"):
        raise ValueError("Unknown source gearing.")
    if any(result["setup"][key] is None for key in SETUP_FIELDS if key != "counterHeightM"):
        raise ValueError("Only automatic counter-spring height may remain null.")
    return result


def chosen_provenance(evidence, unobserved_fields=None):
    return {"kind": "chosen-feasible", "evidence": evidence,
            "unobservedInputFields": list(INPUT_FIELDS if unobserved_fields is None else unobserved_fields)}


def source_views(frame, data):
    if "views" in frame:
        return copy.deepcopy(frame["views"])
    if not needs_machine(frame, data):
        return []
    return [{"id": "main", "rectSourcePixels": [0, 0, data["source"]["width"], data["source"]["height"]],
             "presentation": "native", "camera": frame.get("camera"),
             "mechanicalState": copy.deepcopy(frame.get("mechanicalState", {}))}]


def resolve_warp(view):
    warp = view.get("resolvedImagePlaneWarp") or view.get("imagePlaneWarp")
    if warp and all(key in warp for key in ("kind", "unwarpedViewportPixels", "renderToSourcePixels")):
        return {key: copy.deepcopy(warp[key]) for key in ("kind", "unwarpedViewportPixels", "renderToSourcePixels")}
    return None


def compact_composite(view):
    composite = view.get("composite")
    if not composite:
        return None
    if composite.get("mode") == "opaque":
        return {"mode": "opaque"}
    if composite.get("mode") == "crossfade":
        return {key: composite[key] for key in ("mode", "groupId", "imageLayerId", "opacity")}
    return None


# These identities are supported by the retained anchor correspondence evidence:
# fixed castings/support fasteners, not every unbound part or assembly descendant.
FIXED_ANCHOR_PARTS = {
    f"ha-harmonic-analyzer/{group}/{name}-{index}"
    for group, name, indices in (
        ("fr-frame", "fr-harmonic-base", (1,)), ("fr-frame", "fr-top-frame", (1,)),
        ("fr-frame", "fr-tube-frame", range(1, 5)), ("fr-frame", "vn-tube-frame-cap", (4,)),
        ("fr-frame", "vn-frame-cross-screw", range(1, 9)), ("fr-frame", "vn-fillister-screw", range(1, 5)),
        ("fr-frame", "fr-nameplate", (1,)), ("fr-frame", "fr-rocker-arm-support", (1,)),
        ("fr-frame", "vn-gooseneck-set-screw", (1,)),
        ("ch-channel", "ch-pivot-shaft", (1,)), ("ch-channel", "ch-fulcrum-shaft", (1,)),
        ("ch-channel", "ch-pivot-bracket", (1,)), ("ch-channel", "vn-pedestal-hold-down-screw", (2,)),
        ("dt-drive-train", "dt-arbor-pedestal", (1, 2)),
        ("dt-drive-train", "vn-pedestal-hold-down-screw", (1, 2)),
        ("dt-drive-train", "vn-cone-lock-knob", (1,)), ("dt-drive-train", "vn-cone-pivot-screw", (1,)),
        ("dt-drive-train", "dt-cylinder-gear-shaft", (1,)), ("dt-drive-train", "dt-cylinder-end-disc", (1,)),
        ("dt-drive-train", "dt-pinion-pivot-shaft", (1,)),
        ("mg-magnifier", "mg-wheel-bar", (1,)), ("mg-magnifier", "vn-wheel-axle-nut", (1,)),
        ("mg-magnifier", "vn-clamp-screw", (1, 2)), ("mg-magnifier", "sh-column-clamp-front", (1,)),
        ("pd-paper-drive", "pd-support-bar", (1,)), ("pd-paper-drive", "vn-clamp-screw", range(1, 5)),
        ("pn-pen", "vn-hanger-screw", (1,)),
    )
    for index in indices
}
FIXED_AXIS_ANCHORS = {
    ("ha-harmonic-analyzer/mg-magnifier/mg-magnifying-wheel-1", "wheel.center"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-transgear-knob-shaft-1", "feed-knob.center"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-transgear-knob-shaft-1", "transgear.knob.axis"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-transgear-knob-shaft-1", "paper-chain-axis"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-transgear-knob-shaft-1", "gta.paper.knob.axis"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-rack-pinion-1", "gta.paper.rack.axis"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-rack-pinion-1", "gta.paper.disc.axis"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-transgear-thumbnut-1", "gta.paper.upper.axis"),
    ("ha-harmonic-analyzer/pd-paper-drive/pd-transgear-removable-2", "gta.paper.lower.axis"),
}


@lru_cache(maxsize=1)
def native_motion_bindings():
    """Read the renderer's declarative bindings, without a second motion table."""
    source = (WEB / "src/bindings.ts").read_text()
    groups = dict(re.findall(r"^const (\w+) = '([^']+)'$", source, re.MULTILINE))
    declarations = source.split("export const BINDINGS: readonly Binding[] = [", 1)[1].split("\n]", 1)[0]
    bindings = []
    for line in declarations.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        match = re.fullmatch(r"(family|group)\('[^']+', (\w+), '([^']+)', '([^']+)'(?:, \d+)?\),", line)
        if not match:
            raise ValueError(f"Unrecognized native binding declaration: {line}")
        kind, namespace, names, motion = match.groups()
        pattern = f"{re.escape(groups[namespace])}{names}-[1-9][0-9]*" if kind == "family" else f"{re.escape(groups[namespace])}(?:{names})"
        bindings.append((re.compile(pattern), motion))
    return bindings


def anchor_motion(anchor):
    if anchor.get("motion") in ("fixed", "moving"):
        return anchor["motion"]
    path = anchor.get("partPath")
    if not anchor.get("correspondenceEvidence"):
        return None
    if path in FIXED_ANCHOR_PARTS or (path, anchor["id"]) in FIXED_AXIS_ANCHORS:
        return "fixed"
    motion = next((motion for pattern, motion in native_motion_bindings() if path and pattern.fullmatch(path)), None)
    # A spin/swing binding alone does not prove that this point is off its axis.
    # Crank/cone also have compound platform motion: their unidentified centres
    # remain unknown, rather than being certified fixed or moving by prose.
    if motion in (None, "crank", "cone-spin", "cylinder", "wheel",
                  "paper-knob", "paper-feed", "paper-sprocket",
                  "pinion-swing", "pinion-cam", "pinion-lever"):
        return None
    if motion == "paper-fixed":
        return "fixed"
    return "moving"


def build_track(data, frame_views_callback, evidence_notes=None):
    canonicalize_cut_clock(data)
    shots = [{key: copy.deepcopy(shot[key]) for key in ("id", "startSeconds", "endSeconds", "classification", "hasCorrespondingMachine", "reason", "internalMechanismMotion", "internalMotionEvidence", "internalMotionSourceEvidence") if key in shot} for shot in data["shots"]]
    anchors = []
    for anchor in data["anchors"]:
        item = {key: copy.deepcopy(anchor[key]) for key in ("id", "kind", "partPath", "runtimeTemplatePartPath", "partLocalMetres", "worldMetres", "description", "correspondenceEvidence") if key in anchor}
        item["motion"] = anchor_motion(anchor)
        anchors.append(item)
    frames, blockers = [], []
    for frame in selected_frames(data):
        views = [] if frame.get("sourceSampleUnavailable") else frame_views_callback(frame)
        for view in views:
            if "cameraProvenance" not in view:
                family = f'{data["source"]["videoId"]}:{frame["shotId"]}:{view["id"]}:unqualified-camera'
                view["cameraProvenance"] = {"kind": "source-informed-framing", "family": family,
                                            "evidence": "Chosen playback camera; an independently source-fitted camera family has not been declared for this view."}
                view["cameraContinuityFamily"] = family
        row = {key: copy.deepcopy(frame[key]) for key in ("timeSeconds", "decodedTimeSeconds", "sourceSampleUnavailable", "shotId", "classification", "sourceMachineRequirement", "sourceImage", "retainedObservationTimeSeconds") if key in frame}
        row["landmarks"] = []
        for landmark in frame.get("landmarks", []):
            if landmark.get("status") != "observed" or landmark.get("pixel") is None:
                continue
            row["landmarks"].append({key: copy.deepcopy(landmark[key]) for key in ("anchorId", "viewId", "role", "pixel", "status", "method", "uncertaintyPx", "trackingEvidence", "measurementEvidence") if key in landmark})
        if frame.get("unavailable"):
            row["unavailable"] = [{key: copy.deepcopy(item[key]) for key in ("anchorId", "viewId", "reason") if key in item} if isinstance(item, dict) else item for item in frame["unavailable"]]
        row["views"] = views
        if row["decodedTimeSeconds"] is None or abs(row["decodedTimeSeconds"] - row["timeSeconds"]) > 0.5:
            blockers.append(f'{frame["shotId"]} at {frame["timeSeconds"]:.6f}s: no retained observation within 0.5s.')
        required = [view for view in views if not policy_excluded_view(row, view)
                    and (data.get("kind") != "current-source-observations"
                         or not zero_opacity_source_view(view) and fully_covering_source_view(row, view) is None)]
        if needs_machine(frame, data) and (not views or any(view.get("camera") is None or view.get("input") is None for view in required)):
            blockers.append(f'{frame["shotId"]} at {frame["timeSeconds"]:.6f}s: source-required camera/input remains unavailable.')
        frames.append(row)
    source_keys = ("videoId", "sha256", "width", "height", "durationSeconds", "videoDurationSeconds", "fps", "decodedFrameCount", "firstDecodedTimeSeconds", "lastDecodedTimeSeconds", "rights")
    result = {"schemaVersion": 1, "kind": "compact-source-track",
              "source": {key: copy.deepcopy(data["source"][key]) for key in source_keys if key in data["source"]},
              "model": copy.deepcopy(data["model"]), "anchors": anchors, "shots": shots, "frames": frames,
              "nativeIdentity": copy.deepcopy(data.get("nativeIdentity")),
              "coverage": {"status": "blocked" if blockers or data.get("coverage", {}).get("status") == "blocked" else "complete",
                           "blockers": list(data.get("coverage", {}).get("blockers", [])) + blockers,
                           "requiredEveryIntegerSecond": True,
                           "changeTimesSeconds": sorted(set(data.get("coverage", {}).get("changeTimesSeconds", [])) | set(row["timeSeconds"] for row in frames if not float(row["timeSeconds"]).is_integer())),
                           "samplingPolicy": "Every integer second, every observed change, shot edge, quarter-fade check, and retained camera/layout/observed-motion key. No per-part exposure certificate gates playback."},
              "stages": {str(stage): {"status": "unmeasured"} for stage in (50, 20, 10, 5)},
              "evidence": {"interpretation": "Chosen source-informed physically feasible playback candidates. Hidden inputs are not recovered. Camera FIT/CHECK residuals are CPU diagnostics, not current GPU measurements or stage passes.",
                           "notes": list(evidence_notes or [])}}
    zero_views = [(frame, view) for frame in frames for view in frame["views"]
                  if data.get("kind") == "current-source-observations" and zero_opacity_source_view(view)]
    covered_views = [(frame, view) for frame in frames for view in frame["views"]
                     if data.get("kind") == "current-source-observations" and not zero_opacity_source_view(view)
                     and fully_covering_source_view(frame, view) is not None]
    excluded_views = [(frame, view) for frame in frames for view in frame["views"]
                      if policy_excluded_view(frame, view) and (data.get("kind") != "current-source-observations"
                          or not zero_opacity_source_view(view) and fully_covering_source_view(frame, view) is None)]
    required_views = [(frame, view) for frame in frames if needs_machine(frame, data)
                      for view in frame["views"] if not policy_excluded_view(frame, view)
                      and (data.get("kind") != "current-source-observations"
                           or not zero_opacity_source_view(view) and fully_covering_source_view(frame, view) is None)]
    checked_views = sum(any(point.get("role") == "check" and point.get("viewId", "main") == view["id"] for point in frame["landmarks"]) for frame, view in required_views)
    assumed_cameras = sum(view["cameraProvenance"]["kind"] == "source-informed-framing" for _, view in required_views)
    result["sourceMeasurements"] = {
        "status": "partial" if checked_views else "incomplete",
        "requiredViewSamples": len(required_views), "viewSamplesWithSourceChecks": checked_views,
        "qualifiedExcludedViewSamples": len(excluded_views),
        "noncontributingCoveredViewSamples": len(covered_views),
        "noncontributingZeroOpacityViewSamples": len(zero_views),
        "preservedInadmissibleLandmarkSamples": sum(
            sum(point.get("viewId", "main") == view["id"] for point in frame.get("landmarks", []))
            for frame, view in excluded_views),
        "assumedCameraViewSamples": assumed_cameras,
        "blockers": [
            f"Independent source CHECK pixels are missing in {len(required_views) - checked_views} required view samples.",
            f"{assumed_cameras} view samples use an explicitly source-informed framing assumption, not a source-fitted camera.",
            "Rendered stage matching remains unmeasured; runtime coverage is not source measurement or fidelity completion.",
        ],
    }
    result["samplingDiagnostics"] = copy.deepcopy(data.get("samplingDiagnostics", {}))
    if data.get("nativeGeometryAssumptions"):
        result["nativeGeometryAssumptions"] = copy.deepcopy(data["nativeGeometryAssumptions"])
    return result


def bind_source_record(track, data, producer_path, *, executed_inputs=()):
    """Publication is associated with exact fresh observations, never borrowed receipts."""
    video_id = data["source"]["videoId"]
    path = WEB / "content/v39-source" / f"{video_id}.observations.json.gz"
    raw = path.read_bytes()
    decoded = fresh.decode_observation_bytes(raw)
    stored_sha256 = hashlib.sha256(raw).hexdigest()
    decoded_sha256 = hashlib.sha256(decoded).hexdigest()
    current = fresh.validate_observations(json.loads(decoded), video_id=video_id, web_root=WEB)
    if current != data:
        raise ValueError("Publication data differs from the actual fresh observation record")
    def relative(path):
        path = Path(path)
        return path.resolve().relative_to(WEB.parent).as_posix() if path.is_absolute() else path.as_posix()
    track["sourceRecord"] = {
        "kind": "current-source-observations",
        "path": path.relative_to(WEB).as_posix(),
        "sha256": stored_sha256,
        "decodedSha256": decoded_sha256,
        "producerPath": relative(producer_path),
        "executedInputs": sorted({relative(path) for path in executed_inputs}),
    }
    return track


def _validate_publication(track):
    record = track.get("sourceRecord")
    video_id = track.get("source", {}).get("videoId")
    expected = f"content/v39-source/{video_id}.observations.json.gz"
    if (track.get("kind") != "compact-source-track" or not isinstance(record, dict)
            or record.get("kind") != "current-source-observations"
            or record.get("path") != expected or not isinstance(record.get("producerPath"), str)
            or not isinstance(record.get("executedInputs"), list)
            or any(not isinstance(record.get(key), str)
                   or re.fullmatch(r"[0-9a-f]{64}", record[key]) is None
                   for key in ("sha256", "decodedSha256"))):
        raise ValueError("Only an actual fresh observation assembly can publish a current source track")
    raw = (WEB / expected).read_bytes()
    if hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Fresh source observations changed before publication")
    decoded = fresh.decode_observation_bytes(raw)
    if hashlib.sha256(decoded).hexdigest() != record["decodedSha256"]:
        raise ValueError("Fresh decoded source observations changed before publication")
    data = fresh.validate_observations(json.loads(decoded), video_id=video_id, web_root=WEB)
    validate_current_generation_inputs(data, record["producerPath"],
                                       executed_inputs=record["executedInputs"])
    if any(track.get(key) != data.get(key) for key in ("source", "model", "nativeIdentity")):
        raise ValueError("Current track source/native authority differs from fresh data")
    # Recompute selection and assembly, including exact-exposure unions; this cannot
    # bless a substituted old camera, borrowed native point, or authored stage pass.
    expected_track = build_track(copy.deepcopy(data),
                                 lambda frame: copy.deepcopy(frame["views"]),
                                 track.get("evidence", {}).get("notes", []))
    if expected_track["coverage"]["status"] != "complete":
        raise ValueError("Current publication requires complete source clocks/layouts/cameras/physical inputs")
    for key in ("anchors", "shots", "frames", "coverage", "stages", "sourceMeasurements",
                "nativeGeometryAssumptions"):
        if track.get(key) != expected_track.get(key):
            raise ValueError(f"Current track {key} differs from the actual fresh assembly")


def prepare_track(track):
    """Serialize without publishing, so paired outputs can be prepared together."""
    if track.get("kind") == "historical-source-track-receipt":
        raise ValueError("Historical receipt revalidation cannot publish a source track")
    _validate_publication(track)
    path = WEB / "content" / f'{track["source"]["videoId"]}.source-track.json'
    return path, json.dumps(track, separators=(",", ":"), allow_nan=False) + "\n"


def write_track(track):
    path, contents = prepare_track(track)
    path.write_text(contents)
    return path

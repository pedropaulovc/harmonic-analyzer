#!/usr/bin/env python3
"""Decode current actual-source frames and conservatively track identified physical features.

python web/scripts/observe-source.py --source /private/source.mp4
  --observations web/content/v39-source/XPQwKRt4Y2k.observations.json.gz
  --output /tmp/observed.observations.json.gz --inventory /tmp/current-model-inventory.json
Ordinary inputs/outputs require explicit gzip paths and the shared strict current authority.
Inventory remains ordinary JSON. New output JSON bytes use the shared deterministic codec.
Omitting --inventory loads the independently sealed current inventory.
--historical-diagnostic selects only the old materialized-derivative diagnostic;
private .json output is allowed, but never in current or immutable historical namespaces.

Only numeric observations are written. Never copies source frames/video into the repo.
Content classification comes from the human-observed shot census, NOT guessed image labels.
Part-axis section centres are virtual geometric measurements: they are NOT optical-flow
features. Track only anchors explicitly classified as physical-feature. A failed track
ends permanently until a genuinely observed manual seed, with no extrapolation/recovery
from CAD projections. Forward/backward flow and source-patch correlation reject occlusion,
appearance discontinuity and drift. These checks are conservative, not semantic proof.
Same-exposure aliases require the entire recorded source layout (not just an ROI)
and exact decoded image identity, including the pixel hash and native PTS.
Tracking never supplies a camera or mechanical input for a newly decoded exposure.
"""

import argparse
from bisect import bisect_left
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess

import cv2
import numpy as np

SPEC = importlib.util.spec_from_file_location("compact_source_common", Path(__file__).with_name("compact-source-common.py"))
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)


def fresh_contract():
    spec = importlib.util.spec_from_file_location(
        "fresh_source_observations", Path(__file__).with_name("fresh-source-observations.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_namespace(path, *, historical_diagnostic=False, output=False, video_id=None):
    declared = Path(path).absolute()
    path = declared.resolve()
    web = Path(__file__).resolve().parents[1]
    historical = (web / "content").resolve()
    current = (web / "content/v39-source").resolve()
    if declared != path and (
        declared.is_relative_to(historical) or path.is_relative_to(historical)
    ):
        raise ValueError("Published observation namespaces cannot use filesystem aliases")
    if path.is_relative_to(current):
        if historical_diagnostic:
            raise ValueError("Historical diagnostics cannot read or write current observations")
        if path.parent != current or not path.name.endswith(".observations.json.gz"):
            raise ValueError("Current observations use only direct .observations.json.gz namespace entries")
        if video_id is not None and path != current / f"{video_id}.observations.json.gz":
            raise ValueError("Current observations must use their registered video filename")
    if (
        path.is_relative_to(historical) and not path.is_relative_to(current)
        and (output or not historical_diagnostic)
    ):
        raise ValueError("Historical content is immutable and requires explicit diagnostic input")
    if not historical_diagnostic and declared.suffix != ".gz":
        raise ValueError("Current observation input/output requires an explicit .gz path")
    if historical_diagnostic and output:
        private = web / ".vite/verification-output"
        external_temp = not path.is_relative_to(web.parent) and any(
            path.is_relative_to(Path(temp).resolve()) for temp in ("/tmp", "/var/tmp"))
        private_escape = not path.is_relative_to(private) and any(
            parent.name == "verification-output" and parent.parent.name == ".vite"
            and parent.parent.parent.resolve() == web
            for parent in declared.parents)
        if private_escape or not (path.is_relative_to(private) or external_temp):
            raise ValueError("Historical diagnostics require private .vite/verification-output or external temporary output")


def frame_time(index, fps, pts=None):
    return index / fps if pts is None else pts[index]


def frame_layout(frame):
    """Closed source-pixel layout, independent of chosen cameras and mechanism inputs."""
    keys = (
        "rectSourcePixels", "sourceViewIds", "imagePlaneWarp", "resolvedImagePlaneWarp",
        "composite", "partOverrides", "anchorWorldMetres",
    )
    views = frame.get("views", [])
    result = {}
    for view in views:
        identity = view.get("id")
        if identity in result or not isinstance(identity, str) or not identity:
            return None
        result[identity] = {
            key: copy.deepcopy(view.get(key)) for key in keys
        }
        result[identity]["presentation"] = view.get("presentation", "native")
    return {
        "views": result,
        "viewOrder": [view["id"] for view in views],
        "presentation": frame.get("presentation", "native"),
        **{key: copy.deepcopy(frame.get(key)) for key in keys if key != "rectSourcePixels"},
    }


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def patch(image, point):
    x, y = point
    if not 12 <= x < image.shape[1] - 12 or not 12 <= y < image.shape[0] - 12:
        return None
    value = cv2.getRectSubPix(image, (21, 21), (float(x), float(y))).astype(float)
    return value - value.mean()


def correlation(first, second):
    if first is None or second is None:
        return -1.0
    norm = float(np.linalg.norm(first) * np.linalg.norm(second))
    return float((first * second).sum() / norm) if norm > 1e-6 else -1.0


def track_direction(cap, seed_index, boundary_index, seed, kinds, fps, pts=None):
    direction = 1 if boundary_index > seed_index else -1
    cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
    ok, image = cap.read()
    if not ok:
        raise ValueError("Cannot decode manually observed seed frame")
    previous = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    active = {
        (item.get("viewId"), item["anchorId"]): copy.deepcopy(item)
        for item in seed["landmarks"]
        if kinds[item["anchorId"]] == "physical-feature" and item["method"] == "manual"
    }
    seed_views = {
        view["id"]: view["rectSourcePixels"] for view in seed.get("views", [])
    }
    original_patches = {
        key: patch(previous, item["pixel"]) for key, item in active.items()
    }
    observed, failures = {}, []
    # Seek backward only when necessary; forward decoding stays sequential.
    for index in range(seed_index + direction, boundary_index + direction, direction):
        if not active:
            break
        if direction < 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, image = cap.read()
        if not ok:
            for key in active:
                failures.append(
                    {
                        "anchorId": key[1],
                        "viewId": key[0],
                        "timeSeconds": frame_time(index, fps, pts),
                        "reason": "source decode failed",
                        "direction": direction,
                    }
                )
            break
        current = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        keys = list(active)
        old = np.array(
            [active[key]["pixel"] for key in keys], dtype=np.float32
        ).reshape(-1, 1, 2)
        new, forward_status, _ = cv2.calcOpticalFlowPyrLK(
            previous, current, old, None, winSize=(25, 25), maxLevel=3
        )
        if new is None:
            for key in keys:
                failures.append(
                    {
                        "anchorId": key[1],
                        "viewId": key[0],
                        "timeSeconds": frame_time(index, fps, pts),
                        "reason": "optical flow failed",
                        "direction": direction,
                    }
                )
            break
        reverse, reverse_status, _ = cv2.calcOpticalFlowPyrLK(
            current, previous, new, None, winSize=(25, 25), maxLevel=3
        )
        for offset, key in enumerate(keys):
            candidate = new[offset, 0]
            backward_error = (
                float(np.linalg.norm(reverse[offset, 0] - old[offset, 0]))
                if reverse is not None
                else math.inf
            )
            similarity = correlation(original_patches[key], patch(current, candidate))
            local_similarity = correlation(
                patch(previous, old[offset, 0]), patch(current, candidate)
            )
            valid = (
                bool(forward_status[offset, 0])
                and reverse_status is not None
                and bool(reverse_status[offset, 0])
            )
            reason = None
            if not valid:
                reason = "flow lost visible source feature"
            elif backward_error > 1.0:
                reason = f"forward/backward inconsistency {backward_error:.3f}px (occlusion/discontinuity)"
            elif similarity < 0.80 or local_similarity < 0.90:
                reason = f"source appearance changed: seed correlation {similarity:.3f}, adjacent {local_similarity:.3f}"
            if reason is None and key[0] in seed_views:
                x, y, width, height = seed_views[key[0]]
                if (
                    not x <= candidate[0] < x + width
                    or not y <= candidate[1] < y + height
                ):
                    reason = "source feature left its independently identified source viewport"
            if reason:
                failures.append(
                    {
                        "anchorId": key[1],
                        "viewId": key[0],
                        "timeSeconds": frame_time(index, fps, pts),
                        "reason": reason,
                        "direction": direction,
                    }
                )
                del active[key]
                continue
            item = active[key]
            item["pixel"] = [float(candidate[0]), float(candidate[1])]
            item["method"] = "optical-flow"
            item["uncertaintyPx"] = max(item["uncertaintyPx"], backward_error)
            item["trackingEvidence"] = {
                "seedTimeSeconds": seed["timeSeconds"],
                "forwardBackwardErrorPx": backward_error,
                "seedPatchCorrelation": similarity,
                "adjacentPatchCorrelation": local_similarity,
            }
        observed[index] = [copy.deepcopy(item) for item in active.values()]
        previous = current
    return observed, failures


def repeated_source_views(cap, seed, shot, shots, fps, frame_count, pts=None):
    """Reacquire ONLY an actually repeated source view, using source images, not CAD.

    This does not interpolate through an occlusion. A new view must independently
    match the manual source image and EACH landmark's source patch. The manual
    section centre retains its geometric meaning only for this identical view.
    """
    seed_index = seed["sourceImage"]["frameIndex"] if pts is not None else round(seed["decodedTimeSeconds"] * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, seed_index)
    ok, image = cap.read()
    if not ok:
        raise ValueError("Cannot decode repeated-view manual seed")
    grey_seed = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ys, xs = np.where(grey_seed > 20)
    if not len(xs):
        return {}, []
    # Source-derived crop excludes unrelated overlay/credit regions.
    left, right = max(0, int(xs.min()) - 2), min(image.shape[1], int(xs.max()) + 3)
    top, bottom = max(0, int(ys.min()) - 2), min(image.shape[0], int(ys.max()) + 3)
    reference = cv2.resize(grey_seed[top:bottom, left:right], (160, 240)).astype(float)
    reference -= reference.mean()
    seeds = [item for item in seed["landmarks"] if item["method"] == "manual"]
    patterns = {
        (item.get("viewId"), item["anchorId"]): cv2.getRectSubPix(
            grey_seed, (21, 21), tuple(map(float, item["pixel"]))
        )
        for item in seeds
    }
    result, evidence = {}, []
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for index in range(frame_count):
        ok, image = cap.read()
        if not ok:
            break
        time = frame_time(index, fps, pts)
        current_shot = next(
            (
                item
                for item in shots
                if item["startSeconds"] <= time < item["endSeconds"]
            ),
            None,
        )
        if (
            current_shot is None
            or current_shot["classification"] != "machine"
            or current_shot.get("continuityGroup", current_shot["id"])
            != shot.get("continuityGroup", shot["id"])
        ):
            continue
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(grey[top:bottom, left:right], (160, 240)).astype(float)
        small -= small.mean()
        whole_correlation = correlation(reference, small)
        if whole_correlation < 0.998:
            continue
        landmarks = []
        for original in seeds:
            px, py = map(float, original["pixel"])
            x0, y0 = round(px) - 14, round(py) - 14
            if x0 < 0 or y0 < 0 or x0 + 29 > grey.shape[1] or y0 + 29 > grey.shape[0]:
                break
            score = cv2.matchTemplate(
                grey[y0 : y0 + 29, x0 : x0 + 29],
                patterns[(original.get("viewId"), original["anchorId"])],
                cv2.TM_CCOEFF_NORMED,
            )
            _, maximum, _, location = cv2.minMaxLoc(score)
            if maximum < 0.97:
                break
            item = copy.deepcopy(original)
            item["pixel"] = [float(x0 + location[0] + 10), float(y0 + location[1] + 10)]
            item["method"] = "template-match"
            item["trackingEvidence"] = {
                "seedTimeSeconds": seed["timeSeconds"],
                "wholeSourceViewCorrelation": whole_correlation,
                "sourcePatchCorrelation": maximum,
                "reacquiredFromActualPixels": True,
            }
            landmarks.append(item)
        if len(landmarks) != len(seeds):
            continue
        result[index] = landmarks
        evidence.append(
            {
                "decodedTimeSeconds": time,
                "frameIndex": index,
                "sourceViewCorrelation": whole_correlation,
            }
        )
    return result, evidence


def needs_machine(frame, shot):
    """Same monotonic frame/shot rule as the fitter and acceptance consumer."""
    if "sourceMachineRequirement" in frame:
        if frame["sourceMachineRequirement"] != "required":
            raise ValueError(
                "Source frame sourceMachineRequirement must be the literal required"
            )
        return True
    classification = frame["classification"]
    if classification == "machine":
        return True
    if classification == "non-machine":
        return shot.get("hasCorrespondingMachine") is True
    return shot.get("hasCorrespondingMachine") is not False


def exact_exposure_landmarks(seed, frame, source_image, kinds):
    """Reuse manual physical pixels only for identical decoded exposures AND full layouts."""
    hash_key = {"bgr8": "sha256Bgr8", "gray8": "sha256Gray8"}.get(
        source_image.get("pixelFormat") if isinstance(source_image, dict) else None
    )
    if hash_key is None:
        return []
    identity_keys = (
        "frameIndex", "sourceSha256", hash_key, "pixelFormat", "width", "height",
    )
    if (
        seed["shotId"] != frame["shotId"]
        or not isinstance(source_image, dict)
        or any(key not in source_image for key in identity_keys)
    ):
        return []
    identities = (seed.get("sourceImage"), frame.get("sourceImage", source_image))
    if any(
        not isinstance(identity, dict)
        or any(
            key not in identity or identity[key] != source_image[key]
            for key in identity_keys
        )
        for identity in identities
    ):
        return []
    if (
        type(seed.get("decodedTimeSeconds")) not in (int, float)
        or type(frame.get("decodedTimeSeconds")) not in (int, float)
        or not math.isfinite(seed["decodedTimeSeconds"])
        or not math.isfinite(frame["decodedTimeSeconds"])
        or seed["decodedTimeSeconds"] != frame["decodedTimeSeconds"]
        or frame_layout(seed) is None
        or frame_layout(seed) != frame_layout(frame)
    ):
        return []
    seed_views = {
        view["id"]: view["rectSourcePixels"] for view in seed.get("views", [])
    }
    target_views = {
        view["id"]: view["rectSourcePixels"]
        for view in frame.get("views", [])
    }
    return [
        copy.deepcopy(item)
        for item in seed["landmarks"]
        if kinds[item["anchorId"]] == "physical-feature"
        and item["method"] == "manual"
        and (
            item.get("viewId") is None
            or (
                item["viewId"] in seed_views
                and target_views.get(item["viewId"]) == seed_views[item["viewId"]]
            )
        )
    ]


def _observe_historical(data, source_path, match_repeated_view=False):
    if digest(source_path) != data["source"]["sha256"]:
        raise ValueError("Private source hash does not match observation provenance")
    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        raise ValueError("Cannot open actual source")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if (width, height) != (data["source"]["width"], data["source"]["height"]):
        raise ValueError("Source frame size differs from manual observations")
    output = copy.deepcopy(data)
    kinds = {
        anchor["id"]: anchor.get("kind", "section-center") for anchor in data["anchors"]
    }
    shots = {shot["id"]: shot for shot in data["shots"]}
    manual_seeds = [
        frame
        for frame in data["frames"]
        if any(item["method"] == "manual" for item in frame["landmarks"])
    ]
    tracked, failures = {}, []
    for seed in manual_seeds:
        shot = shots[seed["shotId"]]
        seed_index = round(seed["decodedTimeSeconds"] * fps)
        for boundary in (
            math.ceil(shot["startSeconds"] * fps),
            min(frame_count - 1, math.ceil(shot["endSeconds"] * fps) - 1),
        ):
            if boundary == seed_index:
                continue
            observations, stopped = track_direction(
                cap, seed_index, boundary, seed, kinds, fps
            )
            for index, values in observations.items():
                existing = {
                    (item.get("viewId"), item["anchorId"]): item
                    for item in tracked.get(index, [])
                }
                for item in values:
                    # Prefer the closer genuinely observed seed, never a model-projected point.
                    key = (item.get("viewId"), item["anchorId"])
                    old = existing.get(key)
                    if old is None or abs(
                        index / fps - item["trackingEvidence"]["seedTimeSeconds"]
                    ) < abs(index / fps - old["trackingEvidence"]["seedTimeSeconds"]):
                        existing[key] = item
                tracked[index] = list(existing.values())
            failures.extend(stopped)
    repeated, repeated_evidence = {}, []
    if match_repeated_view:
        for seed in manual_seeds:
            if not seed.get("repeatSourceViewSeed", True):
                continue
            values, evidence = repeated_source_views(
                cap, seed, shots[seed["shotId"]], data["shots"], fps, frame_count
            )
            repeated.update(values)
            repeated_evidence.extend(evidence)
        # These are new source-image measurements, NOT optical-flow continuation.
        tracked.update(repeated)
    # Full cadence PLUS every native-frame tracking observation, loss and content boundary.
    existing = {frame["timeSeconds"]: frame for frame in output["frames"]}
    wanted = set(range(math.ceil(data["source"]["durationSeconds"])))
    wanted.update(shot["startSeconds"] for shot in data["shots"])
    wanted.update(index / fps for index, values in tracked.items() if values)
    wanted.update(item["timeSeconds"] for item in failures)
    wanted.update(existing)
    source_images = {}

    def source_image(index):
        if index not in source_images:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f"Cannot reproduce source observation frame {index}")
            source_images[index] = {
                "frameIndex": index,
                "sha256Bgr8": hashlib.sha256(image.tobytes()).hexdigest(),
                "pixelFormat": "bgr8",
                "width": width,
                "height": height,
                "sourceSha256": data["source"]["sha256"],
            }
        return source_images[index]

    all_frames = []
    for t in sorted(wanted):
        if not 0 <= t < data["source"]["durationSeconds"]:
            continue
        index = min(frame_count - 1, round(t * fps))
        shot = next(
            shot
            for shot in data["shots"]
            if shot["startSeconds"] <= t < shot["endSeconds"]
        )
        frame = existing.get(t)
        if frame is None:
            frame = {
                "timeSeconds": t,
                "decodedTimeSeconds": index / fps,
                "shotId": shot["id"],
                "classification": shot["classification"],
                "landmarks": [],
                "unavailable": [],
                "camera": None,
            }
            required = needs_machine(frame, shot)
            state = copy.deepcopy(
                shot.get(
                    "mechanicalState",
                    {
                        "status": "unobservable" if required else "not-applicable",
                        "input": None,
                        "evidence": "No measured mechanical input for this required native source frame; it remains unavailable."
                        if required
                        else "Shot census declares no corresponding mechanism; no source pose is asserted.",
                    },
                )
            )
            frame["mechanicalState"] = state
            seed_times = [
                item["trackingEvidence"]["seedTimeSeconds"]
                for item in tracked.get(index, [])
            ]
            if seed_times:
                seed = next(
                    item
                    for item in manual_seeds
                    if item["timeSeconds"] == seed_times[0]
                )
                if seed.get("views"):
                    frame["views"] = copy.deepcopy(seed["views"])
                    for view in frame["views"]:
                        view["camera"] = None
                        view["mechanicalState"] = copy.deepcopy(state)
        required = needs_machine(frame, shot)
        if not frame["landmarks"] and frame["classification"] == "machine":
            exposure_index = round(frame["decodedTimeSeconds"] * fps)
            for seed in manual_seeds:
                if (
                    seed["shotId"] != frame["shotId"]
                    or round(seed["decodedTimeSeconds"] * fps) != exposure_index
                    or not seed.get("sourceImage")
                    or ("sourceImage" in frame and not frame["sourceImage"])
                ):
                    continue
                aliases = exact_exposure_landmarks(
                    seed, frame, source_image(exposure_index), kinds
                )
                if aliases:
                    frame["landmarks"] = aliases
                    break
        if not frame["landmarks"] and frame["classification"] == "machine":
            frame["landmarks"] = copy.deepcopy(tracked.get(index, []))
        observed_ids = {item["anchorId"] for item in frame["landmarks"]}
        if required:
            frame["unavailable"] = [
                {
                    "anchorId": anchor["id"],
                    "reason": "No verified measurement at this source frame; axis centres are not optical-flow features and physical tracks stop at occlusion/appearance failure.",
                }
                for anchor in data["anchors"]
                if anchor["id"] not in observed_ids
            ]
        frame["camera"] = None
        for view in frame.get("views", []):
            view["camera"] = None
        all_frames.append(frame)
    # Hash real decoded BGR bytes, not a re-encoded PNG or a rendered model.
    measured_indices = sorted(
        {
            round(frame["decodedTimeSeconds"] * fps)
            for frame in all_frames
            if frame["landmarks"]
        }
    )
    for index in measured_indices:
        source_image(index)
    for frame in all_frames:
        if frame["landmarks"]:
            frame["sourceImage"] = source_images[
                round(frame["decodedTimeSeconds"] * fps)
            ]
    cap.release()
    output["frames"] = all_frames
    output["tracking"] = {
        "method": "native-frame pyramidal Lucas-Kanade, forward/backward <=1px, seed NCC>=0.80, adjacent NCC>=0.90; no CAD-generated pixels",
        "failures": failures,
        "observedNativeFrameCount": sum(bool(values) for values in tracked.values()),
        "autoReacquisition": False,
    }
    output["sourceViewReacquisition"] = {
        "enabled": match_repeated_view,
        "method": "actual-source whole-view NCC>=0.998 plus EACH independently located 21px landmark template NCC>=0.97; no temporal/camera extrapolation or CAD-generated pixels",
        "acceptedNativeFrames": repeated_evidence,
    }
    return output


def source_clock(source_path):
    """Read real per-exposure PTS, never reconstruct a clock from an average FPS."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
            "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(source_path),
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise ValueError("Cannot establish actual decoded source PTS: " + result.stderr.strip())
    frames = json.loads(result.stdout).get("frames", [])
    pts = []
    for frame in frames:
        try:
            time = float(frame["best_effort_timestamp_time"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Actual source exposure lacks a supported decoded PTS") from error
        if not math.isfinite(time) or time < 0 or (pts and time <= pts[-1]):
            raise ValueError("Actual source PTS must be finite, nonnegative and strictly increasing")
        pts.append(time)
    if not pts:
        raise ValueError("Actual source has no supported decoded exposures")
    return pts


class CheckedCapture:
    """Bind every decoded byte array to the index and PTS actually reported by its decoder."""

    def __init__(self, path, pts, width, height):
        self.cap = cv2.VideoCapture(str(path))
        self.pts = pts
        self.dimensions = (width, height)
        self.next_index = 0
        if not self.cap.isOpened():
            self.cap.release()
            raise ValueError("Cannot open actual source")

    def set(self, key, value):
        if key != cv2.CAP_PROP_POS_FRAMES:
            raise ValueError("Current source decoding permits only explicit native-frame seeks")
        if type(value) is not int or not 0 <= value < len(self.pts):
            raise ValueError("Requested native exposure is unsupported by the actual source")
        if not self.cap.set(key, value):
            raise ValueError(f"Cannot seek actual native exposure {value}")
        self.next_index = value
        return True

    def read(self):
        index = self.next_index
        ok, image = self.cap.read()
        if not ok:
            return False, image
        if index >= len(self.pts):
            raise ValueError("Decoder produced an exposure absent from the actual source clock")
        reported = self.cap.get(cv2.CAP_PROP_POS_FRAMES)
        reported_time = self.cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if (
            not math.isfinite(reported)
            or abs(reported - index - 1) > 1e-6
            or not math.isfinite(reported_time)
            or abs(reported_time - self.pts[index]) > 1e-3
        ):
            raise ValueError(f"Decoder cannot establish exact native index/PTS for frame {index}")
        if (image.shape[1], image.shape[0]) != self.dimensions:
            raise ValueError("Decoded source dimensions differ from current observations")
        self.next_index += 1
        return True, image

    def release(self):
        self.cap.release()


def observe(data, source_path, match_repeated_view=False, *, inventory=None, historical_diagnostic=False):
    """Measure current pixels only; unsolved source cameras/inputs remain explicit and blocked."""
    if historical_diagnostic:
        if data.get("identityDerivative", {}).get("kind") != "materialized-canonical-native-identity-derivative":
            raise ValueError("Historical diagnostics require a materialized canonical-native derivative")
        if data.get("kind") == "current-source-observations":
            raise ValueError("Current observations cannot enter the historical diagnostic path")
        output = _observe_historical(data, source_path, match_repeated_view)
        output["historicalDiagnostic"] = True
        return output
    contract = fresh_contract()
    if inventory is None:
        inventory = contract.load_inventory()
    contract.validate_observations(data, inventory=inventory)
    if digest(source_path) != data["source"]["sha256"]:
        raise ValueError("Actual source SHA256 differs from current observation authority")
    pts = source_clock(source_path)
    cap = CheckedCapture(source_path, pts, data["source"]["width"], data["source"]["height"])
    try:
        return _observe_current(data, cap, pts, inventory, contract, match_repeated_view)
    finally:
        cap.release()


def _observe_current(data, cap, pts, inventory, contract, match_repeated_view):
    output = copy.deepcopy(data)
    output.pop("fitReport", None)
    source_images = {}

    def source_image(index, pixel_format="bgr8"):
        key = (index, pixel_format)
        if key not in source_images:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f"Cannot decode actual native exposure {index}")
            if pixel_format == "gray8":
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif pixel_format != "bgr8":
                raise ValueError("Unsupported actual source pixel format")
            hash_key = "sha256Bgr8" if pixel_format == "bgr8" else "sha256Gray8"
            source_images[key] = {
                "frameIndex": index, hash_key: hashlib.sha256(image.tobytes()).hexdigest(),
                "pixelFormat": pixel_format, "width": data["source"]["width"],
                "height": data["source"]["height"], "sourceSha256": data["source"]["sha256"],
            }
        return source_images[key]

    kinds = {anchor["id"]: anchor.get("kind", "section-center") for anchor in data["anchors"]}
    shots = {shot["id"]: shot for shot in data["shots"]}
    existing = {frame["timeSeconds"]: frame for frame in output["frames"]}
    layouts = {}
    exemplars = {}
    for frame in output["frames"]:
        image = frame["sourceImage"]
        index = image["frameIndex"]
        if (
            not 0 <= index < len(pts)
            or abs(frame["decodedTimeSeconds"] - pts[index]) > 1e-6
            or frame.get("decodedFrameIndex", index) != index
            or image != source_image(index, image["pixelFormat"])
        ):
            raise ValueError(f"{frame['timeSeconds']}: recorded source image/index/PTS differs from actual decoding")
        identity = frame["shotId"]
        layout = frame_layout(frame)
        if identity not in layouts:
            layouts[identity] = layout
            exemplars[identity] = frame
        elif layouts[identity] != layout:
            layouts[identity] = None
    transferable = {
        shot_id: layout is not None and all(
            view.get("imagePlaneWarp") is None
            and view.get("resolvedImagePlaneWarp") is None
            and (view.get("composite") or {}).get("mode", "opaque") == "opaque"
            for view in exemplars[shot_id]["views"]
        )
        for shot_id, layout in layouts.items()
    }
    manual_seeds = [
        frame for frame in output["frames"]
        if any(item["method"] == "manual" for item in frame["landmarks"])
    ]
    tracked, failures = {}, []
    for seed in manual_seeds:
        shot = shots[seed["shotId"]]
        if not transferable.get(seed["shotId"], False):
            failures.append({
                "timeSeconds": seed["timeSeconds"],
                "reason": "Source layout changes or is ambiguous; no automatic seed donation across warps/compositing",
            })
            continue
        seed_index = seed["sourceImage"]["frameIndex"]
        first = bisect_left(pts, shot["startSeconds"])
        last = bisect_left(pts, shot["endSeconds"]) - 1
        for boundary in (first, last):
            if boundary == seed_index or not 0 <= boundary < len(pts):
                continue
            values, stopped = track_direction(cap, seed_index, boundary, seed, kinds, 1, pts)
            for index, measurements in values.items():
                previous = {
                    (item.get("viewId"), item["anchorId"]): item for item in tracked.get(index, [])
                }
                for item in measurements:
                    key = (item.get("viewId"), item["anchorId"])
                    old = previous.get(key)
                    if old is None or abs(pts[index] - item["trackingEvidence"]["seedTimeSeconds"]) < abs(
                        pts[index] - old["trackingEvidence"]["seedTimeSeconds"]
                    ):
                        previous[key] = item
                tracked[index] = list(previous.values())
            failures.extend(stopped)
    repeated_evidence = []
    if match_repeated_view:
        for seed in manual_seeds:
            if not transferable.get(seed["shotId"], False) or not seed.get("repeatSourceViewSeed", True):
                continue
            values, evidence = repeated_source_views(
                cap, seed, shots[seed["shotId"]], data["shots"], 1, len(pts), pts,
            )
            for index, measurements in values.items():
                shot = next((item for item in data["shots"] if item["startSeconds"] <= pts[index] < item["endSeconds"]), None)
                if shot and transferable.get(shot["id"], False) and layouts.get(shot["id"]) == frame_layout(seed):
                    tracked[index] = measurements
                    repeated_evidence.extend(row for row in evidence if row["frameIndex"] == index)
    wanted = set(range(math.ceil(data["source"]["durationSeconds"]))) | set(existing)
    wanted.update(shot["startSeconds"] for shot in data["shots"])
    wanted.update(pts[index] for index, values in tracked.items() if values)
    wanted.update(data["coverage"].get("changeTimesSeconds", []))
    wanted.update(item["timeSeconds"] for item in failures)
    blockers = output["coverage"]["blockers"]
    all_frames = []
    for requested in sorted(wanted):
        if not 0 <= requested < data["source"]["durationSeconds"]:
            continue
        shot = next(item for item in data["shots"] if item["startSeconds"] <= requested < item["endSeconds"])
        frame = existing.get(requested)
        if frame is None:
            position = bisect_left(pts, requested)
            candidates = [index for index in (position - 1, position) if 0 <= index < len(pts)
                          and shot["startSeconds"] <= pts[index] < shot["endSeconds"]]
            if not candidates:
                raise ValueError(f"{requested}: no supported actual exposure in the requested shot")
            index = min(candidates, key=lambda value: abs(pts[value] - requested))
            if abs(pts[index] - requested) > 0.5:
                raise ValueError(f"{requested}: no supported actual exposure within the source clock tolerance")
            exact = next((
                item for item in output["frames"]
                if item["shotId"] == shot["id"] and item["sourceImage"]["frameIndex"] == index
            ), None)
            frame = copy.deepcopy(exact) if exact is not None else {
                "timeSeconds": requested, "decodedTimeSeconds": pts[index],
                "decodedFrameIndex": index, "shotId": shot["id"], "classification": shot["classification"],
                "landmarks": [], "unavailable": [], "views": [],
            }
            frame["timeSeconds"] = requested
            exemplar = exemplars.get(shot["id"])
            if exact is None and transferable.get(shot["id"], False) and exemplar:
                for original in exemplar["views"]:
                    view = copy.deepcopy(original)
                    for key in (
                        "cameraMeasurement", "nativeLineChecks", "anchorPoseEvidence", "anchorPoseMissing",
                        "cameraFit", "cameraInterpolationEvidence",
                    ):
                        view.pop(key, None)
                    view["camera"] = None
                    view["input"] = None
                    view["provenance"] = common.chosen_provenance(
                        "No complete current input measured for this newly decoded exposure."
                    )
                    family = f"{data['source']['videoId']}:{shot['id']}:{view['id']}:unavailable"
                    view["cameraProvenance"] = {
                        "kind": "source-informed-framing", "family": family,
                        "evidence": "Source pixel tracking does not solve a current source camera.",
                    }
                    view["cameraContinuityFamily"] = family
                    view["cameraInterpolation"] = "held"
                    view["unavailable"] = [{"reason": "No current camera or complete mechanism input for this decoded exposure"}]
                    frame["views"].append(view)
        index = frame["sourceImage"]["frameIndex"] if "sourceImage" in frame else index
        image = source_image(index, frame.get("sourceImage", {}).get("pixelFormat", "bgr8"))
        frame["sourceImage"] = copy.deepcopy(image)
        frame["decodedFrameIndex"] = index
        frame.setdefault("unavailable", [])
        if not frame["landmarks"] and frame["classification"] == "machine":
            for seed in manual_seeds:
                aliases = exact_exposure_landmarks(seed, frame, image, kinds)
                if aliases:
                    frame["landmarks"] = aliases
                    break
        pixel_tracking = False
        if not frame["landmarks"] and frame["classification"] == "machine" and layouts.get(shot["id"]) == frame_layout(frame):
            frame["landmarks"] = copy.deepcopy(tracked.get(index, []))
            pixel_tracking = bool(frame["landmarks"])
        if pixel_tracking:
            for landmark in frame["landmarks"]:
                evidence = landmark["trackingEvidence"]
                seed = next(item for item in manual_seeds if item["timeSeconds"] == evidence["seedTimeSeconds"])
                evidence["seedSourceImage"] = copy.deepcopy(seed["sourceImage"])
                evidence["sourceImage"] = copy.deepcopy(image)
                original_measurement = landmark.pop("measurementEvidence", None)
                if original_measurement is not None:
                    evidence["seedMeasurementEvidence"] = original_measurement
            for view in frame["views"]:
                view["camera"] = None
                view.pop("cameraMeasurement", None)
                view.setdefault("unavailable", []).append({"reason": "Tracked source pixels require a new current camera fit"})
        required = needs_machine(frame, shot)
        observed = {
            (
                item.get("viewId", "main"),
                item["anchorId"],
            )
            for item in frame["landmarks"]
        }
        if required:
            for view in frame["views"]:
                for anchor in data["anchors"]:
                    if (view["id"], anchor["id"]) not in observed:
                        frame["unavailable"].append({
                            "anchorId": anchor["id"], "viewId": view["id"],
                            "reason": "No verified current source pixel at this actual decoded exposure",
                        })
        unknown = [view for view in frame["views"] if view["camera"] is None or view["input"] is None]
        if (required and not frame["views"]) or unknown:
            reason = "Current source layout, camera or complete input remains unsolved"
            frame["unavailable"].append({"reason": reason})
            for view in unknown:
                if not view.get("unavailable"):
                    view["unavailable"] = [{"reason": reason}]
            blocker = f"{requested}: {reason}"
            if blocker not in blockers:
                blockers.append(blocker)
        all_frames.append(frame)
    output["frames"] = all_frames
    output["tracking"] = {
        "method": "Actual-native-PTS pyramidal Lucas-Kanade, forward/backward <=1px, seed NCC>=0.80, adjacent NCC>=0.90; no CAD-generated pixels",
        "failures": failures, "observedNativeFrameCount": sum(bool(values) for values in tracked.values()),
        "autoReacquisition": False,
    }
    output["sourceViewReacquisition"] = {
        "enabled": match_repeated_view, "method": "Actual-source whole-view NCC>=0.998 plus each manual landmark template NCC>=0.97; identical complete recorded layout required",
        "acceptedNativeFrames": repeated_evidence,
    }
    if blockers:
        output["coverage"]["status"] = "blocked"
    contract.validate_observations(output, inventory=inventory)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True, help="Explicit .gz observations; historical diagnostics use their original storage")
    parser.add_argument("--output", type=Path, required=True, help="Gzip observations; private .json is permitted only with --historical-diagnostic")
    parser.add_argument("--inventory", type=Path, help="Actual current inventory, stored as ordinary JSON; defaults to independently sealed authority")
    parser.add_argument(
        "--historical-diagnostic", action="store_true",
        help="Run the old materialized-derivative diagnostic, never current publication",
    )
    parser.add_argument(
        "--match-repeated-view",
        action="store_true",
        help="Independently measure only actual source images matching a manual seed view",
    )
    args = parser.parse_args()
    check_namespace(args.observations, historical_diagnostic=args.historical_diagnostic)
    observations = (
        common.read_observations(args.observations) if args.historical_diagnostic
        else json.loads(fresh_contract().read_observation_bytes(args.observations))
    )
    check_namespace(
        args.observations, historical_diagnostic=args.historical_diagnostic,
        video_id=observations["source"]["videoId"],
    )
    check_namespace(
        args.output, historical_diagnostic=args.historical_diagnostic,
        output=True, video_id=observations["source"]["videoId"],
    )
    inventory = json.loads(args.inventory.read_text()) if args.inventory else None
    output = observe(
        observations, args.source, args.match_repeated_view,
        inventory=inventory, historical_diagnostic=args.historical_diagnostic,
    )
    if args.historical_diagnostic:
        common.write_observations(args.output, output)
    else:
        decoded = (json.dumps(output, indent=2) + "\n").encode("utf-8")
        args.output.write_bytes(fresh_contract().encode_observation_bytes(decoded))
    print(
        json.dumps(
            {
                "videoId": output["source"]["videoId"],
                "sampleCount": len(output["frames"]),
                "framesWithSourcePixels": sum(
                    bool(frame["landmarks"]) for frame in output["frames"]
                ),
                "tracking": output["tracking"],
                "coverage": output["coverage"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

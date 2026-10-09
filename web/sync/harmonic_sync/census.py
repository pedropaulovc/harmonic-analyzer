"""Preserve the human shot census and representative source view layouts.

Existing committed censuses are authoritative: refresh only source metadata and
preserve hand-edited shots, layouts, and reclassification annotations. On first
extraction, each view uses its most frequent observed rectangle/presentation pair;
ties prefer the shot midpoint, then the earliest observation. Every view identity
is retained, including transition-only views. Static layouts are starting points,
not a reconstruction of animated crops.
"""

from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = Path(__file__).resolve().parents[2]
_CLASSIFICATIONS = {"machine", "transition", "non-machine"}
_PRESENTATIONS = {"native", "horizontal-mirror"}


def _number(value: object, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{context}: expected a finite number, got {value!r}")
    return value


def _source_metadata(path: Path) -> tuple[str, list[int], int, int]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,r_frame_rate",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    streams = json.loads(probe.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"{path}: ffprobe found no video stream")
    stream = streams[0]
    width, height = stream["width"], stream["height"]
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError(f"{path}: invalid source dimensions {width!r} x {height!r}")
    # Average rate is the container's actual frame-count/time rate; the nominal
    # stream rate is only a fallback for containers that do not report it.
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            fps = Fraction(stream.get(key, "0/0"))
        except (ValueError, ZeroDivisionError):
            continue
        if fps > 0:
            return digest.hexdigest(), [fps.numerator, fps.denominator], width, height
    raise ValueError(f"{path}: ffprobe did not report a positive frame rate")


def _view_layout(
    view: dict, width: int, height: int, context: str, id_key: str = "id",
) -> tuple:
    if not isinstance(view, dict):
        raise ValueError(f"{context}: view must be an object")
    view_id = view.get(id_key)
    if not isinstance(view_id, str) or not view_id:
        raise ValueError(f"{context}: view id must be a nonempty string")
    presentation = view.get("presentation")
    if presentation not in _PRESENTATIONS:
        raise ValueError(f"{context}/{view_id}: invalid presentation {presentation!r}")
    rect = view.get("rectSourcePixels")
    if not isinstance(rect, list) or len(rect) != 4:
        raise ValueError(f"{context}/{view_id}: expected [x, y, width, height]")
    x, y, w, h = (_number(value, f"{context}/{view_id} rectangle") for value in rect)
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError(f"{context}/{view_id}: rectangle {rect!r} outside {width} x {height}")
    return view_id, tuple(rect), presentation


def _validate_census(census: dict, video_id: str, width: int, height: int) -> None:
    """Validate hand edits without normalizing or discarding their fields."""
    if not isinstance(census, dict) or census.get("videoId") != video_id:
        raise ValueError(f"{video_id}: census videoId must match the requested video")
    shots = census.get("shots")
    if not isinstance(shots, list):
        raise ValueError(f"{video_id}: census shots must be an array")
    shot_ids = set()
    for shot in shots:
        if not isinstance(shot, dict):
            raise ValueError(f"{video_id}: each census shot must be an object")
        shot_id = shot.get("id")
        if not isinstance(shot_id, str) or not shot_id or shot_id in shot_ids:
            raise ValueError(f"{video_id}: missing or duplicate shot id {shot_id!r}")
        shot_ids.add(shot_id)
        context = f"{video_id}/{shot_id}"
        if shot.get("classification") not in _CLASSIFICATIONS:
            raise ValueError(f"{context}: invalid classification {shot.get('classification')!r}")
        if "reclassifiedFrom" in shot and shot["reclassifiedFrom"] not in _CLASSIFICATIONS:
            raise ValueError(f"{context}: invalid reclassifiedFrom {shot['reclassifiedFrom']!r}")
        start = _number(shot.get("start"), f"{context} start")
        end = _number(shot.get("end"), f"{context} end")
        if start < 0 or end <= start:
            raise ValueError(f"{context}: invalid shot interval [{start}, {end}]")
        if not isinstance(shot.get("reason"), str):
            raise ValueError(f"{context}: reason must be a string")
        views = shot.get("views")
        if not isinstance(views, list):
            raise ValueError(f"{context}: views must be an array")
        view_ids = set()
        for view in views:
            view_id, _, _ = _view_layout(view, width, height, context, id_key="viewId")
            if view_id in view_ids:
                raise ValueError(f"{context}: duplicate view id {view_id!r}")
            view_ids.add(view_id)


def extract_shots(video_id: str) -> dict:
    """Refresh an authoritative census, or bootstrap one from observations.

    Existing ``videos/<video_id>/shots.json`` needs no observation file and keeps
    all hand-edited shot fields and layouts. Only sourceSha256 and fps change.
    Source MP4s live under ``HARMONIC_SYNC_VIDEOS`` or, by default,
    ``~/data/harmonic-analyzer-videos``. Missing or malformed input fails before
    writing the census; no source frames or videos are copied into the project.
    """
    if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", video_id):
        raise ValueError(f"Invalid video id: {video_id!r}")
    destination = PROJECT_ROOT / "videos" / video_id / "shots.json"
    videos_root = Path(os.environ.get("HARMONIC_SYNC_VIDEOS", "~/data/harmonic-analyzer-videos")).expanduser()
    sha256, fps, width, height = _source_metadata(videos_root / f"{video_id}.mp4")
    if destination.exists():
        with destination.open(encoding="utf-8") as source:
            census = json.load(source)
        _validate_census(census, video_id, width, height)
        census["sourceSha256"] = sha256
        census["fps"] = fps
        destination.write_text(
            json.dumps(census, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return census

    observations_path = WEB_ROOT / "content" / f"{video_id}.observations.json"
    with observations_path.open(encoding="utf-8") as source:
        observations = json.load(source)
    shots = observations.get("shots")
    frames = observations.get("frames")
    if not isinstance(shots, list) or not isinstance(frames, list):
        raise ValueError(f"{observations_path}: shots and frames must be arrays")

    extracted = []
    by_id = {}
    for shot in shots:
        shot_id = shot.get("id")
        if not isinstance(shot_id, str) or not shot_id or shot_id in by_id:
            raise ValueError(f"{observations_path}: missing or duplicate shot id {shot_id!r}")
        classification = shot.get("classification")
        if classification not in _CLASSIFICATIONS:
            raise ValueError(f"{video_id}/{shot_id}: invalid classification {classification!r}")
        start = _number(shot.get("startSeconds"), f"{video_id}/{shot_id} start")
        end = _number(shot.get("endSeconds"), f"{video_id}/{shot_id} end")
        if start < 0 or end <= start:
            raise ValueError(f"{video_id}/{shot_id}: invalid shot interval [{start}, {end}]")
        reason = shot.get("reason")
        if not isinstance(reason, str):
            raise ValueError(f"{video_id}/{shot_id}: reason must be a string")
        record = {"id": shot_id, "start": start, "end": end,
                  "classification": classification, "reason": reason, "views": []}
        extracted.append(record)
        by_id[shot_id] = record

    # Collect every explicit view by shotId rather than using a single frame or
    # assuming views exist on the first machine frame (Analysis has none early).
    samples = {}
    for index, frame in enumerate(frames):
        views = frame.get("views", [])
        if not isinstance(views, list):
            raise ValueError(f"{video_id}/frame-{index}: views must be an array")
        if not views:
            continue
        shot_id = frame.get("shotId")
        if shot_id not in by_id:
            raise ValueError(f"{video_id}/frame-{index}: unknown shot id {shot_id!r}")
        time = _number(frame.get("timeSeconds"), f"{video_id}/frame-{index} time")
        shot_views = samples.setdefault(shot_id, {})
        for view in views:
            view_id, rect, presentation = _view_layout(view, width, height, f"{video_id}/{shot_id}")
            shot_views.setdefault(view_id, []).append((rect, presentation, time, index))

    for shot in extracted:
        midpoint = (shot["start"] + shot["end"]) / 2
        for view_id, candidates in samples.get(shot["id"], {}).items():
            presentations = {candidate[1] for candidate in candidates}
            if len(presentations) != 1:
                raise ValueError(
                    f"{video_id}/{shot['id']}/{view_id}: presentation changes within one view; "
                    "a single static shot layout cannot preserve both presentations"
                )
            counts = Counter((rect, presentation) for rect, presentation, _, _ in candidates)
            rect, presentation, _, _ = min(
                candidates,
                key=lambda item: (-counts[item[:2]], abs(item[2] - midpoint), item[2], item[3]),
            )
            shot["views"].append({"viewId": view_id, "rectSourcePixels": list(rect),
                                  "presentation": presentation})
        if not shot["views"] and shot["classification"] in {"machine", "transition"}:
            shot["views"].append({"viewId": "main", "rectSourcePixels": [0, 0, width, height],
                                  "presentation": "native"})

    census = {"videoId": video_id, "sourceSha256": sha256, "fps": fps, "shots": extracted}
    _validate_census(census, video_id, width, height)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(census, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return census

"""Private video paths, source hashes and PTS-checked decoding."""
from __future__ import annotations

import hashlib
import json
import math
import os
from fractions import Fraction
from pathlib import Path
import subprocess

import av
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]


def data_root() -> Path:
    return Path(os.environ.get("HARMONIC_SYNC_DATA", "~/data/harmonic-analyzer-sync")).expanduser()


def video_path(video_id: str) -> Path:
    root = Path(os.environ.get("HARMONIC_SYNC_VIDEOS", "~/data/harmonic-analyzer-videos")).expanduser()
    return root / f"{video_id}.mp4"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_shots(video_id: str) -> dict:
    return json.loads((PROJECT / "videos" / video_id / "shots.json").read_text())


def frame_range(shot: dict, fps: Fraction, step: int = 1) -> list[int]:
    first = math.ceil(shot["start"] * float(fps) - 1e-6)
    stop = math.ceil(shot["end"] * float(fps) - 1e-6)
    first += (-first) % step
    return list(range(first, stop, step))


def key_indices(shot: dict, fps: Fraction) -> list[int]:
    indices = frame_range(shot, fps)
    if not indices:
        return []
    first, last = indices[0], indices[-1]
    times = np.arange(shot["start"], shot["end"], 0.5)
    keys = {first, last, round((first + last) / 2)}
    keys.update(min(last, max(first, round(t * float(fps)))) for t in times)
    return sorted(keys)


def verify_pts(path: Path, fps: Fraction) -> dict:
    """Check every ffprobe container presentation timestamp against the frame clock."""
    result = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    frames = json.loads(result.stdout)["frames"]
    error = max(abs(float(row["best_effort_timestamp_time"]) - i / float(fps))
                for i, row in enumerate(frames))
    if error > 0.0001:
        raise ValueError(f"Non-CFR/nonzero-origin video: PTS differs from index/fps by {error}s")
    return {"frameCount": len(frames), "maxTimestampErrorSeconds": error,
            "method": "ffprobe best_effort_timestamp_time, every frame"}


def decode_selected(path: Path, indices: list[int], fps: Fraction):
    """Seek to preceding keyframe, then emit requested decoded frames by actual PTS."""
    if not indices:
        return
    wanted = set(indices)
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"
        seek_seconds = max(0.0, indices[0] / float(fps) - 1.0)
        container.seek(int(seek_seconds / stream.time_base), stream=stream, backward=True)
        for frame in container.decode(stream):
            if frame.pts is None:
                raise ValueError("Decoded video frame has no PTS")
            t = float(frame.pts * stream.time_base)
            index = round(t * float(fps))
            if abs(t - index / float(fps)) > 0.0001:
                raise ValueError(f"Unexpected presentation timestamp at frame {index}: {t}")
            if index in wanted:
                yield index, frame.to_ndarray(format="bgr24")
                wanted.remove(index)
            if not wanted or index > indices[-1]:
                break
    if wanted:
        raise ValueError(f"Missing decoded source frames: {sorted(wanted)[:10]}")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)

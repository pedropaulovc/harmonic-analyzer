"""Publish complete current source shots without loading SAM 2 or initializing CUDA.

Run ``python -m harmonic_sync.readiness <videoId> [--watch]`` alongside an
already-running source process. Exclusions apply only to this invocation.
"""
from __future__ import annotations

import argparse
import json
import time
from fractions import Fraction

from .source import (FRAME_STRIDE, MODEL, complete, input_hash, log,
                     selected_shots, stage_hashes)
from .video import PROJECT, data_root, frame_range, key_indices, load_shots, sha256, write_json


_INDEX_HASH_FIELDS = ("maskInputHash", "edgeInputHash", "motionInputHash", "inputHash")


def publish_ready(census: dict, all_prompts: list[dict], checkpoint_hash: str,
                  exclude_shots=()) -> dict:
    """Atomically publish only shots whose every current view is fully complete.

    Existing timestamps are retained when the source SHA and ready shot hashes
    are unchanged. Rebuilding the snapshot removes dirty or excluded shots.
    """
    video_id = census["videoId"]
    root = data_root() / video_id
    fps = Fraction(*census["fps"])
    excluded = set(exclude_shots)
    selected = [shot for shot in selected_shots(census, None) if shot["id"] not in excluded]
    ready = {}
    for shot in selected:
        indices = frame_range(shot, fps, FRAME_STRIDE)
        keys = key_indices(shot, fps)
        views = {}
        for view in shot["views"]:
            prompts = [p for p in all_prompts
                       if p["shotId"] == shot["id"] and p["viewId"] == view["viewId"]]
            hashes = stage_hashes(census, shot, view, prompts, checkpoint_hash)
            directory = root / shot["id"] / view["viewId"]
            if not complete(directory, hashes, indices, keys):
                break
            expected = {"maskInputHash": hashes["mask"], "edgeInputHash": hashes["edges"],
                        "motionInputHash": hashes["motion"], "inputHash": input_hash(hashes)}
            try:
                index = json.loads((directory / "index.json").read_text())
                completed = {field: index[field] for field in _INDEX_HASH_FIELDS}
            except (OSError, KeyError, ValueError):
                break
            # The source process may have replaced the index since complete().
            if completed != expected:
                break
            views[view["viewId"]] = completed
        else:
            ready[shot["id"]] = {"views": views}

    destination = root / "ready.json"
    try:
        previous = json.loads(destination.read_text())
    except (OSError, ValueError):
        previous = None
    if (isinstance(previous, dict)
            and set(previous) == {"videoId", "sourceSha256", "updatedAt", "shots"}
            and previous["videoId"] == video_id
            and previous["sourceSha256"] == census["sourceSha256"]
            and previous["shots"] == ready):
        return previous
    snapshot = {"videoId": video_id, "sourceSha256": census["sourceSha256"],
                "updatedAt": time.time(), "shots": ready}
    write_json(destination, snapshot)
    log("source-ready", videoId=video_id, readyShots=len(ready), requiredShots=len(selected))
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish complete per-shot source stages")
    parser.add_argument("video_id")
    parser.add_argument("--watch", action="store_true", help="Poll current inputs and indexes every 3 seconds")
    parser.add_argument("--exclude-shot", action="extend", nargs="+", default=[], metavar="shotId",
                        help="Exclude shots for this invocation only")
    args = parser.parse_args()
    excluded = set(args.exclude_shot)
    checkpoint_hash = sha256(data_root() / "models" / f"{MODEL}.pt")
    while True:
        census = load_shots(args.video_id)
        all_prompts = json.loads((PROJECT / "videos" / args.video_id / "prompts.json").read_text())["prompts"]
        snapshot = publish_ready(census, all_prompts, checkpoint_hash, excluded)
        required = {shot["id"] for shot in selected_shots(census, None) if shot["id"] not in excluded}
        if not args.watch or required.issubset(snapshot["shots"]):
            print(json.dumps(snapshot, allow_nan=False))
            return
        time.sleep(3)


if __name__ == "__main__":
    main()

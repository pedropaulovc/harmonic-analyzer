# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow", "imagehash"]
# ///
"""Collapse near-duplicate video contact thumbs into clusters for curation.

The engineerguy videos are mostly static tripod shots, so 3 s-interval thumbs
contain long runs of near-identical frames. This walks each stills dir in
order, dhashes every thumb, and starts a new cluster whenever the Hamming
distance to the cluster's *representative* (first) frame exceeds the
threshold — comparing against the representative rather than the previous
frame so slow drift (e.g. the 360deg turntable bonus video) still splits.
The sharpest member (edge variance) represents each cluster.

Usage:
    uv run comparisons/tools/dedup_stills.py [--threshold 6]

Writes references/curation/dedup.json.
"""

import argparse
import json
from pathlib import Path

import imagehash
from PIL import Image, ImageFilter, ImageStat

REPO = Path(__file__).resolve().parents[2]
STILLS = REPO / "references" / "engineerguy-youtube" / "stills"
OUT = REPO / "references" / "curation" / "dedup.json"

VIDEOS = {
    "1": ("NAsM30MAHLg", "(1/4) Intro/History"),
    "2": ("8KmVDxkia_w", "(2/4) Synthesis"),
    "3": ("6dW6VYXp9HM", "(3/4) Analysis"),
    "4": ("jfH-NbsmvD4", "(4/4) Operation"),
    "5": ("4mBuyixt22U", "Bonus: Rocker arms"),
    "6": ("XPQwKRt4Y2k", "Bonus: 360 turntable"),
    "7": ("rMHw9GCAtE8", "Page-by-Page PDF guide"),
}

THUMB_INTERVAL_S = 3  # fps=1/3 extraction; tNNNN.jpg -> t = (N-1)*3 s

# Per-video Hamming-threshold overrides:
# 5: fixed tripod shots of *moving* levers — lever positions are not new
#    shots, so split far less eagerly.
# 6: 360deg turntable — every azimuth is distinct geometry evidence, split
#    eagerly to keep dense coverage.
THRESHOLD_OVERRIDES = {"5": 14, "6": 3}


def sharpness(img: Image.Image) -> float:
    return ImageStat.Stat(img.convert("L").filter(ImageFilter.FIND_EDGES)).var[0]


def frame_time_s(path: Path) -> int:
    return (int(path.stem[1:]) - 1) * THUMB_INTERVAL_S


def cluster_video(vdir: Path, threshold: int) -> list[dict]:
    frames = sorted(vdir.glob("t*.jpg"))
    clusters: list[dict] = []
    rep_hash = None
    for f in frames:
        img = Image.open(f)
        h = imagehash.dhash(img)
        sharp = sharpness(img)
        if rep_hash is None or (h - rep_hash) > threshold:
            rep_hash = h
            clusters.append({"rep": f.name, "rep_t_s": frame_time_s(f),
                             "rep_sharpness": round(sharp, 1),
                             "members": [], "span_s": [frame_time_s(f), frame_time_s(f)]})
        cl = clusters[-1]
        cl["members"].append(f.name)
        cl["span_s"][1] = frame_time_s(f)
        if sharp > cl["rep_sharpness"]:
            cl.update(rep=f.name, rep_t_s=frame_time_s(f), rep_sharpness=round(sharp, 1))
    return clusters


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=6, help="dhash Hamming split threshold")
    args = ap.parse_args()

    result = {"threshold": args.threshold, "thumb_interval_s": THUMB_INTERVAL_S, "videos": {}}
    total_in = total_out = 0
    for num, (yt_id, title) in VIDEOS.items():
        vdir = STILLS / num
        if not vdir.is_dir():
            print(f"video {num}: stills dir missing, skipping")
            continue
        clusters = cluster_video(vdir, THRESHOLD_OVERRIDES.get(num, args.threshold))
        n_frames = sum(len(c["members"]) for c in clusters)
        result["videos"][num] = {"yt_id": yt_id, "title": title,
                                 "n_frames": n_frames, "n_clusters": len(clusters),
                                 "clusters": clusters}
        total_in += n_frames
        total_out += len(clusters)
        print(f"video {num} ({title}): {n_frames} thumbs -> {len(clusters)} clusters")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1))
    print(f"total: {total_in} -> {total_out} ({OUT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

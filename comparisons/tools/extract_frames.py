# /// script
# requires-python = ">=3.11"
# ///
"""Extract full-resolution (1080p) frames for curated video keepers.

Reads references/curation/stills_catalog.json, and for every keep=true entry
whose source is a video, pulls the frame at its timestamp from the local MP4
into references/engineerguy-youtube/stills/full/v<N>_t<sssss>.png.

The 480px contact thumbs were sampled with ffmpeg fps=1/3, which emits the
first frame of each 3 s interval — so thumb tNNNN.jpg corresponds to
t=(N-1)*3 s and -ss <t> lands on the same content (verified in the pilot).

Usage:
    uv run comparisons/tools/extract_frames.py [--only v4-t0160,...] [--force]
"""

import argparse
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EG = REPO / "references" / "engineerguy-youtube"
FULL = EG / "stills" / "full"
CATALOG = REPO / "references" / "curation" / "stills_catalog.json"

YT_IDS = {
    "1": "NAsM30MAHLg", "2": "8KmVDxkia_w", "3": "6dW6VYXp9HM",
    "4": "jfH-NbsmvD4", "5": "4mBuyixt22U", "6": "XPQwKRt4Y2k",
    "7": "rMHw9GCAtE8",
}


def video_file(vnum: str) -> Path:
    yt_id = YT_IDS[vnum]
    for p in EG.glob("*.mp4"):
        if yt_id in p.name:
            return p
    raise FileNotFoundError(f"video {vnum} [{yt_id}] not found in {EG}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated catalog ids")
    ap.add_argument("--force", action="store_true", help="re-extract existing")
    args = ap.parse_args()
    only = set(args.only.split(",")) if args.only else None

    entries = json.loads(CATALOG.read_text(encoding="utf-8"))["entries"]
    FULL.mkdir(parents=True, exist_ok=True)
    n_done = n_skip = 0
    for e in entries:
        if not e.get("keep") or not e["source"].startswith("video"):
            continue
        if only and e["id"] not in only:
            continue
        vnum = e["source"].removeprefix("video")
        t = int(e["time_s"])
        out = FULL / f"v{vnum}_t{t:05d}.png"
        if out.exists() and not args.force:
            n_skip += 1
            continue
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", str(t), "-i", str(video_file(vnum)),
             "-frames:v", "1", str(out)],
            check=True,
        )
        print(f"  OK  {e['id']} -> {out.name}")
        n_done += 1
    print(f"extracted {n_done}, skipped {n_skip} existing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

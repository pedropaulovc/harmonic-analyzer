#!/usr/bin/env python3
"""Assemble Operation/Rocker from strict current-source observations only.

Only content/v39-source/<ID>.observations.json.gz supplies fresh source bytes.
No retained source seeds, old native calibration, camera donors or gap exposure
substitutions participate. Selected tracks are fully built and publication-validated
before any output is written; a validation failure leaves all selected outputs untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("operation_rocker_fresh", Path(__file__).with_name("fresh-source-tracks.py"))
fresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fresh)
common = fresh.common
WEB = common.WEB


class Generator(fresh.FreshGenerator):
    def _producer_path(self):
        return Path(__file__)


def operation(data=None):
    return Generator("jfH-NbsmvD4", data=data).build()


def rocker(data=None):
    return Generator("4mBuyixt22U", data=data).build()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", choices=("jfH-NbsmvD4", "4mBuyixt22U"),
                        help="Regenerate only this video; default validates the complete pair before publishing.")
    args = parser.parse_args()
    video_ids = (args.video,) if args.video else ("jfH-NbsmvD4", "4mBuyixt22U")
    tracks = [Generator(video_id).build() for video_id in video_ids]
    outputs = [(track, *common.prepare_track(track)) for track in tracks]
    for track, path, contents in outputs:
        path.write_text(contents)
        print(f"{path.relative_to(WEB)}: {len(track['shots'])} shots, {len(track['frames'])} samples, {path.stat().st_size} bytes; stages unmeasured")


if __name__ == "__main__":
    main()

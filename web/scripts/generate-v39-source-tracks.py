#!/usr/bin/env python3
"""Prepare and transactionally publish all six current compact source tracks.

Run after observation adoption and all three current family choice producers:
  python3 web/scripts/generate-v39-source-tracks.py

Only current v39 observations/choices are consumed. Each family keeps ownership
of its generation policy. No individual family writer is invoked: all six builds
and identity/stage checks finish before the current directory is replaced. A
failed build leaves the published corpus unchanged. Existing current observations
and choice/association packets are preserved. No source/GPU acceptance is claimed.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_script(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_tracks():
    analysis_synthesis = load_script("generate-analysis-synthesis-source-tracks.py", "v39_transaction_analysis_synthesis")
    operation_rocker = load_script("compact-operation-rocker.py", "v39_transaction_operation_rocker")
    intro = load_script("generate-intro-source-track.py", "v39_transaction_intro")
    spin = load_script("compact-spin.py", "v39_transaction_spin")
    tracks = [intro.build_track(),
              analysis_synthesis.Generator("8KmVDxkia_w").build(),
              analysis_synthesis.Generator("6dW6VYXp9HM").build(),
              operation_rocker.operation(), spin.build_track(), operation_rocker.rocker()]
    prepared = {track["source"]["videoId"]: track for track in tracks}
    if len(prepared) != len(tracks):
        raise ValueError("Current family builders produced duplicate video identities")
    return prepared


def main():
    adoption = load_script("adopt-v39-source-observations.py", "v39_transaction_publication")
    prepared = build_tracks()
    adoption.publish_tracks(prepared)
    print(json.dumps({"contentRoot": "web/content/v39", "transaction": "all-six-current-source-tracks",
        "videos": [{"videoId": video_id, "shots": len(track["shots"]), "frames": len(track["frames"]),
                    "views": sum(len(frame["views"]) for frame in track["frames"]),
                    "coverage": track["coverage"]["status"], "stages": track["stages"],
                    "sourceAcceptance": False, "GPUAcceptance": False}
                   for video_id, track in prepared.items()]}))


if __name__ == "__main__":
    main()

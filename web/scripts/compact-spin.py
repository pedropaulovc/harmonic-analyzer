#!/usr/bin/env python3
"""Assemble Spin's compact track from strict current-source observations.

Fresh turntable/montage views carry their own measured source identity, current
camera binding and honest chosen input provenance. Old camera rigs, numeric
seeds, phase maps and photographic donors are not current generation inputs.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("spin_fresh_tracks", HERE / "fresh-source-tracks.py")
fresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh)
common = fresh.common


class Generator(fresh.FreshGenerator):
    def _producer_path(self):
        return Path(__file__)


def generate(data=None):
    return Generator("XPQwKRt4Y2k", data=data).build()


def main():
    track = generate()
    path = common.write_track(track)
    print(json.dumps({"path": str(path.relative_to(common.WEB.parent)), "shots": len(track["shots"]),
                      "frames": len(track["frames"]), "views": sum(len(frame["views"]) for frame in track["frames"]),
                      "coverage": track["coverage"]["status"], "bytes": path.stat().st_size,
                      "stages": track["stages"]}))


if __name__ == "__main__":
    main()

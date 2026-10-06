#!/usr/bin/env python3
"""Assemble Operation/Rocker from strict current-source observations only.

No retained source seeds, old native calibration, camera donors or gap exposure
substitutions participate. Both tracks are fully built and publication-validated
before either output is written; a validation failure leaves both untouched.
"""
from __future__ import annotations

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
    tracks = [operation(), rocker()]
    outputs = [(track, *common.prepare_track(track)) for track in tracks]
    for track, path, contents in outputs:
        path.write_text(contents)
        print(f"{path.relative_to(WEB)}: {len(track['shots'])} shots, {len(track['frames'])} samples, {path.stat().st_size} bytes; stages unmeasured")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Assemble Intro's compact track from strict current-source observations.

Fresh views retain their exact source layouts, input/camera provenance and
current native measurement bindings. No embedded old calibration is executed.
Coverage is playback availability, never a GPU/source matching stage pass.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("intro_fresh_tracks", Path(__file__).with_name("fresh-source-tracks.py"))
fresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fresh)
common = fresh.common


class Generator(fresh.FreshGenerator):
    def _producer_path(self):
        return Path(__file__)


def generate(data=None):
    return Generator("NAsM30MAHLg", data=data).build()


def main():
    path = common.write_track(generate())
    print(path)


if __name__ == "__main__":
    main()

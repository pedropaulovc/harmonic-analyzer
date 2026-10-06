#!/usr/bin/env python3
"""Assemble current-source tracks without retained native/camera calibration.

Only strict content/v39-source observations qualify. The shared shot-aware
selector retains decoded exposures, seconds, cuts, layouts and measured motion
keys; views are copied intact rather than reconstructed from historical seeds.
Build and publication independently re-read current authority and live seals.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load(filename, name):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _load("compact-source-common.py", "fresh_track_common")
observations = _load("fresh-source-observations.py", "fresh_track_observations")
EXECUTED_INPUTS = (Path(__file__), *observations.EXECUTED_INPUTS)


class FreshGenerator:
    """Current-only assembly; caller data must match the fresh file to build."""

    def __init__(self, video_id, data=None):
        self.video_id = video_id
        self.data = copy.deepcopy(observations.load_observations(video_id) if data is None else data)
        self._validate()

    def _producer_path(self):
        return Path(__file__)

    def _validate(self):
        common.validate_current_generation_inputs(
            self.data, self._producer_path(), executed_inputs=EXECUTED_INPUTS)
        if self.data["source"]["videoId"] != self.video_id:
            raise ValueError("Current generation source video identity differs")

    def build(self):
        # Validate mutable caller/generator data and live approval/code afresh.
        # Selection annotates diagnostics/cut clocks: never mutate the bound
        # observation record or let a prior build become its new authority.
        self._validate()
        data = copy.deepcopy(self.data)
        track = common.build_track(data, lambda frame: copy.deepcopy(frame["views"]), [
            "Current source observations supply exact complete views, camera/native/source bindings and independent source pixels; no historical calibration or camera donor is read.",
            "Shared selection retains seconds, cuts, changes and measured camera/layout/landmark keys. Requested playback times never replace actual decoded exposure identities.",
            "Chosen physical inputs remain explicit assumptions; playback coverage is not GPU/source fidelity or stage acceptance.",
        ])
        track["source"] = copy.deepcopy(self.data["source"])
        track["nativeIdentity"] = copy.deepcopy(self.data["nativeIdentity"])
        common.bind_source_record(
            track, self.data, self._producer_path(), executed_inputs=EXECUTED_INPUTS)
        return track


def generate(video_id):
    return FreshGenerator(video_id).build()

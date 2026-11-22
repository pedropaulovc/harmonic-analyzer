"""The crankshaft's traveler and cross-hole program agree with its model.

The cross hole is drilled through the finished stub in the vise overhang,
stationed from the far end F; the drive-pin targets, the guard-banded
acceptance and the faced length land inside the drawing's bands, and the
plug pair gauges the drive-pin holes' band.
"""

from __future__ import annotations

import tomllib

import pytest

import _cam_programs
import _process_plans
import export_features

STEM = "dt_crankshaft"
IN = 25.4


def _plan() -> dict:
    return tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))


def _features() -> dict:
    return export_features.requirement_manifest(STEM)


def test_the_program_drills_the_station_through_the_stub_into_air():
    plan = _plan()
    p = plan["parameters"]
    features = _features()
    ctx = _cam_programs.load_recipe(STEM).context(
        features, plan, _process_plans.load_shop(), "crankshaft.step"
    )
    f = features["features"]
    station = f["cross_hole"]["station_nominal"]
    centres = [k["centres"] for _p, check, k in ctx["expect"] if check == "holes"]
    assert centres == [[[round(-station, 3), 0.0]]] * 2
    bottoms = [k["z_bottom"] for _p, check, k in ctx["expect"] if check == "holes"]
    assert min(bottoms) < -f["hub_shaft"]["nominal_dia"]
    # Its far limit still lies in the overhang, past the jaws' left face.
    assert f["cross_hole"]["station"][1] > p["jaw_left_from_f_mm"]


def test_the_faced_length_puts_the_rim_inside_its_band():
    p = _plan()["parameters"]
    f = _features()["features"]
    low, high = (v / IN for v in f["far_end"]["length"])
    dome = f["dome"]["height_nominal"] / IN
    assert p["dome_height_in"] == pytest.approx(dome, abs=1e-4)
    assert low <= p["overall_min_in"] - dome
    assert p["overall_max_in"] - dome <= high
    assert p["overall_min_mm"] == pytest.approx(p["overall_min_in"] * IN, abs=1e-3)
    assert p["overall_max_mm"] == pytest.approx(p["overall_max_in"] * IN, abs=1e-3)


def test_the_drive_pin_targets_and_acceptance_sit_inside_the_band():
    p = _plan()["parameters"]
    f = _features()["features"]
    for name in ("drive_pin_1", "drive_pin_2"):
        low, high = f[name]["offset"]
        assert low < p["pin_x_mm"] < high
        assert low < p["pin_accept_min_mm"] < p["pin_accept_max_mm"] < high
    assert p["pin_accept_min_mm"] == pytest.approx(
        p["pin_accept_min_in"] * IN, abs=1e-3
    )
    assert p["pin_accept_max_mm"] == pytest.approx(
        p["pin_accept_max_in"] * IN, abs=1e-3
    )


def test_the_plug_pair_is_the_drive_pin_band():
    shop = _process_plans.load_shop()
    f = _features()["features"]
    low, high = shop["gauges"]["plug-gauges-0930-0935"]["range_mm"]
    assert low == pytest.approx(f["drive_pin_1"]["dia"][0], abs=1e-4)
    assert high == pytest.approx(f["drive_pin_1"]["dia"][1], abs=1e-4)

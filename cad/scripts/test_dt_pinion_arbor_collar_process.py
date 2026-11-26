"""The pinion arbor collar's traveler and pin-hole program agree with its model.

The collar is turned and drilled on the end of its blank, its pin hole is
drilled there in the overhang past the vise jaws, and it is parted off last:
the turned length covers the collar and the blade, the hole lies in the
overhang, the drill ends under the O.D. in air, and the bench's pin gauges
and caliper reading sit inside the drawing's bands.
"""

from __future__ import annotations

import tomllib

import pytest

import _cam_programs
import _process_plans
import export_features

STEM = "dt_pinion_arbor_collar"
IN = 25.4


def _plan() -> dict:
    return tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))


def _features() -> dict:
    return export_features.requirement_manifest(STEM)


def test_the_turned_end_covers_the_collar_the_blade_and_the_drill():
    p = _plan()["parameters"]
    length = _features()["features"]["far_end"]["length"][1]
    turned = p["turn_length_in"] * IN
    assert length + p["blade_width_in"] * IN < turned <= p["drill_run_mm"]
    assert turned < p["stickout_mm"] and turned < p["part_off_stickout_mm"]


def test_the_pin_hole_program_drills_the_station_in_the_overhang_into_air():
    plan = _plan()
    features = _features()
    ctx = _cam_programs.load_recipe(STEM).context(
        features, plan, _process_plans.load_shop(), "collar.step"
    )
    hole = features["features"]["pin_hole"]
    od = features["features"]["outer"]["nominal_dia"]
    holes = [k for _p, check, k in ctx["expect"] if check == "holes"]
    assert [k["centres"] for k in holes] == [
        [[round(hole["station_nominal"], 3), 0.0]]
    ] * 2
    assert min(k["z_bottom"] for k in holes) < -od
    assert hole["station"][1] < plan["parameters"]["end_overhang_mm"]


def test_the_bench_gauges_read_inside_the_drawings_bands():
    plan = _plan()
    p = plan["parameters"]
    hole = _features()["features"]["pin_hole"]
    # Fit audit F15: the MHA-DT-VN-63 pin is the pin hole's gauge (it must
    # drive, not enter by hand); no gauge pin is bought for it.
    assert not {t["ref"] for t in plan["tools"]} & {"gauge-pin-0625", "pin-gauges"}
    low, _high = (v / IN for v in hole["dia"])
    assert p["shank_in"] == pytest.approx(low, abs=1e-6)
    station = [v / IN for v in hole["station"]]
    half = p["shank_in"] / 2
    assert p["station_far_side_min_in"] == pytest.approx(station[0] + half, abs=1e-4)
    assert p["station_far_side_max_in"] == pytest.approx(station[1] + half, abs=1e-4)

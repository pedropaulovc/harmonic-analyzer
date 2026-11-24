"""The pinion arbor's traveler and hole programs agree with its model.

Both cross holes are drilled while the blank is still 5/8 bar, each in its
own clamping's overhang past the vise jaws, stationed from the faced head end
(the head crown's apex): the stations land on the drawing's, the drills end
under the bar in air, the length and the matched journal fit sit inside the
drawing's bands, and the bench's pin gauges and caliper readings too.
"""

from __future__ import annotations

import math
import tomllib

import pytest

import _cam_programs
import _process_plans
import export_features

STEM = "dt_pinion_arbor"
IN = 25.4


def _plan() -> dict:
    return tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))


def _features() -> dict:
    return export_features.requirement_manifest(STEM)


def _apex_to_rear(features: dict) -> float:
    f = features["features"]
    crown = f["head_crown"]
    return f["head_rear"]["plane"]["value"] - (
        crown["center"][2] - crown["radius_nominal"]
    )


def test_the_programs_drill_each_station_in_its_overhang_into_air():
    plan = _plan()
    p = plan["parameters"]
    features = _features()
    ctx = _cam_programs.load_recipe(STEM).context(
        features, plan, _process_plans.load_shop(), "arbor.step"
    )
    offset = _apex_to_rear(features)
    f = features["features"]
    cross = round(offset - f["cross_hole"]["station_nominal"], 3)
    pin = round(offset + f["pin_hole"]["station_nominal"], 3)
    centres = {
        program.split("@")[0]: k["centres"]
        for program, check, k in ctx["expect"]
        if check == "holes"
    }
    assert centres == {"PA01_cross_hole": [[cross, 0.0]], "PA02_pin_hole": [[pin, 0.0]]}
    bottoms = [k["z_bottom"] for _p, check, k in ctx["expect"] if check == "holes"]
    assert min(bottoms) < -p["bar_dia_mm"]
    assert offset - f["cross_hole"]["station"][0] < p["cross_jaw_left_mm"]
    assert offset + f["pin_hole"]["station"][1] < p["jaw_left_x_mm"]


def test_the_lathe_stations_match_the_model():
    p = _plan()["parameters"]
    features = _features()
    f = features["features"]
    assert p["head_rear_z_in"] * IN == pytest.approx(_apex_to_rear(features), abs=0.01)
    assert p["neck_end_z_in"] - p["head_rear_z_in"] == pytest.approx(
        f["neck"]["length_nominal"] / IN, abs=1e-4
    )
    crown = f["head_crown"]["radius_nominal"] / IN
    half = f["head"]["nominal_dia"] / IN / 2
    assert p["crown_height_in"] == pytest.approx(
        crown - math.sqrt(crown**2 - half**2), abs=1e-4
    )
    back = f["back_crown"]
    rim = back["rim_station_nominal"] / IN
    r = back["radius_nominal"] / IN
    shaft = f["shaft"]["nominal_dia"] / IN / 2
    assert p["back_crown_height_in"] == pytest.approx(
        r - math.sqrt(r**2 - shaft**2), abs=1e-4
    )
    assert p["overall_in"] == pytest.approx(
        p["head_rear_z_in"] + rim + p["back_crown_height_in"], abs=1e-4
    )
    assert p["overall_min_mm"] == pytest.approx(p["overall_min_in"] * IN, abs=1e-3)
    assert p["overall_max_mm"] == pytest.approx(p["overall_max_in"] * IN, abs=1e-3)


def test_the_journal_aim_gives_the_drawings_clearance_on_the_strap():
    # Owner ruling 2026-11-24, fit audit question 12: the journals are turned
    # to the measured strap bores, aim = the smaller bore less the clearance
    # aim, never over journal_aim_in (the drum and collar pass the shaft).
    p = _plan()["parameters"]
    f = _features()["features"]
    # The journals print no band (REF Ø, made to fit): the aim's cap stays
    # inside the spans' band, which the drum and collar pass.
    low, high = (v / IN for v in f["shaft"]["dia"])
    assert low <= p["journal_aim_in"] <= high
    clearance = [v / IN for v in f["front_journal"]["diametral_clearance"]]
    assert clearance[0] < p["journal_clearance_aim_in"] < clearance[1]
    # The largest strap bore the capped aim still fits at the loosest clearance.
    assert p["strap_bore_max_fit_in"] == pytest.approx(
        p["journal_aim_in"] + clearance[1], abs=1e-4
    )


def test_the_bench_gauges_read_inside_the_drawings_bands():
    plan = _plan()
    p = plan["parameters"]
    f = _features()["features"]
    # Fit audit F15: the MHA-DT-VN-63 pin is the pin hole's gauge (it must
    # drive, not enter by hand); no gauge pin is bought for it.
    refs = {t["ref"] for t in plan["tools"]}
    assert not refs & {"gauge-pin-0625", "pin-gauges"}
    # The station reads over the 1/16 drill's shank.
    low, _high = (v / IN for v in f["pin_hole"]["dia"])
    assert p["pin_shank_in"] == pytest.approx(low, abs=1e-4)
    station = [v / IN for v in f["pin_hole"]["station"]]
    half = p["pin_shank_in"] / 2
    assert p["pin_far_side_min_in"] == pytest.approx(station[0] + half, abs=1e-4)
    assert p["pin_far_side_max_in"] == pytest.approx(station[1] + half, abs=1e-4)

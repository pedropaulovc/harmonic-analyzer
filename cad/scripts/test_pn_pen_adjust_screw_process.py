"""The pen adjust screw's traveler and eye program agree with its model.

The spigot is step-turned toward the chuck with the head in the jaws: the
stick-out is held to the shop's 3 x D rule on the least head the hold allows,
and the shoulder stays clear of the jaw fronts over the drawing's length and
head-length bands. The eye recipe drills the export's station in the head
end's overhang, clear of the jaws.
"""

from __future__ import annotations

import tomllib

import pytest

import _cam_programs
import _process_plans
import export_features

STEM = "pn_pen_adjust_screw"
IN = 25.4


def _plan() -> dict:
    return tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))


def _recipe():
    return _cam_programs.load_recipe(STEM)


def test_the_step_turned_hold_is_inside_the_shops_stickout_rule():
    p = _plan()["parameters"]
    limit = _process_plans.load_shop()["limits"]["stickout_ld_max"]
    # The load section is the least head the hold allows: a skimmed head's low
    # limit, under the bar as bought.
    assert p["head_load_dia_mm"] == pytest.approx(p["head_skim_min_in"] * IN)
    assert p["head_load_dia_mm"] <= p["stock_dia_in"] * IN
    assert p["spigot_stickout_mm"] <= limit * p["head_load_dia_mm"] + 1e-9


def test_the_shoulder_stays_clear_of_the_jaw_fronts():
    p = _plan()["parameters"]
    f = export_features.requirement_manifest(STEM)["features"]
    shoulder = f["shoulder"]["station"]
    assert shoulder[0] <= p["shoulder_aim_in"] * IN <= shoulder[1]
    for length in f["far_end"]["length"]:
        clearance = p["spigot_stickout_mm"] - (length - p["shoulder_aim_in"] * IN)
        assert 0.5 <= clearance <= 1.3


def test_the_head_is_the_bar_inside_the_drawings_band():
    p = _plan()["parameters"]
    outer = export_features.requirement_manifest(STEM)["features"]["outer"]
    assert p["as_supplied_outer"] == 1
    assert outer["dia"][0] <= p["head_skim_min_in"] * IN
    assert p["stock_dia_in"] * IN <= outer["dia"][1]


def test_the_eye_program_drills_the_station_in_the_overhang():
    plan = _plan()
    features = export_features.requirement_manifest(STEM)
    ctx = _recipe().context(features, plan, _process_plans.load_shop(), "screw.step")
    hole = features["features"]["cross_hole"]
    holes = [k for _p, check, k in ctx["expect"] if check == "holes"]
    assert [k["centres"] for k in holes] == [
        [[round(hole["station_nominal"], 3), 0.0]]
    ] * 2
    tip = min(k["z_bottom"] for k in holes)
    assert tip < -plan["parameters"]["stock_dia_in"] * IN
    assert hole["station"][1] < plan["parameters"]["head_overhang_mm"]

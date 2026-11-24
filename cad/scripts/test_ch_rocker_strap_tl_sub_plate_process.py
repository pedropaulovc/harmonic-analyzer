"""The sub-plate's traveler and CAM recipe agree with its model.

``cad/process/ch_rocker_strap_tl_sub_plate/plan.toml`` is a prechips
``fence_plate`` adapter plan: the adapter binds every printed size, band,
station, the drawing number and revision from the plate's feature export, so
the plan's [parameters] carry only process values (prechips is not an HA
dependency; the adapter's own tests hold its bindings). Here the plan's cut
stations and the holding values derived from the plate are held to the plate
spec, and the recipe's ``context`` runs on the drawing's requirement manifest
(the features the plate's export binds) with no FreeCAD: it refuses a hole
depth or cut width that disagrees with the model. The FreeCAD post is
``test_ch_rocker_strap_tl_sub_plate_cam_freecad.py``.
"""

from __future__ import annotations

import math
import re
import tomllib

import pytest

import _cam_programs
import _process_plans
import ch_rocker_strap_tl_sub_plate_spec as spec
import export_features

STEM = "ch_rocker_strap_tl_sub_plate"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
P = PLAN["parameters"]
# prechips stations run from the plate's left sawn end; the model's X0 is the
# stop face, .5 in in from it.
STATION_OFFSET = -spec.LEFT_END_X


def _cut(name: str) -> dict:
    for setup in PLAN["setups"]:
        for op in setup.get("operations", ()):
            for cut in op.get("milling_cuts", ()):
                if cut["name"] == name:
                    return cut
    raise KeyError(name)


@pytest.fixture(scope="module")
def ctx() -> dict:
    recipe = _cam_programs.load_recipe(STEM)
    features = export_features.requirement_manifest(STEM)
    return recipe.context(features, PLAN, SHOP, "plate.step")


def test_context_accepts_the_plans_hole_depths_and_widths(ctx) -> None:
    # context() refuses a plan hole depth or cut width that is not the
    # model's; the bounding box it hands build is the plate spec's.
    expected = [
        [spec.LEFT_END_X, spec.LEFT_END_X + spec.PLATE_LENGTH],
        [spec.BACK_EDGE_Y - spec.PLATE_WIDTH, spec.BACK_EDGE_Y],
        [spec.UNDERSIDE_Z, spec.FENCE_HEIGHT],
    ]
    for got, want in zip(ctx["bbox"], expected, strict=True):
        assert got == pytest.approx(want)


def test_plan_binds_the_plate_from_its_feature_export() -> None:
    assert PLAN["cad"] == {
        "file": f"../../out/features/{STEM}/features.toml",
        "adapter": "fence_plate",
        "part": "ch-rocker-strap-tl-sub-plate",
    }
    assert (PLAN["part"], PLAN["revision"]) == (
        "{{cad.drawing_number}}",
        "{{cad.revision}}",
    )
    # No drawn size or band is restated as a process value: the sheet prints
    # the adapter's, and every process binding names a [parameters] entry.
    text = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    assert not [k for k in P if k.startswith("plate_") and k != "plate_overhang_mm"]
    drawn = (
        "width", "thickness", "fence_height", "fence_width", "notch_depth",
        "pocket_back_wall", "pocket_length", "pocket_depth", "counterbore_dia",
        "counterbore_depth", "hub_x", "hub_y", "length",
    )
    assert not [k for k in P if re.fullmatch(rf"({'|'.join(drawn)})_(min_|max_)?mm", k)]
    assert set(re.findall(r"\{\{process\.(\w+)", text)) <= set(P)


def test_plan_holding_and_hole_depths_are_the_spec() -> None:
    assert P["clamp_hole_depth_mm"] == pytest.approx(spec.CLAMP_THREAD_LENGTH)
    assert P["hub_hole_depth_mm"] == pytest.approx(spec.HUB_THREAD_LENGTH)
    # SP02 cantilevers the plate from the vise, centred on the jaws.
    assert P["plate_overhang_mm"] == pytest.approx(
        (spec.PLATE_LENGTH - P["vise_jaw_width_mm"]) / 2
    )
    assert P["jaw_right_x_mm"] == pytest.approx(
        P["plate_overhang_mm"] + P["vise_jaw_width_mm"]
    )
    assert P["strap_right_x_mm"] == pytest.approx(
        spec.PLATE_LENGTH - P["strap_inset_mm"]
    )


def test_plan_stations_are_the_plates_features() -> None:
    # The pockets', hub's and notches' beam stations are the adapter's (from
    # the plate's left sawn end); the stations it does not bind are the spec's.
    for name in ("pocket plunges", "clamp spots", "clamp holes"):
        assert _cut(name)["stations_mm"] == "{{cad.pocket_beam_x_mm}}", name
    for name in ("counterbore", "hub tap spot", "hub hole"):
        assert _cut(name)["stations_mm"] == "{{cad.hub_beam_x_mm}}", name
    assert _cut("left notch")["traverse_mm"] == "{{cad.notch_left_beam_x_mm}}"
    assert _cut("right notch")["traverse_mm"] == "{{cad.notch_right_beam_x_mm}}"
    stations = [s + STATION_OFFSET for s in spec.CLAMP_STATIONS]
    inset = spec.POCKET_LENGTH / 2 - spec.CORNER_CUTTER_RADIUS
    lines = sorted(s + side * inset for s in stations for side in (-1, 1))
    for name in ("pocket centre lines", "pocket walls"):
        assert _cut(name)["stations_mm"] == pytest.approx(lines, abs=1e-3), name
    plunge = (
        spec.NOTCH_RIGHT_START
        + math.ceil(spec.CORNER_CUTTER_RADIUS * 1000) / 1000
        + STATION_OFFSET
    )
    assert _cut("notch plunge")["stations_mm"] == pytest.approx(plunge, abs=1e-3)


def test_plan_tools_cut_the_drawn_features() -> None:
    tools = SHOP["tools"]
    refs = {t["id"]: t["ref"] for t in PLAN["tools"]}
    assert tools[refs["drill-43"]]["diameter_mm"] == pytest.approx(
        spec.CLAMP_TAP_DRILL, abs=1e-3
    )
    assert tools[refs["drill-21"]]["diameter_mm"] == pytest.approx(
        spec.HUB_TAP_DRILL, abs=1e-3
    )
    assert (
        tools[refs["tap-10-32"]]["tap_drill_mm"]
        == tools[refs["drill-21"]]["diameter_mm"]
    )
    eighth = tools[refs["em-eighth"]]["diameter_mm"]
    # The 1/8 in end mill forms every inside corner: R.07 MAX on the sheet.
    assert eighth / 2 == spec.CORNER_CUTTER_RADIUS <= spec.CORNER_RADIUS
    assert (
        eighth <= spec.NOTCH_DEPTH and eighth <= spec.POCKET_DEPTH + spec.FENCE_HEIGHT
    )
    assert tools[refs["em-half"]]["diameter_mm"] == spec.HUB_CBORE_DIA
    setting = SHOP["settings"]["endmill-carbide-3fl-1-8-6061"]
    assert setting["tool"] == refs["em-eighth"] and 100 <= setting["rpm"] <= 2800


def test_programs_cut_through_and_stop_for_each_tap(ctx) -> None:
    stops = {
        program: kw["at"] for program, check, kw in ctx["expect"] if check == "tap_stop"
    }
    # One file per hole to tap, each ending Idle over its hole; SP02 no M0.
    assert list(stops) == [
        *(f"SP03_tap_clamp_{k}" for k in range(1, len(spec.CLAMP_STATIONS) + 1)),
        "SP03_tap_hub",
    ]
    assert [xy[0] for xy in stops.values()] == pytest.approx(
        [*spec.CLAMP_STATIONS, spec.HUB_X]
    )
    assert [
        kw["count"]
        for program, check, kw in ctx["expect"]
        if program == "SP02_top" and check == "pauses"
    ] == [0]
    depth = {
        program: kw["z_min"]
        for program, check, kw in ctx["expect"]
        if check == "depth" and "@" not in program
    }
    assert depth["SP01_split_edges"] < spec.UNDERSIDE_Z
    assert depth["SP02_top"] == pytest.approx(
        spec.UNDERSIDE_Z + P["drill_tip_below_mm"], abs=1e-3
    )
    assert ctx["numbers"] == {
        t: n for n, t in enumerate(_cam_programs.load_recipe(STEM).CAM_TOOLS, 1)
    }

"""The sub-plate's traveler and CAM recipe agree with its model.

``cad/process/ch_rocker_strap_tl_sub_plate/plan.toml`` is a literal plan (no
prechips adapter reads the plate's feature export): its sizes, printed bands
and milling-cut stations are [parameters] and numbers, held here to the
drawing's requirement manifest and the plate spec. The recipe's ``context``
runs on the manifest (the features the plate's export binds) with no FreeCAD:
it refuses any plan size, band or cut width that disagrees with the model.
The FreeCAD post is ``test_ch_rocker_strap_tl_sub_plate_cam_freecad.py``.
"""

from __future__ import annotations

import math
import tomllib

import pytest

import _cam_programs
import _process_plans
import ch_rocker_strap_tl_sub_plate_spec as spec
import export_features

STEM = "ch_rocker_strap_tl_sub_plate"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = tomllib.loads(_process_plans.SHOP_PATH.read_text(encoding="utf-8"))
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


def test_context_accepts_the_plans_sizes_and_bands(ctx) -> None:
    # context() refuses a plan size, band, hole depth or cut width that is not
    # the model's; the bounding box it hands build is the plate spec's.
    expected = [
        [spec.LEFT_END_X, spec.LEFT_END_X + spec.PLATE_LENGTH],
        [spec.BACK_EDGE_Y - spec.PLATE_WIDTH, spec.BACK_EDGE_Y],
        [spec.UNDERSIDE_Z, spec.FENCE_HEIGHT],
    ]
    for got, want in zip(ctx["bbox"], expected, strict=True):
        assert got == pytest.approx(want)


def test_plan_plate_is_the_spec() -> None:
    assert P["plate_length_mm"] == spec.PLATE_LENGTH
    assert P["plate_width_mm"] == spec.PLATE_WIDTH
    assert P["plate_thickness_mm"] == spec.PLATE_THICKNESS
    assert P["plate_top_height_mm"] == pytest.approx(-spec.UNDERSIDE_Z)
    assert P["fence_height_mm"] == spec.FENCE_HEIGHT
    assert (P["hub_x_mm"], -P["hub_y_mm"]) == (spec.HUB_X, spec.HUB_Y)
    assert P["clamp_hole_depth_mm"] == pytest.approx(spec.CLAMP_THREAD_LENGTH)
    assert P["hub_hole_depth_mm"] == pytest.approx(spec.HUB_THREAD_LENGTH)
    # SP02 cantilevers the plate from the vise, centred on the jaws.
    assert P["plate_overhang_mm"] == pytest.approx(
        (P["plate_length_mm"] - P["vise_jaw_width_mm"]) / 2
    )
    assert P["jaw_right_x_mm"] == pytest.approx(
        P["plate_overhang_mm"] + P["vise_jaw_width_mm"]
    )
    assert P["strap_right_x_mm"] == pytest.approx(
        P["plate_length_mm"] - P["strap_inset_mm"]
    )


def test_plan_stations_are_the_plates_features() -> None:
    stations = [s + STATION_OFFSET for s in spec.CLAMP_STATIONS]
    for name in ("pocket plunges", "clamp spots", "clamp holes"):
        assert _cut(name)["stations_mm"] == pytest.approx(stations), name
    inset = spec.POCKET_LENGTH / 2 - spec.CORNER_CUTTER_RADIUS
    lines = sorted(s + side * inset for s in stations for side in (-1, 1))
    for name in ("pocket centre lines", "pocket walls"):
        assert _cut(name)["stations_mm"] == pytest.approx(lines, abs=1e-3), name
    for name in ("counterbore", "hub tap spot", "hub hole"):
        assert _cut(name)["stations_mm"] == pytest.approx(
            spec.HUB_X + STATION_OFFSET
        ), name
    assert _cut("left notch")["traverse_mm"] == pytest.approx(
        [STATION_OFFSET, spec.NOTCH_LEFT_END + STATION_OFFSET]
    )
    assert _cut("right notch")["traverse_mm"][0] == pytest.approx(
        spec.NOTCH_RIGHT_START + STATION_OFFSET
    )
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
    assert tools[refs["drill-7"]]["diameter_mm"] == pytest.approx(
        spec.HUB_TAP_DRILL, abs=1e-3
    )
    assert (
        tools[refs["tap-1-4-20"]]["tap_drill_mm"]
        == tools[refs["drill-7"]]["diameter_mm"]
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

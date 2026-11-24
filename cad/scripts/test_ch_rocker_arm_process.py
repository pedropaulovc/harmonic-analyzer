"""The rocker arm's traveler and CAM recipe agree with its model, its members
and its plan.

``cad/process/ch_rocker_arm/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the arm's export binds) with no FreeCAD and no SolidWorks, and refuses any
plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
them, and seeded faults show each check catches what it guards. The plan's
members are the hub and strap travelers' products: the hub's land window and
supply length are theirs, and the bond moved here from the hub traveler.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import ch_rocker_arm_spec
import ch_rocker_hub_fit
import ch_rocker_hub_spec
import export_features

STEM = "ch_rocker_arm"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
HUB_PLAN = tomllib.loads(
    _process_plans.plan_path("ch_rocker_hub").read_text(encoding="utf-8")
)
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
IN = 25.4


def _context(plan: dict = PLAN, shop: dict = SHOP) -> dict:
    return RECIPE.context(FEATURES, plan, shop, "cam.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min."""
    sections = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, groups in RECIPE.PROGRAMS:
        text = [
            f"({name})",
            f"({ctx['comment']})",
            "(Begin preamble)",
            "G17 G90",
            "G21",
            "G54",
        ]
        for (key,) in groups:
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
                *(
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines_of[key]
                ),
            ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_the_plan_is_an_enrolled_joined_hub_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    assert STEM in _cam_programs.CAM_STEMS
    assert PLAN["cad"]["adapter"] == "joined_hub"
    assert FEATURES["construction"] == "built_up_permitted"


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {"em-half": 1, "drill-f": 2, "spot": 3, "drill-47": 4}
    assert RECIPE.LOAD_FIRST_TOOL == ("RA01_first_end", "RA02_second_end_holes")


def test_the_members_are_the_hub_and_strap_travelers_products() -> None:
    p = PLAN["parameters"]
    # LAND_WINDOW is the land's deviation from the strap hole's reamer.
    hole = SHOP["tools"]["reamer-4000"]["diameter_mm"]
    land = (p["hub_land_min_in"] * IN - hole, p["hub_land_max_in"] * IN - hole)
    assert land == pytest.approx(ch_rocker_hub_fit.LAND_WINDOW, abs=1e-6)
    assert (p["hub_land_min_in"], p["hub_land_max_in"]) == (
        HUB_PLAN["parameters"]["land_min_in"],
        HUB_PLAN["parameters"]["land_max_in"],
    )
    assert p["hub_supply_length_min_in"] * IN == pytest.approx(
        ch_rocker_hub_spec.SUPPLY_LENGTH_MIN
    )


def test_the_first_arm_checks_hold_the_drawings_position_zones() -> None:
    p = PLAN["parameters"]
    assert p["hub_pilot_bore_in"] * IN == pytest.approx(
        SHOP["tools"]["drill-d"]["diameter_mm"], abs=0.01
    )
    zones = ch_rocker_arm_spec.GEOMETRIC_TOLERANCES_IN
    # The bore's centre within the limit each way stays inside half the hub
    # OD's position zone with room for the edge finder's reading.
    radial = p["bore_centre_max_in"] * 2**0.5
    assert radial < float(zones["hub OD position to bore"]) / 2 - 0.0005
    # The strap's mid-plane from end G: the hub's half within its zone.
    half = ch_rocker_arm_spec.HUB_LENGTH / 2 / IN
    zone = float(zones["strap position to hub"])
    assert p["strap_mid_min_in"] == pytest.approx(half - zone / 2, abs=5e-4)
    assert p["strap_mid_max_in"] == pytest.approx(half + zone / 2, abs=5e-4)


def test_the_bond_moved_from_the_hub_traveler() -> None:
    hub_titles = [setup["title"] for setup in HUB_PLAN["setups"]]
    assert not any("Bond" in title for title in hub_titles)
    assert "gauge-blocks" not in {t["id"] for t in HUB_PLAN["tools"]}
    hub_diagrams = _process_plans.plan_path("ch_rocker_hub").parent / "diagrams"
    assert not (hub_diagrams / "bond.svg").exists()
    first = PLAN["setups"][0]
    assert first["title"].startswith("Bond each hub into its own strap")
    assert first["diagram"]["file"] == "diagrams/bond.svg"
    text = " ".join(op.get("instruction", "") for op in first["operations"])
    assert "LOCTITE 638" in text and "24 h" in text


def test_every_spindle_speed_rests_on_a_stop_or_the_measured_face_setting() -> None:
    machines = (
        _process_plans.PROCESS_ROOT.parent
        / "config"
        / "shop-equipment"
        / "machines.toml"
    )
    step = tomllib.loads(machines.read_text(encoding="utf-8"))["machines"]["pm-30mv"][
        "spindle_speed_step_rpm"
    ]
    for setup in PLAN["setups"]:
        for op in setup.get("operations", ()):
            if "rpm" in op:
                stops = op["rpm"] / step
                assert stops == pytest.approx(round(stops), abs=0.01), op["rpm"]
            if op.get("settings"):
                assert op["settings"] == "em-half-carbide-1018-3439-face"


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {"RA01_first_end", "RA02_second_end_holes"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("face_pass_y_mm", 5.5, "face_pass_y_mm"),
        ("face_pass_x_mm", 10.0, "face_pass_x_mm"),
        ("face_woc_mm", 7.0, "face_woc_mm"),
        ("strap_tip_x_mm", 140.0, "strap_tip_x_mm"),
        ("strap_depth_mm", 15.0, "strap_depth_mm"),
        ("block_inner_x_mm", 5.0, "clear the gap blocks"),
        ("block_outer_x_mm", 80.0, "3 in long"),
        ("tip_block_x_mm", 133.5, "reaches the tip block"),
        ("tip_block_x_mm", 130.0, "between the right block"),
        ("traverse_z_mm", 30.0, "above the clamps"),
        ("bore_tip_z_mm", -6.0, "bore_tip_z_mm"),
        ("bore_drill_past_mm", 2.0, "bore_tip_z_mm"),
        ("rod_tip_z_mm", -3.0, "rod_tip_z_mm"),
        ("spot_dia_mm", 2.1, "under the #47"),
        ("hub_land_max_in", 0.4110, "hub band"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_cut_diameter_off_its_shop_tool_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    for setup in plan["setups"]:
        for op in setup.get("operations", ()):
            for milling in op.get("milling_cuts", ()):
                if milling["name"] == "rod drill":
                    milling["cutter_dia_mm"] = 2.1
    with pytest.raises(ValueError, match="not its tool's"):
        _context(plan)


def test_a_beam_span_off_the_hold_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    plan["setups"][2]["beam"]["supports_mm"] = [-12.7, 12.7]
    with pytest.raises(ValueError, match="beam supports"):
        _context(plan)


@pytest.mark.parametrize(
    ("ref", "dia", "detail"),
    [
        ("jig-drill-f", 6.35, "outside the bore band"),
        ("drill-47", 2.2, "outside the hole band"),
    ],
)
def test_a_drill_off_its_band_is_refused(ref, dia, detail) -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"][ref] = {**shop["tools"][ref], "diameter_mm": dia}
    with pytest.raises(ValueError, match=detail):
        _context(shop=shop)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` replaced."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    assert old in lines, (key, old)
    lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # The end faced below its height (into the strap's share of the length).
        ("face_first", "G1 Z2.286 F{feed}", "G1 Z2.000 F{feed}", "depth"),
        # Both passes on one side: the far half of the end left standing.
        ("face_second", "G1 Y-5.080", "G1 Y5.080", "face"),
        # The F drill stopped inside the hub.
        ("bore", "G1 Z-7.236 F{feed}", "G1 Z-4.000 F{feed}", "holes"),
        # The #47 off its BASIC place.
        ("rod_drill", "G0 X133.067 Y8.456", "G0 X130.000 Y8.456", "holes"),
        # The #47 moved onto the tip block.
        ("rod_drill", "G0 X133.067 Y8.456", "G0 X137.000 Y8.456", "keep_out"),
        # A traverse to the #47 under the clamps' tops.
        ("rod_spot", "G0 Z45.000", "G0 Z20.000", "keep_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

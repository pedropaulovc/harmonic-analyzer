"""The crank arm's CAM recipe agrees with its model and plan.

``cad/process/dt_crank_arm/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest with no FreeCAD
and no SolidWorks, and refuses any plan number that disagrees with the
model, the shop or the holding. The posted programs are stood in for by the
recipe's own section lines under the grbl post's tool-change block, so every
check the recipe declares runs on them, and seeded faults show each check
catches what it guards.
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "dt_crank_arm"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "cam.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and the lines of
    every operation in it, the feeds in mm/min; a tap stop's lines after its
    M6, ending with its M30."""
    jobs = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    for name, groups in RECIPE.PROGRAMS:
        text = [f"({name})", f"({ctx['comment']})", "G17 G90", "G21", "G54"]
        manual_only = True
        for group in groups:
            keys = group if isinstance(group, tuple) else (group,)
            if keys[0] in ctx["manual"]:
                manual = ctx["manual"][keys[0]]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
            manual_only = False
            job = jobs[keys[0]]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for op in job["ops"]:
                text += [line.format(feed=f"{job['feed']:.3f}") for line in op[2]]
        if not manual_only:
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em": 1,
        "spot": 2,
        "drill-50": 3,
        "drill-43": 4,
        "sink": 5,
        "tap-guide": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    for key in ("anchor_tap_stop", "pivot_tap_stop"):
        stop = ctx["manual"][key]
        assert stop["tool"] == 6
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("seat_path_radius_mm", 5.0, "seat_path_radius_mm"),
        ("round_path_radius_mm", 17.0, "round_path_radius_mm"),
        ("through_bottom_mm", -8.0, "through_bottom_mm"),
        ("anchor_drill_tip_mm", -8.5, "anchor_drill_tip_mm"),
        ("pivot_drill_tip_mm", -8.5, "pivot_drill_tip_mm"),
        ("jaw_top_mm", 10.0, "jaw_top_mm"),
        ("parallel_height_mm", 12.7, "jaw_top_mm"),
        ("em_feed_per_min_mm", 600.0, "em_feed_per_min_mm"),
        ("sink_tip_mm", -1.0, "sink_tip_mm"),
        ("sink_dia_mm", 3.0, "countersink"),
        ("hub_spot_dia_mm", 1.9, "under its drill"),
        # The #50 one jaw-width short of the jaws at the least overhang.
        ("overhang_min_mm", 38.0, "reach the jaws"),
        ("handle_jaw_end_max_mm", 82.0, "reaches the jaws"),
        ("handle_waste_max_mm", 6.0, "handle_waste_max_mm"),
        ("drill_projection_min_mm", 19.05, "nose reaches the jaw tops"),
        ("sink_projection_min_mm", 12.7, "nose reaches the jaw tops"),
        ("tap_stack_max_mm", 300.0, "tap_stack_max_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("cut", "dia"), [("seat", 9.0), ("anchor drill", 1.85), ("pivot drill", 2.3)]
)
def test_a_cut_diameter_off_its_shop_tool_is_refused(cut, dia) -> None:
    plan = copy.deepcopy(PLAN)
    for setup in plan["setups"]:
        for op in setup.get("operations", ()):
            for milling in op.get("milling_cuts", ()):
                if milling["name"] == cut:
                    milling["cutter_dia_mm"] = dia
    with pytest.raises(ValueError, match="not its tool's"):
        _context(plan)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line starting ``old`` of operation ``key`` (or
    of a tap stop) replaced by ``new``."""
    seeded = copy.deepcopy(ctx)
    if key in seeded["manual"]:
        lines = seeded["manual"][key]["gcode"]
    else:
        lines = next(
            op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key
        )
    index = next(i for i, line in enumerate(lines) if line.startswith(old))
    lines[index] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # The anchor drilled short of through.
        ("anchor_drill", "G1 Z-8.972", "G1 Z-7.000 F{feed}", "holes"),
        # The boss round climb-cut (G2) instead of conventional.
        ("boss_round", "G3 X16.510", "G2 X16.510 Y-30.162 I0.000 J-17.462", "bounds"),
        # The handle round's last level short of through.
        ("handle_round", "G1 Z-8.191", "G1 Z-7.000 F{feed}", "bounds"),
        # A drill brought over the fixed jaw below its top.
        ("pivot_drill", "G0 X-87.630", "G0 X-70.000 Y3.000", "keep_out"),
        # A tap stop that holds (M0) instead of ending Idle.
        ("pivot_tap_stop", "M30", "M0", "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

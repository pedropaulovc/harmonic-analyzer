"""The arbor pedestal's CAM recipe agrees with its model and plan.

``cad/process/dt_arbor_pedestal/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``drilled_block`` adapter binds) with no FreeCAD and no SolidWorks, and
refuses any plan number that disagrees with the model, the shop or the
holding. The posted programs are stood in for by the recipe's own section
lines under the grbl post's tool-change block, so every check the recipe
declares runs on them, and seeded faults show each check catches what it
guards.
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

STEM = "dt_arbor_pedestal"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "pedestal.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section (a FreeCAD Job: a group, or a program's flat keys) an M6 block
    (M5, the operator's %msg, M6, M3) and its operations' lines, the feeds in
    mm/min; a tap stop's lines after its M6, ending with its M30."""
    jobs = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
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
        flat = not any(isinstance(group, tuple) for group in groups)
        sections = [groups] if flat else groups
        for keys in sections:
            first = keys[0]
            if first in ctx["manual"]:
                manual = ctx["manual"][first]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
            job = jobs[first]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for key in keys:
                text += [
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines_of[key]
                ]
        if not any(keys[0] in ctx["manual"] for keys in sections):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-15": 3,
        "drill-v": 4,
        "drill-43": 5,
        "tap-guide": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # The tap stop stands over the hole PA05 drilled, in the same frame.
    apex_holes = next(
        kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if program == "PA05_top_apex@2" and check == "holes"
    )
    stop = ctx["manual"]["tap_apex"]
    assert apex_holes == [stop["at"]]
    assert stop["tool"] == 6
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("depth_top_mm", 29.0, "depth_top_mm"),
        ("upright_top_max_mm", 57.0, "upright_top_max_mm"),
        ("step_floor_mm", 12.0, "step_floor_mm"),
        ("step_station_mm", 5.08, "step_station_mm"),
        ("step_level_mm", 3.0, "does not divide"),
        ("outline_rough_level_mm", 4.0, "does not divide"),
        ("hold_tip_depth_mm", 6.0, "hold_tip_depth_mm"),
        ("bore_tip_height_mm", -2.0, "bore_tip_height_mm"),
        ("apex_tip_height_mm", 47.0, "apex_tip_height_mm"),
        ("bore_spot_dia_mm", 1.9, "between the pilot"),
        ("hold_spot_dia_mm", 4.7, "not under its drill"),
        ("tap_reach_max_mm", 15.5, "tap_reach_max_mm"),
        ("step_grip_mm", 11.0, "step_grip_mm"),
        ("far_face_stock_mm", 0.5, "depth_top_mm"),
        ("vise_foot_inset_mm", -60.0, "vise_foot_inset_mm"),
        ("vise_step_inset_mm", -50.1269, "vise_step_inset_mm"),
        ("tap_stack_max_mm", 249.428, "tap_stack_max_mm"),
        ("strap_net_width_mm", 14.3, "strap_net_width_mm"),
        ("step_prove_raise_mm", 25.4, "step_prove_raise_mm"),
        ("depth_top_min_mm", 29.21, "depth_top_min_mm"),
        ("step_floor_max_mm", 11.938, "step_floor_max_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_step_floor_below_the_jaw_tops_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    params = plan["parameters"]
    params["step_riser_height_mm"] = 31.75
    params["step_grip_mm"] = params["vise_jaw_height_mm"] - 31.75
    with pytest.raises(ValueError, match="not above the jaw tops"):
        _context(plan)


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` (or of a tap stop)
    that ``pick`` accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The width's first face pass moved onto the blank's middle: a slot.
        (
            "width",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-15.000",
            "face",
        ),
        # A step pass run back along +Y: climb with M3.
        (
            "step",
            lambda line: line.startswith("G1 Y"),
            lambda line: "G1 Y60.000 F{feed}",
            "cut",
        ),
        # The step's last pass moved into the foot.
        (
            "step",
            lambda line: line.startswith("G0 X-11.430 "),
            lambda line: "G0 X-9.000 " + line.split(" ", 2)[2],
            "passes",
        ),
        # The bore drilled short of the strap's far side.
        (
            "bore_drill",
            lambda line: line == "G1 Z-3.877 F{feed}",
            lambda line: "G1 Z2.000 F{feed}",
            "holes",
        ),
        # The crown cut conventional (G3).
        (
            "outline",
            lambda line: line.startswith("G2 "),
            lambda line: "G3" + line[2:],
            "outline",
        ),
        # The finish pass's flank stepped .010 into the part.
        (
            "outline",
            lambda line: line.startswith("G1 X") and " Y" in line,
            lambda line: (
                f"G1 X{float(line.split()[1][1:]) - 0.254:.3f} " + line.split(" ", 2)[2]
            ),
            "outline",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        (
            "tap_apex",
            lambda line: line == "M30",
            lambda line: "M0",
            "tap_stop",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

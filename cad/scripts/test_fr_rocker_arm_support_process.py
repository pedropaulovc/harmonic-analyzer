"""The rocker arm support's traveler and CAM recipe agree with its model.

``cad/process/fr_rocker_arm_support/plan.toml`` is a prechips
``drilled_block`` adapter plan; ``cam.py`` writes every path itself. Its
``context`` runs here on the drawing's requirement manifest (the features the
adapter binds) with no FreeCAD and no SolidWorks, and refuses any plan number
that disagrees with the model, the shop or the holding. The posted programs
are stood in for by the recipe's own section lines under the grbl post's
tool-change block, so every check the recipe declares runs on them, and
seeded faults show the checks catch what they guard.
"""

from __future__ import annotations

import copy
import re
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "fr_rocker_arm_support"
SHOP = _process_plans.load_shop()
PLAN_TEXT = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
PLAN = tomllib.loads(PLAN_TEXT)
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "support.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section (a FreeCAD Job) an M6 block (M5, the operator's %msg, M6, M3) and
    its operations' lines, the feeds in mm/min; a section of the running tool
    at its speed carries on with no tool change."""
    jobs = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, sections in RECIPE.PROGRAMS:
        text = [f"({name})", f"({ctx['comment']})", "(Begin preamble)", "G17 G90", "G21", "G54"]
        previous = None
        for keys in sections:
            job = jobs[keys[0]]
            number = ctx["numbers"][job["tool"]]
            if previous != (number, job["rpm"]):
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                    f"M6 T{number}",
                    f"M3 S{job['rpm']:g}",
                ]
            previous = (number, job["rpm"])
            for key in keys:
                text += [
                    line.format(feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}")
                    for line in lines_of[key]
                ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path, program: str | None = None) -> list:
    checks = [
        check for check in RECIPE.expectations(ctx)
        if program is None or check[0].split("@")[0] == program
    ]
    return cam_nc.verify(checks, out)


def test_plan_binds_the_support_from_its_feature_export() -> None:
    assert PLAN["cad"] == {
        "file": f"../../out/features/{STEM}/features.toml",
        "adapter": "drilled_block",
        "part": "fr-rocker-arm-support",
    }
    assert set(re.findall(r"\{\{process\.(\w+)", PLAN_TEXT)) <= set(PLAN["parameters"])


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {"em-3-8": 1, "spot": 2, "drill-13-32": 3, "drill-5-16": 4, "chamfer": 5}
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    plan_tools = {t["id"] for t in PLAN["tools"]}
    assert set(RECIPE.CAM_TOOLS) <= plan_tools


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("stock_top_mm", 38.0),
        ("em_plunge_feed_mm", 300.0),
        ("rough_level_mm", 3.0),
        ("rough_station_mm", 3.7),
        ("outline_depth_mm", 34.0),
        ("pocket_wall_depth_mm", 24.0),
        ("slant_station_mm", 2.6),
        ("chamfer_foot_wall_mm", 1.5),
        ("chamfer_top_wall_mm", 1.5),
        ("stud_tip_mm", -40.0),
        ("cavity_depth_mm", 13.0),
        ("foot_tip_mm", -9.0),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=f"process.{key}"):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick``
    accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("program", "key", "pick", "change", "check"),
    [
        # The pocket wall loop cut conventional (G2 inside the pocket).
        ("FR03_a_walls", "a_walls", lambda line: line.startswith("G3 "), lambda line: "G2" + line[2:], "outline"),
        # A foot hole drilled short of the pocket.
        ("FR09_foot", "foot_drill", lambda line: line.startswith("G1 Z-9.735"), lambda line: "G1 Z-5.000 F{feed}", "holes"),
        # A stud hole's first peck rapided into the slab.
        ("FR01_studs", "stud_drill", lambda line: line.startswith("G1 Z31.877"), lambda line: "G0 Z31.877", "rapid"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(ctx, tmp_path, program, key, pick, change, check) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path, program)}

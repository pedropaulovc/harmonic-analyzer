"""The stop plate's CAM recipe agrees with its model and plan.

``cad/process/ms_stop_plate/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
plate's export binds) with no FreeCAD and no SolidWorks, and refuses any plan
number that disagrees with the model, the shop, the block under it or the
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
import ms_stop_spec

STEM = "ms_stop_plate"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "plate.step")


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
        for key in (
            group[0] if isinstance(group, tuple) else group for group in groups
        ):
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


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {"spot": 1, "drill-49": 2, "drill-41": 3}
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    assert ctx["manual"] == {}


def test_the_plan_reads_the_block_it_drills_into() -> None:
    p = PLAN["parameters"]
    assert p["block_depth_mm"] == ms_stop_spec.BLOCK_DEPTH
    assert p["block_window_low_mm"] == pytest.approx(ms_stop_spec.WINDOW_Y_MIN)
    assert p["block_window_high_mm"] == pytest.approx(ms_stop_spec.WINDOW_Y_MAX)
    assert p["block_window_depth_mm"] == ms_stop_spec.WINDOW_WIDTH
    hole = FEATURES["features"]["clearance_hole_1"]
    assert hole["pair_pilot_dia"] == ms_stop_spec.PLATE_TAP_DRILL_DIA
    assert (
        hole["pair_pilot_depth_in_mate_nominal"] == ms_stop_spec.PLATE_TAP_DRILL_DEPTH
    )


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("pilot_tip_height_mm", -8.6, "pilot_tip_height_mm"),
        ("open_tip_height_mm", -1.5, "open_tip_height_mm"),
        ("spot_dia_mm", 1.9, "not under the #49"),
        ("stack_height_mm", 14.0, "stack_height_mm"),
        ("parallel_height_mm", 38.1, "stack_below_jaw_top_mm"),
        ("vise_inset_mm", -60.0, "vise_inset_mm"),
        ("block_window_low_mm", 9.5, "not over its window"),
        ("hole_rpm", 2400, "not at process.hole_rpm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


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
        # The #49 pilot stopped short of the block's tap drill depth.
        ("pair_pilot", "G1 Z-9.193 F{feed}", "G1 Z-8.500 F{feed}", "holes"),
        # The #41 stopped inside the plate: the hole is not open through.
        ("plate_open", "G1 Z-2.276 F{feed}", "G1 Z-0.800 F{feed}", "holes"),
        # A rapid down into the plate instead of to the R plane.
        ("pair_spot", "G0 Z1.000", "G0 Z-0.500", "rapid"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

"""The crank pin's CAM recipe agrees with its model and plan.

``cad/process/dt_crank_pin/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the pin's export binds) with no FreeCAD and no SolidWorks, and refuses any
plan number that disagrees with the model, the shop or the holding. The
posted program is stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
it, and seeded faults show each check catches what it guards.
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

STEM = "dt_crank_pin"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "pin.step")


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
        for group in groups:
            key = group[0] if isinstance(group, tuple) else group
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
                *(line.format(feed=f"{job['feed']:.3f}") for line in lines_of[key]),
            ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {"spot": 1, "drill-45": 2}
    assert ctx["manual"] == {}


def test_the_recipes_program_passes_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("jaw_top_over_pin_mm", 12.0, "jaw_top_over_pin_mm"),
        ("hole_tip_height_mm", -0.5, "hole_tip_height_mm"),
        ("big_end_overhang_mm", 4.5, "not in the overhang"),
        ("spot_dia_mm", 2.0, "between the #45"),
        ("hole_peck_mm", 2.5, "over one #45 diameter"),
        ("drill_45_projection_min_mm", 20.0, "drill_45_projection_min_mm"),
        ("parallel_thickness_mm", 6.35, "as wide as the pin"),
        ("big_end_max_mm", 5.62, "big_end_max_mm"),
        ("station_min_mm", 3.556, "station_min_mm"),
        ("station_max_mm", 4.064, "station_max_mm"),
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
        # The #45 stopped inside the pin: no hole through.
        ("hole_drill", "G1 Z-6.609 F{feed}", "G1 Z-5.000 F{feed}", "holes"),
        # A peck re-entry rapided past the depth already drilled.
        ("hole_drill", "G0 Z-4.500", "G0 Z-5.800", "rapid"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

"""The amplitude bar's CAM recipe agrees with its model and plan.

``cad/process/ch_amplitude_bar/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
them, and seeded faults show each check catches what it guards.
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

STEM = "ch_amplitude_bar"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "bar.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a program that does not load its first tool starts on
    its M3."""
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
        keys = [group[0] if isinstance(group, tuple) else group for group in groups]
        for index, key in enumerate(keys):
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            if index or name in RECIPE.LOAD_FIRST_TOOL:
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                    f"M6 T{number}",
                ]
            text += [
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


def _lines(ctx: dict, key: str) -> list[str]:
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def test_context_numbers_the_tools_and_places_the_cuts(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "saw": 2,
        "spot": 3,
        "drill-49": 4,
        "reamer-0775": 5,
    }
    assert set(RECIPE.LOAD_FIRST_TOOL) == {
        "CA01_foot_end",
        "CA03_top_end",
        "CA05_pin_hole",
    }
    # The saw's two levels per notch: the ledge, then the far wall less the
    # saw's thickness, so the notch is the band's middle wide.
    levels = {
        key: sorted({line for line in _lines(ctx, key) if line.startswith("G1 Z")})
        for key in ("foot_notch", "top_notch")
    }
    assert levels == {
        "foot_notch": ["G1 Z1.854 F{feed}", "G1 Z2.946 F{feed}"],
        "top_notch": ["G1 Z1.600 F{feed}", "G1 Z3.213 F{feed}"],
    }
    # Two pin holes .25 in from the top end, one per bar, a pitch apart.
    holes = next(
        kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if program.startswith("CA05") and check == "holes"
    )
    assert holes == [[-6.35, -3.175], [-6.35, -9.5]]


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"top_excess_max_mm": 2.0}, "top_excess_max_mm"),
        (
            {"blank_length_in": 31.83, "blank_length_min_mm": 808.482},
            "under the length",
        ),
        ({"bar_pitch_mm": 6.35}, "bar_pitch_mm"),
        ({"load_width_mm": 25.2984}, "load_width_mm"),
        ({"bars_per_load": 4, "load_width_mm": 25.2984}, "one or two bars"),
        ({"foot_notch_width_mm": 2.6416}, "foot_notch_width_mm"),
        ({"top_notch_depth_mm": 14.224}, "top_notch_depth_mm"),
        ({"top_notch_step_mm": 3.4925}, "top_notch_step_mm"),
        ({"end_protrusion_mm": 14.0}, "top notch's depth"),
        ({"saw_collar_dia_max_mm": 45.0}, "saw_collar_dia_max_mm"),
        ({"drill_tip_height_mm": -0.5}, "drill_tip_height_mm"),
        ({"spot_dia_mm": 1.9}, "under the #49"),
        ({"top_clamp_end_mm": 19.05}, "top_clamp_end_mm"),
        ({"half_mill_projection_min_mm": 19.0}, "jaw tops"),
        ({"drill_projection_mm": 20.0}, "jaw tops"),
        ({"spot_projection_mm": 20.0}, "holder_grip_min_mm"),
        ({"parallel_height_mm": 0}, "jaw tops"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(changes, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"].update(changes)
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The top end's last pass left short of the length.
        (
            "top_end",
            lambda line: line.startswith("G0 X6.350"),
            lambda line: line.replace("X6.350", "X6.604"),
            "passes",
        ),
        # A saw pass run the climb way (+Y with the saw right of the ends).
        (
            "top_notch",
            lambda line: line.startswith("G1 Y"),
            lambda line: "G1 Y100.000 F{feed}",
            "passes",
        ),
        # The saw lowered to its level in a rapid.
        (
            "foot_notch",
            lambda line: line.startswith("G1 Z1.854"),
            lambda line: "G0 Z1.854",
            "rapid",
        ),
        # A pin hole drilled short of the down face.
        (
            "pin_drill",
            lambda line: line == "G1 Z-1.057 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

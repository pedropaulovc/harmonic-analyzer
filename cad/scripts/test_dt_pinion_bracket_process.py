"""The pinion bracket strap's CAM recipe agrees with its model and plan.

``cad/process/dt_pinion_bracket/cam.py`` writes every path itself; its
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

STEM = "dt_pinion_bracket"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "strap.step")


@pytest.fixture(scope="module")
def context() -> dict:
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


def test_context_accepts_the_plan_and_numbers_the_tools(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-c": 3,
        "drill-5-16": 4,
        "reamer-2510": 5,
        "em-eighth": 6,
        "drill-26": 7,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # Both straps' bores on the blank's centre line, the arbor bores the
    # centre distance past the pivot bores; the seat its height from the
    # pivot bore's axis at its station from face A (the cross hole is
    # match-drilled at assembly, owner ruling 2026-11-21: no PB04 hole).
    holes = {
        program: kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if check == "holes"
    }
    assert holes["PB02_flat@2"] == [[17.0, -15.875], [70.0, -15.875]]
    assert holes["PB02_flat@3"] == [[45.0, -15.875], [98.0, -15.875]]
    assert holes["PB04_edge@0"] == [[7.0, -4.572]]
    names = [name for _p, ops in RECIPE.PROGRAMS for group in ops for name in group]
    assert names and all("cross" not in name for name in names)


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("blank_length_max_mm", 120.0, "blank_length_max_mm"),
        ("blank_length_min_in", 4.3, "right end under its web"),
        ("part_pitch_mm", 48.0, "pivot_2_x_mm"),
        ("saw_kerf_mm", 3.5, "too near the second strap"),
        ("saw_offset_mm", 3.5, "across the slot"),
        ("z_touch_y_mm", -10.0, "z_touch_y_mm"),
        ("z_touch_x_mm", 3.0, "wholly on the blank"),
        ("pivot_drill_tip_mm", -2.0, "pivot_drill_tip_mm"),
        ("bore_spot_dia_mm", 3.3, "between the pilot"),
        ("edge_spot_dia_mm", 3.8, "over the #26"),
        ("face_b_skim_mm", 0.5, "face_b_skim_mm"),
        ("grip_mm", 7.5, "grip_mm"),
        ("overhang_min_mm", 6.35, "overhang_min_mm"),
        ("seat_floor_dia_mm", 3.70, "under the #26"),
        ("seat_floor_dia_mm", 4.03, "between the end mill"),
        ("seat_finish_dia_mm", 4.0, "seat_finish_dia_mm"),
        ("seat_floor_z_mm", -4.3, "seat_floor_z_mm"),
        ("pivot_apex_x_mm", -7.5, "pivot_apex_x_mm"),
        ("finder_tip_depth_mm", 2.54, "below the jaw tops"),
        ("parallel_thickness_mm", 6.35, "parallel's inner edge"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # A face pass moved onto the blank's middle: a full-width slot.
        (
            "face_b",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-15.000",
            "face",
        ),
        # A pivot bore drilled short of its exit.
        (
            "pivot_drill",
            lambda line: line == "G1 Z-2.847 F{feed}",
            lambda line: "G1 Z-1.000 F{feed}",
            "holes",
        ),
        # A reamer rapided out of its bore.
        (
            "pivot_ream",
            lambda line: line.startswith("G1 Z10.144"),
            lambda line: "G0 Z10.144",
            "feed_out",
        ),
        # The far flank cut .010 inside the strap.
        (
            "outline",
            lambda line: line == "G1 X45.000 F{feed}",
            lambda line: "G1 X45.000 Y-24.708 F{feed}",
            "outline",
        ),
        # An outline level rapided down past the depth already cut.
        (
            "outline",
            lambda line: line.startswith("G0 Z8.") and line != "G0 Z14.144",
            lambda line: "G0 Z5.000",
            "rapid",
        ),
        # The seat drilled short of its depth.
        (
            "seat_drill",
            lambda line: line == "G1 Z-4.014 F{feed}",
            lambda line: "G1 Z-2.000 F{feed}",
            "holes",
        ),
        # The seat's turns run climb (G3).
        (
            "seat_mill",
            lambda line: line.startswith("G2 "),
            lambda line: "G3" + line[2:],
            "bounds",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(context, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

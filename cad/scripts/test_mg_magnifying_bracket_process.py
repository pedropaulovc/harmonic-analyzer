"""The magnifying bracket's CAM recipe agrees with its model and plan.

``cad/process/mg_magnifying_bracket/cam.py`` writes every path itself; its
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

STEM = "mg_magnifying_bracket"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "bracket.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's lines after its M6, ending with its M30."""
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
        for key in keys:
            if key in ctx["manual"]:
                manual = ctx["manual"][key]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
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
        if not any(key in ctx["manual"] for key in keys):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-37": 3,
        "drill-7": 4,
        "tap-guide": 5,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # The mounting holes from the seat at their stations from F (X0), on
    # the line 5.750 from L once L is faced; the lever tap at the nose's
    # centre, X from the seat, on the width's centre line from L (Y0).
    centres = {
        program: kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    assert centres["MB02_seat@2"] == [[-9.0, -6.639], [-22.7, -6.639]]
    assert centres["MB06_nose@2"] == [[94.057, -5.5]]
    stop = ctx["manual"]["lever_tap"]
    assert stop["tool"] == 5 and stop["at"] == [94.057, -5.5]
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"
    # The notch in two halves that meet past each other: no thin skin.
    depths = {
        program: kwargs["z_min"]
        for program, check, kwargs in ctx["expect"]
        if check == "depth"
    }
    assert (
        depths["MB03_notch"] + depths["MB04_low"] < PLAN["parameters"]["high_level_mm"]
    )
    # Issue #3742: the unloaded inside X-root follows INSIDE CORNERS R.040 MAX
    # and is modeled at .020 in (2x edge_break_r = 0.508 mm).
    assert PLAN["parameters"]["inside_root_model_r_mm"] == pytest.approx(
        2 * FEATURES["general_tolerances"]["edge_break_r"]
    )


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("blank_length_min_in", 4.70, "blank_length_min_mm"),
        ("high_level_mm", 12.0, "high_level_mm"),
        ("width_level_mm", 1.5, "width_level_mm"),
        ("notch_split_mm", 6.0, "notch_split_mm"),
        ("notch_through_mm", 5.0, "notch_through_mm"),
        ("notch_level_mm", 2.0, "notch_level_mm"),
        ("foot_wall_woc_mm", 0.2, "foot_wall_woc_mm"),
        ("neck_level_mm", 2.0, "neck_level_mm"),
        ("inside_root_model_r_mm", 0.254, "inside_root_model_r_mm"),
        ("nose_jaw_back_mm", 10.0, "nose_jaw_back_mm"),
        ("mount_tip_z_mm", -4.0, "mount_tip_z_mm"),
        ("tap_tip_z_mm", -2.0, "tap_tip_z_mm"),
        ("mount_spot_dia_mm", 2.7, "not under its drill"),
        ("tap_spot_dia_mm", 5.0, "not between the pilot"),
        ("tap_reach_max_mm", 30.0, "tap_reach_max_mm"),
        ("tap_stack_max_mm", 260.0, "tap_stack_max_mm"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("riser_height_mm", 30.0, "lying_grip_mm"),
        ("neck_overhang_mm", 6.0, "neck_overhang_mm"),
        ("nose_jaw_side_mm", 85.0, "nose_jaw_side_mm"),
        ("mount_y_mm", 5.75, "mount_y_mm"),
        # A short stick-out: the collet would reach the foot at the last level.
        ("neck_mill_projection_min_mm", 40.0, "collet reaches the foot"),
        ("neck_mill_projection_min_mm", 52.0, "less than 1 in"),
        # The 1/2 in end mill set too short: its collet reaches MB03's part.
        ("half_mill_projection_mm", 10.0, "MB03_notch: the end mill's collet"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with every line of operation ``key`` (or of the tap stop)
    that ``pick`` accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    lines[:] = [change(line) if pick(line) else line for line in lines]
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The nose's finish turned conventional (G3): the climb outline is broken.
        (
            "nose",
            lambda line: line.startswith("G2 X105.907 Y-5.500"),
            lambda line: "G3" + line[2:],
            "outline",
        ),
        # The nose's finish radius .010 too large: off its offset.
        (
            "nose",
            lambda line: line.startswith("G2 X105.907"),
            lambda line: line.replace("X105.907", "X106.161"),
            "outline",
        ),
        # The neck's last level left .010 high: the neck comes out thick.
        (
            "neck",
            lambda line: line == "G1 Z12.500 F{feed}",
            lambda line: "G1 Z12.754 F{feed}",
            "face",
        ),
        # The passes along the foot dropped: the inside corner keeps MB03's R.25.
        (
            "neck",
            lambda line: line == "G1 Y-19.890 F{feed}",
            lambda line: "G1 Y8.890 F{feed}",
            "cleared",
        ),
        # MB03's last notch level left .010 high: its floor not cleared.
        (
            "notch",
            lambda line: line == "G1 Z6.262 F{feed}",
            lambda line: "G1 Z6.516 F{feed}",
            "cleared",
        ),
        # A mounting hole drilled off its station.
        (
            "mount_drill",
            lambda line: line == "G0 X-9.000 Y-6.639",
            lambda line: "G0 X-9.508 Y-6.639",
            "holes",
        ),
        # The #7 stopped short of O: the tap drill not through.
        (
            "tap_drill",
            lambda line: line == "G1 Z-2.534 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # MB05's rapids at the old clearance plane, below the foot's top:
        # entering from beside the seat, the cutter crosses the foot.
        (
            "neck",
            lambda line: line == "G0 Z59.250",
            lambda line: "G0 X-10.000 Y-5.500 Z24.350",
            "keep_out",
        ),
        # MB06's spot section opened below the foot's top: its first XY
        # rapid after the M6 runs under the stated tool-change height.
        (
            "tap_spot",
            lambda line: line == "G0 Z59.250",
            lambda line: "G0 Z24.545",
            "tools",
        ),
        # The foot pass run inside the foot's station: the cutter in the foot.
        (
            "neck",
            lambda line: line == "G0 X9.525",
            lambda line: "G0 X6.000",
            "keep_out",
        ),
        # The tap stop holds (M0) instead of ending Idle.
        (
            "lever_tap",
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


def _reversed_wall_pass(ctx: dict, key: str, start: str, end: str) -> dict:
    """``ctx`` with the foot's wall pass (the operation's last cut) run from
    the neck toward F: the wall on the cutter's left, conventional."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    entry = max(i for i, line in enumerate(lines) if line.startswith(f"G0 X{start} Y"))
    cut = max(i for i, line in enumerate(lines) if line == f"G1 X{end} F{{feed}}")
    assert entry < cut
    lines[entry] = lines[entry].replace(f"X{start}", f"X{end}")
    lines[cut] = f"G1 X{start} F{{feed}}"
    return seeded


@pytest.mark.parametrize(
    ("key", "start", "end", "program"),
    [
        ("notch", "63.140", "19.350", "MB03_notch"),
        ("low_side", "-19.350", "-63.140", "MB04_low"),
    ],
)
def test_the_foot_wall_pass_climbs(ctx, tmp_path, key, start, end, program) -> None:
    seeded = _reversed_wall_pass(ctx, key, start, end)
    _post(seeded, tmp_path)
    found = [
        f
        for f in _findings(seeded, tmp_path)
        if f.check == "engagement" and f.program == f"{program}.nc"
    ]
    assert any(
        "cuts conventional under M3, declared climb" in f.detail for f in found
    ), found

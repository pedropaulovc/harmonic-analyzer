"""The cone tip block's CAM recipe agrees with its model and plan.

``cad/process/dt_cone_tip_block/cam.py`` writes every path itself; its
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

STEM = "dt_cone_tip_block"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "tip.step")


@pytest.fixture(scope="module")
def context() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a program that does not load its first tool starts on
    its M3; a tap stop's lines after its M6, ending with its M30."""
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
        if not any(key in ctx["manual"] for key in keys):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def test_context_accepts_the_plan_and_numbers_the_tools(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-43": 3,
        "drill-30": 4,
        "drill-3": 5,
        "chamfer": 6,
        "tap-guide": 7,
        "slit-saw": 8,
    }
    # Every program but the saw's loads its first tool: the saw is mounted
    # on its arbor by hand, with no tool-setter length.
    names = [name for name, _ops in RECIPE.PROGRAMS]
    assert set(RECIPE.LOAD_FIRST_TOOL) == set(names) - {"DT11_slit"}
    for stop in context["manual"].values():
        assert stop["tool"] == 7
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_slit_saw_steps_in_to_the_slits_depth(context) -> None:
    """Three passes, each a step no deeper than the plan's, the last at the
    slit's depth past the TOP end: the saw's centre its radius less that."""
    p = PLAN["parameters"]
    xs = [
        float(line.split()[1][1:])
        for line in _lines(context, "slit")
        if line.startswith("G0 X")
    ]
    radius = p["saw_dia_mm"] / 2
    depths = [round(radius - x, 3) for x in xs]
    assert depths == sorted(depths) and len(depths) == 3
    assert depths[-1] == pytest.approx(p["slit_depth_mm"], abs=1e-3)
    steps = [b - a for a, b in zip([0.0, *depths], depths, strict=False)]
    assert max(steps) <= p["slit_step_max_mm"] + 1e-3


def test_the_adjuster_is_drilled_where_it_is_countersunk_and_tapped(context) -> None:
    drilled = next(
        kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if program.startswith("DT08_adjuster") and check == "holes"
    )
    assert [context["manual"]["tap_adjuster"]["at"]] == [drilled[0]]


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("east_skim_mm", 1.0, "west_raw"),
        ("length_target_mm", 52.0, "length_target_mm"),
        ("depth_target_mm", 11.5, "depth_target_mm"),
        ("foot_tip_height_mm", 41.5, "foot_tip_height_mm"),
        ("clearance_depth_mm", 9.0, "clearance_depth_mm"),
        ("csk_orbit_mm", 0.5, "csk_orbit_mm"),
        ("foot_bottoming_reach_mm", 10.2, "foot_bottoming_reach_mm"),
        ("pinch_tap_reach_mm", 8.0, "pinch_tap_reach_mm"),
        ("adjuster_tap_reach_mm", 12.0, "adjuster_tap_reach_mm"),
        ("saw_cut_z_mm", 7.5, "saw_cut_z_mm"),
        ("blade_max_mm", 1.524, "blade_max_mm"),
        ("saw_collar_dia_max_mm", 50.8, "saw_collar_dia_max_mm"),
        ("lying_grip_mm", 8.0, "lying_grip_mm"),
        ("east_grip_mm", 6.8453, "east_grip_mm"),
        ("tap_stack_max_mm", 261.62, "tap_stack_max_mm"),
        ("adjuster_wrench_reach_max_mm", 200.0, "adjuster_wrench_reach_max_mm"),
        ("vise_slit_inset_mm", -120.0, "vise_slit_inset_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


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
        # The last saw pass short of the slit's depth.
        (
            "slit",
            lambda line: line.startswith("G0 X22.972"),
            lambda line: line.replace("X22.972", "X25.000"),
            "passes",
        ),
        # A saw pass lowered under the jaw tops, its spacers into the jaws.
        (
            "slit",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z5.000 F{feed}",
            "depth",
        ),
        # The adjuster drilled short of S.
        (
            "adjuster_drill",
            lambda line: line.startswith("G1 Z-2.625"),
            lambda line: "G1 Z1.000 F{feed}",
            "holes",
        ),
        # A countersink circle run too wide.
        (
            "north_csk",
            lambda line: line.startswith("G1 X38.764"),
            lambda line: "G1 X39.200 F{feed}",
            "cleared",
        ),
        # The first seat-face level run into the jaws.
        (
            "seat_face",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z20.000 F{feed}",
            "keep_out",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        (
            "tap_pinch",
            lambda line: line == "M30",
            lambda line: "M0",
            "tap_stop",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(context, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

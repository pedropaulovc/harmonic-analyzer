"""The pen frame's CAM recipe agrees with its model and plan.

``cad/process/pn_pen_frame/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the ``drilled_block`` adapter binds) with no FreeCAD and no SolidWorks, and
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

STEM = "pn_pen_frame"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "frame.step")


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
        "em-eighth": 2,
        "em-fine": 3,
        "spot": 4,
        "drill-43": 5,
        "dead-centre": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    stop = ctx["manual"]["tap"]
    # The tap from the bottom end at the drawing's .50 from L, mid-depth
    # (.155 from the back face against the fixed jaw).
    assert stop["tool"] == 6 and stop["at"] == [12.7, -3.937]
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("upright_top_max_mm", 44.0, "upright_top_max_mm"),
        ("blank_length_min_in", 1.59, "under the height"),
        ("blank_y_in", 1.75, "blank_y_in"),
        ("spot_dia_mm", 2.4, "under the #43"),
        ("drill_tip_depth_mm", 7.0, "drill_tip_depth_mm"),
        ("drill_full_depth_mm", 6.5, "drill_full_depth_mm"),
        ("tap_reach_min_mm", 8.0, "tap_reach_min_mm"),
        ("tap_reach_max_mm", 35.0, "far wall"),
        ("tap_stack_max_mm", 270.0, "tap_stack_max_mm"),
        ("window_finish_stock_mm", 0.2, "radial"),
        ("window_rough_step_mm", 1.2, "window_rough_step_mm"),
        ("window_finish_step_mm", 8.382, "window_finish_step_mm"),
        ("rough_plunge_feed_per_min_mm", 234.7, "rough_plunge_feed_per_min_mm"),
        ("finish_cutter_dia_mm", 2.38125, "cutter"),
        ("window_right_mm", 22.5, "window_right_mm"),
        ("parallel_thickness_mm", 6.35, "parallel stack"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_finish_cutter_over_the_corner_radius_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["endmill-5-64-long"]["diameter_mm"] = 2.38125
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["finish_cutter_dia_mm"] = 2.38125
    with pytest.raises(ValueError, match="corners over"):
        RECIPE.context(FEATURES, plan, shop, "frame.step")


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` (or of the tap
    stop) replaced."""
    seeded = copy.deepcopy(ctx)
    if key in seeded["manual"]:
        lines = seeded["manual"][key]["gcode"]
    else:
        lines = next(
            op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key
        )
    assert old in lines, (key, old)
    lines[lines.index(old)] = new
    return seeded


def _line(ctx: dict, key: str, prefix: str, index: int = 0) -> str:
    lines = next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)
    return [line for line in lines if line.startswith(prefix)][index]


@pytest.mark.parametrize(
    ("key", "prefix", "index", "change", "check"),
    [
        # The first face pass moved onto the part's middle: a full-width cut.
        (
            "back_face",
            "G0 X",
            0,
            lambda line: line.split(" Y")[0] + " Y-20.000",
            "face",
        ),
        # The window's far wall finished .010 too far out: the window oversize.
        ("window_finish", "G1 Y-7.", 0, lambda line: "G1 Y-6.834 F{feed}", "outline"),
        # The rough slot run anticlockwise on its first side: climb.
        ("window_rough", "G1 Y-7.", 0, lambda line: "G1 Y-32.372 F{feed}", "outline"),
        # The finish's last level stopped short of the front face.
        ("window_finish", "G1 Z-0.508", 0, lambda line: "G1 Z0.000 F{plunge}", "depth"),
        # The tap drill stopped in the rail.
        ("tap_drill", "G1 Z-7.775", 0, lambda line: "G1 Z-5.000 F{feed}", "holes"),
        # A peck re-entry rapided past the depth already drilled.
        ("tap_drill", "G0 Z-1.532", 0, lambda line: "G0 Z-3.000", "rapid"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, prefix, index, change, check
) -> None:
    old = _line(ctx, key, prefix, index)
    seeded = _seed(ctx, key, old, change(old))
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


def test_a_tap_stop_that_holds_is_caught(ctx, tmp_path) -> None:
    seeded = _seed(ctx, "tap", "M30", "M0")
    _post(seeded, tmp_path)
    assert "tap_stop" in {finding.check for finding in _findings(seeded, tmp_path)}

"""The stop block's CAM recipe agrees with its model and plan.

``cad/process/ms_stop_block/cam.py`` writes every path itself; its
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

STEM = "ms_stop_block"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "stop.step")


@pytest.fixture(scope="module")
def context() -> dict:
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


def test_context_accepts_the_plan_and_numbers_the_tools(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "em-eighth": 2,
        "chamfer": 3,
        "spot": 4,
        "drill-43": 5,
        "tap-guide": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    assert "MS05_relief" not in dict(RECIPE.PROGRAMS)
    # The thumb hole is tapped where MS08 drilled it.
    drilled = next(
        kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if program == "MS08_thumb@1" and check == "holes"
    )
    assert drilled == [context["manual"]["tap_thumb"]["at"]]
    for stop in context["manual"].values():
        assert stop["tool"] == 6
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_rebate_corner_radius_max_is_validated_from_feature_manifest() -> None:
    bad = copy.deepcopy(FEATURES)
    bad["features"]["rebate_corner"]["corner_radius_max_design"] = 0.20
    with pytest.raises(ValueError, match="corner_radius_max_design"):
        RECIPE.context(bad, PLAN, SHOP, "stop.step")


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("end_trim_mm", 6.0, "end_trim_mm"),
        ("thickness_min_mm", 13.0, "thickness_min_mm"),
        ("rebate_centre_x_mm", 4.5, "rebate_centre_x_mm"),
        ("rebate_back_height_mm", 2.0, "rebate_back_height_mm"),
        ("slot_cut_max_mm", 3.175, "slot_cut_max_mm"),
        ("slot_go_pin_in", 0.123, "slot_go_pin_in"),
        ("slot_nogo_pin_in", 0.131, "slot_nogo_pin_in"),
        ("slot_test_feed_mm_min", 213.36, "slot_test_feed_mm_min"),
        ("slot_test_x_mm", 13.0, "inside the waste end"),
        ("test_far_y_mm", 29.0, "test_far_y_mm"),
        ("chamfer_tip_depth_mm", 1.9, "chamfer_tip_depth_mm"),
        ("thumb_tip_height_mm", 5.5, "thumb_tip_height_mm"),
        ("thumb_tap_reach_mm", 13.0, "lowest roof"),
        ("plate_tap_reach_mm", 8.0, "between the thread"),
        ("spot_dia_mm", 3.0, "under the #43"),
        ("lying_grip_mm", 8.0, "lying_grip_mm"),
        ("tap_stack_max_mm", 300.0, "tap_stack_max_mm"),
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
        # The first back-face pass moved onto the slice's middle: a full-width slot.
        (
            "back_face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-9.525",
            "face",
        ),
        # The first rebate wall pass run into the roof.
        (
            "rebate",
            lambda line: line.startswith("G1 X"),
            lambda line: "G1 X2.000 F{feed}",
            "keep_out",
        ),
        # The thumb hole drilled short of the rebate.
        (
            "thumb_drill",
            lambda line: line == "G1 Z4.510 F{feed}",
            lambda line: "G1 Z6.000 F{feed}",
            "holes",
        ),
        # A peck re-entry rapided past the depth already drilled.
        (
            "thumb_drill",
            lambda line: line == "G0 Z12.692",
            lambda line: "G0 Z10.000",
            "rapid",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        (
            "tap_thumb",
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

"""The feed rack's CAM recipe agrees with its model and plan.

``cad/process/pd_feed_rack/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the ``drilled_block`` adapter binds) with no FreeCAD, no SolidWorks and no
feature bundle, and refuses any plan number that disagrees with the model,
the shop or the holding. The posted programs are stood in for by the
recipe's own section lines under the grbl post's tool-change block, so every
check the recipe declares runs on them, and seeded faults show each check
catches what it guards.
"""

from __future__ import annotations

import copy
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "pd_feed_rack"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "rack.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's lines after its M6, ending with its M30."""
    sections = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, keys in RECIPE.PROGRAMS:
        text = [
            f"({name})",
            f"({ctx['comment']})",
            "(Begin preamble)",
            "G17 G90",
            "G21",
            "G54",
        ]
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


def _expect(ctx: dict, program: str, check: str) -> list[dict]:
    return [
        kwargs
        for name, kind, kwargs in ctx["expect"]
        if name == program and kind == check
    ]


def test_context_numbers_the_tools_and_runs_each_hole_file_at_its_own_zero(ctx) -> None:
    assert ctx["numbers"] == {
        "em-quarter": 1,
        "spot": 2,
        "drill-3-64": 3,
        "tap-guide": 4,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _keys in RECIPE.PROGRAMS)
    taps = [
        f for f in FEATURES["features"].values() if f.get("kind") == "threaded_hole"
    ]
    assert len(taps) == 4
    # Each hole file runs once per hole at X0 Y0, X0 moved onto that hole's
    # tooth by hand: one hole, and the jaws and the stack from all four.
    for program in ("FR03_spot", "FR04_drill"):
        (holes,) = _expect(ctx, program, "holes")
        assert holes["centres"] == [[0.0, 0.0]]
        (keep,) = _expect(ctx, program, "keep_out")
        assert len(keep["boxes"]) == 3 * len(taps)
    stop = ctx["manual"]["tap"]
    assert stop["at"] == [0.0, 0.0] and stop["tool"] == 4
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_each_end_is_milled_in_its_own_hold_from_the_milled_left_end(ctx) -> None:
    p = PLAN["parameters"]
    r = p["em_dia_mm"] / 2
    (left,) = _expect(ctx, "FR01_left", "side_passes")
    (right,) = _expect(ctx, "FR02_right", "side_passes")
    assert (left["final"], left["direction"]) == (round(-r, 3), -1.0)
    assert (right["final"], right["direction"]) == (
        round(p["length_target_mm"] + r, 3),
        1.0,
    )
    assert left["cut"] == right["cut"] == "conventional"
    # The jaws: the left end's hold .30 in in from the left end, the right
    # end's from the longest piece's raw right end.
    jaw = {
        program: next(
            box
            for box in _expect(ctx, program, "keep_out")[0]["boxes"]
            if box["name"] == "fixed jaw"
        )
        for program in ("FR01_left", "FR02_right")
    }
    skim = p["left_end_skim_mm"]
    assert jaw["FR01_left"]["x"][0] == pytest.approx(p["end_overhang_mm"] - skim)
    assert jaw["FR02_right"]["x"][1] == pytest.approx(p["right_clamp_end_mm"])


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _keys in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("length_target_mm", 269.6, "length_target_mm"),
        ("section_max_mm", 4.95, "section_max_mm"),
        ("blank_length_max_in", 10.9, "blank_length_max_mm"),
        ("length_dro_min_mm", 271.9, "length_dro_min_mm"),
        ("end_overhang_mm", 3.0, "left_clamp_end_mm"),
        ("right_hold_overhang_mm", 100.0, "right_hold_overhang_mm"),
        ("measure_overhang_mm", 101.6, "measure_overhang_mm"),
        # Hold B's rod sits toward the jaws (the space on tap 3's tooth's
        # left): 119.0 clears hold A but not hold B.
        ("measure_overhang_mm", 119.0, "the edge finder would reach the jaws"),
        ("y_touch_mm", 5.0, "y_touch_mm"),
        ("spot_dia_mm", 2.0, "spot"),
        ("peck_mm", 1.5, "peck_mm"),
        ("drill_tip_height_mm", -3.3, "drill_tip_height_mm"),
        ("tap_point_depth_mm", 3.3, "tap_point_depth_mm"),
        ("tap_stack_max_mm", 280.0, "tap_stack_max_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_an_end_hold_that_leaves_a_finished_end_inside_the_jaws_is_refused() -> None:
    # The right end's raw end 3 mm past the jaws: the longest piece's finished
    # end lies 0.81 mm inside them, and the cutter would mill the jaw.
    plan = copy.deepcopy(PLAN)
    p = plan["parameters"]
    jaw, hold = p["vise_jaw_width_mm"], p["right_hold_length_mm"]
    p["end_overhang_mm"] = 3.0
    p["left_clamp_end_mm"] = round(3.0 + jaw, 4)
    p["right_hold_overhang_mm"] = round(hold - jaw - 3.0, 4)
    p["right_clamp_end_mm"] = round(hold - 3.0, 4)
    with pytest.raises(ValueError, match="a finished end lies inside the jaws"):
        _context(plan)


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def _reverse_first_right_pass(lines: list[str]) -> None:
    """The right end's first pass run -Y (the strip on the cutter's right
    under M3): climb, where the recipe declares conventional."""
    start = next(
        i
        for i, line in enumerate(lines)
        if line.startswith("G0 X") and line.endswith(" Y-10.630")
    )
    cut = next(i for i, line in enumerate(lines) if line == "G1 Y5.715 F{feed}")
    lines[start] = lines[start].replace(" Y-10.630", " Y5.715")
    lines[cut] = "G1 Y-10.630 F{feed}"


def _replace(old: str, new: str) -> Callable[[list[str]], None]:
    def edit(lines: list[str]) -> None:
        lines[lines.index(old)] = new

    return edit


@pytest.mark.parametrize(
    ("key", "edit", "check"),
    [
        # The left end's first pass dropped: the last takes both steps.
        ("left_end", _replace("G0 X-3.556 Y5.715", "G0 X-3.175 Y5.715"), "passes"),
        ("right_end", _reverse_first_right_pass, "cut"),
        # The right end's first pass moved over the jaws.
        (
            "right_end",
            _replace("G0 X276.352 Y-10.630", "G0 X262.000 Y-10.630"),
            "keep_out",
        ),
        # The hole drilled short of its depth.
        ("drill", _replace("G1 Z-3.634 F{feed}", "G1 Z-3.000 F{feed}"), "holes"),
        # A peck's re-entry rapided past the depth already drilled.
        ("drill", _replace("G0 Z-2.500", "G0 Z-3.500"), "rapid"),
        # A tap stop that holds (M0) instead of ending Idle.
        ("tap", _replace("M30", "M0"), "tap_stop"),
        # A tap stop that moves Z down onto the hole.
        ("tap", _replace("G0 X0.000 Y0.000", "G0 X0.000 Y0.000 Z-1.000"), "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(ctx, tmp_path, key, edit, check) -> None:
    seeded = copy.deepcopy(ctx)
    edit(_lines(seeded, key))
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

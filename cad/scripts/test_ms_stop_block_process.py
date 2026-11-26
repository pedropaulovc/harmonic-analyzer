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
import math
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
        "em-sixteenth": 3,
        "chamfer": 4,
        "spot": 5,
        "drill-43": 6,
        "tap-guide": 7,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # The thumb hole is tapped where MS08 drilled it.
    drilled = next(
        kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if program == "MS08_thumb@1" and check == "holes"
    )
    assert drilled == [context["manual"]["tap_thumb"]["at"]]
    for stop in context["manual"].values():
        assert stop["tool"] == 7
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_relief_plunges_keep_it_inside_its_height_band(context) -> None:
    """Every cutter the traveler accepts (the plan's least to its most)
    plunges no more than half itself apart and leaves the relief's clear
    height between the ridges, √(D² − s²), inside the printed band; the
    nominal cutter's ridge is the plan's scallop."""
    centres = next(
        kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if program == "MS05_relief" and check == "holes"
    )
    steps = {
        round(abs(b[1] - a[1]), 3) for a, b in zip(centres, centres[1:], strict=False)
    }
    step = max(steps)
    p = PLAN["parameters"]
    band = FEATURES["features"]["relief_floor"]["relief_height"]
    nominal = SHOP["tools"]["endmill-carbide-3fl-1-16-loc-1-2"]["diameter_mm"]
    for cutter in (p["relief_cutter_min_mm"], nominal, p["relief_cutter_max_mm"]):
        assert step <= cutter / 2 + 1e-3
        clear = math.sqrt(cutter**2 - step**2)
        assert band[0] - 1e-3 <= clear <= band[1] + 1e-3, cutter
    radius = nominal / 2
    ridge = radius - math.sqrt(radius**2 - (step / 2) ** 2)
    assert ridge <= p["relief_scallop_mm"] + 1e-3


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
        ("relief_plunge_step_mm", 1.0, "relief_plunge_step_mm"),
        ("relief_scallop_mm", 0.2, "relief_scallop_mm"),
        ("relief_cutter_min_mm", 1.6, "relief_cutter_min_mm"),
        ("slot_cut_max_mm", 3.175, "slot_cut_max_mm"),
        ("slot_go_pin_in", 0.123, "slot_go_pin_in"),
        ("relief_nogo_pin_in", 0.071, "relief_nogo_pin_in"),
        ("slot_test_feed_mm_min", 213.36, "slot_test_feed_mm_min"),
        ("relief_test_x_mm", 10.5, "apart"),
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


def test_a_relief_cutter_whose_flutes_stop_above_the_relief_is_refused() -> None:
    """A stub-flute 1/16 (.093 of flutes) would bring its 1/8 shank into the
    rebate beside the roof: refused."""
    shop = copy.deepcopy(SHOP)
    shop["tools"]["endmill-carbide-3fl-1-16-loc-1-2"]["flute_length_mm"] = 2.3622
    with pytest.raises(ValueError, match="flutes stop short"):
        RECIPE.context(FEATURES, PLAN, shop, "stop.step")


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
        # The relief's first plunge moved off its line, below the rebate's back.
        (
            "relief",
            lambda line: line.startswith("G0 X"),
            lambda line: "G0 X4.200" + line[line.index(" Y") :],
            "keep_out",
        ),
        # A relief plunge stopped short of the relief's back.
        (
            "relief",
            lambda line: line == "G1 Z-9.779 F{feed}",
            lambda line: "G1 Z-9.000 F{feed}",
            "holes",
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

"""The transgear arm's CAM recipe agrees with its model and plan.

``cad/process/pd_transgear_arm/cam.py`` writes every path itself; its
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
import math
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "pd_transgear_arm"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "arm.step")


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


def test_context_numbers_the_mill_tools_and_puts_the_holes_on_the_model(ctx) -> None:
    assert list(ctx["numbers"]) == list(RECIPE.CAM_TOOLS)
    assert list(ctx["numbers"].values()) == list(range(1, len(RECIPE.CAM_TOOLS) + 1))
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    f = FEATURES["features"]
    pin = f["pin_bore"]["at"][0]
    spotted = next(
        kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if program == "AR01_holes@0" and check == "holes"
    )
    pivot_x = PLAN["parameters"]["pivot_from_end_mm"]
    assert spotted == [[pivot_x, -12.7], [round(pivot_x + pin, 3), -12.7]]
    stops = [ctx["manual"]["tap_pivot"], ctx["manual"]["tap_pin"]]
    plate_x = PLAN["parameters"]["pivot_on_plate_x_mm"]
    assert [stop["at"] for stop in stops] == [
        [plate_x, -38.1],
        [round(plate_x + pin, 3), -38.1],
    ]
    for stop in stops:
        assert stop["tool"] == ctx["numbers"]["tap-guide"]
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_assembly_holes_are_left_to_md_pd_00(ctx) -> None:
    f = FEATURES["features"]
    assert (
        f["dowel_holes"]["made_at"] == "assembly"
        and f["plate_taps"]["made_at"] == "assembly"
    )
    final = PLAN["setups"][-1]["operations"][-1]["instruction"]
    for words in (
        "Ø.1240",
        "13A",
        "13D",
        "8-32",
        "13L",
        "13N",
        "13P",
        "MHA-PD-23",
        "11A",
    ):
        assert words in final


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_outline_clears_the_screw_heads_and_reaches_every_blank_corner(ctx) -> None:
    keep = next(
        kwargs
        for program, check, kwargs in ctx["expect"]
        if program == "AR05_outline" and check == "keep_out"
    )
    assert [c["name"] for c in keep["circles"]] == [
        "pivot screw head",
        "pin screw head",
    ]
    outline = next(
        kwargs
        for program, check, kwargs in ctx["expect"]
        if program == "AR05_outline" and check == "outline"
    )
    rough, finish = outline["passes"]
    assert finish["offset"] == pytest.approx(3.175) and finish["levels"] == [-0.254]
    assert (
        rough["levels"][-1] == -0.254
        and len(rough["levels"]) == PLAN["parameters"]["outline_levels"]
    )
    assert PLAN["parameters"]["blank_scrap_reach_mm"] < rough["offset"] + 3.175


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("holes_jaw_top_mm", 19.0, "holes_jaw_top_mm"),
        ("drill_14_tip_mm", -2.0, "drill_14_tip_mm"),
        ("drill_32_tip_mm", -1.5, "drill_32_tip_mm"),
        ("chamfer_tip_mm", 7.6, "chamfer_tip_mm"),
        ("plate_jaw_top_mm", 7.0, "plate_jaw_top_mm"),
        ("plate_drill_21_tip_mm", -14.0, "plate_drill_21_tip_mm"),
        ("plate_drill_43_tip_mm", -14.0, "plate_drill_43_tip_mm"),
        ("outline_rough_offset_mm", 3.5, "outline_rough_offset_mm"),
        ("outline_levels", 9, "outline_levels"),
        ("blank_scrap_reach_mm", 6.0, "blank_scrap_reach_mm"),
        ("blank_length_max_mm", 147.5, "blank_scrap_reach_mm"),
        ("blank_end_margin_min_mm", 1.0, "blank_end_margin_min_mm"),
        ("arm_length_mm", 140.0, "arm_length_mm"),
        ("spot_dia_mm", 3.0, "under the #32"),
        ("latch_ream_depth_mm", 9.0, "depth band"),
        ("latch_drill_depth_mm", 11.0, "stops short"),
        ("pivot_on_plate_x_mm", 10.0, "wholly on the plate"),
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


def _bottom(ctx: dict, key: str) -> str:
    return min(
        (line for line in _lines(ctx, key) if line.startswith("G1 Z")),
        key=lambda s: float(s.split()[1][1:]),
    )


@pytest.mark.parametrize(
    ("key", "change", "check"),
    [
        # The pivot drill stopped short of face A.
        ("pivot_drill", lambda line: "G1 Z0.500 F{feed}", "holes"),
        # The spot face plunged past its floor.
        ("spot_face", lambda line: "G1 Z6.500 F{feed}", "holes"),
        # A reamer rapided out of its bore.
        (
            "pin_ream",
            lambda line: line.replace("G1 Z", "G0 Z").replace(" F{feed}", ""),
            "feed_out",
        ),
    ],
)
def test_a_seeded_fault_in_a_hole_is_caught(ctx, tmp_path, key, change, check) -> None:
    bottom = _bottom(ctx, key)
    if check == "feed_out":
        lines = _lines(ctx, key)
        bottom = lines[lines.index(bottom) + 1]
    seeded = _seed(ctx, key, lambda line: line == bottom, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


@pytest.mark.parametrize(
    ("pick", "change", "check"),
    [
        # The finish pass run a level too high: the outline's bottom is left.
        (
            lambda line: line == "G1 Z-0.254 F{plunge}",
            lambda line: "G1 Z0.500 F{plunge}",
            "outline",
        ),
        # The first rough corner arc cut tight to the outline.
        (
            lambda line: line.startswith("G3 ") and " I-3.429 " in line,
            lambda line: line.replace("I-3.429", "I-1.000"),
            "outline",
        ),
        # A rapid to the start dropped through the pivot screw's head.
        (
            lambda line: line.startswith("G0 Z") and float(line[4:]) > 15,
            lambda line: "G0 Z8.000",
            "keep_out",
        ),
    ],
)
def test_a_seeded_fault_in_the_outline_is_caught(
    ctx, tmp_path, pick, change, check
) -> None:
    seeded = _seed(ctx, "outline", pick, change)
    if check == "keep_out":
        # Move the first rapid's XY onto the pivot screw.
        lines = _lines(seeded, "outline")
        pivot = ctx["manual"]["tap_pivot"]["at"]
        lines[1] = f"G0 X{pivot[0]:.3f} Y{pivot[1]:.3f}"
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


def test_a_tap_stop_that_holds_instead_of_ending_is_caught(ctx, tmp_path) -> None:
    seeded = _seed(ctx, "tap_pin", lambda line: line == "M30", lambda line: "M0")
    _post(seeded, tmp_path)
    assert "tap_stop" in {finding.check for finding in _findings(seeded, tmp_path)}


def test_the_lathe_setup_has_no_program(ctx) -> None:
    assert all(not name.startswith("AR06") for name, _ops in RECIPE.PROGRAMS)
    lathe = next(s for s in PLAN["setups"] if s["machine_kind"] == "lathe")
    assert lathe["title"].startswith("Latch-pin hole")
    assert math.isclose(PLAN["parameters"]["arm_length_mm"], 141.4)

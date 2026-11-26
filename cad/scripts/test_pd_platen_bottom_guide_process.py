"""The platen bottom guide's CAM recipe agrees with its model and plan.

``cad/process/pd_platen_bottom_guide/cam.py`` writes every path itself; its
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
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "pd_platen_bottom_guide"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "guide.step")


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


def test_context_numbers_the_tools_and_drills_every_lock_tap_from_one_zero(ctx) -> None:
    assert ctx["numbers"] == {"em-half": 1, "spot": 2, "drill-43": 3, "tap-guide": 4}
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    lock = sorted(
        (
            f
            for f in FEATURES["features"].values()
            if f.get("kind") == "threaded_hole" and "made_at" not in f
        ),
        key=lambda f: f["at"][0],
    )
    drilled = next(
        kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if program == "PB05_ends_drill@2" and check == "holes"
    )
    # X from the milled left end, Y down from the underside at the fixed jaw.
    assert drilled == [[round(f["at"][0], 3), round(-f["at"][1], 3)] for f in lock]
    taps = [ctx["manual"][f"tap_{k}"] for k in range(1, len(lock) + 1)]
    assert [stop["at"] for stop in taps] == drilled
    for stop in taps:
        assert stop["tool"] == 4
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"
    # Nothing made at assembly (the platen taps, the rack-screw holes) is cut.
    assert len(drilled) == 4


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("length_target_mm", 269.64, "length_target_mm"),
        ("depth_target_mm", 10.16, "depth_target_mm"),
        ("height_raw_max_mm", 17.78, "height_raw_max_mm"),
        ("blank_length_min_in", 10.66, "blank_length_min_mm"),
        ("right_end_station_mm", 271.164, "right_end_station_mm"),
        ("end_axial_doc_mm", 10.16, "end_axial_doc_mm"),
        ("drill_tip_height_mm", -1.0, "drill_tip_height_mm"),
        ("spot_dia_mm", 2.4, "under the #43"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("vise_overhang_mm", 55.48, "vise_overhang_mm"),
        ("tap_stack_max_mm", 279.4, "tap_stack_max_mm"),
        ("tap_wrench_reach_max_mm", 199.517, "tap_wrench_reach_max_mm"),
        ("parallel_thickness_mm", 5.5, "reaches the stacks"),
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
        # The first face pass moved onto the rail's middle: a full-width slot.
        (
            "rear_face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-7.925",
            "face",
        ),
        # The left end's first pass dropped: the second takes both steps.
        (
            "ends",
            lambda line: line == "G0 X-7.112 Y8.890",
            lambda line: "G0 X-6.350 Y8.890",
            "passes",
        ),
        # A right-end pass run the other way (-Y, the rail on the cutter's
        # right under M3): climb, where the recipe declares conventional.
        (
            "ends",
            lambda line: line == "G1 Y8.890 F{feed}",
            lambda line: "G1 Y-45.000 F{feed}",
            "cut",
        ),
        # A lock hole drilled short of its exit.
        (
            "lock_drill",
            lambda line: line == "G1 Z-1.679 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # A peck's re-entry rapided past the depth already drilled.
        (
            "lock_drill",
            lambda line: line == "G0 Z8.501",
            lambda line: "G0 Z6.000",
            "rapid",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        ("tap_3", lambda line: line == "M30", lambda line: "M0", "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

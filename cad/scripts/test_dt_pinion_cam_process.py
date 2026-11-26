"""The pinion eccentric cam's CAM recipe agrees with its model and plan.

``cad/process/dt_pinion_cam/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the cam's export binds) with no FreeCAD and no SolidWorks, and refuses any
plan number that disagrees with the model, the shop or the holding. The
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

STEM = "dt_pinion_cam"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "cam.step")


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
        "spot": 1,
        "drill-c": 2,
        "reamer": 3,
        "drill-50": 4,
        "tap-guide": 5,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    stop = ctx["manual"]["tap_stop"]
    assert stop["tool"] == 5 and stop["at"] == [4.1, 0.0]
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    tools = {t["id"]: t for t in PLAN["tools"]}
    assert tools["reamer"].get("status") == "to_order"
    # Fit audit F19: the MHA-DT-17 rod gauges the bore; no Class ZZ pins.
    assert "pins" not in tools
    assert not {t["ref"] for t in PLAN["tools"]} & {"zz-pins-2510-2515"}


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("bore_grip_mm", 7.5, "bore_grip_mm"),
        ("bore_parallel_gap_mm", 9.0, "bore_parallel_gap_mm"),
        ("bore_spot_dia_mm", 6.2, "under the C drill"),
        ("bore_drill_tip_mm", -11.0, "bore_drill_tip_mm"),
        ("bore_ream_tip_mm", -9.5, "bore_ream_tip_mm"),
        ("cross_axis_height_mm", 7.0, "cross_axis_height_mm"),
        ("cross_jaw_top_mm", 5.0, "cross_jaw_top_mm"),
        ("tap_spot_dia_mm", 1.9, "under the #50"),
        ("tap_drill_tip_mm", -9.3, "tap_drill_tip_mm"),
        ("peck_50_mm", 2.0, "peck_50_mm"),
        ("parallel_thickness_mm", 6.35, "bore_parallel_gap_mm"),
        ("tap_tip_below_jaw_top_mm", 15.5, "tap_tip_below_jaw_top_mm"),
        ("tap_stack_max_mm", 290.0, "tap_stack_max_mm"),
        ("r8_collet_gauge_mm", 10.0, "tap_stack_max_mm"),
        # 2.0 mm × tan 1°, not the ±0.10 mm (2.9° of turn) Codjiflo caught.
        ("orient_band_mm", 0.1, "orient_band_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("cut", "dia"), [("bore drill", 6.0), ("bore ream", 6.35), ("tap drill", 1.7)]
)
def test_a_cut_diameter_off_its_shop_tool_is_refused(cut, dia) -> None:
    plan = copy.deepcopy(PLAN)
    for setup in plan["setups"]:
        for op in setup.get("operations", ()):
            for milling in op.get("milling_cuts", ()):
                if milling["name"] == cut:
                    milling["cutter_dia_mm"] = dia
    with pytest.raises(ValueError, match="not its tool's"):
        _context(plan)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` (or of the
    tap stop) replaced."""
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


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # The bore drilled on the O.D. axis, not at the offset.
        ("bore_drill", "G0 X2.000 Y0.000", "G0 X0.000 Y0.000", "holes"),
        # The reamer stopped short of the front face.
        ("bore_ream", "G1 Z-10.500 F{feed}", "G1 Z-8.000 F{feed}", "holes"),
        # The #50 short of the bore.
        ("tap_drill", "G1 Z-9.834 F{feed}", "G1 Z-5.000 F{feed}", "holes"),
        # The reamer rapided out of the finished bore instead of fed out.
        ("bore_ream", "G1 Z1.000 F{feed}", "G0 Z1.000", "feed_out"),
        # A tap stop that holds (M0) instead of ending Idle.
        ("tap_stop", "M30", "M0", "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

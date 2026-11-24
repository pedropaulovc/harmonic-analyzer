"""The disc hub's CAM recipe agrees with its model and plan.

``cad/process/pd_transgear_disc_hub/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the hub's export binds) with no FreeCAD and no SolidWorks, and refuses any
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

STEM = "pd_transgear_disc_hub"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN, shop: dict = SHOP) -> dict:
    return RECIPE.context(FEATURES, plan, shop, "cam.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
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
        for (key,) in groups:
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


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "spot": 1,
        "drill-51": 2,
        "endmill": 3,
        "drill-56": 4,
        "drill-53": 5,
        "reamer-0615": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == (
        "CM01_flange_holes",
        "CM02_pin_hole",
        "CM03_pin_ream",
    )


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    assert STEM in _cam_programs.CAM_STEMS
    tools = {t["id"] for t in PLAN["tools"]}
    assert {
        "sharp",
        "reamer-3135",
        "endmill",
        "reamer-0615",
    } <= {t["id"] for t in PLAN["tools"] if t.get("status") == "to_order"}
    # Fit audit 2026-11-23: the reamed holes print no band, so no Class ZZ
    # pin gauges them; the ream's mate (the MHA-PD-VN-69 dowel) accepts it.
    assert not {"zz-3135", "zz-0615"} & tools
    assert not any("zz-pins" in t.get("ref", "") for t in PLAN["tools"])
    text = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    body = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    for word in ("zz-pins", "GO pin", "NO-GO"):
        assert word not in body


def test_the_traveler_leaves_the_assembly_work_to_pd_00() -> None:
    last = PLAN["setups"][-1]["operations"][-1]
    assert "tool" not in last
    for step in ("MHA-PD-VN-69", "8A", "9G", "MHA-PD-10", "(17)"):
        assert step in last["instruction"]


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {"CM01_flange_holes", "CM02_pin_hole", "CM03_pin_ream"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("stickout_mm", 15.0, "stickout_mm"),
        ("part_off_in", 0.55, "part_off_in"),
        ("regrip_out_mm", 7.0, "regrip_out_mm"),
        ("bar_use_in", 0.5, "bar_use_in"),
        ("flange_run_in", 0.6, "flange_run_in"),
        ("flange_parallel_gap_mm", 18.0, "flange_parallel_gap_mm"),
        ("parallel_thickness_mm", 6.35, "flange_parallel_gap_mm"),
        ("flange_jaw_top_mm", 2.0, "flange_jaw_top_mm"),
        ("parallel_stack_mm", 50.8, "flange_jaw_top_mm"),
        ("flange_spot_dia_mm", 1.8, "under the #51"),
        ("flange_drill_tip_mm", -5.0, "flange_drill_tip_mm"),
        ("flange_drill_past_mm", 2.0, "flange_drill_tip_mm"),
        ("flange_tool_out_min_in", 0.4, "flange_tool_out_min_in"),
        ("pin_jaw_top_mm", 10.0, "pin_jaw_top_mm"),
        ("pin_parallel_height_mm", 31.75, "pin_jaw_top_mm"),
        ("pin_flange_top_mm", 12.0, "pin_flange_top_mm"),
        ("pin_flat_bottom_mm", 5.0, "pin_flat_bottom_mm"),
        ("pin_flat_peck_mm", 1.0, "pin_flat_peck_mm"),
        ("endmill_reach_min_in", 0.05, "endmill_reach_min_in"),
        ("knockout_tip_mm", -7.0, "knockout_tip_mm"),
        ("knockout_past_mm", 1.5, "knockout_tip_mm"),
        ("pilot_tip_mm", -4.0, "pilot_tip_mm"),
        ("ream_tip_mm", -4.2, "ream_tip_mm"),
        ("stop_shallow_mm", -4.064, "stop_shallow_mm"),
        ("stop_deep_mm", -4.3, "stop_deep_mm"),
        ("peck_56_mm", 2.0, "peck"),
        ("pin_tool_out_min_in", 0.8, "pin_tool_out_min_in"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _with_cut(plan: dict, name: str, key: str, value: float) -> dict:
    plan = copy.deepcopy(plan)
    for setup in plan["setups"]:
        for op in setup.get("operations", ()):
            for milling in op.get("milling_cuts", ()):
                if milling["name"] == name:
                    milling[key] = value
    return plan


def test_a_cut_off_its_shop_tool_or_setting_is_refused() -> None:
    with pytest.raises(ValueError, match="not its tool's"):
        _context(_with_cut(PLAN, "flange drill", "cutter_dia_mm", 1.8))
    with pytest.raises(ValueError, match="not its setting's"):
        _context(_with_cut(PLAN, "pin ream", "rpm", 2000))


def test_a_reamer_off_its_hole_band_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["reamer-0615"] = {**shop["tools"]["reamer-0615"], "diameter_mm": 1.6}
    with pytest.raises(ValueError, match="outside its hole band"):
        _context(PLAN, shop)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` replaced."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    assert old in lines, (key, old)
    lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # A flange hole drilled off its circle.
        ("flange_drill", "G0 X9.525 Y0.000", "G0 X9.000 Y0.000", "holes"),
        # A flange hole moved across into the fixed jaw's stack.
        ("flange_drill", "G0 X9.525 Y0.000", "G0 X9.525 Y10.000", "keep_out"),
        # The #53 stopped short of the stop.
        ("pin_pilot", "G1 Z-4.518 F{feed}", "G1 Z-3.900 F{feed}", "holes"),
        # The knockout run down into the parallel.
        ("pin_knockout", "G1 Z-6.344 F{feed}", "G1 Z-7.000 F{feed}", "depth"),
        # The chord hole moved into the fixed jaw.
        ("pin_knockout", "G0 X4.420 Y-3.810", "G0 X4.420 Y-0.300", "keep_out"),
        # The reamer rapided out of its finished hole.
        ("pin_ream", "G1 Z6.888 F{feed}", "G0 Z6.888", "feed_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

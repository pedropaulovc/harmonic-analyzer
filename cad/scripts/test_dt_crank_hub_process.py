"""The crank hub's CAM recipe agrees with its model and plan.

``cad/process/dt_crank_hub/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the hub's export binds) with no FreeCAD and no SolidWorks, and refuses any
plan number that disagrees with the model, the shop or the holding. The
posted program is stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
it, and seeded faults show each check catches what it guards.
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

STEM = "dt_crank_hub"
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
    assert ctx["numbers"] == {"spot": 1, "drill-14": 2}
    assert RECIPE.LOAD_FIRST_TOOL == ("CM01_pin_hole",)


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    assert STEM in _cam_programs.CAM_STEMS
    # Fit audit 2026-11-23 (MHA-DT-31.bore, question 21): the reamed bore is
    # not gauged and the seat is fitted to the arm by trial, so no pins and
    # no sizing plug.
    refs = {t["ref"] for t in PLAN["tools"]}
    assert not any(ref.startswith("zz-pins") for ref in refs)
    assert "plug_length_in" not in PLAN["parameters"]


def test_the_recipes_program_passes_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {"CM01_pin_hole"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("cross_parallel_gap_mm", 15.0, "cross_parallel_gap_mm"),
        ("parallel_thickness_mm", 6.35, "cross_parallel_gap_mm"),
        ("cross_axis_height_mm", 7.0, "cross_axis_height_mm"),
        ("cross_jaw_top_mm", 1.5, "cross_jaw_top_mm"),
        ("vise_jaw_height_mm", 50.0, "cross_jaw_top_mm"),
        ("spot_dia_mm", 4.7, "under the #14"),
        ("drill_tip_mm", -23.0, "drill_tip_mm"),
        ("drill_past_mm", 2.0, "drill_tip_mm"),
        ("peck_14_mm", 5.0, "peck_14_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_cut_diameter_off_its_shop_tool_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    for setup in plan["setups"]:
        for op in setup.get("operations", ()):
            for milling in op.get("milling_cuts", ()):
                if milling["name"] == "pin drill":
                    milling["cutter_dia_mm"] = 4.5
    with pytest.raises(ValueError, match="not its tool's"):
        _context(plan)


def test_a_drill_off_the_hole_band_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["drill-14"] = {**shop["tools"]["drill-14"], "diameter_mm": 4.5}
    with pytest.raises(ValueError, match="outside the hole band"):
        RECIPE.context(FEATURES, PLAN, shop, "cam.step")


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
        # The hole drilled off its station.
        ("pin_drill", "G0 X13.462 Y0.000", "G0 X10.000 Y0.000", "holes"),
        # The #14 stopped inside the barrel, short of breaking through.
        ("pin_drill", "G1 Z-24.741 F{feed}", "G1 Z-15.000 F{feed}", "holes"),
        # The hole moved across into the fixed jaw.
        ("pin_drill", "G0 X13.462 Y0.000", "G0 X13.462 Y11.000", "keep_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

"""The cam turning fixture's CAM recipe agrees with its model and plan.

``cad/process/dt_cylinder_gear_tl_cam_fixture/cam.py`` writes every path
itself; its ``context`` runs here on the drawing's requirement manifest (the
features the fixture's export binds) with no FreeCAD and no SolidWorks, and
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

STEM = "dt_cylinder_gear_tl_cam_fixture"
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
    assert ctx["numbers"] == {
        "spot": 1,
        "drill-23-64": 2,
        "reamer-3740": 3,
        "drill-65": 4,
        "reamer-0365": 5,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # The throw line along +X: the stub at -X on the axis line, the clock pin
    # at +X and its small offset toward the fixed jaw (+Y).
    holes = {job["label"]: job["ops"][0][2][1] for job in ctx["jobs"]}
    assert holes["stub ream"] == "G0 X-8.641 Y0.000"
    assert holes["pin ream"] == "G0 X23.485 Y1.788"


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    assert STEM in _cam_programs.CAM_STEMS
    assert {"reamer-3740", "drill-65", "reamer-0365"} <= {
        t["id"] for t in PLAN["tools"] if t.get("status") == "to_order"
    }
    # Fit policy (#3513): the presses are the check; no plug gauge pair.
    assert not any("plug-gauges" in t.get("ref", "") for t in PLAN["tools"])


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("grip_mm", 25.4, "grip_mm"),
        ("jaw_top_below_z0_mm", 4.0, "jaw_top_below_z0_mm"),
        ("parallel_gap_mm", 70.0, "parallel_gap_mm"),
        ("parallel_thickness_mm", 6.35, "parallel_gap_mm"),
        ("parallel_height_mm", 12.7, "grip_mm"),
        ("stub_spot_dia_mm", 9.5, "under the 23/64"),
        ("pin_spot_dia_mm", 0.95, "under the #65"),
        ("stub_drill_tip_mm", -27.0, "stub_drill_tip_mm"),
        ("stub_ream_tip_mm", -25.0, "stub_ream_tip_mm"),
        ("drill_past_mm", 3.0, "stub_drill_tip_mm"),
        ("pin_drill_tip_mm", -5.5, "pin_drill_tip_mm"),
        # The reamer's end short of the .190 floor of the depth band, or past
        # its .210 top.
        ("pin_ream_tip_mm", -4.8, "depth band"),
        ("pin_ream_tip_mm", -5.4, "depth band"),
        # The #65 ending only .010 under the reamer's end.
        ("pin_drill_full_mm", 5.461, "below the reamer's end"),
        ("vise_jaw_width_mm", 152.4, "overhang_mm"),
        # The 1.000 in air lift review r2 caught: the 23/64 still cuts face F.
        ("prove_raise_mm", 25.4, "air prove-out"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("cut", "dia"),
    [
        ("stub drill", 9.0),
        ("stub ream", 9.525),
        ("pin drill", 0.9),
        ("pin ream", 0.9525),
    ],
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


def test_a_stub_hole_off_its_model_station_is_refused() -> None:
    features = copy.deepcopy(FEATURES)
    features["features"]["stub_hole"]["at"][1] -= 0.1
    with pytest.raises(ValueError, match="not its model position"):
        RECIPE.context(features, PLAN, SHOP, "cam.step")


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
        # The stub reamed on the register axis, not at the throw.
        ("stub_ream", "G0 X-8.641 Y0.000", "G0 X0.000 Y0.000", "holes"),
        # The clock pin's #65 mirrored to the moving-jaw side.
        ("pin_drill", "G0 X23.485 Y1.788", "G0 X23.485 Y-1.788", "holes"),
        # The 23/64 stopped inside the disc: the stub hole not through.
        ("stub_drill", "G1 Z-29.142 F{feed}", "G1 Z-20.000 F{feed}", "holes"),
        # The .0365 reamer short of the .190 floor.
        ("pin_ream", "G1 Z-5.207 F{feed}", "G1 Z-4.000 F{feed}", "holes"),
        # The .3740 reamer rapided out of the finished hole instead of fed out.
        ("stub_ream", "G1 Z1.000 F{feed}", "G0 Z1.000", "feed_out"),
        # A rapid across to the pin hole below face F.
        ("pin_spot", "G0 Z5.000", "G0 Z-1.000", "rapid"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

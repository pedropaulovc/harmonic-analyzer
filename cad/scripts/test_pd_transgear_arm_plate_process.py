"""The transgear arm plate's CAM recipe agrees with its model, plan and shop.

``cad/process/pd_transgear_arm_plate/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
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

STEM = "pd_transgear_arm_plate"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
STOCK = tomllib.loads(
    (
        _process_plans.CAD_ROOT / "config" / "shop-equipment" / "stock-bought.toml"
    ).read_text(encoding="utf-8")
)["stock"]


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "plate.step")


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
        for group in groups:
            job = sections[group[0]]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for key in group:
                text += [
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines_of[key]
                ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em": 1,
        "spot": 2,
        "drill-1": 3,
        "drill-27-64": 4,
        "reamer": 5,
        "sink": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    holes = {
        program: kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    # K at the origin; the screw holes 1.2098 along -X, .4281 and .1624 to
    # either side of the length's centre line (model X -10.875 and 4.125).
    assert holes["AP01_holes@2"] == [[0.0, 0.0], [-30.728, -10.875], [-30.728, 4.125]]
    assert holes["AP02_sink@0"] == [[-30.728, -10.875], [-30.728, 4.125]]


def test_the_frames_put_k_and_a_screw_hole_where_the_programs_cut_them(ctx) -> None:
    for name, z in (("bond", 5.0038),):
        frame = ctx["frames"][name]
        x, y, zz = (
            sum(a * b for a, b in zip(axis, [-10.875, 30.7277, 5.0038]))
            for axis in frame["axes"]
        )
        assert round(x, 3) == -30.728 and round(zz, 4) == z
        assert round(y, 3) == -10.875


def test_the_spoil_block_is_the_owned_bars_section() -> None:
    p = PLAN["parameters"]
    width, height = STOCK["6061-flat-1x3"]["section_mm"]
    assert (p["spoil_width_mm"], p["spoil_height_mm"]) == (width, height)


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("thickness_target_mm", 5.08, "thickness_target_mm"),
        ("x_set_mm", 15.0, "x_set_mm"),
        ("y_set_mm", 19.05, "y_set_mm"),
        ("drill_2764_tip_mm", -3.0, "drill_2764_tip_mm"),
        ("sink_tip_mm", 0.2, "sink_tip_mm"),
        ("outline_level_mm", 0.6, "outline_level_mm"),
        ("rough_arc_radius_mm", 19.0, "corner clearing"),
        ("chamfer_pin_depth_max_mm", 0.5, "chamfer_pin_depth_max_mm"),
        ("bond_area_mm2", 1800.0, "bond_area_mm2"),
        ("side_over_plug_min_mm", 24.0, "side_over_plug_min_mm"),
        ("screw_1_from_k_max_mm", 33.0, "screw_1_from_k_max_mm"),
        ("sink_pin_depth_mid_mm", 0.95, "sink_pin_depth_mid_mm"),
        ("em_feed_per_min_mm", 600.0, "em_feed_per_min_mm"),
        ("drill_past_mm", 0.3, "drill_past_mm"),
        ("ream_past_mm", 0.3, "ream_past_mm"),
        ("k_drill_past_mm", 1.8, "k_drill_past_mm"),
        ("blank_width_max_mm", 38.5, "front edge outside its band"),
        ("spot_dia_mm", 6.0, "spot"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_an_outline_bottom_inside_the_tape_stack_is_refused() -> None:
    # .012 under face A: through the thinnest stack, not the thickest.
    plan = copy.deepcopy(PLAN)
    p = plan["parameters"]
    p["outline_bottom_mm"] = -0.3
    p["outline_level_mm"] = (p["thickness_target_mm"] + 0.3) / p["outline_levels"]
    with pytest.raises(ValueError, match="through the tape stack"):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The end round run climb (G2): against the outline's way.
        (
            "outline",
            lambda line: line.startswith("G3"),
            lambda line: "G2" + line[2:],
            "outline",
        ),
        # A taper's pass .010 inside its offset: the plate gouged.
        (
            "outline",
            lambda line: line.startswith("G1 X") and "Y" in line,
            lambda line: line.replace(
                line.split()[1], f"X{float(line.split()[1][1:]) - 0.254:.3f}"
            ),
            "outline",
        ),
        # The finishing face level left .010 high: the plate comes out thick.
        (
            "face",
            lambda line: line == "G1 Z5.004 F{feed}",
            lambda line: "G1 Z5.258 F{feed}",
            "face",
        ),
        # The reamer rapided out of K.
        (
            "press_ream",
            lambda line: line.startswith("G1 Z6.004"),
            lambda line: "G0 Z6.004",
            "feed_out",
        ),
        # The #1 stopped short of face A.
        (
            "screw_drill",
            lambda line: line.startswith("G1 Z-2.240"),
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # A countersink plunged off its hole.
        (
            "screw_sink",
            lambda line: line.startswith("G0 X-30.728 Y-10.875"),
            lambda line: "G0 X-30.000 Y-10.875",
            "holes",
        ),
        # The corner clearing dropped at its last level: the corners stand.
        (
            "corner_clear",
            lambda line: line == "G1 Z-0.508 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "cleared",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

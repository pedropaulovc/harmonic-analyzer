"""The pinion return leaf spring's CAM recipe agrees with its model and plan.

``cad/process/dt_pinion_spring/cam.py`` writes the #30 hole's path itself
and recomputes every forming number the traveler prints; its ``context``
runs here on the drawing's requirement manifest (the features the spring's
export binds) with no FreeCAD and no SolidWorks, and refuses any plan number
that disagrees with the model, the shop or the holding. The posted program
is stood in for by the recipe's own lines under the grbl post's tool-change
block, so every check the recipe declares runs on it, and seeded faults show
each check catches what it guards.
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
import dt_pinion_spring_geometry as geometry
import export_features

STEM = "dt_pinion_spring"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "spring.step")


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
            key = group[0] if isinstance(group, tuple) else group
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
                *(line.format(feed=f"{job['feed']:.3f}") for line in lines_of[key]),
            ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tool(ctx) -> None:
    assert ctx["numbers"] == {"drill-30": 1}
    assert ctx["manual"] == {}
    job = ctx["jobs"][0]
    # The shop setting: 600 rpm, .0005 in per lip, two lips.
    assert (job["rpm"], round(job["feed"], 3)) == (600.0, 15.24)


def test_the_recipes_program_passes_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_strength_inputs_are_the_designs() -> None:
    p = PLAN["parameters"]
    assert p["strip_modulus_mpa"] == geometry.MODULUS_MPA
    assert p["strip_yield_min_mpa"] == geometry.YIELD_MPA


def test_the_shank_forms_both_bends_inside_their_bands(ctx) -> None:
    low, high = ctx["forming"]["formed"]
    for name in ("bend", "kink"):
        band = FEATURES["features"][name]["radius"]
        assert band[0] < low < high < band[1]
    # The radius reaches the bands' top only at a yield well over the minimum.
    assert ctx["forming"]["yield_limit"] > 1.5 * geometry.YIELD_MPA


def test_the_marks_rebuild_the_free_form() -> None:
    """The kink's and the foot's marks, set at the jaw tops, put each bend's
    clamped-side tangent where the free form has it."""
    p = PLAN["parameters"]
    half = geometry.THICK / 2
    formed = p["formed_radius_nominal_mm"]
    depth = p["shank_below_jaw_mm"]
    developed = FEATURES["features"]["strip"]["developed_length"]
    # Kink: the tip end clamped, the pinch at the kink's exit, the flat
    # below it.
    exit_from_end = p["kink_mark_from_end_in"] * 25.4 + depth
    assert math.isclose(developed - exit_from_end, geometry.FLAT_LEN, abs_tol=0.02)
    # Foot: the blade clamped, the pinch the bend's arc past the foot's tangent.
    arc = (formed + half) * math.radians(FEATURES["features"]["bend"]["angle"])
    tangent = p["foot_mark_from_end_in"] * 25.4 + depth - arc
    assert math.isclose(tangent, geometry.FOOT_LEN, abs_tol=0.02)


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("formed_radius_max_mm", 3.30, "formed_radius_max_mm"),
        ("strip_yield_limit_mpa", 1800.0, "strip_yield_limit_mpa"),
        ("bend_on_shank_deg", 90.0, "bend_on_shank_deg"),
        ("kink_on_shank_deg", 25.0, "kink_on_shank_deg"),
        ("kink_protractor_deg", 65.0, "kink_protractor_deg"),
        ("shank_below_jaw_mm", 1.0, "shank_top_over_jaw_mm"),
        ("kink_mark_from_end_in", 1.930, "kink_mark_from_end_in"),
        ("foot_mark_from_end_in", 0.436, "foot_mark_from_end_in"),
        ("tip_from_end_max_in", 2.070, "tip_from_end_max_in"),
        ("end_reading_min_in", 0.234, "end_reading_min_in"),
        ("wing_reading_max_in", 0.225, "wing_reading_max_in"),
        ("hole_pin_max_in", 0.133, "hole_pin_max_in"),
        ("jaw_top_over_plate_mm", 7.5, "jaw_top_over_plate_mm"),
        ("hole_tip_z_mm", -0.5, "hole_tip_z_mm"),
        ("hole_peck_mm", 3.5, "over one #30 diameter"),
        ("drill_30_projection_min_mm", 20.0, "drill_30_projection_min_mm"),
        ("cover_width_mm", 15.24, "as wide as the piece"),
        ("cover_top_max_mm", 21.0, "cover_top_max_mm"),
        ("hole_from_piece_end_mm", 4.0, "no pad end to file"),
        ("blank_length_in", 2.0, "shorter than the pad end"),
        ("spoil_cut_max_mm", 1.0, "spoil_cut_max_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_mandrel_outside_the_bends_bands_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["drill-2"]["diameter_mm"] = 4.0
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["shank_dia_mm"] = 4.0
    with pytest.raises(ValueError, match="outside the bends'"):
        RECIPE.context(FEATURES, plan, shop, "spring.step")


def _seed(ctx: dict, old: str, new: str) -> dict:
    """``ctx`` with the hole's line ``old`` replaced."""
    seeded = copy.deepcopy(ctx)
    lines = seeded["jobs"][0]["ops"][0][2]
    assert old in lines, old
    lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("old", "new", "check"),
    [
        # The #30 stopped above the strip's underside: no hole through.
        ("G1 Z-1.231 F{feed}", "G1 Z0.000 F{feed}", "holes"),
        # A peck re-entry rapided past the depth already drilled.
        ("G0 Z2.118", "G0 Z1.000", "rapid"),
        # The hole moved over the fixed jaw.
        ("G0 X13.970 Y-13.970", "G0 X13.970 Y0.500", "keep_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, old, new, check
) -> None:
    seeded = _seed(ctx, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

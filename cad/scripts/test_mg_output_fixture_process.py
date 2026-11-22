"""The output fixture's CAM recipe agrees with its model and plan.

``cad/process/mg_output_fixture/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the fixture's export binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
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

STEM = "mg_output_fixture"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN, features: dict = FEATURES) -> dict:
    return RECIPE.context(features, plan, SHOP, "fixture.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """The program as the runtime posts it: the grbl preamble, then per
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
    assert ctx["numbers"] == {"spot": 1, "drill-f": 2}
    assert RECIPE.LOAD_FIRST_TOOL == ("MO01_cross_bore",)
    assert ctx["manual"] == {}


def test_the_recipes_program_passes_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {"MO01_cross_bore"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("cross_grip_mm", 19.0, "cross_grip_mm"),
        ("cross_jaw_top_mm", 9.0, "cross_jaw_top_mm"),
        ("cross_tip_height_mm", -3.0, "cross_tip_height_mm"),
        ("part_length_mm", 18.0, "part_length_mm"),
        ("cross_parallel_start_mm", 14.0, "under the bore"),
        ("jaw_side_from_face_mm", 6.0, "edge finder"),
        ("corner_spot_dia_mm", 5.0, "not between the pilot"),
        ("bar_length_min_mm", 30.0, "too short"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("feature", "field", "value", "detail"),
    [
        # The bore entering off the top corner.
        ("rod_bore", "at", "off-corner", "enter at a corner"),
        # The bore's band moved past where the model puts it.
        ("rod_bore", "face_station", [13.0, 13.5], "outside"),
        # The hex turned so its flats, not corners, face ±Y.
        ("hex", "corner", [0.0, 0.0, 1.0], "corners on ±Y"),
    ],
)
def test_a_model_the_holding_does_not_fit_is_refused(
    feature, field, value, detail
) -> None:
    features = copy.deepcopy(FEATURES)
    target = features["features"][feature]
    if value == "off-corner":
        target["at"] = [target["at"][0], target["at"][1] + 1.0, target["at"][2]]
    else:
        target[field] = value
    with pytest.raises(ValueError, match=detail):
        _context(features=features)


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
        # The F drill stopped short of the lower corner: no bore through.
        ("cross_drill", "G1 Z-15.793 F{feed}", "G1 Z-12.000 F{feed}", "holes"),
        # The spot sunk past the F drill's diameter.
        ("corner_spot", "G1 Z-4.225 F{feed}", "G1 Z-6.000 F{feed}", "holes"),
        # The F drill moved off the axis, into the fixed jaw's side.
        ("cross_drill", "G0 X12.446 Y0.000", "G0 X12.446 Y6.000", "keep_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

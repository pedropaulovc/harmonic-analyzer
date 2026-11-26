"""The wheel bar's CAM recipe agrees with its model and plan.

``cad/process/mg_wheel_bar/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the ``flat_bar`` adapter binds) with no FreeCAD, no SolidWorks and no
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

STEM = "mg_wheel_bar"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "bar.step")


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
        for key in (
            group[0] if isinstance(group, tuple) else group for group in groups
        ):
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


def test_context_numbers_the_tools_and_drills_every_hole_from_the_milled_left_end(
    ctx,
) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-17": 3,
        "drill-15": 4,
        "drill-9": 5,
        "reamer-1865": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    f = FEATURES["features"]
    left_x, top_y = f["left_end"]["plane"]["value"], f["top_face"]["plane"]["value"]

    def centres(program: str) -> list:
        return next(
            kwargs["centres"]
            for name, check, kwargs in ctx["expect"]
            if name == program and check == "holes"
        )

    def model(*names: str) -> list:
        return [
            [round(f[n]["at"][0] - left_x, 3), round(f[n]["at"][1] - top_y, 3)]
            for n in names
        ]

    # X from the milled left end, Y down from T at the fixed jaw.
    assert centres("WB03_left@2") == model("axle_bore")
    assert centres("WB03_left@3") == model("hanger_hole")
    assert centres("WB03_left@4") == model("axle_bore")
    assert centres("WB04_right@2") == model("clamp_hole_1", "clamp_hole_2")


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("length_target_mm", 233.0, "length_target_mm"),
        ("height_target_mm", 11.0, "height_target_mm"),
        ("blank_length_min_mm", 230.0, "blank_length_min_mm"),
        ("right_end_station_mm", 235.0, "right_end_station_mm"),
        ("end_axial_doc_mm", 9.0, "end_axial_doc_mm"),
        ("drill_17_tip_mm", -1.0, "drill_17_tip_mm"),
        ("ream_tip_mm", -1.0, "ream_tip_mm"),
        ("spot_dia_mm", 4.5, "under every drill"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("left_clamp_end_mm", 170.0, "left_clamp_end_mm"),
        ("pickup_reach_min_mm", 70.0, "pickup_reach_min_mm"),
        ("z_touch_right_x_mm", 150.0, "z_touch_right_x_mm"),
        ("parallel_thickness_mm", 8.0, "reaches the stacks"),
        ("half_mill_projection_mm", 12.0, "collet would reach"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, changes: dict[str, str]) -> dict:
    """``ctx`` with the first line of operation ``key`` equal to each key of
    ``changes`` replaced by its value."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    for old, new in changes.items():
        lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "changes", "check"),
    [
        # The first face pass moved onto the bar's middle: a full-width slot.
        ("top_face", {"G0 X-10.414 Y1.338": "G0 X-10.414 Y-4.763"}, "face"),
        # The left end's first pass moved onto the second: it takes two steps.
        ("left_end", {"G0 X-7.493 Y8.890": "G0 X-7.112 Y8.890"}, "passes"),
        # The right end's first pass run the other way: climb, not conventional.
        (
            "right_end",
            {
                "G0 X243.191 Y-30.226": "G0 X243.191 Y8.890",
                "G1 Y8.890 F{feed}": "G1 Y-30.226 F{feed}",
            },
            "engagement",
        ),
        # The axle bore drilled short of its exit.
        ("axle_drill", {"G1 Z-2.320 F{feed}": "G1 Z0.500 F{feed}"}, "holes"),
        # The reamer rapided out of the bore.
        ("axle_ream", {"G1 Z10.627 F{feed}": "G0 Z10.627"}, "feed_out"),
        # A clamp hole drilled over the stacks at the moving jaw.
        ("clamp_drill", {"G0 X187.499 Y-5.000": "G0 X187.499 Y-18.000"}, "keep_out"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, changes, check
) -> None:
    seeded = _seed(ctx, key, changes)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

"""The pinion pivot block's CAM recipe agrees with its model and plan.

``cad/process/dt_pinion_pivot_block/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``drilled_block`` adapter binds) with no FreeCAD and no SolidWorks, and
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

STEM = "dt_pinion_pivot_block"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "block.step")


@pytest.fixture(scope="module")
def context() -> dict:
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


def _centres(ctx: dict, prefix: str) -> list:
    return next(
        kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if program.startswith(prefix) and check == "holes"
    )


def test_context_numbers_the_tools_and_places_the_holes_from_the_model(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-9": 3,
        "drill-c": 4,
        "drill-f": 5,
        "reamer": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    f = FEATURES["features"]
    # PB05: X from B, Y back from the west end at the fixed jaw.
    bottom, west = f["bottom_face"]["plane"]["value"], f["west_end"]["plane"]["value"]
    assert _centres(context, "PB05") == [
        [round(f[h]["at"][1] - bottom, 3), round(west - f[h]["at"][0], 3)]
        for h in ("pivot_bore", "lift_bore")
    ]
    # PB02: X from the back face, Y back from the east bar edge, east_skim_mm
    # beyond the east end.
    east_edge = f["east_end"]["plane"]["value"] + PLAN["parameters"]["east_skim_mm"]
    assert _centres(context, "PB02") == [
        [round(f[h]["at"][2], 3), round(f[h]["at"][0] - east_edge, 3)]
        for h in ("west_hold_down", "east_hold_down")
    ]


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("edge_top_max_mm", 27.0, "edge_top_max_mm"),
        ("upright_top_max_mm", 54.0, "upright_top_max_mm"),
        ("blank_length_min_in", 1.0, "shortest blank"),
        ("blank_width_min_in", 1.65, "narrowest bar"),
        ("hold_tip_height_mm", -2.0, "hold_tip_height_mm"),
        ("bore_tip_height_mm", -2.5, "bore_tip_height_mm"),
        ("lift_tip_height_mm", -2.5, "lift_tip_height_mm"),
        ("ream_tip_height_mm", -3.0, "reamer tip"),
        ("spot_dia_mm", 4.9, "between the pilot"),
        ("east_skim_mm", 1.27, "upright_top_max_mm"),
        ("hold_east_y_mm", -7.0, "hold_east_y_mm"),
        ("edge_grip_mm", 20.0, "edge_grip_mm"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick``
    accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The first front-face pass moved onto the block's middle: a full-width slot.
        (
            "front_face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-20.000",
            "face",
        ),
        # A hold-down drilled short of its exit through B.
        (
            "hold_drill",
            lambda line: line == "G1 Z-2.496 F{feed}",
            lambda line: "G1 Z-1.000 F{feed}",
            "holes",
        ),
        # A hold-down peck re-entry rapided past the depth already drilled.
        (
            "hold_drill",
            lambda line: line == "G0 Z21.074",
            lambda line: "G0 Z15.000",
            "rapid",
        ),
        # The pivot bore's C drill stopped above the back face.
        (
            "bore_drill",
            lambda line: line == "G1 Z-2.847 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # The lift bore's F drill stopped above the back face.
        (
            "lift_drill",
            lambda line: line == "G1 Z-2.961 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # The reamer rapided out of a bore.
        (
            "bore_ream",
            lambda line: line == "G1 Z12.176 F{feed}",
            lambda line: "G0 Z12.176",
            "feed_out",
        ),
        # The west end faced with the cutter plunging into the jaws' parallels.
        (
            "west_end",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z-1.000 F{feed}",
            "keep_out",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(context, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

"""The connecting rod's CAM recipe agrees with its model and plan.

``cad/process/ch_connecting_rod/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
them, and seeded faults show each check catches what it guards.
"""

from __future__ import annotations

import copy
import re
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "ch_connecting_rod"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "rod.step")


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
        keys = [group[0] if isinstance(group, tuple) else group for group in groups]
        for index, key in enumerate(keys):
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            if index or name in RECIPE.LOAD_FIRST_TOOL:
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                    f"M6 T{number}",
                ]
            text += [
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


def _lines(ctx: dict, key: str) -> list[str]:
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def test_context_numbers_the_tools_and_places_the_cuts(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "em-eighth": 2,
        "spot": 3,
        "drill-49": 4,
        "reamer-0775": 5,
        "em-5-64": 6,
        "saw": 7,
    }
    holes = {
        program: (kwargs["centres"], kwargs["z_bottom"])
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    # The pin holes on the crowns' centres, a blank's width apart; the #49's
    # full diameter .5 mm and the reamer's 1.0 mm past face D.
    assert holes["CR07_pin@1"] == ([[181.866, -25.4], [181.866, -76.2]], -1.057)
    assert holes["CR07_pin@2"][1] == -1.0
    # Seven tabs per rod, each .060 thick on the shank's near face; the
    # outline in three levels.
    outline = next(
        kw for p, c, kw in ctx["expect"] if p == "CR08_outline@0" and c == "outline"
    )
    assert len(outline["tabs"]) == 14
    assert {(t["top"], t["floor"], t["thickness"]) for t in outline["tabs"]} == {
        (2.794, 1.27, 1.524)
    }
    assert outline["passes"] == [{"offset": 1.5875, "levels": [3.387, 2.201, 1.016]}]
    # The saw's two heights, each one step into the crowns.
    saw = next(kw for p, c, kw in ctx["expect"] if c == "side_passes")
    assert (saw["final"], saw["raw"], saw["max_step"]) == (207.012, 221.744, 14.732)


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"fork_thickness_mm": 6.2}, "fork_thickness_mm"),
        ({"crown_x_mm": 186.0}, "crown_x_mm"),
        ({"slot_floor_x_mm": 171.0}, "slot_floor_x_mm"),
        ({"saw_collar_dia_max_mm": 40.0}, "saw_collar_dia_max_mm"),
        ({"tab_top_mm": 2.54}, "tab_top_mm"),
        ({"tab_station_7_mm": 162.5}, "tab_station_7_mm"),
        ({"outline_level_mm": 0.889}, "outline_level_mm"),
        ({"web_d_finish_mm": 3.302}, "web_d_finish_mm"),
        ({"slot_mid_x_mm": 172.087}, "slot_mid_x_mm"),
        ({"jaw_start_mm": 20.0}, "jaw_end_mm"),
        ({"ring_from_end_mm": 22.0}, "left end by its margin"),
        ({"spot_dia_mm": 2.0}, "under the #49"),
        ({"tab_top_3_x_mm": 142.0}, "off the shank's flanks"),
        ({"inside_corner_max_mm": 0.9}, "inside-corner ceiling"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(changes, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"].update(changes)
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


def _shift_y(line: str, by: float) -> str:
    y = float(re.search(r"Y(-?[\d.]+)", line).group(1))
    return re.sub(r"Y-?[\d.]+", f"Y{y + by:.3f}", line)


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # A tab cut through: the hop's lift left at the level below it.
        (
            "outline",
            lambda line: line == "G1 Z2.794 F{feed}",
            lambda line: "G1 Z2.201 F{feed}",
            "outline",
        ),
        # The first blank's shank band left .012 high at the rough floor.
        (
            "rough_2",
            lambda line: line == "G1 Z5.080 F{plunge}",
            lambda line: "G1 Z5.380 F{plunge}",
            "cleared",
        ),
        # The fork's face not skimmed.
        (
            "rough_2",
            lambda line: line == "G1 Z6.096 F{feed}",
            lambda line: "G1 Z6.350 F{feed}",
            "cleared",
        ),
        # The #49 stopped short of face D.
        (
            "pin_drill",
            lambda line: line == "G1 Z-1.057 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # The reamer rapided out of the hole.
        (
            "pin_ream",
            lambda line: line == "G1 Z7.096 F{feed}",
            lambda line: "G0 Z7.096",
            "feed_out",
        ),
        # The saw's first pass below the near tine's wall.
        (
            "slot",
            lambda line: line == "G1 Z1.702 F{feed}",
            lambda line: "G1 Z1.400 F{feed}",
            "depth",
        ),
        # A root pass run 0.3 mm into the shank's top flank.
        (
            "roots",
            lambda line: line.startswith("G1 X") and "Y" in line,
            lambda line: _shift_y(line, -0.3),
            "outline",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

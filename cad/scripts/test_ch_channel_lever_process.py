"""The channel lever's CAM recipe agrees with its model and plan.

``cad/process/ch_channel_lever/cam.py`` writes every path itself; its
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

STEM = "ch_channel_lever"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "lever.step")


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
        "drill-47": 4,
        "drill-21": 5,
        "drill-d": 6,
        "reamer-2560": 7,
        "em-5-64": 8,
    }
    holes = {
        program: (kwargs["centres"], kwargs["z_bottom"])
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    # The bores on the hubs' centres a blank's width apart; the pin and spring
    # holes 5.000 and 6.892 in along each lever's centre line from its bore.
    assert holes["CL03_bore@0"][0] == [
        [11.811, -12.7],
        [11.811, -38.1],
        [11.811, -63.5],
        [11.811, -88.9],
    ]
    assert [c[0] for c in holes["CL04_holes@1"][0]] == [138.811] * 4
    assert [c[0] for c in holes["CL04_holes@2"][0]] == [186.861] * 4
    # The reamer 1.0 mm into the spoil plate, the D drill's full diameter .5 mm.
    assert holes["CL03_bore@2"][1] == -1.0
    assert holes["CL03_bore@1"][1] == -2.377
    # Seven tabs per lever, each .050 thick on the plate's near face.
    outline = next(
        kw for p, c, kw in ctx["expect"] if p == "CL06_outline@0" and c == "outline"
    )
    assert len(outline["tabs"]) == 28
    assert {(t["top"], t["floor"], t["thickness"]) for t in outline["tabs"]} == {
        (3.5814, 2.3114, 1.27)
    }


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"hub_thickness_mm": 7.62}, "hub_thickness_mm"),
        ({"pocket_b_floor_mm": 5.4}, "pocket_b_floor_mm"),
        ({"pocket_arc_deg": 30.0}, "pocket_arc_deg"),
        ({"tab_top_mm": 3.0734}, "tab_top_mm"),
        ({"tab_station_7_mm": 178.811}, "tab_station_7_mm"),
        ({"jaw_start_mm": 20.0}, "jaw_start_mm"),
        ({"hub_from_end_mm": 8.0}, "end margins"),
        ({"spot_dia_mm": 2.0}, "under the #47"),
        ({"ring_half_angle_deg": 50}, "short of the bar-to-hub roots"),
        ({"ring_outer_radius_mm": 8.5}, "reach the slot arc"),
        ({"tab_bottom_2_x_mm": 140}, "taper's corner"),
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


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # A tab cut through: the hop's lift left at the level below it.
        (
            "outline",
            lambda line: line == "G1 Z3.581 F{feed}",
            lambda line: "G1 Z3.358 F{feed}",
            "outline",
        ),
        # A tab cut thin: the hop too low.
        (
            "outline",
            lambda line: line == "G1 Z3.581 F{feed}",
            lambda line: "G1 Z3.400 F{feed}",
            "outline",
        ),
        # The first blank's pocket floor left .012 high: the plate thick.
        (
            "pocket_b",
            lambda line: line == "G1 Z5.321 F{feed}",
            lambda line: "G1 Z5.621 F{feed}",
            "cleared",
        ),
        # A face row skipped: a strip of B left standing.
        (
            "face_b",
            lambda line: line.startswith("G1 Y-85.795"),
            lambda line: "G1 Y-78.527 F{feed}",
            "face",
        ),
        # The D drill stopped short of the plate.
        (
            "bore_drill",
            lambda line: line == "G1 Z-2.377 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # The reamer rapided out of the bore.
        (
            "bore_ream",
            lambda line: line == "G1 Z8.633 F{feed}",
            lambda line: "G0 Z8.633",
            "feed_out",
        ),
        # A root pass run 0.3 mm into the bar's edge.
        (
            "roots",
            lambda line: line == "G1 X15.820 Y-7.009 F{feed}",
            lambda line: "G1 X15.820 Y-7.309 F{feed}",
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

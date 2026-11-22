"""The cone swing platform's CAM recipe agrees with its model and plan.

``cad/process/dt_cone_swing_platform/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block (a tap stop's own lines as it posts them), so
every check the recipe declares runs on them, and seeded faults show each
check catches what it guards.
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

STEM = "dt_cone_swing_platform"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "platform.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's M6 block and its own lines."""
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
            if key in ctx["manual"]:
                stop = ctx["manual"][key]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{stop['tool']} {stop['label']}, {stop['setting']}",
                    f"M6 T{stop['tool']}",
                    *stop["gcode"],
                ]
                continue
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
        if not all(key in ctx["manual"] for key in keys):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _lines(ctx: dict, key: str) -> list[str]:
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def test_context_numbers_the_tools_and_places_the_holes(ctx) -> None:
    assert ctx["numbers"] == {
        "em-quarter": 1,
        "em-eighth": 2,
        "spot": 3,
        "drill-31": 4,
        "drill-b": 5,
        "reamer": 6,
        "drill-7": 7,
        "drill-l": 8,
        "drill-25": 9,
        "drill-43": 10,
        "tap-guide": 11,
    }
    holes = {
        program: (kwargs["centres"], kwargs["z_bottom"])
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    # Setup 2: the pivot 236.997 from the sawn south end and 16.225 (E to the
    # pivot, square to E) from the fixed jaw; the B drill into air.
    assert holes["PL01_holes@4"] == ([(236.997, -16.225)], -8.793)
    # Setup 4: the B drill on 2.0 into the plate under the bore, the reamer
    # 1.5 in; G54 on the pivot.
    assert holes["PL05_seat_drills@0"] == ([(0.0, 0.0)], -3.816)
    assert holes["PL05_seat_drills@1"] == ([(0.0, 0.0)], -1.5)
    outline = next(
        kw for p, c, kw in ctx["expect"] if p == "PL08_outline" and c == "outline"
    )
    assert [p["offset"] for p in outline["passes"]] == [3.429, 3.175]
    assert [len(p["levels"]) for p in outline["passes"]] == [8, 2]


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"faced_length_mm": 244.0}, "faced_length_mm"),
        ({"s2_overhang_min_mm": 30.0}, "south hole reaches the jaws"),
        ({"s2_overhang_max_mm": 60.0}, "north hole reaches the jaws"),
        ({"wedge_y_mm": 20.0}, "swath"),
        ({"clear_offset_mm": 4.5}, "SE corner"),
        ({"holddown_seat_depth_mm": 9.0}, "seat's cone"),
        ({"tap_4_40_turns": 12, "tap_4_40_depth_mm": 7.62}, "full threads"),
        ({"spot_dia_mm": 3.1}, "under every drill"),
        ({"drill_projection_min_mm": 15.0}, "nose reaches the jaw tops"),
        ({"ream_past_mm": 1.0}, "ream_tip_mm"),
        ({"outline_levels": 6}, "outline_level_mm"),
        ({"pivot_plate_x_mm": 300.0}, "pivot_plate_x_mm"),
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


def _shift_x(line: str, by: float) -> str:
    return re.sub(
        r"X(-?\d+\.\d+)", lambda m: f"X{float(m.group(1)) + by:.3f}", line, count=1
    )


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The NE round's rough arc ended 0.5 mm inside the part.
        (
            "outline",
            lambda line: line.startswith("G3 "),
            lambda line: _shift_x(line, -0.5),
            "outline",
        ),
        # The south end's last level stopped short of the bar's underside.
        (
            "ends",
            lambda line: line == "G1 Z-6.731 F{feed}",
            lambda line: "G1 Z-4.000 F{feed}",
            "cleared",
        ),
        # The counterbore's helix run .012 deep.
        (
            "holddown_cbore",
            lambda line: "Z-3.505" in line,
            lambda line: line.replace("Z-3.505", "Z-3.805"),
            "bounds",
        ),
        # The B drill stopped short of the plate under the bore.
        (
            "pivot_redrill",
            lambda line: line == "G1 Z-3.816 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # The reamer rapided out of the bore.
        (
            "pivot_ream",
            lambda line: line.startswith("G1 Z7.477"),
            lambda line: "G0 Z7.477",
            "feed_out",
        ),
        # The relief's round cut climb (G3).
        (
            "relief",
            lambda line: line.startswith("G2 "),
            lambda line: "G3" + line[2:],
            "bounds",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

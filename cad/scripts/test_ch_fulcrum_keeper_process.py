"""The fulcrum keeper's CAM recipe agrees with its model and plan.

``cad/process/ch_fulcrum_keeper/cam.py`` writes every path itself; its
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

STEM = "ch_fulcrum_keeper"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "keeper.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's lines after its M6, ending with its M30."""
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
        for key in keys:
            if key in ctx["manual"]:
                manual = ctx["manual"][key]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
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
        if not any(key in ctx["manual"] for key in keys):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-41": 3,
        "drill-d": 4,
        "drill-f": 5,
        "drill-1-16": 6,
        "em-eighth": 7,
        "tap-guide": 8,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # Every hole on the width's centre line, F at Y0: the foot hole from I,
    # the bore from the seat, the crown hole from I.
    centres = {
        program: kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    assert centres["FK03_seat@2"] == [[11.938, -6.985]]
    assert centres["FK04_crown_bore@3"] == [[-25.2, -6.985]]
    assert centres["FK06_crown_cbore@1"] == [[-4.064, -6.985]]
    stop = ctx["manual"]["crown_tap"]
    assert stop["tool"] == 8 and stop["at"] == [-4.064, -6.985]
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_frames_turn_back_to_the_keepers_axes(ctx) -> None:
    # The bracket-axes frames, back in the keeper's model axes, still put
    # the foot hole (model X 7.874, Y 7.874, Z 0) where FK03 drills it.
    frame = ctx["frames"]["seat"]
    d = [p - o for p, o in zip([7.874, 7.874, 0.0], frame["origin"])]
    x, y, _z = (sum(a * b for a, b in zip(axis, d)) for axis in frame["axes"])
    assert (round(x, 3), round(y, 3)) == (11.938, -6.985)


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("upright_top_max_mm", 35.0, "upright_top_max_mm"),
        ("blank_length_min_in", 1.27, "blank_length_min_mm"),
        ("hold_tip_height_mm", 24.0, "hold_tip_height_mm"),
        ("bore_drill_past_mm", 1.0, "bore_tip_height_mm"),
        ("apex_drill_past_mm", 0.0, "apex_tip_height_mm"),
        ("arch_rough_woc_mm", 4.5, "arch_rough_woc_mm"),
        ("arch_past_mm", 0.5, "arch_depth_mm"),
        ("step_level_mm", 1.27, "step_level_mm"),
        ("wall_finish_woc_mm", 0.2, "wall_finish_woc_mm"),
        # The faces' declared stepovers are the passes' true width.
        ("lying_stepover_mm", 3.4, "lying_stepover_mm"),
        ("seat_stepover_mm", 3.4, "seat_stepover_mm"),
        # The measured stick-out leaves the collet nose clear of the stock.
        ("half_mill_projection_mm", 10.0, "collet nose"),
        ("hold_spot_dia_mm", 2.6, "not under its drill"),
        ("apex_spot_dia_mm", 1.6, "under its drill"),
        ("tap_reach_min_mm", 7.0, "tap_reach_min_mm"),
        ("tap_stack_max_mm", 266.7, "tap_stack_max_mm"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("riser_height_mm", 30.0, "lying_grip_mm"),
        ("cbore_path_radius_mm", 0.4, "cbore_path_radius_mm"),
        ("cbore_depth_mm", 2.3, "cbore_depth_mm"),
        ("cbore_projection_min_mm", 25.0, "cbore_projection_min_mm"),
        ("long_reach_mm", 25.4, "the end mill reaches"),
        ("foot_hole_station_from_i_mm", 12.5, "foot_hole_station_from_i_mm"),
        # The setting's centre feed on the helix: 5.6x the chip load at the edge.
        ("cbore_feed_per_min_mm", 213.36, "cbore_feed_per_min_mm"),
        ("cbore_edge_feed_per_min_mm", 37.899, "cbore_edge_feed_per_min_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` (or of the tap stop)
    that ``pick`` accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The crown's finish turned conventional (G3): the climb outline is broken.
        (
            "crown",
            lambda line: line.startswith("G2 X-25.200 Y6.350"),
            lambda line: "G3" + line[2:],
            "outline",
        ),
        # The crown's finish radius .010 too large: off its offset.
        (
            "crown",
            lambda line: line.startswith("G2 X-38.535"),
            lambda line: line.replace("X-38.535", "X-38.789"),
            "outline",
        ),
        # The step's floor left .010 high: the lug comes out thick.
        (
            "step",
            lambda line: line == "G1 Z8.128 F{feed}",
            lambda line: "G1 Z8.382 F{feed}",
            "face",
        ),
        # The wall pass dropped: the foot top keeps its scallops.
        (
            "step",
            lambda line: line.startswith("G1 Y-22.860"),
            lambda line: "G1 Y8.890 F{feed}",
            "passes",
        ),
        # The F drill stopped short of the lug's outer face (fit audit
        # question 1: the bore is F-drilled, no reamer).
        (
            "bore_open",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z15.000 F{feed}",
            "holes",
        ),
        # The 1/16 stopped short of the bore.
        (
            "crown_drill",
            lambda line: line.startswith("G1 Z27.389"),
            lambda line: "G1 Z29.000 F{feed}",
            "holes",
        ),
        # The foot hole drilled off its station.
        (
            "foot_drill",
            lambda line: line.startswith("G0 X11.938"),
            lambda line: "G0 X12.446 Y-6.985",
            "holes",
        ),
        # The counterbore's circle .010 too large: off its band's middle.
        (
            "cbore",
            lambda line: line.startswith("G0 X-11.595"),
            lambda line: "G0 X-11.341 Y-6.985",
            "bounds",
        ),
        # The counterbore's last turn .010 deep: under its floor.
        (
            "cbore",
            lambda line: "Z5.766" in line,
            lambda line: line.replace("Z5.766", "Z5.512"),
            "depth",
        ),
        # The counterbore cut conventional (G2).
        (
            "cbore",
            lambda line: line.startswith("G3") and "Z" not in line,
            lambda line: "G2" + line[2:],
            "bounds",
        ),
        # The counterbore's cutter dropped onto the lug's side of the foot.
        (
            "cbore",
            lambda line: line.startswith("G0 X-11.595"),
            lambda line: "G0 X-9.000 Y-6.985",
            "keep_out",
        ),
        # The tap stop holds (M0) instead of ending Idle.
        (
            "crown_tap",
            lambda line: line == "M30",
            lambda line: "M0",
            "tap_stop",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


def _step_with(ctx: dict, change) -> dict:
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, "step")
    lines[:] = [change(line) for line in lines]
    return seeded


@pytest.mark.parametrize(
    ("change", "detail"),
    [
        # The last station back at the facing's Y-8.120, so no stepover sweeps
        # the wall's N end and the wall pass meets far more than the scallops.
        (lambda line: line.replace("Y-13.970", "Y-8.120"), "radial > 0.263"),
        # The wall pass run +Y, the wall on the cutter's left: conventional.
        (
            lambda line: {"G0 X14.224 Y8.890": "G0 X14.224 Y-22.860"}.get(
                line, "G1 Y8.890 F{feed}" if line.startswith("G1 Y-22.860") else line
            ),
            "cuts conventional, expected climb",
        ),
    ],
)
def test_the_wall_pass_meets_only_its_declared_scallops_climb(
    ctx, tmp_path, change, detail
) -> None:
    seeded = _step_with(ctx, change)
    _post(seeded, tmp_path)
    found = [f for f in _findings(seeded, tmp_path) if f.check == "engagement"]
    assert any(detail in f.detail for f in found), found

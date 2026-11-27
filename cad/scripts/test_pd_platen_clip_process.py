"""The platen clip's CAM recipe agrees with its model and plan.

``cad/process/pd_platen_clip/cam.py`` writes its one file's paths itself (the
holes, the two clips and the bow former's four die laminations); its
``context`` runs here on the drawing's requirement manifest with no FreeCAD
and no SolidWorks, and refuses any plan number that disagrees with the
model, the shop or the holding. The posted program is stood in for by the
recipe's own lines under the grbl post's tool-change block, so every check
the recipe declares runs on it, and seeded faults show each check catches
what it guards.
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

STEM = "pd_platen_clip"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "clip.step")


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
        for key in groups:
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


def _outline(ctx: dict) -> dict:
    return next(kwargs for _p, check, kwargs in ctx["expect"] if check == "outline")


def test_context_accepts_the_plan_and_cuts_every_piece(context) -> None:
    assert context["numbers"] == {"em-sixteenth": 1}
    assert RECIPE.LOAD_FIRST_TOOL == ("PC01_sheet",)
    names = {
        e["name"].split(" ", 2)[0] + " " + e["name"].split(" ", 2)[1]
        for e in _outline(context)["elements"]
    }
    assert names == {
        "clip 1",
        "clip 2",
        "lamination 1",
        "lamination 2",
        "lamination 3",
        "lamination 4",
    }
    # Every level is the same depth; the last stands the plan's tip height.
    levels = context["levels"]
    assert len(levels) == PLAN["parameters"]["level_count"]
    assert levels[-1] == pytest.approx(PLAN["parameters"]["sheet_tip_z_mm"], abs=1e-3)
    # The cutter fits the slit and the title block's inside corners.
    r = _outline(context)["passes"][0]["offset"]
    assert r <= PLAN["parameters"]["inside_corner_max_mm"]
    assert 2 * r < FEATURES["features"]["slits"]["width_nominal"]


def test_the_former_springs_back_inside_the_rise_band() -> None:
    p = PLAN["parameters"]
    lo, hi = FEATURES["features"]["bows"]["rise"]
    assert lo <= p["formed_rise_min_mm"] < p["formed_rise_max_mm"] <= hi
    # The die is bent tighter than the drawing's bow: the strip springs open.
    assert p["die_bow_rise_mm"] > FEATURES["features"]["bows"]["rise_nominal"]


def test_the_recipes_program_passes_every_check_it_declares(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {"PC01_sheet"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("blank_length_mm", 100.0, "blank_length_mm"),
        ("blank_right_margin_mm", 5.0, "blank_right_margin_mm"),
        ("blank_b_front_margin_mm", 3.0, "blank_b_front_margin_mm"),
        ("clip_spring_edge_y_mm", -3.0, "clip_spring_edge_y_mm"),
        ("part_left_x_mm", 1.0, "runs off the blank's end"),
        ("saw_error_mm", 4.0, "may run off the sawn end"),
        ("sheet_tip_z_mm", -0.3, "sheet_tip_into_plate_mm"),
        ("spoil_cut_max_mm", 0.05, "no deeper than spoil_cut_max_mm"),
        ("through_margin_min_mm", 0.4, "through_margin_min_mm below"),
        ("tape_stack_min_mm", 0.3, "over the tape stack"),
        ("tape_stack_max_mm", 0.25, "under the tape stack"),
        ("sheet_depth_mm", 0.9, "sheet_depth_mm"),
        ("level_count", 3, "level_count"),
        ("level_depth_max_fraction", 0.25, "level_count"),
        ("strip_thickness_min_mm", 0.82, "outside the strip's thickness band"),
        ("formed_rise_min_mm", 1.3, "formed_rise_min_mm"),
        ("die_bow_radius_mm", 30.0, "die_bow_radius_mm"),
        ("formed_rise_max_mm", 1.7, "formed_rise_max_mm"),
        ("lamination_flat_mm", 2.5, "lamination_body_min_mm"),
        ("lamination_count", 3, "die_stack_mm"),
        ("hole_dia_target_mm", 3.04, "hole_dia_target_mm"),
        ("clip_bond_area_mm2", 900.0, "clip_bond_area_mm2"),
        ("waste_b_bond_area_mm2", 1600.0, "waste_b_bond_area_mm2"),
        ("jaw_top_over_plate_mm", 6.0, "jaw_top_over_plate_mm"),
        ("em_projection_min_mm", 5.0, "collet would not clear"),
        ("inside_corner_max_mm", 0.3, "inside-corner"),
        ("sheet_cutter_dia_mm", 0.7874, "cutter_dia_mm"),
        ("plunge_feed_mm_min", 100.0, "plunge_feed_mm_min"),
        ("entry_overhang_mm", 1.0, "entry_overhang_mm"),
        ("collet_over_jaw_mm", 10.0, "collet_over_jaw_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_an_upcut_end_mill_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    tool = next(t for t in plan["tools"] if t["id"] == "em-sixteenth")
    del tool["axial_direction"]
    with pytest.raises(ValueError, match="downcut"):
        _context(plan)


def _seed(ctx: dict, pick, change) -> dict:
    """``ctx`` with the first line that ``pick`` accepts replaced by
    ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = seeded["jobs"][0]["ops"][0][2]
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


_LONG_EDGE = re.compile(r"G1 X(\d{2}\.\d{3}) Y(-\d+\.\d{3}) F\{feed\}")


def _long_edge(line: str) -> bool:
    """A clip's straight edge, well along the part."""
    match = _LONG_EDGE.fullmatch(line)
    return bool(match) and 20.0 < float(match.group(1)) < 70.0


def _nudge_y(line: str) -> str:
    match = _LONG_EDGE.fullmatch(line)
    y = float(match.group(2)) + 0.3
    return f"G1 X{match.group(1)} Y{y:.3f} F{{feed}}"


@pytest.mark.parametrize(
    ("pick", "change", "check"),
    [
        # A clip's edge cut .3 mm off its path.
        (_long_edge, _nudge_y, "outline"),
        # The last level taken deeper into the spoil plate.
        (
            lambda line: line.startswith("G1 Z-0.102"),
            lambda line: line.replace("Z-0.102", "Z-0.400"),
            "depth",
        ),
        # The feed in through the blank's margin rapided at cutting depth.
        (
            lambda line: line.startswith("G1 X3.277"),
            lambda line: line.replace("G1", "G0", 1).replace(" F{feed}", ""),
            "rapid",
        ),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    context, tmp_path, pick, change, check
) -> None:
    seeded = _seed(context, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

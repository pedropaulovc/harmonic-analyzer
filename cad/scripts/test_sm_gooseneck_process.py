"""The gooseneck's bend-form CAM recipe agrees with its model and plan.

``cad/process/sm_gooseneck/cam.py`` writes the bend form's two plates'
paths itself; its ``context`` runs here on the drawing's requirement manifest
with no FreeCAD and no SolidWorks, and refuses any plan number that disagrees
with the model, the shop or the holding: the groove against the tube's O.D.
band, the ball's reach, the wrap the form allows against the bend's angle
band and the springback allowance, the ovality limit and the saw lines. The
posted programs are stood in for by the recipe's own lines under the grbl
post's tool-change blocks, so every check the recipe declares runs on them,
and seeded faults show each check catches what it guards.
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
import export_features

STEM = "sm_gooseneck"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "gooseneck.step")


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
        for keys in groups:
            job = sections[keys[0]]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for key in keys:
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


def test_context_numbers_the_tools_and_mirrors_plate_b(context) -> None:
    assert context["numbers"] == {"em-half": 1, "ball": 2}
    assert RECIPE.LOAD_FIRST_TOOL == ("GF01_form_a", "GF02_form_b")
    a, b = context["frames"]["a"], context["frames"]["b"]
    assert a["x"] == pytest.approx([-v for v in reversed(b["x"])])
    assert a["y"] == b["y"]


def test_the_groove_fits_the_tube_and_the_form_wraps_past_the_springback() -> None:
    p = PLAN["parameters"]
    bend, blank = FEATURES["features"]["bend"], FEATURES["features"]["blank"]
    od_min, od_max = blank["od"]
    # The largest tube sits in the groove; the least is snug.
    assert od_max / 2 <= p["groove_radius_mm"] <= od_min / 2 + p["groove_snug_max_mm"]
    # The ball cuts the whole groove radius within its flutes.
    ball = SHOP["tools"]["ball-endmill-carbide-2fl-1-4"]
    assert ball["diameter_mm"] / 2 < p["groove_radius_mm"] <= ball["flute_length_mm"]
    # The form takes the bend's widest angle plus the springback allowance,
    # and its cove runs on past that departure to the back edge.
    assert p["wrap_max_deg"] >= bend["angle"][1] + p["springback_max_deg"]
    clear = math.degrees(
        math.acos(1 - p["groove_radius_mm"] / bend["centreline_radius"])
    )
    assert p["back_edge_angle_deg"] >= p["wrap_max_deg"] - 90 + clear


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {"GF01_form_a", "GF02_form_b"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("groove_radius_mm", 6.3, "largest O.D."),
        ("groove_radius_mm", 7.0, "groove_snug_max_mm"),
        ("springback_max_deg", 10.0, "wrap_max_deg"),
        ("wrap_max_deg", 120.0, "back_edge_angle_deg"),
        ("back_edge_angle_deg", 30.0, "back_edge_angle_deg"),
        ("form_back_y_mm", 45.5, "form_back_y_mm"),
        ("tube_tail_mm", 40.0, "tube_stop_x_mm"),
        ("stop_to_end_mm", 20.0, "arc_from_end_mm"),
        ("cutter_tip_below_mm", 3.5, "flutes"),
        ("groove_step_deg", 7.0, "divide 180"),
        ("stud_hole_x_mm", 60.0, "too near the groove"),
        ("clamp_waste_from_end_mm", 180.0, "waste's clamp"),
        ("ovality_fraction_max", 0.03, "ovality_max_mm"),
        ("arm_line_mm", 94.0, "arm_line_mm"),
        ("foot_line_mm", 500.0, "foot_line_mm"),
        ("x_set_b_mm", 115.0, "x_set_b_mm"),
        ("b_hole_station_mm", 157.97, "b_hole_station_mm"),
        ("tool_y_span_mm", 170.0, "tool_y_span_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, op: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``op`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(o[2] for job in seeded["jobs"] for o in job["ops"] if o[0] == op)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("op", "pick", "change", "check"),
    [
        # The arc's last level stopped short of the plate's underside.
        (
            "outline_a",
            lambda line: "Z-13.843" in line,
            lambda line: line.replace("Z-13.843", "Z-12.000"),
            "cleared",
        ),
        # The ball's centred pass run high: the offset steps alone leave the
        # core round the groove's centre line at the plate top.
        (
            "groove_a",
            lambda line: line.startswith("G1 Z-3.175"),
            lambda line: "G1 Z-3.000 F{plunge}",
            "cleared",
        ),
        # The groove's deepest level run .5 mm off its centre line.
        (
            "groove_a",
            lambda line: line.startswith("G0 X-62.720 Y-76.200"),
            lambda line: line.replace("Y-76.200", "Y-75.700"),
            "cleared",
        ),
        # The ball's first move taken across the left clamp's strap.
        (
            "groove_a",
            lambda line: line.startswith("G0 X-62.720"),
            lambda line: "G0 X-90.000 Y-50.000",
            "keep_out",
        ),
        # A stud hole's rapid re-entry taken below the peck it reached.
        (
            "holes_b",
            lambda line: line.startswith("G0 Z-2.961"),
            lambda line: "G0 Z-5.000",
            "rapid",
        ),
        # A stud hole stopped a level short.
        (
            "holes_a",
            lambda line: line.startswith("G1 Z-13.843"),
            lambda line: "G1 Z-10.500 F{plunge}",
            "holes",
        ),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    context, tmp_path, op, pick, change, check
) -> None:
    seeded = _seed(context, op, pick, change)
    _post(seeded, tmp_path)
    found = _findings(seeded, tmp_path)
    assert any(check in f"{finding.check} {finding.detail}" for finding in found), found

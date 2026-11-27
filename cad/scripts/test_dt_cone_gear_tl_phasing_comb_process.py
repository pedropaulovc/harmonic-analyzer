"""The phasing comb's CAM recipe agrees with its model and plan.

``cad/process/dt_cone_gear_tl_phasing_comb/cam.py`` writes its one outline
path itself; its ``context`` runs here on the drawing's requirement manifest
with no FreeCAD and no SolidWorks, and refuses any plan number that disagrees
with the model, the shop or the holding. The posted program is stood in for
by the recipe's own lines under the grbl post's tool-change block, so every
check the recipe declares runs on it, and seeded faults show each check
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

STEM = "dt_cone_gear_tl_phasing_comb"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "comb.step")


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


def test_context_accepts_the_plan_and_rounds_every_inside_corner(context) -> None:
    assert context["numbers"] == {"em-sixteenth": 1}
    assert RECIPE.LOAD_FIRST_TOOL == ("CB01_outline",)
    outline = next(
        kwargs for _p, check, kwargs in context["expect"] if check == "outline"
    )
    # The staircase's inside corners are rounded by the cutter's radius, as
    # cut: the five the title block's R.040 MAX allows, none larger.
    corners = [e for e in outline["elements"] if e["name"].endswith(" corner")]
    assert len(corners) == len(RECIPE.BLADES) + 1
    r = outline["passes"][0]["offset"]
    for corner in corners:
        assert r <= PLAN["parameters"]["inside_corner_max_mm"]
        for end in ("start", "end"):
            assert (
                abs(
                    (
                        (corner[end][0] - corner["centre"][0]) ** 2
                        + (corner[end][1] - corner["centre"][1]) ** 2
                    )
                    ** 0.5
                    - r
                )
                < 1e-9
            )


def test_the_recipes_program_passes_every_check_it_declares(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {"CB01_outline"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("blank_length_mm", 100.0, "blank_length_mm"),
        ("blank_length_in", 4.0, "blank_length_in is short"),
        ("blank_margin_mm", 3.0, "blank_length_mm"),
        ("comb_back_y_mm", -19.0, "comb_back_y_mm"),
        ("blank_left_x_mm", 50.0, "comb_south_x_mm"),
        ("outline_tip_z_mm", -0.3, "outline_tip_into_plate_mm"),
        ("spoil_cut_max_mm", 0.05, "no deeper than spoil_cut_max_mm"),
        ("through_margin_min_mm", 0.4, "through_margin_min_mm below"),
        ("tape_stack_min_mm", 0.3, "over the tape stack"),
        ("tape_stack_max_mm", 0.25, "under the tape stack"),
        ("tape_stack_max_mm", 0.65, "first level on the thickest tape stack"),
        ("outline_depth_mm", 0.5, "outline_depth_mm"),
        ("comb_bond_area_mm2", 900.0, "comb_bond_area_mm2"),
        ("jaw_top_over_plate_mm", 6.0, "jaw_top_over_plate_mm"),
        ("em_sixteenth_projection_min_mm", 5.0, "collet would not clear"),
        ("inside_corner_max_mm", 0.3, "title block's"),
        ("outline_cutter_dia_mm", 0.7874, "cutter_dia_mm"),
        ("level_count", 3, "level_count"),
        ("level_depth_mm", 0.4, "level_depth_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, pick, change) -> dict:
    """``ctx`` with the first outline line that ``pick`` accepts replaced by
    ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(
        op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == "outline"
    )
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("pick", "change", "check"),
    [
        # The back edge cut .27 mm inside the comb.
        (
            lambda line: line.startswith("G1 X113.030 Y-43.967"),
            lambda line: line.replace("Y-43.967", "Y-43.700"),
            "outline",
        ),
        # The last level taken deeper into the spoil plate.
        (
            lambda line: line.startswith("G1 Z-0.102"),
            lambda line: line.replace("Z-0.102", "Z-0.400"),
            "depth",
        ),
        # The feed in through the margin rapided at cutting depth.
        (
            lambda line: line.startswith("G1 Y-43.967"),
            lambda line: "G0 Y-43.967",
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

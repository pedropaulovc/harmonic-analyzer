"""The latch hook's CAM recipe agrees with its model and plan.

``cad/process/pd_latch_hook/cam.py`` writes its three files' paths itself
(the flat hook and the trial strip from the sheet, the former's two die
halves from one length of 1/2 in bar, the base's two holes); its ``context``
runs here on the drawing's requirement manifest with no FreeCAD and no
SolidWorks, and refuses any plan number that disagrees with the model, the
shop or the holding. The posted programs are stood in for by the recipe's
own lines under the grbl post's tool-change block, so every check the recipe
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

STEM = "pd_latch_hook"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
P = PLAN["parameters"]
F = FEATURES["features"]


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "hook.step")


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


def _outline(ctx: dict, program: str) -> dict:
    return next(
        kwargs
        for name, check, kwargs in ctx["expect"]
        if name == program and check == "outline"
    )


def test_context_accepts_the_plan_and_cuts_every_piece(context) -> None:
    assert context["numbers"] == {"em-sixteenth": 1, "em-quarter": 2, "drill-30": 3}
    assert RECIPE.LOAD_FIRST_TOOL == ("HL01_sheet", "HL02_former", "HL03_holes")
    sheet = {
        e["name"].split(" ")[0] for e in _outline(context, "HL01_sheet")["elements"]
    }
    assert sheet == {"hook", "trial"}
    former = {
        e["name"].split(" ")[0] for e in _outline(context, "HL02_former")["elements"]
    }
    assert former == {"outer", "inner"}
    assert len(context["holes"]) == 2
    # Every level is the same depth; the last stands the plan's tip height.
    levels = context["levels"]
    assert len(levels["sheet"]) == P["sheet_level_count"]
    assert len(levels["former"]) == P["die_level_count"]
    assert levels["sheet"][-1] == pytest.approx(P["sheet_tip_z_mm"], abs=1e-3)
    assert levels["former"][-1] == pytest.approx(P["die_tip_z_mm"], abs=1e-3)
    # The 1/16 end mill fits the title block's inside corners.
    r = _outline(context, "HL01_sheet")["passes"][0]["offset"]
    assert r <= P["inside_corner_max_mm"]


def test_the_former_presses_the_drawing_at_its_design_point() -> None:
    # The design yield sits inside the window of yields at which the die
    # presses every printed formed value; the first caliper reading's band
    # spans that window and holds the design point's reading.
    assert (
        P["window_yield_min_mpa"]
        < P["former_design_yield_mpa"]
        < P["window_yield_max_mpa"]
    )
    assert P["strip_yield_min_mpa"] <= P["window_yield_min_mpa"]
    assert P["window_yield_max_mpa"] <= P["strip_yield_max_mpa"]
    assert (
        P["check_tip_x_min_mm"] <= P["relation_tip_x_yd_mm"] <= P["check_tip_x_max_mm"]
    )
    # Softer strip springs back less: the tab's far point stands further out.
    assert (
        P["relation_tip_x_yhi_mm"]
        < P["relation_tip_x_yd_mm"]
        < P["relation_tip_x_ylo_mm"]
    )
    # The dies are bent tighter than the drawing: the strip springs open.
    assert P["roll_die_radius_mm"] < F["roll"]["radius_nominal"]
    assert P["roll_die_deg"] > F["roll"]["angle"]
    assert P["tab_die_radius_mm"] < F["tab"]["radius_nominal"]
    # The trial strip's length reading is the hook's less the ear's width.
    width = F["side_edge"]["width_nominal"]
    assert P["check_trial_length_min_mm"] == pytest.approx(
        P["check_overall_min_mm"] - width, abs=1e-3
    )
    assert P["check_trial_length_max_mm"] == pytest.approx(
        P["check_overall_max_mm"] - width, abs=1e-3
    )


def test_every_yield_and_thickness_corner_keeps_the_tab_in_its_band() -> None:
    lo, hi = F["tab"]["radius"]
    assert lo <= P["corner_tab_r_min_mm"] <= P["corner_tab_r_max_mm"] <= hi
    lo, hi = F["ear_bend"]["radius"]
    assert lo <= P["ear_formed_radius_min_mm"] <= P["ear_formed_radius_max_mm"] <= hi


def test_the_die_blank_holds_both_halves_and_their_channel() -> None:
    # The channel takes one slot and at most two passes, with the place error
    # on each side.
    least = P["die_cutter_dia_mm"] + 2 * P["die_place_error_mm"]
    assert least <= P["die_gap_min_mm"] <= P["die_gap_max_mm"] <= 2 * least
    assert P["die_least_width_mm"] >= P["die_body_min_mm"]
    # Each half's tape holds the cutter's lift over its narrowest body.
    for key in ("outer_die_bond_area_mm2", "inner_die_bond_area_mm2"):
        assert P[key] >= P["die_least_width_mm"] ** 2
    assert P["die_y_span_mm"] <= P["plate_width_mm"] + P["die_blank_back_y_mm"]


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {"HL01_sheet", "HL02_former", "HL03_holes"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("blank_length_mm", 100.0, "blank_length_mm"),
        ("blank_front_margin_mm", 10.0, "blank_front_margin_mm"),
        ("hook_bond_area_mm2", 1000.0, "hook_bond_area_mm2"),
        ("trial_bond_area_mm2", 900.0, "trial_bond_area_mm2"),
        ("tape_stack_mm", 0.4, "tape stack is outside its band"),
        ("sheet_tip_z_mm", 0.1, "sheet_tip_into_plate_mm"),
        ("sheet_cutter_dia_mm", 0.7874, "1/16 end mill's diameter"),
        ("jaw_top_over_plate_mm", 6.0, "jaw_top_over_plate_mm"),
        ("em_sixteenth_projection_min_mm", 5.0, "collet would not clear"),
        ("part_gap_mm", 0.5, "part_gap_mm"),
        ("former_design_yield_mpa", 300.0, "former_design_yield_mpa"),
        ("strip_yield_max_mpa", 400.0, "former_design_yield_mpa"),
        ("roll_die_radius_mm", 40.0, "roll_die_radius_mm"),
        ("window_yield_min_mpa", 300.0, "window_yield_min_mpa"),
        ("check_tip_x_min_mm", 29.0, "check_tip_x_min_mm"),
        ("check_overall_max_mm", 98.0, "check_overall_max_mm"),
        ("ear_press_deg", 90.0, "ear_press_deg"),
        # The inner half moved: its least body behind the face changes.
        ("die_shift_mm", 3.0, "die_least_width_mm"),
        ("die_gap_min_mm", 7.0, "die_gap_min_mm"),
        ("die_least_width_mm", 30.0, "die_least_width_mm"),
        ("die_body_min_mm", 40.0, "least body"),
        ("outer_die_bond_area_mm2", 6000.0, "outer_die_bond_area_mm2"),
        ("die_level_count", 4, "die_level_count"),
        ("former_feed_mm_min", 500.0, "former_feed_mm_min"),
        ("em_quarter_projection_min_mm", 10.0, "collet would not clear"),
        ("drill_30_dia_mm", 3.3, "is not the #30's"),
        ("drill_30_projection_min_mm", 80.0, "longer than the drill"),
        ("spoil_drill_max_mm", 0.5, "deeper into the plate"),
        ("holes_bond_area_mm2", 100.0, "holes_bond_area_mm2"),
        ("holes_tip_z_mm", -1.5, "holes_tip_z_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_an_upcut_sheet_end_mill_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    tool = next(t for t in plan["tools"] if t["id"] == "em-sixteenth")
    del tool["axial_direction"]
    with pytest.raises(ValueError, match="downcut"):
        _context(plan)


def _seed(ctx: dict, label: str, pick, change) -> dict:
    """``ctx`` with the first line of job ``label`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    job = next(j for j in seeded["jobs"] if j["label"] == label)
    lines = job["ops"][0][2]
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


def _swap(old: str, new: str):
    return (lambda line: line.startswith(old)), (lambda line: line.replace(old, new, 1))


@pytest.mark.parametrize(
    ("label", "pick_change", "check"),
    [
        # The hook's arm edge cut .3 mm off its path.
        ("sheet", _swap("G1 X31.074 Y-22.445", "G1 X31.074 Y-22.145"), "outline"),
        # The sheet's last level taken deeper into the spoil plate.
        ("sheet", _swap("G1 Z-0.102", "G1 Z-0.400"), "depth"),
        # A die face cut .3 mm off its path.
        ("former", _swap("G1 X62.218 Y-54.514", "G1 X62.218 Y-54.214"), "outline"),
        # The former's last level taken deeper into the spoil plate.
        ("former", _swap("G1 Z-0.102", "G1 Z-0.400"), "depth"),
        # The channel's opening slot rapided through the blank.
        (
            "former",
            _swap("G1 X149.400 Y-66.220 F{feed}", "G0 X149.400 Y-66.220"),
            "rapid",
        ),
        # The near hole drilled .3 mm off its station.
        ("holes", _swap("G0 X-5.639 Y4.039", "G0 X-5.339 Y4.039"), "holes"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, label, pick_change, check
) -> None:
    seeded = _seed(context, label, *pick_change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

"""The cylinder gear's CAM recipe agrees with its model, its plan and the shop.

``cad/process/dt_cylinder_gear/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest with no FreeCAD
and no SolidWorks, and refuses any plan number that disagrees with the
model, the shop, the index or the depth and runout budgets. The posted
programs are stood in for by the recipe's own lines under the grbl post's
preamble, so every check the recipe declares runs on them, and seeded
faults show each check catches what it guards.
"""

from __future__ import annotations

import copy
import math
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import _shop_equipment
import cam_nc
import dt_cone_gear_spec
import dt_cone_gear_tl_keyed_arbor_spec as keyed_arbor
import dt_cylinder_gear_spec
import export_features

STEM = "dt_cylinder_gear"
IN = 25.4
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
P = PLAN["parameters"]


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "cam.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> dict[str, list[str]]:
    """Each program as the runtime posts it with no tool change: the grbl
    preamble, the first section's M3 and its lines (feeds in mm/min), a
    manual section's lines as written, then the postamble."""
    lines_of = {op[0]: (job, op[2]) for job in ctx["jobs"] for op in job["ops"]}
    posted: dict[str, list[str]] = {}
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
        for k, key in enumerate(keys):
            if key in ctx["manual"]:
                text += ctx["manual"][key]["gcode"]
                continue
            job, lines = lines_of[key]
            if k == 0:
                text.append(f"M3 S{job['rpm']:g}")
            text += [
                line.format(feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}")
                for line in lines
            ]
        text += ["M5", "G17 G90", "M2"]
        posted[name] = text
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")
    return posted


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_numbers_the_tools_and_closes_the_index(ctx) -> None:
    assert ctx["numbers"] == {"cutter": 1, "saw": 2}
    assert RECIPE.LOAD_FIRST_TOOL == ()
    index = ctx["budget"]["index"]
    assert index == {
        "plate": "A",
        "circle": 15,
        "turns": 0,
        "spaces": 5,
        "total_turns": 40,
    }
    # 120 indexes of 5 spaces: 600 spaces, 40 whole turns of the 15 circle.
    assert 120 * index["spaces"] % index["circle"] == 0


def test_the_budgets_fit_the_teeth_bands(ctx) -> None:
    teeth = FEATURES["features"]["teeth"]
    band = teeth["plunge"][1] - teeth["plunge"][0]
    budget = ctx["budget"]
    assert 0 < budget["deflection_mm"] < 0.02
    assert budget["depth_spread_mm"] <= band
    assert budget["runout_mm"] <= teeth["tooth_runout_tir_max"]


def test_the_plan_is_an_enrolled_traveler() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    ordered = {t["id"] for t in PLAN["tools"] if t.get("status") == "to_order"}
    assert {"cutter", "cutter-arbor", "saw"} <= ordered
    # Fit policy (#3513): no plug gauge pair; the owned saw arbor is not bought.
    assert not {"plugs", "saw-arbor"} & ordered
    assert not any("plug-gauges" in t.get("ref", "") for t in PLAN["tools"])
    assert {"gang-arbor", "fixture"} <= {
        t["id"] for t in PLAN["tools"] if t.get("status") == "to_make"
    }


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    posted = _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    stops = [line for line in posted["GP02_teeth"] if line == "M0"]
    assert len(stops) == 119
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_depth_check_and_over_pins_numbers_match_the_gear_data() -> None:
    """The plan's pin readings are the spec's corner profiles' (Ø.040 pins),
    rounded inward to .0001."""
    pin = P["pin_dia_in"] * IN
    over, both = [], []
    for profile in dt_cylinder_gear_spec.manufacturing_corner_profiles():
        m, _contact, interior = dt_cone_gear_spec._over_pins_mm(profile, pin)
        assert interior
        od = 2 * profile.blank_radius_mm
        over.append(m / IN)
        both.append((m - od) / IN)
    assert P["over_pins_min_in"] == math.ceil(min(over) * 1e4 - 1e-6) / 1e4
    assert P["over_pins_max_in"] == math.floor(max(over) * 1e4 + 1e-6) / 1e4
    assert P["pins_less_od_min_in"] == math.ceil(min(both) * 1e4 - 1e-6) / 1e4
    assert P["pins_less_od_max_in"] == math.floor(max(both) * 1e4 + 1e-6) / 1e4
    assert (
        P["pins_less_od_min_in"]
        < P["depth_window_min_in"]
        < P["depth_aim_in"]
        < P["depth_window_max_in"]
        < P["pins_less_od_max_in"]
    )


def test_the_boss_holds_the_cam_and_the_arbor_takes_the_cone_kits_collar() -> None:
    cam = FEATURES["features"]["cam"]
    reach = cam["throw"][1] + cam["dia"][1] / 2
    assert P["boss_dia_mm"] / 2 - reach >= 0.254
    assert P["collar_dia_mm"] == pytest.approx(max(keyed_arbor.COLLAR_DIAS))
    assert P["collar_length_mm"] == pytest.approx(keyed_arbor.COLLAR_LENGTH)
    assert P["pilot_dia_mm"] == pytest.approx(keyed_arbor.PILOT_DIA)
    assert P["pilot_dia_mm"] < keyed_arbor.COLLAR_BORE
    assert P["relief_dia_mm"] == pytest.approx(keyed_arbor.RELIEF_DIA)
    assert P["thread_pitch_mm"] == pytest.approx(keyed_arbor.THREAD_PITCH, abs=1e-6)
    assert P["thread_major_mm"] == pytest.approx(keyed_arbor.THREAD_MAJOR)


def test_the_plans_cutter_and_saw_records_are_the_inventorys() -> None:
    tools = _shop_equipment.load()["tools"]
    cutters = tools["gear-cutters-48dp-20pa"]
    member = cutters["members"][str(FEATURES["features"]["teeth"]["cutter_number"])]
    assert [P["cutter_member_teeth_min"], P["cutter_member_teeth_max"]] == member[
        "teeth"
    ]
    assert P["cutter_diametral_pitch"] == cutters["diametral_pitch"]
    assert P["cutter_pressure_angle_deg"] == cutters["pressure_angle_deg"]
    saw = tools["cylinder-notch-saw"]
    assert P["saw_thickness_mm"] == pytest.approx(saw["thickness_in"] * IN)
    assert SHOP["tools"]["gear-cutters-48dp-20pa"]["diameter_mm"] == pytest.approx(
        cutters["dia_in"] * IN
    )
    assert SHOP["tools"]["cylinder-notch-saw"]["diameter_mm"] == pytest.approx(
        saw["dia_in"] * IN
    )
    arbor = tools["saw-arbor-r8-stepped"]
    assert arbor["status"] == "on_hand" and saw["bore_in"] in arbor["pilot_bores_in"]
    assert P["saw_arbor_cap_dia_mm"] == pytest.approx(arbor["cap_dia_in"] * IN)
    assert arbor["body_dia_above_saw_in"] <= arbor["cap_dia_in"]


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("cutter_x_start_mm", 70.0, "cutter_x_start_mm"),
        ("cutter_x_end_mm", -2.0, "cutter_x_end_mm"),
        ("saw_x_start_mm", 80.0, "saw_x_start_mm"),
        ("saw_touch_z_mm", 0.5, "saw_touch_z_mm"),
        ("saw_touch_y_mm", -0.025, "saw_touch_y_mm"),
        ("plunge_aim_mm", 1.16, "plunge_aim_mm"),
        ("notch_aim_mm", 3.2, "notch_aim_mm"),
        ("stack_stickout_mm", 130.0, "stack_stickout_mm"),
        ("stack_od_max_in", 2.537, "O.D. band"),
        ("mount_tir_max_mm", 0.04, "runout budget"),
        ("depth_deep_blank", 2, "depth check's blanks"),
        ("depth_aim_in", 0.0278, "depth_aim_in"),
        ("depth_spread_stop_in", 0.0034, "depth_spread_stop_in"),
        ("depth_spread_stop_in", 0.0020, "depth_spread_stop_in"),
        ("depth_window_max_in", 0.0291, "depth_window_max_in"),
        ("opposite_turns", 19, "opposite_turns"),
        ("journal_dia_min_mm", 9.50, "beam_brass_equiv_dia_mm"),
        ("standoff_mm", 25.0, "past the jaws"),
        ("journal_length_mm", 80.0, "blank 10's bore"),
        ("arbor_modulus_gpa", 20.0, "beam_brass_equiv_dia_mm"),
        ("pilot_length_mm", 9.906, "cannot clamp"),
        ("pilot_length_mm", 1.0, "ride the pilot"),
        ("relief_width_mm", 0.5, "narrower than one pitch"),
        ("cutter_teeth_min", 6, "depth_spread_in"),
        ("cutter_member_teeth_max", 110, "cuts 55-110"),
        ("brass_unit_power_hp_min_per_in3", 3.0, "depth_spread_in"),
    ],
)
def test_a_plan_number_off_the_model_shop_or_budget_is_refused(
    key, value, detail
) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_loose_arbor_fit_breaks_the_runout_budget() -> None:
    plan = copy.deepcopy(PLAN)
    p = plan["parameters"]
    p["journal_dia_min_mm"] = 9.50
    p["beam_brass_equiv_dia_mm"] = (
        9.50 * (p["arbor_modulus_gpa"] / p["brass_modulus_gpa"]) ** 0.25
    )
    with pytest.raises(ValueError, match="runout budget"):
        _context(plan)


def test_a_journal_that_cannot_enter_the_least_bore_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    p = plan["parameters"]
    p["journal_dia_min_mm"] = FEATURES["features"]["bore"]["dia"][0]
    p["beam_brass_equiv_dia_mm"] = (
        p["journal_dia_min_mm"]
        * (p["arbor_modulus_gpa"] / p["brass_modulus_gpa"]) ** 0.25
    )
    with pytest.raises(ValueError, match="does not enter the least bore"):
        _context(plan)


def test_a_park_too_close_for_the_micrometer_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["measure_park_y_mm"] = plan["parameters"]["clear_y_mm"]
    with pytest.raises(ValueError, match="the micrometer needs"):
        _context(plan)
    # The traveler prints the park the program makes.
    park_in = -PLAN["parameters"]["measure_park_y_mm"] / 25.4
    (step,) = (
        op["instruction"]
        for setup in PLAN["setups"]
        for op in setup["operations"]
        if op.get("instruction", "").startswith("Run GP01_first_space (")
    )
    assert f"drawn back {park_in:.2f} from the tips" in step


def test_an_index_count_off_the_teeth_is_refused() -> None:
    plan = copy.deepcopy(PLAN)
    setup = next(s for s in plan["setups"] if isinstance(s.get("indexing"), dict))
    setup["indexing"]["positions"] = 119
    with pytest.raises(ValueError, match="indexes 119 positions"):
        _context(plan)


def _seed(posted: list[str], fault: str) -> list[str]:
    lines = list(posted)
    stops = [i for i, line in enumerate(lines) if line == "M0"]
    passes = [
        i for i, line in enumerate(lines) if line.startswith("G1 X") and "Y" not in line
    ]
    if fault == "a stop dropped":
        k = stops[40]
        del lines[k - 2 : k + 1]
    elif fault == "a space numbered twice":
        k = stops[10]
        lines[k - 1] = lines[k - 1].replace("SPACE 13 OF", "SPACE 12 OF")
    elif fault == "the spindle left on":
        k = stops[5]
        assert lines[k - 2] == "M5"
        del lines[k - 2]
    elif fault == "the spindle not restarted":
        k = stops[8]
        assert lines[k + 1].startswith("M3 ")
        lines[k + 1] = lines[k + 1].split()[1]
    elif fault == "the spindle restarted after the pass":
        k = stops[9]
        assert lines[k + 1].startswith("M3 ") and lines[k + 3].startswith("G1 X")
        lines.insert(k + 3, lines.pop(k + 1))
    elif fault == "a pass drawn back":
        k = passes[7]
        target = lines[passes[6]].split()[1]
        lines[k] = f"G1 {target} {lines[k].split()[2]}"
    elif fault == "a pass off the depth":
        k = passes[20]
        lines[k] = lines[k].replace("G1 X", "G1 Y1.150 X")
    elif fault == "a rapid into the stack":
        lines.insert(passes[3] + 1, "G0 Y0.500")
    elif fault == "the closure dropped":
        k = stops[-1]
        del lines[k - 2 : k + 4]
    return lines


@pytest.mark.parametrize(
    "fault",
    [
        "a stop dropped",
        "a space numbered twice",
        "the spindle left on",
        "the spindle not restarted",
        "the spindle restarted after the pass",
        "a pass drawn back",
        "a pass off the depth",
        "a rapid into the stack",
        "the closure dropped",
    ],
)
def test_a_seeded_fault_in_the_teeth_program_is_caught(ctx, tmp_path, fault) -> None:
    posted = _post(ctx, tmp_path)
    (tmp_path / "GP02_teeth.nc").write_text(
        "\n".join(_seed(posted["GP02_teeth"], fault)) + "\n", encoding="utf-8"
    )
    findings = [str(f) for f in _findings(ctx, tmp_path)]
    assert findings, fault
    assert all(f.startswith("GP02_teeth.nc") for f in findings)


def test_a_notch_cut_past_its_depth_is_caught(ctx, tmp_path) -> None:
    posted = _post(ctx, tmp_path)
    deep = [line.replace("G1 Y3.048", "G1 Y3.400") for line in posted["GP03_notch"]]
    (tmp_path / "GP03_notch.nc").write_text("\n".join(deep) + "\n", encoding="utf-8")
    findings = [str(f) for f in _findings(ctx, tmp_path)]
    assert any("rims past the deepest limit" in f for f in findings)


def test_the_phase_check_band_is_the_drawings_cam_angle() -> None:
    cam = FEATURES["features"]["cam"]
    throw = sum(cam["throw"]) / 2 / IN
    angle, tol = cam["notch_phase_deg"], cam["notch_phase_tol_deg"]
    low = throw * math.sin(math.radians(angle - tol))
    high = throw * math.sin(math.radians(angle + tol))
    assert P["phase_drop_min_in"] == math.ceil(low * 1e4) / 1e4
    assert P["phase_drop_max_in"] == math.floor(high * 1e4) / 1e4

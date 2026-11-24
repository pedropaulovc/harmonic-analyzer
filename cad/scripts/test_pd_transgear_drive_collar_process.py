"""The drive collar's CAM recipe agrees with its model and plan.

``cad/process/pd_transgear_drive_collar/cam.py`` writes every path itself;
its ``context`` runs here on the drawing's requirement manifest (the
features the collar's export binds) with no FreeCAD and no SolidWorks, and
refuses any plan number that disagrees with the model, the shop or the
holding. The posted program is stood in for by the recipe's own section
lines under the grbl post's tool-change block, so every check the recipe
declares runs on it, and seeded faults show each check catches what it
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
import pd_transgear_drive_collar_spec as SPEC

STEM = "pd_transgear_drive_collar"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN, shop: dict = SHOP) -> dict:
    return RECIPE.context(FEATURES, plan, shop, "cam.step")


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
        for (key,) in groups:
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


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "spot": 1,
        "drill-43": 2,
        "reamer-0930": 3,
        "drill-53": 4,
        "reamer-0615": 5,
    }
    assert RECIPE.LOAD_FIRST_TOOL == ("CM01_holes",)


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    assert STEM in _cam_programs.CAM_STEMS
    # Fit audit 2026-11-23: the bore is drilled #11 (owned index) and the
    # reamed holes are gauged by their own pins, so the .1920 reamer and the
    # three Class ZZ pin pairs are gone; the .001-step set reads the flat
    # pin's centre.
    tools = {t["id"]: t.get("status") for t in PLAN["tools"]}
    assert {k for k, status in tools.items() if status == "to_order"} == {
        "reamer-0930",
        "reamer-0615",
        "pin-gauges",
    }
    assert "drill-11" in tools and not {"reamer-1920", "drill-14"} & set(tools)
    assert not any(k.startswith("zz-") for k in tools)
    used = {
        check["gauge"]
        for setup in PLAN["setups"]
        for op in setup["operations"]
        if isinstance(op.get("gauge_checks"), list)
        for check in op["gauge_checks"]
    }
    assert not any(g.startswith("zz-pins") for g in used)


def test_the_recipes_program_passes_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {"CM01_holes"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("parallel_gap_mm", 12.0, "parallel_gap_mm"),
        ("parallel_thickness_mm", 6.35, "parallel_gap_mm"),
        ("rear_over_jaws_mm", 1.5, "rear_over_jaws_mm"),
        ("vise_jaw_height_mm", 50.0, "rear_over_jaws_mm"),
        ("spot_dia_mm", 1.6, "under both drills"),
        ("spot_dia_mm", 1.2, "bore's edge"),
        ("dowel_drill_tip_mm", -8.5, "dowel_drill_tip_mm"),
        ("drill_past_mm", 2.0, "dowel_drill_tip_mm"),
        ("flat_drill_tip_mm", -5.5, "flat_drill_tip_mm"),
        ("flat_ream_tip_mm", -6.0, "flat_ream_tip_mm"),
        ("body_max_in", 0.31, "flat pin's floor"),
        ("body_supply_in", 0.29, "body_min_in"),
        ("pilot_supply_in", 0.13, "pilot_supply_min_in"),
        ("pilot_supply_min_in", 0.13, "pilot_supply_min_in"),
        ("pilot_supply_max_in", 0.15, "part_off_in"),
        ("part_off_in", 0.45, "part_off_in"),
        ("peck_43_mm", 3.0, "peck"),
        ("tool_out_min_in", 0.5, "tool_out_min_in"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _with_cut(plan: dict, name: str, key: str, value: float) -> dict:
    plan = copy.deepcopy(plan)
    for setup in plan["setups"]:
        for op in setup.get("operations", ()):
            for milling in op.get("milling_cuts", ()):
                if milling["name"] == name:
                    milling[key] = value
    return plan


def test_a_cut_off_its_shop_tool_or_setting_is_refused() -> None:
    with pytest.raises(ValueError, match="not its tool's"):
        _context(_with_cut(PLAN, "dowel drill", "cutter_dia_mm", 2.3))
    with pytest.raises(ValueError, match="not its setting's"):
        _context(_with_cut(PLAN, "flat ream", "rpm", 2000))


def test_a_reamer_off_its_hole_band_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["reamer-0930"] = {
        **shop["tools"]["reamer-0930"],
        "diameter_mm": 2.4,
    }
    with pytest.raises(ValueError, match="outside its hole band"):
        _context(PLAN, shop)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` replaced."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    assert old in lines, (key, old)
    lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # A dowel hole drilled off its station.
        ("dowel_drill", "G0 X7.000 Y0.000", "G0 X6.000 Y0.000", "holes"),
        # The flat pin's #53 stopped short of its floor.
        ("flat_drill", "G1 Z-6.296 F{feed}", "G1 Z-4.000 F{feed}", "holes"),
        # A dowel hole moved across into the fixed jaw's parallels.
        ("dowel_drill", "G0 X7.000 Y0.000", "G0 X7.000 Y5.000", "keep_out"),
        # The dowel reamer rapided out of its finished hole.
        ("dowel_ream", "G1 Z1.000 F{feed}", "G0 Z1.000", "feed_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}


def test_the_flat_pin_centre_is_accepted_as_printed_and_the_spec_charges_the_bias() -> None:
    # D6 (delegated ruling 2026-11-24, Main): Op 260 accepts the
    # sheet's .116-.120 as read, so the spec's worst cases charge the true
    # centre that band widened by the loose pins' .0012 reading bias.
    assert SPEC.FLAT_PIN_CENTRE_READ_BIAS == pytest.approx(0.0012 * 25.4)
    lo, hi = SPEC._FLAT_PIN_CENTRE_LIMITS
    widen = SPEC.FLAT_PIN_CENTRE_TOL + SPEC.FLAT_PIN_CENTRE_READ_BIAS
    assert (lo, hi) == pytest.approx(
        (SPEC.FLAT_PIN_CENTRE - widen, SPEC.FLAT_PIN_CENTRE + widen)
    )
    assert min(SPEC.FLAT_PIN_CREST_LIMITS) == pytest.approx(
        lo - max(SPEC._FLAT_PIN_R_LIMITS)
    )
    p = PLAN["parameters"]
    for retired in ("over_pins_bias_in", "flat_centre_accept_min_in", "flat_centre_accept_max_in"):
        assert retired not in p
    text = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    accept = "{{cad.flat_pin_hole_centre_min_in:.3dot}}–{{cad.flat_pin_hole_centre_max_in:.3dot}}"
    assert f"Flat pin's centre {accept} from the bore's axis" in text

"""The disc hub's CAM recipe agrees with its model and plan.

``cad/process/pd_transgear_disc_hub/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the hub's export binds) with no FreeCAD and no SolidWorks, and refuses any
plan number that disagrees with the model, the shop or the holding. The
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

STEM = "pd_transgear_disc_hub"
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
        "drill-51": 2,
        "endmill": 3,
        "drill-56": 4,
        "drill-53": 5,
        "reamer-0615": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == (
        "CM01_flange_holes",
        "CM02_pin_hole",
        "CM03_pin_ream",
    )


def test_the_plan_is_an_enrolled_traveler_and_cam_stem() -> None:
    assert PLAN["revision"] != "placeholder"
    assert STEM in _process_plans.enrolled_stems()
    assert STEM in _cam_programs.CAM_STEMS
    tools = {t["id"] for t in PLAN["tools"]}
    to_order = {t["id"] for t in PLAN["tools"] if t.get("status") == "to_order"}
    assert {
        "sharp",
        "reamer-0615",
        "zz-3135",
    } <= to_order
    # #3739: the 1/16 end mill is the owned Kyocera 1800.0625.200 (on_hand).
    assert "endmill" not in to_order
    endmill = next(t for t in PLAN["tools"] if t["id"] == "endmill")
    assert endmill["ref"] == "endmill-kyocera-1800-1-16"
    # Fit audit 2026-11-23: the reamed holes print no band, so no Class ZZ
    # pin gauges them; the ream's mate (the MHA-PD-VN-69 dowel) accepts it.
    # The bore is the one exception (owner ruling 2026-11-26: the ZZ .3135
    # plus GO, the set's .314 minus NO-GO); the chord ream keeps the rule.
    assert "zz-0615" not in tools
    assert {t["ref"] for t in PLAN["tools"] if "zz-pins" in t.get("ref", "")} == {
        "zz-pins-3135-3140"
    }
    for index, setup in enumerate(PLAN["setups"]):
        if index == 1:  # Setup 2 reams and gauges the bore
            continue
        for op in setup["operations"]:
            words = f"{op.get('instruction', '')} {op.get('inspection', '')} {op.get('gauge_checks', '')}"
            for word in ("zz-pins", "GO pin", "NO-GO"):
                assert word not in words


def test_the_bore_is_hand_reamed_with_the_owned_adjustable_set() -> None:
    # Coordinator 2026-11-25 (D19 as amended): the bore is made to fit, so no
    # fixed reamer is bought for it. Owner ruling 2026-11-26 gauges it to the
    # printed Ø.3135: the ZZ .3135 plus GO (MHA-PD-10's boss wall) and the
    # set's .314 minus NO-GO (the spigot's WALL .071 MIN at .3140).
    text = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    assert "reamer-3135" not in text
    reamer = next(t for t in PLAN["tools"] if t["ref"] == "reamers-adjustable-lms-5948")
    assert "status" not in reamer
    ops = PLAN["setups"][1]["operations"]
    reams = [op for op in ops if op.get("tool") == reamer["id"]]
    assert len(reams) == 2  # the trial piece's, then the hub's
    for op in reams:
        assert (op["speed_kind"], op["feed"]) == ("other", "hand")
        assert "settings" not in op
        assert "the GO passes through, the NO-GO does not enter" in op["inspection"]
        assert ".313" not in op["inspection"]
    assert reams[1]["gauge_checks"] == [
        {"gauge": "zz-pins-3135-3140", "band_mm": "{{cad.bore_dia_band_mm}}"}
    ]
    # The first op of the setup holds the bore until both pins are in hand;
    # the GO pin's lead time (to order) is This job's, read before Setup 1.
    first = ops[0]["instruction"]
    assert ".3135 plus GO pin" in first and ".314 minus NO-GO" in first
    (this_job,) = [n for n in PLAN["notes"] if n["title"] == "This job"]
    assert any(".3135 GO pin" in text for _, text in this_job["rows"] if text.startswith("To order"))
    assert "the bore cannot be accepted" in first
    # Codjiflo #3592 r2: a NO-GO entering at the first .3135 pass has no
    # earlier setting to fall back to; the remedy backs off by a stated step.
    trial_remedy = ops[ops.index(reams[0]) + 1]["instruction"]
    assert "{{process.ream_back_off_in:.4dot}} under the one that let it in" in trial_remedy
    assert PLAN["parameters"]["ream_back_off_in"] > PLAN["parameters"]["ream_open_step_in"]


def test_the_flange_face_is_set_from_the_miked_length_not_the_spigot_nominal() -> None:
    # Codjiflo #3592 r1: with the spigot at the title block's ±.005, a fixed
    # Z-.144 leaves the flange .086-.102 against its .089-.099; Z-F (F = T
    # less the flange's .094) keeps the flange at size and F inside .139-.149.
    sharp = next(op for op in PLAN["setups"][1]["operations"] if op.get("tool") == "sharp")
    assert "spigot_length_mm" not in sharp["instruction"]
    assert "less {{cad.flange_front_face_thickness_mm:in.3dot}}" in sharp["instruction"]
    assert sharp["instruction"].count("Z-F") == 2
    # Codjiflo #3592 r2: every outcome of the face and flange checks has an
    # action; a face short of Z-.139 is faced on, never scrapped.
    remedy = PLAN["setups"][1]["operations"][PLAN["setups"][1]["operations"].index(sharp) + 1]
    text = remedy["instruction"]
    assert "The face short of Z-{{cad.spigot_length_min_in:.3dot}} or the flange over" in text
    assert "never past Z-{{cad.spigot_length_max_in:.3dot}}" in text


def test_the_traveler_leaves_the_assembly_work_to_pd_00() -> None:
    last = PLAN["setups"][-1]["operations"][-1]
    assert "tool" not in last
    for step in ("MHA-PD-VN-69", "8A", "9G", "MHA-PD-10", "(17)"):
        assert step in last["instruction"]


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {"CM01_flange_holes", "CM02_pin_hole", "CM03_pin_ream"}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("stickout_mm", 15.0, "stickout_mm"),
        ("part_off_in", 0.55, "part_off_in"),
        ("regrip_out_mm", 7.0, "regrip_out_mm"),
        ("bar_use_in", 0.5, "bar_use_in"),
        ("flange_run_in", 0.6, "flange_run_in"),
        ("flange_parallel_gap_mm", 18.0, "flange_parallel_gap_mm"),
        ("parallel_thickness_mm", 6.35, "flange_parallel_gap_mm"),
        ("flange_jaw_top_mm", 2.0, "flange_jaw_top_mm"),
        ("parallel_stack_mm", 50.8, "flange_jaw_top_mm"),
        ("flange_spot_dia_mm", 1.8, "under the #51"),
        ("flange_drill_tip_mm", -5.0, "flange_drill_tip_mm"),
        ("flange_drill_past_mm", 2.0, "flange_drill_tip_mm"),
        ("flange_tool_out_min_in", 0.4, "flange_tool_out_min_in"),
        ("pin_jaw_top_mm", 10.0, "pin_jaw_top_mm"),
        ("pin_parallel_height_mm", 31.75, "pin_jaw_top_mm"),
        ("pin_flange_top_mm", 12.0, "pin_flange_top_mm"),
        ("pin_flat_bottom_mm", 5.0, "pin_flat_bottom_mm"),
        ("pin_flat_peck_mm", 1.0, "pin_flat_peck_mm"),
        ("endmill_reach_min_in", 0.05, "endmill_reach_min_in"),
        ("endmill_out_min_in", 0.5, "endmill_out_min_in"),
        ("endmill_out_min_in", 0.9, "endmill_out_min_in"),
        ("knockout_tip_mm", -7.0, "knockout_tip_mm"),
        ("knockout_past_mm", 1.5, "knockout_tip_mm"),
        ("pilot_tip_mm", -4.0, "pilot_tip_mm"),
        ("ream_tip_mm", -4.2, "ream_tip_mm"),
        ("stop_shallow_mm", -4.064, "stop_shallow_mm"),
        ("stop_deep_mm", -4.3, "stop_deep_mm"),
        ("peck_56_mm", 2.0, "peck"),
        ("pin_tool_out_min_in", 0.8, "pin_tool_out_min_in"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_an_end_mill_whose_flutes_are_shorter_than_its_reach_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["endmill-kyocera-1800-1-16"]["flute_length_mm"] = 2.3622
    with pytest.raises(ValueError, match="flutes are shorter"):
        _context(PLAN, shop)


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
        _context(_with_cut(PLAN, "flange drill", "cutter_dia_mm", 1.8))
    with pytest.raises(ValueError, match="not its setting's"):
        _context(_with_cut(PLAN, "pin ream", "rpm", 2000))


def test_a_reamer_off_its_hole_band_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["reamer-0615"] = {**shop["tools"]["reamer-0615"], "diameter_mm": 1.6}
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
        # A flange hole drilled off its circle.
        ("flange_drill", "G0 X9.525 Y0.000", "G0 X9.000 Y0.000", "holes"),
        # A flange hole moved across into the fixed jaw's stack.
        ("flange_drill", "G0 X9.525 Y0.000", "G0 X9.525 Y10.000", "keep_out"),
        # The #53 stopped short of the stop.
        ("pin_pilot", "G1 Z-4.518 F{feed}", "G1 Z-3.900 F{feed}", "holes"),
        # The knockout run down into the parallel.
        ("pin_knockout", "G1 Z-6.344 F{feed}", "G1 Z-7.000 F{feed}", "depth"),
        # The chord hole moved into the fixed jaw.
        ("pin_knockout", "G0 X4.420 Y-3.810", "G0 X4.420 Y-0.300", "keep_out"),
        # The reamer rapided out of its finished hole.
        ("pin_ream", "G1 Z6.888 F{feed}", "G0 Z6.888", "feed_out"),
    ],
)
def test_a_seeded_fault_in_the_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

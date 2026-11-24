"""The cone tip block's CAM recipe agrees with its model and plan.

``cad/process/dt_cone_tip_block/cam.py`` writes every path itself; its
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
import _shop_equipment
import cam_nc
import export_features

STEM = "dt_cone_tip_block"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "tip.step")


@pytest.fixture(scope="module")
def context() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a program that does not load its first tool starts on
    its M3; a tap stop's lines after its M6, ending with its M30; a manual
    section of the tool already in the spindle (the saw's stop) is its own
    lines alone, and the section after it starts on its M3."""
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
        previous = None
        for key in keys:
            if key in ctx["manual"]:
                manual = ctx["manual"][key]
                if manual["tool"] != previous:
                    text += [
                        "M5",
                        f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                        f"M6 T{manual['tool']}",
                    ]
                text += manual["gcode"]
                previous = manual["tool"]
                continue
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            if (
                name in RECIPE.LOAD_FIRST_TOOL
                if previous is None
                else number != previous
            ):
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
            previous = number
        if keys[-1] not in ctx["manual"]:
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def test_context_accepts_the_plan_and_numbers_the_tools(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-43": 3,
        "drill-30": 4,
        "drill-3": 5,
        "chamfer": 6,
        "tap-guide": 7,
        "slit-saw": 8,
    }
    # Every program but the saw's loads its first tool: the saw is mounted
    # on its arbor by hand, with no tool-setter length.
    names = [name for name, _ops in RECIPE.PROGRAMS]
    assert set(RECIPE.LOAD_FIRST_TOOL) == set(names) - {"DT11_slit"}
    taps = {key: stop for key, stop in context["manual"].items() if key != "slit_check"}
    assert set(taps) == {"tap_foot", "tap_pinch", "tap_adjuster"}
    for stop in taps.values():
        assert stop["tool"] == 7
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_saw_and_arbor_sizes_are_their_inventory_records() -> None:
    """Tool-audit Q10: the slit is cut with the owned 2-3/4 x .064 saw on the
    owned R8 stepped arbor. Every size of either that the plan repeats is the
    inventory record's; the two sizes the record does not carry stay named
    bounds of the plan, not record numbers."""
    p = PLAN["parameters"]
    refs = {tool["id"]: tool["ref"] for tool in PLAN["tools"]}
    assert refs["slit-saw"] == "slitting-saw-2-75-064"
    assert refs["arbor"] == "saw-arbor-r8-stepped"
    tools = _shop_equipment.load()["tools"]
    saw, arbor = tools[refs["slit-saw"]], tools[refs["arbor"]]
    assert saw["bore_in"] == 1.0  # Q10's condition: it goes on the 1 in pilot
    for key, value in (
        ("saw_dia_mm", saw["dia_in"]),
        ("saw_thickness_mm", saw["thickness_in"]),
        ("saw_bore_mm", saw["bore_in"]),
        ("saw_arbor_body_dia_mm", arbor["body_dia_above_saw_in"]),
        ("saw_arbor_cap_dia_mm", arbor["cap_dia_in"]),
        ("saw_arbor_cap_thickness_mm", arbor["cap_thickness_in"]),
        ("saw_arbor_screw_head_dia_mm", arbor["screw_head_dia_in"]),
        ("saw_arbor_nose_to_cap_mm", arbor["below_spindle_nose_in"]),
    ):
        assert p[key] == pytest.approx(value * 25.4, abs=1e-4), key
    assert p["saw_teeth"] == saw["teeth"]
    assert arbor["screw_head_past_cap_in"] == "to_measure"
    # The drive is the cap's friction alone, at the record's clamp torque, on
    # the record's thread and its engagement as the owner counted it.
    assert arbor["keyed"] is False
    assert p["saw_clamp_torque_nm"] == arbor["clamp_torque_nm"]
    assert arbor["screw_thread"].split(" x ")[0] == f"M{p['saw_screw_dia_mm']:g}"
    assert p["saw_screw_engagement_no_saw_mm"] == arbor["screw_engagement_no_saw_mm"]
    # The saw and the arbor that were to buy are no tools of the plan, and the
    # limits laid out on them (that blade's upper bound, the spacer-type
    # arbor's collars, spacers and nut) are no parameters of it.
    assert not {"slitting-saw-3-051", "gear-cutter-arbor-1"} & set(refs.values())
    for gone in (
        "blade_max_mm",
        "saw_collar_dia_max_mm",
        "saw_spacer_above_min_mm",
        "saw_spacer_below_min_mm",
        "saw_nut_dia_max_mm",
    ):
        assert gone not in p, gone


def test_the_clamp_torque_is_set_with_the_recorded_wrench() -> None:
    """The friction drive is checked against the clamp torque, so the
    operation that sets it names the torque wrench (the owner's, on hand, to
    be identified) and the 5 mm hex bit record (to be confirmed, no status).
    Setup 10's rule and straightedge are the owned combination square."""
    refs = {tool["id"]: tool["ref"] for tool in PLAN["tools"]}
    tools = _shop_equipment.load()["tools"]
    for tool_id in ("torque-wrench", "square"):
        assert tools[refs[tool_id]]["status"] == "on_hand", tool_id
    assert refs["hex-bit-5mm"] in tools
    assert any(
        op.get("tool") == "torque-wrench"
        for setup in PLAN["setups"]
        for op in setup["operations"]
    )


@pytest.mark.parametrize(
    ("preload_kn", "drive_nm"),
    [
        # One face carries less than the heaviest pass takes (8.1 N·m).
        (3.0, 6.03),
        # It carries the pass, but not twice it.
        (7.0, 14.06),
    ],
)
def test_a_pass_over_the_friction_drive_is_refused(preload_kn, drive_nm) -> None:
    """The arbor is not keyed. One face of the clamp carries the drive (the
    other face and the screw are reserve), and the heaviest pass may take half
    of it at most: a weaker clamp is refused."""
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["saw_clamp_preload_kn"] = preload_kn
    plan["parameters"]["saw_drive_torque_max_nm"] = drive_nm
    with pytest.raises(ValueError, match="friction drive with its reserve"):
        _context(plan)


def test_the_arbor_must_have_room_to_drop_out_at_the_machine_top(monkeypatch) -> None:
    """The arbor comes out with the saw clamped on it: its shank drops its
    own length, so the traveler sends Z to the machine top first, and the
    recipe refuses a mill without that room under the spindle nose there."""
    monkeypatch.setattr(RECIPE, "R8_SHANK_MM", 300.0)
    with pytest.raises(ValueError, match="cannot drop out of the spindle"):
        _context()


def test_the_slit_saw_steps_in_to_the_slits_depth(context) -> None:
    """Four passes: a light first one, half a step, then the file's own stop
    with the spindle off (the arbor drives the saw by friction: its marker
    lines are read there), then three equal steps no deeper than the plan's,
    the last at the slit's depth past the TOP end: the saw's centre its
    radius less that."""
    p = PLAN["parameters"]
    radius = p["saw_dia_mm"] / 2

    def depths(key: str) -> list[float]:
        return [
            round(radius - float(line.split()[1][1:]), 3)
            for line in _lines(context, key)
            if line.startswith("G0 X")
        ]

    first, rest = depths("slit_first"), depths("slit")
    assert (len(first), len(rest)) == (1, 3)
    cut = first + rest
    assert cut == sorted(cut)
    assert cut[-1] == pytest.approx(p["slit_depth_mm"], abs=1e-3)
    steps = [b - a for a, b in zip(cut, cut[1:], strict=False)]
    assert max(steps) <= p["slit_step_max_mm"] + 1e-3
    assert max(steps) - min(steps) < 2e-3
    assert first[0] == pytest.approx(steps[0] / 2, abs=2e-3)
    assert first[0] == pytest.approx(p["slit_first_pass_mm"], abs=1e-3)
    assert steps[0] == pytest.approx(p["slit_step_mm"], abs=1e-3)
    groups = dict(RECIPE.PROGRAMS)["DT11_slit"]
    assert [group[0] for group in groups] == ["slit_first", "slit_check", "slit"]
    stop = context["manual"]["slit_check"]
    assert stop["tool"] == context["numbers"]["slit-saw"]
    assert stop["gcode"][0] == "M5" and stop["gcode"][-1] == "M0"
    assert stop["gcode"][-2].startswith("%msg ")


def test_the_adjuster_is_drilled_where_it_is_countersunk_and_tapped(context) -> None:
    drilled = next(
        kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if program.startswith("DT08_adjuster") and check == "holes"
    )
    assert [context["manual"]["tap_adjuster"]["at"]] == [drilled[0]]


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("east_skim_mm", 1.0, "west_raw"),
        ("length_target_mm", 52.0, "length_target_mm"),
        ("depth_target_mm", 11.5, "depth_target_mm"),
        ("foot_tip_height_mm", 41.5, "foot_tip_height_mm"),
        ("clearance_depth_mm", 9.0, "clearance_depth_mm"),
        ("csk_orbit_mm", 0.5, "csk_orbit_mm"),
        ("foot_bottoming_reach_mm", 10.2, "foot_bottoming_reach_mm"),
        ("pinch_tap_reach_mm", 8.0, "pinch_tap_reach_mm"),
        ("adjuster_tap_reach_mm", 12.0, "adjuster_tap_reach_mm"),
        ("saw_cut_z_mm", 7.5, "saw_cut_z_mm"),
        ("kerf_max_mm", 1.778, "kerf_max_mm"),
        ("saw_side_tir_nominal_mm", 0.1524, "saw_side_tir_nominal_mm"),
        ("saw_tip_tir_max_mm", 2.0, "saw_tip_tir_max_mm"),
        ("saw_dia_min_mm", 66.0, "saw_dia_min_mm"),
        ("slit_first_pass_mm", 4.3223, "slit_first_pass_mm"),
        ("saw_reach_max_mm", 20.0, "saw_reach_max_mm"),
        ("saw_screw_stand_max_mm", 12.7, "saw_below_max_mm"),
        ("saw_below_stack_top_mm", 9.0, "saw_below_stack_top_mm"),
        ("spacer_under_max_mm", 0.02, "spacer_under_max_mm"),
        ("saw_screw_engagement_no_saw_mm", 9.0, "under one diameter of thread"),
        ("saw_nose_above_min_mm", 5.0, "saw_nose_above_min_mm"),
        ("saw_arbor_body_dia_mm", 44.45, "saw_reach_max_mm"),
        ("saw_drive_torque_max_nm", 44.2, "saw_drive_torque_max_nm"),
        ("lying_grip_mm", 8.0, "lying_grip_mm"),
        ("east_grip_mm", 6.8453, "east_grip_mm"),
        ("tap_stack_max_mm", 261.62, "tap_stack_max_mm"),
        ("adjuster_wrench_reach_max_mm", 200.0, "adjuster_wrench_reach_max_mm"),
        ("vise_slit_inset_mm", -120.0, "vise_slit_inset_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` (or of a tap stop)
    that ``pick`` accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The last saw pass short of the slit's depth.
        (
            "slit",
            lambda line: line.startswith("G0 X19.797"),
            lambda line: line.replace("X19.797", "X22.000"),
            "passes",
        ),
        # A saw pass lowered under its height, toward the jaw tops.
        (
            "slit",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z5.000 F{feed}",
            "depth",
        ),
        # The saw's stop after its first pass left with the spindle running.
        (
            "slit_check",
            lambda line: line == "M5",
            lambda line: "G17",
            "pauses",
        ),
        # The saw's first pass run at full depth: the arbor's body into TOP.
        (
            "slit_first",
            lambda line: line.startswith("G0 X32.764"),
            lambda line: line.replace("X32.764", "X12.000"),
            "keep_out",
        ),
        # The adjuster drilled short of S.
        (
            "adjuster_drill",
            lambda line: line.startswith("G1 Z-2.625"),
            lambda line: "G1 Z1.000 F{feed}",
            "holes",
        ),
        # A countersink circle run too wide.
        (
            "north_csk",
            lambda line: line.startswith("G1 X38.764"),
            lambda line: "G1 X39.200 F{feed}",
            "cleared",
        ),
        # The first seat-face level run into the jaws.
        (
            "seat_face",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z20.000 F{feed}",
            "keep_out",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        (
            "tap_pinch",
            lambda line: line == "M30",
            lambda line: "M0",
            "tap_stop",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(context, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

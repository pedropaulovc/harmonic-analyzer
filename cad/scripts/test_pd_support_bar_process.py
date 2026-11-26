"""The support bar's CAM recipe agrees with its model and plan.

``cad/process/pd_support_bar/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the ``flat_bar`` adapter binds) with no FreeCAD, no SolidWorks and no
feature bundle, and refuses any plan number that disagrees with the model,
the shop or the holding. The posted programs are stood in for by the
recipe's own section lines under the grbl post's tool-change block (a
program's flat key list one section, as the runtime posts one Job), so every
check the recipe declares runs on them, and seeded faults show each check
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

STEM = "pd_support_bar"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
PREAMBLE = ["(Begin preamble)", "G17 G90", "G21", "G54"]


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "bar.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its
    operations' lines, the feeds in mm/min; a manual section (the tap stop)
    its M6 block and its own G-code, ending the file."""
    jobs = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, keys in RECIPE.PROGRAMS:
        flat = all(isinstance(key, str) for key in keys)
        text = [f"({name})", f"({ctx['comment']})", *PREAMBLE]
        manual_only = True
        for section in [keys] if flat else keys:
            if section[0] in ctx["manual"]:
                stop = ctx["manual"][section[0]]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{stop['tool']} {stop['label']}, {stop['setting']}",
                    f"M6 T{stop['tool']}",
                    *stop["gcode"],
                ]
                continue
            manual_only = False
            job = jobs[section[0]]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for key in section:
                assert jobs[key] is job, f"{name}: {key} is not in its section's Job"
                text += [
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines_of[key]
                ]
        if not manual_only:
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _expected(ctx: dict, program: str, check: str) -> dict:
    return next(
        kwargs
        for name, found, kwargs in ctx["expect"]
        if name == program and found == check
    )


def test_context_numbers_the_tools_and_places_every_feature_from_end_a(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-9": 3,
        "cbore": 4,
        "drill-29": 5,
        "chamfer": 6,
        "em-eighth": 7,
        "tap-guide": 8,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    f = FEATURES["features"]
    end_x, top_y = f["end_a"]["plane"]["value"], f["top_face"]["plane"]["value"]

    def front(*names: str) -> list:
        # Front face up, T at the fixed jaw: END A at the right, the bar
        # toward -X; Y down from T.
        return [
            [round(end_x - f[n]["at"][0], 3), round(f[n]["at"][1] - top_y, 3)]
            for n in names
        ]

    assert _expected(ctx, "SB03_end_a@1", "holes")["centres"] == front(
        "clamp_hole_1", "clamp_hole_2", "pivot_tap"
    )
    for section in ("SB03_end_a@2", "SB03_end_a@3"):
        assert _expected(ctx, section, "holes")["centres"] == front(
            "clamp_hole_1", "clamp_hole_2"
        )
    for section in ("SB03_end_a@4", "SB03_end_a@5"):
        assert _expected(ctx, section, "holes")["centres"] == front("pivot_tap")
    # Turned over end for end: END A at the left, the bar toward +X.
    pivot = f["pivot_tap"]["at"]
    back = [round(pivot[0] - end_x, 3), round(pivot[1] - top_y, 3)]
    assert _expected(ctx, "SB05_back_csk", "holes")["centres"] == [back]
    assert _expected(ctx, "SB06_tap", "tap_stop")["at"] == back


def test_each_slot_is_cut_to_its_programmed_width_about_its_station(ctx) -> None:
    f = FEATURES["features"]
    end_x, top_y = f["end_a"]["plane"]["value"], f["top_face"]["plane"]["value"]
    p = PLAN["parameters"]
    cutter = p["slot_cutter_dia_mm"]
    through, counterbores = [], []
    for name, check, kwargs in ctx["expect"]:
        if (name, check) == ("SB04_slots", "bounds"):
            deep = kwargs["z_min"] == pytest.approx(p["slot_bottom_mm"])
            (through if deep else counterbores).append(kwargs)
    # Each counterbore by two windows: its +Y straight's line, then its -Y.
    pairs = list(zip(counterbores[::2], counterbores[1::2], strict=True))
    for slot, cut, (upper, lower) in zip(
        ("clamp_slot_3", "clamp_slot_4"), through, pairs, strict=True
    ):
        x = end_x - f[slot]["at"][0]
        y = f[slot]["at"][1] - top_y
        # The cutter-centre envelope plus the cutter: the programmed width
        # across the slot, and the run plus that width along it.
        assert cut["y"][1] - cut["y"][0] + cutter == pytest.approx(p["slot_width_mm"])
        assert sum(cut["y"]) / 2 == pytest.approx(y, abs=1e-3)
        assert sum(cut["x"]) / 2 == pytest.approx(x, abs=1e-3)
        assert cut["x"][1] - cut["x"][0] + cutter == pytest.approx(
            f[slot]["run_nominal"] + p["slot_width_mm"], abs=2e-3
        )
        assert upper["y"] == lower["y"]
        assert upper["y"][1] - upper["y"][0] + cutter == pytest.approx(
            p["slot_cbore_width_mm"]
        )
        assert sum(upper["y"]) / 2 == pytest.approx(y, abs=1e-3)
        assert lower["x"][1] - upper["x"][0] + cutter == pytest.approx(
            f[slot]["run_nominal"] + p["slot_cbore_width_mm"], abs=2e-3
        )
        for cbore in (upper, lower):
            assert cbore["z_min"] == pytest.approx(-f[slot]["cbore_depth_nominal"])
            assert cut["arc"] == cbore["arc"] == "G2"


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_no_slot_lap_ramps_deeper_than_the_plan_declares(ctx) -> None:
    p = PLAN["parameters"]
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for key, step in (
        ("slots", p["slot_step_max_mm"]),
        ("slot_counterbores", p["slot_cbore_step_max_mm"]),
    ):
        z, laps = 0.0, 0
        for line in lines_of[key]:
            if line.startswith("G1 Z"):
                z = float(line.split()[1][1:])  # a new slot's entry at the top
            elif line.startswith("G1 X") and " Z" in line:
                down = float(line.split()[2][1:])
                # Each straight ramps half a lap's step at most.
                assert z - down <= step / 2 + 1e-3, line
                z, laps = down, laps + 1
        assert laps > 0


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("blank_length_min_mm", 450.0, "blank_length_min_mm"),
        ("blank_length_in", 17.7, "blank_length_min_mm"),
        ("top_jaw_clear_mm", 8.0, "top_jaw_clear_mm"),
        ("bar_length_max_mm", 455.0, "bar_length_max_mm"),
        ("height_target_mm", 25.16, "under one level"),
        ("bow_max_mm", 0.2, "more than the narrowest bar's skim"),
        ("end_axial_doc_mm", 9.0, "end_axial_doc_mm"),
        ("spot_dia_mm", 4.0, "under every drill"),
        ("drill_9_tip_mm", -10.0, "drill_9_tip_mm"),
        ("drill_29_tip_mm", -10.0, "drill_29_tip_mm"),
        ("csk_dia_mm", 4.25, "countersink"),
        ("csk_tip_mm", -1.0, "csk_tip_mm"),
        ("slot_width_mm", 5.0, "leaves the band"),
        ("slot_cbore_width_mm", 8.8, "leaves the band"),
        ("slot_cutter_max_mm", 3.3, "slot_cutter_max_mm"),
        ("slot_cbore_radial_mm", 1.0, "slot_cbore_radial_mm"),
        ("slot_bottom_mm", -9.0, "slot_bottom_mm"),
        ("slot_far_station_mm", 440.0, "slot_far_station_mm"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("a_clamp_end_mm", 171.0, "a_clamp_end_mm"),
        ("end_overhang_mm", 40.0, "a_clamp_start_mm"),
        ("pickup_out_mm", 150.0, "top_out_mm"),
        ("z_touch_b_x_mm", -200.0, "z_touch_b_x_mm"),
        ("parallel_thickness_mm", 12.0, "reaches a stack"),
        ("half_mill_projection_mm", 12.0, "1/2 in end mill's collet would reach"),
        ("eighth_mill_projection_min_mm", 9.0, "collet would reach"),
        ("eighth_mill_projection_max_mm", 10.0, "projection band is empty"),
        ("tap_point_depth_mm", 12.0, "tap_point_depth_mm"),
        ("tap_stack_max_mm", 300.0, "tap_stack_max_mm"),
        ("tap_wrench_reach_max_mm", 210.0, "tap_wrench_reach_max_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("constant", "value", "detail"),
    [
        # An edge finder brought up from farther off needs travel SB02 never ran.
        ("PICKUP_APPROACH_MM", 6.0, "SB02 proves"),
        # A wider margin than the sawn blank keeps inside the length band.
        ("LENGTH_MARGIN_MM", 2.0, "inside the length band"),
        # A wider margin than the countersink keeps under the drawing's maximum.
        ("CSK_MARGIN_MM", 0.5, "countersink"),
    ],
)
def test_a_margin_the_plan_does_not_keep_is_refused(
    monkeypatch, constant, value, detail
) -> None:
    monkeypatch.setattr(RECIPE, constant, value)
    with pytest.raises(ValueError, match=detail):
        _context()


def test_a_front_face_a_cut_would_have_to_finish_is_refused() -> None:
    # No program cuts F: its finish must be one the bar's skin meets as supplied.
    features = copy.deepcopy(FEATURES)
    del features["features"]["front_face"]["finish_process"]
    with pytest.raises(ValueError, match="front_face"):
        RECIPE.context(features, PLAN, SHOP, "bar.step")


def _seed(ctx: dict, key: str, changes: dict[str, str]) -> dict:
    """``ctx`` with the first line of operation ``key`` equal to each key of
    ``changes`` replaced by its value."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    for old, new in changes.items():
        lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "changes", "check"),
    [
        # The first face pass moved onto the edge's middle: a full-width cut.
        ("top_face", {"G0 X-462.534 Y1.338": "G0 X-462.534 Y-4.763"}, "face"),
        # END A's first pass moved onto the second: it takes two steps.
        ("end_a", {"G0 X7.493 Y-34.112": "G0 X7.112 Y-34.112"}, "passes"),
        # END A's first pass run the other way: climb, not conventional.
        (
            "end_a",
            {
                "G0 X7.493 Y-34.112": "G0 X7.493 Y8.890",
                "G1 Y8.890 F{feed}": "G1 Y-34.112 F{feed}",
            },
            "engagement",
        ),
        # A clamp hole drilled short of its exit.
        ("clamp_drill", {"G1 Z-12.021 F{feed}": "G1 Z-5.000 F{feed}"}, "holes"),
        # A counterbore fed past its depth.
        ("counterbore", {"G1 Z-4.826 F{feed}": "G1 Z-6.000 F{feed}"}, "holes"),
        # The pivot hole drilled over the stack at the fixed jaw.
        ("pivot_drill", {"G0 X-168.060 Y-14.500": "G0 X-100.000 Y-1.500"}, "keep_out"),
        # A slot's half circle turned the other way: climb on the wall.
        (
            "slots",
            {
                "G2 X-404.063 Y-14.940 I0.000 J-0.940 F{feed}": "G3 X-404.063 Y-14.940 I0.000 J-0.940 F{feed}"
            },
            "bounds",
        ),
        # A slot's last level lap run wide: the slot cut over its width.
        (
            "slots",
            {"G1 X-404.063 Z-10.025 F{feed}": "G1 X-404.063 Y-12.900 Z-10.025 F{feed}"},
            "bounds",
        ),
        # A counterbore lap ramped through its floor.
        (
            "slot_counterbores",
            {"G1 X-404.063 Z-0.121 F{feed}": "G1 X-404.063 Z-5.500 F{feed}"},
            "bounds",
        ),
        # A counterbore's level lap lifted: its floor left as the ramp cut it.
        (
            "slot_counterbores",
            {"G1 X-404.063 Z-4.826 F{feed}": "G1 X-404.063 Z-4.700 F{feed}"},
            "cleared",
        ),
        # The back countersink fed past the drawing's maximum.
        ("back_csk", {"G1 Z-2.007 F{feed}": "G1 Z-2.300 F{feed}"}, "holes"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, changes, check
) -> None:
    seeded = _seed(ctx, key, changes)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


@pytest.mark.parametrize(
    ("old", "new"),
    [
        # The guide lowered by the file, not by the operator's jog.
        ("M30", "G0 Z5.000\nM30"),
        # The file left holding at an M0: FluidNC refuses the jog there.
        ("M30", "M0"),
        # The guide brought over another hole.
        ("G0 X168.060 Y-14.500", "G0 X46.558 Y-14.000"),
    ],
)
def test_a_seeded_fault_in_the_tap_stop_is_caught(ctx, tmp_path, old, new) -> None:
    seeded = copy.deepcopy(ctx)
    gcode = seeded["manual"]["tap"]["gcode"]
    at = gcode.index(old)
    gcode[at : at + 1] = new.split("\n")
    _post(seeded, tmp_path)
    assert "tap_stop" in {finding.check for finding in _findings(seeded, tmp_path)}

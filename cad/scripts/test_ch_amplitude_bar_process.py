"""The amplitude bar's CAM recipe agrees with its model and plan.

``cad/process/ch_amplitude_bar/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
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
import _shop_equipment
import cam_nc
import export_features

STEM = "ch_amplitude_bar"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "bar.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section its lines, the feeds in mm/min, after an M6 block (M5, the
    operator's %msg, M6) where the tool changes or the program loads its
    first tool; a manual section (the saw's witness-line stop) is its own
    lines, and the section after it restarts the spindle on its M3."""
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
                assert manual["tool"] == previous, "a stop on the tool running"
                text += manual["gcode"]
                continue
            job = sections[key]
            number = ctx["numbers"][job["tool"]]
            if number != previous and (
                previous is not None or name in RECIPE.LOAD_FIRST_TOOL
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
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _lines(ctx: dict, key: str) -> list[str]:
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


def test_context_numbers_the_tools_and_places_the_cuts(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "saw": 2,
        "spot": 3,
        "drill-49": 4,
        "reamer-0775": 5,
    }
    assert set(RECIPE.LOAD_FIRST_TOOL) == {
        "CA00_riser_face",
        "CA01_foot_end",
        "CA03_top_end",
        "CA05_pin_hole",
    }
    # The saw's two levels per notch: the ledge, then the far wall less the
    # saw's thickness: the foot notch the band's middle wide, the top notch
    # .126 (a .062 rise, half its least width, so its kerfs overlap).
    levels = {
        key: sorted({line for line in _lines(ctx, key) if line.startswith("G1 Z")})
        for key in ("foot_notch", "top_notch")
    }
    assert levels == {
        "foot_notch": ["G1 Z1.854 F{feed}", "G1 Z2.946 F{feed}"],
        "top_notch": ["G1 Z1.600 F{feed}", "G1 Z3.175 F{feed}"],
    }
    # Four pin holes .25 in from the top end, one per bar, a pitch apart.
    holes = next(
        kwargs["centres"]
        for program, check, kwargs in ctx["expect"]
        if program.startswith("CA05") and check == "holes"
    )
    assert holes == [
        [-6.35, -3.175],
        [-6.35, -9.5],
        [-6.35, -15.824],
        [-6.35, -22.149],
    ]


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_saw_is_mounted_and_moved_only_where_its_arbor_clears(ctx) -> None:
    p = PLAN["parameters"]
    # CA01 and CA03 leave T1 parked over the touch-off station, past the
    # ends on the saw's side: up, then X, then Y.
    for key, side in (("foot_end", -1), ("top_end", 1)):
        assert _lines(ctx, key)[-3:] == [
            f"G0 Z{p['saw_park_z_mm']:.3f}",
            f"G0 X{side * p['saw_touch_x_mm']:.3f}",
            "G0 Y-3.162",
        ]
    # The saw rises straight up from the touch-off before any X or Y move,
    # and moves between passes at that height (down to the pass only beside
    # the load, 1 mm over the bars' top).
    for key in ("foot_light", "foot_notch", "top_light", "top_notch"):
        lines = _lines(ctx, key)
        assert lines[0] == f"G0 Z{p['saw_clear_z_mm']:.3f}"
        assert {line for line in lines if line.startswith("G0 Z")} == {
            lines[0],
            "G0 Z7.350",
        }


def test_the_saw_runs_on_the_owned_arbor_as_its_record_gives_it() -> None:
    # The arbor's sizes in the plan are the inventory record's (inches there),
    # the saw's hole its own record's; nothing of the arbor that was to buy
    # (its spacers, its nut) is left in the plan.
    inventory = _shop_equipment.load()["tools"]
    record = inventory["saw-arbor-r8-stepped"]
    p = PLAN["parameters"]
    assert record["status"] == "on_hand" and record["keyed"] is False
    for key, field in (
        ("saw_arbor_body_dia_mm", "body_dia_above_saw_in"),
        ("saw_arbor_cap_dia_mm", "cap_dia_in"),
        ("saw_arbor_cap_thickness_mm", "cap_thickness_in"),
        ("saw_arbor_screw_head_dia_mm", "screw_head_dia_in"),
        ("saw_arbor_nose_to_cap_mm", "below_spindle_nose_in"),
    ):
        assert p[key] == pytest.approx(record[field] * 25.4, abs=1e-4), key
    # The thread, its engagement and the clamp torque are the record's.
    assert p["saw_clamp_torque_nm"] == record["clamp_torque_nm"]
    assert record["screw_thread"].startswith(f"M{p['saw_screw_dia_mm']:g} x ")
    assert (
        p["saw_screw_engagement_no_saw_mm"] == record["screw_engagement_no_saw_mm"]
    )
    assert p["saw_bore_mm"] == pytest.approx(
        inventory["slitting-saw-2-75-064"]["bore_in"] * 25.4
    )
    arbor = next(tool for tool in PLAN["tools"] if tool["id"] == "saw-arbor")
    assert arbor["ref"] == "saw-arbor-r8-stepped"
    # The arbor that was to buy is no tool of the plan, and its limits are no
    # parameters of it.
    assert "gear-cutter-arbor-1" not in {tool["ref"] for tool in PLAN["tools"]}
    for gone in (
        "saw_collar_dia_max_mm",
        "saw_spacer_below_min_mm",
        "saw_nut_dia_max_mm",
    ):
        assert gone not in p, gone


def test_each_saw_program_stops_after_a_light_pass_for_the_witness_lines(
    ctx, tmp_path
) -> None:
    p = PLAN["parameters"]
    # The light pass: one level, half a step into the ends, at the ledge.
    for key, x, z in (
        ("foot_light", p["foot_notch_light_mm"] - p["saw_dia_mm"] / 2, "1.854"),
        ("top_light", p["saw_dia_mm"] / 2 - p["top_notch_light_mm"], "1.600"),
    ):
        lines = _lines(ctx, key)
        assert [line for line in lines if line.startswith("G1 Z")] == [
            f"G1 Z{z} F{{feed}}"
        ]
        assert sum(line.startswith(f"G0 X{x:.3f} Y") for line in lines) == 1
    # Then M5, the operator's %msg and M0; the rest restarts on its own M3.
    _post(ctx, tmp_path)
    for name in ("CA02_foot_notch", "CA04_top_notch"):
        text = (tmp_path / f"{name}.nc").read_text(encoding="utf-8").splitlines()
        stop = text.index("M0")
        assert text.count("M0") == 1 and "M6" not in " ".join(text)
        assert text[stop - 2] == "M5" and "WITNESS LINES" in text[stop - 1]
        assert text[stop + 1] == "M3 S100"
        assert sum(line.startswith("G1 Y") for line in text[:stop]) == 1


def test_a_pass_past_the_arbors_reach_is_caught_at_the_bars_ends(ctx, tmp_path) -> None:
    # The top notch's deepest pass stationed 7 mm further in than its depth:
    # the cap below the saw and the body above it meet the bars' ends.
    seeded = _seed(
        ctx,
        "top_notch",
        lambda line: line.startswith("G0 X20.955 Y"),
        lambda line: line.replace("X20.955", "X14.000"),
    )
    _post(seeded, tmp_path)
    found = [f.detail for f in _findings(seeded, tmp_path) if f.check == "keep_out"]
    for part in ("the arbor's cap below the saw", "the arbor's body above the saw"):
        assert any(f"the bars' ends ({part})" in detail for detail in found), part
    assert not any("the cap's screw head" in detail for detail in found)


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"top_excess_max_mm": 2.0}, "top_excess_max_mm"),
        (
            {"blank_length_in": 31.83, "blank_length_min_mm": 808.482},
            "under the length",
        ),
        ({"bar_pitch_mm": 6.35}, "bar_pitch_mm"),
        ({"load_width_mm": 12.6492}, "load_width_mm"),
        ({"riser_width_max_mm": 25.2}, "narrowest load"),
        ({"riser_width_min_mm": 22.8}, "half its width"),
        ({"bars_per_load": 5, "load_width_mm": 31.623}, "half its width"),
        ({"riser_chamfer_mm": 1.6}, "quarter of the first bar"),
        ({"riser_length_max_mm": 80.0}, "longer than the jaws"),
        ({"foot_notch_width_mm": 2.6416}, "foot_notch_width_mm"),
        # The old .128 target: two .064 saw widths, a .064 rise the least
        # accepted saw does not cover.
        ({"top_notch_width_mm": 3.2512}, "leaves a fin"),
        ({"top_notch_depth_mm": 14.224}, "top_notch_depth_mm"),
        ({"top_notch_step_mm": 3.4925}, "top_notch_step_mm"),
        ({"end_protrusion_mm": 14.0}, "top notch's depth"),
        ({"saw_arbor_cap_dia_mm": 44.45}, "saw_depth_past_arbor_max_mm"),
        (
            {"saw_arbor_body_dia_mm": 44.45, "saw_depth_past_arbor_max_mm": 11.7},
            "top notch's deepest limit 14.224 passes the arbor's reach",
        ),
        ({"saw_arbor_screw_head_dia_mm": 31.75}, "not inside the cap"),
        ({"drill_tip_height_mm": -0.5}, "drill_tip_height_mm"),
        ({"spot_dia_mm": 1.9}, "under the #49"),
        ({"top_clamp_end_mm": 19.05}, "top_clamp_end_mm"),
        ({"half_mill_projection_min_mm": 19.0}, "jaw tops"),
        ({"drill_projection_mm": 20.0}, "jaw tops"),
        ({"spot_projection_mm": 20.0}, "holder_grip_min_mm"),
        ({"riser_height_min_mm": 0}, "riser_height_min_mm"),
        ({"seat_offset_max_mm": 0.0254}, "ledge's budget"),
        ({"saw_touch_error_mm": 0.0254}, "ledge's budget"),
        ({"saw_touch_error_mm": 0.0127}, "saw_touch_error_mm is finer"),
        ({"seat_measure_mm": 0.00254}, "seat_measure_mm is finer"),
        ({"saw_touch_step_mm": 0.0254}, "saw_touch_error_mm is finer"),
        ({"sweep_zero_return_mm": 0.005}, "seat_measure_mm is finer"),
        ({"riser_blank_spread_max_mm": 0.127}, "riser_blank_spread_max_mm"),
        ({"riser_face_overhang_mm": -50.0}, "riser_face_overhang_mm"),
        ({"riser_parallel_height_mm": 38.1}, "to grip"),
        ({"riser_parallel_height_mm": 12.7}, "over the jaw tops"),
        ({"saw_below_max_mm": 12.7}, "saw_below_max_mm"),
        ({"saw_clear_z_mm": 11.35}, "saw_clear_z_mm"),
        ({"saw_proof_raise_mm": 20.0}, "air proof"),
        (
            {
                "saw_screw_head_stand_max_mm": 1.27,
                "saw_below_max_mm": 13.97,
                "saw_clear_z_mm": 25.32,
            },
            "not the largest the air proof tolerates",
        ),
        ({"saw_arbor_below_nose_mm": 36.0}, "nose-to-cap distance plus the saw"),
        ({"saw_arbor_length_mm": 38.1}, "saw_arbor_length_mm"),
        ({"saw_touch_x_mm": 31.9}, "saw_touch_x_mm"),
        ({"saw_touch_y_mm": -3.0}, "saw_touch_y_mm"),
        ({"saw_park_z_mm": 17.75}, "saw_park_z_mm"),
        ({"saw_clamp_preload_kn": 2.0}, "saw_drive_torque_max_nm"),
        ({"saw_screw_engagement_no_saw_mm": 9.0}, "under one screw diameter"),
        (
            {"saw_clamp_preload_kn": 2.0, "saw_drive_torque_max_nm": 4.02},
            "over the arbor's friction drive",
        ),
        ({"saw_feed_per_min_mm": 365.76}, "not the .001 in/tooth"),
        ({"saw_swept_margin_mm": 0.0508}, "saw_swept_max_mm"),
        ({"foot_notch_rise_mm": 1.0}, "foot_notch_rise_mm"),
        ({"top_saw_radial_tir_max_mm": 0.6}, "top_saw_radial_tir_max_mm"),
        ({"saw_axial_reading_per_in_mm": 25.4}, "saw_axial_reading_per_in_mm"),
        ({"saw_axial_nominal_mm": 0.07}, "saw_axial_nominal_mm"),
        ({"foot_notch_light_mm": 2.1273}, "foot_notch_light_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(changes, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"].update(changes)
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change) -> dict:
    """``ctx`` with the first line of operation ``key`` that ``pick`` accepts
    replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, key)
    index = next(i for i, line in enumerate(lines) if pick(line))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "check"),
    [
        # The top end's last pass left short of the length.
        (
            "top_end",
            lambda line: line.startswith("G0 X6.350"),
            lambda line: line.replace("X6.350", "X6.604"),
            "passes",
        ),
        # A saw pass run the climb way (-Y with the saw right of the ends).
        (
            "top_notch",
            lambda line: line.startswith("G1 Y"),
            lambda line: "G1 Y-100.000 F{feed}",
            "passes",
        ),
        # The foot end's pass run +Y, the ends on the end mill's right:
        # climb, where the recipe declares conventional (#3680).
        (
            "foot_end",
            lambda line: line.startswith("G1 Y"),
            lambda line: "G1 Y60.000 F{feed}",
            "cut",
        ),
        # The deepest pass started over the load instead of beside it: the
        # saw comes down flat onto the bars' tops.
        (
            "top_notch",
            lambda line: line.startswith("G0 X20.955 Y"),
            lambda line: "G0 X20.955 Y-6.000",
            "keep_out",
        ),
        # The saw lowered to its level in a rapid.
        (
            "foot_notch",
            lambda line: line.startswith("G1 Z1.854"),
            lambda line: "G0 Z1.854",
            "rapid",
        ),
        # A pin hole drilled between the jaws, down into the riser.
        (
            "pin_drill",
            lambda line: line.startswith("G0 X-6.350 Y"),
            lambda line: line.replace("X-6.350", "X-25.000"),
            "keep_out",
        ),
        # The riser faced down beside the jaws instead of over them.
        (
            "riser_face",
            lambda line: line == "G1 Z-0.127 F{feed}",
            lambda line: "G1 Z-8.000 F{feed}",
            "keep_out",
        ),
        # A pin hole drilled short of the down face.
        (
            "pin_drill",
            lambda line: line == "G1 Z-1.057 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

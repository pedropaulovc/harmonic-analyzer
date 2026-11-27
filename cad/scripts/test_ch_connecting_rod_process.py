"""The connecting rod's CAM recipe agrees with its model and plan.

``cad/process/ch_connecting_rod/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
them, and seeded faults show each check catches what it guards.
"""

from __future__ import annotations

import copy
import re
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import _shop_equipment
import cam_nc
import export_features

STEM = "ch_connecting_rod"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "rod.step")


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
        "em-eighth": 2,
        "spot": 3,
        "drill-49": 4,
        "reamer-0775": 5,
        "saw": 6,
    }
    holes = {
        program: (kwargs["centres"], kwargs["z_bottom"])
        for program, check, kwargs in ctx["expect"]
        if check == "holes"
    }
    # The pin holes on the crowns' centres, a blank's width apart; the #49's
    # full diameter .5 mm and the reamer's 1.0 mm past face D.
    assert holes["CR07_pin@1"] == ([[181.866, -25.4], [181.866, -76.2]], -1.057)
    assert holes["CR07_pin@2"][1] == -1.0
    # Seven tabs per rod, each .060 thick on the shank's near face; the
    # outline in three levels.
    outline = next(
        kw for p, c, kw in ctx["expect"] if p == "CR08_outline@0" and c == "outline"
    )
    assert len(outline["tabs"]) == 14
    assert {(t["top"], t["floor"], t["thickness"]) for t in outline["tabs"]} == {
        (2.794, 1.27, 1.524)
    }
    assert outline["passes"] == [{"offset": 1.5875, "levels": [3.387, 2.201, 1.016]}]
    # The saw's two heights, each three steps into the crowns: a step is what
    # the arbor's friction drive carries with its reserve.
    saw = next(
        kw for p, c, kw in ctx["expect"] if p == "CR06_slot" and c == "side_passes"
    )
    assert (saw["final"], saw["raw"]) == (207.012, 221.744)
    assert saw["max_step"] == pytest.approx(14.732 / 3)
    # The end trim: two passes of 1/16 in from the longest blank's end to the
    # crowns, each 6.6 mm deep, on the measured deep setting.
    trim = next(
        kw for p, c, kw in ctx["expect"] if p == "CR04a_end_trim" and c == "side_passes"
    )
    assert (
        trim["final"],
        trim["raw"],
        trim["max_step"],
        trim["direction"],
        trim["max_stepdown"],
    ) == (193.169, 196.342, 1.5865, 1, 6.6)


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_saw_is_mounted_and_moved_only_where_its_arbor_clears(ctx) -> None:
    p = PLAN["parameters"]
    # CR05 leaves T1 parked over the touch-off station: up, then X, then Y.
    assert _lines(ctx, "bore")[-3:] == [
        f"G0 Z{p['saw_park_z_mm']:.3f}",
        f"G0 X{p['saw_touch_x_mm']:.3f}",
        "G0 Y-25.400",
    ]
    # CR06 rises straight up from the touch-off before any X or Y move, and
    # moves between passes at that height (down to a pass only beside the
    # load, 1 mm over the stock top).
    for key in ("slot_light", "slot"):
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


def test_the_slot_program_stops_after_a_light_pass_for_the_witness_lines(
    ctx, tmp_path
) -> None:
    p = PLAN["parameters"]
    # The light pass: half a step into the crowns at the near tine's wall;
    # then three steps at each level, none over the step the drive carries.
    crown = p["crown_x_mm"] + p["saw_dia_mm"] / 2
    light = _lines(ctx, "slot_light")
    assert [line for line in light if line.startswith("G1 Z")] == ["G1 Z1.702 F{feed}"]
    assert sum(
        line.startswith(f"G0 X{crown - p['slot_light_mm']:.3f} Y") for line in light
    ) == 1
    stations = [
        float(line.split()[1][1:])
        for line in _lines(ctx, "slot")
        if line.startswith("G0 X")
    ]
    assert stations == pytest.approx(
        [crown - k * p["slot_step_mm"] for k in (1, 2, 3)] * 2, abs=1e-3
    )
    # Then M5, the operator's %msg and M0; the rest restarts on its own M3.
    _post(ctx, tmp_path)
    text = (tmp_path / "CR06_slot.nc").read_text(encoding="utf-8").splitlines()
    stop = text.index("M0")
    assert text.count("M0") == 1 and "M6" not in " ".join(text)
    assert text[stop - 2] == "M5" and "WITNESS LINES" in text[stop - 1]
    assert text[stop + 1] == "M3 S100"
    assert sum(line.startswith("G1 Y") for line in text[:stop]) == 1


def test_a_pass_past_the_arbors_reach_is_caught_at_the_forks(ctx, tmp_path) -> None:
    # The slot's deepest pass stationed 7 mm further in than its depth: the
    # cap below the saw and the body above it meet the blanks' ends.
    seeded = _seed(
        ctx,
        "slot",
        lambda line: line.startswith("G0 X207.012 Y"),
        lambda line: line.replace("X207.012", "X200.000"),
    )
    _post(seeded, tmp_path)
    found = [f.detail for f in _findings(seeded, tmp_path) if f.check == "keep_out"]
    for part in ("the arbor's cap below the saw", "the arbor's body above the saw"):
        assert any(
            f"the blanks past the plate ({part})" in detail for detail in found
        ), part


def test_the_eighth_cutter_leaves_the_shank_corners_inside_their_limits() -> None:
    """Owner ruling 2026-11-23, tool audit Q9: the 1/8 in end mill's R.0625
    is the shank's four corners, printed R.065 (.060-.070), and no 5/64 in
    end mill recuts them; a print whose limits shut that radius out stops
    the recipe."""
    lo, hi = FEATURES["features"]["shank_right_flank"]["corner_r"]
    assert (lo, hi) == pytest.approx((0.060 * 25.4, 0.070 * 25.4))
    assert "em-5-64" not in RECIPE.CAM_TOOLS
    assert "em-5-64" not in {tool["id"] for tool in PLAN["tools"]}
    features = copy.deepcopy(FEATURES)
    features["features"]["shank_right_flank"]["corner_r"] = [0.889, 1.016]
    with pytest.raises(ValueError, match="outside the shank corners' limits"):
        RECIPE.context(features, PLAN, SHOP, "rod.step")


_PLATE_OUTLINE = re.compile(
    r'<path class="hidden" d="M([\d.]+) ([\d.]+)H([\d.]+)V([\d.]+)H\1Z"/>'
)
_TOP_SCALE = re.compile(r"(?:both views|from above) at ([\d.]+) px/mm")
_BLANK = re.compile(
    r'<rect class="part-rest" x="([\d.]+)" y="([\d.]+)" width="[\d.]+" '
    r'height="([\d.]+)"/>'
)


@pytest.mark.parametrize(
    "picture",
    [
        "face_f",
        "face_f-band",
        "face_d",
        "face_d-band",
        "face_f_finish",
        "face_f_finish-band",
        "outline",
        "fork",
    ],
)
def test_the_top_views_draw_the_support_plate_at_its_size(picture) -> None:
    """#3729: each top view's hidden support plate is the plate's milled
    width across the jaws and its length along X, at the scale the picture
    states, centred across the load of two blanks."""
    p = PLAN["parameters"]
    svg = (
        _process_plans.plan_path(STEM).parent / "diagrams" / f"{picture}.svg"
    ).read_text(encoding="utf-8")
    scale = float(_TOP_SCALE.search(svg).group(1))
    (outline,) = _PLATE_OUTLINE.findall(svg)
    x0, y0, x1, y1 = map(float, outline)
    assert x1 - x0 == pytest.approx(p["support_plate_length_mm"] * scale, abs=0.01)
    assert y1 - y0 == pytest.approx(p["support_plate_width_mm"] * scale, abs=0.01)
    # The top view's two blanks start at X0, the plate's left edge.
    blanks = [
        (float(y), float(y) + float(h))
        for x, y, h in _BLANK.findall(svg)
        if float(x) == x0
    ]
    assert len(blanks) == 2
    load_middle = (min(b[0] for b in blanks) + max(b[1] for b in blanks)) / 2
    assert (y0 + y1) / 2 == pytest.approx(load_middle, abs=0.05)


def test_each_setup_places_the_pair_by_blank_number() -> None:
    """#3728: loads are paired by thickness and all wait between Setups 2
    and 3, so each holding names which number goes against the fixed jaw:
    the lower in Setups 2 and 4, the higher in Setup 3 (the pair turned over
    as one stack). Each setup's step that clamps the next pair repeats it,
    and Setups 2 and 3 keep the unclamped load's two together."""
    face_f, face_d, finish_f = PLAN["setups"][1:4]
    outline = PLAN["setups"][5]
    assert "the lower number against the fixed jaw" in face_f["holding"]
    assert "the higher number against the fixed jaw" in face_d["holding"]
    assert "the lower number against the fixed jaw" in finish_f["holding"]

    def unclamp(setup: dict) -> str:
        (step,) = [
            op["instruction"]
            for op in setup["operations"]
            if op["instruction"].startswith("Unclamp the load")
        ]
        return step

    for setup, number in ((face_f, "lower"), (face_d, "higher")):
        assert "keep its two together" in unclamp(setup)
        assert f"{number} number against the fixed jaw" in unclamp(setup)
    assert (
        "Clamp the next pair as in Setup 4, its lower number against the fixed jaw"
        in unclamp(outline)
    )


_NUMBER_LABEL = re.compile(
    r'<text class="label" x="[\d.]+" y="([\d.]+)" text-anchor="middle">([12])</text>'
)
_FIXED_JAW = re.compile(
    r'<text class="[\w-]+" x="[\d.]+" y="([\d.]+)" text-anchor="middle">fixed jaw</text>'
)


@pytest.mark.parametrize(
    ("picture", "at_fixed_jaw"),
    [
        ("face_f", "1"),
        ("face_f-band", "1"),
        ("face_d", "2"),
        ("face_d-band", "2"),
        ("face_f_finish", "1"),
        ("face_f_finish-band", "1"),
        ("fork", "1"),
        ("outline", "1"),
    ],
)
def test_the_top_views_label_the_pair_by_its_numbers(picture, at_fixed_jaw) -> None:
    """#3728: a top view's 1 and 2 are the pair's lower and higher numbers,
    so the label at the fixed jaw is 1 in Setups 2 and 4-6 and 2 in Setup 3
    (the pair turned over as one stack)."""
    svg = (
        _process_plans.plan_path(STEM).parent / "diagrams" / f"{picture}.svg"
    ).read_text(encoding="utf-8")
    fixed_y = float(_FIXED_JAW.search(svg).group(1))
    labels = {text: float(y) for y, text in _NUMBER_LABEL.findall(svg)}
    assert set(labels) == {"1", "2"}
    nearer = min(labels, key=lambda text: abs(labels[text] - fixed_y))
    assert nearer == at_fixed_jaw


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"fork_thickness_mm": 6.2}, "fork_thickness_mm"),
        ({"crown_x_mm": 186.0}, "crown_x_mm"),
        ({"slot_floor_x_mm": 171.0}, "slot_floor_x_mm"),
        # The reamer's tip 0.42 past the far face: its .0070 in chamfer plus
        # the 0.25 margin is 0.428 (cnc.ream-full-diameter).
        ({"ream_past_mm": 0.42}, "full diameter does not reach the far face"),
        ({"saw_arbor_cap_dia_mm": 44.45}, "saw_depth_past_arbor_max_mm"),
        (
            {"saw_arbor_body_dia_mm": 44.45, "saw_depth_past_arbor_max_mm": 11.7},
            "fork slot's deepest limit 14.986 passes the arbor's reach",
        ),
        ({"saw_arbor_screw_head_dia_mm": 31.75}, "not inside the cap"),
        ({"saw_touch_y_mm": -25.0}, "saw_touch_y_mm"),
        ({"fork_touch_z_mm": 6.096}, "fork_touch_z_mm"),
        ({"tab_top_mm": 2.54}, "tab_top_mm"),
        ({"tab_station_7_mm": 162.5}, "tab_station_7_mm"),
        ({"outline_level_mm": 0.889}, "outline_level_mm"),
        ({"web_d_finish_mm": 3.302}, "web_d_finish_mm"),
        ({"slot_mid_x_mm": 172.087}, "slot_mid_x_mm"),
        ({"jaw_start_mm": 20.0}, "jaw_end_mm"),
        # The support plate's milled width (#3652, D44): its middle, under
        # the narrowest pair, onto the moving parallel on the widest, and the
        # width op's grip on edge.
        ({"support_plate_width_mm": 99.06}, "support_plate_width_mm"),
        (
            {
                "support_plate_width_mm": 101.15,
                "support_plate_width_min_mm": 100.9,
                "support_plate_width_max_mm": 101.4,
            },
            "grip the support plate",
        ),
        (
            {
                "support_plate_width_mm": 98.6,
                "support_plate_width_min_mm": 98.4,
                "support_plate_width_max_mm": 98.8,
            },
            "misses the moving parallel",
        ),
        ({"edge_shim_height_mm": 12.7}, "less than the shop's fraction"),
        # The blanks' width gate: 1.992 leaves the outer frame 1.38 mm.
        ({"blank_width_min_mm": 50.5968}, "blank 2's frame beside the ring"),
        ({"ring_from_end_mm": 22.0}, "left end by its margin"),
        ({"spot_dia_mm": 2.0}, "under the #49"),
        ({"tab_top_3_x_mm": 142.0}, "off the shank's flanks"),
        (
            {"blank_length_in": 7.36, "blank_length_min_mm": 186.944},
            "right end by its margin",
        ),
        ({"saw_below_max_mm": 25.4}, "saw_below_max_mm"),
        ({"saw_clear_z_mm": 11.35}, "saw_clear_z_mm"),
        ({"saw_below_plate_top_mm": 12.7}, "saw_below_plate_top_mm"),
        (
            {
                "saw_screw_head_stand_max_mm": 5.08,
                "saw_below_max_mm": 17.78,
                "saw_clear_z_mm": 29.13,
            },
            "under the stock top in CR06's air proof",
        ),
        (
            {
                "saw_screw_head_stand_max_mm": 1.27,
                "saw_below_max_mm": 13.97,
                "saw_clear_z_mm": 25.32,
            },
            "not the largest the air proof tolerates",
        ),
        ({"saw_arbor_below_nose_mm": 36.0}, "nose-to-cap distance plus the saw"),
        ({"saw_arbor_length_mm": 76.2}, "saw_arbor_length_mm"),
        ({"saw_park_z_mm": 40.61}, "saw_park_z_mm"),
        ({"saw_clamp_preload_kn": 2.0}, "saw_drive_torque_max_nm"),
        ({"saw_screw_engagement_no_saw_mm": 9.0}, "under one screw diameter"),
        # The slot in two steps a level: a step over the drive's reserve.
        (
            {"slot_step_max_mm": 7.5, "slot_step_mm": 7.366, "slot_light_mm": 3.683},
            "takes 13.1 N·m, over the arbor's friction drive",
        ),
        ({"saw_feed_per_min_mm": 365.76}, "not the .001 in/tooth"),
        ({"saw_swept_margin_mm": 0.0508}, "slot_saw_swept_max_mm"),
        (
            {"saw_swept_margin_mm": -0.0127, "slot_saw_swept_max_mm": 1.6891},
            "far tine under its band",
        ),
        ({"slot_rise_mm": 1.0}, "slot_rise_mm"),
        ({"slot_saw_radial_tir_max_mm": 0.6}, "slot_saw_radial_tir_max_mm"),
        ({"saw_axial_reading_per_in_mm": 25.4}, "saw_axial_reading_per_in_mm"),
        ({"slot_saw_axial_nominal_mm": 0.07}, "slot_saw_axial_nominal_mm"),
        ({"slot_light_mm": 7.366}, "slot_light_mm"),
        ({"end_trim_run_past_mm": 0.254}, "thickest blank plus its run-past"),
        ({"end_trim_step_mm": 2.0}, "even step"),
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
        # A tab cut through: the hop's lift left at the level below it.
        (
            "outline",
            lambda line: line == "G1 Z2.794 F{feed}",
            lambda line: "G1 Z2.201 F{feed}",
            "outline",
        ),
        # The first blank's shank band left .012 high at the rough floor.
        (
            "rough_2",
            lambda line: line == "G1 Z5.080 F{plunge}",
            lambda line: "G1 Z5.380 F{plunge}",
            "cleared",
        ),
        # The fork's face not skimmed.
        (
            "rough_2",
            lambda line: line == "G1 Z6.096 F{feed}",
            lambda line: "G1 Z6.350 F{feed}",
            "cleared",
        ),
        # The #49 stopped short of face D.
        (
            "pin_drill",
            lambda line: line == "G1 Z-1.057 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # The reamer rapided out of the hole.
        (
            "pin_ream",
            lambda line: line == "G1 Z7.096 F{feed}",
            lambda line: "G0 Z7.096",
            "feed_out",
        ),
        # The saw's first pass below the near tine's wall.
        (
            "slot",
            lambda line: line == "G1 Z1.702 F{feed}",
            lambda line: "G1 Z1.400 F{feed}",
            "depth",
        ),
        # The saw's deepest pass started over the load instead of beside it:
        # the saw comes down flat onto the blanks.
        (
            "slot",
            lambda line: line.startswith("G0 X207.012 Y"),
            lambda line: "G0 X207.012 Y-30.000",
            "keep_out",
        ),
        # The end trim's first pass skipped: the crown pass takes the whole
        # excess, past the measured width.
        (
            "end_trim",
            lambda line: line == "G0 X194.755 Y-110.490",
            lambda line: "G0 X193.169 Y-110.490",
            "passes",
        ),
        # The end trim run deeper than its declared depth.
        (
            "end_trim",
            lambda line: line == "G1 Z-0.250 F{feed}",
            lambda line: "G1 Z-0.500 F{feed}",
            "depth",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

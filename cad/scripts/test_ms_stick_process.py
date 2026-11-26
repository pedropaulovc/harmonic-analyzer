"""The stick's CAM recipe agrees with its model, plan, shop and inventory.

``cad/process/ms_stick/cam.py`` writes every path itself; its ``context``
runs here on the drawing's requirement manifest (the features the stick's
export binds) with no FreeCAD and no SolidWorks, and refuses any plan number
that disagrees with the model, the shop or the holding. The posted programs
are stood in for by the recipe's own section lines under the grbl post's
tool-change block, so every check the recipe declares runs on them, and
seeded faults show each check catches what it guards. The STEP solid the
recipe probes inside FreeCAD is stood in for by ``ms_stick_spec``'s own tick
layout and the numeral generator's strokes, which the recipe never reads.
"""

from __future__ import annotations

import copy
import math
import tomllib
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pytest

import _cam_programs
import _process_plans
import _shop_equipment
import cam_nc
import export_features
import gen_ms_stick_numerals_dxf as numeral_generator
import ms_stick_callouts as callouts
import ms_stick_spec as spec

STEM = "ms_stick"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
EQUIPMENT = _shop_equipment.load()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
LAST_TICK = (spec.DIVISION_COUNT - 1) * spec.MINOR_PER_DIVISION


def _context(plan: dict = PLAN, features: dict = FEATURES) -> dict:
    return RECIPE.context(features, plan, SHOP, "stick.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min."""
    sections = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, keys in RECIPE.PROGRAMS:
        text = [
            f"({name})",
            f"({ctx['comment']})",
            "(Begin preamble)",
            "G17 G90",
            "G21",
            "G54",
        ]
        for key in keys:
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
    assert ctx["numbers"] == {"em-half": 1, "engraver": 2}
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    assert ctx["manual"] == {}
    assert len(ctx["ticks"]) == LAST_TICK + 1
    assert ctx["numerals"] == spec.DIVISION_COUNT
    instructions = " ".join(
        op.get("instruction", "")
        for setup in PLAN["setups"]
        for op in setup.get("operations", ())
    )
    for name, _ops in RECIPE.PROGRAMS:
        assert name in instructions


def test_every_tick_is_cut_at_the_drawings_station(ctx) -> None:
    """Sheet 2's station table prints each graduation's distance from the end
    face nearest the 10; the recipe's X0 is that face and the stick lies
    toward -X."""
    for tick in ctx["ticks"]:
        assert spec.inch_text(-tick["x"], 3) == callouts.station_x_text(tick["index"])
    kinds = {tick["index"]: tick["kind"] for tick in ctx["ticks"]}
    half = PLAN["parameters"]["half_tick_index"]
    # The model's one long tenth: build_ms_stick's "tick 0.5".
    assert half * spec.MINOR_SPACING == pytest.approx(spec.DIVISION_SPACING / 2)
    assert [k for k, kind in kinds.items() if kind == "half"] == [half]
    assert [k for k, kind in kinds.items() if kind == "full"] == list(
        range(0, LAST_TICK + 1, spec.MINOR_PER_DIVISION)
    )


def test_the_plan_repeats_the_shop_inventory() -> None:
    p = PLAN["parameters"]
    grads = FEATURES["features"]["graduations"]
    bit = EQUIPMENT["tools"]["engravers-esao-30-0-1"]
    assert p["engraver_tip_mm"] == pytest.approx(bit["tip_width_mm"])
    assert bit["included_angle_deg"] == grads["v_angle_deg"]
    # The Tools table's line for the bit is the inventory's bit.
    described = SHOP["tools"]["engravers-esao-30-0-1"]["description"]
    assert bit["make"] in described
    assert f"{bit['included_angle_deg']:g}°" in described
    assert f"{bit['tip_width_mm']:g} mm" in described
    # One strip of the hold's tape covers the bar's top (no seam): the plan
    # tapes each face with a single strip trimmed to width.
    hold = EQUIPMENT["consumables"]["hold-painters-tape-ca"]
    tape = EQUIPMENT["consumables"][hold["tape"]]
    assert tape["width_mm"] > p["fixture_width_mm"] > p["blank_width_max_mm"]
    bar = EQUIPMENT["stock"]["6061-flat-1-2x1-12in"]
    assert [p["fixture_height_mm"], p["fixture_width_mm"]] == bar["section_mm"]
    assert p["fixture_length_mm"] == bar["length_mm"]
    brass = EQUIPMENT["stock"]["c360-flat-1-8x3-8"]
    width, thickness = brass["section_mm"]
    assert p["blank_width_min_mm"] < width < p["blank_width_max_mm"]
    assert thickness == FEATURES["features"]["back_face"]["thickness_nominal"]
    assert p["blank_length_max_mm"] < brass["length_mm"]
    assert set(PLAN["stock_refs"]) == {"c360-flat-1-8x3-8", "6061-flat-1-2x1-12in"}


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}
    # The run times the traveler states.
    p = PLAN["parameters"]
    for name, key in (
        ("MS03_graduations", "graduations_run_min"),
        ("MS04_numerals", "numerals_run_min"),
    ):
        assert times[name].total <= p[key] <= times[name].total + 3


def test_the_engraving_cuts_run_the_scales_length() -> None:
    """The plan's engraving cuts traverse from the 0 tick to the 10 tick,
    along model X from the zero end."""
    grads = FEATURES["features"]["graduations"]
    length = FEATURES["features"]["zero_end"]["length_nominal"]
    span = [
        length - grads["zero_station_nominal"],
        length - grads["ten_station_ref"],
    ]
    cuts = {
        cut["name"]: cut
        for setup in PLAN["setups"]
        for op in setup.get("operations", ())
        for cut in op.get("milling_cuts", ())
    }
    for name in ("graduations", "numerals"):
        assert cuts[name]["traverse_mm"] == pytest.approx(span)


def test_the_fixture_bar_holds_under_the_screening_load(ctx) -> None:
    limit = PLAN["parameters"]["fixture_deflection_max_mm"]
    assert set(ctx["bends"]) == {"down", "across"}
    assert 0 < ctx["bends"]["down"] < ctx["bends"]["across"] <= limit


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("tick_depth_mm", 0.9, "tick_width_mm"),
        ("numeral_depth_mm", 0.7, "numeral_width_mm"),
        ("engrave_depth_margin_mm", 0.3, "inside the graduations' depth"),
        ("engrave_step_max_mm", 0.1, "engrave_step_max_mm"),
        ("tick_rough_levels", 5, "do not make"),
        ("engrave_slow_feed_per_min_mm", 71.12, "engrave_slow_feed_per_min_mm"),
        ("half_tick_index", 4, "half_tick_index"),
        ("numeral_gap_min_mm", 0.5, "numeral_gap_min_mm"),
        ("outline_step_mm", 0.3, "outline_levels × outline_step_mm"),
        ("outline_breakthrough_mm", 0.3, "outline_depth_mm"),
        ("outline_end_stations", 5, "outline_end_stations"),
        ("blank_width_max_mm", 9.9, "outline_radial_max_mm"),
        ("blank_length_in", 7.9, "zero end of the shortest blank"),
        ("fixture_skim_max_mm", 0.1, "fixture_skim_max_mm"),
        ("tape_stack_min_mm", 0.05, "thinnest tape stack"),
        ("tape_stack_mm", 0.4, "tape_stack_min_mm..tape_stack_max_mm"),
        ("fixture_length_mm", 609.6, "fixture_overhang_mm"),
        ("fixture_check_load_n", 500.0, "fixture_deflection_max_mm"),
        ("fixture_face_woc_mm", 5.0, "fixture_face_woc_mm"),
        ("parallel_height_mm", 12.7, "fixture_raw_proud_mm"),
        ("fixture_proud_mm", 5.8547, "fixture_proud_mm"),
        ("fixture_grip_mm", 25.4, "fixture_grip_mm"),
        ("ruled_edge_y_mm", 8.7, "ruled_edge_y_mm"),
        ("datum_find_x_mm", 3.4, "datum_find_x_mm"),
        ("edge_finder_radius_mm", 3.0, "datum_find_x_mm"),
        ("blank_scribe_in", 8.05, "blank_scribe_in"),
        ("fixture_clamp_end_mm", 240.0, "fixture_clamp_end_mm"),
        ("tick_rough_depth_mm", 0.7, "tick_rough_depth_mm"),
        ("jaw_clearance_min_mm", 6.0, "jaw_clearance_min_mm"),
        ("vise_jaw_height_mm", 50.8, "vise-pm-6"),
        ("bond_area_mm2", 1700.0, "bond_area_mm2"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


@pytest.mark.parametrize(
    ("feature", "key", "value", "detail"),
    [
        # The 0 tick moved off its printed station.
        ("graduations", "zero_station_nominal", 146.43, "outside its band"),
        # The pitch no longer lands the last tick on the 10's reference.
        ("graduations", "minor_pitch", 1.4, "ten_station_ref"),
        ("graduations", "open_to", "plain_edge", "open to the ruled edge"),
        ("graduations", "count", 100, "whole divisions"),
        # Narrower limits than the plan's depth holds.
        ("graduations", "width", [0.4064, 0.5334], "inside the graduations' depth"),
        ("numerals", "height", [1.778, 2.2], "inside the numerals' depth"),
        # The stroke layers are not the ones the export measured.
        ("numerals", "x_span", [57.2112, 196.7888], "ink box"),
        ("numerals", "v_angle_deg", 60.0, "V angles differ"),
    ],
)
def test_a_feature_off_the_recipes_frame_is_refused(
    feature, key, value, detail
) -> None:
    features = copy.deepcopy(FEATURES)
    features["features"][feature][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(features=features)


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
        # The second facing pass set short of the bar's front face.
        ("fixture_face", "G1 Y-9.525 F{feed}", "G1 Y-8.000 F{feed}", "face"),
        # The front edge pass fed across to a line inside the stick's width.
        (
            "outline",
            "G1 X-214.852 Y-15.113 F{feed}",
            "G1 X-214.852 Y-14.613 F{feed}",
            "keep_out",
        ),
        # Two levels taken at once: 1.08 MPa of lift on the stick's edge,
        # over the 0.6 MPa the shop accepts for the bond.
        ("outline", "G1 Z-1.128 F{feed}", "G1 Z-2.256 F{feed}", "passes"),
        # The last level cut past the stack: into the fixture bar deeper than
        # the skim under the thinnest blank on the thinnest stack.
        ("outline", "G1 Z-3.384 F{feed}", "G1 Z-3.600 F{feed}", "keep_out"),
        # A pass of the last level left short of the tape.
        ("outline", "G1 Z-3.384 F{feed}", "G1 Z-3.100 F{feed}", "holes"),
        # The 0 tick .002 off its station.
        ("graduations", "G0 X-145.430 Y-9.513", "G0 X-145.380 Y-9.513", "cleared"),
        # The 0 tick left under its depth.
        ("graduations", "G1 Z-0.762 F{feed}", "G1 Z-0.700 F{feed}", "cleared"),
        # A tenth cut as long as a numbered tick.
        ("graduations", "G1 Y-7.239 F{feed}", "G1 Y-5.969 F{feed}", "keep_out"),
        # Three levels taken at once.
        ("graduations", "G1 Z-0.119 F{feed}", "G1 Z-0.356 F{feed}", "passes"),
        # A rapid down into the brass instead of to the R plane.
        ("graduations", "G0 Z0.500", "G0 Z-0.200", "rapid"),
        # A stroke of the 0 off its line.
        (
            "numerals",
            "G1 X-144.599 Y-4.782 F{feed}",
            "G1 X-144.899 Y-4.782 F{feed}",
            "keep_out",
        ),
        # The 0's last level left under its depth.
        ("numerals", "G1 Z-0.533 F{plunge}", "G1 Z-0.400 F{plunge}", "cleared"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}


def test_a_climb_pass_is_caught(ctx, tmp_path) -> None:
    """The first rear edge pass run the other way: the stick on its right.
    The pass line first, so the entry's feed across is the line's first match."""
    seeded = ctx
    for line, fault in (
        ("G1 X-214.852 Y5.588 F{feed}", "G1 X9.112 Y5.588 F{feed}"),
        ("G1 X9.112 Y5.588 F{feed}", "G1 X-214.852 Y5.588 F{feed}"),
        ("G0 X9.112 Y8.350", "G0 X-214.852 Y8.350"),
    ):
        seeded = _seed(seeded, "outline", line, fault)
    _post(seeded, tmp_path)
    found = {finding.check for finding in _findings(seeded, tmp_path)}
    assert found >= {"passes", "engagement"}


def _outline_entries(ctx: dict) -> list[list[float]]:
    """Where MS02 plunges: the recipe's ``holes`` expectation."""
    (holes,) = [
        kwargs
        for name, check, kwargs in RECIPE.expectations(ctx)
        if name == "MS02_outline" and check == "holes"
    ]
    return holes["centres"]


def test_every_outline_pass_is_entered_off_the_fixture_bar(ctx) -> None:
    """The last level reaches the tape and, under a thin blank, the fixture
    bar's top. Every plunge of MS02 stands with the whole cutter behind the
    bar's rear face (Y0) or in front of its front face; the blank lies
    inside the bar's width."""
    p = PLAN["parameters"]
    radius = p["face_cutter_dia_mm"] / 2
    entries = _outline_entries(ctx)
    assert len(entries) == p["outline_end_stations"] + 3
    assert p["blank_width_max_mm"] <= p["fixture_width_mm"]
    for _x, y in entries:
        assert y - radius > 0 or y + radius < -p["fixture_width_mm"]


def test_the_outline_diagram_draws_the_posted_entries(ctx) -> None:
    """Setup 3's picture shows where MS02 comes down: the end mill at the
    datum-end pass's entry, and every drawn pass starting at its posted
    entry (of the zero-end passes it draws the last). The scale and origins
    are the picture's own: 10 px/mm, Y0 at px 150, X0 at px 650 right of the
    break, the longest blank's left end (X−206.5) at px 125 left of it."""

    def px(x: float, y: float) -> tuple[float, float]:
        return (650 + 10 * x if x > -100 else 125 + 10 * (x + 206.5), 150 - 10 * y)

    radius = PLAN["parameters"]["face_cutter_dia_mm"] / 2
    entries = [tuple(entry) for entry in _outline_entries(ctx)]
    zero_end = [entry for entry in entries if entry[0] < 0 < entry[1]]
    drawn = [max(zero_end), *(entry for entry in entries if entry not in zero_end)]
    (datum,) = [entry for entry in drawn if entry[0] > 0 > entry[1]]
    svg = ElementTree.parse(
        _process_plans.plan_path(STEM).parent / "diagrams" / "outline.svg"
    ).getroot()
    shapes = {
        kind: [e for e in svg.iter(f"{{http://www.w3.org/2000/svg}}{kind}")]
        for kind in ("circle", "line")
    }
    (cutter,) = [e for e in shapes["circle"] if e.get("class") == "cutter"]
    assert [float(cutter.get(k)) for k in ("cx", "cy", "r")] == pytest.approx(
        [*px(*datum), 10 * radius], abs=0.06
    )
    starts = [
        (float(e.get("x1")), float(e.get("y1")))
        for e in shapes["line"]
        if e.get("class") == "arrow"
    ]
    for entry in drawn:
        assert any(start == pytest.approx(px(*entry), abs=0.06) for start in starts), (
            entry
        )


def test_the_registration_band_is_the_edge_finders_radius() -> None:
    """Op 230 reads the edge finder back on the datum end: its console band
    is the offset Ops 50, 130 and 190 enter, the finder's radius, ±0.025."""
    radius = PLAN["parameters"]["edge_finder_radius_mm"]
    bands = [
        check["band_mm"]
        for setup in PLAN["setups"]
        for op in setup["operations"]
        if isinstance(op.get("gauge_checks"), list)
        for check in op["gauge_checks"]
        if check["gauge"] == "mill-x-dro"
    ]
    assert bands == [pytest.approx([radius - 0.025, radius + 0.025])]


def _model(
    half_index: int = spec.MINOR_PER_DIVISION // 2,
    reversed_end_for_end: bool = False,
    mirrored_across: bool = False,
):
    """Whether a point of the recipe's stick frame lies in the metal of the
    stick ``ms_stick_spec`` describes (``build_ms_stick``'s ticks, the numeral
    generator's strokes), or in a variant of it."""
    rects = [ring for numeral in numeral_generator.numeral_rects() for ring in numeral]
    slope = math.tan(math.radians(spec.ENGRAVING_V_INCLUDED_ANGLE_DEG / 2))
    trim = PLAN["parameters"]["outline_trim_mm"]

    def inside(point) -> bool:
        x, y, depth = point[0] + spec.BODY_LENGTH, -point[1] - trim, -point[2]
        if reversed_end_for_end:
            x = spec.BODY_LENGTH - x
        if mirrored_across:
            y = spec.BODY_WIDTH - y
        if not (
            0 <= x <= spec.BODY_LENGTH
            and 0 <= y <= spec.BODY_WIDTH
            and 0 <= depth <= spec.BODY_THICKNESS
        ):
            return False
        k = round((x - spec.SCALE_START_X) / spec.MINOR_SPACING)
        if 0 <= k <= LAST_TICK:
            length = (
                spec.TICK_LENGTH
                if k % spec.MINOR_PER_DIVISION == 0
                else spec.HALF_TICK_LENGTH
                if k == half_index
                else spec.MINOR_TICK_LENGTH
            )
            off_centre = abs(x - spec.SCALE_START_X - k * spec.MINOR_SPACING)
            if (
                depth < spec.TICK_DEPTH
                and off_centre < spec.TICK_WIDTH / 2 - depth * slope
                and y > spec.BODY_WIDTH - length + depth * slope
            ):
                return False
        cut = numeral_generator._depth_field(rects, np.array([x]), np.array([y]))
        return depth >= cut[0]

    return inside


def test_the_model_is_engraved_where_the_recipe_engraves(ctx) -> None:
    points = ctx["probe"]
    assert len(points["air"]) > LAST_TICK + 1 and len(points["metal"]) == 2 * (
        LAST_TICK + 1
    )
    RECIPE.probe(_model(), points)


@pytest.mark.parametrize(
    "variant",
    [
        {"half_index": 15},
        {"reversed_end_for_end": True},
        {"mirrored_across": True},
    ],
)
def test_a_model_engraved_elsewhere_stops_the_build(ctx, variant) -> None:
    with pytest.raises(RuntimeError, match="not engraved where the recipe engraves"):
        RECIPE.probe(_model(**variant), ctx["probe"])

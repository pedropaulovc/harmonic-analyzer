"""The platen's CAM recipe agrees with its model, plan and shop.

``cad/process/pd_platen/cam.py`` writes every path itself; its ``context``
runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD, no SolidWorks and no feature
bundle, and refuses any plan number that disagrees with the model, the shop
or the holding. The posted programs are stood in for by the recipe's own
section lines under the grbl post's tool-change block, so every check the
recipe declares runs on them, and seeded faults show each check catches what
it guards.
"""

from __future__ import annotations

import copy
import re
import tomllib
from fractions import Fraction
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "pd_platen"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
EQUIPMENT = Path(__file__).resolve().parents[1] / "config" / "shop-equipment"


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "platen.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and every one of
    its operations' lines, the feeds in mm/min; a tap stop's lines after its
    M6, ending with its M30."""
    jobs = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    for name, groups in RECIPE.PROGRAMS:
        text = [
            f"({name})",
            f"({ctx['comment']})",
            "(Begin preamble)",
            "G17 G90",
            "G21",
            "G54",
        ]
        flat = all(isinstance(group, str) for group in groups)
        sections = [groups] if flat else groups
        for section in sections:
            if section[0] in ctx["manual"]:
                manual = ctx["manual"][section[0]]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
            job = jobs[section[0]]
            assert [op[0] for op in job["ops"]] == list(section)
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
                    for op in job["ops"]
                    for line in op[2]
                ),
            ]
        if not any(section[0] in ctx["manual"] for section in sections):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def _centres(ctx: dict, program: str) -> list[list[float]]:
    return next(
        kwargs["centres"]
        for name, check, kwargs in ctx["expect"]
        if name == program and check == "holes"
    )


def test_context_numbers_the_tools_and_makes_every_hole_from_one_zero(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-50": 3,
        "drill-27": 4,
        "em-quarter": 5,
        "tap-guide": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    features = FEATURES["features"]

    # Work X is the model's, work Y minus the model's: the plate is cut paper
    # face up, the drawing's bottom edge at the back. Each group in the
    # drawing's order, by station then height (A1-A4, B1-B10).
    def work(prefix: str) -> list[list[float]]:
        at = sorted(
            (f["at"][0], f["at"][1])
            for name, f in features.items()
            if name.startswith(prefix)
        )
        return [[round(x, 3), round(-y, 3)] for x, y in at]

    sockets, guides = work("socket_"), work("guide_")
    assert (len(sockets), len(guides)) == (4, 10)
    assert _centres(ctx, "PL04_platen@1") == sorted(sockets + guides)
    assert _centres(ctx, "PL04_platen@2") == sockets
    assert _centres(ctx, "PL04_platen@3") == guides
    assert _centres(ctx, "PL04_platen@4") == guides
    # The relief pockets in the bar sit under the sockets, from the same zero.
    assert _centres(ctx, "PL02_bar_relief") == sockets
    taps = [ctx["manual"][f"tap_{k}"] for k in range(1, 5)]
    assert [stop["at"] for stop in taps] == sockets
    for stop in taps:
        assert stop["tool"] == 6
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_fixture_bar_and_blank_are_the_shop_equipment_records() -> None:
    bought = tomllib.loads(
        (EQUIPMENT / "stock-bought.toml").read_text(encoding="utf-8")
    )["stock"]
    p = PLAN["parameters"]
    bar = bought["6061-flat-1-2x6-18in"]
    assert [p["bar_width_mm"], p["bar_thickness_mm"]] == bar["section_mm"]
    assert p["bar_length_mm"] == bar["length_mm"]
    blank = bought["c360-flat-1-4x6"]
    assert [p["blank_width_in"] * 25.4, p["blank_thickness_in"] * 25.4] == (
        pytest.approx(blank["section_mm"])
    )
    assert p["blank_length_in"] * 25.4 == pytest.approx(blank["length_mm"])
    assert PLAN["stock_refs"] == ["c360-flat-1-4x6", "6061-flat-1-2x6-18in"]
    consumables = tomllib.loads(
        (EQUIPMENT / "consumables.toml").read_text(encoding="utf-8")
    )["consumables"]
    hold = consumables["hold-painters-tape-ca"]
    assert p["tape_strip_width_mm"] == consumables[hold["tape"]]["width_mm"]
    assert [p["tape_stack_min_mm"], p["tape_stack_mm"], p["tape_stack_max_mm"]] == [
        hold["stack_min_mm"],
        hold["stack_thickness_mm"],
        hold["stack_max_mm"],
    ]


def _inch_fraction(mm: float) -> str:
    """``mm`` as the sheet prints a strip length: whole inches and a fraction."""
    inches = Fraction(mm / 25.4).limit_denominator(16)
    whole, rest = divmod(inches, 1)
    return f"{whole} {rest.numerator}/{rest.denominator}" if rest else f"{whole}"


def test_the_printed_strip_lengths_are_the_plans_keys() -> None:
    """Every bond's printed strip lengths are tape_bar_strip_length_mm and
    tape_blank_strip_length_mm, so a changed key cannot leave stale text."""
    p = PLAN["parameters"]
    expected = {
        "bar": _inch_fraction(p["tape_bar_strip_length_mm"]),
        "blank": _inch_fraction(p["tape_blank_strip_length_mm"]),
    }
    patterns = {
        "bar": re.compile(
            r"(\d+(?: \d+/\d+)?) in strips (?:of the 1\.41 in tape|on the bar)"
        ),
        "blank": re.compile(
            r"(\d+(?: \d+/\d+)?) in (?:strips along the blank's length|on face [BP])"
        ),
    }
    texts = [
        op.get("instruction", "")
        for setup in PLAN["setups"]
        for op in setup["operations"]
    ]
    for face, pattern in patterns.items():
        printed = [length for text in texts for length in pattern.findall(text)]
        # Setup 3 spells the bond out; Setups 4, 5 and 6 repeat it.
        assert printed == [expected[face]] * 4, face


def test_the_recipes_programs_pass_every_check_they_declare(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("length_target_mm", 269.64, "length_target_mm"),
        ("thickness_target_mm", 3.85, "thickness_target_mm"),
        ("blank_width_min_mm", 146.0, "fits the vise"),
        ("blank_length_min_mm", 276.0, "left margin|right margin"),
        ("placement_tol_mm", 4.0, "margin"),
        ("x0_from_bar_left_mm", 88.9, "x0_from_bar_left_mm"),
        ("y_set_mm", -143.637, "y_set_mm"),
        ("face_z_set_mm", 0.6223, "face_z_set_mm"),
        ("z_touch_y_mm", -122.174, "z_touch_y_mm"),
        ("z_touch_inset_in", 0.3, "overhangs the blank"),
        ("z_leaf_mm", 0.0254, "z_leaf_mm"),
        ("faced_z_set_mm", 3.8608, "faced_z_set_mm"),
        ("edge_x_set_mm", 2.54, "edge_x_set_mm"),
        ("edge_y_set_mm", -2.54, "edge_y_set_mm"),
        ("third_cut_max_mm", 4.7, "third_cut_max_mm"),
        ("final_face_doc_max_mm", 0.6223, "final_face_doc_max_mm"),
        ("face_cut_mm", 0.78, "face_z_set_mm"),
        ("seat_right_mm", 279.4, "seat_right_mm"),
        ("clamp_zone_mm", 80.0, "step clamp"),
        ("outline_breakthrough_mm", 0.08, "skin"),
        ("outline_breakthrough_mm", 0.25, "reaches the bar"),
        ("tape_stack_min_mm", 0.20, "thickness band"),
        ("outline_axial_doc_mm", 3.9408, "outline_axial_doc_mm"),
        ("tape_strip_count", 4, "bare"),
        ("tape_seam_offset_mm", 35.814, "quarter strip"),
        ("tape_seam_gap_max_mm", 10.0, "bridge"),
        ("tape_end_overhang_mm", 1.0, "bare"),
        ("tape_bar_strip_length_mm", 292.1, "past the longest blank"),
        ("tape_bar_strip_length_mm", 305.0, "skimmed seat"),
        ("tape_blank_strip_length_mm", 279.4, "longest blank bare"),
        ("bond_patch_area_mm2", 12740.17, "bond_patch_area_mm2"),
        ("spot_dia_mm", 1.8, "under the #50"),
        ("socket_tip_height_mm", -0.5, "socket_tip_height_mm"),
        ("guide_tip_height_mm", -1.0, "guide_tip_height_mm"),
        ("relief_depth_mm", 2.5, "relief pocket"),
        ("cbore_orbit_mm", 0.254, "cbore_orbit_mm"),
        ("cbore_floor_height_mm", 0.929, "cbore_floor_height_mm"),
        ("tap_point_depth_mm", 3.9878, "tap_point_depth_mm"),
        ("block_height_mm", 12.7, "does not reach"),
        ("tap_stack_max_mm", 400.0, "tap_stack_max_mm"),
        ("tap_wrench_reach_max_mm", 300.0, "tap_stack_max_mm"),
        ("drill_projection_max_mm", 400.0, "drill chuck"),
        ("spot_feed_per_min_mm", 711.2, "spot_feed_per_min_mm"),
        ("socket_drill_feed_per_min_mm", 213.36, "socket_drill_feed_per_min_mm"),
        ("guide_drill_feed_per_min_mm", 71.12, "guide_drill_feed_per_min_mm"),
        ("bar_skim_feed_per_min_mm", 89.6112, "bar_skim_feed_per_min_mm"),
        ("plunge_feed_per_min_mm", 533.4, "plunge_feed_per_min_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_a_drill_that_is_not_its_holes_size_is_refused() -> None:
    shop = copy.deepcopy(SHOP)
    shop["tools"]["drill-27"]["diameter_mm"] = 3.5718  # 9/64 in
    with pytest.raises(ValueError, match="#27"):
        RECIPE.context(FEATURES, PLAN, shop, "platen.step")


def _lines(ctx: dict, key: str) -> list[str]:
    if key in ctx["manual"]:
        return ctx["manual"][key]["gcode"]
    return next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)


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
        # The bar skim run on past its patch, into the right step clamps.
        (
            "bar_skim",
            lambda line: line == "G1 X288.226 F{feed}",
            lambda line: "G1 X310.000 F{feed}",
            "keep_out",
        ),
        # A relief pocket plunged beside its socket station.
        (
            "relief",
            lambda line: line == "G0 X4.318 Y-58.442",
            lambda line: "G0 X14.318 Y-58.442",
            "holes",
        ),
        # The first face pass moved onto the blank's middle: a full-width slot.
        (
            "face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-67.437",
            "face",
        ),
        # The last face left above the thickness.
        (
            "thickness",
            lambda line: line == "G1 Z3.861 F{feed}",
            lambda line: "G1 Z4.200 F{feed}",
            "face",
        ),
        # The left edge's first pass dropped: the second takes both steps.
        (
            "edges",
            lambda line: line == "G0 X-10.710 Y20.511",
            lambda line: "G0 X-8.657 Y20.511",
            "passes",
        ),
        # A right-edge pass stopped short of the back corner.
        (
            "edges",
            lambda line: line == "G1 Y20.511 F{feed}",
            lambda line: "G1 Y-20.000 F{feed}",
            "passes",
        ),
        # The through cut taken down into the bar.
        (
            "edges",
            lambda line: line == "G1 Z-0.152 F{feed}",
            lambda line: "G1 Z-0.300 F{feed}",
            "depth",
        ),
        # A socket drilled short of its exit.
        (
            "socket_drill",
            lambda line: line == "G1 Z-1.034 F{feed}",
            lambda line: "G1 Z0.500 F{feed}",
            "holes",
        ),
        # A guide hole drilled off its station.
        (
            "guide_drill",
            lambda line: line == "G0 X26.975 Y-14.056",
            lambda line: "G0 X27.975 Y-14.056",
            "holes",
        ),
        # A counterbore's circle run anticlockwise (climb).
        (
            "cbore",
            lambda line: line.startswith("G2 "),
            lambda line: "G3 " + line[3:],
            "bounds",
        ),
        # A counterbore opened too wide.
        (
            "cbore",
            lambda line: line == "G1 X27.102 F{feed}",
            lambda line: "G1 X27.302 F{feed}",
            "bounds",
        ),
        # A counterbore cut through the floor.
        (
            "cbore",
            lambda line: line == "G1 Z0.940 F{plunge}",
            lambda line: "G1 Z-0.100 F{plunge}",
            "holes",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        ("tap_3", lambda line: line == "M30", lambda line: "M0", "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, pick, change, check
) -> None:
    seeded = _seed(ctx, key, pick, change)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


def test_an_edge_pass_wider_than_the_plans_step_is_caught(ctx, tmp_path) -> None:
    """Stations alone would pass a first pass that meets the whole margin:
    with the front edge's first three passes gone the fourth meets all of it."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, "edges")
    front = [i for i, line in enumerate(lines) if line.startswith("G0 Y-1")]
    assert len(front) == 5
    del lines[front[0] : front[3]]
    _post(seeded, tmp_path)
    assert {"engagement", "passes"} <= {
        finding.check for finding in _findings(seeded, tmp_path)
    }


def test_an_edge_pass_run_the_other_way_is_caught(ctx, tmp_path) -> None:
    """The right edge's first pass from the back corner toward the operator:
    the plate on the cutter's right, a climb cut."""
    seeded = copy.deepcopy(ctx)
    lines = _lines(seeded, "edges")
    start = lines.index("G0 X282.877 Y-154.114")
    cut = lines.index("G1 Y20.511 F{feed}", start)
    lines[start] = "G0 X282.877 Y20.511"
    lines[cut] = "G1 Y-154.114 F{feed}"
    _post(seeded, tmp_path)
    assert {"engagement", "passes"} <= {
        finding.check for finding in _findings(seeded, tmp_path)
    }


def test_the_counterbore_depth_band_reaches_the_bundle_and_the_plan() -> None:
    """The drawing bands the depth on its callout's own variable
    (draw_pd_platen._print_counterbore_depth_band); the features bundle
    declares the same CBORE_DEPTH_BAND for every guide hole
    (draw_pd_platen's requirement fields), and the plan's inspection and the
    CAM read their limits from that bundle, never from a typed number."""
    import pd_platen_spec as spec

    upper, lower = spec.CBORE_DEPTH_BAND
    expected = [spec.CBORE_DEPTH + lower, spec.CBORE_DEPTH + upper]
    guides = {
        name: feature
        for name, feature in FEATURES["features"].items()
        if name.startswith("guide_b")
    }
    assert len(guides) == 10
    for name, feature in guides.items():
        assert feature["cbore_depth"] == pytest.approx(expected, abs=1e-6), name
    plan = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
    assert (
        "counterbore depth {{cad.guide_b1_cbore_depth_min_in:.3dot}}–"
        "{{cad.guide_b1_cbore_depth_max_in:.3dot}} from P"
    ) in plan
    assert 'band_mm = "{{cad.guide_b1_cbore_depth_band_mm}}"' in plan
    # Comments may name the nominal; no instruction or check types a limit.
    lines = [line for line in plan.splitlines() if not line.lstrip().startswith("#")]
    assert not [line for line in lines if re.search(r"\.11[05]\b|\.120\b", line)]

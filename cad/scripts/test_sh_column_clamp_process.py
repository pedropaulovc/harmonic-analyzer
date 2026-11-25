"""The column clamp pair's family plan and its one CAM recipe agree with
both halves' models.

``cad/process/sh_column_clamp/plan.toml`` is one prechips family plan for
MHA-SH-01 (front) and MHA-SH-02 (back) and ``cam.py`` beside it posts every
program of the pair once (owner rulings 2026-11-24): neither half has a plan
or a recipe of its own. The recipe writes every path itself; its ``context``
runs here on both drawings' requirement manifests (the features the
``clamp_half`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with a model, the shop or the holding, and
any difference between the two halves' shared CC programs. The posted programs are stood in for by the recipe's
own section lines under the grbl post's tool-change block, so every check
the recipe declares runs on them, and seeded faults show each check catches
what it guards.
"""

from __future__ import annotations

import copy
import os
import re
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "sh_column_clamp"
PARTS = {"front": "sh_column_clamp_front", "back": "sh_column_clamp_back"}
SHOP = _process_plans.load_shop()
PLAN_TEXT = _process_plans.plan_path(STEM).read_text(encoding="utf-8")
PLAN = tomllib.loads(PLAN_TEXT)
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = {
    half: export_features.requirement_manifest(part) for half, part in PARTS.items()
}
STEPS = {half: f"{half}.step" for half in PARTS}
PROGRAMS = tuple(name for name, _ops in RECIPE.PROGRAMS)


def _views(plan: dict | None = None) -> dict:
    return {half: _process_plans.part_view(plan or PLAN, half) for half in PARTS}


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, _views(plan), SHOP, STEPS)


@pytest.fixture(scope="module")
def context() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's lines after its M6, ending with its M30."""
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
        for key in keys:
            if key in ctx["manual"]:
                manual = ctx["manual"][key]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
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
        if not any(key in ctx["manual"] for key in keys):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_the_family_is_the_enrolled_plan_and_recipe_of_both_halves() -> None:
    assert _process_plans.family_parts(STEM) == PARTS
    assert _process_plans.part_stems(STEM) == tuple(PARTS.values())
    assert STEM in _process_plans.TRAVELER_STEMS and STEM in _cam_programs.CAM_STEMS
    for part in PARTS.values():
        # No plan, recipe, task or nc/ directory under a half's own name.
        assert part not in _process_plans.TRAVELER_STEMS
        assert part not in _cam_programs.CAM_STEMS
        # (A leftover __pycache__ from an older checkout is not a plan.)
        for name in ("plan.toml", "cam.py"):
            assert not (_process_plans.PROCESS_ROOT / part / name).exists()
    # The shared sheet once, then a placeholder under each half's own name.
    assert [path.name for path in _process_plans.traveler_pdf_paths(STEM)] == [
        "sh-column-clamp-traveler.pdf",
        "sh-column-clamp-front-traveler.pdf",
        "sh-column-clamp-back-traveler.pdf",
    ]
    inputs = _cam_programs.cam_inputs(STEM)
    assert {name for name in inputs if "/sh_" in name} == {
        f"{kind}/{part}" for kind in ("features", "step") for part in PARTS.values()
    }


def test_one_tool_number_means_one_tool_in_every_file(context) -> None:
    assert context["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-9": 3,
        "drill-29": 4,
        "tap-guide": 5,
    }
    assert context["numbers"] == {
        tool["id"]: tool["number"] for tool in PLAN["tools"] if "number" in tool
    }
    assert RECIPE.LOAD_FIRST_TOOL == PROGRAMS
    # Every file's M6 calls are checked against those numbers.
    called = {
        program: kwargs["tools"]
        for program, check, kwargs in context["expect"]
        if check == "tool_changes"
    }
    assert called["CF06_bar_drill"] == [1, 2, 3]
    assert called["CB06_back_drill"] == [1, 2, 4]
    for stop in context["manual"].values():
        assert stop["tool"] == 5
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"
    # The sheet says the same numbers wherever it names an M6.
    setups = PLAN_TEXT[PLAN_TEXT.index("[[setups]]") :]
    assert set(re.findall(r"M6 T(\d)", setups)) == {"1", "2", "3", "4", "5"}
    for number, tool in (("3", "#9 drill"), ("4", "#29 drill"), ("5", "the tap guide")):
        assert all(
            tool in sentence for sentence in re.findall(rf"M6 T{number}[^.]*\.", setups)
        )


def test_both_halves_holes_come_from_one_zero_at_the_near_side(context) -> None:
    # The front's from its right end (-X), the back's from its left (+X), at
    # the same stations.
    front_holes = next(
        kwargs["centres"]
        for program, check, kwargs in context["expect"]
        if program.startswith("CF06") and check == "holes"
    )
    back_holes = [context["manual"][key]["at"] for key in ("back.tap_1", "back.tap_2")]
    assert [[-x, y] for x, y in front_holes] == back_holes


def test_the_shared_programs_are_posted_once_and_cut_every_blank_alike(context) -> None:
    assert PROGRAMS[:4] == tuple(RECIPE.SHARED)
    keys = [op[0] for job in context["jobs"] for op in job["ops"]]
    assert len(keys) == len(set(keys))
    assert [key for key in keys if "." not in key] == list(RECIPE.SHARED.values())
    # A skim one half takes deeper than the other: each half is consistent
    # in itself, so only the comparison of their shared programs can refuse.
    plan = copy.deepcopy(PLAN)
    back = next(part for part in plan["parts"] if part["id"] == "back")
    back["parameters"]["bottom_skim_mm"] = PLAN["parameters"]["bottom_skim_mm"] + 0.1
    with pytest.raises(ValueError, match="derive different programs"):
        _context(plan)


def test_no_touch_off_is_taken_with_the_work_stop_between_the_jaws() -> None:
    # CodeRabbit, 2026-11-24: the rod left locked from the setup before can
    # lie under the end mill when it comes down beside the blank for Z0. No
    # posted program's keep-out covers a hand move, so every mill setup opens
    # with the rod drawn back, and the stop is set only after its touch-offs.
    drawn_back = "rod drawn back clear of the vise"
    mill = [setup for setup in PLAN["setups"] if setup.get("programs")]
    assert len(mill) == 9
    first_blank = "Before the first blank goes in"
    setup_3 = next(s for s in mill if s["title"] == "Other end to the width")
    for key in ("instruction", "instruction_detailed"):
        assert first_blank in setup_3["operations"][0][key], key
    for setup in mill:
        operations = setup["operations"]
        touches = [
            index
            for index, operation in enumerate(operations)
            if "G54" in operation["instruction"]
            or "touch-off" in operation["instruction"]
        ]
        first = operations[touches[0]]
        # Both texts: the hobby sheet prints the detailed one where an op has
        # it, the pro sheet the short one.
        for key in ("instruction", "instruction_detailed"):
            assert drawn_back in first.get(key, drawn_back), (setup["title"], key)
        stops = [
            index
            for index, operation in enumerate(operations)
            if operation.get("tool") == "work-stop"
        ]
        if setup["title"].startswith("Deburr, then the pair bore"):
            assert not stops
            for key in ("instruction", "instruction_detailed"):
                assert "No work stop" in first.get(key, "No work stop")
            continue
        (stop,) = stops
        # Every zero of the setup is taken before the stop goes in.
        zeros = [
            index
            for index, operation in enumerate(operations)
            if re.search(r"G54 [XZ]0|Repeat Setup \d's", operation["instruction"])
        ]
        assert zeros and max(zeros) < stop, setup["title"]


def test_a_rewrite_inside_one_clock_tick_is_read_again(tmp_path) -> None:
    # Codjiflo, 2026-11-25: the parse was cached on the file's mtime, which a
    # rewrite inside one clock tick keeps.
    plan = tmp_path / "pair" / "plan.toml"
    plan.parent.mkdir()
    row = '[[parts]]\nid = "a"\nfile = "../../out/features/{}/features.toml"\n'
    plan.write_text(row.format("p_a"), encoding="utf-8")
    stamp = plan.stat()
    assert _process_plans.family_parts("pair", tmp_path) == {"a": "p_a"}
    plan.write_text(row.format("p_b"), encoding="utf-8")
    os.utime(plan, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert _process_plans.family_parts("pair", tmp_path) == {"a": "p_b"}


def test_a_depth_remedy_puts_z0_back_only_after_the_file_has_drilled() -> None:
    # Codjiflo, 2026-11-25: the depth is re-checked at the file's M6 T2 stop,
    # before the holes; Z0 put back there would drill them from the wrong Z0.
    remedies = [
        operation["instruction"]
        for setup in PLAN["setups"]
        for operation in setup["operations"]
        if operation["instruction"].startswith("Depth over")
    ]
    assert len(remedies) == 2
    for text in remedies:
        again = text.index("let it drill the holes")
        assert again < text.index("After the file ends: G10 L2 P1 Z(the noted Z)")
    # Both of Setup 3's texts put Z0 back after an oversize re-cut.
    (width,) = [
        operation
        for setup in PLAN["setups"]
        for operation in setup["operations"]
        if "run CC02_length again" in operation["instruction"]
    ]
    assert "put G54 Z back for the next blank" in width["instruction"]
    assert "Z0 goes back for the next blank" in width["instruction_detailed"]


def test_a_peck_that_is_not_a_positive_step_is_refused() -> None:
    for peck in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="not a positive step"):
            RECIPE._pecked((0.0, 0.0), 0.0, -10.0, peck, 5.0)
    assert RECIPE._pecked((0.0, 0.0), 0.0, -10.0, 4.0, 5.0)


def test_a_family_plan_binds_each_part_once_to_its_scoped_manifest(tmp_path) -> None:
    def parts(*rows: tuple[str, str]) -> dict[str, str]:
        plan = tmp_path / "pair" / "plan.toml"
        plan.parent.mkdir(exist_ok=True)
        plan.write_text(
            "".join(
                f'[[parts]]\nid = "{part}"\nfile = "{file}"\n' for part, file in rows
            ),
            encoding="utf-8",
        )
        return _process_plans.family_parts("pair", tmp_path)

    scoped = "../../out/features/{}/features.toml".format
    assert parts(("a", scoped("p_a")), ("b", scoped("p_b"))) == {"a": "p_a", "b": "p_b"}
    with pytest.raises(ValueError, match="share the id 'a'"):
        parts(("a", scoped("p_a")), ("a", scoped("p_b")))
    with pytest.raises(ValueError, match="two \\[\\[parts\\]\\] bind one manifest"):
        parts(("a", scoped("p_a")), ("b", scoped("p_a")))
    # A manifest of that name elsewhere is not the part's scoped one.
    for elsewhere in (
        "../../archive/features/p_a/features.toml",
        "features/p_a/features.toml",
    ):
        with pytest.raises(ValueError, match="not its ../../out/features"):
            parts(("a", elsewhere), ("b", scoped("p_b")))


def test_the_sheet_names_exactly_the_recipes_programs() -> None:
    listed = [name for setup in PLAN["setups"] for name in setup.get("programs", ())]
    assert sorted(listed) == sorted(PROGRAMS)
    setups = PLAN_TEXT[PLAN_TEXT.index("[[setups]]") :]
    assert set(re.findall(r"\bC[CFB]\d\d_\w+", setups)) == set(PROGRAMS)
    # A setup of one half runs no other half's file; a shared one only CC.
    for setup in PLAN["setups"]:
        letters = {name[1] for name in setup.get("programs", ())}
        if setup.get("part") == "front":
            assert letters == {"F"}, setup["title"]
        elif setup.get("part") == "back":
            assert letters == {"B"}, setup["title"]
        elif "serves" not in setup and "mating" not in setup["title"].lower():
            assert letters <= {"C"}, setup["title"]


def test_the_backs_are_marked_k_and_the_fronts_f() -> None:
    # Owner ruling 2026-11-24: B is the bottom face's mark, so no blank is B1-B3.
    assert not re.search(r"\bB[1-3]\b", PLAN_TEXT)
    assert "F1, F2, F3 (fronts) and K1, K2, K3 (backs)" in PLAN_TEXT


def test_the_bar_covers_the_blanks_and_kerfs() -> None:
    numbers = PLAN["parameters"]
    assert numbers["blank_count"] == numbers["quantity"] * len(PARTS)
    assert numbers["sawn_bar_length_in"] == pytest.approx(
        numbers["blank_count"] * numbers["blank_length_max_in"]
        + (numbers["blank_count"] - 1) * numbers["kerf_in"]
    )


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == set(PROGRAMS)


def test_no_cutter_comes_within_the_promised_clearance_of_the_work_stop(
    context, tmp_path
) -> None:
    # Owner ruling 2026-11-24: "Yes, use the work stop for X0". Every
    # single-blank program keeps out of the rod, its top raised by the plan's
    # clearance; the bolted pair has no stop.
    numbers = PLAN["parameters"]
    top = numbers["stop_rod_top_max_mm"] + numbers["stop_clear_min_mm"]
    rods: dict[str, list[dict]] = {}
    for program, check, kwargs in context["expect"]:
        if check == "keep_out":
            rods.setdefault(program.partition("@")[0], []).extend(
                box for box in kwargs["boxes"] if box["name"] == "work stop rod"
            )
    pair = {"CB09_pair_bore", "CB10_bore_open"}
    assert all(not rods[name] for name in pair)
    assert all(rods[name] for name in set(rods) - pair)
    assert set(rods) == set(PROGRAMS) - {"CB07_tap_1", "CB08_tap_2"}
    # Lying, the stacks' top is Z0: the rod's box stands the clearance over it.
    assert [box["z_top"] for box in rods["CC04_height"]] == [pytest.approx(top)]
    # The rod is on the N end: right of the front in CF06, left of the back in CB06.
    assert rods["CF06_bar_drill"][0]["x"][0] == 0.0
    assert rods["CB06_back_drill"][0]["x"][1] == 0.0
    # A rod set .033 higher than the plan allows is under the face-off's cut.
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["stop_rod_top_max_mm"] = 12.0
    high = _context(plan)
    _post(high, tmp_path)
    hits = [f for f in _findings(high, tmp_path) if f.check == "keep_out"]
    assert hits and all("work stop rod" in str(f) for f in hits)
    assert {f.program for f in hits} == {"CB11_face_off.nc"}


@pytest.mark.parametrize(
    ("half", "key", "value", "detail"),
    [
        ("front", "upright_top_max_mm", 50.0, "upright_top_max_mm"),
        ("front", "blank_length_min_in", 1.88, "under the width"),
        ("front", "drill_tip_height_mm", -2.0, "drill_tip_height_mm"),
        ("front", "spot_dia_mm", 4.8, "between the pilot"),
        ("front", "lying_grip_mm", 7.5, "lying_grip_mm"),
        ("back", "drill_tip_height_mm", -2.5, "drill_tip_height_mm"),
        ("back", "spot_dia_mm", 3.6, "under the #29"),
        ("back", "tap_stack_max_mm", 273.558, "tap_stack_max_mm"),
        ("back", "bore_finish_stock_mm", 0.05, "leaves a core"),
        ("back", "bore_feed_per_min_mm", 565.4, "bore_feed_per_min_mm"),
        ("back", "pair_jaw_span_mm", 100.0, "pair_jaw_span_mm"),
        ("back", "back_parallel_end_mm", 12.0, "under the bore"),
        ("back", "spacer_block_width_mm", 38.1, "screw heads"),
        ("back", "screw_length_mm", 33.0, "stand out"),
        ("back", "bore_mill_projection_min_mm", 25.4, "collet's face"),
        ("back", "grip_offset_mm", 0.635, "export's grip offset"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(
    half, key, value, detail
) -> None:
    # The number is seeded where the plan keeps it: a half's own table, or
    # the shared one (then both halves read it, and the named half refuses).
    plan = copy.deepcopy(PLAN)
    own = next(part for part in plan["parts"] if part["id"] == half)["parameters"]
    (own if key in own else plan["parameters"])[key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


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
        # The first face pass moved onto the part's middle: a full-width slot.
        (
            "front.outside_face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-8.001",
            "face",
        ),
        # An ear hole drilled short of its exit.
        (
            "front.ear_drill",
            lambda line: line == "G1 Z-2.496 F{feed}",
            lambda line: "G1 Z-1.000 F{feed}",
            "holes",
        ),
        # A tap drill's peck re-entry rapided past the depth already drilled.
        (
            "back.ear_drill",
            lambda line: line == "G0 Z9.898",
            lambda line: "G0 Z7.000",
            "rapid",
        ),
        # The bore's finish turn run conventional (G2).
        (
            "back.pair_bore",
            lambda line: line.startswith("G3 X17.551"),
            lambda line: "G2" + line[2:],
            "bounds",
        ),
        # The bore's finish radius stepped out .010 too far: oversize.
        (
            "back.pair_bore",
            lambda line: line == "G1 X30.455 F{feed}",
            lambda line: "G1 X30.709 F{feed}",
            "bounds",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        (
            "back.tap_1",
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

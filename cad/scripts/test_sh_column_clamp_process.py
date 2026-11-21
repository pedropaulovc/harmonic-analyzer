"""The column clamp halves' CAM recipes agree with their models and plans.

``cad/process/sh_column_clamp_{front,back}/cam.py`` write every path
themselves; each ``context`` runs here on the drawing's requirement manifest
(the features the ``clamp_half`` adapter binds) with no FreeCAD and no
SolidWorks, and refuses any plan number that disagrees with the model, the
shop or the holding. The posted programs are stood in for by the recipe's
own section lines under the grbl post's tool-change block, so every check
the recipe declares runs on them, and seeded faults show each check catches
what it guards.
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

STEMS = ("sh_column_clamp_front", "sh_column_clamp_back")
SHOP = tomllib.loads(_process_plans.SHOP_PATH.read_text(encoding="utf-8"))


def _plan(stem: str) -> dict:
    return tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))


PLANS = {stem: _plan(stem) for stem in STEMS}
RECIPES = {stem: _cam_programs.load_recipe(stem) for stem in STEMS}
FEATURES = {stem: export_features.requirement_manifest(stem) for stem in STEMS}


def _context(stem: str, plan: dict | None = None) -> dict:
    return RECIPES[stem].context(
        FEATURES[stem], plan or PLANS[stem], SHOP, "clamp.step"
    )


@pytest.fixture(scope="module")
def contexts() -> dict:
    return {stem: _context(stem) for stem in STEMS}


def _post(stem: str, ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min; a tap stop's lines after its M6, ending with its M30."""
    sections = {op[0]: job for job in ctx["jobs"] for op in job["ops"]}
    lines_of = {op[0]: op[2] for job in ctx["jobs"] for op in job["ops"]}
    for name, groups in RECIPES[stem].PROGRAMS:
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


def _findings(stem: str, ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPES[stem].expectations(ctx), out)


def test_context_accepts_each_plan_and_numbers_the_tools(contexts) -> None:
    assert contexts["sh_column_clamp_front"]["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-9": 3,
    }
    back = contexts["sh_column_clamp_back"]
    assert back["numbers"] == {"em-half": 1, "spot": 2, "drill-29": 3, "dead-centre": 4}
    for stem in STEMS:
        recipe = RECIPES[stem]
        assert recipe.LOAD_FIRST_TOOL == tuple(name for name, _ops in recipe.PROGRAMS)
    # Both halves' holes from one zero at the near side: the front's from its
    # right end (-X), the back's from its left (+X), at the same stations.
    front_holes = next(
        kwargs["centres"]
        for program, check, kwargs in contexts["sh_column_clamp_front"]["expect"]
        if program.startswith("CF06") and check == "holes"
    )
    back_holes = [
        stop["at"] for stop in (back["manual"]["tap_1"], back["manual"]["tap_2"])
    ]
    assert [[-x, y] for x, y in front_holes] == back_holes
    for stop in back["manual"].values():
        assert stop["tool"] == 4
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


@pytest.mark.parametrize("stem", STEMS)
def test_the_recipes_programs_pass_every_check_they_declare(
    contexts, tmp_path, stem
) -> None:
    ctx = contexts[stem]
    _post(stem, ctx, tmp_path)
    assert _findings(stem, ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPES[stem].expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPES[stem].PROGRAMS}


@pytest.mark.parametrize(
    ("stem", "key", "value", "detail"),
    [
        ("sh_column_clamp_front", "upright_top_max_mm", 50.0, "upright_top_max_mm"),
        ("sh_column_clamp_front", "blank_length_min_in", 1.88, "under the width"),
        ("sh_column_clamp_front", "drill_tip_height_mm", -2.0, "drill_tip_height_mm"),
        ("sh_column_clamp_front", "spot_dia_mm", 4.8, "between the pilot"),
        ("sh_column_clamp_front", "lying_grip_mm", 7.5, "lying_grip_mm"),
        ("sh_column_clamp_back", "drill_tip_height_mm", -2.5, "drill_tip_height_mm"),
        ("sh_column_clamp_back", "spot_dia_mm", 3.6, "under the #29"),
        ("sh_column_clamp_back", "tap_stack_max_mm", 273.558, "tap_stack_max_mm"),
        ("sh_column_clamp_back", "bore_finish_stock_mm", 0.05, "leaves a core"),
        ("sh_column_clamp_back", "bore_feed_per_min_mm", 565.4, "bore_feed_per_min_mm"),
        ("sh_column_clamp_back", "pair_jaw_span_mm", 100.0, "pair_jaw_span_mm"),
        ("sh_column_clamp_back", "back_parallel_end_mm", 12.0, "under the bore"),
        ("sh_column_clamp_back", "spacer_block_width_mm", 38.1, "screw heads"),
        ("sh_column_clamp_back", "screw_length_mm", 33.0, "stand out"),
        ("sh_column_clamp_back", "bore_mill_projection_min_mm", 25.4, "collet's face"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(
    stem, key, value, detail
) -> None:
    plan = copy.deepcopy(PLANS[stem])
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(stem, plan)


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
    ("stem", "key", "pick", "change", "check"),
    [
        # The first face pass moved onto the part's middle: a full-width slot.
        (
            "sh_column_clamp_front",
            "outside_face",
            lambda line: line.startswith("G0 X") and " Y" in line,
            lambda line: line.split(" Y")[0] + " Y-8.001",
            "face",
        ),
        # An ear hole drilled short of its exit.
        (
            "sh_column_clamp_front",
            "ear_drill",
            lambda line: line == "G1 Z-2.496 F{feed}",
            lambda line: "G1 Z-1.000 F{feed}",
            "holes",
        ),
        # A tap drill's peck re-entry rapided past the depth already drilled.
        (
            "sh_column_clamp_back",
            "ear_drill",
            lambda line: line == "G0 Z9.898",
            lambda line: "G0 Z7.000",
            "rapid",
        ),
        # The bore's finish turn run conventional (G2).
        (
            "sh_column_clamp_back",
            "pair_bore",
            lambda line: line.startswith("G3 X17.551"),
            lambda line: "G2" + line[2:],
            "bounds",
        ),
        # The bore's finish radius stepped out .010 too far: oversize.
        (
            "sh_column_clamp_back",
            "pair_bore",
            lambda line: line == "G1 X30.455 F{feed}",
            lambda line: "G1 X30.709 F{feed}",
            "bounds",
        ),
        # A tap stop that holds (M0) instead of ending Idle.
        (
            "sh_column_clamp_back",
            "tap_1",
            lambda line: line == "M30",
            lambda line: "M0",
            "tap_stop",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    contexts, tmp_path, stem, key, pick, change, check
) -> None:
    seeded = _seed(contexts[stem], key, pick, change)
    _post(stem, seeded, tmp_path)
    assert check in {finding.check for finding in _findings(stem, seeded, tmp_path)}

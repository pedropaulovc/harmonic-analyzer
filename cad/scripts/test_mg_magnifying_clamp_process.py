"""The magnifying clamp's CAM recipe agrees with its model and plan.

``cad/process/mg_magnifying_clamp/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the clamp's export binds) with no FreeCAD and no SolidWorks, and refuses any
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

STEM = "mg_magnifying_clamp"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "clamp.step")


@pytest.fixture(scope="module")
def ctx() -> dict:
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
                ]
                text += [f"M6 T{manual['tool']}", *manual["gcode"]]
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


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "spot": 2,
        "drill-43": 3,
        "drill-f": 4,
        "tap-guide": 5,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    for key in ("tap_rod", "tap_thumb"):
        stop = ctx["manual"][key]
        assert stop["tool"] == 5 and stop["at"] == [0.0, 0.0]
        assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("upright_top_max_mm", 33.0, "upright_top_max_mm"),
        ("blank_length_min_in", 1.17, "under the height"),
        ("end_spot_dia_mm", 2.3, "under the #43"),
        ("corner_spot_dia_mm", 1.9, "between the pilot"),
        ("rod_tip_height_mm", 18.0, "rod_tip_height_mm"),
        ("thumb_tip_height_mm", 19.0, "thumb_tip_height_mm"),
        ("cross_tip_height_mm", -3.0, "cross_tip_height_mm"),
        ("cross_parallel_end_mm", 17.0, "under the bore"),
        ("face_stepover_mm", 5.0, "two passes"),
        ("drill_f_feed_per_min_mm", 300.0, "not its setting"),
        ("upright_grip_mm", 20.0, "upright_grip_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` (or of a tap
    stop) replaced."""
    seeded = copy.deepcopy(ctx)
    if key in seeded["manual"]:
        lines = seeded["manual"][key]["gcode"]
    else:
        lines = next(
            op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key
        )
    assert old in lines, (key, old)
    lines[lines.index(old)] = new
    return seeded


@pytest.mark.parametrize(
    ("key", "old", "new", "check"),
    [
        # The first face pass moved onto the axis: a full-width slot.
        ("bottom_face", "G0 X-16.222 Y6.350", "G0 X-16.222 Y0.000", "face"),
        # The rod hole drilled short.
        ("rod_drill", "G1 Z-12.871 F{feed}", "G1 Z-11.871 F{feed}", "holes"),
        # The F drill stopped short of the far corner: no bore through.
        ("cross_drill", "G1 Z-17.626 F{feed}", "G1 Z-14.000 F{feed}", "holes"),
        # A peck re-entry rapided past the depth already drilled.
        ("thumb_drill", "G0 Z25.900", "G0 Z23.000", "rapid"),
        # A tap stop that holds (M0) instead of ending Idle.
        ("tap_rod", "M30", "M0", "tap_stop"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, old, new, check
) -> None:
    seeded = _seed(ctx, key, old, new)
    _post(seeded, tmp_path)
    assert {finding.check for finding in _findings(seeded, tmp_path)} >= {check}

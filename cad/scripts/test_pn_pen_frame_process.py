"""The pen frame's CAM recipe agrees with its model and plan.

``cad/process/pn_pen_frame/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features
the ``drilled_block`` adapter binds) with no FreeCAD and no SolidWorks, and
refuses any plan number that disagrees with the model, the shop or the
holding. The posted programs are stood in for by the recipe's own section
lines under the grbl post's tool-change block, so every check the recipe
declares runs on them, and seeded faults show each check catches what it
guards.
"""

from __future__ import annotations

import copy
import math
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "pn_pen_frame"
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
SHOP = _process_plans.load_shop()
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)


def _context(plan: dict = PLAN) -> dict:
    return RECIPE.context(FEATURES, plan, SHOP, "frame.step")


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
        for group in groups:
            keys = group if isinstance(group, tuple) else (group,)
            if keys[0] in ctx["manual"]:
                manual = ctx["manual"][keys[0]]
                text += [
                    "M5",
                    f"%msg TOOL CHANGE: T{manual['tool']} {manual['label']}, {manual['setting']}",
                    f"M6 T{manual['tool']}",
                    *manual["gcode"],
                ]
                continue
            job = sections[keys[0]]
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
                    for key in keys
                    for line in lines_of[key]
                ),
            ]
        manual_keys = [g if isinstance(g, str) else g[0] for g in groups]
        if not any(key in ctx["manual"] for key in manual_keys):
            text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(ctx) -> None:
    assert ctx["numbers"] == {
        "em-half": 1,
        "em-eighth": 2,
        "spot": 3,
        "drill-43": 4,
        "tap-guide": 5,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    stop = ctx["manual"]["tap"]
    # The tap from the bottom end at the drawing's .50 from L, .155 from the
    # front face against the fixed jaw; L on the right, the frame to -X.
    assert stop["tool"] == 5 and stop["at"] == [-12.7, -3.937]
    assert stop["gcode"][0] == "G53 G0 Z0.000" and stop["gcode"][-1] == "M30"


def test_the_recipes_programs_pass_every_check_it_declares(ctx, tmp_path) -> None:
    _post(ctx, tmp_path)
    assert _findings(ctx, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(ctx), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("upright_top_max_mm", 44.0, "upright_top_max_mm"),
        ("blank_length_min_in", 1.59, "under the height"),
        ("blank_y_in", 1.75, "blank_y_in"),
        ("spot_dia_mm", 2.4, "under the #43"),
        ("drill_tip_depth_mm", 7.0, "drill_tip_depth_mm"),
        ("drill_full_depth_mm", 6.5, "drill_full_depth_mm"),
        ("tap_reach_min_mm", 8.0, "tap_reach_min_mm"),
        ("tap_reach_max_mm", 35.0, "far wall"),
        ("tap_stack_max_mm", 270.0, "tap_stack_max_mm"),
        ("window_finish_stock_mm", 0.2, "corner band"),
        ("window_step_mm", 1.2, "window_step_mm"),
        ("window_plunge_feed_per_min_mm", 234.7, "window_plunge_feed_per_min_mm"),
        ("window_cutter_dia_mm", 2.38125, "cutter"),
        ("window_right_mm", 22.5, "window_right_mm"),
        # The .22 top rail's window wall of the withdrawn PN-01 B1.
        ("window_near_mm", 5.588, "window_near_mm"),
        ("parallel_thickness_mm", 6.35, "parallel stack"),
        ("lying_grip_mm", 7.5, "lying_grip_mm"),
        ("bar_width_min_mm", 31.5, "bar_width_min_mm"),
        ("bar_thick_max_mm", 10.0, "bar_thick_max_mm"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def test_no_5_64_cutter_and_a_1_8_cutter_off_the_corner_band_is_refused(ctx) -> None:
    """Owner ruling 2026-11-23, tool audit Q9: no 5/64 cutter; the 1/8 in end
    mill's finish leaves the window's corners at its radius plus the finish
    stock, which the printed R.065 (.060-.070) must hold."""
    assert "em-fine" not in {tool["id"] for tool in PLAN["tools"]}
    shop = copy.deepcopy(SHOP)
    shop["tools"]["endmill-carbide-3fl-1-8"]["diameter_mm"] = 3.6
    plan = copy.deepcopy(PLAN)
    plan["parameters"]["window_cutter_dia_mm"] = 3.6
    with pytest.raises(ValueError, match="corner band"):
        RECIPE.context(FEATURES, plan, shop, "frame.step")


def test_the_finish_takes_the_stock_evenly_round_each_corner(ctx) -> None:
    """At each level the finish turns each window corner on an arc of the
    stock's radius about the slot path's corner, so it takes the same .003
    in the corners as on the walls and leaves them at R.0655, inside the
    printed .060-.070."""
    p = PLAN["parameters"]
    stock, e8 = p["window_finish_stock_mm"], p["window_cutter_dia_mm"]
    d_rough = e8 / 2 + stock
    assert 0.060 * 25.4 <= d_rough <= 0.070 * 25.4
    assert d_rough / 25.4 == pytest.approx(0.0655)
    g = RECIPE._geometry(FEATURES)
    height = g["height"]
    (x0, x1), (y0, y1) = g["window_x"], g["window_y"]
    centres = [
        (x + sx * d_rough, y - height + sy * d_rough)
        for x, sx in ((x0, 1), (x1, -1))
        for y, sy in ((y0, 1), (y1, -1))
    ]
    lines = next(
        op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == "window_finish"
    )
    z = None
    turned: dict[tuple, list[float]] = {}
    for line in lines:
        words = dict((w[0], w[1:]) for w in line.split()[1:] if w[0] in "XYZ")
        if "Z" in words:
            z = float(words["Z"])
        if line.startswith("G1") and "X" in words:
            px, py = float(words["X"]), float(words["Y"])
            for cx, cy in centres:
                gap = math.dist((px, py), (cx, cy))
                if gap < 1.0:
                    turned.setdefault((z, cx, cy), []).append(gap)
    assert len({key[0] for key in turned}) == 8 and len(turned) == 32
    for gaps in turned.values():
        assert all(gap == pytest.approx(stock, abs=0.002) for gap in gaps), gaps


def _seed(ctx: dict, key: str, old: str, new: str) -> dict:
    """``ctx`` with the first line ``old`` of operation ``key`` (or of the tap
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


def _line(ctx: dict, key: str, prefix: str, index: int = 0) -> str:
    lines = next(op[2] for job in ctx["jobs"] for op in job["ops"] if op[0] == key)
    return [line for line in lines if line.startswith(prefix)][index]


def _shift(dx: float, dy: float):
    """A change moving a G1 X Y line's point by ``dx``, ``dy``."""

    def change(line: str) -> str:
        words = dict((w[0], float(w[1:])) for w in line.split()[1:] if w[0] in "XY")
        return f"G1 X{words['X'] + dx:.3f} Y{words['Y'] + dy:.3f} F{{feed}}"

    return change


@pytest.mark.parametrize(
    ("key", "prefix", "index", "change", "check"),
    [
        # The first face pass moved onto the part's middle: a full-width cut.
        (
            "front_face",
            "G0 X",
            0,
            lambda line: line.split(" Y")[0] + " Y-20.000",
            "face",
        ),
        # The finish's left wall run .010 too far out: the window oversize.
        ("window_finish", "G1 X", 0, _shift(-0.254, 0.0), "outline"),
        # The rough slot run anticlockwise on its first side: climb.
        ("window_rough", "G1 Y-7.", 0, lambda line: "G1 Y-32.372 F{feed}", "outline"),
        # The finish's last level stopped short of the front face: the walls
        # below it uncut.
        (
            "window_finish",
            "G1 Z-0.508",
            0,
            lambda line: "G1 Z0.000 F{plunge}",
            "outline",
        ),
        # A finish corner point pushed into the corner: a gouge.
        ("window_finish", "G1 X", 2, _shift(-0.2, 0.2), "outline"),
        # The tap drill stopped in the rail.
        ("tap_drill", "G1 Z-7.775", 0, lambda line: "G1 Z-5.000 F{feed}", "holes"),
        # A peck re-entry rapided past the depth already drilled.
        ("tap_drill", "G0 Z-1.532", 0, lambda line: "G0 Z-3.000", "rapid"),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    ctx, tmp_path, key, prefix, index, change, check
) -> None:
    old = _line(ctx, key, prefix, index)
    seeded = _seed(ctx, key, old, change(old))
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}


def test_a_tap_stop_that_holds_is_caught(ctx, tmp_path) -> None:
    seeded = _seed(ctx, "tap", "M30", "M0")
    _post(seeded, tmp_path)
    assert "tap_stop" in {finding.check for finding in _findings(seeded, tmp_path)}

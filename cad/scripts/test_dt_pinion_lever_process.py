"""The pinion engage lever's CAM recipe agrees with its model and plan.

``cad/process/dt_pinion_lever/cam.py`` writes every path itself; its
``context`` runs here on the drawing's requirement manifest (the features the
``flat_bar`` adapter binds) with no FreeCAD and no SolidWorks, and refuses
any plan number that disagrees with the model, the shop or the holding. The
posted programs are stood in for by the recipe's own section lines under the
grbl post's tool-change block, so every check the recipe declares runs on
them, and seeded faults show each check catches what it guards. The ball end
mill's paths, which the flat-cutter keep-outs cannot judge, are checked here
against the lever's solid: the ball's centre never comes nearer the rod, the
hub, the crown or a tab than its radius.
"""

from __future__ import annotations

import copy
import math
import re
import tomllib
from pathlib import Path

import pytest

import _cam_programs
import _process_plans
import cam_nc
import export_features

STEM = "dt_pinion_lever"
SHOP = _process_plans.load_shop()
PLAN = tomllib.loads(_process_plans.plan_path(STEM).read_text(encoding="utf-8"))
RECIPE = _cam_programs.load_recipe(STEM)
FEATURES = export_features.requirement_manifest(STEM)
# The posted coordinates' rounding (3 places) and the arcs' sampling.
TOL_MM = 0.003


def _context(plan: dict | None = None) -> dict:
    return RECIPE.context(FEATURES, plan or PLAN, SHOP, "lever.step")


@pytest.fixture(scope="module")
def context() -> dict:
    return _context()


def _post(ctx: dict, out: Path) -> None:
    """Each program as the runtime posts it: the grbl preamble, then per
    section an M6 block (M5, the operator's %msg, M6, M3) and its lines, the
    feeds in mm/min."""
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
        sections = [groups] if all(isinstance(key, str) for key in groups) else groups
        for keys in sections:
            job = jobs[keys[0]]
            number = ctx["numbers"][job["tool"]]
            text += [
                "M5",
                f"%msg TOOL CHANGE: T{number} {ctx['names'][job['tool']]}, SET SPINDLE TO {job['rpm']:g} RPM",
                f"M6 T{number}",
                f"M3 S{job['rpm']:g}",
            ]
            for key in keys:
                lines = next(op[2] for op in job["ops"] if op[0] == key)
                text += [
                    line.format(
                        feed=f"{job['feed']:.3f}", plunge=f"{job['plunge']:.3f}"
                    )
                    for line in lines
                ]
        text += ["M5", "G17 G90", "M2"]
        (out / f"{name}.nc").write_text("\n".join(text) + "\n", encoding="utf-8")


def _findings(ctx: dict, out: Path) -> list:
    return cam_nc.verify(RECIPE.expectations(ctx), out)


def test_context_accepts_the_plan_and_numbers_the_tools(context) -> None:
    assert context["numbers"] == {
        "em-quarter": 1,
        "ball": 2,
        "em-sixteenth": 3,
        "spot": 4,
        "drill-f": 5,
        "em-hss": 6,
    }
    assert RECIPE.LOAD_FIRST_TOOL == tuple(name for name, _ops in RECIPE.PROGRAMS)
    # The reference hole the crown setup zeroes X on is where the top setup
    # drilled it, turned end for end: X mirrored, Y kept.
    ref = context["holes"]["ref"]
    p = PLAN["parameters"]
    assert ref == (
        pytest.approx(p["ref_hole_y_mm"]),
        pytest.approx(-p["ref_hole_x_mm"]),
    )


def test_the_recipes_programs_pass_every_check_they_declare(context, tmp_path) -> None:
    _post(context, tmp_path)
    assert _findings(context, tmp_path) == []
    times = cam_nc.cycle_times(RECIPE.expectations(context), tmp_path)
    assert set(times) == {name for name, _ops in RECIPE.PROGRAMS}


def test_the_finishing_passes_leave_cusps_under_the_scallop(context) -> None:
    g, rb = context["geometry"], context["cutters"]["rb"]
    scallop = PLAN["parameters"]["scallop_max_mm"]
    for side in ("top", "crown"):
        phis = [pass_["phi"] for pass_ in context["built"][f"{side}_rod_finish"]]
        assert phis[0] == pytest.approx(-math.pi / 2) and phis[-1] == pytest.approx(
            math.pi / 2
        )
        step = max(b - a for a, b in zip(phis, phis[1:], strict=False))
        assert RECIPE.ball_cusp(rb, g["rod_r"], step) <= scallop + 1e-6
    rings = [ring["a"] for ring in context["built"]["crown_dome_finish"]]
    step = max(b - a for a, b in zip(rings, rings[1:], strict=False))
    assert RECIPE.ball_cusp(rb, g["crown_r"], step) <= scallop + 1e-6
    assert rings[-1] == pytest.approx(math.asin(g["hub_r"] / g["crown_r"]))


def test_the_root_steps_leave_stairs_under_the_cusp(context) -> None:
    g, p = context["geometry"], PLAN["parameters"]
    levels = context["levels"]["root"]
    assert levels[-1] < 0.0  # past the rod's axis plane
    above = g["rod_r"]
    for e in levels:
        step = above - e
        assert 0.0 < step <= p["root_level_max_mm"] + 1e-9
        # A step at height ``above`` stands step * above / rod_r off the rod.
        assert step * max(above, 0.0) / g["rod_r"] <= p["root_cusp_max_mm"] + 1e-9
        above = e


def test_the_owned_short_sixteenth_does_not_reach_the_root() -> None:
    # The owned Kyocera 1800.0625.200 (#3750: .200 of flutes) is why the
    # plan buys the .500-flute 1/16 in end mill.
    assert PLAN["parameters"]["root_reach_mm"] > 0.200 * 25.4
    assert (
        SHOP["tools"]["endmill-carbide-3fl-1-16-loc-1-2"]["flute_length_mm"]
        >= (PLAN["parameters"]["root_reach_mm"])
    )


def test_the_floor_circle_sits_in_the_bores_band(context) -> None:
    holes, bore = context["holes"], FEATURES["features"]["bore"]
    p = PLAN["parameters"]
    lines = {op[0]: op[2] for job in context["jobs"] for op in job["ops"]}["bore_floor"]
    circle = [line for line in lines if line.startswith("G2")]
    assert len(circle) == 1
    words = dict(_WORD.findall(circle[0]))
    edge = 2 * abs(float(words["I"])) + 2 * context["cutters"]["r6"]
    assert edge == pytest.approx(p["floor_dia_mm"], abs=TOL_MM)
    lo, hi = bore["dia"]
    assert lo <= edge <= hi
    # The F drill's point stops short of the floor the end mill flattens.
    assert holes["drill_tip"] > holes["floor"]


_WORD = re.compile(r"([XYZIJ])(-?\d+\.?\d*)")


def _ball_centres(lines: list[str], flip: bool, mouth: float, rb: float):
    """The ball's centre along every feed move of ``lines``, in model plan
    terms (x, y) and e, the height above the rod's axis plane on the side
    cut, sampled no more than 0.1 mm apart (arcs on their circles)."""
    here = None
    for line in lines:
        words = {k: float(v) for k, v in _WORD.findall(line)}
        word = line.split()[0]
        target = (
            words.get("X", here[0] if here else 0.0),
            words.get("Y", here[1] if here else 0.0),
            words.get("Z", here[2] if here else 0.0),
        )
        points = [target]
        if word in ("G1", "G2", "G3") and here is not None:
            if word == "G1":
                n = max(1, math.ceil(math.dist(here, target) / 0.1))
                points = [
                    tuple(
                        a + (b - a) * k / n for a, b in zip(here, target, strict=True)
                    )
                    for k in range(n + 1)
                ]
            else:
                cx, cy = here[0] + words["I"], here[1] + words["J"]
                radius = math.hypot(here[0] - cx, here[1] - cy)
                a0 = math.atan2(here[1] - cy, here[0] - cx)
                a1 = math.atan2(target[1] - cy, target[0] - cx)
                sweep = (
                    (a0 - a1) % (2 * math.pi)
                    if word == "G2"
                    else (a1 - a0) % (2 * math.pi)
                )
                sweep = sweep or 2 * math.pi
                n = max(4, math.ceil(radius * sweep / 0.1))
                sign = -1.0 if word == "G2" else 1.0
                points = [
                    (
                        cx + radius * math.cos(a0 + sign * sweep * k / n),
                        cy + radius * math.sin(a0 + sign * sweep * k / n),
                        here[2],
                    )
                    for k in range(n + 1)
                ]
            for X, Y, Z in points:
                if Z > (mouth + 12.0 if flip else 0.0):
                    continue  # above the stock
                y = -X if flip else X
                e = Z - mouth if flip else Z + mouth
                yield (-Y, y, e + rb)
        here = target


def _gap_to_lever(g: dict, side: str, x: float, y: float, e: float) -> float:
    """Distance from (x, y, e) to the lever's solid on this side: rod, hub
    (and crown on the crown side) and tabs."""
    gaps = []
    # The rod: a cylinder along +y from the hub's axis to its tip.
    radial = math.hypot(x, e)
    if radial <= g["rod_r"]:
        gaps.append(max(y - g["tip_y"], -y) if not 0.0 <= y <= g["tip_y"] else 0.0)
    else:
        gaps.append(math.hypot(max(0.0, y - g["tip_y"], -y), radial - g["rod_r"]))
    # The hub's wall, as tall each side of the axis plane as the mouth face.
    rho = math.hypot(x, y)
    gaps.append(
        math.hypot(max(0.0, rho - g["hub_r"]), max(0.0, abs(e) - g["hub_half"]))
    )
    if side == "crown":
        # The crown: its sphere, where its nearest point lies on the dome.
        dz = e + g["crown_c"]
        if dz > 0 and rho / math.hypot(rho, dz) <= g["hub_r"] / g["crown_r"]:
            gaps.append(math.hypot(rho, dz) - g["crown_r"])
    # The tabs: boxes on the axis plane at the window's ends.
    for y0, y1 in (
        (-PLAN["parameters"]["window_back_mm"], -g["hub_r"]),
        (g["tip_y"], PLAN["parameters"]["window_tip_mm"]),
    ):
        dx = max(0.0, abs(x) - g["tab_half_w"])
        dy = max(0.0, y0 - y, y - y1)
        de = max(0.0, abs(e) - g["tab_half_t"])
        gaps.append(math.hypot(dx, dy, de))
    return min(gaps)


@pytest.mark.parametrize(
    ("side", "keys"),
    [
        ("top", ("top_rod_semi", "top_rod_finish")),
        (
            "crown",
            (
                "crown_dome_semi",
                "crown_dome_finish",
                "crown_rod_semi",
                "crown_rod_finish",
            ),
        ),
    ],
)
def test_the_ball_never_cuts_into_the_lever(context, side, keys) -> None:
    g, rb = context["geometry"], context["cutters"]["rb"]
    mouth = PLAN["parameters"]["mouth_above_axis_mm"]
    lines = {op[0]: op[2] for job in context["jobs"] for op in job["ops"]}
    worst = math.inf
    for key in keys:
        for x, y, e in _ball_centres(lines[key], side == "crown", mouth, rb):
            worst = min(worst, _gap_to_lever(g, side, x, y, e))
    # It touches the finished surfaces and never goes nearer.
    assert worst == pytest.approx(rb, abs=TOL_MM)


@pytest.mark.parametrize(
    ("key", "value", "detail"),
    [
        ("window_half_mm", 12.7, "window_half_mm"),
        ("window_tip_mm", 92.0, "window_tip_mm"),
        ("end_wall_min_mm", 6.0, "end_wall_min_mm"),
        ("side_wall_min_mm", 14.0, "side_wall_min_mm"),
        ("tab_thickness_mm", 3.0, "outside the rod"),
        ("ref_hole_x_mm", 15.0, "ref_hole_x_mm"),
        ("ref_station_mm", 60.0, "ref_station_mm"),
        ("top_floor_depth_mm", 8.0, "top_floor_depth_mm"),
        ("crown_raster_z_mm", 8.0, "crown_raster_z_mm"),
        ("crown_floor_z_mm", 5.08, "crown_floor_z_mm"),
        ("rod_step_deg", 9.0, "rod_step_deg"),
        ("dome_step_deg", 4.0, "dome_step_deg"),
        ("sr_drop_min_mm", 2.4, "sr_drop_min_mm"),
        ("sr_probe_x_mm", 9.5, "rim"),
        ("drill_tip_mm", 7.5, "drill_tip_mm"),
        ("ref_tip_mm", 15.0, "ref_tip_mm"),
        ("root_reach_mm", 5.08, "root_reach_mm"),
        ("floor_dia_mm", 6.4, "floor_dia_mm"),
        ("rough_stepover_mm", 7.0, "rough_stepover_mm"),
        ("ball_low_z_mm", 2.5, "ball_low_z_mm"),
        ("cutter_dia_mm", 6.0, "cutter_dia_mm"),
        ("apex_below_axis_mm", 7.0, "apex_below_axis_mm"),
        ("bar_thickness_min_mm", 12.3, "apex"),
    ],
)
def test_a_plan_number_off_the_model_or_shop_is_refused(key, value, detail) -> None:
    plan = copy.deepcopy(PLAN)
    plan["parameters"][key] = value
    with pytest.raises(ValueError, match=detail):
        _context(plan)


def _seed(ctx: dict, key: str, pick, change, last: bool = False) -> dict:
    """``ctx`` with the first (or last) line of operation ``key`` that
    ``pick`` accepts replaced by ``change(line)``."""
    seeded = copy.deepcopy(ctx)
    lines = next(op[2] for job in seeded["jobs"] for op in job["ops"] if op[0] == key)
    order = range(len(lines) - 1, -1, -1) if last else range(len(lines))
    index = next(i for i in order if pick(lines[i]))
    lines[index] = change(lines[index])
    return seeded


@pytest.mark.parametrize(
    ("key", "pick", "change", "last", "check"),
    [
        # The tip face's first pass moved over the rod's middle: into the rod.
        (
            "top_tip",
            lambda line: line.startswith("G0 X"),
            lambda line: "G0 X60.000 Y0.000",
            False,
            "keep_out",
        ),
        # The tip face's last pass (a tab level) run across the tab.
        (
            "top_tip",
            lambda line: line.startswith("G1 X"),
            lambda line: line.split(" Y")[0] + " Y0.000 F{feed}",
            True,
            "keep_out",
        ),
        # A roughing plunge taken past the window's floor.
        (
            "top_rough",
            lambda line: line.endswith("F{plunge}"),
            lambda line: "G1 Z-9.500 F{plunge}",
            True,
            "depth",
        ),
        # A ball pass dropped to the rod's top at full speed: a rapid below the stock.
        (
            "top_rod_finish",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G0" + line[2:].replace(" F{feed}", ""),
            False,
            "rapid",
        ),
        # The crown's roughing run into the hub's wall.
        (
            "crown_wall",
            lambda line: line.startswith("G0 X"),
            lambda line: "G0 X0.000 Y-8.000",
            False,
            "keep_out",
        ),
        # The reference hole spotted off its place.
        (
            "spot",
            lambda line: line.startswith("G0 X38.1"),
            lambda line: "G0 X40.000 Y-20.320",
            False,
            "holes",
        ),
        # The bore drilled past its point.
        (
            "bore_drill",
            lambda line: line.startswith("G1 Z"),
            lambda line: "G1 Z-8.200 F{feed}",
            False,
            "keep_out",
        ),
        # The bore's floor circle run the other way round: a climb cut.
        (
            "bore_floor",
            lambda line: line.startswith("G2"),
            lambda line: "G3" + line[2:],
            False,
            "cut",
        ),
        # The root's first arc run the other way round the hub: a climb cut.
        (
            "top_root",
            lambda line: line.startswith("G2") or line.startswith("G3"),
            lambda line: ("G2" if line.startswith("G3") else "G3") + line[2:],
            False,
            "cut",
        ),
        # The root cutter's first level run into the hub.
        (
            "top_root",
            lambda line: line.startswith("G2") or line.startswith("G3"),
            lambda line: re.sub(
                r"X-?\d+\.\d+ Y-?\d+\.\d+", "X3.000 Y0.000", line, count=1
            ),
            False,
            "keep_out",
        ),
    ],
)
def test_a_seeded_fault_in_a_program_is_caught(
    context, tmp_path, key, pick, change, last, check
) -> None:
    seeded = _seed(context, key, pick, change, last)
    _post(seeded, tmp_path)
    assert check in {finding.check for finding in _findings(seeded, tmp_path)}

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
import _gcode
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
    assert levels[0] == pytest.approx(g["rod_r"])  # the rod's top itself first
    assert levels[-1] < 0.0  # past the rod's axis plane
    above = levels[0]
    for e in levels[1:]:
        step = above - e
        assert 0.0 < step <= p["root_level_max_mm"] + 1e-9
        # A step at height ``above`` stands step * above / rod_r off the rod.
        assert step * max(above, 0.0) / g["rod_r"] <= p["root_cusp_max_mm"] + 1e-9
        above = e


@pytest.mark.parametrize("side", ["top", "crown"])
def test_the_root_sweeps_the_rods_crest_beside_the_hub(context, side) -> None:
    # The 1/4 in end mill stops a level above the rod's top beside the hub's
    # wall, and the ball's pass over the top stops short of the wall: the
    # root's first level, on the rod's top, takes the crest between them.
    g, cut = context["geometry"], context["cutters"]
    r5, rb = cut["r5"], cut["rb"]
    first = [
        b
        for b in context["built"][f"{side}_root"]
        if b["e"] == pytest.approx(g["rod_r"])
    ]
    assert sorted(math.copysign(1.0, b["x"]) for b in first) == [-1.0, 1.0]
    wall = min(e for e in context["levels"][side] if e > g["rod_r"])
    over = min(context["built"][f"{side}_rod_finish"], key=lambda p: abs(p["x"]))
    assert over["x"] == pytest.approx(0.0, abs=1e-9)
    # Along the rod, the ball's bottom is below the 1/4 in end mill's level
    # past here.
    dip = over["y_hub"] - math.sqrt(rb * rb - (over["e_centre"] - wall) ** 2)
    crest = context["levels"]["root"][1]
    for b in first:
        # Each side's inner edge reaches the rod's middle, so the two sweep
        # the whole crest the next level leaves (|x| under its half width).
        assert abs(b["x"]) - r5 <= 1e-9
        assert abs(b["x"]) + r5 > math.sqrt(g["rod_r"] ** 2 - crest**2)
        # From the hub's wall out past where the ball's pass dips below it.
        assert b["meet"] == pytest.approx(math.sqrt((g["hub_r"] + r5) ** 2 - r5**2))
        assert b["y_start"] > dip


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
    edge = 2 * abs(float(words["I"])) + 2 * context["cutters"]["hss"]
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


def test_the_crown_rings_descend_at_the_plunge_feed(context) -> None:
    # The crown's roughing leaves steps over the dome: every move down below
    # the stock's top, the apex plunge and each ring's, is at the plunge feed.
    top = PLAN["parameters"]["bar_thickness_max_mm"]
    lines = {op[0]: op[2] for job in context["jobs"] for op in job["ops"]}
    for key in ("crown_dome_semi", "crown_dome_finish"):
        z, descents = None, []
        for line in lines[key]:
            words = dict(_WORD.findall(line))
            if "Z" not in words:
                continue
            target = float(words["Z"])
            if line.startswith("G1") and z is not None and target < min(z, top):
                descents.append(line)
            z = target
        assert len(descents) == len(context["built"][key])
        assert all(line.endswith("F{plunge}") for line in descents), descents


def test_every_jaw_keep_out_keeps_the_shops_jaw_floor(context) -> None:
    # _gcode applies the shop's 1.0 mm jaw clearance only to the shapes it
    # reads as jaws: every jaw box the recipe declares is one, and no support.
    names = {
        box["name"]
        for _program, check, kwargs in RECIPE.expectations(context)
        if check == "keep_out"
        for box in kwargs.get("boxes", ())
    }
    jaws = {name for name in names if name.endswith("jaw")}
    assert jaws == {"fixed jaw", "moving jaw"}
    assert all(_gcode.is_jaw_shape(name) for name in jaws)
    assert not any(_gcode.is_jaw_shape(name) for name in names - jaws)


def test_the_fixtures_stand_where_the_narrowest_thinnest_bar_puts_them(context) -> None:
    # Nearest the cutters: the moving jaw closes in to the narrowest bar, and
    # under face B's zero the stacks' top rises to the thinnest.
    p = PLAN["parameters"]
    grip = p["lying_grip_mm"]
    moving = RECIPE._r(p["half_width_mm"] - p["bar_width_min_mm"])
    for program, check, kwargs in RECIPE.expectations(context):
        if check != "keep_out" or not kwargs.get("boxes"):
            continue
        boxes = {box["name"]: box for box in kwargs["boxes"]}
        assert boxes["moving jaw"]["y"][1] == moving
        assert boxes["moving-jaw stack"]["y"][0] == moving
        stacks = -p["bar_thickness_min_mm"] if "_top_" in program else 0.0
        assert boxes["moving-jaw stack"]["z_top"] == RECIPE._r(stacks)
        assert boxes["fixed jaw"]["z_top"] == RECIPE._r(stacks + grip)


@pytest.mark.parametrize("side", ["top", "crown"])
def test_the_window_raster_never_cuts_climb(context, tmp_path, side) -> None:
    # The window's passes overlap: each meets steel on one side, cut
    # conventional, or is a full-width slot (the first from each wall and
    # the one on the axis). The rough program cut from its stock box: the
    # crown's levels below its raster's floor break into Setup 2's window,
    # which the box does not know, so those are left out.
    p = PLAN["parameters"]
    _post(context, tmp_path)
    job = next(
        j for j in context["jobs"] if j["frame"] == side and j["tool"] == "em-quarter"
    )
    program = _gcode.read_program(tmp_path / f"DT16_{side}_rough.nc")
    cuts = [
        e
        for e in _gcode.engagements(program, job["stock"], context["cutters"]["r6"])
        if e.side
        and math.dist(e.move.start[:2], e.move.end[:2]) > TOL_MM
        and (
            side == "top"
            or min(e.move.start[2], e.move.end[2]) > p["crown_raster_z_mm"]
        )
    ]
    slots = {0.0, RECIPE._r(p["window_half_mm"] - p["cutter_dia_mm"] / 2)}
    assert any(e.side == "conventional" for e in cuts)
    for e in cuts:
        where = f"line {e.move.line}: {e.move.start} -> {e.move.end}"
        assert e.side != "climb", where
        if e.side == "both":
            assert e.move.start[1] == e.move.end[1], where
            assert abs(e.move.start[1]) in slots, where


def _uncut_beside_the_tab(context: dict, side: str, tip_tab: bool) -> list:
    """Points of the material beyond the rod's tip face beside the tip tab's
    stock (model x, y and e, at each of ``side``'s tip-tab levels) that no
    flat cutter of either setup reaches: the 1/4 in end mill's roughing, wall
    and tip passes and, with ``tip_tab``, the 1/16 in end mill's passes beside
    the tab. A point at height e on ``side`` stands until a cutter's end
    comes within its radius at or below e on that side, or at or below -e on
    the other (cutting through from it)."""
    import numpy as np

    g, cut, p = context["geometry"], context["cutters"], PLAN["parameters"]
    mouth, stock = p["mouth_above_axis_mm"], p["stock_mm"]
    lines = {op[0]: op[2] for job in context["jobs"] for op in job["ops"]}
    tab, tip = g["tab_half_w"] + stock, g["tip_y"]
    ends = []
    for frame in ("top", "crown"):
        ops = [("rough", cut["r6"]), ("wall", cut["r6"]), ("tip", cut["r6"])]
        ops += [("tip_tab", cut["r5"])] if tip_tab else []
        flip = -1.0 if frame != side else 1.0
        for op, r in ops:
            for x, y, e in _ball_centres(
                lines[f"{frame}_{op}"], frame == "crown", mouth, 0.0
            ):
                if abs(x) < g["rod_r"] + 2 * r and tip - r < y < tip + 3 * cut["r6"]:
                    # Its reach as a height on ``side``: up from e on that
                    # side, down from -e from the other.
                    ends.append((x, y, flip * e, flip, r))
    ends = np.array(ends)
    out = []
    for e in context["levels"]["tip_tab"][side]:
        half = math.sqrt(g["rod_r"] ** 2 - e * e)
        xs = np.arange(tab, half, 0.02)
        ys = np.arange(tip + 0.01, tip + 2 * cut["r6"], 0.02)
        gx, gy = np.meshgrid(np.concatenate([xs, -xs]), ys, indexing="ij")
        mine = ends[(ends[:, 3] > 0) & (ends[:, 2] <= e + 1e-6)]
        through = ends[(ends[:, 3] < 0) & (ends[:, 2] >= e - 1e-6)]
        reach = np.full(gx.shape, False)
        for x, y, _e, _flip, r in np.concatenate([mine, through]):
            reach |= np.hypot(gx - x, gy - y) <= r + TOL_MM
        out += [
            (float(a), float(b), e) for a, b in zip(gx[~reach], gy[~reach], strict=True)
        ]
    return out


@pytest.mark.parametrize("side", ["top", "crown"])
def test_the_tip_face_beside_the_tab_is_cut_but_for_the_small_corner(
    context, side
) -> None:
    # The 1/4 in end mill cannot reach the tip face beside the tab (its radius
    # is more than the rod's half less the tab's): it leaves its own corner
    # there, up to its radius proud. The 1/16 in end mill takes it all but
    # what lies within its radius of the tab's stock: its corner with the face
    # and the cusps between its rows along the tab, filed off with the stub.
    g, r5 = context["geometry"], context["cutters"]["r5"]
    tab = g["tab_half_w"] + PLAN["parameters"]["stock_mm"]
    before = _uncut_beside_the_tab(context, side, tip_tab=False)
    assert any(abs(x) - tab >= r5 and y - g["tip_y"] >= r5 for x, y, _e in before)
    left = _uncut_beside_the_tab(context, side, tip_tab=True)
    assert left
    for x, y, e in left:
        assert abs(x) - tab < r5, (x, y, e)
        # On the face itself, only the corner the cutter's radius leaves.
        if y - g["tip_y"] < r5:
            assert math.hypot(abs(x) - tab - r5, y - g["tip_y"] - r5) > r5 - TOL_MM


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
        # Clear of the moving jaw's stack on the widest bar, not the narrowest.
        ("ref_hole_x_mm", 21.8, "ref_hole_x_mm"),
        ("rough_woc_mm", 5.1435, "rough_woc_mm"),
        ("tip_tab_step_mm", 0.5373, "tip_tab_step_mm"),
        ("tip_station_mm", 106.0, "tip_station_mm"),
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
        # The tip face's first pass beside the tab run across the tab.
        (
            "top_tip_tab",
            lambda line: line.startswith("G1 X"),
            lambda line: line.split(" Y")[0] + " Y0.000 F{feed}",
            False,
            "keep_out",
        ),
        # The tip face's first pass beside the tab run back toward the
        # corner's far side: a climb cut.
        (
            "top_tip_tab",
            lambda line: line.startswith("G1 X"),
            lambda line: re.sub(r"Y-?\d+\.\d+", "Y-3.500", line),
            False,
            "cut",
        ),
        # A raster pass on the moving-jaw side run away from the axis, along
        # the steel it should have kept on its left: a climb cut.
        (
            "top_rough",
            lambda line: line.startswith("G1 X-8.579 Y-4.953"),
            lambda line: "G1 X-12.000 Y-4.953 F{feed}",
            False,
            "cut",
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

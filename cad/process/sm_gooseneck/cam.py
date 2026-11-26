"""FreeCAD CAM recipe for the MHA-SM-01 gooseneck's bend form.

The gooseneck itself is bent by hand at the bench; the only milled work in its
traveler is the form of Setups 3 and 4 (``fixtures.sm-gooseneck-bend-form``,
owner ruling 2026-11-22, option A: two 6061 plates, the groove cut with the
owned 1/4 in ball end mill). ``cam_nc.py`` loads this module on the host, calls
:func:`context` with the gooseneck's ``features.toml`` and the plan/shop TOML,
runs :func:`build` inside headless FreeCAD and checks the posted G-code
against :func:`expectations`.

The form's working sizes come from the manifest: the groove's centre line is
the bend's centreline radius (``bend.centreline_radius``), its radius is
checked against the tube's O.D. band (``blank.od``), the channel holding the
tail is the arm's straight (``arm.arm_straight_ref``) plus the owner's tail,
and the wrap it allows is checked against the bend's angle band
(``bend.angle``) and the plan's springback allowance. The plate, its place on
the table, the clamps, the levels and steps come from ``plan.toml``
``[parameters]``; cutter sizes, flute lengths, speeds and feeds from the shop
(``shop/``). Typed here, because neither record carries them: the safe,
clearance and approach heights, the front margin past the bar's width
tolerance, the air ramp, the 1-2-3 blocks' footprint, the step clamps'
lanes, and the least wall the plan's stud holes keep.

Route (plan text in ``plan.toml``): each plate, a 9 in length of the owned 1/2
x 6 in bar, lies on three 1-2-3 blocks on the table under three step clamps
(LMS 1268), as the MHA-CH-13-TL-01 sub-plate's SP01 does. One file per plate:
T1, the 1/2 in end mill, plunges the two stud holes and cuts the form's arc
out through the plate in four levels (the waste, the plate outside the arc,
comes free under its own clamp); T2, the 1/4 in ball end mill, cuts the
groove: first a pass with the ball centred on the groove's centre line at the
plate top (the offset steps alone leave a core there whenever the ball is
narrower than the groove's radius), then Z steps round the centre line: a full
half-round channel along the lead that holds the tube's tail, and a quarter
cove on the arc's top edge. Plate B is plate A mirrored, so that turned over
onto A its cove meets A's: GF02 is GF01 with X negated (its zero at the
plate's right end).

Work frame (G54, plate A): X0 Y0 the arc's centre, +X from the lead toward the
arc, +Y toward the plate's back edge (Y0 is found on it); Z0 the plate top.
The lead's channel runs along Y = -R from the tube stop to X0; the arc is the
circle of radius R about X0 Y0, from its bottom round its right side to the
back edge.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "sm_gooseneck"
COMMENT = "MHA-SM-01 gooseneck bend form"
# One file per plate: T1's section (stud holes, then the arc through), then
# T2's (the groove), joined at the M6.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("GF01_form_a", (("holes_a", "outline_a"), ("groove_a",))),
    ("GF02_form_b", (("holes_b", "outline_b"), ("groove_b",))),
)
# Each file loads its own first tool: a plate is set up with whatever the
# mill last held.
LOAD_FIRST_TOOL = ("GF01_form_a", "GF02_form_b")
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these.
CAM_TOOLS = ("em-half", "ball")
IN = 25.4
# Moves to and from the cut run this far above the plate top; descents start
# this far above it.
CLEAR_MM = 5.0
SAFE_MM = 1.0
# The cutter clears the plate's edge by this much before it turns down or
# after it leaves.
APPROACH_MM = 2.54
# Y0 is the back edge; the front edge stands the bar's width away. The 1/2
# in end mill starts this much farther out in front, past any width the
# 6 in bar arrives at (the author's 1/4 in).
FRONT_MARGIN_MM = 6.35
# T1 comes down to each level along a ramp of this length in the air, so a
# level's entry is no plunge (only the stud holes are).
RAMP_MM = 5.0
# A pecked hole's rapid re-entry stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# 1-2-3 blocks lying flat (1 in up): 3 in by 2 in.
BLOCK_LONG_MM = 3 * IN
BLOCK_SHORT_MM = 2 * IN
# A step clamp's lane: its half width, its nose past the clamp point, its run
# out to the stud beyond the plate's end. Nothing passes under a strap.
STRAP_HALF_WIDTH_MM = 12.7
STRAP_NOSE_MM = 12.7
STRAP_RUN_MM = 4 * IN
STRAP_TOP_MM = 1000.0
# A stud hole keeps this much plate round it, to the groove and the edges
# (the author's 1/4 in: the flange nut seats on it).
HOLE_WALL_MIN_MM = 6.35
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(
    plan: dict[str, Any], name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        cuts = op.get("milling_cuts", ())
        for cut in cuts if isinstance(cuts, list) else ():
            if cut["name"] == name:
                return op, cut
    raise KeyError(f"plan has no milling cut {name!r}")


def _resolve(plan: dict[str, Any], value: Any, what: str) -> float:
    """A number, or a ``{{process.<parameter>}}`` binding read from [parameters]."""
    if isinstance(value, str):
        match = re.fullmatch(r"\{\{process\.(\w+)\}\}", value.strip())
        if not match:
            raise ValueError(
                f"{what} = {value!r}: only numbers and {{{{process.…}}}} bindings are read"
            )
        value = plan["parameters"][match.group(1)]
    return float(value)


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    """Field ``key`` of the plan's milling cut ``name``."""
    return _resolve(plan, _op_with_cut(plan, name)[1][key], f"'{name}' {key}")


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float]:
    """(rpm, mm/min) of the shop setting the operation holding ``cut`` names:
    its chip load × flutes × rpm, or its stated in/min feed. The cut's own
    rpm and feed must agree."""
    op, record_cut = _op_with_cut(plan, cut)
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    if "chip_load_mm_per_tooth" in record:
        feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
    else:
        value, unit = record["feed"].split()
        if unit != "in/min":
            raise ValueError(
                f"settings.{op['settings']}: feed {record['feed']!r} is not in/min"
            )
        feed = float(value) * IN
    for key, expected in (("rpm", rpm), ("feed_mm_min", feed)):
        if key in record_cut and not math.isclose(
            _cut(plan, cut, key), expected, abs_tol=1e-3
        ):
            raise ValueError(
                f"'{cut}' {key} {_cut(plan, cut, key):g} is not its setting's {expected:g}"
            )
    return rpm, feed


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n)]


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [min(x), max(x)], "y": [min(y), max(y)], "z_top": z_top}


def _lane(name: str, at: tuple[float, float], side: float) -> dict[str, Any]:
    """A step clamp's lane: from the clamp point's nose out past the plate's
    end on ``side`` (-1 the left, +1 the right) to its stud."""
    x, y = at
    near = x - side * STRAP_NOSE_MM
    far = x + side * (STRAP_RUN_MM + 300.0)
    return _box(
        name,
        (near, far),
        (y - STRAP_HALF_WIDTH_MM, y + STRAP_HALF_WIDTH_MM),
        STRAP_TOP_MM,
    )


def _block(
    name: str, at: tuple[float, float], along_x: float, z_top: float
) -> dict[str, Any]:
    """A 1-2-3 block lying flat, centred under a clamp point, ``along_x`` mm
    of it along X."""
    along_y = BLOCK_SHORT_MM if along_x == BLOCK_LONG_MM else BLOCK_LONG_MM
    x, y = at
    return _box(
        name,
        (x - along_x / 2, x + along_x / 2),
        (y - along_y / 2, y + along_y / 2),
        z_top,
    )


def _form(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any]
) -> dict[str, Any]:
    """Plate A's geometry in its work frame, every number checked against the
    manifest, the plan and the shop."""
    f = features["features"]
    p = plan["parameters"]
    bend, blank, arm = f["bend"], f["blank"], f["arm"]
    radius = float(bend["centreline_radius"])
    od_min, od_max = (float(v) for v in blank["od"])
    angle_max = float(bend["angle"][1])
    arm_straight = float(arm["arm_straight_ref"])

    # The groove: a half round the tube's largest O.D. sits in, snug on its
    # least.
    rc = p["groove_radius_mm"]
    if rc < od_max / 2:
        raise ValueError(
            f"groove_radius_mm {rc:g}: under the tube's largest O.D./2 {od_max / 2:.4f}"
        )
    if rc - od_min / 2 > p["groove_snug_max_mm"] + 1e-9:
        raise ValueError(
            f"groove_radius_mm {rc:g}: {rc - od_min / 2:.4f} over the least tube's"
            f" radius, more than groove_snug_max_mm {p['groove_snug_max_mm']:g}"
        )

    # The bend's ovality limit: the plan's fraction (ASME B31.3 §332.2.1) of
    # the tube's nominal O.D.
    _agree(
        plan, "ovality_max_mm", p["ovality_fraction_max"] * float(blank["od_nominal"])
    )
    # The ends' saw lines: each end's largest size plus the stock its file
    # takes off.
    _agree(plan, "arm_line_mm", float(f["arm_end"]["reach"][1]) + p["file_stock_mm"])
    _agree(plan, "foot_line_mm", float(arm["height"][1]) + p["file_stock_mm"])

    # Wrap: the bend's widest angle plus the springback allowance, overbent on
    # the form; the cove runs on past the farthest departure until the circle
    # has fallen a groove radius inside that departing tube.
    if p["wrap_max_deg"] + 1e-9 < angle_max + p["springback_max_deg"]:
        raise ValueError(
            f"wrap_max_deg {p['wrap_max_deg']:g}: under the bend's {angle_max:g} plus"
            f" springback_max_deg {p['springback_max_deg']:g}"
        )
    clear_deg = math.degrees(math.acos(1 - rc / radius))
    need = p["wrap_max_deg"] - 90.0 + clear_deg
    if p["back_edge_angle_deg"] + 1e-9 < need:
        raise ValueError(
            f"back_edge_angle_deg {p['back_edge_angle_deg']:g}: the cove must reach"
            f" {need:.2f} deg past the arc's quarter for a {p['wrap_max_deg']:g} deg wrap"
        )
    y_back = radius * math.sin(math.radians(p["back_edge_angle_deg"]))
    _agree(plan, "form_back_y_mm", y_back)
    width = p["plate_width_in"] * IN
    y_front = y_back - width

    # The lead: the tube's tail lies in the channel, its end on the channel's
    # end, the bend starting at X0; the plate runs on past the channel's end
    # far enough to carry the left clamp and its block.
    x_stop = -(arm_straight + p["tube_tail_mm"])
    _agree(plan, "tube_stop_x_mm", x_stop)
    x_left = x_stop - p["stop_to_end_mm"]
    _agree(plan, "arc_from_end_mm", -x_left)
    x_right = x_left + p["plate_length_in"] * IN

    # The 1/2 in end mill: through the thickest plate in equal levels.
    em = _shop_tool(plan, shop, "em-half")
    re1 = em["diameter_mm"] / 2
    if not math.isclose(_cut(plan, "form outline", "cutter_dia_mm"), em["diameter_mm"]):
        raise ValueError("'form outline' cutter_dia_mm is not the end mill's diameter")
    t_min = p["plate_thickness_min_in"] * IN
    t_max = p["plate_thickness_max_in"] * IN
    _agree(plan, "plate_top_max_mm", t_max)
    _agree(plan, "plate_thickness_min_mm", t_min)
    tip = -(t_max + p["cutter_tip_below_mm"])
    if -tip > em["flute_length_mm"]:
        raise ValueError(
            f"the through cut ({-tip:.3f}) is deeper than the end mill's flutes"
            f" ({em['flute_length_mm']:.3f})"
        )
    levels = _levels(0.0, tip, p["slot_step_mm"])
    _agree(plan, "outline_level_mm", -levels[0])
    if _cut(plan, "form outline", "axial_doc_mm") + 1e-6 < -levels[0]:
        raise ValueError("'form outline' axial_doc_mm is under one level's depth")
    # The waste (the plate outside the arc) comes free in one piece: the
    # cut's outer edge stays inside the plate's right end.
    if x_right <= radius + 2 * re1 + APPROACH_MM:
        raise ValueError(
            "the arc's cut reaches the plate's right end: the waste splits"
        )
    if y_front > -(radius + rc + re1):
        raise ValueError("the plate's front edge is inside the channel's outer wall")

    # The 1/4 in ball end mill: its centre on circles of radius rc - rb about
    # the groove's centre line, in equal angle steps.
    ball = _shop_tool(plan, shop, "ball")
    rb = ball["diameter_mm"] / 2
    if not math.isclose(_cut(plan, "groove", "cutter_dia_mm"), ball["diameter_mm"]):
        raise ValueError("'groove' cutter_dia_mm is not the ball end mill's diameter")
    if rb >= rc:
        raise ValueError("the ball end mill is wider than the groove")
    if rc > ball["flute_length_mm"]:
        raise ValueError(
            f"the groove ({rc:.3f} deep) is deeper than the ball end mill's flutes"
            f" ({ball['flute_length_mm']:.3f})"
        )
    rho = rc - rb
    n = round(180.0 / p["groove_step_deg"])
    if not math.isclose(n * p["groove_step_deg"], 180.0):
        raise ValueError("groove_step_deg must divide 180")
    thetas = [math.radians(k * p["groove_step_deg"]) for k in range(n + 1)]

    # Stud holes: inside the form, clear of the groove and the back edge.
    holes = [
        (p["stud_hole_x_mm"], p["stud_hole_1_y_mm"]),
        (p["stud_hole_x_mm"], p["stud_hole_2_y_mm"]),
    ]
    for x, y in holes:
        if math.hypot(x, y) + re1 + HOLE_WALL_MIN_MM > radius - rc:
            raise ValueError(f"stud hole at X{x:g} Y{y:g}: too near the groove")
        if y + re1 + HOLE_WALL_MIN_MM > y_back:
            raise ValueError(f"stud hole at X{x:g} Y{y:g}: too near the back edge")

    return {
        "radius": radius,
        "rc": rc,
        "rb": rb,
        "rho": rho,
        "thetas": thetas,
        "re1": re1,
        "tip": tip,
        "levels": levels,
        "t_min": t_min,
        "y_back": y_back,
        "y_front": y_front,
        "x_left": x_left,
        "x_right": x_right,
        "x_stop": x_stop,
        "holes": holes,
    }


def _exit_x(radius: float, y: float) -> float:
    return math.sqrt(radius * radius - y * y)


def _plate_a(g: dict[str, Any], p: dict[str, Any]) -> dict[str, Any]:
    """Plate A's paths, in its own frame: lists of (word, x, y, z, i, j)
    moves the poster writes, mirrored for plate B."""
    radius, re1, rb = g["radius"], g["re1"], g["rb"]
    clear, safe = CLEAR_MM, SAFE_MM
    ro = radius + re1
    y_start = g["y_front"] - FRONT_MARGIN_MM - re1
    y_exit = g["y_back"] + re1 + APPROACH_MM
    x_exit = _exit_x(ro, y_exit)

    holes: list[tuple] = [("G0", None, None, clear)]
    pecks = _levels(0.0, g["tip"], p["hole_peck_mm"])
    for x, y in g["holes"]:
        holes += [("G0", x, y, None), ("G0", None, None, safe)]
        last = None
        for z in pecks:
            if last is not None:
                holes += [
                    ("G0", None, None, safe),
                    ("G0", None, None, last + PECK_REENTRY_MM),
                ]
            holes.append(("G1p", None, None, z))
            last = z
        holes.append(("G0", None, None, clear))

    outline: list[tuple] = [("G0", None, None, clear)]
    for k, z in enumerate(g["levels"]):
        if k % 2 == 0:  # in from the front, up the line, round the arc
            outline += [
                ("G0", 0.0, y_start - RAMP_MM, None),
                ("G0", None, None, safe),
                ("G1", 0.0, y_start, z),
                ("G1", 0.0, -ro, None),
                ("ccw", x_exit, y_exit, None, 0.0, ro),
                ("G0", None, None, clear),
            ]
        else:  # back from beyond the back edge, round the arc, down the line
            outline += [
                ("G0", x_exit, y_exit + RAMP_MM, None),
                ("G0", None, None, safe),
                ("G1", x_exit, y_exit, z),
                ("cw", 0.0, -ro, None, -x_exit, -y_exit),
                ("G1", 0.0, y_start, None),
                ("G0", None, None, clear),
            ]

    groove: list[tuple] = [("G0", None, None, clear)]
    x_stop = g["x_stop"]
    # The centred pass: the ball centred on the centre line at the plate top
    # (tip at -rb), back from beyond the back edge round the arc and down the
    # channel to the tube stop, where the first step starts. The steps' ball
    # centres lie rho off the centre line, so with rb < rho they reach only to
    # rho - rb from it; this pass cuts that core.
    yb = g["y_back"] + rb + APPROACH_MM
    xb = _exit_x(radius, yb)
    groove += [
        ("G0", xb, yb, None),
        ("G0", None, None, safe),
        ("G1p", None, None, -rb),
        ("cw", 0.0, -radius, None, -xb, -yb),
        ("G1", x_stop, None, None),
        ("G0", None, None, clear),
    ]
    for k, theta in enumerate(g["thetas"]):
        d = g["rho"] * math.cos(theta)
        z = -g["rho"] * math.sin(theta) - rb
        y_line = -radius + d
        if d >= -1e-9:  # the form-side half: the channel, then the arc's cove
            r = radius - d
            yb = g["y_back"] + rb + APPROACH_MM
            xb = _exit_x(r, yb)
            if k % 2 == 0:
                groove += [
                    ("G0", x_stop, y_line, None),
                    ("G0", None, None, safe),
                    ("G1p", None, None, z),
                    ("G1", 0.0, None, None),
                    ("ccw", xb, yb, None, 0.0, r),
                    ("G0", None, None, clear),
                ]
            else:
                groove += [
                    ("G0", xb, yb, None),
                    ("G0", None, None, safe),
                    ("G1p", None, None, z),
                    ("cw", 0.0, -r, None, -xb, -yb),
                    ("G1", x_stop, None, None),
                    ("G0", None, None, clear),
                ]
        else:  # the channel's outer half, along the lead only
            ends = (x_stop, 0.0) if k % 2 == 0 else (0.0, x_stop)
            groove += [
                ("G0", ends[0], y_line, None),
                ("G0", None, None, safe),
                ("G1p", None, None, z),
                ("G1", ends[1], None, None),
                ("G0", None, None, clear),
            ]
    return {
        "holes": holes,
        "outline": outline,
        "groove": groove,
        "y_start": y_start,
        "exit": (x_exit, y_exit),
        "outline_radius": ro,
    }


def _gcode(moves: list[tuple], sign: float) -> list[str]:
    """Moves as G-code, X times ``sign`` (plate B mirrors A: arcs reverse)."""
    lines = []
    for move in moves:
        word, x, y, z = move[:4]
        if word in ("ccw", "cw"):
            arc = "G3" if (word == "ccw") == (sign > 0) else "G2"
            i, j = move[4], move[5]
            lines.append(
                f"{arc} X{_r(sign * x):.3f} Y{_r(y):.3f} I{_r(sign * i):.3f} J{_r(j):.3f} F{{feed}}"
            )
            continue
        g = "G0" if word == "G0" else "G1"
        parts = [g]
        if x is not None:
            parts.append(f"X{_r(sign * x):.3f}")
        if y is not None:
            parts.append(f"Y{_r(y):.3f}")
        if z is not None:
            parts.append(f"Z{_r(z):.3f}")
        if g == "G1":
            parts.append("F{plunge}" if word == "G1p" else "F{feed}")
        lines.append(" ".join(parts))
    return lines


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    p = plan["parameters"]
    g = _form(features, plan, shop)
    a = _plate_a(g, p)
    radius, re1, rb, rc = g["radius"], g["re1"], g["rb"], g["rc"]

    rpm1, feed1 = _setting(plan, shop, "form outline")
    rpm2, feed2 = _setting(plan, shop, "groove")
    plunge1 = _cut(plan, "stud holes a", "feed_mm_min")
    if _cut(plan, "stud holes a", "rpm") != rpm1:
        raise ValueError(
            "'stud holes' must run at the outline's speed (one T1 section)"
        )
    plunge2 = p["ball_plunge_feed_per_min_mm"]
    if plunge2 > feed2:
        raise ValueError("ball_plunge_feed_per_min_mm is over the groove's feed")

    # Work zero entries: the .200 in edge finder half its Ø off the edge.
    finder = 0.1 * IN
    _agree(plan, "x_set_mm", g["x_left"] - finder)
    _agree(plan, "x_set_b_mm", -(g["x_left"] - finder))
    _agree(plan, "y_set_mm", g["y_back"] + finder)

    numbers = {
        t["id"]: n
        for n, t in enumerate((t for t in plan["tools"] if t["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")
    names = {t["id"]: t["name"] for t in plan["tools"]}
    em, ball = _shop_tool(plan, shop, "em-half"), _shop_tool(plan, shop, "ball")

    # Keep-outs, plate A's frame: the 1-2-3 blocks' tops are the plate's
    # underside (the thinnest plate's, the highest); the clamps' lanes have
    # no top.
    block_top = -g["t_min"]

    def at(key: str) -> tuple[float, float]:
        """A clamp point placed from the plate's left end and back edge."""
        return (
            g["x_left"] + p[f"clamp_{key}_from_end_mm"],
            g["y_back"] - p[f"clamp_{key}_from_back_mm"],
        )

    c_left, c_mid, c_waste = at("left"), at("mid"), at("waste")
    if not (g["x_left"] < c_left[0] < -re1 and g["x_left"] < c_mid[0] < radius - rc):
        raise ValueError("the form's clamps must bear on the form")
    if not radius + 2 * re1 < c_waste[0] < g["x_right"]:
        raise ValueError("the waste's clamp must bear on the waste, past the arc's cut")
    if not g["y_front"] < c_waste[1] - STRAP_NOSE_MM:
        raise ValueError("the waste's clamp must bear on the plate")

    # The beam screen's stations, from each plate's left end as it lies on
    # the table (plate B's left end is its far end from plate A's frame).
    length = g["x_right"] - g["x_left"]
    ends = {"a": lambda x: x - g["x_left"], "b": lambda x: g["x_right"] - x}
    for key, station in ends.items():
        _agree(
            plan, f"{key}_outline_from_mm", min(station(-re1), station(radius + re1))
        )
        _agree(plan, f"{key}_outline_to_mm", max(station(-re1), station(radius + re1)))
        _agree(
            plan,
            f"{key}_groove_from_mm",
            min(station(g["x_stop"] - rb), station(radius + rb)),
        )
        _agree(
            plan,
            f"{key}_groove_to_mm",
            max(station(g["x_stop"] - rb), station(radius + rb)),
        )
        _agree(plan, f"{key}_hole_station_mm", station(p["stud_hole_x_mm"]))
        _agree(
            plan, f"{key}_support_left_mm", min(station(c_left[0]), station(c_waste[0]))
        )
        _agree(
            plan,
            f"{key}_support_right_mm",
            max(station(c_left[0]), station(c_waste[0])),
        )
    _agree(plan, "plate_length_mm", length)
    # The form's least section across the beam once the arc is through: at
    # X0, from the channel's centre line to the back edge.
    _agree(plan, "form_section_y_mm", radius + g["y_back"])
    _agree(plan, "tip_over_underside_mm", g["tip"] + g["t_min"])
    a_moves = a["outline"]
    ys = [m[2] for m in a_moves if m[0] != "ccw" and m[0] != "cw" and m[2] is not None]
    _agree(plan, "tool_y_span_mm", max(ys) - min(ys))
    blocks = [
        _block("form block left", c_left, BLOCK_LONG_MM, block_top),
        _block("form block middle", c_mid, BLOCK_SHORT_MM, block_top),
        _block("waste block", c_waste, BLOCK_SHORT_MM, block_top),
    ]
    lanes = [
        _lane("left clamp", c_left, -1.0),
        _lane("middle clamp", c_mid, -1.0),
        _lane("waste clamp", c_waste, 1.0),
    ]

    plates = {"a": 1.0, "b": -1.0}
    jobs, expect = [], []
    t1, t2 = numbers["em-half"], numbers["ball"]
    for (name, _sections), (key, sign) in zip(PROGRAMS, plates.items()):

        def mirror(box: dict[str, Any], sign: float = sign) -> dict[str, Any]:
            x0, x1 = (sign * v for v in box["x"])
            return {**box, "x": [min(x0, x1), max(x0, x1)]}

        xs = sorted((sign * g["x_left"], sign * g["x_right"]))
        stock = [xs, [g["y_front"], g["y_back"]], [-g["t_min"], 0.0]]
        common = {"frame": key, "stock": stock}
        jobs += [
            {
                **common,
                "tool": "em-half",
                "dia": em["diameter_mm"],
                "shape": "endmill",
                "flutes": 2,
                "rpm": rpm1,
                "feed": feed1,
                "plunge": plunge1,
                "label": f"form {key.upper()} through",
                "ops": [
                    [f"holes_{key}", "stud holes", _gcode(a["holes"], sign)],
                    [f"outline_{key}", "arc through", _gcode(a["outline"], sign)],
                ],
            },
            {
                **common,
                "tool": "ball",
                "dia": ball["diameter_mm"],
                "shape": "ballend",
                "flutes": 2,
                "rpm": rpm2,
                "feed": feed2,
                "plunge": plunge2,
                "label": f"form {key.upper()} groove",
                "ops": [[f"groove_{key}", "groove", _gcode(a["groove"], sign)]],
            },
        ]
        holes = [[_r(sign * x), _r(y)] for x, y in g["holes"]]
        ro = a["outline_radius"]
        x_exit, y_exit = a["exit"]
        end = math.atan2(y_exit, x_exit)
        arc_points = [
            [_r(sign * ro * math.cos(t)), _r(ro * math.sin(t))]
            for t in (-math.pi / 2 + (end + math.pi / 2) * k / 60 for k in range(61))
        ]
        line_points = [
            [0.0, _r(a["y_start"] + (-ro - a["y_start"]) * k / 10)] for k in range(11)
        ]
        # The groove's centre line, cut by the centred pass (tip at -rb: the
        # core the offset steps leave) and by the deepest level: the channel
        # from the tube stop to X0, then the circle R to the back edge.
        back = math.asin(g["y_back"] / radius)
        centre = [
            [_r(sign * (g["x_stop"] * (1 - k / 20))), _r(-radius)] for k in range(21)
        ] + [
            [_r(sign * radius * math.cos(t)), _r(radius * math.sin(t))]
            for t in (-math.pi / 2 + (back + math.pi / 2) * k / 60 for k in range(61))
        ]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": 0.0, "tools": [t1, t2], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[rpm1], [rpm2]]}],
            [name, "pauses", {"z_top": 0.0, "count": 0}],
            [name, "rapids_clear", {"z_top": 0.0, "open_holes": holes}],
            [name, "air_feed", {"z_top": 0.0}],
            [f"{name}@0", "depth", {"z_min": _r(g["tip"])}],
            [f"{name}@0", "holes", {"centres": holes, "z_bottom": _r(g["tip"])}],
            [
                f"{name}@0",
                "cleared",
                {"points": arc_points + line_points, "radius": 0.01, "z": _r(g["tip"])},
            ],
            [
                f"{name}@0",
                "keep_out",
                {"radius": re1, "boxes": [mirror(b) for b in blocks + lanes]},
            ],
            [f"{name}@1", "depth", {"z_min": _r(-rc)}],
            [f"{name}@1", "cleared", {"points": centre, "radius": 0.01, "z": _r(-rb)}],
            [f"{name}@1", "cleared", {"points": centre, "radius": 0.01, "z": _r(-rc)}],
            [
                f"{name}@1",
                "keep_out",
                {"radius": rb, "boxes": [mirror(b) for b in lanes]},
            ],
        ]
    frames = {
        key: {
            "x": sorted((sign * g["x_left"], sign * g["x_right"])),
            "y": [g["y_front"], g["y_back"]],
            "z": [-g["t_min"], 0.0],
        }
        for key, sign in plates.items()
    }
    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": {},
        "expect": expect,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job
    per tool per plate, each over a box the size of its plate; returns
    {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.box(
            doc, f"Form plate {key.upper()}", frame["x"], frame["y"], frame["z"]
        )
        for key, frame in ctx["frames"].items()
    }
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc, section["label"], [models[section["frame"]]], section["stock"]
        )
        tc = rt.tool_controller(
            doc,
            ctx["names"][section["tool"]],
            ctx["numbers"][section["tool"]],
            section["shape"],
            section["dia"],
            section["rpm"],
            section["feed"],
            section["plunge"],
            flutes=section.get("flutes"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}


# The as-machined report (``cad/scripts/_as_machined.py``) cannot compare
# these programs with the part: they cut the bend form, a shop fixture.
AS_MACHINED_NOT_COVERED = (
    "GF01/GF02 cut the bend form (fixtures.sm-gooseneck-bend-form, two 6061 plates),"
    " not MHA-SM-01: the gooseneck is 1/2 in 4130 tube bent by hand on that form and"
    " sawn to length; no CAD model of the form exists to compare with"
)

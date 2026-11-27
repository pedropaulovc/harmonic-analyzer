"""FreeCAD CAM recipe for MHA-PN-02, the pen hanger.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The part's sizes come
from the feature export (the strap's four corners, its thickness band, the
screw hole, the two guide plates' width, reach, drop and overhang, and the
slots' width, depth and arms); the blanks, the layout in them, the levels,
the tabs, the spots, the pecks, the feeds and the holding heights from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter and drill
diameters and the cutting settings from the shop (``shop/``). Every path is
written here (``rt.custom``): straight lines and arcs a recipe can state
exactly. Typed here, because neither record carries them: the #1 centre
drill's catalogue geometry, the twist drill's 118° point, the safe and
clearance heights, the vise jaws' depth, the cutter's clearance from a jaw
or a fixture face, the outline's tolerance and the least side strip of the
blank's frame (keep-out and check shapes only).

Route (plan text in ``plan.toml``): the strap and the two guide plates are
cut from the 1/8 x 1-1/2 in bar on tabs, each blank flat on a 1/2 in 6061
spoil plate on two 1 in parallels, gripped on its two as-supplied edges.
PH01 (the strap blank, back face up): spot and drill the #15 screw hole,
then the strap's outline on tabs. PH02 (two plate blanks end to end): each
plate's outline on tabs. The plates are bonded to the strap's front in the
vise (Setup 5), and after the 24 h cure PH03, in that same clamping, cuts
both slots in line in one set of passes along the strap's axis.

Work frames (G54), each set in its setup:
- PH01: X0 the strap blank's left end (the strap's top end at +X), Y0 the
  fixed jaw's face (the bar's edge on the strap's outer side), the strap at
  -Y; Z0 the spoil plate's top (the blank's underside), the back face up.
- PH02: X0 the left plate blank's left end, Y0 the fixed jaw's face, Z0 the
  spoil plate's top; each plate's bonded end toward -X.
- PH03: X0 the strap's foot end (the lower plate's outer face, flush with
  it), +X toward the top end; Y0 the fixed jaw's face (both plates' outer
  sides against it); Z0 the plates' far ends, the strap below.

Toolpath rules (owner rulings 2026-11-16): plunges beside the stock at the
cutting feed, real G0 above the stock. The outlines run anticlockwise round
each part (G3 at the corners: conventional outside with M3). Each slot level
is two straight passes along X through both plates, out and back.
"""

from __future__ import annotations

import math
from typing import Any

STEM = "pn_pen_hanger"
COMMENT = "MHA-PN-02 pen hanger"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("PH01_strap", (("strap_spot",), ("strap_drill",), ("strap_outline",))),
    ("PH02_plates", ("plate_outline",)),
    ("PH03_slots", ("slots",)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the files and the gauges are not).
CAM_TOOLS = ("spot", "drill-15", "em-eighth")
IN = 25.4
# #1 combined drill and countersink (shop centre-drills-carbide-60, trade
# size 1): 1/8 body, 3/64 pilot and pilot length, 60° countersink, its pilot
# ground with a 118° point (as ch_channel_lever's recipe).
CENTRE_DRILL = {
    "body_mm": 1 / 8 * IN,
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Plunges and drill R planes start this far above the stock top.
SAFE_MM = 1.0
# Moves between cuts run this far above the highest obstacle.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from its face.
JAW_DEPTH_MM = IN
# A cutter or a holder's nose passes a jaw, a block or a part face at no
# less than this.
CLEARANCE_MM = 1.5
# How far the cutter centre may stray from its offset round an outline.
OUTLINE_TOL_MM = 0.05
# The frame left round a part on tabs: no strip of it (bar edge or blank end
# to the cutter's swath) narrower than this, so the jaws' push stays in the
# frame and on the tabs (the author's floor).
STRIP_MIN_MM = 4.5
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01


def _plan_operations(plan: dict[str, Any]):
    for setup in plan["setups"]:
        yield from setup.get("operations", ())


def _op_with_cut(
    plan: dict[str, Any], name: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    for op in _plan_operations(plan):
        for cut in op.get("milling_cuts", ()):
            if cut["name"] == name:
                return op, cut
    raise KeyError(f"plan has no milling cut {name!r}")


def _resolve(plan: dict[str, Any], value: Any, what: str) -> float:
    """A number, or a ``{{process.<parameter>}}`` binding read from [parameters]."""
    if isinstance(value, str):
        key = value.removeprefix("{{process.").removesuffix("}}")
        if key == value or key not in plan["parameters"]:
            raise ValueError(f"{what}: {value!r} is not a process parameter")
        return float(plan["parameters"][key])
    return float(value)


def _cut(plan: dict[str, Any], name: str, key: str) -> float:
    """Field ``key`` of the plan's milling cut ``name``."""
    return _resolve(plan, _op_with_cut(plan, name)[1][key], f"'{name}' {key}")


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _xy(x: float, y: float) -> str:
    return f"X{_r(x):.3f} Y{_r(y):.3f}"


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #1 centre drill reaches ``dia`` on
    its 60° countersink (between the pilot and the body)."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < dia <= body:
        raise ValueError(f"spot Ø{dia:.3f} is not on the centre drill's countersink")
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _spot(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 {_xy(*xy)}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck``, each with a full
    retract to the R plane and a rapid back to just above the last peck."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", f"G0 {_xy(*xy)}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _normal(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """The right-hand unit normal of a→b: outward on an anticlockwise loop."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    return (dy / length, -dx / length)


def _shift(
    p: tuple[float, float], n: tuple[float, float], r: float
) -> tuple[float, float]:
    return (p[0] + n[0] * r, p[1] + n[1] * r)


def _elements(corners: list[tuple[float, float]], name: str) -> list[dict[str, Any]]:
    """A convex outline's sides, anticlockwise from ``corners[0]``."""
    sides = []
    for k, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
        sides.append(
            {
                "name": f"{name} side {k + 1}",
                "start": a,
                "end": b,
                "tol": OUTLINE_TOL_MM,
            }
        )
    return sides


def _tab_box(
    corners: list[tuple[float, float]], side: int, x: float, r: float, width: float
) -> dict[str, Any]:
    """The box round a tab ``width`` wide on side ``side`` (a run along X) at
    station ``x``: the tab plus the cutter's diameter along X, from inside
    the outline to past the cutter-centre path across it."""
    a, b = corners[side], corners[(side + 1) % len(corners)]
    n = _normal(a, b)
    half = width / 2 + r

    def on_side(at: float) -> float:
        return a[1] + (at - a[0]) * (b[1] - a[1]) / (b[0] - a[0])

    ys = [on_side(x - half), on_side(x + half)]
    lo, hi = min(ys), max(ys)
    if n[1] > 0:
        y = (lo - 0.5, hi + r + 0.5)
    else:
        y = (lo - r - 0.5, hi + 0.5)
    return {"x": [x - half, x + half], "y": [y[0], y[1]]}


def _straight(
    a: tuple[float, float],
    b: tuple[float, float],
    z: float,
    boxes: list[dict[str, Any]],
) -> list[str]:
    """Feed along a→b at level ``z``, hopping each tab box the run crosses
    below its top: up to the top at its first edge, level across, down at
    its far edge at the plunge feed."""
    lines: list[str] = []
    if not math.isclose(a[0], b[0], abs_tol=1e-9):
        lo, hi = sorted((a[0], b[0]))

        def y_at(x: float) -> float:
            return a[1] + (x - a[0]) * (b[1] - a[1]) / (b[0] - a[0])

        crossing = [
            box
            for box in boxes
            if z < box["top"] - 1e-6
            and lo <= box["x"][0]
            and box["x"][1] <= hi
            and box["y"][0] <= y_at(box["x"][0]) <= box["y"][1]
        ]
        forward = b[0] > a[0]
        crossing.sort(key=lambda box: box["x"][0] if forward else -box["x"][1])
        for box in crossing:
            x0, x1 = (
                (box["x"][0], box["x"][1]) if forward else (box["x"][1], box["x"][0])
            )
            lines += [
                f"G1 {_xy(x0, y_at(x0))} F{{feed}}",
                f"G1 Z{_r(box['top']):.3f} F{{feed}}",
                f"G1 {_xy(x1, y_at(x1))} F{{feed}}",
                f"G1 Z{_r(z):.3f} F{{plunge}}",
            ]
    return lines + [f"G1 {_xy(*b)} F{{feed}}"]


def _arc_g3(
    start: tuple[float, float], end: tuple[float, float], centre: tuple[float, float]
) -> str:
    i, j = centre[0] - start[0], centre[1] - start[1]
    return f"G3 {_xy(*end)} I{_r(i):.3f} J{_r(j):.3f}"


def _laps(
    corners: list[tuple[float, float]],
    r: float,
    start_side: int,
    levels: list[float],
    top: float,
    boxes: list[dict[str, Any]],
    clear: float,
) -> list[str]:
    """The cutter-centre path ``r`` outside a convex anticlockwise outline,
    one lap per level, each from the middle of side ``start_side`` (no tab
    on it) round to it again: straight runs along the offset sides, G3 arcs
    round each corner. The first level is entered from above the stock at
    the cutting feed, each next one plunged at the start point."""
    n = len(corners)
    sides = [(corners[k], corners[(k + 1) % n]) for k in range(n)]
    normals = [_normal(a, b) for a, b in sides]
    a, b = sides[start_side]
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    start = _shift(mid, normals[start_side], r)
    lines = [
        f"G0 Z{_r(clear):.3f}",
        f"G0 {_xy(*start)}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{plunge}}")
        here = start
        for step in range(n + 1):
            k = (start_side + step) % n
            a, b = sides[k]
            if step == n:
                lines += _straight(here, start, z, boxes)
                break
            end = _shift(b, normals[k], r)
            lines += _straight(here, end, z, boxes)
            following = normals[(k + 1) % n]
            here = _shift(b, following, r)
            lines.append(_arc_g3(end, here, b))
    return lines + [f"G0 Z{_r(clear):.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The strap and the plates as the routes assume them: the strap's back
    face on Z0 and its front at -Z, its top end on Y0 and its foot at -Y,
    both plates on the front across the same X span as the foot, the slots
    on X0."""
    f = features["features"]
    edges = f["strap_edges"]
    corners = {
        key: (edges[f"{key}_at"][0], edges[f"{key}_at"][1])
        for key in ("outer_top", "inner_top", "inner_foot", "outer_foot")
    }
    top_y, foot_y = f["top_end"]["plane"]["value"], f["foot"]["plane"]["value"]
    if f["top_end"]["plane"]["axis"] != "y" or f["foot"]["plane"]["axis"] != "y":
        raise ValueError("the strap's ends are not Y planes")
    if corners["outer_top"][1] != top_y or corners["inner_top"][1] != top_y:
        raise ValueError("the top corners are off the top end's plane")
    if corners["outer_foot"][1] != foot_y or corners["inner_foot"][1] != foot_y:
        raise ValueError("the foot corners are off the foot's plane")
    back, front = f["strap_back"]["plane"]["value"], f["strap_front"]["plane"]["value"]
    if back != 0.0 or not front < back:
        raise ValueError("the strap's back face is not Z0 with the front at -Z")
    hole = f["screw_hole"]
    if hole["axis"] != [0.0, 0.0, -1.0] or not hole.get("thru"):
        raise ValueError("the screw hole is not a through hole along Z")
    plates, slots = f["guide_plates"], f["slots"]
    foot_w = corners["outer_foot"][0] - corners["inner_foot"][0]
    # Note 1: the lower plate flush with the strap end and both corners.
    if not math.isclose(plates["width_nominal"], foot_w) or not math.isclose(
        f["foot"]["bottom_width_nominal"], foot_w
    ):
        raise ValueError(
            "the plates are not the foot's width: not flush with its corners"
        )
    if not math.isclose(corners["outer_foot"][0] + corners["inner_foot"][0], 0.0):
        raise ValueError("the foot is not centred on X0")
    if slots["centre_x"] != 0.0:
        raise ValueError("the slots are off the plates' centre")
    lower_y, upper_y = plates["plate_ys"]
    t_plate = plates["thickness_as_supplied"]
    if not math.isclose(lower_y, foot_y):
        raise ValueError("the lower plate is not flush with the strap's foot")
    if not math.isclose(upper_y + t_plate, top_y - plates["upper_drop_nominal"]):
        raise ValueError("the upper plate's drop disagrees with its station")
    if not math.isclose(plates["extent_z"][0], front - plates["reach_nominal"]):
        raise ValueError("the plates' reach is not measured from the strap's front")
    return {
        "corners": corners,
        "rise": top_y - foot_y,
        "t": back - front,
        "t_band": f["strap_front"]["thickness_band_mm"],
        "hole": (hole["at"][0], hole["at"][1]),
        "hole_band": hole["dia"],
        "plate_w": plates["width_nominal"],
        "plate_w_band": plates["width"],
        "reach": plates["reach_nominal"],
        "plate_t": t_plate,
        "lower_y": lower_y,
        "upper_y": upper_y,
        "overhang_band": plates["upper_overhang"],
        "slot_band": slots["width"],
        "slot_depth": slots["depth_nominal"],
        "slot_depth_band": slots["depth"],
        "arm_band": slots["arm_width"],
        "corner_r_max": slots["corner_r_max"],
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    c = g["corners"]
    t = g["t"]

    dspot = CENTRE_DRILL["body_mm"]
    d15 = _shop_tool(plan, shop, "drill-15")["diameter_mm"]
    e8_tool = _shop_tool(plan, shop, "em-eighth")
    e8 = e8_tool["diameter_mm"]
    r8 = e8 / 2
    if not g["hole_band"][0] - 1e-6 <= d15 <= g["hole_band"][1]:
        raise ValueError(f"#15 Ø{d15} outside the screw hole's band {g['hole_band']}")
    for name, dia in (
        ("strap outline", e8),
        ("plate outline", e8),
        ("slots", e8),
        ("screw drill", d15),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    if not math.isclose(_cut(plan, "screw spot", "cutter_dia_mm"), p["spot_dia_mm"]):
        raise ValueError("'screw spot' cutter_dia_mm is not process.spot_dia_mm")
    if not p["spot_dia_mm"] < d15:
        raise ValueError("the spot is not under the #15")

    # The bar as supplied: its thickness band is the drawing's (1/8 CF FLAT,
    # thickness_as_supplied), the incoming-stock gate.
    _agree(plan, "blank_thickness_min_mm", g["t_band"][0])
    _agree(plan, "blank_thickness_max_mm", g["t_band"][1])
    t_min, t_max = p["blank_thickness_min_mm"], p["blank_thickness_max_mm"]
    _agree(plan, "blank_length_min_mm", p["blank_length_in"] * IN)
    _agree(plan, "blank_length_max_mm", p["blank_length_max_in"] * IN)
    _agree(plan, "plate_blank_length_min_mm", p["plate_blank_length_in"] * IN)
    _agree(plan, "plate_blank_length_max_mm", p["plate_blank_length_max_in"] * IN)
    bar_w = p["blank_width_in"] * IN
    if not math.isclose(p["plate_blank_width_in"], p["blank_width_in"]):
        raise ValueError("the plate blanks are not off the strap's bar")

    # Heights in the vise (Setups 2 and 3): the spoil plate on the
    # parallels, the blank on it, Z0 the spoil plate's top.
    support = p["parallel_height_mm"] + p["spoil_plate_thickness_mm"]
    _agree(plan, "support_height_mm", support)
    nominal = p["vise_jaw_height_mm"] - support
    _agree(plan, "jaw_top_mm", nominal)
    # Setup 2 gauges the jaws' top in a band round it: its low end grips the
    # thickest bar whole; every keep-out and clearance stands at its high end.
    if not p["jaw_top_min_mm"] <= nominal <= p["jaw_top_max_mm"]:
        raise ValueError("process.jaw_top_mm is outside the gauged jaw-top band")
    if p["jaw_top_min_mm"] < t_max + 1e-6:
        raise ValueError(
            "the jaws' top is under the thickest bar: it is not gripped whole"
        )
    jaw_top = p["jaw_top_max_mm"]
    if p["spoil_plate_width_mm"] >= bar_w:
        raise ValueError(
            "the spoil plate is not narrower than the bar: the jaws would grip it"
        )
    through = p["outline_through_mm"]
    bottom = -through
    clear = jaw_top + CLEAR_MM

    # PH01: the strap in its blank, back face up. Model -> work: X = e1 - y,
    # Y = x - bar edge, Z = z + t (the front face on the spoil plate).
    e1 = p["top_waste_mm"]
    edge = p["bar_edge_offset_mm"]
    x_lo, x_hi = c["inner_top"][0], c["outer_foot"][0]
    for key in ("inner_foot", "outer_top"):
        x_lo, x_hi = min(x_lo, c[key][0]), max(x_hi, c[key][0])
    # The strap centred across the bar: equal waste at its widest corners.
    _agree(plan, "bar_edge_offset_mm", x_hi + (bar_w - (x_hi - x_lo)) / 2)

    def strap_xy(x: float, y: float) -> tuple[float, float]:
        return (e1 - y, x - edge)

    corners = [
        strap_xy(*c[key])
        for key in ("outer_top", "inner_top", "inner_foot", "outer_foot")
    ]
    # Every side strip of the frame and both end pieces hold STRIP_MIN past
    # the cutter's swath.
    ys = [y for _x, y in corners]
    strips = {
        "fixed-jaw side": -max(ys) - e8,
        "moving-jaw side": bar_w + min(ys) - e8,
        "left end": e1 - e8,
        "right end": p["blank_length_min_mm"] - e1 - g["rise"] - e8,
    }
    for what, width in strips.items():
        if width < STRIP_MIN_MM - 1e-6:
            raise ValueError(
                f"the strap blank's {what} strip is {width:.2f} mm past the cutter"
            )
    hole = strap_xy(*g["hole"])
    # The spoil plate (6 in, shorter than the strap) sits under the strap's
    # top end, its left end set inside the blank's within its band: the hole
    # and the outline's plunge (mid top end) bear on it at the band's far
    # end; the foot is cut over air, hanging on its tabs.
    spoil_at = p["spoil_plate_start_max_mm"]
    if not 0.0 < p["spoil_plate_start_min_mm"] < spoil_at:
        raise ValueError("process.spoil_plate_start band is not inside the blank")
    if hole[0] - d15 / 2 < spoil_at + CLEARANCE_MM:
        raise ValueError("the screw hole is off the spoil plate's left end")
    if corners[0][0] - 2 * r8 < spoil_at - 1e-6:
        raise ValueError("the outline's plunge at the top end is off the spoil plate")

    # The screw hole: spot on the countersink at the thinnest bar's top
    # (a thicker bar spots a little wider, still under the #15); the #15's
    # full diameter drill_past into the spoil plate.
    spot_z = t_min - _spot_depth(p["spot_dia_mm"])
    _agree(plan, "spot_z_mm", spot_z)
    tip = -(p["drill_past_mm"] + _point(d15))
    _agree(plan, "drill_tip_mm", tip)
    if not math.isclose(_op_with_cut(plan, "screw drill")[0]["peck"]["step_mm"], d15):
        raise ValueError("'screw drill' pecks are not one drill diameter")

    # Outlines: levels from the thickest bar's top to through_mm into the
    # spoil plate; tabs on the bar's underside.
    n = int(p["outline_levels"])
    step = (t_max + through) / n
    _agree(plan, "outline_level_mm", step)
    levels = [_r(t_max - k * step) for k in range(1, n + 1)]
    for name in ("strap outline", "plate outline"):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), step, abs_tol=1e-3):
            raise ValueError(f"'{name}' axial_doc_mm is not process.outline_level_mm")
    if e8_tool["flute_length_mm"] < t_max + through + SAFE_MM:
        raise ValueError("the 1/8 in end mill's flutes do not reach through the bar")
    tab_top = p["tab_thickness_mm"]
    _agree(plan, "tab_top_mm", tab_top)
    if not levels[-1] < 0 < tab_top < levels[0]:
        raise ValueError("the tabs do not stand between the outline's levels")
    tab_w = p["tab_width_mm"]

    def tabs_on(
        name: str, corners_: list, side: int, stations: list[float]
    ) -> list[dict[str, Any]]:
        out = []
        for k, x in enumerate(stations):
            box = _tab_box(corners_, side, x, r8, tab_w)
            box.update(
                name=f"{name} {k + 1}",
                top=tab_top,
                floor=0.0,
                thickness=p["tab_thickness_mm"],
            )
            out.append(box)
        return out

    strap_stations = [
        p[f"tab_station_{k}_mm"] for k in range(1, int(p["strap_tabs"]) + 1)
    ]
    # Each tab's box (the tab and the cutter's diameter) clear of the end
    # corners' arcs by 1 mm.
    margin = tab_w / 2 + r8 + r8 + 1.0
    for x in strap_stations:
        if not corners[0][0] + margin <= x <= corners[3][0] - margin:
            raise ValueError(
                "a strap tab's box reaches the corners at the strap's ends"
            )
    gaps = [b - a for a, b in zip([corners[0][0]] + strap_stations, strap_stations)]
    gaps.append(corners[3][0] - strap_stations[-1])
    if max(gaps) > p["tab_pitch_max_mm"] + 1e-6:
        raise ValueError(
            "a run of the strap between tabs is over process.tab_pitch_max_mm"
        )
    strap_tabs = tabs_on("strap inner", corners, 1, strap_stations) + tabs_on(
        "strap outer", corners, 3, strap_stations
    )
    # The tabs off the foot and its corners, where the lower plate sits
    # flush: no stub to file there.
    plate_zone = corners[3][0] - (
        g["lower_y"] + g["plate_t"] - g["corners"]["outer_foot"][1]
    )
    for box in strap_tabs:
        if box["x"][1] > plate_zone - 1e-6 and box["x"][0] < corners[3][0]:
            raise ValueError("a strap tab lies beside the lower plate's seat")
    strap_outline = _laps(corners, r8, 0, levels, t_max, strap_tabs, clear)

    # PH02: two plate blanks end to end, each plate's bonded end to -X,
    # centred across the bar. Model (lower plate) -> work: X = -z + e2 + z_bond
    # (the bond face at X = e2), Y = -x - bar_w / 2, Z = y - y_lower.
    e2 = p["plate_end_waste_mm"]
    _agree(
        plan, "plate_end_waste_mm", (p["plate_blank_length_min_mm"] - g["reach"]) / 2
    )
    pitch = p["plate_pitch_mm"]
    _agree(
        plan,
        "plate_pitch_mm",
        (p["plate_blank_length_min_mm"] + p["plate_blank_length_max_mm"]) / 2,
    )
    half_w = g["plate_w"] / 2
    plate_corners: list[list[tuple[float, float]]] = []
    plate_tabs: list[dict[str, Any]] = []
    for k in range(2):
        x0 = k * pitch + e2
        x1 = x0 + g["reach"]
        y0, y1 = -bar_w / 2 - half_w, -bar_w / 2 + half_w
        pc = [(x1, y1), (x0, y1), (x0, y0), (x1, y0)]
        plate_corners.append(pc)
        # Two tabs a side, a quarter of the reach in from each end.
        stations = [x0 + g["reach"] / 4, x0 + 3 * g["reach"] / 4]
        if k == 0:
            _agree(plan, "plate_tab_station_1_mm", stations[0])
            _agree(plan, "plate_tab_station_2_mm", stations[1])
        plate_tabs += tabs_on(f"plate {k + 1} top", pc, 0, stations)
        plate_tabs += tabs_on(f"plate {k + 1} bottom", pc, 2, stations)
    lmin, lmax = p["plate_blank_length_min_mm"], p["plate_blank_length_max_mm"]
    plate_strips = {
        "plate side": bar_w / 2 - half_w - e8,
        "plate 1 left end": e2 - e8,
        "plate 1 right end": lmin - (e2 + g["reach"]) - e8,
        "plate 2 left end": pitch + e2 - lmax - e8,
        "plate 2 right end": 2 * lmin - (pitch + e2 + g["reach"]) - e8,
    }
    for what, width in plate_strips.items():
        if width < STRIP_MIN_MM - 1e-6:
            raise ValueError(
                f"the plate blanks' {what} strip is {width:.2f} mm past the cutter"
            )
    plate_outline: list[str] = []
    for pc in plate_corners:
        plate_outline += _laps(pc, r8, 3, levels, t_max, plate_tabs, clear)

    # PH03: the bonded strap in the vise, plates up. Model -> work: X = y - y_foot,
    # Y = x - x_outer (the plates' outer sides on the fixed jaw), Z = -z + z_end.
    z_end = -(g["t"] + g["reach"])
    x_outer = half_w
    foot_y = g["corners"]["outer_foot"][1]
    slot_y = 0.0 - x_outer
    lower = (g["lower_y"] - foot_y, g["lower_y"] + g["plate_t"] - foot_y)
    upper = (g["upper_y"] - foot_y, g["upper_y"] + g["plate_t"] - foot_y)
    # The stack the upper plate is set from in Setup 5: between the plates'
    # facing faces, equal to the drawing's drop on a strap cut to its rise.
    _agree(plan, "plate_gap_mm", upper[0] - lower[1])
    # Width: the 1/8 in cutter on two passes either side of the centre line.
    offset = p["slot_offset_mm"]
    width = e8 + 2 * offset
    _agree(plan, "slot_width_mm", width)
    if not g["slot_band"][0] + 0.01 <= width <= g["slot_band"][1] - 0.01:
        raise ValueError(
            f"slot {width:.4f} wide is not inside its band {g['slot_band']}"
        )
    arm = half_w - width / 2
    if not g["arm_band"][0] <= arm <= g["arm_band"][1]:
        raise ValueError(f"the slot's arms {arm:.3f} wide are outside their band")
    if offset >= r8:
        raise ValueError("the slot's two passes leave a ridge between them")
    # The slot's floor corners are the end mill's square corners, under
    # the drawing's R.08 MAX.
    if g["corner_r_max"] <= 0:
        raise ValueError("the slots' corner limit is not a positive radius")
    m = int(p["slot_levels"])
    depth = g["slot_depth"]
    _agree(plan, "slot_level_mm", depth / m)
    if depth / m > p["slot_level_max_mm"] + 1e-6:
        raise ValueError("a slot level is deeper than process.slot_level_max_mm")
    if not math.isclose(_cut(plan, "slots", "axial_doc_mm"), depth / m, abs_tol=1e-3):
        raise ValueError("'slots' axial_doc_mm is not process.slot_level_mm")
    slot_levels = [_r(-depth * k / m) for k in range(1, m + 1)]
    if e8_tool["flute_length_mm"] < depth + CLEARANCE_MM:
        raise ValueError("the 1/8 in end mill's flutes do not reach the slot's floor")
    # Heights in Setups 5-6: the strap's back on the support block (a 1-2-3
    # block, 1 in high, on the vise bed), the packing block on its front.
    strap_back = p["support_block_mm"]
    jaw_top_6 = p["vise_jaw_height_mm"] - strap_back - (g["t"] + g["reach"])
    _agree(plan, "slot_jaw_top_mm", jaw_top_6)
    packing_top = p["packing_block_mm"] + g["t"] - (g["t"] + g["reach"])
    _agree(plan, "packing_top_mm", packing_top)
    if jaw_top_6 >= 0.0:
        raise ValueError("the jaws' top stands over the plates' far ends")
    if p["support_block_mm"] + g["t"] > p["vise_jaw_height_mm"] - p["vise_grip_min_mm"]:
        raise ValueError("the jaws grip the plates less than the shop's minimum")
    # The collet's nose over the packing block at the slot's floor, and the
    # flutes all out of the collet.
    proj = p["slot_projection_min_mm"]
    if -depth + proj < packing_top + CLEARANCE_MM - 1e-6:
        raise ValueError("the 1/8 in end mill's collet reaches the packing block")
    if proj < e8_tool["flute_length_mm"] + 1.0 - 1e-6:
        raise ValueError("the 1/8 in end mill would be gripped on its flutes")
    x_start = upper[1] + r8 + CLEARANCE_MM
    x_end = lower[0] - r8 - CLEARANCE_MM
    clear_6 = max(packing_top, 0.0) + CLEAR_MM
    ya, yb = slot_y - offset, slot_y + offset
    slots = [
        f"G0 Z{_r(clear_6):.3f}",
        f"G0 {_xy(x_start, ya)}",
        f"G0 Z{_r(SAFE_MM):.3f}",
    ]
    for z in slot_levels:
        slots += [
            f"G1 Z{_r(z):.3f} F{{feed}}",
            f"G1 {_xy(x_end, ya)} F{{feed}}",
            f"G1 {_xy(x_end, yb)} F{{feed}}",
            f"G1 {_xy(x_start, yb)} F{{feed}}",
            f"G1 {_xy(x_start, ya)} F{{feed}}",
        ]
    slots.append(f"G0 Z{_r(clear_6):.3f}")

    # The 1/8 in collet's and the chuck's noses over the jaws (PH01/PH02
    # cut within a holder's radius of the jaws): each tool's least
    # projection keeps its nose above the jaw tops at its deepest point.
    for what, deepest, projection in (
        ("1/8 in end mill's collet", bottom, p["eighth_projection_min_mm"]),
        ("#15's chuck", tip, p["drill_projection_min_mm"]),
        ("centre drill's chuck", spot_z, p["drill_projection_min_mm"]),
    ):
        if deepest + projection < jaw_top + CLEARANCE_MM - 1e-6:
            raise ValueError(f"the {what} nose reaches the jaw tops")
    if p["eighth_projection_min_mm"] < e8_tool["flute_length_mm"] + 1.0 - 1e-6:
        raise ValueError("the 1/8 in end mill would be gripped on its flutes")

    # Speeds and feeds: the 1/8 in end mill's shop settings; the drills' and
    # the spot's from the plan's cited rates.
    e8_setting = shop["settings"][_op_with_cut(plan, "strap outline")[0]["settings"]]
    sl_setting = shop["settings"][_op_with_cut(plan, "slots")[0]["settings"]]
    if (
        _op_with_cut(plan, "plate outline")[0]["settings"]
        != _op_with_cut(plan, "strap outline")[0]["settings"]
    ):
        raise ValueError("the strap's and the plates' outlines name different settings")
    for setting in (e8_setting, sl_setting):
        if setting["tool"] != "endmill-carbide-3fl-1-8":
            raise ValueError(
                f"setting for {setting['tool']} named where endmill-carbide-3fl-1-8 cuts"
            )
    _agree(plan, "em_rpm", e8_setting["rpm"])
    _agree(
        plan,
        "em_feed_per_min_mm",
        e8_setting["rpm"] * e8_setting["flutes"] * e8_setting["chip_load_mm_per_tooth"],
    )
    _agree(plan, "slot_rpm", sl_setting["rpm"])
    _agree(
        plan,
        "slot_feed_per_min_mm",
        sl_setting["rpm"] * sl_setting["flutes"] * sl_setting["chip_load_mm_per_tooth"],
    )
    speeds = {}
    for name, rpm_key, feed_key in (
        ("screw spot", "spot_rpm", "spot_feed_per_min_mm"),
        ("screw drill", "drill_rpm", "drill_feed_per_min_mm"),
        ("strap outline", "em_rpm", "em_feed_per_min_mm"),
        ("plate outline", "em_rpm", "em_feed_per_min_mm"),
        ("slots", "slot_rpm", "slot_feed_per_min_mm"),
    ):
        op, cut = _op_with_cut(plan, name)
        rpm = _resolve(plan, cut.get("rpm", op.get("rpm", p[rpm_key])), f"'{name}' rpm")
        if not math.isclose(rpm, p[rpm_key]):
            raise ValueError(f"'{name}' rpm {rpm:g} is not process.{rpm_key}")
        if "feed_mm_min" in cut:
            feed = _cut(plan, name, "feed_mm_min")
            if not math.isclose(feed, p[feed_key], abs_tol=1e-6):
                raise ValueError(f"'{name}' feed_mm_min is not process.{feed_key}")
        speeds[name] = (p[rpm_key], p[feed_key])
    plunge = p["plunge_feed_per_min_mm"]

    names = {t_["id"]: t_["name"] for t_ in plan["tools"]}
    numbers = {
        t_["id"]: k
        for k, t_ in enumerate((t_ for t_ in plan["tools"] if t_["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    frames = {
        "strap": {"origin": [edge, e1, -t], "axes": [[0, -1, 0], [1, 0, 0], [0, 0, 1]]},
        "plate": {
            "origin": [-bar_w / 2, g["lower_y"], e2 - t],
            "axes": [[0, 0, -1], [-1, 0, 0], [0, 1, 0]],
        },
        "slots": {
            "origin": [x_outer, foot_y, z_end],
            "axes": [[0, 1, 0], [1, 0, 0], [0, 0, -1]],
        },
    }
    stock_strap = ((0.0, p["blank_length_max_mm"]), (-bar_w, 0.0), (0.0, t_max))
    stock_plates = ((0.0, 2 * lmax), (-bar_w, 0.0), (0.0, t_max))
    stock_slots = (
        (0.0, g["rise"]),
        (-(x_hi - x_lo) - (x_outer - x_hi), 0.0),
        (-(g["t"] + g["reach"]), 0.0),
    )

    def job(
        key: str,
        label: str,
        tool: str,
        dia: float,
        shape: str,
        rpm: float,
        feed: float,
        plunge_: float,
        frame: str,
        stock: tuple,
        lines: list[str],
        flutes: int | None = None,
        tip_angle: float | None = None,
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "flutes": flutes,
            "tip_angle": tip_angle,
            "rpm": rpm,
            "feed": feed,
            "plunge": plunge_,
            "frame": frame,
            "label": label,
            "stock": stock,
            "ops": [[key, label, lines]],
        }

    sp_rpm, sp_feed = speeds["screw spot"]
    dr_rpm, dr_feed = speeds["screw drill"]
    em_rpm, em_feed = speeds["strap outline"]
    sl_rpm, sl_feed = speeds["slots"]
    jobs = [
        job(
            "strap_spot",
            "spot the screw hole",
            "spot",
            dspot,
            "drill",
            sp_rpm,
            sp_feed,
            sp_feed,
            "strap",
            stock_strap,
            _spot(hole, t_max, spot_z, clear),
            tip_angle=CENTRE_DRILL["point_deg"],
        ),
        job(
            "strap_drill",
            "drill the screw hole #15",
            "drill-15",
            d15,
            "drill",
            dr_rpm,
            dr_feed,
            dr_feed,
            "strap",
            stock_strap,
            _pecked(hole, t_max, tip, d15, clear),
            tip_angle=DRILL_POINT_DEG,
        ),
        job(
            "strap_outline",
            "strap outline on tabs",
            "em-eighth",
            e8,
            "endmill",
            em_rpm,
            em_feed,
            plunge,
            "strap",
            stock_strap,
            strap_outline,
            flutes=3,
        ),
        job(
            "plate_outline",
            "plate outlines on tabs",
            "em-eighth",
            e8,
            "endmill",
            em_rpm,
            em_feed,
            plunge,
            "plate",
            stock_plates,
            plate_outline,
            flutes=3,
        ),
        job(
            "slots",
            "both slots in line",
            "em-eighth",
            e8,
            "endmill",
            sl_rpm,
            sl_feed,
            sl_feed,
            "slots",
            stock_slots,
            slots,
            flutes=3,
        ),
    ]

    # Keep-outs. PH01/PH02: the jaws on the bar's edges from Z0 to their
    # top, along the whole blank. PH03: the jaws on the plates' sides to
    # their top, the packing block on the plates' inner sides, and each
    # plate's two arms beside the slot's widest limit.
    long = p["blank_length_max_mm"] + 2 * JAW_DEPTH_MM
    jaws = [
        _box("fixed jaw", (-JAW_DEPTH_MM, long), (0.0, JAW_DEPTH_MM), jaw_top),
        _box(
            "moving jaw",
            (-JAW_DEPTH_MM, long),
            (-bar_w - JAW_DEPTH_MM, -bar_w),
            jaw_top,
        ),
    ]
    gap = 2 * half_w + p["packing_width_mm"]
    span6 = (p["slot_jaw_start_mm"], p["slot_jaw_start_mm"] + p["vise_jaw_width_mm"])
    w_max = g["slot_band"][1]
    keep6 = [
        _box("fixed jaw", span6, (0.0, JAW_DEPTH_MM), jaw_top_6),
        _box("moving jaw", span6, (-gap - JAW_DEPTH_MM, -gap), jaw_top_6),
        _box(
            "packing block",
            (0.0, p["packing_length_mm"]),
            (-gap, -2 * half_w),
            packing_top,
        ),
    ]
    for name, (a, b) in (("lower plate", lower), ("upper plate", upper)):
        keep6 += [
            _box(f"{name} outer arm", (a, b), (slot_y + w_max / 2, 0.0), 0.0),
            _box(f"{name} inner arm", (a, b), (-2 * half_w, slot_y - w_max / 2), 0.0),
        ]
    # The slot's least width reached at its floor across each plate's
    # thickness, both sides.
    corners6 = [
        [_r(x), _r(slot_y + s * g["slot_band"][0] / 2)]
        for a, b in (lower, upper)
        for x in (a, (a + b) / 2, b)
        for s in (-1.0, 1.0)
    ]

    tn = numbers
    expect: list[list[Any]] = []
    elements = _elements(corners, "strap")
    plate_elements = [
        e for k, pc in enumerate(plate_corners) for e in _elements(pc, f"plate {k + 1}")
    ]
    hole_xy = [[_r(hole[0]), _r(hole[1])]]
    name = "PH01_strap"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": jaw_top,
                "tools": [tn["spot"], tn["drill-15"], tn["em-eighth"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[sp_rpm], [dr_rpm], [em_rpm]]}],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(min(tip, bottom))}],
        [f"{name}@0", "holes", {"centres": hole_xy, "z_bottom": _r(spot_z)}],
        [f"{name}@0", "rapids_clear", {"z_top": t_max}],
        [f"{name}@0", "vertical_below_top", {"z_top": t_max}],
        [f"{name}@0", "air_feed", {"z_top": t_max}],
        [f"{name}@0", "keep_out", {"radius": dspot / 2, "boxes": jaws}],
        [f"{name}@1", "holes", {"centres": hole_xy, "z_bottom": _r(tip)}],
        [f"{name}@1", "rapids_clear", {"z_top": t_max, "open_holes": hole_xy}],
        [f"{name}@1", "vertical_below_top", {"z_top": t_max}],
        [f"{name}@1", "air_feed", {"z_top": t_max}],
        [f"{name}@1", "keep_out", {"radius": d15 / 2, "boxes": jaws}],
        [f"{name}@2", "rapids_clear", {"z_top": t_max}],
        [f"{name}@2", "air_feed", {"z_top": t_max}],
        [f"{name}@2", "depth", {"z_min": _r(bottom)}],
        [f"{name}@2", "keep_out", {"radius": r8, "boxes": jaws}],
        [
            f"{name}@2",
            "outline",
            {
                "elements": elements,
                "z_top": t_max,
                "passes": [{"offset": r8, "levels": levels}],
                "tabs": strap_tabs,
                "cut": "conventional",
                "part": "left",
            },
        ],
    ]
    name = "PH02_plates"
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": jaw_top, "tools": [tn["em-eighth"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[em_rpm]]}],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(bottom)}],
        [name, "rapids_clear", {"z_top": t_max}],
        [name, "air_feed", {"z_top": t_max}],
        [name, "keep_out", {"radius": r8, "boxes": jaws}],
        [
            name,
            "outline",
            {
                "elements": plate_elements,
                "z_top": t_max,
                "passes": [{"offset": r8, "levels": levels}],
                "tabs": plate_tabs,
                "cut": "conventional",
                "part": "left",
            },
        ],
    ]
    name = "PH03_slots"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": max(packing_top, 0.0),
                "tools": [tn["em-eighth"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[sl_rpm]]}],
        [name, "pauses", {"z_top": 0.0, "count": 0}],
        [name, "depth", {"z_min": _r(-depth)}],
        [name, "rapids_clear", {"z_top": 0.0}],
        [name, "air_feed", {"z_top": 0.0}],
        [name, "keep_out", {"radius": r8, "boxes": keep6}],
        [name, "cleared", {"points": corners6, "radius": r8, "z": _r(-depth)}],
    ]

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
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Pen hanger {key}", ctx["step"], frame["origin"], frame["axes"]
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
            tip_angle=section.get("tip_angle"),
        )
        for key, label, lines in section["ops"]:
            ops[key] = rt.custom(target, tc, label, lines)
    ops.update(ctx["manual"])
    rt.generate(doc)
    return {"ops": ops}


# The as-machined report (``cad/scripts/_as_machined.py``) cannot take this
# part: it is built up from three blanks (the strap's, PH01; the two plates'
# end to end in PH02's one frame) bonded at gauge-block places before PH03,
# and the report holds one blank per part.
AS_MACHINED_NOT_COVERED = (
    "a built-up part: the STEP is the strap with two bonded guide plates, cut"
    " from three blanks (the strap's in PH01, the two plates' end to end in"
    " PH02, whose one frame maps only the lower plate onto the model) and"
    " bonded at gauge-block places before PH03 slots them; the report holds"
    " one blank per part"
)

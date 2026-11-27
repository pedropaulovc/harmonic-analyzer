"""FreeCAD CAM recipe for MHA-CH-07, the fulcrum keeper.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The keeper's sizes
come from the feature export (its sides, inner face, lug outer face, foot
tip, seat and stepped foot top, the crown, the bore, the plain foot hole and
the crown tap); the blank, the skims, levels, spots, tips and the stacks from
``plan.toml`` ``[parameters]`` and ``milling_cuts``; cutter diameters, speeds
and feeds from the shop (``shop/``) and the plan's authored settings. Every
path is written here (``rt.custom``): straight lines and arcs a recipe can
state exactly.

The keeper is the pivot bracket's shape (``ch_pivot_bracket``) turned a
quarter about the height: the bracket's X is the keeper's -Z, its Z the
keeper's X. The route and every computation below are written in the
bracket's axes (:func:`_bracket`: the far side F is the bracket's west side
W, the near side N its east side, the inner face I its inboard face, the lug
its ear, the foot tip its foot end, the crown its arch); the frames go back
to the keeper's model axes for the STEP import (:func:`_model_frame`).

Route (the agent's for speed; plan text in ``plan.toml``): one 3/4 in square
1018 blank about 1.35 long per run, the bar's length along the keeper's
height. Lying on the 1 in + 1/2 in parallel stacks: FK01 skims the far side
F, FK02 (F down) faces the near side N to the width. Upright on the 1 in
parallels: FK03 faces the seat, spots and drills the #41 foot hole from it
into the waste above the .227 stepped foot. Lying, the inner face I up: FK04
profiles the crown through the lug and spots, drills D and opens F the bore
through it, both into the waste the step removes; the jaws grip only that
waste. Lying, I down: FK05 faces the foot tip to the length and mills the open
step to the .32 lug and .227 foot top (#3744 Panel F), opening the bore and
the foot hole with the 1/2 in end mill. Upright on the seat: FK06 spots and
drills 1/16 through the crown into the bore; FK07 is the hand-tap stop.

Work frames (G54), each set in its setup:
- FK01-FK02: X0 the blank's left end, Y0 the fixed jaw (I), Z0 the stacks.
- FK03: X0 I, Y0 the fixed jaw (F), Z0 the faced seat.
- FK04: X0 the seat (the right end, the part to -X), Y0 F, Z0 the stacks.
- FK05: X0 the seat (the left end), Y0 F, Z0 the stacks (I).
- FK06-FK07: X0 I (the right side, the part to -X), Y0 F, Z0 the
  parallels (the seat).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, real G0 above the stock; the
crown is profiled climb (G2 round the outside). The crown hole is tapped by
hand (FluidNC cannot rigid-tap; owner, Pedro, 2026-11-17), the T-handle
wrench's centre hole on the spring point of the Fisher tap guide in the 1/2 in
R8 collet (owner, Pedro, 2026-11-21), spindle off, the operator jogging Z down
to push the point home. FluidNC refuses jogs while an M0 holds the program, so
the tap stop is a file of its own that ends with M30 over its hole.
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "ch_fulcrum_keeper"
COMMENT = "MHA-CH-07 fulcrum keeper"
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("FK01_far", ("far_side",)),
    ("FK02_width", ("near_side",)),
    ("FK03_seat", (("seat",), ("foot_spot",), ("foot_drill",))),
    (
        "FK04_crown_bore",
        (("crown",), ("bore_spot",), ("bore_drill",), ("bore_open",)),
    ),
    ("FK05_step", ("step",)),
    ("FK06_crown", (("crown_spot",), ("crown_drill",))),
    ("FK07_crown_tap", ("crown_tap",)),
)
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-41",
    "drill-d",
    "drill-f",
    "drill-1-16",
    "tap-guide",
)
IN = 25.4
CENTRE_DRILL = {
    "pilot_mm": 5 / 64 * IN,
    "pilot_length_mm": 5 / 64 * IN,
    "body_mm": 3 / 16 * IN,
    "point_deg": 60.0,
    "pilot_point_deg": 118.0,
}
DRILL_POINT_DEG = 118.0
UNF_1_72_MAJOR_MM = 0.073 * IN
MACHINE_Z_TOP_MM = 0.0
APPROACH_MM = 2.54
FACE_OVERHANG_MM = 0.5
SAFE_MM = 1.0
CLEAR_MM = 5.0
PECK_REENTRY_MM = 0.5
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
OUTLINE_TOL_MM = 0.01
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
    """(rpm, mm/min) of the operation holding ``cut``."""
    op, record_cut = _op_with_cut(plan, cut)
    if "settings" not in op:
        return _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    record = shop["settings"][op["settings"]]
    rpm = float(record["rpm"])
    feed = record["chip_load_mm_per_tooth"] * record["flutes"] * rpm
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


def _levels(top: float, bottom: float, max_step: float) -> list[float]:
    """Equal step-down levels no deeper than ``max_step`` from ``top`` to
    ``bottom``, ``bottom`` last."""
    n = math.ceil((top - bottom) / max_step - 1e-9)
    return [top - (top - bottom) * (k + 1) / n for k in range(n - 1)] + [bottom]


def _r(value: float) -> float:
    """A coordinate as the post prints it (3 places)."""
    return round(value + 0.0, 3)


def _box(
    name: str, x: tuple[float, float], y: tuple[float, float], z_top: float
) -> dict[str, Any]:
    return {"name": name, "x": [x[0], x[1]], "y": [y[0], y[1]], "z_top": z_top}


def _agree(plan: dict[str, Any], key: str, value: float) -> None:
    """A plan parameter the recipe recomputes from the export and the shop."""
    stated = plan["parameters"][key]
    if not math.isclose(stated, value, abs_tol=PLAN_TOL_MM):
        raise ValueError(f"process.{key} {stated:g}, the recipe computes {value:.4f}")


def _inside(value: float, band: list[float]) -> bool:
    """``value`` in ``band``, to the export's 0.001 mm rounding."""
    return band[0] - 1e-3 <= value <= band[1] + 1e-3


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, abs_tol=1e-3)


def _spot_depth(dia: float) -> float:
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not 0 < dia <= body:
        raise ValueError(f"spot Ø{dia:.3f} is over the body Ø{body:.3f}")
    if dia < pilot:
        return dia / 2 / math.tan(math.radians(CENTRE_DRILL["pilot_point_deg"] / 2))
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _frame(
    origin: list[float], y_axis: list[float], z_axis: list[float]
) -> dict[str, Any]:
    y, z = y_axis, z_axis
    x = [
        y[1] * z[2] - y[2] * z[1],
        y[2] * z[0] - y[0] * z[2],
        y[0] * z[1] - y[1] * z[0],
    ]
    return {"origin": origin, "axes": [x, y, z]}


def _to(frame: dict[str, Any], p: list[float]) -> list[float]:
    d = [p[i] - frame["origin"][i] for i in range(3)]
    return [sum(axis[i] * d[i] for i in range(3)) for axis in frame["axes"]]


def _bracket(v: list[float]) -> list[float]:
    return [-v[2] + 0.0, v[1], v[0]]


def _keeper(v: list[float]) -> list[float]:
    return [v[2], v[1], -v[0] + 0.0]


def _model_frame(frame: dict[str, Any]) -> dict[str, Any]:
    return {
        "origin": _keeper(frame["origin"]),
        "axes": [_keeper(axis) for axis in frame["axes"]],
    }


def _spot(xy: tuple[float, float], top: float, z: float, clear: float) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G0 Z{r_plane:.3f}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: tuple[float, float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    depths = []
    depth = top
    while depth - peck > tip + 1e-6:
        depth -= peck
        depths.append(_r(depth))
    depths.append(_r(tip))
    lines = [f"G0 Z{clear:.3f}", f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _stepover(y: tuple[float, float], max_step: float) -> tuple[int, float]:
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    return n, span / n


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    n, step = _stepover(y, max_step)
    if 2 * radius - step < FACE_OVERHANG_MM:
        raise ValueError(
            f"a {step:.3f} stepover leaves the first pass short of the edge"
        )
    first = y[1] + radius - step
    return [_r(first - k * step) for k in range(n)]


def _face(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    clear = _r(top + CLEAR_MM)
    x0, x1 = _r(x[0]), _r(x[1])
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{x0:.3f} Y{ys[0]:.3f}",
        f"G0 Z{_r(top + SAFE_MM):.3f}",
    ]
    for z in levels:
        lines.append(f"G1 Z{_r(z):.3f} F{{feed}}")
        for k, y in enumerate(ys):
            if k:
                lines.append(f"G1 Y{y:.3f} F{{feed}}")
            lines.append(f"G1 X{x1 if k % 2 == 0 else x0:.3f} F{{feed}}")
        if len(ys) % 2:
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    f = features["features"]

    def plane(name: str, axis: str) -> float:
        p = f[name]["plane"]
        if p["axis"] != axis:
            raise ValueError(f"{name}: expected a plane normal to {axis}")
        return float(p["value"])

    def moved(hole: dict[str, Any]) -> dict[str, Any]:
        return {**hole, "at": _bracket(hole["at"]), "axis": _bracket(hole["axis"])}

    west, east = -plane("far_side", "z"), -plane("near_side", "z")
    width = east - west
    if not _close(width, f["far_side"]["width_nominal"]) or not _close(west, -east):
        raise ValueError(f"F to N {width:.4f} is not the width, centred on Z0")
    seat, foot_top = plane("seat", "y"), plane("foot_top", "y")
    if seat != 0.0 or not _close(foot_top - seat, f["foot_top"]["height_nominal"]):
        raise ValueError("the seat is not Y0 or the foot top not its height above it")
    inboard = plane("inner_face", "x")
    outboard = plane("lug_outer_face", "x")
    foot_end = plane("foot_tip", "x")
    ear = outboard - inboard
    length = foot_end - inboard
    if not _close(ear, f["lug_outer_face"]["thickness_nominal"]):
        raise ValueError(f"I to the lug's outer face {ear:.4f} is not its thickness")
    if not _close(length, f["foot_tip"]["length_nominal"]):
        raise ValueError(f"I to the foot tip {length:.4f} is not the length")
    crown = f["crown"]
    centre, radius = _bracket(crown["center"]), crown["radius_nominal"]
    if (
        crown["axis"] != [1.0, 0.0, 0.0]
        or not _close(centre[0], 0.0)
        or not _close(2 * radius, width)
        or not _close(centre[1] + radius, crown["overall_height_ref"])
    ):
        raise ValueError("crown: expected a full round about X over the width")
    height = centre[1] + radius
    bore = moved(f["bore"])
    if (
        bore["axis"] != [0.0, 0.0, -1.0]
        or not _close(bore["at"][2], outboard)
        or not _close(bore["at"][0], 0.0)
        or not _close(bore["at"][1], centre[1])
        or not bore.get("thru")
    ):
        raise ValueError(
            "bore: expected through the lug along -X from its outer face,"
            " on the crown's centre"
        )
    hold = moved(f["foot_hole"])
    if (
        hold["axis"] != [0.0, -1.0, 0.0]
        or not _close(hold["at"][1], foot_top)
        or not _close(hold["at"][0], 0.0)
        or not hold.get("thru")
        or "cbore_dia" in hold
        or not outboard < hold["at"][2] < foot_end
    ):
        raise ValueError(
            "foot_hole: expected a plain through-hole along -Y from the stepped foot top"
        )
    tap = moved(f["crown_tap"])
    if (
        tap["axis"] != [0.0, -1.0, 0.0]
        or not _close(tap["at"][1], height)
        or not _close(tap["at"][0], 0.0)
        or tap["into"] != "bore"
        or tap["thread"] != "#1-72 UNF-2B"
        or not inboard < tap["at"][2] < outboard
    ):
        raise ValueError(
            "crown_tap: expected a #1-72 along -Y from the apex into the bore"
        )
    return {
        "west": west,
        "width": width,
        "foot_top": foot_top,
        "inboard": inboard,
        "ear": ear,
        "length": length,
        "arch_centre": centre,
        "radius": radius,
        "height": height,
        "bore": bore,
        "hold": hold,
        "tap": tap,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    width, ear, length, height = g["width"], g["ear"], g["length"], g["height"]
    west, inboard, foot_top = g["west"], g["inboard"], g["foot_top"]
    radius = g["radius"]
    bore_y = g["bore"]["at"][1]
    bore_dia = g["bore"]["dia"]

    section = p["blank_section_mm"]
    _agree(plan, "blank_section_mm", p["blank_section_in"] * IN)
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_min_mm", blank_min)
    _agree(plan, "blank_length_max_mm", blank_max)
    seat_skim, west_skim = p["seat_skim_mm"], p["west_skim_mm"]
    top_max = blank_max - seat_skim
    _agree(plan, "upright_top_max_mm", top_max)
    if blank_min - seat_skim <= height:
        raise ValueError(
            f"the shortest blank less the seat skim, {blank_min - seat_skim:.3f}, is not over the height {height:.3f}"
        )
    west_level = section - west_skim
    if west_level <= width or section <= length:
        raise ValueError(
            "the section leaves nothing to face to the width or the length"
        )

    em = _shop_tool(plan, shop, "em-half")["diameter_mm"]
    d41 = _shop_tool(plan, shop, "drill-41")["diameter_mm"]
    dd = _shop_tool(plan, shop, "drill-d")["diameter_mm"]
    df = _shop_tool(plan, shop, "drill-f")["diameter_mm"]
    d16 = _shop_tool(plan, shop, "drill-1-16")["diameter_mm"]
    tap_drill = _shop_tool(plan, shop, "tap-1-72")["tap_drill_mm"]
    r = em / 2
    hold_band, tap_band = g["hold"]["dia"], g["tap"]["dia"]
    if not _inside(d41, hold_band):
        raise ValueError(f"#41 Ø{d41} is outside the foot hole's band {hold_band}")
    if not _inside(df, bore_dia):
        raise ValueError(f"F Ø{df} is outside the bore's band {bore_dia}")
    if not dd < df:
        raise ValueError(f"D Ø{dd} is not under the F Ø{df}")
    if not _inside(d16, tap_band) or not _close(d16, tap_drill):
        raise ValueError(
            f"1/16 Ø{d16} is not the #1-72 tap's drill in the band {tap_band}"
        )

    face_cap = p["face_stepover_max_mm"]
    step_max = p["step_stepover_max_mm"]
    face_cuts = {
        "west side": "lying_stepover_mm",
        "width": "lying_stepover_mm",
        "seat": "seat_stepover_mm",
    }
    chart_cuts = ("foot end", "step", "arch rough", "arch finish", "step wall")
    face_rpm, face_feed = _setting(plan, shop, "west side")
    em_rpm, em_feed = _setting(plan, shop, "step")
    for name in (*face_cuts, *chart_cuts):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), em, abs_tol=1e-6):
            raise ValueError(
                f"'{name}' cutter Ø{_cut(plan, name, 'cutter_dia_mm')}, the end mill is Ø{em}"
            )
    for names, first, speeds in (
        (face_cuts, "west side", (face_rpm, face_feed)),
        (chart_cuts, "step", (em_rpm, em_feed)),
    ):
        for name in names:
            if _setting(plan, shop, name) != speeds:
                raise ValueError(f"'{name}' runs at another setting than '{first}'")
    for name, key in (
        *face_cuts.items(),
        ("foot end", "step_stepover_max_mm"),
        ("step", "step_stepover_max_mm"),
    ):
        if not math.isclose(_cut(plan, name, "radial_woc_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' radial_woc_mm is not process.{key}")
    level_max = p["face_step_max_mm"]
    for name, doc in (
        ("west side", west_skim),
        ("seat", seat_skim),
        ("width", level_max),
        ("foot end", level_max),
        ("step", p["step_level_mm"]),
    ):
        if not math.isclose(_cut(plan, name, "axial_doc_mm"), doc, abs_tol=1e-6):
            raise ValueError(f"'{name}' axial_doc_mm is not its skim or level")
    if west_skim > level_max + 1e-9:
        raise ValueError("the F skim is over one level")
    width_levels = _levels(west_level, width, level_max)
    foot_levels = _levels(section, length, level_max)
    for what, top, bottom, levels in (
        ("N's", west_level, width, width_levels),
        ("the foot tip's", section, length, foot_levels),
    ):
        if not _close((top - bottom) / len(levels), level_max):
            raise ValueError(f"{what} levels are not face_step_max_mm each")
    step_levels = _levels(length, ear, level_max)
    _agree(plan, "step_level_mm", (length - ear) / len(step_levels))

    stock_a = p["arch_finish_stock_mm"]
    arch_depth = ear + p["arch_past_mm"]
    _agree(plan, "arch_depth_mm", arch_depth)
    rough_levels = _levels(section, section - arch_depth, p["arch_rough_level_mm"])
    _agree(plan, "arch_rough_level_mm", arch_depth / len(rough_levels))
    corner = math.hypot(width / 2, top_max - g["arch_centre"][1])
    rough_woc = corner - radius - stock_a
    _agree(plan, "arch_rough_woc_mm", rough_woc)
    if corner > radius + stock_a + 2 * r:
        raise ValueError("the rough arch pass leaves the longest blank's corners uncut")
    for name, axial, woc in (
        ("arch rough", p["arch_rough_level_mm"], p["arch_rough_woc_mm"]),
        ("arch finish", arch_depth, stock_a),
    ):
        if not (
            math.isclose(_cut(plan, name, "axial_doc_mm"), axial, abs_tol=1e-6)
            and math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6)
        ):
            raise ValueError(f"'{name}' depth or width is not the plan's")

    spot_rpm, spot_feed = _setting(plan, shop, "hold spot")
    spots = {}
    for name, key, drill in (
        ("hold spot", "hold_spot_dia_mm", d41),
        ("bore spot", "bore_spot_dia_mm", dd),
        ("apex spot", "apex_spot_dia_mm", d16),
    ):
        if _setting(plan, shop, name) != (spot_rpm, spot_feed):
            raise ValueError(f"'{name}' runs at another speed than 'hold spot'")
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), p[key], abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not process.{key}")
        if p[key] >= drill:
            raise ValueError(
                f"'{name}' is not under its drill: it would chamfer the hole"
            )
        spots[name] = _spot_depth(p[key])
    for name, dia in (
        ("hold drill", d41),
        ("bore drill", dd),
        ("bore open", df),
        ("apex drill", d16),
    ):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter_dia_mm is not its tool's Ø{dia}")
    hold_rpm, hold_feed = _setting(plan, shop, "hold drill")
    drill_rpm, drill_feed = _setting(plan, shop, "bore drill")
    open_rpm, open_feed = _setting(plan, shop, "bore open")
    apex_rpm, apex_feed = _setting(plan, shop, "apex drill")

    hold_full = -(foot_top + p["hold_drill_past_mm"])
    hold_tip = hold_full - _point(d41)
    _agree(plan, "hold_tip_height_mm", blank_min - seat_skim + hold_tip)
    out_z = section - ear
    bore_full = out_z - p["bore_drill_past_mm"]
    bore_tip = bore_full - _point(dd)
    open_tip = bore_full - _point(df)
    _agree(plan, "bore_tip_height_mm", bore_tip)
    _agree(plan, "bore_open_tip_height_mm", open_tip)
    arch_bottom = section - arch_depth
    bore_r = bore_dia[0] / 2
    wall = bore_y + math.sqrt(bore_r**2 - (d16 / 2) ** 2)
    apex_full = wall - p["apex_drill_past_mm"]
    apex_tip = apex_full - _point(d16)
    _agree(plan, "apex_tip_height_mm", apex_tip)
    if apex_tip <= bore_y - bore_r:
        raise ValueError("the 1/16's point reaches the bore's far wall")
    major = UNF_1_72_MAJOR_MM
    major_wall = bore_y + math.sqrt(bore_r**2 - (major / 2) ** 2)
    _agree(plan, "tap_reach_min_mm", height - major_wall + p["plug_tap_lead_mm"])
    _agree(plan, "tap_reach_max_mm", height - (bore_y - bore_r) - 1.0)
    for op, (key, peck) in (
        (_op_with_cut(plan, "hold drill")[0], ("{{cad.foot_top_height_mm}}", "none")),
        (_op_with_cut(plan, "bore drill")[0], (ear + p["bore_drill_past_mm"], "none")),
        (
            _op_with_cut(plan, "apex drill")[0],
            (
                "{{cad.crown_tap_into_axis_mm}}",
                {"step_mm": p["apex_peck_mm"], "retract": "full"},
            ),
        ),
    ):
        if op["hole_depth_mm"] != key or op["peck"] != peck:
            raise ValueError(f"{op['tool']}: hole_depth_mm or peck is not the recipe's")

    upright_grip = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    lying_grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "upright_grip_mm", upright_grip)
    _agree(plan, "lying_grip_mm", lying_grip)
    if arch_bottom <= lying_grip or ear <= lying_grip:
        raise ValueError("the arch or the step's floor reaches the jaw tops")
    projection = p["half_mill_projection_mm"]
    for what, top, deepest in (
        ("FK01", section, west_level),
        ("FK02", west_level, width),
        ("FK03", seat_skim, 0.0),
        ("FK04", section, arch_bottom),
        ("FK05", section, ear),
    ):
        if deepest + projection < top + CLEAR_MM:
            raise ValueError(
                f"{what}: the collet nose {projection:g} out comes to "
                f"{top - deepest - projection:.3f} above the stock top"
            )
    t = p["parallel_thickness_mm"]
    jaw_w = p["vise_jaw_width_mm"]
    for key, along in (
        ("vise_lying_inset_mm", blank_max),
        ("vise_upright_inset_mm", section),
        ("vise_seat_inset_mm", length),
    ):
        _agree(plan, key, -(jaw_w - along) / 2)
    machine = shop["machines"]["pm-30mv"]
    stack = (
        machine["spindle_to_table_mm"][1]
        - shop["limits"]["tool_change_clearance_mm"]
        - p["vise_bed_height_mm"]
        - p["parallel_height_mm"]
        - height
        - p["r8_collet_gauge_mm"]
    )
    _agree(plan, "tap_stack_max_mm", math.floor(stack / 0.254 + 1e-9) * 0.254)

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    raw_east = west - west_skim + section
    raw_foot = inboard + section
    frames = {
        "west": _frame([raw_east, -seat_skim, inboard], [0, 0, -1], [-1, 0, 0]),
        "width": _frame([west, top_max, inboard], [0, 0, -1], [1, 0, 0]),
        "seat": _frame([west, 0.0, inboard], [-1, 0, 0], [0, -1, 0]),
        "arch": _frame([west, 0.0, raw_foot], [-1, 0, 0], [0, 0, -1]),
        "step": _frame([west, 0.0, inboard], [-1, 0, 0], [0, 0, 1]),
        "apex": _frame([west, 0.0, inboard], [-1, 0, 0], [0, 1, 0]),
    }
    stocks = {
        "west": ((0.0, blank_max), (-section, 0.0), (0.0, section)),
        "width": ((0.0, blank_max), (-section, 0.0), (0.0, west_level)),
        "seat": ((0.0, section), (-width, 0.0), (-top_max, seat_skim)),
        "arch": ((-top_max, 0.0), (-width, 0.0), (0.0, section)),
        "step": ((0.0, top_max), (-width, 0.0), (0.0, section)),
        "apex": ((-length, 0.0), (-width, 0.0), (0.0, height)),
    }

    def xy(key: str, point: list[float]) -> list[float]:
        x, y, _z = _to(frames[key], point)
        return [_r(x), _r(y)]

    hold_xy = xy("seat", g["hold"]["at"])
    bore_xy = xy("arch", g["bore"]["at"])
    arch_c = xy("arch", g["arch_centre"])
    tap_xy = xy("apex", g["tap"]["at"])
    for key, point, want in (
        ("seat", [west, 0.0, inboard], [0.0, 0.0, 0.0]),
        ("arch", [west, 0.0, inboard], [0.0, 0.0, section]),
        ("step", [-west, foot_top, inboard + length], [foot_top, -width, length]),
        ("apex", [west, height, inboard], [0.0, 0.0, height]),
    ):
        if not all(_close(a, b) for a, b in zip(_to(frames[key], point), want)):
            raise ValueError(
                f"{key}: the frame does not put the part where its stock is"
            )
    holes = {"hold": [hold_xy], "bore": [bore_xy], "apex": [tap_xy]}
    _agree(plan, "foot_hole_station_from_i_mm", hold_xy[0])
    _agree(plan, "width_middle_mm", width / 2)
    for key, at in (("seat", hold_xy), ("arch", bore_xy), ("apex", tap_xy)):
        if not _close(-at[1], width / 2):
            raise ValueError(f"{key}: a hole is off the width's middle")

    def tool(key: str, rpm: float, feed: float, **extra: Any) -> dict[str, Any]:
        return {"tool": key, "rpm": rpm, "feed": feed, "plunge": feed, **extra}

    em_face = tool("em-half", face_rpm, face_feed, dia=em, shape="endmill", flutes=3)
    em_tool = tool("em-half", em_rpm, em_feed, dia=em, shape="endmill", flutes=3)
    spot_tool = tool(
        "spot",
        spot_rpm,
        spot_feed,
        dia=CENTRE_DRILL["body_mm"],
        shape="drill",
        tip_angle=CENTRE_DRILL["point_deg"],
    )

    def drill_tool(key: str, dia: float, rpm: float, feed: float) -> dict[str, Any]:
        return tool(key, rpm, feed, dia=dia, shape="drill", tip_angle=DRILL_POINT_DEG)

    def run(x: tuple[float, float]) -> tuple[float, float]:
        return (x[0] - r - APPROACH_MM, x[1] + r + APPROACH_MM)

    lying_ys = _stations((-section, 0.0), r, face_cap)
    seat_ys = _stations((-width, 0.0), r, face_cap)
    _agree(plan, "lying_stepover_mm", _stepover((-section, 0.0), face_cap)[1])
    _agree(plan, "seat_stepover_mm", _stepover((-width, 0.0), face_cap)[1])
    width_ys = _stations((-width, 0.0), r, step_max)
    blank_x = run((0.0, blank_max))
    wall_x = foot_top + r
    far_x = top_max + r + APPROACH_MM
    step_ys = [*width_ys[:-1], _r(-width)]
    if len(step_ys) % 2:
        raise ValueError("an odd number of step passes ends a level at the wall")
    if step_ys[0] < 0 or step_ys[-2] - r + width > step_max + 1e-9:
        raise ValueError("the step's stations leave W unswept or overload the E pass")
    gap = max(step_ys[k] - step_ys[k + 1] for k in range(1, len(step_ys) - 1, 2))
    scallop = r - math.sqrt(r**2 - (gap / 2) ** 2)
    _agree(plan, "wall_finish_woc_mm", scallop)
    for name, axial, woc in (("step wall", length - ear, p["wall_finish_woc_mm"]),):
        if not (
            math.isclose(_cut(plan, name, "axial_doc_mm"), axial, abs_tol=1e-3)
            and math.isclose(_cut(plan, name, "radial_woc_mm"), woc, abs_tol=1e-6)
        ):
            raise ValueError(f"'{name}' depth or width is not the recipe's")
    wall_y = (_r(r + APPROACH_MM), _r(-width - r - APPROACH_MM))
    step_lines = _step_lines(
        foot_levels,
        section,
        ear,
        step_levels,
        width_ys,
        step_ys,
        r,
        far_x,
        wall_x,
        wall_y,
    )

    cx, cy = arch_c
    lead = p["arch_lead_mm"]
    elements = [
        {
            "name": "east side",
            "start": [cx + lead, cy - radius],
            "end": [cx, cy - radius],
        },
        {
            "name": "arch, east half",
            "start": [cx, cy - radius],
            "end": [cx - radius, cy],
            "centre": [cx, cy],
        },
        {
            "name": "arch, west half",
            "start": [cx - radius, cy],
            "end": [cx, cy + radius],
            "centre": [cx, cy],
        },
        {
            "name": "west side",
            "start": [cx, cy + radius],
            "end": [cx + lead, cy + radius],
        },
    ]
    for element in elements:
        element["tol"] = OUTLINE_TOL_MM
    passes = [
        {"offset": r + stock_a, "levels": [_r(z) for z in rough_levels]},
        {"offset": r, "levels": [_r(arch_bottom)]},
    ]
    arch_lines: list[str] = []
    for pass_ in passes:
        o = pass_["offset"]
        for z in pass_["levels"]:
            arch_lines += [
                f"G0 Z{_r(section + CLEAR_MM):.3f}",
                f"G0 X{_r(cx + lead):.3f} Y{_r(cy - radius - o):.3f}",
                f"G0 Z{_r(section + SAFE_MM):.3f}",
                f"G1 Z{z:.3f} F{{feed}}",
                f"G1 X{_r(cx):.3f} F{{feed}}",
                f"G2 X{_r(cx - radius - o):.3f} Y{_r(cy):.3f} I0.000 J{_r(radius + o):.3f} F{{feed}}",
                f"G2 X{_r(cx):.3f} Y{_r(cy + radius + o):.3f} I{_r(radius + o):.3f} J0.000 F{{feed}}",
                f"G1 X{_r(cx + lead):.3f} F{{feed}}",
            ]
    arch_lines.append(f"G0 Z{_r(section + CLEAR_MM):.3f}")

    seat_top = seat_skim
    jobs = [
        {
            **em_face,
            "frame": "west",
            "label": "west side",
            "stock": stocks["west"],
            "ops": [
                ["far_side", "skim F", _face([west_level], section, blank_x, lying_ys)]
            ],
        },
        {
            **em_face,
            "frame": "width",
            "label": "east side",
            "stock": stocks["width"],
            "ops": [
                [
                    "near_side",
                    "face N to the width",
                    _face(width_levels, west_level, blank_x, lying_ys),
                ]
            ],
        },
        {
            **em_face,
            "frame": "seat",
            "label": "seat",
            "stock": stocks["seat"],
            "ops": [
                [
                    "seat",
                    "face the seat",
                    _face([0.0], seat_top, run((0.0, section)), seat_ys),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "seat",
            "label": "hold spot",
            "stock": stocks["seat"],
            "ops": [
                [
                    "foot_spot",
                    "spot the foot hole",
                    _spot(hold_xy, 0.0, -spots["hold spot"], CLEAR_MM),
                ]
            ],
        },
        {
            **drill_tool("drill-41", d41, hold_rpm, hold_feed),
            "frame": "seat",
            "label": "hold drill",
            "stock": stocks["seat"],
            "ops": [
                [
                    "foot_drill",
                    "drill the foot hole #41",
                    _pecked(hold_xy, 0.0, hold_tip, math.inf, CLEAR_MM),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "arch",
            "label": "crown",
            "stock": stocks["arch"],
            "ops": [["crown", "profile the crown", arch_lines]],
        },
        {
            **spot_tool,
            "frame": "arch",
            "label": "bore spot",
            "stock": stocks["arch"],
            "ops": [
                [
                    "bore_spot",
                    "spot the bore",
                    _spot(
                        bore_xy,
                        section,
                        section - spots["bore spot"],
                        section + CLEAR_MM,
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-d", dd, drill_rpm, drill_feed),
            "frame": "arch",
            "label": "bore drill",
            "stock": stocks["arch"],
            "ops": [
                [
                    "bore_drill",
                    "drill the bore D",
                    _pecked(bore_xy, section, bore_tip, math.inf, section + CLEAR_MM),
                ]
            ],
        },
        {
            **drill_tool("drill-f", df, open_rpm, open_feed),
            "frame": "arch",
            "label": "bore open",
            "stock": stocks["arch"],
            "ops": [
                [
                    "bore_open",
                    "open the bore F",
                    _pecked(bore_xy, section, open_tip, math.inf, section + CLEAR_MM),
                ]
            ],
        },
        {
            **em_tool,
            "frame": "step",
            "label": "step",
            "stock": stocks["step"],
            "ops": [["step", "face the foot tip, mill the step", step_lines]],
        },
        {
            **spot_tool,
            "frame": "apex",
            "label": "crown spot",
            "stock": stocks["apex"],
            "ops": [
                [
                    "crown_spot",
                    "spot the crown",
                    _spot(
                        tap_xy, height, height - spots["apex spot"], height + CLEAR_MM
                    ),
                ]
            ],
        },
        {
            **drill_tool("drill-1-16", d16, apex_rpm, apex_feed),
            "frame": "apex",
            "label": "crown drill",
            "stock": stocks["apex"],
            "ops": [
                [
                    "crown_drill",
                    "drill the crown hole 1/16",
                    _pecked(
                        tap_xy, height, apex_tip, p["apex_peck_mm"], height + CLEAR_MM
                    ),
                ]
            ],
        },
    ]
    manual = {
        "crown_tap": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: #1-72 TAP IN THE CROWN HOLE",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{tap_xy[0]:.3f} Y{tap_xy[1]:.3f}",
                "(#1-72 TAP IN THE CROWN HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND TO THE NOTED DRO Z, READ WITH THE POINT PUSHED HOME. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": tap_xy,
        }
    }

    def jaws(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (y[0] - JAW_DEPTH_MM, y[0]), z_top),
            _box("fixed jaw", span, (y[1], y[1] + JAW_DEPTH_MM), z_top),
        ]

    def parallels(
        z_top: float, x: tuple[float, float], y: tuple[float, float]
    ) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallels", span, (y[0], y[0] + t), z_top),
            _box("fixed-jaw parallels", span, (y[1] - t, y[1]), z_top),
        ]

    lying = (0.0, blank_max)
    keep = {
        "west": jaws(lying_grip, lying, (-section, 0.0)),
        "width": jaws(lying_grip, lying, (-section, 0.0)),
        "seat": jaws(
            upright_grip - (blank_min - seat_skim), (0.0, section), (-width, 0.0)
        )
        + parallels(-(blank_min - seat_skim), (0.0, section), (-width, 0.0)),
        "arch": jaws(lying_grip, (-blank_max, 0.0), (-width, 0.0))
        + parallels(0.0, (-blank_max, 0.0), (-width, 0.0)),
        "step": jaws(lying_grip, lying, (-width, 0.0))
        + parallels(0.0, lying, (-width, 0.0)),
        "apex": jaws(upright_grip, (-length, 0.0), (-width, 0.0))
        + parallels(0.0, (-length, 0.0), (-width, 0.0)),
    }

    tn = numbers
    expect: list[list[Any]] = []

    def face_checks(levels, top, y, span, frame, engagement) -> list[list[Any]]:
        return [
            ["rapids_clear", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            *[
                [
                    "face_passes",
                    {
                        "z": _r(z),
                        "y": list(y),
                        "max_engagement": engagement,
                        "radius": r,
                        "span": span,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ]
                for z in levels
            ],
            ["keep_out", {"radius": r, "boxes": keep[frame]}],
        ]

    def hole_checks(key, frame, top, bottom, radius) -> list[list[Any]]:
        return [
            ["holes", {"centres": holes[key], "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": holes[key]}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": keep[frame]}],
        ]

    for name, levels, top in (
        ("FK01_far", [west_level], section),
        ("FK02_width", width_levels, west_level),
    ):
        frame = "west" if name == "FK01_far" else "width"
        engagement = p["lying_stepover_mm"]
        expect += [
            [
                name,
                "tool_changes",
                {"z_top": top, "tools": [tn["em-half"]], "loads_first": True},
            ],
            [name, "spindle", {"rpm": [[face_rpm]]}],
            [name, "pauses", {"z_top": top, "count": 0}],
            [name, "depth", {"z_min": _r(levels[-1])}],
            *[
                [name, check, kwargs]
                for check, kwargs in face_checks(
                    levels, top, (-section, 0.0), blank_max, frame, engagement
                )
            ],
        ]

    name = "FK03_seat"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": seat_top,
                "tools": [tn["em-half"], tn["spot"], tn["drill-41"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[face_rpm], [spot_rpm], [hold_rpm]]}],
        [name, "pauses", {"z_top": seat_top, "count": 0}],
        [name, "depth", {"z_min": _r(hold_tip)}],
    ]
    for k, checks in enumerate(
        (
            [
                ["depth", {"z_min": 0.0}],
                *face_checks(
                    [0.0],
                    seat_top,
                    (-width, 0.0),
                    section,
                    "seat",
                    p["seat_stepover_mm"],
                ),
            ],
            hole_checks(
                "hold", "seat", 0.0, -spots["hold spot"], CENTRE_DRILL["body_mm"] / 2
            ),
            hole_checks("hold", "seat", 0.0, hold_tip, d41 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "FK04_crown_bore"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": section,
                "tools": [tn["em-half"], tn["spot"], tn["drill-d"], tn["drill-f"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[em_rpm], [spot_rpm], [drill_rpm], [open_rpm]]}],
        [name, "pauses", {"z_top": section, "count": 0}],
        [name, "depth", {"z_min": _r(open_tip)}],
    ]
    for k, checks in enumerate(
        (
            [
                ["depth", {"z_min": _r(arch_bottom)}],
                [
                    "outline",
                    {
                        "elements": elements,
                        "passes": passes,
                        "z_top": section,
                        "cut": "climb",
                        "part": "right",
                    },
                ],
                ["rapids_clear", {"z_top": section}],
                ["air_feed", {"z_top": section}],
                ["keep_out", {"radius": r, "boxes": keep["arch"]}],
            ],
            hole_checks(
                "bore",
                "arch",
                section,
                section - spots["bore spot"],
                CENTRE_DRILL["body_mm"] / 2,
            ),
            hole_checks("bore", "arch", section, bore_tip, dd / 2),
            hole_checks("bore", "arch", section, open_tip, df / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "FK05_step"
    floor_points = [
        [_r(x), _r(y)]
        for x in (foot_top + 0.1, (foot_top + top_max) / 2, top_max)
        for y in (-width, -width / 2, 0.0)
    ]
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": section, "tools": [tn["em-half"]], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[em_rpm]]}],
        [name, "pauses", {"z_top": section, "count": 0}],
        [name, "depth", {"z_min": _r(ear)}],
        *[
            [name, check, kwargs]
            for check, kwargs in face_checks(
                [*foot_levels, *step_levels],
                section,
                (-width, 0.0),
                top_max - foot_top - r,
                "step",
                step_max,
            )
        ],
        [name, "cleared", {"points": floor_points, "radius": r, "z": _r(ear)}],
        [
            name,
            "side_passes",
            {
                "axis": "X",
                "final": _r(wall_x),
                "raw": _r(wall_x + p["wall_finish_woc_mm"]),
                "max_step": p["wall_finish_woc_mm"],
                "direction": -1.0,
                "span": width,
                "below_z": length,
            },
        ],
        [
            name,
            "engagement",
            {
                "stock": stocks["step"],
                "radius": r,
                "max_radial": p["wall_finish_woc_mm"],
                "z": _r(ear),
                "window": [[_r(wall_x), _r(wall_x)], [wall_y[1], wall_y[0]]],
                "min_length": width,
                "cut": "climb",
            },
        ],
    ]

    name = "FK06_crown"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": height,
                "tools": [tn["spot"], tn["drill-1-16"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[spot_rpm], [apex_rpm]]}],
        [name, "pauses", {"z_top": height, "count": 0}],
        [name, "depth", {"z_min": _r(apex_tip)}],
    ]
    for k, checks in enumerate(
        (
            hole_checks(
                "apex",
                "apex",
                height,
                height - spots["apex spot"],
                CENTRE_DRILL["body_mm"] / 2,
            ),
            hole_checks("apex", "apex", height, apex_tip, d16 / 2),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "FK07_crown_tap"
    expect += [
        [
            name,
            "tap_stop",
            {"tool": tn["tap-guide"], "at": tap_xy, "machine_top": MACHINE_Z_TOP_MM},
        ],
        [name, "air_feed", {"z_top": height}],
    ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": {key: _model_frame(frame) for key, frame in frames.items()},
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": manual,
        "expect": expect,
    }


def _step_lines(
    foot_levels: list[float],
    section: float,
    ear: float,
    levels: list[float],
    ys: list[float],
    step_ys: list[float],
    radius: float,
    far_x: float,
    wall_x: float,
    wall_y: tuple[float, float],
) -> list[str]:
    foot = _face(foot_levels, section, (-radius - APPROACH_MM, far_x), ys)
    step = _face(levels, section, (far_x, wall_x), step_ys)
    clear = _r(section + CLEAR_MM)
    return [
        *foot,
        *step[1:],
        f"G0 X{_r(wall_x):.3f} Y{wall_y[0]:.3f}",
        f"G0 Z{_r(section + SAFE_MM):.3f}",
        f"G1 Z{_r(ear):.3f} F{{feed}}",
        f"G1 Y{wall_y[1]:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Fulcrum keeper {key}", ctx["step"], frame["origin"], frame["axes"]
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

"""FreeCAD CAM recipe for MHA-PD-18, the transgear arm.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. Every part size and
station comes from the feature export (the pivot round, the flanks' lean and
tangency, the square end's station and width, the bores, the spot face's
floor, the pin mouth's leg, the latch-pin hole); the blank, the holding, the
levels, the depths past the faces and the speeds from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters and the end mills'
settings from ``shop/``. Every path is written here (``rt.custom``). Typed
here, because neither record carries them: the #1 centre drill's catalogue
geometry (it sets the spot depth), the twist drills' 118° point, the 90°
chamfer mill's point, the safe and clearance heights, the jaws' depth (keep-out
shapes only) and the fixture screws' heads (keep-out shapes only).

Route (``plan.toml``): the arm is cut from one blank of 3/8 x 1 ground flat,
its faces as supplied. AR01 (Setup 2): the blank lies front face (datum A) down
on 1 in parallels, gripped by its edges; spot and drill the pivot bore (#14,
then #9 to size), spot, drill and ream
the pin bore through, plunge the rear spot face with the 1/2 in end mill,
chamfer the pin bore's rear mouth. Setup 3: a 1/2 in 6061 plate in the vise;
AR02 drills it for a #10-32 and a #4-40 screw under the two bores, AR03 and
AR04 stop for the hand taps; the arm is screwed down through its bores and
AR05 cuts the whole outline through into the plate (no tabs: the screws hold
it). Setup 4 drills and reams the blind latch-pin hole on the lathe (the arm
through the spindle, its square end in the 4-jaw): no NC.

Work frames (G54), each set in its setup:
- holes (AR01): X0 the blank's left end, Y0 the fixed jaw (the blank to −Y),
  Z0 the parallels' top (face A).
- plate (AR02-AR05): X0 the plate's left end, Y0 the fixed jaw (the plate to
  −Y), Z0 the plate's top (face A once the arm is on).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "pd_transgear_arm"
COMMENT = "MHA-PD-18 transgear arm"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job, or a manual
# section), joined at M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    (
        "AR01_holes",
        (
            ("holes_spot",),
            ("pivot_drill",),
            ("pin_drill",),
            ("spot_face",),
            ("pivot_drill_9",),
            ("pin_ream",),
            ("pin_mouth",),
        ),
    ),
    ("AR02_plate", (("plate_spot",), ("plate_drill_10",), ("plate_drill_4",))),
    ("AR03_tap_pivot", ("tap_pivot",)),
    ("AR04_tap_pin", ("tap_pin",)),
    ("AR05_outline", ("outline",)),
)
# Every program loads its own first tool (M6, the tool setter).
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the taps, the gauges and the files are not).
CAM_TOOLS = (
    "spot",
    "drill-14",
    "drill-32",
    "em-half",
    "drill-9",
    "reamer-1260",
    "chamfer",
    "drill-21",
    "drill-43",
    "tap-guide",
    "em-quarter",
)
IN = 25.4
# ANSI #1 combined drill and countersink, 60° included (the carbide set's
# trade size 1): the shop record names the set, not its geometry.
CENTRE_DRILL = {
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "body_mm": 1 / 8 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# The 90° chamfer mill's flutes run to a point (McMaster 3073A46, as the
# shop's tools.chamfer-mill-carbide-1-4-90 note reads it): a 45° half angle.
CHAMFER_HALF_DEG = 45.0
# The tap files' first motion: G53 G0 to machine Z0, the homed top (owner,
# Pedro, 2026-11-21: machine Z = 0 is the top of travel after homing).
MACHINE_Z_TOP_MM = 0.0
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the highest thing under the tool.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole stops this far above the last peck.
PECK_REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from its gripping face.
JAW_DEPTH_MM = IN
# The outline's tolerance on the cutter centre against its offset.
OUTLINE_TOL_MM = 0.005
# The fixture screws' socket heads (ASME B18.3, catalogue maxima): #10 Ø.312
# × .190 high, #4 Ø.183 × .112 high. Keep-out shapes only.
HEAD_10_MM = (0.312 * IN, 0.190 * IN)
HEAD_4_MM = (0.183 * IN, 0.112 * IN)
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# A reamer's stock on the diameter after its drill: .004–.016 in, the
# chucking-reamer allowance for these sizes.
REAM_STOCK_MM = (0.004 * IN, 0.016 * IN)


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


def _speed(plan: dict[str, Any], cut: str) -> tuple[float, float]:
    """(rpm, mm/min) the plan authors on a drill, reamer or plunge cut,
    agreeing with its operation's rpm."""
    op, _record = _op_with_cut(plan, cut)
    rpm, feed = _cut(plan, cut, "rpm"), _cut(plan, cut, "feed_mm_min")
    if float(op["rpm"]) != rpm:
        raise ValueError(f"'{cut}': its operation's rpm is not the cut's {rpm:g}")
    return rpm, feed


def _setting(
    plan: dict[str, Any], shop: dict[str, Any], cut: str
) -> tuple[float, float, int]:
    """(rpm, mm/min, flutes) from the shop setting the cut's operation names."""
    op, _record = _op_with_cut(plan, cut)
    setting = shop["settings"][op["settings"]]
    rpm, flutes = float(setting["rpm"]), int(setting["flutes"])
    return rpm, rpm * flutes * float(setting["chip_load_mm_per_tooth"]), flutes


def _shop_tool(plan: dict[str, Any], shop: dict[str, Any], tool: str) -> dict[str, Any]:
    ref = next(t["ref"] for t in plan["tools"] if t["id"] == tool)
    return shop["tools"][ref]


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


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the #1 centre drill's 60° countersink
    reaches ``dia``; refused unless it is between the pilot and the body."""
    pilot, body = CENTRE_DRILL["pilot_mm"], CENTRE_DRILL["body_mm"]
    if not pilot < dia <= body:
        raise ValueError(
            f"spot Ø{dia:.3f} is not between the pilot Ø{pilot:.3f} and the body Ø{body:.3f}"
        )
    half = math.radians(CENTRE_DRILL["point_deg"] / 2)
    return CENTRE_DRILL["pilot_length_mm"] + (dia - pilot) / 2 / math.tan(half)


def _point(dia: float) -> float:
    """A twist drill's point length."""
    return dia / 2 / math.tan(math.radians(DRILL_POINT_DEG / 2))


def _frame(
    origin: list[float], y_axis: list[float], z_axis: list[float]
) -> dict[str, Any]:
    """A right-handed setup frame from its Y and Z model axes: X = Y × Z."""
    y, z = y_axis, z_axis
    x = [
        y[1] * z[2] - y[2] * z[1],
        y[2] * z[0] - y[0] * z[2],
        y[0] * z[1] - y[1] * z[0],
    ]
    return {"origin": origin, "axes": [x, y, z]}


def _to(frame: dict[str, Any], p: list[float]) -> list[float]:
    """Model point ``p`` in the setup frame."""
    d = [p[i] - frame["origin"][i] for i in range(3)]
    return [sum(axis[i] * d[i] for i in range(3)) for axis in frame["axes"]]


def _plunge(xy: list[float], top: float, z: float, clear: float) -> list[str]:
    """Straight down from the R plane to ``z`` and back out at feed (a spot,
    a reamer, a spot-face plunge, a chamfer): no rapid leaves the hole."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(z):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _pecked(
    xy: list[float], top: float, tip: float, peck: float, clear: float
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
    lines = [f"G0 Z{clear:.3f}", f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}", f"G0 Z{r_plane:.3f}"]
    previous = None
    for z in depths:
        if previous is not None:
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + PECK_REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The arm's sizes from the export, each checked against the frame the
    recipe assumes: the pivot axis at the model origin on face A (z 0), the
    rear face at the stock's thickness, the arm along +X, every bore along
    −Z from the rear face, the latch-pin hole along −X from the square end."""
    f = features["features"]
    front, rear, end = f["front_face"], f["rear_face"], f["end_face"]
    if front["plane"]["axis"] != "z" or front["plane"]["value"] != 0.0:
        raise ValueError("front_face (A) is not the model's z 0 plane")
    thickness = float(rear["plane"]["value"])
    thickness_band = [float(v) for v in rear["thickness_stock"]]
    pivot, pin = f["pivot_bore"], f["pin_bore"]
    for name, hole, process in (
        ("pivot_bore", pivot, "drill"),
        ("pin_bore", pin, "ream"),
    ):
        if hole["axis"] != [0.0, 0.0, -1.0] or not math.isclose(
            hole["at"][2], thickness
        ):
            raise ValueError(f"{name} does not run down from the rear face")
        if (
            hole["at"][1] != 0.0
            or hole.get("process") != process
            or hole.get("thru") is not True
        ):
            raise ValueError(f"{name} is not a through {process} on the centreline")
    if pivot["at"][:2] != [0.0, 0.0]:
        raise ValueError("pivot_bore is not on the model origin")
    station = float(pin["at"][0])
    if not math.isclose(station, float(pin["station_basic"]), abs_tol=1e-9):
        raise ValueError("pin_bore stands off its BASIC station")
    arc, flanks = f["pivot_end"], f["flanks"]
    radius = float(arc["radius_nominal"])
    if arc["center"] != [0.0, 0.0, 0.0]:
        raise ValueError("pivot_end is not about the pivot axis")
    tip = float(end["station_nominal"])
    if end["plane"] != {"frame": "model", "axis": "x", "value": tip}:
        raise ValueError("end_face is not the square end at its station")
    half = float(end["width_nominal"]) / 2
    upper, lower = flanks["normals"]
    nx, ny = float(upper[0]), float(upper[1])
    if not (math.isclose(lower[0], nx) and math.isclose(lower[1], -ny) and nx > 0 < ny):
        raise ValueError(
            "the flanks are not mirror images leaning in toward the square end"
        )
    if not math.isclose(nx * tip + ny * half, radius, abs_tol=1e-6):
        raise ValueError(
            "the square end's corners are not on the flanks tangent to the pivot round"
        )
    spot = f["spot_face"]
    if spot["about"] != "pivot_bore" or spot["floor_from"] != "front_face":
        raise ValueError("spot_face is not the pivot's floor from face A")
    mouth = f["pin_mouth"]
    if (
        mouth["edge_of"] != "pin_bore"
        or mouth["at_face"] != "rear_face"
        or mouth["angle_deg"] != 45.0
    ):
        raise ValueError("pin_mouth is not a 45° break on the pin bore's rear mouth")
    latch = f["latch_pin_hole"]
    if (
        latch["axis"] != [-1.0, 0.0, 0.0]
        or latch["at"][:2] != [tip, 0.0]
        or latch.get("process") != "ream"
    ):
        raise ValueError(
            "latch_pin_hole is not reamed along −X from the square end's middle"
        )
    if latch["height_from"] != "front_face":
        raise ValueError("latch_pin_hole's height is not from face A")
    for name in ("dowel_holes", "plate_taps"):
        if f[name].get("made_at") != "assembly":
            raise ValueError(f"{name} is not left to the assembly")
    return {
        "thickness": thickness,
        "thickness_max": thickness_band[1],
        "radius": radius,
        "tip": tip,
        "half": half,
        "normal": (nx, ny),
        "station": station,
        "pivot_dia": [float(v) for v in pivot["dia"]],
        "pin_dia": [float(v) for v in pin["dia"]],
        "floor": [float(v) for v in spot["floor"]],
        "floor_nominal": float(spot["floor_nominal"]),
        "spot_dia": [float(v) for v in spot["dia"]],
        "leg": [float(v) for v in mouth["leg"]],
        "leg_nominal": float(mouth["leg_nominal"]),
        "latch_dia": [float(v) for v in latch["dia"]],
        "latch_depth_min": float(latch["depth"][0]),
        "latch_depth_max": float(latch["depth"][1]),
        "latch_z": float(latch["at"][2]),
    }


def _outline_lap(
    g: dict[str, Any], offset: float, origin: tuple[float, float]
) -> tuple[list[float], list[str]]:
    """One anticlockwise lap of the cutter centre ``offset`` outside the
    outline in the plate frame (the pivot at ``origin``): from the square end's
    middle up its upper half, round its corner, along the upper flank, round
    the pivot end, along the lower flank, round the lower corner and back to
    the start. Returns the start point and the lap's G1/G3 lines."""
    ox, oy = origin
    tip, half, radius = g["tip"], g["half"], g["radius"]
    nx, ny = g["normal"]

    def at(x: float, y: float) -> str:
        return f"X{_r(ox + x):.3f} Y{_r(oy + y):.3f}"

    start = [_r(ox + tip + offset), _r(oy)]
    big = radius + offset
    lines = [
        f"G1 {at(tip + offset, half)} F{{feed}}",
        f"G3 {at(tip + offset * nx, half + offset * ny)} I{_r(-offset):.3f} J0.000 F{{feed}}",
        f"G1 {at(big * nx, big * ny)} F{{feed}}",
        f"G3 {at(big * nx, -big * ny)} I{_r(-big * nx):.3f} J{_r(-big * ny):.3f} F{{feed}}",
        f"G1 {at(tip + offset * nx, -half - offset * ny)} F{{feed}}",
        f"G3 {at(tip + offset, -half)} I{_r(-offset * nx):.3f} J{_r(offset * ny):.3f} F{{feed}}",
        f"G1 {at(tip + offset, 0.0)} F{{feed}}",
    ]
    return start, lines


def _outline_elements(
    g: dict[str, Any], origin: tuple[float, float]
) -> list[dict[str, Any]]:
    """The outline in the plate frame, anticlockwise, the pivot round split
    at its far point into two minor arcs."""
    ox, oy = origin
    tip, half, radius = g["tip"], g["half"], g["radius"]
    nx, ny = g["normal"]

    def p(x: float, y: float) -> list[float]:
        return [ox + x, oy + y]

    centre = p(0.0, 0.0)
    return [
        {
            "name": "end face upper",
            "start": p(tip, 0.0),
            "end": p(tip, half),
            "tol": OUTLINE_TOL_MM,
        },
        {
            "name": "upper flank",
            "start": p(tip, half),
            "end": p(radius * nx, radius * ny),
            "tol": OUTLINE_TOL_MM,
        },
        {
            "name": "pivot round upper",
            "start": p(radius * nx, radius * ny),
            "end": p(-radius, 0.0),
            "centre": centre,
            "tol": OUTLINE_TOL_MM,
        },
        {
            "name": "pivot round lower",
            "start": p(-radius, 0.0),
            "end": p(radius * nx, -radius * ny),
            "centre": centre,
            "tol": OUTLINE_TOL_MM,
        },
        {
            "name": "lower flank",
            "start": p(radius * nx, -radius * ny),
            "end": p(tip, -half),
            "tol": OUTLINE_TOL_MM,
        },
        {
            "name": "end face lower",
            "start": p(tip, -half),
            "end": p(tip, 0.0),
            "tol": OUTLINE_TOL_MM,
        },
    ]


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    t, t_max = g["thickness"], g["thickness_max"]

    def dia(tool: str) -> float:
        return float(_shop_tool(plan, shop, tool)["diameter_mm"])

    d14, d9, d32, d21, d43 = (
        dia("drill-14"),
        dia("drill-9"),
        dia("drill-32"),
        dia("drill-21"),
        dia("drill-43"),
    )
    em2, em4, chamfer_dia = dia("em-half"), dia("em-quarter"), dia("chamfer")
    r126, r124 = dia("reamer-1260"), dia("reamer-1240")
    # The pivot bore is the #9 drill's hole (the drawing's DRILL THRU): the
    # drill's size is the band's low limit, and the #14 goes first under it.
    if not g["pivot_dia"][0] - 1e-6 <= d9 <= g["pivot_dia"][1]:
        raise ValueError(f"the Ø{d9:.4f} drill is outside pivot_bore's band")
    if d14 >= d9:
        raise ValueError("the #14 is not under the pivot bore's #9 drill")
    for name, reamer, band in (
        ("pin_bore", r126, g["pin_dia"]),
        ("latch_pin_hole", r124, g["latch_dia"]),
    ):
        if not band[0] - 1e-6 <= reamer <= band[1]:
            raise ValueError(
                f"the Ø{reamer:.4f} reamer is outside {name}'s band {band}"
            )
    for drill, reamer, what in (
        (d32, r126, "#32"),
        (d32, r124, "#32"),
    ):
        if not REAM_STOCK_MM[0] <= reamer - drill <= REAM_STOCK_MM[1]:
            raise ValueError(
                f"the {what} leaves {reamer - drill:.3f} mm for the Ø{reamer:.4f} reamer"
            )
    if not g["spot_dia"][0] - 1e-6 <= em2 <= g["spot_dia"][1]:
        raise ValueError(
            f"the Ø{em2} end mill is outside the spot face's band {g['spot_dia']}"
        )

    # Setup 2: the blank on the parallels, face A down (Z0), its left end X0,
    # the fixed jaw Y0; the pivot at pivot_from_end_mm, the arm on the blank's
    # middle.
    width = p["blank_width_mm"]
    lo, hi = p["blank_length_min_mm"], p["blank_length_max_mm"]
    x_pivot = p["pivot_from_end_mm"]
    if not (x_pivot - g["radius"] > 0 and x_pivot + g["tip"] < lo):
        raise ValueError("the arm does not lie inside the shortest blank")
    if g["radius"] > width / 2:
        raise ValueError("the pivot round is wider than the blank")
    _agree(
        plan,
        "blank_end_margin_min_mm",
        min(x_pivot - g["radius"], lo - x_pivot - g["tip"]),
    )
    jaw_top = p["vise_jaw_height_mm"] - p["parallel_height_mm"]
    _agree(plan, "holes_jaw_top_mm", jaw_top)
    if jaw_top <= t_max:
        raise ValueError(
            "the jaws' top stands under the blank's rear face: the parallels are too tall"
        )
    frames = {
        "holes": _frame([-x_pivot, width / 2, 0.0], [0, 1, 0], [0, 0, 1]),
    }
    xy_pivot = [_r(v) for v in _to(frames["holes"], [0.0, 0.0, 0.0])[:2]]
    xy_pin = [_r(v) for v in _to(frames["holes"], [g["station"], 0.0, 0.0])[:2]]
    holes = [xy_pivot, xy_pin]
    spot_dia = p["spot_dia_mm"]
    if not math.isclose(
        _cut(plan, "holes spot", "cutter_dia_mm"), spot_dia, abs_tol=1e-6
    ):
        raise ValueError("'holes spot' cutter_dia_mm is not process.spot_dia_mm")
    if spot_dia >= d32:
        raise ValueError("the spot is not under the #32: it would chamfer the bores")
    spot_depth = _spot_depth(spot_dia)
    past = p["drill_past_mm"]
    tip_14 = -(past + _point(d14))
    tip_9 = -(past + _point(d9))
    tip_32 = -(past + _point(d32))
    _agree(plan, "drill_14_tip_mm", tip_14)
    _agree(plan, "drill_9_tip_mm", tip_9)
    _agree(plan, "drill_32_tip_mm", tip_32)
    ream_tip = -p["ream_past_mm"]
    import cam_nc

    if p["ream_past_mm"] <= cam_nc.ream_full_diameter_past_min_mm(plan, "reamer-1260"):
        raise ValueError(
            "the reamer's full diameter does not reach face A (cnc.ream-full-diameter)"
        )
    # The reamer's flat end runs out between the parallels.
    cam_nc.ream_end_face_clear("reamer-1260", ream_tip, -past, 0.0, -math.inf)
    # The parallels stand under the blank's edges: every drill and reamer
    # passes between them.
    gap = width / 2 - p["parallel_thickness_mm"]
    if max(d14, d9) / 2 >= gap:
        raise ValueError("a drill through the pivot reaches the parallels")
    floor = g["floor_nominal"]
    if not g["floor"][0] <= floor <= g["floor"][1]:
        raise ValueError("the spot face's floor target is outside its band")
    # The pin mouth: the chamfer mill's point below the rear face by the
    # bore's radius plus the leg (45°: the leg is the cone's run past the
    # bore's edge). The stock's thickness band moves the leg as much.
    leg = g["leg_nominal"]
    chamfer_tip = t - (r126 / 2 + leg) / math.tan(math.radians(CHAMFER_HALF_DEG))
    _agree(plan, "chamfer_tip_mm", chamfer_tip)
    swing = g["thickness_max"] - t
    if not (g["leg"][0] <= leg - swing and leg + swing <= g["leg"][1]):
        raise ValueError(
            "the stock's thickness band carries the pin mouth's leg out of its band"
        )
    if (r126 / 2 + leg) * 2 >= chamfer_dia:
        raise ValueError("the pin mouth's break is wider than the chamfer mill")
    clear_holes = jaw_top + CLEAR_MM

    # Setup 3: the plate on the parallels (Z0 its top), its left end X0, the
    # fixed jaw Y0; the arm face A down on it, the pivot at
    # pivot_on_plate_x_mm, the arm along the plate's middle.
    plate_w, plate_l, plate_t = (
        p["plate_width_mm"],
        p["plate_length_mm"],
        p["plate_thickness_mm"],
    )
    px = p["pivot_on_plate_x_mm"]
    origin = (px, -plate_w / 2)
    if not (px - g["radius"] > 0 and px + g["tip"] < plate_l):
        raise ValueError("the arm does not lie wholly on the plate")
    ef_r = p["edge_finder_dia_mm"] / 2
    _agree(plan, "arm_x_set_mm", px - p["pivot_from_end_mm"] - ef_r)
    _agree(plan, "arm_y_set_mm", -plate_w / 2 + p["blank_width_mm"] / 2 + ef_r)
    plate_jaw_top = p["vise_jaw_height_mm"] - p["parallel_height_mm"] - plate_t
    _agree(plan, "plate_jaw_top_mm", plate_jaw_top)
    frames["plate"] = _frame([-px, plate_w / 2, 0.0], [0, 1, 0], [0, 0, 1])
    plate_pivot = [_r(v) for v in _to(frames["plate"], [0.0, 0.0, 0.0])[:2]]
    plate_pin = [_r(v) for v in _to(frames["plate"], [g["station"], 0.0, 0.0])[:2]]
    plate_holes = [plate_pivot, plate_pin]
    plate_tip_21 = -(plate_t + p["plate_drill_past_mm"] + _point(d21))
    plate_tip_43 = -(plate_t + p["plate_drill_past_mm"] + _point(d43))
    _agree(plan, "plate_drill_21_tip_mm", plate_tip_21)
    _agree(plan, "plate_drill_43_tip_mm", plate_tip_43)
    plate_gap = plate_w / 2 - p["parallel_thickness_mm"]
    if d21 / 2 >= plate_gap:
        raise ValueError("a plate drill reaches the parallels")
    # The screw heads: #10 on the spot face's floor, #4 on the rear face.
    heads = [
        {
            "name": "pivot screw head",
            "centre": plate_pivot,
            "radius": HEAD_10_MM[0] / 2,
            "z_top": floor + HEAD_10_MM[1],
        },
        {
            "name": "pin screw head",
            "centre": plate_pin,
            "radius": HEAD_4_MM[0] / 2,
            "z_top": t_max + HEAD_4_MM[1],
        },
    ]
    clear_outline = max(h["z_top"] for h in heads) + CLEAR_MM

    # The outline: one rough pass finish_mm outside the outline in levels to
    # through_mm into the plate, then the finish pass at the cutter's radius
    # in one level at that depth.
    finish, through = p["outline_finish_mm"], p["outline_through_mm"]
    rough_offset, finish_offset = em4 / 2 + finish, em4 / 2
    _agree(plan, "outline_rough_offset_mm", rough_offset)
    depth = t_max + through
    count = math.ceil(depth / p["outline_level_max_mm"] - 1e-9)
    _agree(plan, "outline_levels", count)
    _agree(plan, "outline_level_mm", depth / count)
    rough_levels = [_r(t_max - depth * k / count) for k in range(1, count + 1)]
    bottom = _r(-through)
    # Every scrap of the blank lies within the rough pass's reach: the
    # farthest corner of the longest blank from the outline is under the
    # cutter's far edge, so no loose piece is left when it cuts through.
    reach = rough_offset + em4 / 2
    nx, ny = g["normal"]
    corners = [
        (-x_pivot, width / 2),
        (hi - x_pivot, width / 2),
    ]
    far = max(
        math.hypot(corners[0][0], corners[0][1]) - g["radius"],
        math.hypot(corners[1][0] - g["tip"], corners[1][1] - g["half"]),
    )
    _agree(plan, "blank_scrap_reach_mm", far)
    if far >= reach:
        raise ValueError(
            f"a blank corner stands {far:.3f} from the outline, past the rough pass's {reach:.3f}"
        )
    rough_start, rough_lap = _outline_lap(g, rough_offset, origin)
    finish_start, finish_lap = _outline_lap(g, finish_offset, origin)
    outline_lines = [
        f"G0 Z{_r(clear_outline):.3f}",
        f"G0 X{rough_start[0]:.3f} Y{rough_start[1]:.3f}",
        f"G0 Z{_r(t_max + SAFE_MM):.3f}",
    ]
    for z in rough_levels:
        outline_lines += [f"G1 Z{z:.3f} F{{plunge}}", *rough_lap]
    outline_lines += [
        f"G0 Z{_r(clear_outline):.3f}",
        f"G0 X{finish_start[0]:.3f} Y{finish_start[1]:.3f}",
        f"G0 Z{_r(t_max + SAFE_MM):.3f}",
        f"G1 Z{bottom:.3f} F{{plunge}}",
        *finish_lap,
        f"G0 Z{_r(clear_outline):.3f}",
    ]

    # Setup 4 (the lathe, no NC): the latch-pin hole's depths from the
    # tailstock, checked against the export.
    latch_ream = p["latch_ream_depth_mm"]
    if not g["latch_depth_min"] <= latch_ream <= g["latch_depth_max"]:
        raise ValueError("the latch ream's full diameter misses its depth band")
    latch_drill = p["latch_drill_depth_mm"]
    if latch_drill < latch_ream + p["latch_ream_lead_mm"] + p["drill_past_mm"]:
        raise ValueError(
            "the latch drill's full diameter stops short of the reamer's tip"
        )
    if latch_drill + _point(d32) > g["latch_depth_max"]:
        raise ValueError("the latch drill's point runs past the depth the walls allow")
    _agree(plan, "arm_length_mm", g["radius"] + g["tip"])

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    speeds = {
        cut: _speed(plan, cut)
        for cut in (
            "holes spot",
            "pivot drill",
            "pin drill",
            "spot face",
            "pivot drill 9",
            "pin ream",
            "pin mouth",
            "plate spot",
            "plate drill 10",
            "plate drill 4",
        )
    }
    out_rpm, out_feed, out_flutes = _setting(plan, shop, "outline rough")
    if _setting(plan, shop, "outline finish")[:2] != (out_rpm, out_feed):
        raise ValueError("the outline's passes are not at one setting")
    plunge = p["outline_plunge_feed_per_min_mm"]
    # Each drill's peck as its operation states it: pecks of its step_mm with
    # full retract, or "none" (one feed down).
    pecks: dict[str, float] = {}
    for cut in ("pivot drill", "pin drill", "plate drill 10", "plate drill 4"):
        stated = _op_with_cut(plan, cut)[0]["peck"]
        if stated == "none":
            pecks[cut] = math.inf
        elif isinstance(stated, dict) and stated.get("retract") == "full":
            pecks[cut] = float(stated["step_mm"])
        else:
            raise ValueError(
                f"'{cut}' peck is neither \"none\" nor a full-retract step"
            )

    def tool(
        key: str,
        cut: str,
        *,
        dia: float,
        shape: str,
        tip_angle: float | None = None,
        flutes: int | None = None,
    ) -> dict[str, Any]:
        rpm, feed = speeds[cut]
        section = {
            "tool": key,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": feed,
        }
        if tip_angle is not None:
            section["tip_angle"] = tip_angle
        if flutes is not None:
            section["flutes"] = flutes
        return section

    holes_stock = ((0.0, hi), (-width, 0.0), (0.0, t_max))
    plate_stock = ((0.0, plate_l), (-plate_w, 0.0), (-plate_t, 0.0))
    outline_stock = ((0.0, plate_l), (-plate_w, 0.0), (-plate_t, t_max))
    jobs = [
        {
            **tool(
                "spot",
                "holes spot",
                dia=CENTRE_DRILL["body_mm"],
                shape="drill",
                tip_angle=CENTRE_DRILL["point_deg"],
            ),
            "frame": "holes",
            "label": "holes spot",
            "stock": holes_stock,
            "ops": [
                [
                    "holes_spot",
                    "spot the pivot and the pin bore",
                    [
                        line
                        for xy in holes
                        for line in _plunge(xy, t_max, t_max - spot_depth, clear_holes)
                    ],
                ]
            ],
        },
        {
            **tool(
                "drill-14",
                "pivot drill",
                dia=d14,
                shape="drill",
                tip_angle=DRILL_POINT_DEG,
            ),
            "frame": "holes",
            "label": "pivot drill",
            "stock": holes_stock,
            "ops": [
                [
                    "pivot_drill",
                    "drill the pivot #14 through",
                    _pecked(xy_pivot, t_max, tip_14, pecks["pivot drill"], clear_holes),
                ]
            ],
        },
        {
            **tool(
                "drill-32",
                "pin drill",
                dia=d32,
                shape="drill",
                tip_angle=DRILL_POINT_DEG,
            ),
            "frame": "holes",
            "label": "pin drill",
            "stock": holes_stock,
            "ops": [
                [
                    "pin_drill",
                    "drill the pin bore #32 through",
                    _pecked(xy_pin, t_max, tip_32, pecks["pin drill"], clear_holes),
                ]
            ],
        },
        {
            **tool("em-half", "spot face", dia=em2, shape="endmill", flutes=3),
            "frame": "holes",
            "label": "spot face",
            "stock": holes_stock,
            "ops": [
                [
                    "spot_face",
                    "plunge the pivot's rear spot face",
                    _plunge(xy_pivot, t_max, floor, clear_holes),
                ]
            ],
        },
        {
            **tool(
                "drill-9",
                "pivot drill 9",
                dia=d9,
                shape="drill",
                tip_angle=DRILL_POINT_DEG,
            ),
            "frame": "holes",
            "label": "pivot drill 9",
            "stock": holes_stock,
            "ops": [
                [
                    "pivot_drill_9",
                    "drill the pivot #9 through to size",
                    _plunge(xy_pivot, t_max, tip_9, clear_holes),
                ]
            ],
        },
        {
            **tool("reamer-1260", "pin ream", dia=r126, shape="reamer"),
            "frame": "holes",
            "label": "pin ream",
            "stock": holes_stock,
            "ops": [
                [
                    "pin_ream",
                    "ream the pin bore .1260 through",
                    _plunge(xy_pin, t_max, ream_tip, clear_holes),
                ]
            ],
        },
        {
            # The chamfer bit's shape carries its own angle (no TipAngle).
            **tool("chamfer", "pin mouth", dia=chamfer_dia, shape="chamfer", flutes=2),
            "frame": "holes",
            "label": "pin mouth",
            "stock": holes_stock,
            "ops": [
                [
                    "pin_mouth",
                    "break the pin bore's rear mouth",
                    _plunge(xy_pin, t_max, chamfer_tip, clear_holes),
                ]
            ],
        },
        {
            **tool(
                "spot",
                "plate spot",
                dia=CENTRE_DRILL["body_mm"],
                shape="drill",
                tip_angle=CENTRE_DRILL["point_deg"],
            ),
            "frame": "plate",
            "label": "plate spot",
            "stock": plate_stock,
            "ops": [
                [
                    "plate_spot",
                    "spot the plate's two screw holes",
                    [
                        line
                        for xy in plate_holes
                        for line in _plunge(
                            xy, 0.0, -spot_depth, plate_jaw_top + CLEAR_MM
                        )
                    ],
                ]
            ],
        },
        {
            **tool(
                "drill-21",
                "plate drill 10",
                dia=d21,
                shape="drill",
                tip_angle=DRILL_POINT_DEG,
            ),
            "frame": "plate",
            "label": "plate drill 10",
            "stock": plate_stock,
            "ops": [
                [
                    "plate_drill_10",
                    "drill the #10-32 tap hole through",
                    _pecked(
                        plate_pivot,
                        0.0,
                        plate_tip_21,
                        pecks["plate drill 10"],
                        plate_jaw_top + CLEAR_MM,
                    ),
                ]
            ],
        },
        {
            **tool(
                "drill-43",
                "plate drill 4",
                dia=d43,
                shape="drill",
                tip_angle=DRILL_POINT_DEG,
            ),
            "frame": "plate",
            "label": "plate drill 4",
            "stock": plate_stock,
            "ops": [
                [
                    "plate_drill_4",
                    "drill the #4-40 tap hole through",
                    _pecked(
                        plate_pin,
                        0.0,
                        plate_tip_43,
                        pecks["plate drill 4"],
                        plate_jaw_top + CLEAR_MM,
                    ),
                ]
            ],
        },
        {
            "tool": "em-quarter",
            "dia": em4,
            "shape": "endmill",
            "flutes": out_flutes,
            "rpm": out_rpm,
            "feed": out_feed,
            "plunge": plunge,
            "frame": "plate",
            "label": "outline",
            "stock": outline_stock,
            "ops": [["outline", "cut the arm's outline through", outline_lines]],
        },
    ]
    manual = {
        "tap_pivot": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: #10-32 TAP THROUGH THE PLATE AT THE PIVOT",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{plate_pivot[0]:.3f} Y{plate_pivot[1]:.3f}",
                "(#10-32 TAP IN THE PIVOT HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND THROUGH THE PLATE. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": plate_pivot,
        },
        "tap_pin": {
            "tool": numbers["tap-guide"],
            "label": names["tap-guide"],
            "setting": "SPINDLE STAYS OFF. NEXT: #4-40 TAP THROUGH THE PLATE AT THE PIN",
            "gcode": [
                f"G53 G0 Z{MACHINE_Z_TOP_MM:.3f}",
                f"G0 X{plate_pin[0]:.3f} Y{plate_pin[1]:.3f}",
                "(#4-40 TAP IN THE PIN HOLE. JOG Z DOWN TO PUSH THE GUIDE POINT HOME IN THE WRENCH."
                " TAP BY HAND THROUGH THE PLATE. JOG Z UP CLEAR)",
                "M30",
            ],
            "at": plate_pin,
        },
    }

    # Keep-outs: the jaws (across the jaw width centred on the work) and the
    # parallels under the edges, each below its top.
    jaw_w = p["vise_jaw_width_mm"]
    par_t = p["parallel_thickness_mm"]

    def vise(
        x_mid: float, y_low: float, y_high: float, z_top: float, par_top: float | None
    ) -> list[dict[str, Any]]:
        span = (x_mid - jaw_w / 2, x_mid + jaw_w / 2)
        shapes = [
            _box("moving jaw", span, (y_low - JAW_DEPTH_MM, y_low), z_top),
            _box("fixed jaw", span, (y_high, y_high + JAW_DEPTH_MM), z_top),
        ]
        if par_top is not None:
            shapes += [
                _box("moving-jaw parallel", span, (y_low, y_low + par_t), par_top),
                _box("fixed-jaw parallel", span, (y_high - par_t, y_high), par_top),
            ]
        return shapes

    keep_holes = vise(hi / 2, -width, 0.0, jaw_top, 0.0)
    keep_plate = vise(plate_l / 2, -plate_w, 0.0, plate_jaw_top, -plate_t)
    tn = numbers

    def hole_checks(
        z_top: float,
        centres: list[list[float]],
        bottom: float,
        radius: float,
        keep: list[dict[str, Any]],
        *,
        ream: bool = False,
    ) -> list[list[Any]]:
        checks = [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": z_top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": z_top}],
            ["air_feed", {"z_top": z_top}],
            ["keep_out", {"radius": radius, "boxes": keep}],
        ]
        if ream:
            checks.append(["feed_out", {"z_top": z_top}])
        return checks

    expect: list[list[Any]] = []
    name = "AR01_holes"
    order = [
        "spot",
        "drill-14",
        "drill-32",
        "em-half",
        "drill-9",
        "reamer-1260",
        "chamfer",
    ]
    cuts = [
        "holes spot",
        "pivot drill",
        "pin drill",
        "spot face",
        "pivot drill 9",
        "pin ream",
        "pin mouth",
    ]
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": jaw_top, "tools": [tn[k] for k in order], "loads_first": True},
        ],
        [name, "spindle", {"rpm": [[speeds[c][0]] for c in cuts]}],
        [name, "pauses", {"z_top": jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(min(tip_14, tip_9, tip_32))}],
    ]
    sections = (
        hole_checks(
            t_max, holes, t_max - spot_depth, CENTRE_DRILL["body_mm"] / 2, keep_holes
        ),
        hole_checks(t_max, [xy_pivot], tip_14, d14 / 2, keep_holes),
        hole_checks(t_max, [xy_pin], tip_32, d32 / 2, keep_holes),
        hole_checks(t_max, [xy_pivot], floor, em2 / 2, keep_holes, ream=True),
        hole_checks(t_max, [xy_pivot], tip_9, d9 / 2, keep_holes, ream=True),
        hole_checks(t_max, [xy_pin], ream_tip, r126 / 2, keep_holes, ream=True),
        hole_checks(
            t_max, [xy_pin], chamfer_tip, chamfer_dia / 2, keep_holes, ream=True
        ),
    )
    for k, checks in enumerate(sections):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "AR02_plate"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": plate_jaw_top,
                "tools": [tn["spot"], tn["drill-21"], tn["drill-43"]],
                "loads_first": True,
            },
        ],
        [
            name,
            "spindle",
            {
                "rpm": [
                    [speeds[c][0]]
                    for c in ("plate spot", "plate drill 10", "plate drill 4")
                ]
            },
        ],
        [name, "pauses", {"z_top": plate_jaw_top, "count": 0}],
        [name, "depth", {"z_min": _r(min(plate_tip_21, plate_tip_43))}],
    ]
    for k, checks in enumerate(
        (
            hole_checks(
                0.0, plate_holes, -spot_depth, CENTRE_DRILL["body_mm"] / 2, keep_plate
            ),
            hole_checks(0.0, [plate_pivot], plate_tip_21, d21 / 2, keep_plate),
            hole_checks(0.0, [plate_pin], plate_tip_43, d43 / 2, keep_plate),
        )
    ):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    for name, key in (("AR03_tap_pivot", "tap_pivot"), ("AR04_tap_pin", "tap_pin")):
        expect += [
            [
                name,
                "tap_stop",
                {
                    "tool": tn["tap-guide"],
                    "at": manual[key]["at"],
                    "machine_top": MACHINE_Z_TOP_MM,
                },
            ],
            [name, "air_feed", {"z_top": 0.0}],
        ]

    name = "AR05_outline"
    expect += [
        [
            name,
            "tool_changes",
            {
                "z_top": clear_outline - CLEAR_MM,
                "tools": [tn["em-quarter"]],
                "loads_first": True,
            },
        ],
        [name, "spindle", {"rpm": [[out_rpm]]}],
        [name, "pauses", {"z_top": clear_outline - CLEAR_MM, "count": 0}],
        [name, "depth", {"z_min": bottom}],
        [
            name,
            "outline",
            {
                "elements": _outline_elements(g, origin),
                "passes": [
                    {"offset": rough_offset, "levels": rough_levels},
                    {"offset": finish_offset, "levels": [bottom]},
                ],
                "z_top": t_max,
            },
        ],
        [name, "rapids_clear", {"z_top": t_max}],
        [name, "air_feed", {"z_top": t_max}],
        [name, "keep_out", {"radius": em4 / 2, "boxes": keep_plate, "circles": heads}],
    ]

    return {
        "stem": STEM,
        "step": step_path,
        "comment": COMMENT,
        "frames": frames,
        "names": names,
        "numbers": numbers,
        "jobs": jobs,
        "manual": manual,
        "expect": expect,
    }


def expectations(ctx: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """(program, ``_gcode.check_<name>``, kwargs) for every posted file."""
    return [(program, check, kwargs) for program, check, kwargs in ctx["expect"]]


def build(ctx: dict[str, Any], rt: Any) -> dict[str, Any]:
    """Runs inside freecadcmd with ``rt`` = ``_freecad_cam_runtime``. One Job per
    section; returns {"ops": {operation key: operation or manual section}}."""
    doc = rt.document()
    models = {
        key: rt.import_step(
            doc, f"Transgear arm {key}", ctx["step"], frame["origin"], frame["axes"]
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

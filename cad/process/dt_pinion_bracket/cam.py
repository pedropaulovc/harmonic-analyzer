"""FreeCAD CAM recipe for MHA-DT-14, the pinion bracket strap.

``cam_nc.py`` loads this module on the host, calls :func:`context` with the
part's exported ``features.toml`` and the plan/shop TOML, then runs
:func:`build` inside headless FreeCAD (``freecadcmd``) with that context and
checks the posted G-code against :func:`expectations`. The strap's sizes come
from the feature export (its thickness, flanks, round ends, both bores,
the follower seat); the blank, the parts' places in it,
the levels, spots, drill and reamer depths and the holding from ``plan.toml``
``[parameters]`` and ``milling_cuts``; cutter diameters and end-mill speeds
from the shop (``shop/``), the drills' and reamers' speeds from the plan's
operations. Every path is written here (``rt.custom``): straight lines and
arcs a recipe can state exactly. Typed here, because neither record carries
them: the trade-size 1 centre drill's catalogue geometry (it sets the spot
depth), the twist drills' 118° point, the approach, safe and clearance
heights, the face overhang, the vise jaws' depth and the parallels' length
(keep-out shapes only) and the share of a printed band the posted outline
may use.

Route (plan text in ``plan.toml``): two straps from one sawn blank of 3/8 x
1-1/4 in 1018 flat, end to end along it, face A (the bar's cold-finished
face) down.

- PB02 (the blank lying on stacked parallels, gripped on the bar's edges):
  face B to the thickness, spot all four bores, drill the pivot bores C and
  ream them .2510 (fed in and out), drill the arbor bores 5/16 to size
  (owner ruling 2026-11-24, fit audit question 12), then cut
  each outline with the 1/8 in end mill through into the gap between the
  parallels, anticlockwise from one side of a bridge at the arbor end's apex
  round to its other side: the bridge alone holds each strap in the blank
  until the saw cuts across it (Setup 3).
- PB04 (one strap on edge on stacked parallels, A against the fixed jaw, the
  far flank down, the seat flank up): spot the follower seat, drill it #26
  short of its floor, then the 1/8 in end mill plunges to the floor and
  interpolates the seat: one turn that flattens the floor, one that finishes
  the wall to the middle of its .157 +.003/.000 band (owner ruling
  2026-11-23, tool audit Q8: "finish with the 1/8 end mill"). The
  cross hole is not drilled here: it is match-drilled 1/16 through the strap
  and the MHA-DT-19 shaft together at assembly (owner ruling 2026-11-21,
  MHA-DT-00 STEP 16, SHAFT DRILL SET).

Work frames (G54), each set in its setup:
- PB02: X0 the blank's LEFT end, Y0 the fixed jaw's face (the bar's edge,
  the blank at -Y), Z0 the stacks' top (face A). The straps' pivot bores at
  ``first_pivot_mm`` and one ``part_pitch_mm`` on, on the blank's centre line.
- PB04: X0 the pivot bore's axis (the pivot end's apex found with the edge
  finder, plus the end's radius), Y0 the fixed jaw's face (face A), Z0 the
  seat flank (the top).

Toolpath rules (owner rulings 2026-11-16): faces zigzag (ball screws),
plunges beside the stock at the cutting feed, plunges into metal (the outline
levels and the seat floor) at the plan's plunge feed, real G0 above the
stock. The outline runs anticlockwise round the strap: conventional with a
clockwise spindle; the seat's turns run clockwise inside it, conventional too.
Reamers feed in and out (a rapid retract can score the bore).
"""

from __future__ import annotations

import math
import re
from typing import Any

STEM = "dt_pinion_bracket"
COMMENT = "MHA-DT-14 pinion bracket strap"
# Programs in order, each listing its operation keys. A program whose keys
# are grouped in tuples is one section per group (a FreeCAD Job), joined at
# M6 tool changes.
PROGRAMS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    (
        "PB02_flat",
        (
            ("face_b",),
            ("bore_spot",),
            ("pivot_drill",),
            ("arbor_drill",),
            ("pivot_ream",),
            ("outline",),
        ),
    ),
    (
        "PB04_edge",
        (
            ("edge_spot",),
            ("seat_drill",),
            ("seat_mill",),
        ),
    ),
)
# Every program loads its own first tool (M6, the tool setter): each setup
# starts on whatever the mill last held.
LOAD_FIRST_TOOL = tuple(name for name, _ops in PROGRAMS)
# The plan's tools the mill runs, numbered by their places in the plan's tool
# list among these (the saw, the files and the gauges are not).
CAM_TOOLS = (
    "em-half",
    "spot",
    "drill-c",
    "drill-5-16",
    "reamer-2510",
    "em-eighth",
    "drill-26",
)
IN = 25.4
# ANSI trade size 1 combined drill and countersink, 60° included (3/64 pilot,
# 1/8 body): the shop record names the set, not the geometry.
CENTRE_DRILL = {
    "body_mm": 1 / 8 * IN,
    "pilot_mm": 3 / 64 * IN,
    "pilot_length_mm": 3 / 64 * IN,
    "point_deg": 60.0,
}
# Jobber drills' point (the shop records give the diameter only).
DRILL_POINT_DEG = 118.0
# Face passes start and finish with the cutter this far clear of the part's
# ends, so every plunge and stepover link is in the air beside it.
APPROACH_MM = 2.54
# Faces reach at least this far past the faces the jaws grip.
FACE_OVERHANG_MM = 0.5
# Plunges and drill R planes start this far above the stock top: real G0
# brings the tool down to it.
SAFE_MM = 1.0
# Moves between cuts run this far above the stock top.
CLEAR_MM = 5.0
# Rapid re-entry into a pecked hole or an outline slot stops this far above
# the last depth cut there.
REENTRY_MM = 0.5
# Keep-outs: each vise jaw's depth outward from the gripped face; the
# parallels' length (4 in, shop-equipment fixtures.parallels-lms-6745).
JAW_DEPTH_MM = IN
PARALLEL_LENGTH_MM = 4 * IN
# The .200 in edge finder's tip radius (tools.edge-finder).
EDGE_FINDER_RADIUS_MM = 0.1 * IN
# A 0-1 in outside micrometer's anvil, .250 in across (Mitutoyo 103 series
# and Starrett T436 catalogue pages): PB02's thickness check puts it under
# the blank's overhang beyond the parallels.
MIC_ANVIL_MM = 0.25 * IN
# A plan number the recipe recomputes must agree to this (its rounding).
PLAN_TOL_MM = 0.01
# The posted outline's cutter centre may stray from its offset by this share
# of the end radius's printed band; the rest is the machine's.
BAND_FRACTION = 0.1


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
    """(rpm, mm/min) of the operation holding ``cut``: the shop setting it
    names (chip load × flutes × rpm), or, with no setting, the rpm and feed
    the cut itself authors."""
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


def _spot_depth(dia: float) -> float:
    """Depth below the surface at which the centre drill's 60° countersink
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


def _spot(xy: list[float], top: float, z: float, clear: float) -> list[str]:
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
    xy: list[float], top: float, tip: float, peck: float, clear: float
) -> list[str]:
    """Drill from ``top`` to ``tip`` in pecks of ``peck`` (one plunge when
    ``peck`` reaches the tip), each with a full retract to the R plane and a
    rapid back to just above the last peck. Moves to and from the hole run at
    ``clear``."""
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
            lines += [f"G0 Z{r_plane:.3f}", f"G0 Z{_r(previous + REENTRY_MM):.3f}"]
        lines.append(f"G1 Z{z:.3f} F{{feed}}")
        previous = z
    return lines + [f"G0 Z{r_plane:.3f}", f"G0 Z{clear:.3f}"]


def _reamed(xy: list[float], top: float, tip: float, clear: float) -> list[str]:
    """Feed the reamer in to ``tip`` and back out to the R plane, spindle
    running: no rapid leaves the bore."""
    clear, r_plane = _r(clear), _r(top + SAFE_MM)
    return [
        f"G0 Z{clear:.3f}",
        f"G0 X{xy[0]:.3f} Y{xy[1]:.3f}",
        f"G0 Z{r_plane:.3f}",
        f"G1 Z{_r(tip):.3f} F{{feed}}",
        f"G1 Z{r_plane:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _stations(y: tuple[float, float], radius: float, max_step: float) -> list[float]:
    """Zigzag pass stations across the face ``y`` (low, high), from its high
    side: each pass takes the same width, at most ``max_step``, and together
    the cutter reaches ``FACE_OVERHANG_MM`` past both edges."""
    span = y[1] - y[0] + FACE_OVERHANG_MM
    n = math.ceil(span / max_step - 1e-9)
    step = span / n
    if 2 * radius - step < FACE_OVERHANG_MM:
        raise ValueError(
            f"a {step:.3f} stepover leaves the first pass short of the edge"
        )
    first = y[1] + radius - step
    return [_r(first - k * step) for k in range(n)]


def _face(
    levels: list[float], top: float, x: tuple[float, float], ys: list[float]
) -> list[str]:
    """Zigzag faces at ``levels``: at each, one X pass per Y in ``ys``
    between the cutter-centre ends ``x``, alternating direction, starting at
    the low X end; every plunge, level change and stepover beside the part."""
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
            # Back to the low X side, beside the part, for the next level.
            lines.append(f"G1 X{x0:.3f} F{{feed}}")
        if z != levels[-1]:
            lines.append(f"G1 Y{ys[0]:.3f} F{{feed}}")
    return lines + [f"G0 Z{clear:.3f}"]


def _outline(
    pivot: tuple[float, float],
    length: float,
    radius: float,
    bridge: float,
    levels: list[float],
    top: float,
) -> list[str]:
    """One strap's outline at the cutter-centre ``radius`` round each end,
    anticlockwise: from the bridge's upper side at the arbor end (``bridge``
    radians above its apex) round the arbor end, along the seat flank, round
    the pivot end, along the far flank and round the arbor end to the
    bridge's lower side. Each level plunges at the start, the first from
    above the stock, each later one by a rapid down the slot to just above
    the level before."""
    px, py = pivot
    ax = px + length
    clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    rr = _r(radius)
    c, s = radius * math.cos(bridge), radius * math.sin(bridge)
    start = (_r(ax + c), _r(py + s))
    finish = (_r(ax + c), _r(py - s))
    lines: list[str] = []
    previous = None
    for z in levels:
        lines += [f"G0 Z{clear:.3f}", f"G0 X{start[0]:.3f} Y{start[1]:.3f}"]
        lines.append(
            f"G0 Z{safe:.3f}"
            if previous is None
            else f"G0 Z{_r(previous + REENTRY_MM):.3f}"
        )
        lines += [
            f"G1 Z{_r(z):.3f} F{{plunge}}",
            f"G3 X{_r(ax):.3f} Y{_r(py + radius):.3f} I{_r(-c):.3f} J{_r(-s):.3f} F{{feed}}",
            f"G1 X{_r(px):.3f} F{{feed}}",
            f"G3 X{_r(px - radius):.3f} Y{_r(py):.3f} I0.000 J{-rr:.3f} F{{feed}}",
            f"G3 X{_r(px):.3f} Y{_r(py - radius):.3f} I{rr:.3f} J0.000 F{{feed}}",
            f"G1 X{_r(ax):.3f} F{{feed}}",
            f"G3 X{finish[0]:.3f} Y{finish[1]:.3f} I0.000 J{rr:.3f} F{{feed}}",
            f"G0 Z{clear:.3f}",
        ]
        previous = z
    return lines


def _seat(
    xy: list[float], top: float, floor: float, offsets: tuple[float, ...]
) -> list[str]:
    """The seat: plunge the end mill at the seat's centre to the floor, then
    one clockwise turn at each of ``offsets`` off the centre (two halves
    each, stepping out between them on the floor), back to the centre and
    out."""
    x, y = xy
    clear, safe = _r(top + CLEAR_MM), _r(top + SAFE_MM)
    lines = [
        f"G0 Z{clear:.3f}",
        f"G0 X{_r(x):.3f} Y{_r(y):.3f}",
        f"G0 Z{safe:.3f}",
        f"G1 Z{_r(floor):.3f} F{{plunge}}",
    ]
    for offset in offsets:
        e = _r(offset)
        lines += [
            f"G1 X{_r(x + offset):.3f} F{{feed}}",
            f"G2 X{_r(x - offset):.3f} Y{_r(y):.3f} I{-e:.3f} J0.000 F{{feed}}",
            f"G2 X{_r(x + offset):.3f} Y{_r(y):.3f} I{e:.3f} J0.000 F{{feed}}",
        ]
    return lines + [
        f"G1 X{_r(x):.3f} F{{feed}}",
        f"G1 Z{safe:.3f} F{{feed}}",
        f"G0 Z{clear:.3f}",
    ]


def _geometry(features: dict[str, Any]) -> dict[str, Any]:
    """The strap's sizes and holes from the export, each checked against the
    frame the recipe assumes: face A at model Z0 and face B above it, the
    flanks square to X either side of the bores' line, the pivot bore through
    the origin and the arbor bore along +Y, both through along Z; the round
    ends about the bores; the seat entering the seat flank along +X at its
    station from face A."""
    f = features["features"]
    if f["broad_face_a"]["plane"] != {"frame": "model", "axis": "z", "value": 0.0}:
        raise ValueError("broad_face_a: expected at model Z0")
    b = f["broad_face_b"]
    thickness = b["plane"]["value"]
    if not math.isclose(thickness, b["thickness_nominal"], abs_tol=1e-3):
        raise ValueError(f"face B at Z {thickness:.4f} is not the thickness")
    seat_x, far_x = f["seat_flank"]["plane"]["value"], f["far_flank"]["plane"]["value"]
    if f["seat_flank"]["plane"]["axis"] != "x" or not seat_x < 0 < far_x:
        raise ValueError("the flanks: expected square to X either side of the bores")
    pivot, arbor = f["pivot_bore"], f["arbor_bore"]
    for name, hole in (("pivot_bore", pivot), ("arbor_bore", arbor)):
        if hole["axis"] != [0.0, 0.0, 1.0] or not hole.get("thru"):
            raise ValueError(f"{name}: expected through along +Z from face A")
    if pivot["at"] != [0.0, 0.0, 0.0]:
        raise ValueError("pivot_bore: expected at the model origin")
    centre = arbor["at"][1]
    if arbor["at"] != [0.0, centre, 0.0] or not math.isclose(
        centre, arbor["center_distance_nominal"], abs_tol=1e-3
    ):
        raise ValueError("arbor_bore: expected along +Y at its centre distance")
    radius = None
    for name, end, at in (
        ("pivot_end", f["pivot_end"], 0.0),
        ("arbor_end", f["arbor_end"], centre),
    ):
        if end["center"] != [0.0, at, 0.0] or end["axis"] != [0.0, 0.0, 1.0]:
            raise ValueError(f"{name}: expected about its bore")
        r = end["radius_nominal"]
        if radius is not None and not math.isclose(r, radius, abs_tol=1e-6):
            raise ValueError("the round ends: expected one radius")
        radius = r
        band = end["radius"]
    assert radius is not None
    if not (
        math.isclose(-seat_x, radius, abs_tol=1e-3)
        and math.isclose(far_x, radius, abs_tol=1e-3)
    ):
        raise ValueError("the flanks: expected tangent to the round ends")
    seat = f["follower_seat"]
    if seat["axis"] != [1.0, 0.0, 0.0] or not math.isclose(
        seat["at"][0], seat_x, abs_tol=1e-3
    ):
        raise ValueError("follower_seat: expected into the seat flank along +X")
    if not math.isclose(seat["at"][2], seat["station_nominal"], abs_tol=1e-3):
        raise ValueError("follower_seat: its Z is not its station from face A")
    if not seat.get("flat_bottom") or "depth_nominal" not in seat:
        raise ValueError("follower_seat: expected a flat-bottomed blind seat")
    if not math.isclose(seat["at"][1], seat["height_nominal"], abs_tol=1e-3):
        raise ValueError("follower_seat: its Y is not its height from the pivot bore")
    return {
        "thickness": thickness,
        "width": far_x - seat_x,
        "seat_x": seat_x,
        "far_x": far_x,
        "radius": radius,
        "radius_band": band,
        "centre": centre,
        "pivot_band": pivot["dia"],
        "arbor_band": arbor["dia"],
        "seat": seat,
    }


def context(
    features: dict[str, Any], plan: dict[str, Any], shop: dict[str, Any], step_path: str
) -> dict[str, Any]:
    g = _geometry(features)
    p = plan["parameters"]
    T, W, R, C = g["thickness"], g["width"], g["radius"], g["centre"]

    # The blank: the bar's width and thickness, sawn to length.
    bar_w, bar_t = p["blank_x_in"] * IN, p["blank_z_in"] * IN
    blank_min, blank_max = p["blank_length_min_in"] * IN, p["blank_length_max_in"] * IN
    _agree(plan, "blank_length_max_mm", blank_max)
    if bar_t <= T:
        raise ValueError("the bar is not thicker than the strap: nothing to face")
    if bar_w <= W:
        raise ValueError("the bar is not wider than the strap")

    def tool_dia(tool: str) -> float:
        return _shop_tool(plan, shop, tool)["diameter_mm"]

    em, e8 = tool_dia("em-half"), tool_dia("em-eighth")
    r, r8 = em / 2, e8 / 2
    t = p["parallel_thickness_mm"]

    # Both straps along the blank's centre line, end to end; the saw cuts
    # across each bridge on a line saw_offset_mm past the arbor end's apex,
    # its kerf on the line's far side from the strap (the plan's saw cut, Setup 3).
    first, pitch = p["first_pivot_mm"], p["part_pitch_mm"]
    pivot_xs = (first, first + pitch)
    for k, x in enumerate(pivot_xs, 1):
        _agree(plan, f"pivot_{k}_x_mm", x)
        _agree(plan, f"arbor_{k}_x_mm", x + C)
    end_web = p["end_web_min_mm"]
    if first - R - e8 < end_web - 1e-6:
        raise ValueError(
            "the first strap's slot leaves the blank's left end under its web"
        )
    if not 0 < p["saw_offset_mm"] < e8:
        raise ValueError("the saw line is not across the slot at the bridge")
    kerf_far = first + C + R + p["saw_offset_mm"] + p["saw_kerf_mm"]
    if pivot_xs[1] - R - e8 < kerf_far + p["saw_clear_min_mm"] - 1e-6:
        raise ValueError(
            "the first bridge's saw cut comes too near the second strap's slot"
        )
    last = pivot_xs[1] + C + R + p["saw_offset_mm"] + p["saw_kerf_mm"]
    if blank_min - last < end_web - 1e-6:
        raise ValueError(
            "the second bridge's saw cut leaves the shortest blank's right end under its web"
        )
    # The slot beside each flank clears the parallel under that bar edge.
    side = (bar_w - W) / 2 - e8 - t
    if side < p["parallel_clear_min_mm"] - 1e-6:
        raise ValueError(
            f"the outline slot comes {side:.3f} from a parallel's inner edge"
        )
    # PB02's Z0 (face A on the stacks): the 1/2 in end mill touches face B,
    # as bought, wholly on the blank between its left end and the first
    # pivot bore (before anything is cut there), Z set to the
    # micrometer's reading there (Op 20); no stack is exposed beside the
    # blank. Its thickness check after facing puts the micrometer's anvil
    # under the blank's overhang beyond the parallels at each end: the
    # holding text centres the stacks along the jaws and the blank over
    # them, ends checked equal with the rule, so each overhang is half the
    # shortest blank less the parallels' length.
    _agree(plan, "z_touch_y_mm", -bar_w / 2)
    if not r <= p["z_touch_x_mm"] <= first:
        raise ValueError("the Z touch-off is not wholly on the blank's left end")
    _agree(plan, "overhang_min_mm", (blank_min - PARALLEL_LENGTH_MM) / 2)
    if (blank_min - PARALLEL_LENGTH_MM) / 2 < MIC_ANVIL_MM - 1e-9:
        raise ValueError(
            "the blank overhangs the parallels less than the micrometer's anvil"
        )

    # PB02: face B to the thickness in one level.
    face_rpm, face_feed = _setting(plan, shop, "face b")
    step_max = p["face_stepover_max_mm"]
    if not math.isclose(_cut(plan, "face b", "cutter_dia_mm"), em, abs_tol=1e-6):
        raise ValueError("'face b' cutter is not the 1/2 in end mill")
    if not math.isclose(_cut(plan, "face b", "radial_woc_mm"), step_max, abs_tol=1e-6):
        raise ValueError("'face b' radial_woc_mm is not process.face_stepover_max_mm")
    _agree(plan, "face_b_skim_mm", bar_t - T)
    if not math.isclose(
        _cut(plan, "face b", "axial_doc_mm"), p["face_b_skim_mm"], abs_tol=1e-6
    ):
        raise ValueError("'face b' axial_doc_mm is not process.face_b_skim_mm")

    # Holes from the trade-size 1 centre drill's spots, under each drill.
    spot_rpm, spot_feed = _setting(plan, shop, "bore spot")
    if _setting(plan, shop, "edge spot") != (spot_rpm, spot_feed):
        raise ValueError("'edge spot' runs at another speed than 'bore spot'")
    bore_spot, edge_spot = p["bore_spot_dia_mm"], p["edge_spot_dia_mm"]
    for cut, dia in (("bore spot", bore_spot), ("edge spot", edge_spot)):
        if not math.isclose(_cut(plan, cut, "cutter_dia_mm"), dia, abs_tol=1e-6):
            raise ValueError(f"'{cut}' cutter_dia_mm is not its spot Ø")
    drills = {
        "pivot": ("drill-c", "pivot drill", "pivot_drill_tip_mm"),
        "arbor": ("drill-5-16", "arbor drill", "arbor_drill_tip_mm"),
    }
    drill = {}
    for key, (tool, cut, tip_key) in drills.items():
        dia = tool_dia(tool)
        if bore_spot >= dia:
            raise ValueError(
                f"the bore spot is not under the {tool}: it would chamfer the bore"
            )
        tip = -(p["drill_past_mm"] + _point(dia))
        _agree(plan, tip_key, tip)
        rpm, feed = _setting(plan, shop, cut)
        drill[key] = {"tool": tool, "dia": dia, "tip": tip, "rpm": rpm, "feed": feed}
    # The arbor bores are drilled to size: the 5/16 drill is the bore.
    arbor_band = g["arbor_band"]
    if not arbor_band[0] <= drill["arbor"]["dia"] <= arbor_band[1]:
        raise ValueError(f"the 5/16 drill is outside the arbor bore's band {arbor_band}")
    # The pivot bores: the .2510 reamer after the C drill.
    reamer_dia = tool_dia("reamer-2510")
    pivot_band = g["pivot_band"]
    if not pivot_band[0] <= reamer_dia <= pivot_band[1]:
        raise ValueError(f"reamer-2510 Ø{reamer_dia} is outside the pivot bore's band")
    if not 0 < reamer_dia - drill["pivot"]["dia"] <= p["ream_stock_max_mm"]:
        raise ValueError("the pivot drill leaves the reamer-2510 no stock or too much")
    ream_rpm, ream_feed = _setting(plan, shop, "pivot ream")
    ream = {"tool": "reamer-2510", "dia": reamer_dia, "rpm": ream_rpm, "feed": ream_feed}
    ream_tip = -p["ream_past_mm"]

    # The outline: the 1/8 in end mill in equal levels into the gap, round
    # all but the bridge at each arbor end.
    out_rpm, out_feed = _setting(plan, shop, "outline")
    seat_mill_rpm, seat_mill_feed = _setting(plan, shop, "seat")
    if (seat_mill_rpm, seat_mill_feed) != (out_rpm, out_feed):
        raise ValueError("'seat' runs at another setting than 'outline'")
    plunge = p["eighth_plunge_feed_per_min_mm"]
    if not 0 < plunge <= out_feed:
        raise ValueError("the 1/8 in end mill's plunge feed is not under its feed")
    for name in ("outline", "seat"):
        if not math.isclose(_cut(plan, name, "cutter_dia_mm"), e8, abs_tol=1e-6):
            raise ValueError(f"'{name}' cutter is not the 1/8 in end mill")
    if not math.isclose(
        _cut(plan, "outline", "axial_doc_mm"), p["outline_step_max_mm"], abs_tol=1e-6
    ):
        raise ValueError("'outline' axial_doc_mm is not process.outline_step_max_mm")
    out_levels = _levels(T, -p["outline_past_mm"], p["outline_step_max_mm"])
    out_radius = R + r8
    half_bridge = p["bridge_width_mm"] / 2
    bridge = math.asin((half_bridge + r8) / out_radius)

    # Vise: lying and on edge, both on the stacked parallels.
    grip = p["vise_jaw_height_mm"] - p["riser_height_mm"]
    _agree(plan, "grip_mm", grip)
    if not grip < T:
        raise ValueError("the blank's top does not stand above the jaws")
    if not grip < W / 2:
        raise ValueError("on edge, the jaws reach the round ends' apex height")
    # PB02's edge-finder tip below the jaw tops (it must touch the fixed
    # jaw's face beside the blank) and on the blank's end.
    finder_z = p["blank_top_mm"] - p["finder_tip_depth_mm"]
    if not (0 < finder_z < grip):
        raise ValueError("the edge finder's tip is not below the jaw tops on the blank")

    # PB04: Z0 the seat flank, the far flank on the stacks at -W; X0 the
    # pivot bore's axis, the edge finder touching the pivot end's apex. The
    # operator adds the radius measured on each strap; the plan's worked
    # example is the drawing's printed radius, its band's middle.
    _agree(
        plan, "pivot_apex_x_mm", -(sum(g["radius_band"]) / 2 + EDGE_FINDER_RADIUS_MM)
    )
    seat = g["seat"]
    d26 = tool_dia("drill-26")
    # The spot's mouth under the #26, so the drill takes it out.
    if not edge_spot < d26:
        raise ValueError("the edge spot is over the #26")
    floor = -seat["depth_nominal"]
    _agree(plan, "seat_floor_z_mm", floor)
    seat_drill_tip = floor + p["seat_drill_floor_gap_mm"]
    # The 1/8 in end mill plunges to the floor and interpolates the seat:
    # a plunged 1/8 cutter cuts .125, not the .157 +.003/.000 band (owner
    # ruling 2026-11-23, tool audit Q8). Its first turn takes out the #26's
    # wall and point cone and flattens the floor; its second finishes the
    # wall at the band's middle, so the mill's circle may stray half the band
    # either way. Both turns run on the floor, so the floor's corner is the
    # square end mill's own, inside the drawing's R max corner.
    floor_dia = p["seat_floor_dia_mm"]
    finish_dia = p["seat_finish_dia_mm"]
    _agree(plan, "seat_finish_dia_mm", sum(seat["dia"]) / 2)
    if not e8 < floor_dia < finish_dia:
        raise ValueError(
            "the seat floor's turn is not between the end mill and the seat's finish"
        )
    if not d26 <= floor_dia:
        raise ValueError(
            "the seat floor's turn is under the #26: it leaves the drill's wall"
        )
    if not finish_dia - floor_dia <= e8 / 2:
        raise ValueError("the seat's finish turn takes more than a quarter of the cutter")
    seat_rpm, seat_feed = _setting(plan, shop, "seat drill")

    names = {tool["id"]: tool["name"] for tool in plan["tools"]}
    numbers = {
        tool["id"]: n
        for n, tool in enumerate((x for x in plan["tools"] if x["id"] in CAM_TOOLS), 1)
    }
    missing = sorted(set(CAM_TOOLS) - set(numbers))
    if missing:
        raise ValueError(f"plan tools lack {missing}")

    # Frames (model point p -> axes · (p - origin)). Lying: the strap's length
    # along +X, the seat flank toward the fixed jaw (+Y), face A down; each
    # strap's pivot bore at its station on the blank's centre line. On edge:
    # the length along +X from the pivot bore, face A at the fixed jaw, the
    # seat flank up.
    frames = {
        "flat_1": _frame([-bar_w / 2, -pivot_xs[0], 0.0], [-1, 0, 0], [0, 0, 1]),
        "flat_2": _frame([-bar_w / 2, -pivot_xs[1], 0.0], [-1, 0, 0], [0, 0, 1]),
        "edge": _frame([g["seat_x"], 0.0, 0.0], [0, 0, -1], [-1, 0, 0]),
    }
    pivots = []
    arbors = []
    for key in ("flat_1", "flat_2"):
        x, y, _z = _to(frames[key], [0.0, 0.0, 0.0])
        pivots.append([_r(x), _r(y)])
        x, y, _z = _to(frames[key], [0.0, C, 0.0])
        arbors.append([_r(x), _r(y)])
    edge = frames["edge"]
    seat_xy = [_r(v) for v in _to(edge, seat["at"])[:2]]

    stocks = {
        "flat": ((0.0, blank_max), (-bar_w, 0.0), (0.0, bar_t)),
        "flat_faced": ((0.0, blank_max), (-bar_w, 0.0), (0.0, T)),
        "edge": ((-R, C + R), (-T, 0.0), (-W, 0.0)),
    }

    def tool_spec(
        tool: str, dia: float, shape: str, rpm: float, feed: float, **kw: Any
    ) -> dict[str, Any]:
        return {
            "tool": tool,
            "dia": dia,
            "shape": shape,
            "rpm": rpm,
            "feed": feed,
            "plunge": kw.pop("plunge", feed),
            **kw,
        }

    em_tool = tool_spec("em-half", em, "endmill", face_rpm, face_feed, flutes=3)
    e8_tool = tool_spec(
        "em-eighth", e8, "endmill", out_rpm, out_feed, plunge=plunge, flutes=3
    )
    spot_tool = tool_spec(
        "spot",
        CENTRE_DRILL["body_mm"],
        "drill",
        spot_rpm,
        spot_feed,
        tip_angle=CENTRE_DRILL["point_deg"],
    )

    def drill_tool(tool: str, dia: float, rpm: float, feed: float) -> dict[str, Any]:
        return tool_spec(tool, dia, "drill", rpm, feed, tip_angle=DRILL_POINT_DEG)

    def reamer_tool(tool: str, dia: float, rpm: float, feed: float) -> dict[str, Any]:
        return tool_spec(tool, dia, "endmill", rpm, feed, flutes=6)

    # PB02 passes: the blank's whole length along X, its width across Y.
    flat_ys = _stations((-bar_w, 0.0), r, step_max)
    flat_x = (-r - APPROACH_MM, blank_max + r + APPROACH_MM)
    flat_clear = T + CLEAR_MM
    bores = pivots + arbors
    bore_spot_depth = _spot_depth(bore_spot)
    edge_spot_depth = _spot_depth(edge_spot)
    edge_holes = [seat_xy]

    jobs = [
        {
            **em_tool,
            "frame": "flat",
            "label": "face b",
            "stock": stocks["flat"],
            "ops": [
                [
                    "face_b",
                    "face B to the thickness",
                    _face([T], bar_t, flat_x, flat_ys),
                ]
            ],
        },
        {
            **spot_tool,
            "frame": "flat",
            "label": "bore spot",
            "stock": stocks["flat_faced"],
            "ops": [
                [
                    "bore_spot",
                    "spot the four bores",
                    [
                        line
                        for xy in bores
                        for line in _spot(xy, T, T - bore_spot_depth, flat_clear)
                    ],
                ]
            ],
        },
    ]
    for key, xys in (("pivot", pivots), ("arbor", arbors)):
        d = drill[key]
        jobs.append(
            {
                **drill_tool(d["tool"], d["dia"], d["rpm"], d["feed"]),
                "frame": "flat",
                "label": f"{key} drill",
                "stock": stocks["flat_faced"],
                "ops": [
                    [
                        f"{key}_drill",
                        f"drill both {key} bores through",
                        [
                            line
                            for xy in xys
                            for line in _pecked(xy, T, d["tip"], T + 10.0, flat_clear)
                        ],
                    ]
                ],
            }
        )
    jobs.append(
        {
            **reamer_tool(ream["tool"], ream["dia"], ream["rpm"], ream["feed"]),
            "frame": "flat",
            "label": "pivot ream",
            "stock": stocks["flat_faced"],
            "ops": [
                [
                    "pivot_ream",
                    "ream both pivot bores",
                    [
                        line
                        for xy in pivots
                        for line in _reamed(xy, T, ream_tip, flat_clear)
                    ],
                ]
            ],
        }
    )
    jobs.append(
        {
            **e8_tool,
            "frame": "flat",
            "label": "outline",
            "stock": stocks["flat_faced"],
            "ops": [
                [
                    "outline",
                    "cut both outlines to their bridges",
                    [
                        line
                        for xy in pivots
                        for line in _outline(
                            (xy[0], xy[1]), C, out_radius, bridge, out_levels, T
                        )
                    ],
                ]
            ],
        }
    )
    edge_clear = CLEAR_MM
    jobs += [
        {
            **spot_tool,
            "frame": "edge",
            "label": "edge spot",
            "stock": stocks["edge"],
            "ops": [
                [
                    "edge_spot",
                    "spot the seat",
                    [
                        line
                        for xy in edge_holes
                        for line in _spot(xy, 0.0, -edge_spot_depth, edge_clear)
                    ],
                ]
            ],
        },
        {
            **drill_tool("drill-26", d26, seat_rpm, seat_feed),
            "frame": "edge",
            "label": "seat drill",
            "stock": stocks["edge"],
            "ops": [
                [
                    "seat_drill",
                    "drill the seat #26 short of its floor",
                    _pecked(seat_xy, 0.0, seat_drill_tip, W, edge_clear),
                ]
            ],
        },
        {
            **e8_tool,
            "frame": "edge",
            "label": "seat",
            "stock": stocks["edge"],
            "ops": [
                [
                    "seat_mill",
                    "flatten the seat's floor and finish its wall",
                    _seat(
                        seat_xy,
                        0.0,
                        floor,
                        ((floor_dia - e8) / 2, (finish_dia - e8) / 2),
                    ),
                ]
            ],
        },
    ]

    # Keep-outs: the jaws beside the gripped span from the stacks' top to
    # the jaw top, across the jaw width; the parallels under the gripped
    # edges, 1/8 in thick against each jaw.
    jaw_w = p["vise_jaw_width_mm"]

    def jaws(x, y, base: float) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - jaw_w / 2, mid + jaw_w / 2)
        return [
            _box("moving jaw", span, (y[0] - JAW_DEPTH_MM, y[0]), base + grip),
            _box("fixed jaw", span, (y[1], y[1] + JAW_DEPTH_MM), base + grip),
        ]

    def parallels(x, y, base: float) -> list[dict[str, Any]]:
        mid = (x[0] + x[1]) / 2
        span = (mid - PARALLEL_LENGTH_MM / 2, mid + PARALLEL_LENGTH_MM / 2)
        return [
            _box("moving-jaw parallels", span, (y[0], y[0] + t), base),
            _box("fixed-jaw parallels", span, (y[1] - t, y[1]), base),
        ]

    flat_span = ((0.0, blank_min), (-bar_w, 0.0))
    edge_span = ((-R, C + R), (-T, 0.0))
    flat_keep = jaws(*flat_span, 0.0) + parallels(*flat_span, 0.0)
    edge_keep = jaws(*edge_span, -W) + parallels(*edge_span, -W)

    # The outline's elements: each strap's arbor end from the bridge, the
    # seat flank, the pivot end (two quarters), the far flank and the arbor
    # end to the bridge, anticlockwise.
    tol = BAND_FRACTION * (g["radius_band"][1] - g["radius_band"][0])
    cb, sb = R * math.cos(bridge), R * math.sin(bridge)
    elements = []
    for px, py in pivots:
        ax = px + C
        elements += [
            {
                "name": "arbor end",
                "start": [ax + cb, py + sb],
                "end": [ax, py + R],
                "centre": [ax, py],
                "tol": tol,
            },
            {
                "name": "seat flank",
                "start": [ax, py + R],
                "end": [px, py + R],
                "tol": tol,
            },
            {
                "name": "pivot end",
                "start": [px, py + R],
                "end": [px - R, py],
                "centre": [px, py],
                "tol": tol,
            },
            {
                "name": "pivot end",
                "start": [px - R, py],
                "end": [px, py - R],
                "centre": [px, py],
                "tol": tol,
            },
            {
                "name": "far flank",
                "start": [px, py - R],
                "end": [ax, py - R],
                "tol": tol,
            },
            {
                "name": "arbor end",
                "start": [ax, py - R],
                "end": [ax + cb, py - sb],
                "centre": [ax, py],
                "tol": tol,
            },
        ]
    starts = [
        [
            _r(px + C + out_radius * math.cos(bridge)),
            _r(py + out_radius * math.sin(bridge)),
        ]
        for px, py in pivots
    ]

    tn = numbers
    expect: list[list[Any]] = []

    def hole_checks(centres, bottom, top, radius, keep, feed_out=False):
        return [
            ["holes", {"centres": centres, "z_bottom": _r(bottom)}],
            ["rapids_clear", {"z_top": top, "open_holes": centres}],
            ["vertical_below_top", {"z_top": top}],
            ["air_feed", {"z_top": top}],
            ["keep_out", {"radius": radius, "boxes": keep}],
            *([["feed_out", {"z_top": top}]] if feed_out else []),
        ]

    name = "PB02_flat"
    flat_sections = [
        (
            [face_rpm],
            [
                ["depth", {"z_min": _r(T)}],
                ["rapids_clear", {"z_top": bar_t}],
                ["air_feed", {"z_top": bar_t}],
                [
                    "face_passes",
                    {
                        "z": _r(T),
                        "y": [-bar_w, 0.0],
                        "max_engagement": step_max,
                        "radius": r,
                        "span": blank_min,
                        "overhang": FACE_OVERHANG_MM,
                    },
                ],
                ["keep_out", {"radius": r, "boxes": flat_keep}],
            ],
        ),
        (
            [spot_rpm],
            hole_checks(
                bores, T - bore_spot_depth, T, CENTRE_DRILL["body_mm"] / 2, flat_keep
            ),
        ),
        (
            [drill["pivot"]["rpm"]],
            hole_checks(
                pivots, drill["pivot"]["tip"], T, drill["pivot"]["dia"] / 2, flat_keep
            ),
        ),
        (
            [drill["arbor"]["rpm"]],
            hole_checks(
                arbors, drill["arbor"]["tip"], T, drill["arbor"]["dia"] / 2, flat_keep
            ),
        ),
        (
            [ream["rpm"]],
            hole_checks(pivots, ream_tip, T, ream["dia"] / 2, flat_keep, True),
        ),
        (
            [out_rpm],
            [
                ["depth", {"z_min": _r(out_levels[-1])}],
                ["rapids_clear", {"z_top": T, "open_holes": starts}],
                ["air_feed", {"z_top": T}],
                [
                    "outline",
                    {
                        "elements": elements,
                        "z_top": T,
                        "passes": [
                            {"offset": r8, "levels": [_r(z) for z in out_levels]}
                        ],
                    },
                ],
                ["keep_out", {"radius": r8, "boxes": flat_keep}],
            ],
        ),
    ]
    flat_tools = [
        tn["em-half"],
        tn["spot"],
        tn["drill-c"],
        tn["drill-5-16"],
        tn["reamer-2510"],
        tn["em-eighth"],
    ]
    deepest = min(
        drill["arbor"]["tip"], drill["pivot"]["tip"], ream_tip, out_levels[-1]
    )
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": bar_t, "tools": flat_tools, "loads_first": True},
        ],
        [name, "spindle", {"rpm": [speeds for speeds, _c in flat_sections]}],
        [name, "pauses", {"z_top": bar_t, "count": 0}],
        [name, "depth", {"z_min": _r(deepest)}],
    ]
    for k, (_speeds, checks) in enumerate(flat_sections):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

    name = "PB04_edge"
    finish_offset = (finish_dia - e8) / 2
    sx, sy = seat_xy
    edge_sections = [
        (
            [spot_rpm],
            hole_checks(
                edge_holes,
                -edge_spot_depth,
                0.0,
                CENTRE_DRILL["body_mm"] / 2,
                edge_keep,
            ),
        ),
        ([seat_rpm], hole_checks([seat_xy], seat_drill_tip, 0.0, d26 / 2, edge_keep)),
        (
            [seat_mill_rpm],
            [
                [
                    "bounds",
                    {
                        "window": [[sx - 2.0, sx + 2.0], [sy - 2.0, sy + 2.0]],
                        "x": [_r(sx - finish_offset), _r(sx + finish_offset)],
                        "y": [_r(sy - finish_offset), _r(sy + finish_offset)],
                        "z_min": _r(floor),
                        "arc": "G2",
                        "entry": [sx, sy],
                        "z_top": 0.0,
                    },
                ],
                ["rapids_clear", {"z_top": 0.0}],
                ["air_feed", {"z_top": 0.0}],
                ["keep_out", {"radius": r8, "boxes": edge_keep}],
            ],
        ),
    ]
    edge_tools = [
        tn["spot"],
        tn["drill-26"],
        tn["em-eighth"],
    ]
    expect += [
        [
            name,
            "tool_changes",
            {"z_top": 0.0, "tools": edge_tools, "loads_first": True},
        ],
        [name, "spindle", {"rpm": [speeds for speeds, _c in edge_sections]}],
        [name, "pauses", {"z_top": 0.0, "count": 0}],
        # The deepest cut: the end mill on the seat's floor.
        [name, "depth", {"z_min": _r(floor)}],
    ]
    for k, (_speeds, checks) in enumerate(edge_sections):
        expect += [[f"{name}@{k}", check, kwargs] for check, kwargs in checks]

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
            doc, f"Pinion bracket {key}", ctx["step"], frame["origin"], frame["axes"]
        )
        for key, frame in ctx["frames"].items()
    }
    groups = {"flat": [models["flat_1"], models["flat_2"]], "edge": [models["edge"]]}
    ops: dict[str, Any] = {}
    for section in ctx["jobs"]:
        target = rt.job(
            doc, section["label"], groups[section["frame"]], section["stock"]
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
